"""Replace the link-budget tab's time charts with readout tables and add a
fixed-length BER test. Only stock GNU Radio blocks are used.

GRC has no table widget, so each table is one stock QT GUI Number Sink with
several labelled inputs, rendered as a header row of names over a row of
values with units. All inputs of a table run at the same rate (one value per
4096 samples), so the readouts update together.

Link-budget tab (2x2):
    Transmit table    | Receive table
    RX spectrum       | BER test table
plus a text label under the tables with the BER test's length and duration.

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
TX_ROWS = [("tx_dbm", "Average", "dBm"), ("tx_peak_dbm", "Sampled peak", "dBm"),
           ("tx_papr", "Peak/average", "dB")]
RX_ROWS = [("rx_dbm", "Signal + noise", "dBm"), ("rx_snr", "SNR over Fs", "dB"),
           ("rx_ebno", "Eb/N0 per bit", "dB")]


def number_table(name, title, rows, gui_hint):
    parameters = dict(name=title, type="float", nconnections=str(len(rows)),
                      autoscale="False", avg="0", graph_type="qtgui.NUM_GRAPH_NONE",
                      min="-200", max="100", update_time="0.25", gui_hint=gui_hint)
    for index, (_, label, unit) in enumerate(rows, start=1):
        parameters.update({f"label{index}": label, f"unit{index}": unit,
                           f"color{index}": '("black", "black")', f"factor{index}": "1"})
    return parameters


def apply(graph):
    blocks = {b["name"]: b for b in graph["blocks"]}
    converted = "link_tx_table" in blocks
    anchor = blocks["link_tx_table" if converted else "power_history"]["states"]["coordinate"]
    # Safe to re-run: layout tools may recreate old charts; always strip them.
    graph["blocks"][:] = [b for b in graph["blocks"] if b["name"] not in REMOVED]
    graph["connections"][:] = [c for c in graph["connections"]
                               if c[0] not in REMOVED and c[2] not in REMOVED]
    blocks = {b["name"]: b for b in graph["blocks"]}
    if converted:
        blocks["spectrum_budget"]["parameters"].update(gui_hint="views@3:2,0,1,1", label1="RX")
        return ber_test(graph)
    anchor = [anchor[0] - 200, anchor[1]]
    x0, y0 = anchor

    def add(block_name, kind, dx, dy, **parameters):
        node = dict(name=block_name, id=kind, parameters={k: str(v) for k, v in parameters.items()},
                    states=dict(coordinate=[x0 + dx, y0 + dy], rotation=0, state="enabled"))
        graph["blocks"].append(node)
        blocks[block_name] = node

    def wire(src, dst, dst_port=0):
        graph["connections"].append([src, "0", dst, str(dst_port)])

    def link(source, stream, sink_xy, target, target_port, source_xy):
        """Short stock virtual link instead of a long canvas wire."""
        sink_name, source_name = f"{stream}_link", f"{stream}_to_{target}"
        if sink_name not in blocks:
            graph["blocks"].append(dict(
                name=sink_name, id="virtual_sink", parameters=dict(stream_id=stream),
                states=dict(coordinate=list(sink_xy), rotation=0, state="enabled")))
            blocks[sink_name] = graph["blocks"][-1]
            graph["connections"].append([source, "0", sink_name, "0"])
        graph["blocks"].append(dict(
            name=source_name, id="virtual_source", parameters=dict(stream_id=stream),
            states=dict(coordinate=[x0 + source_xy[0], y0 + source_xy[1]], rotation=0,
                        state="enabled")))
        blocks[source_name] = graph["blocks"][-1]
        graph["connections"].append([source_name, "0", target, str(target_port)])

    add("tx_papr", "blocks_sub_xx", 0, 0, type="float", vlen="1", num_inputs="2")
    wire("tx_peak_dbm", "tx_papr", 0)
    wire("tx_dbm", "tx_papr", 1)
    add("link_tx_table", "qtgui_number_sink", 200, 0,
        **number_table("link_tx_table", "Transmit (conducted, nominal)", TX_ROWS,
                       "views@3:1,0,1,1"))
    add("link_rx_table", "qtgui_number_sink", 200, 140,
        **number_table("link_rx_table", "Receive (noise over Fs)", RX_ROWS,
                       "views@3:1,1,1,1"))
    for port, (source, _, _) in enumerate(TX_ROWS):
        wire(source, "link_tx_table", port)
    wire("rx_dbm", "link_rx_table", 0)
    # SNR / Eb/N0 readouts sit elsewhere on the canvas; bring them over with
    # short virtual links.
    for port, source in ((1, "rx_snr"), (2, "rx_ebno")):
        sx, sy = blocks[source]["states"]["coordinate"]
        link(source, f"{source}_value", (sx + 200, sy + 60), "link_rx_table", port,
             (40, 140 + 70 * port))

    blocks["spectrum_budget"]["parameters"].update(gui_hint="views@3:2,0,1,1", label1="RX")
    return ber_test(graph)


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
    x0, y0 = blocks["link_tx_table"]["states"]["coordinate"]
    x0, y0 = x0 - 200, y0 + 280

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
    add("ber_test_time", "variable_qtgui_label", 1700, 472, label="BER test",
        type="string", formatter="None", gui_hint="views@3:3,0,1,2",
        value="'%d-bit test: result after about %.2f s at %g Mbit/s, then it holds' "
              "% (10000*ber_test_blocks, ber_test_seconds, bit_rate/1e6)")

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
    add("ber_test_display", "qtgui_number_sink", x0 + 1040, y0,
        **number_table("ber_test_display", "BER test",
                       [(None, "Bits compared", "bits"), (None, "Bit errors", "errors"),
                        (None, "BER", "errors/bit")], "views@3:2,1,1,1"))
    blocks["ber_test_display"]["parameters"].update(min="0", max="1e12")
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
    wire("ber_test_count", "ber_test_display", 0)
    wire("ber_test_errors", "ber_test_display", 1)
    wire("ber_test_ratio", "ber_test_display", 2)
    return graph


if __name__ == "__main__":
    for file in sorted((ROOT / "grc").glob("single_carrier_*.grc")):
        graph = apply(yaml.safe_load(file.read_text()))
        file.write_text(yaml.safe_dump(graph, sort_keys=False, width=110))
        print("updated", file.relative_to(ROOT))
