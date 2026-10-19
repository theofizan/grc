"""Run fixed-length BER tests on the single-carrier simulation flowcharts.

No radios needed. Each test runs the real generated flowchart
(grc/single_carrier_<modulation>.grc) with the settings you give, waits for
its built-in BER test (the "BER test" rows of the Link budget table) to
finish, and saves the result.

Examples:
    # 1 million bits of QPSK at Eb/N0 = 8 dB
    python scripts/run_ber_test.py --modulation qpsk --ebno-db 8

    # several Eb/N0 points in one go, 10 million bits each
    python scripts/run_ber_test.py --modulation 16qam --bits 1e7 --ebno-db 10 12 14

    # set the link budget directly instead of Eb/N0
    python scripts/run_ber_test.py --modulation 8psk --tx-power-dbm 0 \\
        --path-loss-db 80 --rx-noise-dbm -92

    # watch it run in the normal dashboard (real time, slower)
    python scripts/run_ber_test.py --modulation qpsk --ebno-db 8 --gui

Eb/N0 uses the flowcharts' convention: receiver noise is integrated over
Fs = 4 Msamples/s and Eb/N0 = SNR(Fs) + 10*log10(Fs / bit rate), per
uncoded bit. Without --gui the throttle is lifted so the simulation runs
as fast as the computer allows.

Each test prints errors, BER and the exact 95% Clopper-Pearson interval, and
is saved to results/ber_tests/<time>_<modulation>_<label>.json together with
all settings and the measured TX/RX levels, SNR, Eb/N0 and EVM.
"""

from pathlib import Path
import argparse
import datetime
import importlib
import json
import math
import os
import sys
import time
import numpy as np
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
BITS_PER_SYMBOL = {"bpsk": 1, "qpsk": 2, "8psk": 3, "4ask": 2, "8ask": 3, "16qam": 4}
SAMPLES_PER_SYMBOL = 4


def clopper_pearson(errors, n, confidence=0.95):
    a = 1 - confidence
    low = 0.0 if errors == 0 else float(beta.ppf(a / 2, errors, n - errors + 1))
    high = 1.0 if errors == n else float(beta.ppf(1 - a / 2, errors + 1, n - errors))
    return low, high


def run_one(module, name, app, args, rx_noise_dbm, Qt):
    from gnuradio import blocks

    test_bits = max(1, int(args.bits) // 10000) * 10000  # flowchart counts in 10k blocks
    lab = getattr(module, name)(
        tx_power_dbm=args.tx_power_dbm, path_loss_db=args.path_loss_db,
        rx_noise_dbm=-100 if rx_noise_dbm is None else rx_noise_dbm,
        noise_enabled=int(rx_noise_dbm is not None),
        channel_echo=args.echo, ber_test_bits=test_bits, symbol_rate=args.symbol_rate)
    module.snippets_main_after_init(lab)
    if not args.gui:
        lab.throttle.set_sample_rate(1e12)  # run as fast as possible
    # Independent check: total of the raw 10,000-bit error sums.
    windows = blocks.vector_sink_f()
    lab.connect(lab.ber_test_sum_10k, windows)
    if args.gui:
        lab.views.setCurrentIndex(3)
        lab.show()
    started = time.time()
    lab.start()
    last_report = 0.0
    while lab.probe_ber_test_count.level() < test_bits:
        app.processEvents()
        time.sleep(0.02)
        elapsed = time.time() - started
        if elapsed - last_report >= 2:
            last_report = elapsed
            print(f"    {elapsed:6.1f} s  {lab.probe_ber_test_count.level():,.0f} / "
                  f"{test_bits:,} bits", flush=True)
    time.sleep(0.1)
    app.processEvents()
    errors = int(round(lab.probe_ber_test_errors.level()))
    compared = int(round(lab.probe_ber_test_count.level()))
    level = {n: float(getattr(lab, f"probe_{n}").level())
             for n in ("tx_dbm", "tx_peak_dbm", "rx_dbm", "rx_snr", "rx_ebno", "evm_rms")}
    lab.stop()
    lab.wait()
    raw = np.asarray(windows.data())[:test_bits // 10000]
    independent = int(round(raw.sum()))
    assert independent == errors, f"BER test {errors} != raw window total {independent}"
    if args.gui:
        lab.close()
    low, high = clopper_pearson(errors, compared)
    return dict(compared_bits=compared, bit_errors=errors, ber=errors / compared,
                ber_95ci=[low, high], elapsed_s=round(time.time() - started, 2),
                measured=dict(tx_average_dbm=level["tx_dbm"],
                              tx_sample_peak_dbm=level["tx_peak_dbm"],
                              rx_total_dbm=level["rx_dbm"], snr_fs_db=level["rx_snr"],
                              ebno_db=level["rx_ebno"],
                              evm_decision_directed_percent=level["evm_rms"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modulation", required=True, choices=list(BITS_PER_SYMBOL))
    parser.add_argument("--bits", type=float, default=1e6,
                        help="compared bits per test (multiple of 10,000; default 1e6)")
    noise = parser.add_mutually_exclusive_group()
    noise.add_argument("--ebno-db", type=float, nargs="+",
                       help="one or more Eb/N0 values (dB per uncoded bit)")
    noise.add_argument("--rx-noise-dbm", type=float, nargs="+",
                       help="one or more receiver noise powers over Fs (dBm)")
    noise.add_argument("--no-noise", action="store_true", help="noise off")
    parser.add_argument("--tx-power-dbm", type=float, default=0.0)
    parser.add_argument("--path-loss-db", type=float, default=80.0)
    parser.add_argument("--echo", type=float, default=0.0,
                        help="one-symbol echo voltage ratio (multipath test)")
    parser.add_argument("--symbol-rate", type=float, default=1e6)
    parser.add_argument("--label", default="sim", help="name saved with the result")
    parser.add_argument("--gui", action="store_true",
                        help="show the dashboard and run in real time")
    args = parser.parse_args()
    if not args.gui:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT / "grc/generated"))
    from PyQt5 import Qt

    app = Qt.QApplication.instance() or Qt.QApplication(sys.argv)
    name = f"single_carrier_{args.modulation}"
    module = importlib.import_module(name)
    k = BITS_PER_SYMBOL[args.modulation]
    fs = SAMPLES_PER_SYMBOL * args.symbol_rate
    bit_rate = k * args.symbol_rate
    rx_signal_dbm = args.tx_power_dbm - args.path_loss_db
    if args.ebno_db:
        points = [(e, rx_signal_dbm - (e - 10 * math.log10(fs / bit_rate)))
                  for e in args.ebno_db]
    elif args.rx_noise_dbm:
        points = [(rx_signal_dbm - n + 10 * math.log10(fs / bit_rate), n)
                  for n in args.rx_noise_dbm]
    else:
        points = [(None, None)]

    folder = ROOT / "results/ber_tests"
    folder.mkdir(parents=True, exist_ok=True)
    print(f"{args.modulation.upper()}: {int(args.bits):,} bits per test at "
          f"{bit_rate / 1e6:g} Mbit/s")
    for ebno, noise_dbm in points:
        setting = "noise off" if noise_dbm is None else (
            f"Eb/N0 {ebno:.2f} dB (RX noise {noise_dbm:.2f} dBm over Fs)")
        print(f"  {setting}")
        result = run_one(module, name, app, args, noise_dbm, Qt)
        low, high = result["ber_95ci"]
        print(f"  -> BER {result['ber']:.3e}  ({result['bit_errors']} errors in "
              f"{result['compared_bits']:,} bits; 95% CI {low:.2e} to {high:.2e})  "
              f"EVM {result['measured']['evm_decision_directed_percent']:.1f}%  "
              f"[{result['elapsed_s']} s]")
        record = dict(modulation=args.modulation, label=args.label,
                      time=datetime.datetime.now().isoformat(timespec="seconds"),
                      ebno_db=ebno, rx_noise_dbm=noise_dbm, **result,
                      settings=dict(vars(args), bit_rate_bps=bit_rate, sample_rate_hz=fs))
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        tag = "nonoise" if ebno is None else f"ebno{ebno:g}dB"
        path = folder / f"{stamp}_{args.modulation}_{tag}_{args.label}.json"
        path.write_text(json.dumps(record, indent=2) + "\n")
        print(f"     saved {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
