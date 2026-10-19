"""Run the simulation BER tests across Eb/N0 and check that the results make sense.

For every modulation and Eb/N0 point this runs the real single-carrier
flowchart's built-in BER test (scripts/run_ber_test.py; error count also
cross-checked against the raw error sums). Each point gets enough bits for at
least ~300 errors, up to 20 million bits.

Checks written to results/ber_tests/:
  1. Noise off: 0 errors in 10 million bits.
  2. Ideal-synchronization reference (NumPy, same constellation, bit mapping
     and differential coding, perfect timing). Each measured point is
     converted to an equivalent Eb/N0 loss against it (how many dB the ideal
     receiver could give up and still reach the same BER).
  3. Textbook coherent Gray theory: the gap to it is the known cost of
     differential coding and the stock (natural-order) ASK mapping.
  4. BER falls monotonically with Eb/N0 (within confidence intervals).
  5. Required Eb/N0 at BER 1e-3 and 1e-4, and the spacing between formats,
     compared with the references.
  6. Agreement with the earlier, independently scored 250k-bit sweep. Errors
     after differential decoding come in pairs, so intervals use half counts.
  7. Noise-off residual error: worst-case (99.99th percentile) decision-
     relevant error relative to each format's half decision spacing, from the
     saved noise-off captures. Explains why high-Eb/N0 loss can grow.

Run: python scripts/ber_validation.py   (several minutes)
"""

from pathlib import Path
from types import SimpleNamespace
import csv
import importlib
import json
import math
import os
import sys
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "grc/generated"))
from ber_theory import BITS, clopper_pearson, coherent_gray_ber, ebno_at_ber  # noqa: E402
from run_ber_test import run_one  # noqa: E402
from sweep_ber import constellation_points, ideal_reference  # noqa: E402

OUT = ROOT / "results/ber_tests"
GRID_DB = {"bpsk": (0, 12), "qpsk": (0, 12), "8psk": (2, 15), "4ask": (4, 16),
           "8ask": (8, 21), "16qam": (4, 16)}
TARGET_ERRORS = 300
MIN_BITS, MAX_BITS = 1_000_000, 20_000_000
FS, SYMBOL_RATE = 4e6, 1e6


def ideal_ber(points, ebno, guess):
    """Ideal-sync reference with enough bits for ~2000 errors (max 3e7)."""
    want = int(min(3e7, max(1e6, 2000 / max(guess, 1e-9))))
    errors = bits = 0
    seed = 1
    while bits < want:
        # Ask for a little extra: the first symbol only seeds differential decoding.
        e, n = ideal_reference(points, ebno, bits=min(2_000_000, want - bits) + 64, seed=seed)
        errors, bits, seed = errors + e, bits + n, seed + 1
    return errors, bits


def measure(module, name, app, Qt, ebno, k):
    args = SimpleNamespace(bits=MIN_BITS, tx_power_dbm=0.0, path_loss_db=80.0, echo=0.0,
                           symbol_rate=SYMBOL_RATE, gui=False)
    noise_dbm = -80.0 - (ebno - 10 * math.log10(FS / (k * SYMBOL_RATE)))
    result = run_one(module, name, app, args, noise_dbm, Qt)
    if result["bit_errors"] < TARGET_ERRORS:
        ber = result["ber"] if result["bit_errors"] else 1 / result["compared_bits"]
        args.bits = int(min(MAX_BITS, max(MIN_BITS, 1.2 * TARGET_ERRORS / ber)))
        if args.bits > MIN_BITS:
            result = run_one(module, name, app, args, noise_dbm, Qt)
    return result


def main():
    from PyQt5 import Qt

    app = Qt.QApplication.instance() or Qt.QApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    rows, noiseless = [], {}
    for profile, (start, stop) in GRID_DB.items():
        name = f"single_carrier_{profile}"
        module = importlib.import_module(name)
        k = BITS[profile]
        points = constellation_points(profile)
        # Check 1: noise off must give zero errors.
        args = SimpleNamespace(bits=10_000_000, tx_power_dbm=0.0, path_loss_db=80.0,
                               echo=0.0, symbol_rate=SYMBOL_RATE, gui=False)
        clean = run_one(module, name, app, args, None, Qt)
        noiseless[profile] = dict(bits=clean["compared_bits"], errors=clean["bit_errors"])
        print(f"{profile}: noise off -> {clean['bit_errors']} errors in "
              f"{clean['compared_bits']:,} bits", flush=True)
        zero_points = 0
        for ebno in range(start, stop + 1):
            r = measure(module, name, app, Qt, float(ebno), k)
            guess = max(r["ber"], float(coherent_gray_ber(profile, ebno)))
            ref_errors, ref_bits = ideal_ber(points, float(ebno), guess)
            low, high = r["ber_95ci"]
            ref = ref_errors / ref_bits
            ref_low, ref_high = clopper_pearson(ref_errors, ref_bits)
            row = dict(
                modulation=profile, ebno_db=ebno, bits=r["compared_bits"],
                errors=r["bit_errors"], ber=r["ber"], ci_low=low, ci_high=high,
                ideal_ber=ref, ideal_errors=ref_errors, ideal_bits=ref_bits,
                ideal_ci_low=ref_low, ideal_ci_high=ref_high,
                gray_theory_ber=float(coherent_gray_ber(profile, ebno)),
                agrees_with_ideal=bool(low <= ref_high and ref_low <= high),
                ratio_to_ideal=(r["ber"] / ref) if ref > 0 else None,
                evm_percent=r["measured"]["evm_decision_directed_percent"],
                awgn_evm_percent=100 / math.sqrt(10 ** ((ebno + 10 * math.log10(k)) / 10)),
                snr_fs_db=r["measured"]["snr_fs_db"], ebno_readout_db=r["measured"]["ebno_db"],
            )
            rows.append(row)
            print(f"  {profile:6s} {ebno:3d} dB  BER {r['ber']:.3e} [{low:.2e}, {high:.2e}] "
                  f"({r['bit_errors']} / {r['compared_bits']:,})  ideal {ref:.3e}  "
                  f"Gray {row['gray_theory_ber']:.2e}", flush=True)
            zero_points = zero_points + 1 if r["bit_errors"] == 0 else 0
            if zero_points == 2:
                break
    with (OUT / "ber_validation.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "noiseless.json").write_text(json.dumps(noiseless, indent=2) + "\n")
    summarize(rows, noiseless)


def residual_eye_closure(profile):
    """Worst-case decision-relevant residual error with noise off (steady state)."""
    from scipy.io import loadmat

    data = loadmat(ROOT / f"results/{profile}_noise_0.mat", squeeze_me=True)
    points = np.ravel(data["constellation_points"]).astype(complex)
    tx = np.ravel(data["aligned_tx_symbols"]).astype(complex)
    rx = np.ravel(data["aligned_rx_symbols"]).astype(complex)
    n = min(tx.size, rx.size)
    error, tx = (rx[:n] - tx[:n])[n // 2:], tx[:n][n // 2:]  # steady state
    rms = np.sqrt(np.mean(abs(points) ** 2))
    if profile in ("bpsk", "4ask", "8ask"):
        relevant = abs(error.real)
        half = np.min(np.diff(np.unique(np.round(points.real, 9)))) / 2
    elif profile == "16qam":
        relevant = np.maximum(abs(error.real), abs(error.imag))
        half = np.min(np.diff(np.unique(np.round(points.real, 9)))) / 2
    else:  # PSK: distance across the nearest angular decision boundary
        radius = abs(points[0])
        relevant = radius * abs(np.sin(np.angle((tx + error) / tx)))
        half = radius * np.sin(np.pi / points.size)
    worst = float(np.percentile(relevant, 99.99))
    closure = worst / half
    return dict(rms_evm_percent=float(100 * np.sqrt(np.mean(abs(error) ** 2)) / rms),
                half_spacing_rms=float(half / rms), worst_error_rms=worst / rms,
                eye_closure_percent=100 * closure,
                asymptotic_loss_db=float(-20 * np.log10(1 - closure)))


def summarize(rows, noiseless):
    summary = dict(noiseless=noiseless, formats={})
    sweep = {}
    sweep_file = ROOT / "results/ber_sweep/ber_sweep.csv"
    if sweep_file.exists():
        with sweep_file.open() as file:
            for r in csv.DictReader(file):
                sweep[(r["modulation"], round(float(r["ebno_db"])))] = (
                    int(r["bit_errors"]), int(r["compared_bits"]))
    for profile in BITS:
        mine = [r for r in rows if r["modulation"] == profile]
        e = [r["ebno_db"] for r in mine]
        info = dict(points=len(mine), total_bits=int(sum(r["bits"] for r in mine)))
        for target in (1e-3, 1e-4):
            tag = f"{target:.0e}"
            measured = ebno_at_ber(e, [r["ber"] for r in mine], target)
            ideal = ebno_at_ber(e, [r["ideal_ber"] for r in mine], target)
            fine = np.arange(0, 30, 0.01)
            gray = ebno_at_ber(list(fine), list(coherent_gray_ber(profile, fine)), target)
            info[f"ebno_at_{tag}"] = dict(
                measured=measured, ideal_same_coding=ideal, gray_theory=gray,
                implementation_loss_db=None if None in (measured, ideal) else measured - ideal,
                coding_and_mapping_penalty_db=None if None in (ideal, gray) else ideal - gray)
        # Equivalent Eb/N0 loss of each locked point against the ideal curve.
        ideal_pts = [(r["ebno_db"], r["ideal_ber"]) for r in mine if r["ideal_ber"] > 0]
        losses = {}
        for r in mine:
            # Only where the ideal curve brackets this BER (no extrapolation).
            if (r["errors"] >= 20 and 0 < r["ber"] < 0.2 and ideal_pts
                    and min(b for _, b in ideal_pts) <= r["ber"] < max(b for _, b in ideal_pts)):
                equivalent = np.interp(-np.log10(r["ber"]),
                                       [-np.log10(b) for _, b in ideal_pts],
                                       [x for x, _ in ideal_pts])
                losses[f"{r['ebno_db']:g}"] = round(float(r["ebno_db"] - equivalent), 2)
                r["equivalent_loss_db"] = losses[f"{r['ebno_db']:g}"]
        info["equivalent_loss_db_per_point"] = losses
        values = list(losses.values())
        info["equivalent_loss_db_range"] = [min(values), max(values)] if values else None
        locked = [r for r in mine if r["ber"] < 0.2]
        info["monotonic"] = all(b["ci_low"] <= a["ci_high"] for a, b in zip(locked, locked[1:]))
        info["low_snr_lock_loss_points"] = [r["ebno_db"] for r in mine
                                            if r["ber"] > 0.3 and r["ideal_ber"] < 0.2]
        cross = []
        for r in mine:
            if (profile, r["ebno_db"]) in sweep and r["ber"] < 0.2:
                se, sn = sweep[(profile, r["ebno_db"])]
                if se >= 10:
                    # Differentially decoded errors come in pairs: use half counts.
                    lo, hi = clopper_pearson(se // 2, sn // 2)
                    mlo, mhi = clopper_pearson(int(r["errors"]) // 2, int(r["bits"]) // 2)
                    cross.append(lo <= mhi and mlo <= hi)
        info["agree_with_250k_sweep"] = f"{sum(cross)}/{len(cross)}"
        info["noise_off_residual"] = residual_eye_closure(profile)
        summary["formats"][profile] = info
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--summarize":
        with (OUT / "ber_validation.csv").open() as file:
            data = []
            for r in csv.DictReader(file):
                for key, value in r.items():
                    if key == "modulation":
                        continue
                    if value in ("True", "False"):
                        r[key] = value == "True"
                    elif value == "":
                        r[key] = None
                    else:
                        r[key] = float(value)
                data.append(r)
        summarize(data, json.loads((OUT / "noiseless.json").read_text()))
    else:
        main()
