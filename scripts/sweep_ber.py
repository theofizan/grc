"""Measure BER versus Eb/N0 by running the real flowcharts at many noise levels.

Each point is one finite GNU Radio capture (about 262,000 bits). Receiver noise
is set from the requested Eb/N0 using the same Fs noise-bandwidth convention as
the live readouts: Eb/N0 = SNR(Fs) + 10*log10(Fs / bit rate).

An "ideal-synchronization" reference is also computed in NumPy with the same
constellation points, bit packing, and differential coding, but with perfect
timing and no equalizer. The gap between it and the measured points is the
implementation loss of the GNU Radio receiver.

Writes results/ber_sweep/ber_sweep.csv and ideal_reference.csv.
"""

from pathlib import Path
import csv
import json
import os
import re
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/ber_sweep"
DELAY_BITS = {"bpsk": 34, "qpsk": 68, "8psk": 102, "4ask": 68, "8ask": 102, "16qam": 136}
TX_DBM, LOSS_DB = 0.0, 80.0
EBNO_GRID_DB = np.arange(0, 25, 1.0)
SAMPLES_PER_SYMBOL = 4


def constellation_points(profile):
    """Read the constellation exactly as the generated flowchart defines it."""
    from gnuradio import digital  # noqa: F401  (used by eval)

    source = (ROOT / f"grc/generated/single_carrier_{profile}.py").read_text()
    expression = re.search(r"self\.const = const = (.+?\.base\(\))", source, re.S).group(1)
    return np.asarray(eval(expression).points(), dtype=complex)


def ideal_reference(points, ebno_db, bits=2_000_000, seed=1):
    """Ideal timing/gain, nearest-point decisions, stock differential coding."""
    rng = np.random.default_rng(seed)
    m = len(points)
    k = int(np.log2(m))
    symbols_in = rng.integers(0, m, bits // k)
    encoded = np.cumsum(symbols_in) % m  # digital.diff_encoder_bb(M)
    es = np.mean(abs(points) ** 2)
    n0 = es / (k * 10 ** (ebno_db / 10))
    rx = points[encoded] + np.sqrt(n0 / 2) * (
        rng.standard_normal(encoded.size) + 1j * rng.standard_normal(encoded.size)
    )
    decided = np.argmin(abs(rx[:, None] - points[None, :]), axis=1)
    decoded = np.diff(decided, prepend=0) % m  # digital.diff_decoder_bb(M)
    shifts = np.arange(k - 1, -1, -1)
    tx_bits = (symbols_in[1:, None] >> shifts) & 1
    rx_bits = (decoded[1:, None] >> shifts) & 1
    return int(np.sum(tx_bits != rx_bits)), tx_bits.size


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    measured, ideal = [], []
    for profile, delay in DELAY_BITS.items():
        points = constellation_points(profile)
        k = int(np.log2(len(points)))
        bit_rate = 1e6 * k
        samp_rate = 1e6 * SAMPLES_PER_SYMBOL
        zero_runs = 0
        for ebno in EBNO_GRID_DB:
            snr_fs = ebno - 10 * np.log10(samp_rate / bit_rate)
            noise_dbm = TX_DBM - LOSS_DB - snr_fs
            folder = OUT / profile
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/validate_single_carrier.py"),
                    "--modulation", profile,
                    "--delay", str(delay),
                    "--tx-power-dbm", str(TX_DBM),
                    "--path-loss-db", str(LOSS_DB),
                    "--rx-noise-dbm", f"{noise_dbm:.6f}",
                    "--no-fixture",
                    "--output-dir", str(folder),
                ],
                cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL,
            )
            result_file = max(folder.glob(f"{profile}_noise_*.json"), key=os.path.getmtime)
            result = json.loads(result_file.read_text())
            result_file.rename(folder / f"{profile}_ebno_{ebno:g}dB.json")
            bits = result["compared_bits"]
            errors = int(round(result["display_ber_mean"] * bits))
            measured.append(dict(
                modulation=profile, ebno_db=round(float(result["nominal_rx_ebno_db"]), 3),
                snr_fs_db=round(float(result["nominal_rx_snr_db"]), 3),
                rx_noise_dbm=round(noise_dbm, 3), bit_errors=errors, compared_bits=bits,
                ber=errors / bits, data_aided_evm_percent=result["reference_evm_percent"],
            ))
            ideal_errors, ideal_bits = ideal_reference(points, ebno)
            ideal.append(dict(modulation=profile, ebno_db=float(ebno),
                              bit_errors=ideal_errors, compared_bits=ideal_bits,
                              ber=ideal_errors / ideal_bits))
            print(f"{profile:6s} Eb/N0 {ebno:4.1f} dB  BER {errors/bits:.3e}  ({errors} errors)")
            zero_runs = zero_runs + 1 if errors == 0 else 0
            if zero_runs == 2:
                break
    for name, rows in [("ber_sweep.csv", measured), ("ideal_reference.csv", ideal)]:
        with (OUT / name).open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
