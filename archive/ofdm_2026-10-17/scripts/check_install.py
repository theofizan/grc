"""Check required runtime imports and project discovery outside the source tree."""

from datetime import datetime, timezone
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            "import antenna_bench, antenna_steering; from gnuradio import gr, blocks, analog, fft, uhd; "
            'import numpy, scipy, matplotlib, yaml; import gi; gi.require_version("Gtk", "3.0"); '
            "from gi.repository import Gtk; import cairo; "
            "print(gr.version()); print(antenna_bench.__file__); print(Gtk.MAJOR_VERSION)",
        ],
        cwd="/tmp",
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert check.returncode == 0, check.stderr
    from gnuradio import gr, uhd

    packages = {
        name: metadata.version(name)
        for name in (
            "numpy",
            "scipy",
            "matplotlib",
            "PyYAML",
            "PyQt5",
            "antenna-benchmark",
        )
    }
    webengine_available = (
        importlib.util.find_spec("PyQt5.QtWebEngineWidgets") is not None
    )
    if webengine_available:
        from PyQt5.QtWebEngineWidgets import QWebEngineView

        packages["PyQtWebEngine"] = metadata.version("PyQtWebEngine")
    # Import success cannot detect Qt5/Qt6 Qwt ABI mixing. Construct a real GNU
    # Radio plot in an isolated offscreen process so a native abort is reported.
    gui_env = env.copy()
    gui_env["QT_QPA_PLATFORM"] = "offscreen"
    gui_check = subprocess.run(
        [
            sys.executable,
            "-c",
            "from PyQt5 import Qt; app=Qt.QApplication([]); from gnuradio import qtgui; "
            'sink=qtgui.const_sink_c(64,"installation probe",1); '
            'app.processEvents(); del sink; app.quit(); print("Qt5/Qwt widget passed")',
        ],
        env=gui_env,
        cwd="/tmp",
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert (
        gui_check.returncode == 0
    ), f"Qt probe exit {gui_check.returncode}: {gui_check.stderr}"
    qwt_files = list((Path(sys.base_prefix) / "conda-meta").glob("qwt-*.json"))
    qwt = json.loads(qwt_files[0].read_text()) if qwt_files else {}
    # Discovery sends no samples and opens no transmitter. Use UHD's default local
    # discovery rather than probing an assumed static address or changing networking.
    discovery = subprocess.run(
        [str(Path(sys.base_prefix) / "bin/uhd_find_devices")],
        capture_output=True,
        text=True,
        timeout=20,
    )
    (ROOT / "results/validation/uhd_discovery.log").write_text(
        discovery.stdout + discovery.stderr
    )
    report = dict(
        status="passed",
        utc=datetime.now(timezone.utc).isoformat(),
        interpreter=sys.executable,
        base_python_prefix=sys.base_prefix,
        project_venv=sys.prefix != sys.base_prefix,
        gnuradio=gr.version(),
        uhd=uhd.get_version_string(),
        packages=packages,
        imports_from_tmp_without_pythonpath=check.stdout.strip().splitlines(),
        required_gtk_imports="passed",
        launcher=str(Path(sys.executable).parent / "antenna-grc"),
        qtgui_widget_check=gui_check.stdout.strip(),
        qwt_build=qwt.get("build"),
        qwt_dependencies=qwt.get("depends", []),
        fixes=[
            "Editable local package installed with --no-deps --no-build-isolation",
            "Launcher uses radioconda Python and prepends its bin directory to PATH",
        ]
        + (
            [
                "Added conda-forge pyqtwebengine, qt-webengine, giflib and libwebp; no existing packages replaced"
            ]
            if webengine_available
            else []
        ),
        qt_document_browser_available=webengine_available,
        qt_note=(
            "Qt WebEngine widget import passed; stable GTK frontend remains the default launcher"
            if webengine_available
            else "Optional Qt documentation browser unavailable; use GTK frontend"
        ),
        discovery_exit_code=discovery.returncode,
        device_found="Device Address:" in discovery.stdout,
        hardware_streaming_tested=False,
    )
    (ROOT / "results/validation/install_check.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
