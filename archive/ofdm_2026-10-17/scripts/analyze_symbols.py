"""Score GRC's aligned symbol-rate files; no timing recovery is assumed here."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from scipy.io import savemat
from antenna_bench.math import score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tx", type=Path, default=ROOT / "results/grc/symbol_tx.c64")
    parser.add_argument("--rx", type=Path, default=ROOT / "results/grc/symbol_rx.c64")
    parser.add_argument("--order", type=int, default=16)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "results/grc/symbol_metrics.json"
    )
    args = parser.parse_args()
    tx = np.fromfile(args.tx, dtype="<c8").astype(complex)
    rx = np.fromfile(args.rx, dtype="<c8").astype(complex)
    result = score(tx, rx, args.order)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    savemat(
        args.output.with_suffix(".mat"),
        {
            "tx": tx[:, None],
            "rx": rx[:, None],
            "order": args.order,
            "python_errors": result["errors"],
            "python_bits": result["bits"],
            "python_evm": result["evm_rms"],
        },
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
