"""Pack controls using their actual GRC-rendered sizes, with an 8-pixel gap."""

from pathlib import Path
import argparse
import json
import math
import sys
import yaml
import runpy

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--modulation", default="bpsk")
profile = parser.parse_args().modulation
# Reuse GRC's native font/shape setup; no approximate label-width guesses.
sys.argv = ["export_layout.py", "--modulation", profile]
namespace = runpy.run_path(str(root / "scripts/export_layout.py"))
canvas = namespace["graph"]
file = root / "grc" / f"single_carrier_{profile}.grc"
from label_sections import label_sections, remove_sections

graph = remove_sections(yaml.safe_load(file.read_text()))
by = {b["name"]: b for b in graph["blocks"]}
rendered = {b.name: b for b in canvas.blocks}
control_types = {
    "variable",
    "parameter",
    "variable_constellation",
    "variable_constellation_rect",
    "variable_adaptive_algorithm",
    "import",
    "snippet",
    "qtgui_tab_widget",
}
controls = {name for name, b in by.items() if b["id"] in control_types}
groups = [
    [
        "symbol_rate",
        "sps",
        "samp_rate",
        "bit_rate",
        "alpha",
        "nfilts",
        "timing_bw",
        "rrc_taps",
        "eye_synthesis_taps",
        "rrc_bandwidth",
    ],
    ["tx_power_dbm", "path_loss_db", "rx_noise_dbm", "noise_enabled", "channel_echo"],
    [
        "tx_amplitude",
        "path_gain",
        "expected_rx_dbm",
        "noise_volt",
        "snr_rx_db",
        "esno_rx_db",
        "ebno_rx_db",
        "k",
        "symbol_rms",
    ],
    [
        "reference_delay",
        "ber_window",
        "warmup_bits",
        "eq_delay_symbols",
        "eq_taps",
        "eq_step",
        "evm_guide_percent",
    ],
    [
        "const",
        "eq_algorithm",
        "chart_math",
        "square_plot_panels",
        "equalizer_initial_taps",
        "views",
    ],
]
assigned = set()
y = 8
for group in groups:
    x = 160
    row_height = 0
    for name in group:
        if name not in controls:
            continue
        b = rendered[name]
        width = 8 * math.ceil(b.width / 8)
        height = 8 * math.ceil(b.height / 8)
        if x + width > 1600 and x > 160:
            y += row_height + 8
            x = 160
            row_height = 0
        by[name]["states"]["coordinate"] = [x, y]
        assigned.add(name)
        x += width + 8
        row_height = max(row_height, height)
    y += row_height + 8
for name in sorted(controls - assigned):
    by[name]["states"]["coordinate"] = [160, y]
    y += 8 * math.ceil(rendered[name].height / 8) + 8
# Keep the processing chain clear of the tightly packed control panel.
body = [b for name, b in by.items() if name not in controls]
first = min(b["states"]["coordinate"][1] for b in body)
shift = (y + 24) - first
for b in body:
    b["states"]["coordinate"][1] += shift
# Pack the main RF path by native widths too: blocks must never overlap.
main_path = [
    "random_bytes",
    "modulator",
    "tx_power",
    "throttle",
    "channel",
    "rx_level",
    "clock_sync",
    "rx_scale",
    "equalizer",
    "decoder",
    "decoded_link",
]
main_y = by["random_bytes"]["states"]["coordinate"][1]
x = 16
for name in main_path:
    by[name]["states"]["coordinate"] = [x, main_y]
    x += 8 * math.ceil(rendered[name].width / 8) + 32
# Place each short virtual branch below its physical source. The clock's
# auxiliary outputs and EQ tap vectors stay separate from the signal path.
for name, source, extra in [
    ("reference_link", "random_bytes", 100),
    ("tx_plot_link", "tx_power", 100),
    ("rx_iq_link", "channel", 120),
    ("timing_link", "clock_sync", 160),
    ("unused_timing_states", "clock_sync", 220),
    ("pre_eq_link", "rx_scale", 100),
    ("symbols_link", "equalizer", 128),
    ("adaptive_tap_vectors_link", "equalizer", 192),
]:
    if name in by:
        by[name]["states"]["coordinate"] = [
            by[source]["states"]["coordinate"][0],
            main_y + extra,
        ]
label_sections(graph)
file.write_text(yaml.safe_dump(graph, sort_keys=False, width=110))
config = root / "configs/packed_controls.json"
try:
    layouts = json.loads(config.read_text())
except FileNotFoundError:
    layouts = {}
layouts[profile] = {name: by[name]["states"]["coordinate"] for name in controls}
config.write_text(json.dumps(layouts, indent=2) + "\n")
print(f"Packed {len(controls)} controls using real block sizes and 8 px spacing")
