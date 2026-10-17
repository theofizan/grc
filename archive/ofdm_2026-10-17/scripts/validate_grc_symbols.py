"""Execute the generated native GRC symbol graph for all supported modulations.

Check finite sample counts, Gaussian noise energy and BER against known theory.
The six-standard-deviation BER envelope includes covariance of bits within a
QAM symbol via a conservative k-fold variance bound (not an exact BER CI).
"""

import json
from pathlib import Path
import subprocess
import sys
import numpy as np
from scipy.io import savemat
from antenna_bench.math import exact_ber, score

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "results/grc"
    reports = []
    for order in (2, 4, 16, 64):
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "grc/generated/awgn_symbol_benchmark.py"),
                "--order",
                str(order),
                "--ebno-db",
                "8",
            ],
            check=True,
            timeout=30,
        )
        tx = np.fromfile(output / "symbol_tx.c64", dtype="<c8").astype(complex)
        rx = np.fromfile(output / "symbol_rx.c64", dtype="<c8").astype(complex)
        assert tx.size == rx.size == 100000, "Truncated or dropped symbol samples"
        metrics = score(tx, rx, order)
        expected_variance = 1 / (np.log2(order) * 10**0.8)
        measured_variance = metrics["error_energy"] / metrics["symbols"]
        assert (
            abs(measured_variance / expected_variance - 1) < 0.03
        ), "Complex AWGN scaling mismatch"
        probability = float(exact_ber(order, 8))
        envelope = 6 * np.sqrt(probability * (1 - probability) / metrics["symbols"])
        assert (
            abs(metrics["ber"] - probability) < envelope + 1 / metrics["bits"]
        ), "BER outside noise-model envelope"
        metrics.update(
            ebno_db=8,
            theory_ber=probability,
            expected_noise_power=expected_variance,
            measured_noise_power=measured_variance,
            status="passed",
        )
        stem = f"symbol_order_{order}"
        (output / f"{stem}.json").write_text(json.dumps(metrics, indent=2) + "\n")
        savemat(
            output / f"{stem}_fixture.mat",
            dict(
                tx=tx[:, None],
                rx=rx[:, None],
                order=order,
                python_errors=metrics["errors"],
                python_bits=metrics["bits"],
                python_evm=metrics["evm_rms"],
            ),
        )
        reports.append(metrics)
    (output / "symbol_runtime_validation.json").write_text(
        json.dumps(dict(status="passed", ebno_db=8, cases=reports), indent=2) + "\n"
    )
    print(
        "All four GRC modulations: exact finite counts, noise scaling and BER envelope passed"
    )


if __name__ == "__main__":
    main()
