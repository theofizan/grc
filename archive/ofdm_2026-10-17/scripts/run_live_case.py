"""Execute a FINITE generated Qt GRC lab with its actual sinks/event loop.

Set QT_QPA_PLATFORM=offscreen for automated testing; omit it for a desktop run.
Does not start hardware graphs. Each case archives exact counts and fixtures.
"""

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import numpy as np
from scipy.io import savemat
from scipy.signal import lfilter
from gnuradio import blocks
from PyQt5 import Qt
from antenna_bench.math import score, exact_ber
from antenna_bench.live import wlan_reference, parse_taps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "grc/generated"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["modem", "wlan"], default="modem")
    parser.add_argument("--order", type=int, default=16)
    parser.add_argument("--ebno-db", type=float, default=8)
    parser.add_argument("--rate-index", type=int, default=2)
    parser.add_argument("--snr-db", type=float, default=25)
    parser.add_argument("--path-loss-db", type=float, default=0)
    parser.add_argument("--cfo-hz", type=float, default=0)
    parser.add_argument("--channel-taps", default="1+0j")
    parser.add_argument("--correct-cfo", type=int, default=1)
    parser.add_argument("--pilot-tracking", type=int, default=1)
    parser.add_argument("--symbol-count", type=int, default=100000)
    parser.add_argument("--packet-count", type=int, default=8)
    parser.add_argument("--case-id", default="example")
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument(
        "--replay-capture",
        type=Path,
        help="Receiver control: replay identical stored RX waveform",
    )
    args = parser.parse_args()
    if not args.case_id.replace("_", "").replace("-", "").isalnum():
        parser.error("Use a simple case ID")
    if args.packet_count <= 0 or args.symbol_count <= 0:
        parser.error("Finite counts must be positive")
    app = Qt.QApplication([])
    name = "siso_" + args.mode + "_lab"
    cls = getattr(importlib.import_module(name), name)
    kwargs = dict(path_loss_db=args.path_loss_db, pace=100e6)
    if args.mode == "modem":
        kwargs.update(
            order=args.order, ebno_db=args.ebno_db, symbol_count=args.symbol_count
        )
        expected_symbols = args.symbol_count
        order = args.order
    else:
        kwargs.update(
            rate_index=args.rate_index,
            snr_db=args.snr_db,
            packet_count=args.packet_count,
            cfo_hz=args.cfo_hz,
            channel_taps=args.channel_taps,
            correct_cfo=args.correct_cfo,
            pilot_tracking=args.pilot_tracking,
        )
        reference = wlan_reference(args.rate_index)
        expected_symbols = reference["reference_symbols"].size * args.packet_count
        order = int(reference["order"])
    tb = cls(**kwargs)
    destination = ROOT / "results/live/cases" / args.case_id
    destination.mkdir(parents=True, exist_ok=True)
    tb.ber_meter.set_report_path(destination / "ber.json")
    tb.evm_meter.set_report_path(destination / "evm.json")
    if args.mode == "wlan":
        tb.burst_receiver.set_report_path(destination / "receiver.json")
    channel_source = tb.channel_output
    if args.replay_capture:
        assert args.mode == "wlan"
        replay = np.load(args.replay_capture)["rx_waveform"]
        tb.disconnect((tb.channel_output, 0), (tb.extract_bursts, 0))
        tb.disconnect((tb.channel_output, 0), (tb.rx_scope, 0))
        discarded = blocks.null_sink(8)
        tb.connect(tb.channel_output, discarded)
        channel_source = blocks.vector_source_c(replay.tolist(), False)
        tb.connect(channel_source, tb.extract_bursts)
        tb.connect(channel_source, tb.rx_scope)
    taps = {}
    for key, source in [
        ("reference", "mapper" if args.mode == "modem" else "finite_reference"),
        ("equalized", "equalize" if args.mode == "modem" else "burst_receiver"),
        ("tx_waveform", "pace_tx"),
        ("rx_waveform", "channel_output"),
    ]:
        sink = blocks.vector_sink_c()
        tb.connect(
            (channel_source if key == "rx_waveform" else getattr(tb, source), 0), sink
        )
        taps[key] = sink
    for key, source in [
        ("tx_bits", "finite_bits" if args.mode == "modem" else "tx_bits"),
        ("rx_bits", "rx_bits"),
    ]:
        sink = blocks.vector_sink_b()
        tb.connect((getattr(tb, source), 0), sink)
        taps[key] = sink
    completed = threading.Event()
    started = time.monotonic()
    timed_out = []

    def wait():
        tb.wait()
        completed.set()

    def poll():
        if completed.is_set():
            app.quit()
        elif time.monotonic() - started > 30:
            timed_out.append(True)
            tb.stop()
            app.quit()

    timer = Qt.QTimer()
    timer.timeout.connect(poll)
    timer.start(20)
    tb.start()
    waiter = threading.Thread(target=wait, daemon=True)
    waiter.start()
    app.exec_()
    tb.stop()
    waiter.join(timeout=5)
    assert (
        not timed_out and completed.is_set()
    ), "Finite GUI flowgraph failed to terminate"
    arrays = {
        key: np.asarray(
            sink.data(), dtype=np.uint8 if key.endswith("bits") else np.complex64
        )
        for key, sink in taps.items()
    }
    # Require the block's real stop callback to have written the files. The
    # automated test must not silently perform the GUI's promised save itself.
    ber = json.loads((destination / "ber.json").read_text())
    evm = json.loads((destination / "evm.json").read_text())
    assert ber == tb.ber_meter.statistics() and evm == tb.evm_meter.statistics()
    expected_bits = expected_symbols * int(np.log2(order))
    assert (
        len(arrays["reference"])
        == len(arrays["equalized"])
        == evm["symbols"]
        == expected_symbols
    )
    assert (
        len(arrays["tx_bits"]) == len(arrays["rx_bits"]) == ber["bits"] == expected_bits
    )
    assert ber["errors"] == int(
        np.count_nonzero(arrays["tx_bits"] != arrays["rx_bits"])
    )
    independent = score(arrays["reference"], arrays["equalized"], order)
    assert independent["errors"] == ber["errors"] and independent["bits"] == ber["bits"]
    np.testing.assert_allclose(independent["evm_rms"], evm["evm_rms"], atol=1e-12)
    np.testing.assert_allclose(
        np.mean(
            abs(
                arrays["tx_waveform"]
                if args.mode == "modem"
                else reference["tx_packet"]
            )
            ** 2
        ),
        1,
        atol=0.02,
    )
    receiver = (
        json.loads((destination / "receiver.json").read_text())
        if args.mode == "wlan"
        else None
    )
    if receiver:
        assert (
            receiver["bursts"] == args.packet_count
            and receiver["partial_input_samples"]
            == receiver["pending_output_symbols"]
            == 0
        )
    assert (
        arrays["tx_waveform"].size == arrays["rx_waveform"].size
    ), "Channel dropped samples"
    h = 10 ** (-args.path_loss_db / 20)
    clean = (
        lfilter(
            [h * t for t in parse_taps(args.channel_taps)],
            [1],
            arrays["tx_waveform"].astype(complex),
        )
        * np.exp(
            2j * np.pi * args.cfo_hz * np.arange(arrays["tx_waveform"].size) / 20e6
        )
        if receiver
        else h * arrays["tx_waveform"]
    )
    noise_power = float(np.mean(abs(arrays["rx_waveform"] - clean) ** 2))
    expected_noise = (
        10 ** (-args.snr_db / 10)
        if receiver
        else 1 / (np.log2(order) * 10 ** (args.ebno_db / 10))
    )
    if expected_noise > 1e-10:
        assert (
            abs(noise_power / expected_noise - 1) < 0.04
        ), "Channel noise calibration failed"
    theory = None
    if args.mode == "modem":
        theory = float(exact_ber(order, args.ebno_db - args.path_loss_db))
        bound = (
            6 * np.sqrt(theory * (1 - theory) / expected_symbols) + 1 / expected_bits
        )
        assert abs(ber["ber"] - theory) < bound
        expected_variance = 1 / (
            np.log2(order) * 10 ** ((args.ebno_db - args.path_loss_db) / 10)
        )
        assert (
            abs(independent["error_energy"] / expected_symbols / expected_variance - 1)
            < 0.03
        )
    parameters = vars(args).copy()
    parameters["replay_capture"] = (
        str(args.replay_capture) if args.replay_capture else None
    )
    report = dict(
        status="passed",
        case=parameters,
        siso=dict(tx_channels=1, rx_channels=1),
        ber=ber,
        evm=evm,
        receiver=receiver,
        theory_ber=theory,
        power=dict(
            tx_active_mean=(
                float(np.mean(abs(reference["tx_packet"]) ** 2))
                if receiver
                else float(np.mean(abs(arrays["tx_waveform"]) ** 2))
            ),
            tx_peak=float(np.max(abs(arrays["tx_waveform"]))),
            measured_awgn_power=noise_power,
            configured_awgn_power=expected_noise,
            units="normalized simulation sample power; not dBm",
        ),
        qt_widgets=dict(
            constellation=True,
            frequency=True,
            waterfall=True,
            time=True,
            numeric_ber=True,
            numeric_evm=True,
        ),
        qt_backend=os.environ.get("QT_QPA_PLATFORM", "desktop"),
        elapsed_seconds=time.monotonic() - started,
    )
    (destination / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    fixture = dict(
        tx=arrays["reference"][:, None],
        rx=arrays["equalized"][:, None],
        order=order,
        python_errors=ber["errors"],
        python_bits=ber["bits"],
        python_evm=evm["evm_rms"],
    )
    if receiver:
        fixture.update(
            reference={k: v for k, v in reference.items() if not k.startswith("__")},
            received_packet=arrays["rx_waveform"][: len(reference["tx_packet"])][
                :, None
            ],
            correct_cfo=args.correct_cfo,
            pilot_tracking=args.pilot_tracking,
        )
    savemat(destination / "live_fixture.mat", fixture)
    if args.snapshot:
        np.savez_compressed(destination / "capture.npz", **arrays)
    print(
        json.dumps(
            dict(
                status="passed",
                case=args.case_id,
                bits=ber["bits"],
                errors=ber["errors"],
                ber=ber["ber"],
                evm_percent=evm["evm_percent"],
            )
        )
    )
    tb.close()


if __name__ == "__main__":
    main()
