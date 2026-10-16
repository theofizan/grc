"""Check the capture gate, hardware-adapter failures, and JSON command records."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from antenna_steering import MockSteeringBackend, Pointing, SteeringController


class AlteredAckBackend(MockSteeringBackend):
    def __init__(self, **changes):
        self.changes = changes
        self.calls = 0

    def apply(self, command, *, timeout_seconds):
        self.calls += 1
        return replace(super().apply(command, timeout_seconds=timeout_seconds), **self.changes)


class SteeringTests(unittest.TestCase):
    def controller(self, backend=None, **kwargs):
        return SteeringController(backend or MockSteeringBackend(), settle_seconds=0, **kwargs)

    def test_mock_result_is_explicitly_simulated_and_correlated(self):
        result = self.controller().steer(20, 5, calibration_id="example-calibration")
        self.assertTrue(result.simulated)
        self.assertEqual(result.command.pointing, Pointing(20, 5))
        self.assertEqual(result.command.command_id, result.acknowledgement.command_id)
        self.assertEqual(result.command.calibration_id, "example-calibration")
        self.assertEqual(result.to_dict()["status"], "ready")
        json.dumps(result.to_dict(), allow_nan=False)

    def test_invalid_angles_never_reach_backend(self):
        backend = AlteredAckBackend()
        controller = self.controller(backend)
        for az, el in ((91, 0), (0, -46), (float("nan"), 0), (0, float("inf"))):
            with self.subTest(az=az, el=el), self.assertRaises(ValueError):
                controller.steer(az, el)
        self.assertEqual(backend.calls, 0)

    def test_invalid_frequencies_never_reach_backend(self):
        backend = AlteredAckBackend()
        for frequency in (0, -1, float("nan"), float("inf")):
            with self.subTest(frequency=frequency), self.assertRaises(ValueError):
                self.controller(backend).steer(0, center_frequency_hz=frequency)
        self.assertEqual(backend.calls, 0)

    def test_unaccepted_or_unready_ack_cannot_open_capture_gate(self):
        for change in ({"accepted": False}, {"ready": False}, {"ready": "false"}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.controller(AlteredAckBackend(**change)).steer(0)

    def test_ack_from_another_command_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "different command"):
            self.controller(AlteredAckBackend(command_id="stale")).steer(0)

    def test_bad_readback_is_not_treated_as_correct_pointing(self):
        with self.assertRaisesRegex(RuntimeError, "tolerance"):
            self.controller(AlteredAckBackend(reported_pointing=Pointing(3))).steer(0)

    def test_missing_readback_remains_missing(self):
        result = self.controller(AlteredAckBackend(reported_pointing=None)).steer(0)
        self.assertIsNone(result.acknowledgement.reported_pointing)

    def test_late_adapter_response_is_rejected(self):
        with patch("antenna_steering.time.monotonic", side_effect=[0, 6]):
            with self.assertRaises(TimeoutError):
                self.controller().steer(0)

    def test_extra_settling_precedes_ready_result(self):
        controller = SteeringController(MockSteeringBackend(), settle_seconds=0.25)
        with patch("antenna_steering.time.sleep") as sleep:
            with patch("antenna_steering.time.monotonic", side_effect=[10, 10.02, 10.27]):
                result = controller.steer(0)
        sleep.assert_called_once_with(0.25)
        self.assertAlmostEqual(result.elapsed_seconds, 0.27)

    def test_backend_timeout_propagates(self):
        backend = MockSteeringBackend()
        with patch.object(backend, "apply", side_effect=TimeoutError("No controller response")):
            with self.assertRaisesRegex(TimeoutError, "No controller response"):
                self.controller(backend).steer(0)

    def test_cli_records_success_and_invalid_request_as_json(self):
        script = Path(__file__).resolve().parents[1] / "antenna_steering.py"
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "steering.jsonl"
            for angle, exit_code in (("15", 0), ("nan", 1)):
                run = subprocess.run([sys.executable, str(script), "--azimuth", angle,
                                      "--log", str(log)], capture_output=True, text=True)
                self.assertEqual(run.returncode, exit_code, run.stderr)
                self.assertTrue(json.loads(run.stdout)["simulated"])
            records = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual([row["status"] for row in records], ["ready", "failed"])


if __name__ == "__main__":
    unittest.main()
