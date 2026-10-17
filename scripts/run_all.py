"""Compile saved flowcharts, check all six modulations, and write a short report.

This does not overwrite your editable .grc sources or run radio hardware.
"""

from pathlib import Path
import json
import hashlib
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
profiles = {"bpsk": 34, "qpsk": 68, "8psk": 102, "4ask": 68, "8ask": 102, "16qam": 136}
subprocess.run(
    [
        PYTHON,
        "-c",
        "from gnuradio.grc.compiler import main; main()",
        "-o",
        "grc/generated",
        *[str(p) for p in sorted((ROOT / "grc").glob("*.grc"))],
    ],
    cwd=ROOT,
    check=True,
)
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "offscreen"
rows = []
for profile, delay in profiles.items():
    for noise in (0, 0.3):
        subprocess.run(
            [
                PYTHON,
                "scripts/validate_single_carrier.py",
                "--modulation",
                profile,
                "--delay",
                str(delay),
                "--noise",
                str(noise),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
        result = json.loads(
            (ROOT / "results" / f"{profile}_noise_{noise:g}.json").read_text()
        )
        assert result["best_delay_bits"] == delay
        rows.append(result)
    subprocess.run(
        [PYTHON, "scripts/export_layout.py", "--modulation", profile],
        cwd=ROOT,
        check=True,
    )
zero_noise = [r for r in rows if r["noise_voltage"] == 0]
powers = [r["tx_mean_sample_power"] for r in zero_noise]
assert max(powers) / min(powers) < 1.04, "Transmit powers differ by more than 4%"
subprocess.run([PYTHON, "scripts/check_link_budget.py"], cwd=ROOT, check=True)
subprocess.run(
    [
        PYTHON,
        "scripts/validate_single_carrier.py",
        "--modulation",
        "16qam",
        "--delay",
        "136",
        "--noise",
        "0.1",
        "--render-dashboards",
        "--echo",
        "0.25",
        "--output-dir",
        str(ROOT / "results/equalizer_checks"),
    ],
    cwd=ROOT,
    env=env,
    check=True,
)
# MATLAB independently checks the actual saved GNU Radio captures.
matlab_path = "/Applications/MATLAB_R2026a.app/bin/matlab"
matlab_folder = str(ROOT / "matlab").replace("'", "''")
subprocess.run(
    [matlab_path, "-batch", f"addpath('{matlab_folder}'); validate_single_carrier;"],
    cwd=ROOT,
    check=True,
)
# BER versus Eb/N0 from the real flowcharts (about 100 finite captures).
subprocess.run([PYTHON, "scripts/sweep_ber.py"], cwd=ROOT, env=env, check=True)
subprocess.run([PYTHON, "scripts/plot_results.py"], cwd=ROOT, check=True)
# N210 over-the-air variants: rebuild from the saved simulations, then check
# them through a software stand-in for the radio (no hardware needed).
subprocess.run([PYTHON, "scripts/build_n210.py"], cwd=ROOT, check=True)
subprocess.run([PYTHON, "scripts/check_n210_loopback.py"], cwd=ROOT, env=env, check=True)
subprocess.run([PYTHON, "scripts/plot_equalizer.py"], cwd=ROOT, check=True)
matlab_results = json.loads((ROOT / "results/matlab_validation.json").read_text())
subprocess.run([PYTHON, "scripts/write_report.py"], cwd=ROOT, check=True)
print(
    "PASS: six graphs; 16 cases: 12 baseline, three link-budget, one echo/EQ; MATLAB checked."
)

# Save the exact editable sources associated with this validation run.
source_paths = [ROOT / "README.md", ROOT / "AGENTS.md"]
for pattern in (
    "scripts/*.py",
    "antenna_bench/*.py",
    "grc/*.grc",
    "matlab/*.m",
    "configs/*.json",
):
    source_paths.extend(ROOT.glob(pattern))
source_hashes = {
    str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(source_paths)
}
(ROOT / "results/source_hashes.json").write_text(
    json.dumps(source_hashes, indent=2) + "\n"
)
