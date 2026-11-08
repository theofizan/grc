"""Pack the controls of a BER-curve flowchart by GRC's real block sizes.

Variables, parameters, imports and snippets are placed left to right in rows
with 8-pixel gaps (wrapping at 1600 px) under the CONTROLS heading, in this
order: Eb/N0 points and test settings, link/power, modem, equalizer. The
processing sections below are then moved up (or down) to sit 40 px under the
packed controls. Called by build_ber_curves.py; can also be run directly:

    python scripts/pack_ber_curve_controls.py grc/ber_curve_qpsk.grc
"""

from pathlib import Path
import math
import runpy
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTROL_TYPES = {"variable", "parameter", "variable_constellation",
                 "variable_constellation_rect", "variable_adaptive_algorithm",
                 "import", "snippet"}
ORDER = [
    # What you change for a curve
    "ebno_db", "min_errors", "ber_floor_log10", "sim_speed", "plot_update_s", "noise_volts",
    # Link and power
    "tx_power_dbm", "tx_amplitude", "path_loss_db", "path_gain",
    # Modem
    "symbol_rate", "sps", "samp_rate", "bit_rate", "k", "const", "symbol_rms",
    "alpha", "nfilts", "rrc_taps", "timing_bw",
    # Equalizer and BER alignment
    "eq_taps", "eq_step", "eq_delay_symbols", "eq_algorithm", "reference_delay",
    "warmup_bits", "chart_math", "equalizer_initial_taps", "curve_title",
]
GAP, LEFT, WIDTH_LIMIT = 8, 16, 1600


def snap(value):
    return GAP * math.ceil(value / GAP)


def pack(file):
    file = Path(file).resolve()
    sys.argv = ["export_layout.py", "--file", str(file)]
    rendered = {b.name: b for b in runpy.run_path(str(ROOT / "scripts/export_layout.py"))
                ["graph"].blocks}
    graph = yaml.safe_load(file.read_text())
    by = {b["name"]: b for b in graph["blocks"]}
    controls = [n for n in ORDER if n in by and by[n]["id"] in CONTROL_TYPES]
    controls += sorted(n for n, b in by.items()
                       if b["id"] in CONTROL_TYPES and n not in controls)
    heading = by["section_controls"]
    heading["states"]["coordinate"] = [LEFT, 8]
    y = 8 + snap(rendered["section_controls"].height) + 16
    x, row_height = LEFT, 0
    for name in controls:
        width, height = snap(rendered[name].width), snap(rendered[name].height)
        if x + width > WIDTH_LIMIT and x > LEFT:
            x, y, row_height = LEFT, y + row_height + GAP, 0
        by[name]["states"]["coordinate"] = [x, y]
        x += width + GAP
        row_height = max(row_height, height)
    bottom = y + row_height
    # Move everything below (sections, rows, sink) to just under the controls.
    body = [b for n, b in by.items() if n not in controls and n != "section_controls"]
    first = min(b["states"]["coordinate"][1] for b in body)
    shift = bottom + 40 - first
    for block in body:
        block["states"]["coordinate"][1] += shift
    graph["options"]["states"]["coordinate"] = [WIDTH_LIMIT + 40, 8]
    file.write_text(yaml.safe_dump(graph, sort_keys=False, width=110))
    return len(controls), bottom


if __name__ == "__main__":
    for path in sys.argv[1:]:
        count, bottom = pack(path)
        print(f"{Path(path).name}: packed {count} controls, controls end at y={bottom}")
