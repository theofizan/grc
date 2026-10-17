"""Export GRC's own canvas to a PNG for layout review (no screen capture)."""

from pathlib import Path
import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--modulation", default="16qam")
profile = parser.parse_args().modulation
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk

app = Gtk.Application(application_id="org.antenna.layout")
app.register(None)
from antenna_bench.section_notes import install

install()
from gnuradio import gr
from gnuradio.grc.gui.Platform import Platform
from gnuradio.grc.gui.Utils import make_screenshot

root = Path(__file__).resolve().parents[1]
platform = Platform(
    name="GNU Radio",
    prefs=gr.prefs(),
    version=gr.version(),
    version_parts=(3, 10, 12),
    install_prefix=gr.prefix(),
)
platform.build_library()
app.platform = platform
app.config = platform.config
from gnuradio.grc.gui.MainWindow import MainWindow

main_window = MainWindow(app, platform)
graph = platform.make_flow_graph()
graph.import_data(
    platform.parse_flow_graph(str(root / f"grc/single_carrier_{profile}.grc"))
)
from gnuradio.grc.gui import Actions

Actions.TOGGLE_HIDE_VARIABLES.set_active(False)
Actions.TOGGLE_SHOW_BLOCK_IDS.set_active(False)
graph.update()
make_screenshot(graph, str(root / f"results/{profile}_flowchart.png"))
print(f"Wrote results/{profile}_flowchart.png")
