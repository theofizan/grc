"""Re-lay out a flowchart canvas by GRC's real block sizes (positions only).

    python scripts/tidy_layout.py grc/n210_qpsk.grc [more.grc ...]

No parameter or wire changes: only block coordinates move.

* Controls (variables, parameters, imports, snippets, GUI ranges and labels)
  are packed in rows with 8 px gaps under the CONTROLS banner, following the
  user's BPSK control grouping, with newer controls in a final group.
* Every wired chain (virtual sinks/sources split the canvas into short chains)
  is laid out left to right: each block sits one column right of whatever
  feeds it, branches stack under the main path.
* Chains are grouped into the banner sections (transmitter/receiver, BER,
  BER test, link budget, diagnostics, ...) and the sections are stacked top to
  bottom with their blue banners above them. The result is checked for
  overlapping blocks.
"""

from pathlib import Path
import math
import runpy
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
GAP, COLUMN_GAP, ROW_GAP, SECTION_GAP, WIDTH_LIMIT = 8, 48, 16, 72, 2400
CONTROL_TYPES = {"variable", "parameter", "variable_constellation",
                 "variable_constellation_rect", "variable_adaptive_algorithm", "import",
                 "snippet", "variable_qtgui_range", "variable_qtgui_label",
                 "qtgui_tab_widget"}
# The user's BPSK control grouping (configs/control_layout.json era), then the rest.
CONTROL_GROUPS = [
    ["symbol_rate", "sps", "samp_rate", "bit_rate", "alpha", "nfilts", "timing_bw",
     "rrc_taps", "eye_synthesis_taps", "rrc_bandwidth"],
    ["tx_power_dbm", "tx_level_dbfs", "path_loss_db", "rx_noise_dbm", "noise_enabled",
     "channel_echo"],
    ["tx_amplitude", "path_gain", "expected_rx_dbm", "noise_volt", "snr_rx_db", "esno_rx_db",
     "ebno_rx_db", "k", "symbol_rms"],
    ["reference_delay", "ber_window", "warmup_bits", "eq_delay_symbols", "eq_taps", "eq_step",
     "evm_guide_percent"],
    ["const", "eq_algorithm", "chart_math", "square_plot_panels", "equalizer_initial_taps",
     "views"],
    # Radio (N210 flowcharts)
    ["tx_usrp_address", "rx_usrp_address", "center_freq_hz", "tx_gain_norm", "rx_gain_norm",
     "carrier_loop_bw", "settle_s", "data_period_bits", "tx_data", "training_symbols",
     "preamble_len", "eq_training_len"],
    # BER test and display
    ["ber_test_bits", "ber_test_blocks", "ber_test_seconds", "ber_error_weight",
     "plot_update_s", "link_table"],
]
# Section order, banner name, banner title, and blocks that identify a chain.
SECTIONS = [
    ("main", "section_transmitter", "TRANSMITTER",
     {"random_bytes", "modulator", "usrp_tx", "usrp_rx", "clock_sync", "channel"}),
    ("ber", "section_ber", "BER MEASUREMENT", {"xor", "unpack_rx", "skip_rx", "skip_tx"}),
    ("ber_test", "section_ber_test", "BER TEST (FIXED LENGTH)", set()),
    ("power", "section_power", "LINK BUDGET & POWER METERS",
     {"tx_milliwatts", "rx_milliwatts", "tx_peak_vectors", "tx_papr", "rx_snr", "rx_ebno",
      "spectrum_budget", "rf_constellation"}),
    ("rx_diagnostics", "section_rx_diagnostics", "RX DIAGNOSTICS", set()),
    ("reference", "section_reference", "TX SYMBOL REFERENCE & EVM GUIDES",
     {"tx_symbol_chunks", "tx_constellation", "ideal_symbols", "evm_circles"}),
    ("pre_eq", "section_pre_eq", "BEFORE EQUALIZATION", {"before_eq_constellation"}),
    ("eyes", "section_eyes", "EYE COMPARISON: MIDDLE / AFTER EQ / TX",
     {"middle_eye_reconstruction", "after_eye_reconstruction"}),
    ("extra_plots", "section_extra_plots", "LIVE WAVEFORM & ADAPTATION MONITORS", set()),
]


def snap(value):
    return GAP * math.ceil(value / GAP)


def rendered_sizes(file):
    sys.argv = ["export_layout.py", "--file", str(file)]
    graph = runpy.run_path(str(ROOT / "scripts/export_layout.py"))["graph"]
    return {b.name: (snap(b.width), snap(b.height)) for b in graph.blocks}


def tidy(file):
    file = Path(file).resolve()
    size = rendered_sizes(file)
    graph = yaml.safe_load(file.read_text())
    blocks = {b["name"]: b for b in graph["blocks"]}
    xy = {n: tuple(b["states"]["coordinate"]) for n, b in blocks.items()}
    notes = {n: b for n, b in blocks.items() if b["id"] == "note" and n.startswith("section_")}
    controls = [n for n, b in blocks.items() if b["id"] in CONTROL_TYPES]
    body = [n for n, b in blocks.items() if n not in controls and n not in notes]

    # --- Controls --------------------------------------------------------------
    ordered = [n for group in CONTROL_GROUPS for n in group if n in controls]
    ordered += sorted((n for n in controls if n not in ordered), key=lambda n: (xy[n][1], xy[n][0]))
    group_of = {n: i for i, group in enumerate(CONTROL_GROUPS) for n in group}
    top_note = notes.get("section_controls")
    y = 8
    if top_note:
        top_note["states"]["coordinate"] = [16, y]
        y += size["section_controls"][1] + 16
    x, row_height, last_group = 16, 0, None
    for name in ordered:
        w, h = size[name]
        group = group_of.get(name, len(CONTROL_GROUPS))
        new_row = x + w > WIDTH_LIMIT or (last_group is not None and group != last_group
                                          and group >= 5 and x > 16)
        if new_row and x > 16:
            x, y, row_height = 16, y + row_height + GAP, 0
        blocks[name]["states"]["coordinate"] = [x, y]
        x += w + GAP
        row_height = max(row_height, h)
        last_group = group
    y += row_height + SECTION_GAP

    # --- Chains: connected components of wired blocks ----------------------------
    neighbours = {n: set() for n in body}
    successors = {n: [] for n in body}
    predecessors = {n: [] for n in body}
    for src, _, dst, _ in graph["connections"]:
        if src in neighbours and dst in neighbours:
            neighbours[src].add(dst)
            neighbours[dst].add(src)
            successors[src].append(dst)
            predecessors[dst].append(src)
    seen, chains = set(), []
    for start in sorted(body, key=lambda n: (xy[n][1], xy[n][0])):
        if start in seen:
            continue
        stack, chain = [start], []
        seen.add(start)
        while stack:
            node = stack.pop()
            chain.append(node)
            for other in neighbours[node] - seen:
                seen.add(other)
                stack.append(other)
        chains.append(chain)

    # Which section each chain belongs to: identifying blocks first, then the
    # banner it used to sit under (majority of its blocks).
    note_name = {key: note for key, note, _, _ in SECTIONS}
    bands = sorted((xy[note_name[key]][1], key) for key, *_ in SECTIONS
                   if note_name[key] in notes)

    def band_of(name):
        current = "main"
        for top, key in bands:
            if xy[name][1] >= top - 10:
                current = key
        return current

    def section_of(chain):
        names = set(chain)
        if any(n.startswith(("ber_test", "bit_errors_to")) for n in names):
            return "ber_test"
        for key, _, _, keys in SECTIONS:
            if names & keys:
                return key
        votes = {}
        for n in chain:
            votes[band_of(n)] = votes.get(band_of(n), 0) + 1
        return max(votes, key=votes.get)

    by_section = {key: [] for key, *_ in SECTIONS}
    for chain in chains:
        by_section[section_of(chain)].append(chain)

    def layout_chain(chain, x0, y0):
        """Columns by longest path from the chain's inputs; returns (w, h)."""
        layer = {}

        def depth(n):
            if n not in layer:
                layer[n] = 0
                layer[n] = 1 + max((depth(p) for p in predecessors[n] if p in chain_set),
                                   default=-1)
            return layer[n]

        chain_set = set(chain)
        for n in chain:
            depth(n)
        # Main path: walk from the deepest block back along its deepest inputs.
        main = set()
        node = max(chain, key=lambda n: (layer[n], -xy[n][1]))
        while node is not None:
            main.add(node)
            ins = [p for p in predecessors[node] if p in chain_set]
            node = max(ins, key=lambda p: layer[p]) if ins else None
        columns = {}
        for n in chain:
            columns.setdefault(layer[n], []).append(n)
        x, height = x0, 0
        for col in sorted(columns):
            members = sorted(columns[col], key=lambda n: (n not in main, xy[n][1], xy[n][0]))
            yy = y0
            for n in members:
                blocks[n]["states"]["coordinate"] = [x, yy]
                yy += size[n][1] + ROW_GAP
            height = max(height, yy - ROW_GAP - y0)
            x += max(size[n][0] for n in members) + COLUMN_GAP
        return x - COLUMN_GAP - x0, height

    # --- Sections, top to bottom ---------------------------------------------------
    for key, note, title, _ in SECTIONS:
        chains_here = sorted(by_section[key], key=lambda c: min((xy[n][1], xy[n][0]) for n in c))
        if not chains_here:
            continue
        if note not in blocks:
            blocks[note] = dict(name=note, id="note", parameters=dict(note=title, comment=""),
                                states=dict(coordinate=[16, y], rotation=0, state="enabled"))
            graph["blocks"].append(blocks[note])
            size[note] = (8 * len(title) + 40, 40)
        blocks[note]["states"]["coordinate"] = [16, y]
        y += size.get(note, (0, 40))[1] + 16
        x, shelf_height = 16, 0
        for chain in chains_here:
            # Measure by laying out at the origin, then shift into place.
            w, h = layout_chain(chain, 0, 0)
            if x + w > WIDTH_LIMIT and x > 16:
                x, y, shelf_height = 16, y + shelf_height + 40, 0
            for n in chain:
                cx, cy = blocks[n]["states"]["coordinate"]
                blocks[n]["states"]["coordinate"] = [cx + x, cy + y]
            x += w + 64
            shelf_height = max(shelf_height, h)
        y += shelf_height + SECTION_GAP

    # Secondary banners in the main section: above the receiver / RF front end.
    for note, anchors in (("section_receiver", ("usrp_rx", "rx_level")),
                          ("section_channel", ("usrp_tx", "channel"))):
        anchor = next((a for a in anchors if a in blocks), None)
        if note in blocks and anchor:
            ax, ay = blocks[anchor]["states"]["coordinate"]
            blocks[note]["states"]["coordinate"] = [ax, ay - size.get(note, (0, 40))[1] - 8]

    graph["options"]["states"]["coordinate"] = [WIDTH_LIMIT + 80, 8]
    file.write_text(yaml.safe_dump(graph, sort_keys=False, width=110))
    return overlaps(graph, size)


def overlaps(graph, size):
    boxes = [(b["name"], *b["states"]["coordinate"], *size.get(b["name"], (0, 0)))
             for b in graph["blocks"]]
    hits = []
    for i, (a, ax, ay, aw, ah) in enumerate(boxes):
        for b, bx, by, bw, bh in boxes[i + 1:]:
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                hits.append((a, b))
    return hits


if __name__ == "__main__":
    import subprocess

    if len(sys.argv) > 2:  # one process per file: the renderer starts a GTK app
        for path in sys.argv[1:]:
            subprocess.run([sys.executable, __file__, path], check=True)
    else:
        path = sys.argv[1]  # the renderer replaces sys.argv
        hits = tidy(path)
        print(f"{Path(path).name}: {len(hits)} overlapping block pairs"
              + (f" {hits[:6]}" if hits else ""))
