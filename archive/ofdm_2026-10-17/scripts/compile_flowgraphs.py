"""Compile edited module sources first, then parents. Does not regenerate GRC."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def compile_graphs(modules_only=False):
    output = ROOT / "grc/generated"
    output.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["GRC_HIER_PATH"] = str(output)
    groups = [sorted((ROOT / "grc/modules").glob("*.grc"))]
    if not modules_only:
        groups.append(sorted((ROOT / "grc").glob("*.grc")))
    for files in groups:
        if files:
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from gnuradio.grc.compiler import main; main()",
                    "-o",
                    str(output),
                    *[str(p) for p in files],
                ],
                env=env,
                cwd=ROOT,
                check=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules-only", action="store_true")
    compile_graphs(parser.parse_args().modules_only)
