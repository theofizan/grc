"""Generate simulation results and a shared MATLAB metric-validation fixture."""

from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys
import platform

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from scipy.io import savemat
from antenna_bench.math import exact_ber, make_symbols, score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/python")
    parser.add_argument("--symbols", type=int, default=100000)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for order in (2, 4, 16, 64):
        tx = make_symbols(order, args.symbols)
        for ebno in range(0, 19, 2):
            variance = 1 / (np.log2(order) * 10 ** (ebno / 10))
            rng = np.random.default_rng(20261016 + order * 100 + ebno)
            noise = np.sqrt(variance / 2) * (
                rng.normal(size=tx.size) + 1j * rng.normal(size=tx.size)
            )
            rx = tx.astype(np.complex128) + noise
            row = dict(
                ebno_db=ebno,
                theory_ber=float(exact_ber(order, ebno)),
                theory_evm_rms=float(np.sqrt(variance)),
                **score(tx, rx, order),
            )
            rows.append(row)
            if ebno == 8:
                tx.astype("<c8").tofile(args.output / f"order_{order}_tx.c64")
                rx.astype("<c8").tofile(args.output / f"order_{order}_rx.c64")
                savemat(
                    args.output / f"order_{order}_metric_fixture.mat",
                    {
                        "tx": tx[:, None],
                        "rx": rx[:, None],
                        "order": order,
                        "ebno_db": ebno,
                        "python_errors": row["errors"],
                        "python_bits": row["bits"],
                        "python_evm": row["evm_rms"],
                    },
                )
    with (args.output / "awgn_results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "manifest.json").write_text(
        json.dumps(
            {
                "kind": "uncoded_symbol_rate_AWGN_simulation_not_RF",
                "seed": 20261016,
                "symbols_per_point": args.symbols,
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "noise_convention": "E|n|^2=N0=1/(log2(M)*10^(EbNo_dB/10)), Es=1",
                "confidence": "two-sided 95% Clopper-Pearson, independent bits assumed",
            },
            indent=2,
        )
        + "\n"
    )
    print(
        f"Wrote {len(rows)} simulation points and four shared fixtures to {args.output}"
    )


if __name__ == "__main__":
    main()
