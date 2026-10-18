"""Replace the link-budget tab's time charts with readout tables and add a
fixed-length BER test. Only stock GNU Radio blocks are used.

GRC has no table widget, so each table is one stock QT GUI Number Sink with
several labelled inputs, rendered as a header row of names over a row of
values with units. All inputs of a table run at the same rate (one value per
4096 samples), so the readouts update together.

Link-budget tab (2x2):
    Transmit table    | Receive table
    RX spectrum       | BER test result
plus a text label under the tables with the BER test's estimated duration.

BER test: the stock error stream (XOR -> UChar to Float) also feeds
Integrate(10000) -> Integrate(ber_test_bits/10000) -> Multiply, so the BER
test readout shows the BER of each consecutive block of ber_test_bits compared
bits (rounded to a multiple of 10,000; a single huge Integrate overflows the
scheduler). There is deliberately no Head block: a finished Head stops the
whole flowgraph, radios included. scripts/run_n210_ber.py runs exactly N bits
and saves the result. The rolling 10,000-bit BER display is unchanged.

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
        return graph
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

    # Fixed-length BER test on the same stock error stream as the BER display.
    # Its control and derived variables go with the other controls at the top.
    def top(name, kind, x, y, **parameters):
        add(name, kind, 0, 0, **parameters)
        blocks[name]["states"]["coordinate"] = [x, y]

    top("ber_test_bits", "parameter", 1700, 8, value="1000000", type="intx",
        label="BER test length (compared bits)", short_id="", hide="none")
    top("ber_test_blocks", "variable", 1700, 100,
        value="max(1, int(ber_test_bits) // 10000)")
    top("ber_test_seconds", "variable", 1700, 170,
        value="(warmup_bits + ber_test_bits) / bit_rate")
    top("ber_test_time", "variable_qtgui_label", 1700, 240,
        label="BER test", type="string", formatter="None", gui_hint="views@3:3,0,1,2",
        value="'%d-bit blocks: first result after about %.2f s at %g Mbit/s' "
              "% (10000 * ber_test_blocks, ber_test_seconds, bit_rate / 1e6)")
    add("ber_test_sum_10k", "blocks_integrate_xx", 180, 280, type="float", decim="10000",
        vlen="1")
    add("ber_test_sum", "blocks_integrate_xx", 180, 360, type="float",
        decim="ber_test_blocks", vlen="1")
    add("ber_test_scale", "blocks_multiply_const_vxx", 360, 280, type="float",
        const="1.0/(10000*ber_test_blocks)", vlen="1")
    add("ber_test_display", "qtgui_number_sink", 540, 280,
        name="BER test | latest complete block (0 until the first block ends)",
        type="float",
        nconnections="1", autoscale="False", avg="0", graph_type="qtgui.NUM_GRAPH_NONE",
        min="0", max="1", update_time="0.25", gui_hint="views@3:2,1,1,1",
        label1="BER over block", unit1="errors/bit", color1='("black", "black")',
        factor1="1")
    ex, ey = blocks["errors_float"]["states"]["coordinate"]
    link("errors_float", "bit_errors", (ex, ey + 70), "ber_test_sum_10k", 0, (0, 280))
    wire("ber_test_sum_10k", "ber_test_sum")
    wire("ber_test_sum", "ber_test_scale")
    wire("ber_test_scale", "ber_test_display")
    blocks["spectrum_budget"]["parameters"].update(gui_hint="views@3:2,0,1,1", label1="RX")
    return graph


if __name__ == "__main__":
    for file in sorted((ROOT / "grc").glob("single_carrier_*.grc")):
        graph = apply(yaml.safe_load(file.read_text()))
        file.write_text(yaml.safe_dump(graph, sort_keys=False, width=110))
        print("updated", file.relative_to(ROOT))
