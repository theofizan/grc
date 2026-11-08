"""Quick over-the-air BER campaign: every format, stepped TX level, real radios.

    python scripts/n210_campaign.py --label "two antennas side by side"

Each format's flowchart is opened once (the slow part, ~3 s for UHD); the TX
level and gains are then changed live, exactly like moving the GRC sliders.
For each format this measures:
  * the flowcharts' defaults (TX/RX gain 10 dB, TX level -15 dBFS), then
  * fixed sweep gains (TX 0 dB, RX 10 dB by default) with the TX digital level
    stepped down (4 dB steps from -30 dBFS) until a level cannot sync.
Every point syncs on the known data, then compares --bits bits (default
300,000) with the actual transmitted data, exactly like run_n210_ber.py, and
records RX ADC level, MER, BER with 95% interval, and losses of sync.

Results: results/n210_campaign/summary.csv and setup.json. About a minute.
"""

from pathlib import Path
import argparse
import csv
import importlib
import json
import os
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/n210_campaign"
FORMATS = ["bpsk", "qpsk", "8psk", "4ask", "8ask", "16qam"]
SETTLE_S = 0.3        # after a level/gain change, before counting
SYNC_TIMEOUT_S = 1.5  # give up on a point if no sync within this much signal


def measure(lab, app, bits_sink, probes, tx_block, test_bits, bit_rate):
    from run_n210_ber import CHUNK_BITS, clopper_pearson, score

    def pump(seconds):
        end = time.time() + seconds
        samples = {k: [] for k in probes}
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)
            for key, probe in probes.items():
                samples[key].append(probe.level())
        return samples

    pump(SETTLE_S)
    bits_sink.reset()
    needed = test_bits + CHUNK_BITS * 4
    readings = {k: [] for k in probes}
    started = time.time()
    while True:
        for key, values in pump(0.1).items():
            readings[key] += values
        have = len(bits_sink.data())
        if have < needed:
            if time.time() - started > needed / bit_rate + SYNC_TIMEOUT_S + 2:
                return None  # receiver stalled
            continue
        scored = score(np.asarray(bits_sink.data(), dtype=np.uint8), tx_block, test_bits)
        if scored is not None and scored[1] >= test_bits:
            break
        if have > needed + SYNC_TIMEOUT_S * bit_rate:
            return None  # no sync at this level
        needed = have + int(bit_rate)  # wait another second before re-scoring
    errors, compared, losses, acquisition_bits = scored
    low, high = clopper_pearson(errors, compared)

    def median(key):
        values = np.asarray(readings[key][len(readings[key]) // 3:])
        values = values[np.isfinite(values)]
        return float(np.median(values)) if values.size else None

    return dict(synced=True, bits=compared, errors=errors, ber=errors / compared,
                ber_ci_low=low, ber_ci_high=high, rx_adc_dbfs=median("rx"),
                mer_db=median("mer"), tx_peak_dbfs=median("tx_peak"),
                losses_of_sync=losses, acquisition_s=round(acquisition_bits / bit_rate, 3))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", default="over the air", help="setup description")
    parser.add_argument("--address", default="addr=192.168.10.2")
    parser.add_argument("--freq", type=float, default=915e6)
    parser.add_argument("--bits", type=float, default=3e5)
    parser.add_argument("--sweep-tx-gain-db", type=float, default=0.0)
    parser.add_argument("--sweep-rx-gain-db", type=float, default=10.0)
    parser.add_argument("--start-dbfs", type=float, default=-30.0)
    parser.add_argument("--step-db", type=float, default=4.0)
    parser.add_argument("--formats", nargs="+", default=FORMATS, choices=FORMATS)
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT / "grc/generated"))
    sys.path.insert(0, str(ROOT / "scripts"))
    from PyQt5 import Qt
    from gnuradio import blocks

    app = Qt.QApplication.instance() or Qt.QApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    test_bits = max(1, int(args.bits) // 50_000) * 50_000
    rows, started = [], time.time()
    for modulation in args.formats:
        module = importlib.import_module(f"n210_{modulation}")
        lab = getattr(module, f"n210_{modulation}")(
            tx_usrp_address=args.address, rx_usrp_address=args.address,
            center_freq_hz=args.freq)
        module.snippets_main_after_init(lab)
        bits_sink = blocks.vector_sink_b()
        lab.connect(lab.unpack_rx, bits_sink)
        probes = dict(rx=lab.probe_rx_dbm, mer=lab.probe_rx_snr, tx_peak=lab.probe_tx_peak_dbm)
        tx_block = np.unpackbits(np.asarray(lab.tx_data, dtype=np.uint8))
        bit_rate = float(lab.bit_rate)
        lab.start()
        plan = [("default", 10.0, 10.0, -15.0)]
        level = args.start_dbfs
        while level >= -80:
            plan.append(("sweep", args.sweep_tx_gain_db, args.sweep_rx_gain_db, level))
            level -= args.step_db
        for kind, tx_gain, rx_gain, level in plan:
            lab.set_tx_gain_db(tx_gain)
            lab.set_rx_gain_db(rx_gain)
            lab.set_tx_level_dbfs(level)
            result = measure(lab, app, bits_sink, probes, tx_block, test_bits, bit_rate)
            row = dict(modulation=modulation, kind=kind, tx_gain_db=tx_gain,
                       rx_gain_db=rx_gain, tx_level_dbfs=level)
            row.update(result or dict(synced=False))
            rows.append(row)
            print(f"{modulation:6s} {kind:7s} {level:6.1f} dBFS  " + summary(row), flush=True)
            if kind == "sweep" and result is None:
                break
        lab.stop()
        lab.wait()
        lab.link_table_timer.stop()  # the table's refresh timer outlives the flowchart
        lab.close()
        del lab
    fields = ["modulation", "kind", "tx_gain_db", "rx_gain_db", "tx_level_dbfs", "synced",
              "bits", "errors", "ber", "ber_ci_low", "ber_ci_high", "rx_adc_dbfs", "mer_db",
              "tx_peak_dbfs", "losses_of_sync", "acquisition_s"]
    with (OUT / "summary.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "setup.json").write_text(json.dumps(dict(
        label=args.label, frequency_hz=args.freq, address=args.address,
        bits_per_point=test_bits, sweep_tx_gain_db=args.sweep_tx_gain_db,
        sweep_rx_gain_db=args.sweep_rx_gain_db, step_db=args.step_db,
        date=time.strftime("%Y-%m-%d %H:%M"), duration_s=round(time.time() - started)),
        indent=2) + "\n")
    print(f"wrote {(OUT / 'summary.csv').relative_to(ROOT)} in {time.time() - started:.0f} s")


def summary(row):
    if not row["synced"]:
        return "no sync"
    return (f"ADC {row['rx_adc_dbfs']:6.1f} dBFS  MER {row['mer_db']:5.1f} dB  "
            f"BER {row['ber']:.2e} ({row['errors']} / {row['bits']:,})  "
            f"losses of sync {row['losses_of_sync']}")


if __name__ == "__main__":
    main()
