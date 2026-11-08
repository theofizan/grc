"""Exercise the generated N210 flowcharts without hardware.

The two UHD blocks are replaced at run time by stand-ins: the TX stand-in
records the exact samples the flowchart would send to the N210, and the RX
stand-in plays them back after a synthetic over-the-air channel with an
unknown integer + fractional delay and the offsets of two free-running N210
oscillators (3 kHz carrier offset, 2 ppm sample-clock offset), an arbitrary
carrier phase, -40 dB gain, and AWGN. Everything between the two UHD blocks
is the real generated flowchart: AGC, FLL, timing recovery, preamble
detection, Costas loop, the preamble-trained equalizer, and BER.

Pass/fail uses BER against the true transmitted bits, and also requires the
BER the flowchart itself displays to agree with it.

Writes results/n210_loopback_check.json. This is not a hardware test.
"""

from pathlib import Path
import importlib
import json
import os
import subprocess
import sys
import time
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from gnuradio import blocks, gr, uhd  # noqa: E402
from PyQt5 import Qt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_n210 import DATA_BYTES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "grc/generated"
PROFILES = ["bpsk", "qpsk", "8psk", "4ask", "8ask", "16qam"]
CHANNEL = dict(delay_samples=12345.37, cfo_hz=3000.0, clock_offset_ppm=2.0,
               phase_deg=137.0, gain_db=-40.0, esno_db=25.0)


class StandIn(gr.hier_block2):
    """Accepts every UHD setter as a no-op around one real GNU Radio block."""

    def __init__(self, inner, is_sink):
        item = gr.io_signature(1, 1, gr.sizeof_gr_complex)
        none = gr.io_signature(0, 0, 0)
        gr.hier_block2.__init__(self, "uhd_stand_in",
                                item if is_sink else none, none if is_sink else item)
        self.inner = inner
        if is_sink:
            self.connect(self, inner)
        else:
            self.connect(inner, self)

    def __getattr__(self, name):
        if name.startswith(("set_", "get_")):
            return lambda *args, **kwargs: None
        raise AttributeError(name)


def build(profile, sink_block, source_block, **parameters):
    module = importlib.import_module(f"n210_{profile}")
    module.uhd.usrp_sink = lambda *a, **k: StandIn(sink_block, True)
    module.uhd.usrp_source = lambda *a, **k: StandIn(source_block, False)
    parameters.setdefault("settle_s", 0.0)  # short recordings: no extra settling
    lab = getattr(module, f"n210_{profile}")(**parameters)
    return lab


def run_until(lab, done, timeout_s):
    lab.start()
    start = time.time()
    while not done() and time.time() - start < timeout_s:
        time.sleep(0.2)
    lab.stop()
    lab.wait()


def over_the_air(tx, fs, rng):
    n = np.arange(len(tx) + int(CHANNEL["delay_samples"]) + 1000)
    t = n * (1 + CHANNEL["clock_offset_ppm"] * 1e-6) - CHANNEL["delay_samples"]
    delayed = (np.interp(t, np.arange(len(tx)), tx.real, left=0, right=0)
               + 1j * np.interp(t, np.arange(len(tx)), tx.imag, left=0, right=0))
    rotation = np.exp(1j * (2 * np.pi * CHANNEL["cfo_hz"] * n / fs
                            + np.radians(CHANNEL["phase_deg"])))
    gain = 10 ** (CHANNEL["gain_db"] / 20)
    rx = gain * delayed * rotation
    signal_power = np.mean(abs(gain * tx) ** 2)
    noise_power = signal_power * 4 / 10 ** (CHANNEL["esno_db"] / 10)  # 4 samples/symbol
    rx += np.sqrt(noise_power / 2) * (rng.standard_normal(rx.size)
                                     + 1j * rng.standard_normal(rx.size))
    return rx.astype(np.complex64)


def true_ber(rx_bits, start=50_000, span=200_000):
    """BER against the actual transmitted data, aligned by cross-correlation."""
    data = np.unpackbits(np.random.RandomState(42).randint(0, 256, DATA_BYTES).astype(np.uint8))
    tx_bits = np.tile(data, 6)
    segment = 2.0 * rx_bits[start:start + 20_000] - 1
    reference = 2.0 * tx_bits[:2 * data.size] - 1
    correlation = np.fft.irfft(np.fft.rfft(reference)
                               * np.conj(np.fft.rfft(segment, reference.size)), reference.size)
    lag = int(np.argmax(correlation))
    compared = rx_bits[start:start + span]
    return float(np.mean(compared != tx_bits[lag:lag + compared.size]))


def check(profile):
    app = Qt.QApplication.instance() or Qt.QApplication([])
    bits_needed = 3 * 8 * DATA_BYTES + 80_000
    probe = build(profile, blocks.null_sink(gr.sizeof_gr_complex),
                  blocks.null_source(gr.sizeof_gr_complex))
    k, sps, fs = int(probe.k), int(probe.sps), float(probe.samp_rate)
    tx_samples = bits_needed // k * sps
    tx_capture = blocks.vector_sink_c()
    lab = build(profile, tx_capture, blocks.null_source(gr.sizeof_gr_complex))
    run_until(lab, lambda: len(tx_capture.data()) >= tx_samples, 120)
    tx = np.asarray(tx_capture.data()[:tx_samples])
    tx_rms_dbfs = 10 * np.log10(np.mean(abs(tx) ** 2))
    tx_peak_dbfs = 10 * np.log10(np.max(abs(tx) ** 2))
    rx = over_the_air(tx, fs, np.random.default_rng(7))

    lab = build(profile, blocks.null_sink(gr.sizeof_gr_complex),
                blocks.vector_source_c(rx.tolist(), False))
    ber = blocks.vector_sink_f()
    mer = blocks.vector_sink_f()
    bits = blocks.vector_sink_b()
    lab.connect(lab.ber_scale, ber)
    lab.connect(lab.rx_snr, mer)
    lab.connect(lab.unpack_rx, bits)
    progress = dict(count=-1, since=time.time())

    def finished():  # playback is finite; stop once BER output stops growing
        count = len(ber.data())
        if count != progress["count"]:
            progress.update(count=count, since=time.time())
        return count > 0 and time.time() - progress["since"] > 3

    run_until(lab, finished, 300)
    app.processEvents()
    values = np.asarray(ber.data())
    mer_values = np.asarray(mer.data())
    displayed = float(np.median(values[len(values) // 2:]))
    rx_bits = np.asarray(bits.data())
    # Score after acquisition (AGC, Costas, and equalizer training settle
    # within the first data period); the second half of the capture is used.
    measured = true_ber(rx_bits, start=rx_bits.size // 2, span=rx_bits.size // 2 - 30_000)
    return dict(modulation=profile, tx_rms_dbfs=round(tx_rms_dbfs, 2),
                tx_sample_peak_dbfs=round(tx_peak_dbfs, 2), ber_windows=int(values.size),
                displayed_ber=displayed, ber_vs_true_tx=measured,
                mer_db_settled=float(np.median(mer_values[len(mer_values) // 2:
                                                          -len(mer_values) // 10])),
                passed=bool(measured < 1e-3 and abs(displayed - measured) < 1e-3
                            and tx_peak_dbfs < 0))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(check(sys.argv[1])))
        sys.exit(0)
    subprocess.run([sys.executable, str(ROOT / "scripts/build_n210.py")], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "-c", "from gnuradio.grc.compiler import main; main()",
                    "-o", str(GENERATED), *map(str, sorted((ROOT / "grc").glob("n210_*.grc")))],
                   check=True, stdout=subprocess.DEVNULL)
    sys.path.insert(0, str(GENERATED))
    results = []
    for profile in PROFILES:  # one process per flowchart keeps Qt state clean
        out = subprocess.run([sys.executable, __file__, profile], check=True,
                             capture_output=True, text=True,
                             env={**os.environ, "PYTHONPATH": str(GENERATED)}).stdout
        result = json.loads(out.strip().splitlines()[-1])
        results.append(result)
        print(f'{profile:6s} BER vs TX {result["ber_vs_true_tx"]:.2g}  '
              f'displayed {result["displayed_ber"]:.2g}  MER {result["mer_db_settled"]:.1f} dB  '
              f'TX peak {result["tx_sample_peak_dbfs"]} dBFS  {"PASS" if result["passed"] else "FAIL"}')
    (ROOT / "results/n210_loopback_check.json").write_text(
        json.dumps(dict(channel=CHANNEL, note="Software stand-in for N210 RF; not a "
                        "hardware measurement.", results=results), indent=2) + "\n")
