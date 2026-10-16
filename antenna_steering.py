"""Steering interface for a measurement runner; CLI uses simulation only.

Coordinates are antenna-local: +x is boresight, +azimuth turns toward +y,
and +elevation turns toward +z. Angles describe the requested beam direction,
not necessarily mechanical rotation. A hardware adapter must map these angles
and RF frequency to its calibrated phase states, beam codebook, or positioner.

Implement SteeringBackend.apply() to send the actual controller command and
wait for its matching acknowledgement/readiness. Transport timeouts must be
implemented inside the adapter; this synchronous wrapper cannot interrupt a
blocked driver. No device wire protocol or address is assumed here.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import threading
import time
from typing import Protocol
from uuid import uuid4


def _finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Pointing:
    azimuth_deg: float
    elevation_deg: float = 0.0

    def __post_init__(self) -> None:
        _finite(self.azimuth_deg, "azimuth_deg")
        _finite(self.elevation_deg, "elevation_deg")


@dataclass(frozen=True)
class SteeringCommand:
    command_id: str
    requested_utc: str
    pointing: Pointing
    center_frequency_hz: float
    calibration_id: str | None = None


@dataclass(frozen=True)
class SteeringAck:
    command_id: str
    accepted: bool
    ready: bool
    # Controller readback is not a measured far-field beam direction.
    reported_pointing: Pointing | None = None
    beam_id: str | None = None
    detail: str = ""


class SteeringBackend(Protocol):
    name: str
    simulated: bool

    def apply(self, command: SteeringCommand, *, timeout_seconds: float) -> SteeringAck:
        """Send, correlate acknowledgement, and await ready within the timeout.

        Return accepted=False on rejection, or raise on transport/controller
        failure. A send-only acknowledgement is not ready. Drivers without a
        ready indication must define and validate their readiness policy.
        """
        ...


class MockSteeringBackend:
    """Exercise orchestration without sending anything to hardware."""

    name = "mock"
    simulated = True

    def apply(self, command: SteeringCommand, *, timeout_seconds: float) -> SteeringAck:
        return SteeringAck(
            command.command_id, accepted=True, ready=True,
            reported_pointing=command.pointing, beam_id="mock",
            detail="Simulated acknowledgement and pointing; no hardware command sent",
        )


@dataclass(frozen=True)
class SteeringResult:
    command: SteeringCommand
    acknowledgement: SteeringAck
    backend: str
    simulated: bool
    ready_utc: str
    elapsed_seconds: float
    settle_seconds: float

    def to_dict(self) -> dict:
        return {"schema_version": 1, "status": "ready", **asdict(self)}


class SteeringController:
    """Validate commands and return only after readiness and extra settling.

    A runner must keep acquisition stopped during steer(), attach the result
    to its capture, and reject simulated results for physical-radio runs.
    Serialize steering and capture in the runner: the lock here protects
    steering requests only, not a later measurement interval.
    """

    def __init__(
        self, backend: SteeringBackend, *,
        azimuth_limits_deg: tuple[float, float] = (-90.0, 90.0),
        elevation_limits_deg: tuple[float, float] = (-45.0, 45.0),
        pointing_tolerance_deg: float = 0.5,
        settle_seconds: float = 0.25,
        timeout_seconds: float = 5.0,
    ) -> None:
        for name, limits in (("azimuth", azimuth_limits_deg), ("elevation", elevation_limits_deg)):
            if len(limits) != 2:
                raise ValueError(f"{name} limits require a lower and upper bound")
            for bound in limits:
                _finite(bound, f"{name} limit")
            if limits[0] > limits[1]:
                raise ValueError(f"{name} limits must be ordered")
        for name, value in (("pointing_tolerance_deg", pointing_tolerance_deg),
                            ("settle_seconds", settle_seconds), ("timeout_seconds", timeout_seconds)):
            _finite(value, name)
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if timeout_seconds <= settle_seconds:
            raise ValueError("timeout_seconds must exceed settle_seconds")
        self.backend = backend
        self.azimuth_limits_deg = tuple(azimuth_limits_deg)
        self.elevation_limits_deg = tuple(elevation_limits_deg)
        self.pointing_tolerance_deg = pointing_tolerance_deg
        self.settle_seconds = settle_seconds
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()

    def steer(
        self, azimuth_deg: float, elevation_deg: float = 0.0, *,
        center_frequency_hz: float = 5.18e9,
        calibration_id: str | None = None,
    ) -> SteeringResult:
        pointing = Pointing(azimuth_deg, elevation_deg)
        for name, value, bounds in (
            ("azimuth", pointing.azimuth_deg, self.azimuth_limits_deg),
            ("elevation", pointing.elevation_deg, self.elevation_limits_deg),
        ):
            if not bounds[0] <= value <= bounds[1]:
                raise ValueError(f"{name} {value} is outside configured limits {bounds}")
        _finite(center_frequency_hz, "center_frequency_hz")
        if center_frequency_hz <= 0:
            raise ValueError("center_frequency_hz must be positive")
        with self._lock:
            command = SteeringCommand(str(uuid4()), _utc_now(), pointing,
                                      center_frequency_hz, calibration_id)
            started = time.monotonic()
            ack = self.backend.apply(
                command, timeout_seconds=self.timeout_seconds - self.settle_seconds,
            )
            elapsed = time.monotonic() - started
            if elapsed + self.settle_seconds >= self.timeout_seconds:
                raise TimeoutError("Steering exceeded the command/settling time budget")
            if ack.command_id != command.command_id:
                raise RuntimeError("Steering acknowledgement belongs to a different command")
            if ack.accepted is not True or ack.ready is not True:
                raise RuntimeError(f"Steering was rejected or is not ready: {ack.detail}")
            if ack.reported_pointing is not None:
                for axis in ("azimuth_deg", "elevation_deg"):
                    error = abs(getattr(ack.reported_pointing, axis) - getattr(pointing, axis))
                    if error > self.pointing_tolerance_deg:
                        raise RuntimeError(f"Controller readback outside {axis} tolerance")
            time.sleep(self.settle_seconds)
            elapsed = time.monotonic() - started
            if elapsed >= self.timeout_seconds:
                raise TimeoutError("Steering did not finish settling before the deadline")
            return SteeringResult(command, ack, self.backend.name, self.backend.simulated,
                                  _utc_now(), elapsed, self.settle_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview a steering command with a mock backend")
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "configs/wifi_nonht_defaults.json")
    parser.add_argument("--azimuth", type=float, required=True)
    parser.add_argument("--elevation", type=float, default=0.0)
    parser.add_argument("--frequency-hz", type=float)
    parser.add_argument("--log", type=Path, help="Append this attempt as one JSONL record")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        settings = config["steering"]
        if settings["backend"] != "mock":
            raise ValueError("CLI supports mock only; connect a hardware adapter through the Python API")
        controller = SteeringController(
            MockSteeringBackend(),
            **{key: settings[key] for key in (
                "azimuth_limits_deg", "elevation_limits_deg", "pointing_tolerance_deg",
                "settle_seconds", "timeout_seconds",
            )},
        )
        frequency = args.frequency_hz if args.frequency_hz is not None else config["radio"]["center_frequency_hz"]
        result = controller.steer(args.azimuth, args.elevation,
                                  center_frequency_hz=frequency,
                                  calibration_id=settings["calibration_id"])
        record = result.to_dict()
        exit_code = 0
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        record = {"schema_version": 1, "status": "failed", "simulated": True,
                  "requested_utc": _utc_now(),
                  "requested_arguments": {"azimuth": str(args.azimuth),
                                          "elevation": str(args.elevation),
                                          "frequency_hz": str(args.frequency_hz)},
                  "error": str(exc)}
        exit_code = 1
    encoded = json.dumps(record, allow_nan=False)
    if args.log:
        with args.log.open("a") as stream:
            stream.write(encoded + "\n")
    print(encoded)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
