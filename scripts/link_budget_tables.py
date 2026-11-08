"""Replace the link-budget tab's time charts with readout tables and add a
fixed-length BER test. Only stock GNU Radio blocks are used.

GRC has no table block, so the table is a Qt table widget created by a stock
Python Snippet and filled from stock Probe Signal blocks (display only).

Link-budget tab (2x2): one spreadsheet-style table on the left (Transmit,
Receive, BER, BER test rows), the RX spectrum and received constellation on
the right. See spreadsheet() below.

BER test (press Run in GRC): the stock error stream (XOR -> UChar to Float,
after the warm-up skip) is summed per 10,000 bits (Integrate). A window
counter (IIR filter used as a running sum) and a Threshold make a gate that
is 1 for the first N/10000 windows and 0 afterwards. Gated running sums give
    bits compared, bit errors, and BER = errors / bits,
which count up during the test and then hold exactly the N-bit result on
screen while the flowgraph keeps running (close the window when done). N is
rounded to a multiple of 10,000. There is no auto-stop: a Head on this branch
cannot end the flowgraph while the other branches keep running. The rolling 10,000-bit BER display is
unchanged.

Run on the six saved simulation flowcharts (DSP settings and other layout are
kept): python scripts/link_budget_tables.py
"""

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
REMOVED = [
    "power_history", "envelope_plot", "envelope_dbm", "envelope_floor", "envelope_input",
    "power_reference_chart", "power_reference_chart_input", "snr_history_link",
    "tx_power_display", "rx_power_display", "peak_display", "snr_display", "ebno_display",
]


def apply(graph):
    blocks = {b["name"]: b for b in graph["blocks"]}
    converted = "tx_papr" in blocks
    anchor = blocks["tx_papr" if converted else "power_history"]["states"]["coordinate"]
    # Safe to re-run: layout tools may recreate old charts; always strip them.
    graph["blocks"][:] = [b for b in graph["blocks"] if b["name"] not in REMOVED]
    graph["connections"][:] = [c for c in graph["connections"]
                               if c[0] not in REMOVED and c[2] not in REMOVED]
    if not converted:
        # Peak-to-average for the table: sampled peak dBm minus average dBm.
        graph["blocks"].append(dict(
            name="tx_papr", id="blocks_sub_xx",
            parameters=dict(type="float", vlen="1", num_inputs="2"),
            states=dict(coordinate=[anchor[0] - 200, anchor[1]], rotation=0,
                        state="enabled")))
        graph["connections"] += [["tx_peak_dbm", "0", "tx_papr", "0"],
                                 ["tx_dbm", "0", "tx_papr", "1"]]
    return plot_refresh(ber_test(graph))


PLOT_SINKS = {"qtgui_time_sink_x", "qtgui_freq_sink_x", "qtgui_const_sink_x",
              "qtgui_eye_sink_x", "qtgui_number_sink", "qtgui_vector_sink_f",
              "qtgui_bercurve_sink"}


def plot_refresh(graph, default_s="0.5"):
    """One control for how often every plot redraws (display only).

    Each Qt GUI sink still receives and processes every sample; its update
    interval only sets how often it repaints. Slower repaints free the CPU
    without changing any measurement. Safe to run repeatedly.
    """
    blocks = {b["name"]: b for b in graph["blocks"]}
    if "plot_update_s" not in blocks:
        x, y = blocks["ber_test_bits"]["states"]["coordinate"] if "ber_test_bits" in blocks \
            else (16, 8)
        graph["blocks"].append(dict(
            name="plot_update_s", id="parameter",
            parameters=dict(value=default_s, type="eng_float",
                            label="Plot refresh interval (s)", short_id="", hide="none"),
            states=dict(coordinate=[x + 200, y], rotation=0, state="enabled")))
    for block in graph["blocks"]:
        if block["id"] in PLOT_SINKS:
            block["parameters"]["update_time"] = "plot_update_s"
    return graph


def ber_test(graph, error_weight="1.0"):
    """(Re)build the fixed-length BER test. Safe to run repeatedly."""
    graph["blocks"][:] = [b for b in graph["blocks"]
                          if not b["name"].startswith(("ber_test", "bit_errors_"))
                          and b["name"] not in ("stop_after_ber_test", "ber_error_weight")]
    # (stop_after_ber_test is removed from older builds of this test.)
    names = {b["name"] for b in graph["blocks"]}
    graph["connections"][:] = [c for c in graph["connections"]
                               if c[0] in names and c[2] in names]
    blocks = {b["name"]: b for b in graph["blocks"]}
    x0, y0 = blocks["tx_papr"]["states"]["coordinate"]
    y0 += 280

    def add(block_name, kind, x, y, **parameters):
        node = dict(name=block_name, id=kind,
                    parameters={k: str(v) for k, v in parameters.items()},
                    states=dict(coordinate=[x, y], rotation=0, state="enabled"))
        graph["blocks"].append(node)
        blocks[block_name] = node

    def wire(src, dst, dst_port=0):
        graph["connections"].append([src, "0", dst, str(dst_port)])

    # Controls and derived values, with the other controls at the top.
    add("ber_test_bits", "parameter", 1700, 8, value="1000000", type="intx",
        label="BER test length (compared bits)", short_id="", hide="none")
    add("ber_test_blocks", "variable", 1700, 192, value="max(1, int(ber_test_bits) // 10000)")
    add("ber_error_weight", "variable", 1700, 332, value=error_weight)
    add("ber_test_seconds", "variable", 1700, 402,
        value="(warmup_bits + 10000*ber_test_blocks) / bit_rate")
    # Error stream comes over a short virtual link from the BER section.
    ex, ey = blocks["errors_float"]["states"]["coordinate"]
    add("bit_errors_link", "virtual_sink", ex, ey + 70, stream_id="bit_errors")
    wire("errors_float", "bit_errors_link")
    add("bit_errors_to_ber_test", "virtual_source", x0, y0, stream_id="bit_errors")
    add("ber_test_sum_10k", "blocks_integrate_xx", x0 + 160, y0, type="float",
        decim="10000", vlen="1")
    # Gate: 1 for the first ber_test_blocks windows, then 0.
    add("ber_test_zero", "blocks_multiply_const_vxx", x0 + 330, y0 + 100, type="float",
        const="0", vlen="1")
    add("ber_test_unit", "blocks_add_const_vxx", x0 + 500, y0 + 100, type="float",
        const="1", vlen="1")
    add("ber_test_index", "iir_filter_xxx", x0 + 670, y0 + 100, type="ffd",
        fftaps="[1.0]", fbtaps="[0.0, 1.0]", oldstyle="True")
    add("ber_test_done", "blocks_threshold_ff", x0 + 840, y0 + 100,
        low="ber_test_blocks + 0.5", high="ber_test_blocks + 0.5", init="0")
    add("ber_test_not_done", "blocks_multiply_const_vxx", x0 + 1010, y0 + 100,
        type="float", const="-1", vlen="1")
    add("ber_test_gate", "blocks_add_const_vxx", x0 + 1180, y0 + 100, type="float",
        const="1", vlen="1")
    # Gated running sums (IIR running sum = y[n] = x[n] + y[n-1]).
    add("ber_test_gated_errors", "blocks_multiply_xx", x0 + 500, y0, type="float",
        num_inputs="2", vlen="1")
    add("ber_test_error_sum", "iir_filter_xxx", x0 + 670, y0, type="ffd",
        fftaps="[1.0]", fbtaps="[0.0, 1.0]", oldstyle="True")
    add("ber_test_errors", "blocks_multiply_const_vxx", x0 + 840, y0, type="float",
        const="ber_error_weight", vlen="1")
    add("ber_test_window_sum", "iir_filter_xxx", x0 + 1350, y0 + 100, type="ffd",
        fftaps="[1.0]", fbtaps="[0.0, 1.0]", oldstyle="True")
    add("ber_test_count", "blocks_multiply_const_vxx", x0 + 1520, y0 + 100,
        type="float", const="10000", vlen="1")
    add("ber_test_ratio", "blocks_divide_xx", x0 + 1010, y0, type="float", vlen="1",
        num_inputs="2")
    wire("bit_errors_to_ber_test", "ber_test_sum_10k")
    wire("ber_test_sum_10k", "ber_test_zero")
    wire("ber_test_zero", "ber_test_unit")
    wire("ber_test_unit", "ber_test_index")
    wire("ber_test_index", "ber_test_done")
    wire("ber_test_done", "ber_test_not_done")
    wire("ber_test_not_done", "ber_test_gate")
    wire("ber_test_sum_10k", "ber_test_gated_errors", 0)
    wire("ber_test_gate", "ber_test_gated_errors", 1)
    wire("ber_test_gated_errors", "ber_test_error_sum")
    wire("ber_test_error_sum", "ber_test_errors")
    wire("ber_test_gate", "ber_test_window_sum")
    wire("ber_test_window_sum", "ber_test_count")
    wire("ber_test_errors", "ber_test_ratio", 0)
    wire("ber_test_count", "ber_test_ratio", 1)
    return spreadsheet(graph)


# --- Spreadsheet-style table --------------------------------------------------
# (section, quantity, source block or None, unit, format). Formats: "dB" two
# decimals, "count" with thousands separators, "ber" scientific, "status"
# (BER test progress), or a Python expression on `self` for fixed values.
SIM_ROWS = [
    ("Transmit", "Average power", "tx_dbm", "dBm", "dB"),
    ("", "Sampled peak power", "tx_peak_dbm", "dBm", "dB"),
    ("", "Peak / average", "tx_papr", "dB", "dB"),
    ("Receive", "Signal + noise power", "rx_dbm", "dBm", "dB"),
    ("", "SNR (noise over Fs)", "rx_snr", "dB", "dB"),
    ("", "Eb/N0 per uncoded bit", "rx_ebno", "dB", "dB"),
    ("", "EVM (decision-directed)", "evm_rms", "%", "dB"),
    ("BER", "Latest 10,000 bits", "ber_scale", "errors/bit", "ber"),
    ("BER test", "Test length", None, "bits", "f'{10000 * self.ber_test_blocks:,}'"),
    ("", "Estimated time", None, "s", "f'{self.ber_test_seconds:.2f}'"),
    ("", "Status", "ber_test_count", "", "status"),
    ("", "Bits compared", "ber_test_count", "bits", "count"),
    ("", "Bit errors", "ber_test_errors", "errors", "count"),
    ("", "BER", "ber_test_ratio", "errors/bit", "ber"),
]
REPLACED_TABLES = ["link_tx_table", "link_rx_table", "ber_test_display", "ber_test_time",
                   "rx_snr_value_link", "rx_ebno_value_link",
                   "rx_snr_value_to_link_rx_table", "rx_ebno_value_to_link_rx_table"]


def spreadsheet(graph, rows=SIM_ROWS):
    """Show the link budget and BER test as one spreadsheet-style table.

    Stock Probe Signal blocks hold the latest value of each stream; a stock
    Python Snippet builds a Qt table (gridlines, header row) on the link-budget
    tab and refreshes it four times a second. Display only: no DSP changes.
    Safe to run repeatedly.
    """
    drop = set(REPLACED_TABLES) | {b["name"] for b in graph["blocks"]
                                   if b["name"].startswith("probe_")
                                   or b["name"] in ("link_table", "rf_constellation",
                                                    "rf_constellation_input")}
    graph["blocks"][:] = [b for b in graph["blocks"] if b["name"] not in drop]
    graph["connections"][:] = [c for c in graph["connections"]
                               if c[0] not in drop and c[2] not in drop]
    blocks = {b["name"]: b for b in graph["blocks"]}

    def add(block_name, kind, x, y, **parameters):
        node = dict(name=block_name, id=kind,
                    parameters={k: str(v) for k, v in parameters.items()},
                    states=dict(coordinate=[x, y], rotation=0, state="enabled"))
        graph["blocks"].append(node)
        blocks[block_name] = node

    probes = []
    for _, _, source, _, _ in rows:
        if source and f"probe_{source}" not in blocks:
            sx, sy = blocks[source]["states"]["coordinate"]
            add(f"probe_{source}", "blocks_probe_signal_x", sx + 40, sy + 90, type="float")
            graph["connections"].append([source, "0", f"probe_{source}", "0"])
            probes.append(source)

    table_rows = ",\n".join(
        f"    ({section!r}, {quantity!r}, {('self.probe_' + source) if source else 'None'}, "
        f"{unit!r}, {fmt!r})" for section, quantity, source, unit, fmt in rows)
    code = f'''# Link budget and BER test as a spreadsheet-style table (display only).
# Values come from stock Probe Signal blocks; edit rows here to change it.
rows = [
{table_rows},
]
table = Qt.QTableWidget(len(rows), 4)
table.setHorizontalHeaderLabels(["Section", "Quantity", "Value", "Unit"])
table.verticalHeader().setVisible(False)
table.setEditTriggers(Qt.QAbstractItemView.NoEditTriggers)
table.setSelectionMode(Qt.QAbstractItemView.NoSelection)
table.setAlternatingRowColors(True)
table.setShowGrid(True)
bold = Qt.QFont(table.font())
bold.setBold(True)
for row, (section, quantity, probe, unit, fmt) in enumerate(rows):
    for column, text in ((0, section), (1, quantity), (3, unit)):
        item = Qt.QTableWidgetItem(text)
        if column == 0:
            item.setFont(bold)
        table.setItem(row, column, item)
    value = Qt.QTableWidgetItem("" if probe else str(eval(fmt)))
    value.setTextAlignment(Qt.Qt.AlignRight | Qt.Qt.AlignVCenter)
    table.setItem(row, 2, value)
header = table.horizontalHeader()
header.setSectionResizeMode(Qt.QHeaderView.ResizeToContents)
header.setStretchLastSection(True)
test_bits = 10000 * self.ber_test_blocks

def refresh_link_table():
    for row, (section, quantity, probe, unit, fmt) in enumerate(rows):
        if probe is None:
            continue
        level = probe.level()
        if fmt == "dB":
            text = f"{{level:.2f}}"
        elif fmt == "count":
            text = f"{{level:,.0f}}"
        elif fmt == "ber":
            text = f"{{level:.3e}}"
        else:
            text = "complete" if level >= test_bits else (
                "counting" if level > 0 else "waiting for warm-up")
        table.item(row, 2).setText(text)

self.link_table = table
self.link_table_timer = Qt.QTimer()
self.link_table_timer.timeout.connect(refresh_link_table)
self.link_table_timer.start(int(1000 * self.plot_update_s))
self.views_grid_layout_3.addWidget(table, 1, 0, 2, 1)
'''
    x, y = blocks["ber_test_seconds"]["states"]["coordinate"]
    add("link_table", "snippet", x, y + 90, section="main_after_init", priority="1",
        code=code)
    # Right column: RX spectrum and a received constellation for quick checks.
    blocks["spectrum_budget"]["parameters"]["gui_hint"] = "views@3:1,1,1,1"
    sx, sy = blocks["spectrum_budget"]["states"]["coordinate"]
    add("rf_constellation_input", "virtual_source", sx, sy + 140, stream_id="rx_symbols")
    add("rf_constellation", "qtgui_const_sink_x", sx + 180, sy + 140, type="complex",
        name="Received symbols (after equalizer)", size="1024", nconnections="1",
        grid="True", autoscale="False", xmin="-2", xmax="2", ymin="-2", ymax="2",
        gui_hint="views@3:2,1,1,1", label1="RX", color1='"blue"', marker1="0",
        style1="0", alpha1="0.4", width1="1", update_time="0.10",
        tr_mode="qtgui.TRIG_MODE_FREE", tr_slope="qtgui.TRIG_SLOPE_POS", tr_level="0.0",
        tr_chan="0", tr_tag='""', legend="False", axislabels="True")
    graph["connections"].append(["rf_constellation_input", "0", "rf_constellation", "0"])
    return graph


if __name__ == "__main__":
    for file in sorted((ROOT / "grc").glob("single_carrier_*.grc")):
        graph = apply(yaml.safe_load(file.read_text()))
        file.write_text(yaml.safe_dump(graph, sort_keys=False, width=110))
        print("updated", file.relative_to(ROOT))
