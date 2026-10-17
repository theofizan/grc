"""Three physical link-budget checks with fixed receiver noise at -100 dBm."""

from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "offscreen"
records = []
for name, tx_dbm, loss_db in [
    ("baseline", 0, 80),
    ("same_rx_power", 10, 90),
    ("lower_tx_power", -10, 80),
]:
    folder = root / "results/link_budget_checks" / name
    subprocess.run(
        [
            sys.executable,
            "scripts/validate_single_carrier.py",
            "--modulation",
            "16qam",
            "--delay",
            "136",
            "--tx-power-dbm",
            str(tx_dbm),
            "--path-loss-db",
            str(loss_db),
            "--rx-noise-dbm",
            "-100",
            "--output-dir",
            str(folder),
        ],
        cwd=root,
        env=env,
        check=True,
    )
    record = json.loads(next(folder.glob("*.json")).read_text())
    record["case"] = name
    records.append(record)
assert abs(records[1]["tx_measured_dbm"] - records[0]["tx_measured_dbm"] - 10) < 0.02
assert abs(records[1]["rx_measured_dbm"] - records[0]["rx_measured_dbm"]) < 0.02
assert abs(records[1]["display_ber_mean"] - records[0]["display_ber_mean"]) < 1e-4
assert records[2]["display_ber_mean"] > records[0]["display_ber_mean"]
(root / "results/link_budget_checks/summary.json").write_text(
    json.dumps(records, indent=2) + "\n"
)
print("PASS: absolute TX power, compensating loss, and lower-TX-power BER penalty")
