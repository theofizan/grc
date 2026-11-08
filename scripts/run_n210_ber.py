"""Run a fixed-length BER test on the two-N210 flowchart and save the result.

Example (1 million bits of QPSK, antenna under test labelled "patch_A"):
    python scripts/run_n210_ber.py --modulation qpsk --bits 1e6 --label patch_A \\
        --tx-address addr=192.168.10.2 --rx-address addr=192.168.10.3 \\
        --freq 915e6 --tx-gain-db 10 --rx-gain-db 10

The script prints its time estimate, runs the generated flowchart (with its
dashboard if --gui), discards the acquisition period (AGC, Costas loop, and
the first full equalizer training), then compares the next --bits received
bits with the actual transmitted data. Bits are scored in chunks that are
each re-aligned to the known data, so a USRP overflow/underflow (dropped
samples) only affects the chunk it occurs in. Counting starts at sync (see
score()); the acquisition time and any later losses of sync are reported.

Results go to results/n210_runs/<time>_<modulation>_<label>.json with the
error count, BER, exact 95% Clopper-Pearson interval, RX ADC level, MER, and
every RF setting, so antenna runs can be compared later.

--simulate replaces both radios with the software channel used by
check_n210_loopback.py (no hardware), useful for trying the procedure.
"""

from pathlib import Path
import argparse
import datetime
import importlib
import json
import os
import sys
import time
import numpy as np
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "grc/generated"
CHUNK_BITS = 50_000
ACQUISITION_PERIODS = 3  # data blocks allowed for acquisition before the test bits


def clopper_pearson(errors, n, confidence=0.95):
    a = 1 - confidence
    low = 0.0 if errors == 0 else float(beta.ppf(a / 2, errors, n - errors + 1))
    high = 1.0 if errors == n else float(beta.ppf(1 - a / 2, errors + 1, n - errors))
    return low, high


def score(rx_bits, tx_block_bits, test_bits):
    """Sync first, then count, like a lab BER tester.

    Every 50,000-bit chunk is aligned to the known data block by
    cross-correlation. Sync is declared at the first of three consecutive
    chunks that line up end to end with under 1% errors; everything before
    that is receiver acquisition and is discarded. From the sync point on,
    every chunk is counted, and any later jump in alignment (a loss of sync,
    for example after dropped USRP samples) is reported, not hidden.
    """
    period = tx_block_bits.size
    reference = 2.0 * np.concatenate([tx_block_bits, tx_block_bits]) - 1
    reference_fft = np.fft.rfft(reference)
    chunks = []
    for start in range(0, rx_bits.size - CHUNK_BITS + 1, CHUNK_BITS):
        chunk = rx_bits[start:start + CHUNK_BITS]
        probe = 2.0 * chunk[:4096] - 1
        correlation = np.fft.irfft(reference_fft * np.conj(np.fft.rfft(probe, reference.size)),
                                   reference.size)
        lag = int(np.argmax(correlation[:period]))
        expected = np.resize(np.roll(tx_block_bits, -lag), chunk.size)
        chunks.append((lag, int(np.count_nonzero(chunk != expected))))

    def contiguous(i):
        return (chunks[i + 1][0] - chunks[i][0] - CHUNK_BITS) % period == 0

    sync = next((i for i in range(len(chunks) - 3)
                 if all(chunks[j][1] < 0.01 * CHUNK_BITS for j in range(i, i + 3))
                 and contiguous(i) and contiguous(i + 1)), None)
    if sync is None:
        return None
    counted = chunks[sync:sync + test_bits // CHUNK_BITS]
    errors = sum(e for _, e in counted)
    losses = sum(1 for i in range(sync, sync + len(counted) - 1) if not contiguous(i))
    return errors, len(counted) * CHUNK_BITS, losses, sync * CHUNK_BITS


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modulation", required=True,
                        choices=["bpsk", "qpsk", "8psk", "4ask", "8ask", "16qam"])
    parser.add_argument("--bits", type=float, default=1e6, help="compared bits (default 1e6)")
    parser.add_argument("--label", default="antenna", help="name saved with the result")
    parser.add_argument("--tx-address", default="addr=192.168.10.2")
    parser.add_argument("--rx-address", default="addr=192.168.10.2",
                        help="same as --tx-address for one-radio loopback")
    parser.add_argument("--freq", type=float, default=915e6, help="RF center frequency (Hz)")
    parser.add_argument("--tx-gain-db", type=float, default=10.0,
                        help="TX gain in dB (UBX: 0-31.5)")
    parser.add_argument("--rx-gain-db", type=float, default=10.0,
                        help="RX gain in dB (UBX: 0-31.5)")
    parser.add_argument("--tx-level-dbfs", type=float, default=-15)
    parser.add_argument("--gui", action="store_true", help="show the live dashboard")
    parser.add_argument("--simulate", action="store_true",
                        help="software channel instead of radios (see check_n210_loopback.py)")
    parser.add_argument("--esno-db", type=float, default=12.0, help="--simulate only")
    args = parser.parse_args()
    if not args.gui:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(GENERATED))
    sys.path.insert(0, str(ROOT / "scripts"))
    from PyQt5 import Qt
    from gnuradio import blocks, gr

    app = Qt.QApplication.instance() or Qt.QApplication(sys.argv)
    name = f"n210_{args.modulation}"
    module = importlib.import_module(name)
    settings = dict(tx_usrp_address=args.tx_address, rx_usrp_address=args.rx_address,
                    center_freq_hz=args.freq, tx_level_dbfs=args.tx_level_dbfs)

    def make():
        lab = getattr(module, name)(**settings)
        lab.set_tx_gain_db(args.tx_gain_db)
        lab.set_rx_gain_db(args.rx_gain_db)
        return lab

    probe_lab = None
    if args.simulate:
        import check_n210_loopback as loop
        loop.CHANNEL["esno_db"] = args.esno_db
        probe_lab = loop.build(args.modulation, blocks.null_sink(gr.sizeof_gr_complex),
                               blocks.null_source(gr.sizeof_gr_complex))
    lab_for_rates = probe_lab or make()
    k = int(lab_for_rates.k)
    bit_rate = float(lab_for_rates.bit_rate)
    period_bits = int(lab_for_rates.data_period_bits)
    tx_block = np.unpackbits(np.asarray(lab_for_rates.tx_data, dtype=np.uint8))
    skip_bits = ACQUISITION_PERIODS * period_bits  # expected acquisition (max)
    test_bits = max(1, int(args.bits) // CHUNK_BITS) * CHUNK_BITS
    total_bits = skip_bits + test_bits + CHUNK_BITS
    estimate = total_bits / bit_rate
    print(f"{args.modulation.upper()}: {test_bits:,} test bits at {bit_rate / 1e6:g} Mbit/s, "
          f"plus {skip_bits:,} acquisition bits -> about {estimate:.1f} s of radio time")

    if args.simulate:
        sps, fs = int(lab_for_rates.sps), float(lab_for_rates.samp_rate)
        tx_capture = blocks.vector_sink_c()
        lab = loop.build(args.modulation, tx_capture, blocks.null_source(gr.sizeof_gr_complex))
        # Margin for the channel delay and filter latency of the playback.
        samples = (total_bits + 200_000) // k * sps + 50_000
        loop.run_until(lab, lambda: len(tx_capture.data()) >= samples, 600)
        rx = loop.over_the_air(np.asarray(tx_capture.data()[:samples]), fs,
                               np.random.default_rng(1))
        lab = loop.build(args.modulation, blocks.null_sink(gr.sizeof_gr_complex),
                         blocks.vector_source_c(rx.tolist(), False))
    else:
        lab = lab_for_rates
    bits = blocks.vector_sink_b()
    rx_level = blocks.vector_sink_f()
    mer = blocks.vector_sink_f()
    tx_peak = blocks.vector_sink_f()
    lab.connect(lab.unpack_rx, bits)
    lab.connect(lab.rx_dbm, rx_level)
    lab.connect(lab.rx_snr, mer)
    lab.connect(lab.tx_peak_dbm, tx_peak)
    if args.gui:
        lab.show()
    started = time.time()
    lab.start()
    last_report, last_count, last_change = 0, -1, time.time()
    target = total_bits
    max_acquisition_bits = int(5 * bit_rate) + 3 * period_bits  # give up after ~5 s
    while True:
        app.processEvents()
        time.sleep(0.05)
        elapsed = time.time() - started
        count = len(bits.data())
        if elapsed - last_report >= 2:
            last_report = elapsed
            print(f"  {elapsed:6.1f} s  {count:,} bits received", flush=True)
        if count != last_count:
            last_count, last_change = count, time.time()
        if args.simulate and time.time() - last_change > 5:
            raise SystemExit(f"Simulated playback ended at {count:,} bits")
        if count < target:
            continue
        # Enough bits for the planned test: check sync and the counted length.
        scored = score(np.asarray(bits.data(), dtype=np.uint8), tx_block, test_bits)
        if scored is not None and scored[1] >= test_bits:
            break
        acquired = count - test_bits if scored is None else scored[3]
        if acquired > max_acquisition_bits:
            lab.stop()
            lab.wait()
            raise SystemExit("No sync within about 5 s: the received bits never lined up with "
                             "the known data. Check the RF connection, gains and frequency.")
        target = count + period_bits  # acquisition took longer; keep receiving
    lab.stop()
    lab.wait()
    errors, compared, shifts, acquisition_bits = scored
    low, high = clopper_pearson(errors, compared)

    def settled_median(sink):
        values = np.asarray(sink.data())
        return float(np.median(values[len(values) // 2:])) if values.size else None

    result = dict(
        label=args.label, modulation=args.modulation, simulated=args.simulate,
        time=datetime.datetime.now().isoformat(timespec="seconds"),
        compared_bits=compared, bit_errors=errors, ber=errors / compared,
        ber_95ci=[low, high], losses_of_sync=shifts,
        acquisition_s=round(acquisition_bits / bit_rate, 3),
        rx_adc_level_dbfs=settled_median(rx_level), mer_db=settled_median(mer),
        tx_sample_peak_dbfs=float(np.max(tx_peak.data())) if tx_peak.data() else None,
        elapsed_s=round(time.time() - started, 1), estimated_s=round(estimate, 1),
        settings=dict(vars(args), bit_rate_bps=bit_rate, data_block_bits=period_bits,
                      acquisition_bits_discarded=acquisition_bits),
    )
    folder = ROOT / "results/n210_runs"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = folder / f"{stamp}_{args.modulation}_{args.label}.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"BER {result['ber']:.3g}  ({errors} errors in {compared:,} bits; "
          f"95% CI {low:.2g} to {high:.2g})  RX ADC {result['rx_adc_level_dbfs']:.1f} dBFS  "
          f"MER {result['mer_db']:.1f} dB  sync after {result['acquisition_s']} s, "
          f"losses of sync {shifts}")
    print("saved", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
