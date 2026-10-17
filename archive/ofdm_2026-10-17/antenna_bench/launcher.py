"""Launch the installed GRC with this interpreter and its executable search path."""

import os
from pathlib import Path
import sys
import subprocess
from antenna_bench.paths import ROOT


def main():
    python_bin = Path(sys.executable).parent
    executable = next(
        (
            folder / "gnuradio-companion"
            for folder in (python_bin, Path(sys.base_prefix) / "bin")
            if (folder / "gnuradio-companion").is_file()
        ),
        None,
    )
    if executable is None:
        raise SystemExit(
            "Install this project in your GNU Radio/radioconda Python environment."
        )
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(
        (str(python_bin), str(executable.parent), env.get("PATH", ""))
    )
    env["GRC_HIER_PATH"] = str(ROOT / "grc/generated")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/compile_flowgraphs.py"), "--modules-only"],
        env=env,
        check=True,
    )
    arguments = sys.argv[1:] or [str(p) for p in sorted((ROOT / "grc").glob("*.grc"))]
    # Stable GTK frontend; --qt can be explicitly selected by the caller.
    if not any(a in ("--qt", "--gtk") for a in arguments):
        arguments.insert(0, "--gtk")
    os.execve(sys.executable, [sys.executable, str(executable), *arguments], env)
