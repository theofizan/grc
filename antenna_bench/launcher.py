"""Launch the installed GRC with this interpreter and its executable search path."""

import os
from pathlib import Path
import sys
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
    arguments = sys.argv[1:] or [str(p) for p in sorted((ROOT / "grc").glob("*.grc"))]
    # Stable GTK frontend; --qt can be explicitly selected by the caller.
    if not any(a in ("--qt", "--gtk") for a in arguments):
        arguments.insert(0, "--gtk")
    # Project-only presentation of ordinary Note blocks; installed GRC stays intact.
    bootstrap = """import sys, runpy
sys.argv = sys.argv[1:]
if '--qt' not in sys.argv:
    from antenna_bench.section_notes import install
    install()
runpy.run_path(sys.argv[0], run_name='__main__')
"""
    os.execve(
        sys.executable,
        [sys.executable, "-c", bootstrap, str(executable), *arguments],
        env,
    )
