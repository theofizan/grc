"""Run the real GRC lab finitely; independently check delay and its BER branch."""

from pathlib import Path
import argparse
import json
import sys
import threading
import numpy as np
from scipy.io import savemat
from gnuradio import blocks
from PyQt5 import Qt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "grc/generated"))
import importlib

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--modulation",
    choices=["bpsk", "qpsk", "8psk", "4ask", "8ask", "16qam"],
    default="16qam",
)
parser.add_argument("--calibrate", action="store_true")
parser.add_argument(
    "--render-dashboards",
    action="store_true",
    help="Render native Qt dashboards offscreen for layout review",
)
parser.add_argument("--echo", type=float, default=0)
parser.add_argument("--noise", type=float, default=0)
parser.add_argument("--delay", type=int, default=136)
parser.add_argument("--tx-power-dbm", type=float, default=0)
parser.add_argument("--path-loss-db", type=float, default=80)
parser.add_argument("--rx-noise-dbm", type=float, default=None)
parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
args = parser.parse_args()
output_directory = args.output_dir
output_directory.mkdir(parents=True, exist_ok=True)
if args.rx_noise_dbm is not None:
    args.noise = 10 ** (
        (args.rx_noise_dbm - args.tx_power_dbm + args.path_loss_db) / 20
    )

np.random.seed(42)
app = Qt.QApplication([])
name = "single_carrier_" + args.modulation
lab = getattr(importlib.import_module(name), name)(
    channel_echo=args.echo,
    tx_power_dbm=args.tx_power_dbm,
    path_loss_db=args.path_loss_db,
    rx_noise_dbm=(
        args.tx_power_dbm - args.path_loss_db + 20 * np.log10(args.noise)
        if args.noise
        else -100
    ),
    noise_enabled=int(args.noise > 0),
    reference_delay=args.delay,
)
module = importlib.import_module(name)
module.snippets_main_after_init(lab)
app.processEvents()
tile_layouts = {}
for index in range(lab.views.count()):
    layout = getattr(lab, "views_grid_layout_" + str(index))
    tile_layouts[str(index)] = [
        layout.rowStretch(1),
        layout.rowStretch(2),
        layout.columnStretch(0),
        layout.columnStretch(1),
    ]
    assert tile_layouts[str(index)] == [1, 1, 1, 1]
    for row in (1, 2):
        for column in (0, 1):
            item = layout.itemAtPosition(row, column)
            assert item is not None and item.widget() is not None, "Missing plot tile"
if args.render_dashboards:
    lab.show()
square_panels = {}  # Retained only as an empty legacy JSON field.
lab.random_bytes.set_repeat(False)
lab.throttle.set_sample_rate(100e6)
captures = {}
for name, source, kind in [
    ("tx", lab.unpack_tx, "byte"),
    ("rx", lab.unpack_rx, "byte"),
    ("errors", lab.xor, "byte"),
    ("ber", lab.ber_scale, "float"),
]:
    sink = blocks.vector_sink_b() if kind == "byte" else blocks.vector_sink_f()
    lab.connect(source, sink)
    captures[name] = sink
# Capture symbols and the two stock EVM outputs for independent MATLAB checks.
symbol_capture = blocks.vector_sink_c()
evm_capture = blocks.vector_sink_f()
evm_rms_capture = blocks.vector_sink_f()
lab.connect(lab.equalizer, symbol_capture)
lab.connect(lab.evm, evm_capture)
lab.connect(lab.evm_rms, evm_rms_capture)
power_capture = blocks.vector_sink_c()
lab.connect(lab.tx_power, power_capture)
rx_power_capture = blocks.vector_sink_c()
lab.connect(lab.channel, rx_power_capture)
power_meters = {}
for label, source in [
    ("tx_dbm", lab.tx_dbm),
    ("rx_dbm", lab.rx_dbm),
    ("tx_peak_dbm", lab.tx_peak_dbm),
]:
    sink = blocks.vector_sink_f()
    lab.connect(source, sink)
    power_meters[label] = sink
tap_capture = blocks.vector_sink_c(vlen=lab.eq_taps)
lab.connect((lab.equalizer, 1), tap_capture)
pre_eq_capture = blocks.vector_sink_c()
lab.connect(lab.rx_scale, pre_eq_capture)
eye_captures = {}
for name, source in [
    ("middle_eye", lab.middle_eye_reconstruction),
    ("after_eye", lab.after_eye_reconstruction),
]:
    sink = blocks.vector_sink_c()
    lab.connect(source, sink)
    eye_captures[name] = sink
tx_symbol_capture = blocks.vector_sink_c()
lab.connect(lab.tx_symbols, tx_symbol_capture)
ratio_captures = {}
for label, source in [("snr", lab.rx_snr), ("ebno", lab.rx_ebno)]:
    sink = blocks.vector_sink_f()
    lab.connect(source, sink)
    ratio_captures[label] = sink
complete = threading.Event()


def wait():
    lab.wait()
    complete.set()


thread = threading.Thread(target=wait, daemon=True)
timer = Qt.QTimer()
timer.timeout.connect(lambda: app.quit() if complete.is_set() else None)
timer.start(20)
Qt.QTimer.singleShot(20000, app.quit)
lab.start()
thread.start()
app.exec_()
lab.stop()
thread.join(5)
assert complete.is_set(), "Finite graph did not finish"
tx = np.array(captures["tx"].data(), dtype=np.uint8)
rx = np.array(captures["rx"].data(), dtype=np.uint8)


# Positive lag means received bits arrive later than the TX reference.
def ber_at_delay(delay):
    count = min(len(tx), len(rx) - delay) - 4096
    return float(
        np.mean(tx[4096 : 4096 + count] != rx[4096 + delay : 4096 + delay + count])
    )


best_delay = min(range(512), key=ber_at_delay)
errors = np.array(captures["errors"].data())
display = np.array(captures["ber"].data())
# Check the actual XOR stream against independent TX/RX bit comparisons.
start = 4096
expected_errors = (
    tx[start - args.delay : start - args.delay + len(errors)]
    != rx[start : start + len(errors)]
)
np.testing.assert_array_equal(errors, expected_errors)
if args.noise == 0 and not args.calibrate:
    assert (
        args.delay == best_delay
    ), "Recalibrate the reference delay before scoring BER"
    assert not np.any(errors), "Noiseless aligned link must have zero bit errors"
count = len(display) * 10000
expected = errors[:count].reshape(-1, 10000).mean(axis=1)
np.testing.assert_allclose(display, expected, atol=1e-6)
symbols = np.asarray(symbol_capture.data(), dtype=np.complex64)
constellation_points = np.asarray(lab.const.points(), dtype=np.complex64)
evm_percent = np.asarray(evm_capture.data())
evm_rms_percent = np.asarray(evm_rms_capture.data())
nearest = np.min(abs(symbols[:, None] - constellation_points[None, :]) ** 2, axis=1)
expected_evm = 100 * np.sqrt(nearest / np.mean(abs(constellation_points) ** 2))
np.testing.assert_allclose(evm_percent, expected_evm, atol=2e-4, rtol=2e-6)
# Calibrate physical units from the actual IQ samples, not the symbol labels.
tx_iq = np.asarray(power_capture.data(), dtype=np.complex64)
rx_iq = np.asarray(rx_power_capture.data(), dtype=np.complex64)
tx_avg_mw = float(np.mean(abs(tx_iq[4096:]) ** 2))
rx_avg_mw = float(np.mean(abs(rx_iq[4096:]) ** 2))
tx_measured_dbm = 10 * np.log10(tx_avg_mw)
rx_measured_dbm = 10 * np.log10(rx_avg_mw)
tx_sample_peak_dbm = float(10 * np.log10(np.max(abs(tx_iq[4096:]) ** 2)))
assert (
    abs(tx_measured_dbm - args.tx_power_dbm) < 0.05
), "TX average power calibration failed"
expected_rx_mw = 10 ** ((args.tx_power_dbm - args.path_loss_db) / 10) * (
    1 + args.noise**2
)
assert (
    abs(rx_measured_dbm - 10 * np.log10(expected_rx_mw)) < 0.08
), "RX link budget power failed"
for label, iq in [("tx_dbm", tx_iq), ("rx_dbm", rx_iq)]:
    meter = np.asarray(power_meters[label].data())
    expected = 10 * np.log10(
        np.mean(abs(iq[: len(meter) * 4096].reshape(-1, 4096)) ** 2, axis=1)
    )
    np.testing.assert_allclose(meter, expected, atol=1e-3)
peak_windows = np.asarray(power_meters["tx_peak_dbm"].data())
expected_peak_windows = 10 * np.log10(
    np.max(abs(tx_iq[: len(peak_windows) * 4096].reshape(-1, 4096)) ** 2, axis=1)
)
np.testing.assert_allclose(peak_windows, expected_peak_windows, atol=1e-3)
pre_eq_symbols = np.asarray(pre_eq_capture.data(), dtype=np.complex64)
final_eq_taps = np.asarray(lab.equalizer.taps(), dtype=np.complex64)
assert np.all(np.isfinite(symbols)) and np.all(
    np.isfinite(final_eq_taps)
), "Equalizer diverged"
assert len(final_eq_taps) == lab.eq_taps
tx_symbols = np.asarray(tx_symbol_capture.data(), dtype=np.complex64)
symbol_delay = best_delay // lab.k
rx_start = 1024 + symbol_delay
aligned_count = min(len(tx_symbols) - 1024, len(symbols) - rx_start)
aligned_tx_symbols = tx_symbols[1024 : 1024 + aligned_count]
aligned_rx_symbols = symbols[rx_start : rx_start + aligned_count]
reference_evm_percent = float(
    100
    * np.sqrt(
        np.mean(abs(aligned_rx_symbols - aligned_tx_symbols) ** 2)
        / np.mean(abs(aligned_tx_symbols) ** 2)
    )
)
for label, offset in [
    ("snr", 0),
    ("ebno", 10 * np.log10(lab.samp_rate / lab.bit_rate)),
]:
    observed = np.asarray(ratio_captures[label].data())
    expected = (
        np.asarray(power_meters["tx_dbm"].data())
        - args.path_loss_db
        - lab.rx_noise_dbm
        + offset
        if lab.noise_enabled
        else np.full(len(observed), np.inf)
    )
    np.testing.assert_allclose(observed, expected, atol=1e-4)
pre_delay = 29
pre_start = 1024 + pre_delay
pre_count = min(len(tx_symbols) - 1024, len(pre_eq_symbols) - pre_start)
pre_reference_evm_percent = float(
    100
    * np.sqrt(
        np.mean(
            abs(
                pre_eq_symbols[pre_start : pre_start + pre_count]
                - tx_symbols[1024 : 1024 + pre_count]
            )
            ** 2
        )
        / np.mean(abs(tx_symbols[1024 : 1024 + pre_count]) ** 2)
    )
)
tap_history = np.asarray(tap_capture.data(), dtype=np.complex64).reshape(
    -1, lab.eq_taps
)
check_count = min(16384, len(symbols), len(pre_eq_symbols), len(tap_history))
window = np.lib.stride_tricks.sliding_window_view(
    np.pad(pre_eq_symbols[:check_count], (lab.eq_taps - 1, 0)), lab.eq_taps
)
filter_forward = np.sum(window * tap_history[:check_count], axis=1)
filter_reverse = np.sum(window[:, ::-1] * tap_history[:check_count], axis=1)
forward_error = float(np.max(abs(filter_forward - symbols[:check_count])))
reverse_error = float(np.max(abs(filter_reverse - symbols[:check_count])))
tap_history_oldest_first = forward_error < reverse_error
expected_eq = filter_forward if tap_history_oldest_first else filter_reverse
np.testing.assert_allclose(expected_eq, symbols[:check_count], atol=2e-5)
fixture_name = f"{args.modulation}_noise_{args.noise:g}.mat"
savemat(
    output_directory / fixture_name,
    dict(
        eq_input_excerpt=pre_eq_symbols[:check_count, None],
        eq_output_excerpt=symbols[:check_count, None],
        eq_tap_history=tap_history[:check_count],
        eq_taps_oldest_first=int(tap_history_oldest_first),
        pre_eq_symbols=pre_eq_symbols[:, None],
        equalizer_final_taps=final_eq_taps[:, None],
        middle_eye_waveform=np.asarray(eye_captures["middle_eye"].data())[:16384, None],
        after_eye_waveform=np.asarray(eye_captures["after_eye"].data())[:16384, None],
        eye_reconstruction_taps=np.asarray(lab.eye_synthesis_taps)[:, None],
        channel_echo=args.echo,
        pre_reference_evm_percent=pre_reference_evm_percent,
        tx_symbols=tx_symbols[:, None],
        aligned_tx_symbols=aligned_tx_symbols[:, None],
        aligned_rx_symbols=aligned_rx_symbols[:, None],
        tile_layouts=np.asarray(list(tile_layouts.values()), dtype=int),
        reference_evm_percent=reference_evm_percent,
        nominal_rx_snr_db=lab.snr_rx_db,
        nominal_rx_ebno_db=lab.ebno_rx_db,
        measured_rx_snr_windows_db=np.asarray(ratio_captures["snr"].data())[:, None],
        measured_rx_ebno_windows_db=np.asarray(ratio_captures["ebno"].data())[:, None],
        evm_guide_percent=lab.evm_guide_percent,
        tx_iq=tx_iq[:, None],
        rx_iq=rx_iq[:, None],
        tx_power_windows_dbm=np.asarray(power_meters["tx_dbm"].data())[:, None],
        rx_power_windows_dbm=np.asarray(power_meters["rx_dbm"].data())[:, None],
        tx_power_dbm=args.tx_power_dbm,
        path_loss_db=args.path_loss_db,
        rx_noise_dbm=float(lab.rx_noise_dbm),
        noise_enabled=int(lab.noise_enabled),
        tx_measured_dbm=tx_measured_dbm,
        rx_measured_dbm=rx_measured_dbm,
        tx_peak_windows_dbm=np.asarray(power_meters["tx_peak_dbm"].data())[:, None],
        tx_sample_peak_dbm=tx_sample_peak_dbm,
        tx_bits=tx[:, None],
        rx_bits=rx[:, None],
        xor_errors=errors[:, None],
        ber_windows=display[:, None],
        received_symbols=symbols[:, None],
        constellation_points=constellation_points[:, None],
        evm_percent=evm_percent[:, None],
        evm_rms_percent=evm_rms_percent[:, None],
        reference_delay_bits=args.delay,
        warmup_bits=4096,
        ber_window_bits=10000,
        symbol_rate_hz=float(lab.symbol_rate),
        sample_rate_hz=float(lab.samp_rate),
        bits_per_symbol=int(lab.k),
        gross_bit_rate_bps=float(lab.bit_rate),
        rrc_bandwidth_hz=float(lab.rrc_bandwidth),
    ),
    do_compression=True,
)
result = dict(
    tx_power_dbm=args.tx_power_dbm,
    path_loss_db=args.path_loss_db,
    rx_noise_dbm=float(lab.rx_noise_dbm),
    noise_enabled=int(lab.noise_enabled),
    tx_measured_dbm=tx_measured_dbm,
    rx_measured_dbm=rx_measured_dbm,
    expected_rx_signal_dbm=args.tx_power_dbm - args.path_loss_db,
    tx_sample_peak_dbm=tx_sample_peak_dbm,
    papr_db=tx_sample_peak_dbm - tx_measured_dbm,
    tile_layouts=tile_layouts,
    reference_evm_percent=reference_evm_percent,
    nominal_rx_snr_db=lab.snr_rx_db if lab.noise_enabled else None,
    nominal_rx_ebno_db=lab.ebno_rx_db if lab.noise_enabled else None,
    square_plot_panels=square_panels,
    channel_echo=args.echo,
    pre_reference_evm_percent=pre_reference_evm_percent,
    equalizer_final_taps=[[float(t.real), float(t.imag)] for t in final_eq_taps],
    modulation=args.modulation,
    noise_voltage=args.noise,
    configured_delay_bits=args.delay,
    best_delay_bits=best_delay,
    aligned_ber=ber_at_delay(best_delay),
    display_ber_mean=float(display.mean()),
    compared_bits=count,
    ber_windows=len(display),
    stock_ber_arithmetic="XOR -> UChar to Float -> Integrate(10000) -> Multiply(1/10000)",
    finite_completed=True,
    symbol_rate_hz=float(lab.symbol_rate),
    sample_rate_hz=float(lab.samp_rate),
    gross_bit_rate_bps=float(lab.bit_rate),
    decision_directed_evm_rms_percent=float(np.sqrt(np.mean(evm_percent[4096:] ** 2))),
    matlab_fixture=fixture_name,
    tx_mean_sample_power=float(
        np.mean(abs(np.array(power_capture.data())[4096:]) ** 2)
    ),
)
print(json.dumps(result, indent=2))
(ROOT / "results").mkdir(exist_ok=True)
(output_directory / f"{args.modulation}_noise_{args.noise:g}.json").write_text(
    json.dumps(result, indent=2) + "\n"
)
if args.render_dashboards:
    for index in range(lab.views.count()):
        lab.views.setCurrentIndex(index)
        wait_for_paint = Qt.QEventLoop()
        Qt.QTimer.singleShot(200, wait_for_paint.quit)
        wait_for_paint.exec_()
        lab.grab().save(str(ROOT / "results" / f"live_dashboard_{index}.png"))
lab.close()
