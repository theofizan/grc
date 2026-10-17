"""Apply display improvements while preserving saved DSP settings and wiring."""

from pathlib import Path
import json
import yaml
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "configs/control_layout.json"


def improve(graph):
    from label_sections import remove_sections

    graph = remove_sections(graph)
    # Keep body placement stable when repacking controls repeatedly.
    base_canvas = json.loads((ROOT / "configs/base_canvas.json").read_text())
    for node in graph["blocks"]:
        if node["name"] in base_canvas:
            node["states"]["coordinate"] = base_canvas[node["name"]]
    nodes = graph["blocks"]
    edges = graph["connections"]
    old = {b["name"]: b for b in nodes}

    def add(block_id, kind, x, y, **parameters):
        if block_id not in old:
            node = dict(
                name=block_id,
                id=kind,
                parameters={k: str(v) for k, v in parameters.items()},
                states=dict(coordinate=[x, y], rotation=0, state="enabled"),
            )
            nodes.append(node)
            old[block_id] = node
        else:
            old[block_id]["states"]["coordinate"] = [x, y]

    def wire(source, target, port=0):
        edge = [source, "0", target, str(port)]
        if edge not in edges:
            edges.append(edge)

    # Save the user's BPSK grouping once. Regeneration keeps this project preference.
    positions = json.loads(LAYOUT.read_text())
    for name, coordinate in positions.items():
        if name in old:
            old[name]["states"]["coordinate"] = coordinate
    # Rectangular ASK objects show more fields and need a taller clear area.
    if old["const"]["id"] == "variable_constellation_rect":
        old["const"]["states"]["coordinate"] = [1120, 8]
    add("chart_math", "import", 1120, 1380, imports="import math\nimport numpy")
    add(
        "evm_guide_percent",
        "parameter",
        1120,
        1490,
        value=5,
        type="eng_float",
        label="Constellation guide radius (% RMS)",
        short_id="",
        hide="none",
    )
    for name, value, x in [
        (
            "snr_rx_db",
            "expected_rx_dbm-rx_noise_dbm if noise_enabled else float('inf')",
            16,
        ),
        ("esno_rx_db", "snr_rx_db+10*math.log10(samp_rate/symbol_rate)", 350),
        ("ebno_rx_db", "snr_rx_db+10*math.log10(samp_rate/bit_rate)", 720),
    ]:
        add(name, "variable", x, 2180, value=value)
    # Actual measured-TX-average readout, using known loss and configured noise.
    for name, source, offset, title, column in [
        (
            "snr_display",
            "rx_snr",
            "-path_loss_db-rx_noise_dbm",
            "RX SNR | noise over Fs",
            0,
        ),
        (
            "ebno_display",
            "rx_ebno",
            "-path_loss_db-rx_noise_dbm+10*math.log10(samp_rate/bit_rate)",
            "RX Eb/N0 | known TX and noise",
            1,
        ),
    ]:
        add(
            source,
            "blocks_add_const_vxx",
            350 + column * 400,
            2310,
            type="float",
            vlen=1,
            const=f"{offset} if noise_enabled else float('inf')",
        )
        add(
            name,
            "qtgui_number_sink",
            550 + column * 400,
            2310,
            type="float",
            name=title,
            nconnections=1,
            autoscale="False",
            avg=0,
            graph_type="qtgui.NUM_GRAPH_NONE",
            min=-100,
            max=100,
            label1=title,
            unit1="dB",
            gui_hint=f"views@3:3,{column},1,1",
        )
        wire("tx_dbm", source)
        wire(source, name)
    # TX symbol monitor reproduces generic_mod's stock packing/differential mapping.
    m = {
        "single_carrier_bpsk": 2,
        "single_carrier_qpsk": 4,
        "single_carrier_8psk": 8,
        "single_carrier_4ask": 4,
        "single_carrier_8ask": 8,
        "single_carrier_16qam": 16,
    }[graph["options"]["parameters"]["id"]]
    add("tx_symbol_input", "virtual_source", 16, 2480, stream_id="reference")
    add(
        "tx_symbol_chunks",
        "blocks_packed_to_unpacked_xx",
        160,
        2480,
        type="byte",
        bits_per_chunk="k",
        endianness="gr.GR_MSB_FIRST",
        num_ports=1,
    )
    add(
        "tx_symbol_diff",
        "digital_diff_encoder_bb",
        380,
        2480,
        modulus=m,
        coding="digital.DIFF_DIFFERENTIAL",
    )
    add(
        "tx_symbols",
        "digital_chunks_to_symbols_xx",
        600,
        2480,
        in_type="byte",
        out_type="complex",
        symbol_table="const.points()",
        dimension=1,
    )
    wire("tx_symbol_input", "tx_symbol_chunks")
    wire("tx_symbol_chunks", "tx_symbol_diff")
    wire("tx_symbol_diff", "tx_symbols")
    add(
        "tx_constellation",
        "qtgui_const_sink_x",
        840,
        2480,
        type="complex",
        name="TX symbols | before RRC pulse shaping",
        size=1024,
        nconnections=3,
        grid="True",
        autoscale="False",
        xmin=-2,
        xmax=2,
        ymin=-2,
        ymax=2,
        gui_hint="views@0:2,0,1,1",
    )
    wire("tx_symbols", "tx_constellation")
    add(
        "ideal_symbols",
        "blocks_vector_source_x",
        16,
        2640,
        type="complex",
        vector="const.points()",
        repeat="True",
        vlen=1,
        tags="[]",
    )
    circles = "[p+symbol_rms*evm_guide_percent/100*complex(math.cos(t),math.sin(t)) for p in const.points() for t in numpy.linspace(0,2*math.pi,64,endpoint=False)]"
    add(
        "evm_circles",
        "blocks_vector_source_x",
        420,
        2640,
        type="complex",
        vector=circles,
        repeat="True",
        vlen=1,
        tags="[]",
    )
    for target in ["constellation", "tx_constellation"]:
        wire("ideal_symbols", target, 1)
        wire("evm_circles", target, 2)
        old[target]["parameters"].update(
            nconnections="3",
            label1="RX symbols" if target == "constellation" else "TX encoded symbols",
            label2="Ideal reference",
            label3="EVM radius guide (% RMS)",
            color1='"blue"',
            color2='"black"',
            color3='"dark green"',
            marker1="0",
            marker2="8",
            marker3="0",
            style1="0",
            style2="0",
            style3="0",
            alpha1="0.3",
            alpha2="1.0",
            alpha3="0.5",
            xmin="-2",
            xmax="2",
            ymin="-2",
            ymax="2",
        )
    old["constellation"]["parameters"]["gui_hint"] = "views@0:2,1,1,1"
    old["spectrum"]["parameters"]["gui_hint"] = "views@1:0,0,1,1"
    old["waveform"]["parameters"]["gui_hint"] = "views@1:0,1,1,1"
    old["power_history"]["parameters"]["gui_hint"] = "views@3:1,0,1,1"
    old["envelope_plot"]["parameters"]["gui_hint"] = "views@3:1,1,1,1"
    # Separate I/Q eyes to compare receiver stages in tiled dashboards.
    old["eye"]["parameters"].update(type="float", gui_hint="views@2:0,0,1,1")
    edge = ["eye_input", "0", "eye", "0"]
    if edge in edges:
        edges.remove(edge)
    add("eye_i", "blocks_complex_to_real", 800, 2640, vlen=1)
    add("eye_q", "blocks_complex_to_imag", 980, 2640, vlen=1)
    add(
        "eye_quadrature",
        "qtgui_eye_sink_x",
        1140,
        2640,
        type="float",
        size=1024,
        samp_per_symbol="sps",
        srate="samp_rate",
        nconnections=1,
        grid="True",
        autoscale="True",
        gui_hint="views@2:0,1,1,1",
    )
    wire("eye_input", "eye_i")
    wire("eye_input", "eye_q")
    wire("eye_i", "eye")
    wire("eye_q", "eye_quadrature")
    # Local virtual links keep ideal points, guide circles, and readouts from
    # drawing cables through unrelated sections of the canvas.
    for source, stream in [
        ("ideal_symbols", "ideal_points"),
        ("evm_circles", "guide_circles"),
        ("tx_dbm", "sensed_tx_dbm"),
    ]:
        add(
            source + "_link",
            "virtual_sink",
            (
                160
                if source == "ideal_symbols"
                else 620 if source == "evm_circles" else 780
            ),
            2720 if source != "tx_dbm" else 1560,
            stream_id=stream,
        )
        wire(source, source + "_link")
    for source in ["ideal_symbols", "evm_circles"]:
        edges[:] = [
            edge
            for edge in edges
            if not (
                edge[0] == source and edge[2] in ["constellation", "tx_constellation"]
            )
        ]
    for chart, x, y in [("constellation", 16, 930), ("tx_constellation", 620, 2570)]:
        for index, stream in [(1, "ideal_points"), (2, "guide_circles")]:
            name = chart + "_reference_" + str(index)
            add(name, "virtual_source", x, y + (index - 1) * 70, stream_id=stream)
            wire(name, chart, index)
    for target, x in [("rx_snr", 16), ("rx_ebno", 620)]:
        edge = ["tx_dbm", "0", target, "0"]
        if edge in edges:
            edges.remove(edge)
        add(target + "_input", "virtual_source", x, 2310, stream_id="sensed_tx_dbm")
        wire(target + "_input", target)
    add("eye_q_input", "virtual_source", 480, 1250, stream_id="rx_iq")
    edge = ["eye_input", "0", "eye_q", "0"]
    if edge in edges:
        edges.remove(edge)
    wire("eye_q_input", "eye_q")
    for name, coordinate in {
        "eye_i": (160, 1250),
        "eye": (300, 1250),
        "eye_q": (620, 1250),
        "eye_quadrature": (760, 1250),
        "timing_input": (1040, 1250),
        "timing_error": (1180, 1250),
        "scope": (16, 1540),
        "rx_snr": (160, 2310),
        "snr_display": (350, 2310),
        "rx_ebno": (780, 2310),
        "ebno_display": (980, 2310),
    }.items():
        old[name]["states"]["coordinate"] = list(coordinate)
    # The receiver update fills this stock snippet with 2x2 dashboard sizing.
    code = "# Dashboard layout is configured below."
    add(
        "square_plot_panels",
        "snippet",
        1120,
        2800,
        section="main_after_init",
        priority=0,
        code=code,
    )
    old["eye"]["parameters"]["ylabel"] = "RX in-phase amplitude"
    old["eye_quadrature"]["parameters"]["ylabel"] = "RX quadrature amplitude"
    old["square_plot_panels"]["parameters"]["code"] = code
    old["constellation"]["parameters"][
        "name"
    ] = "RX: blue symbols / black ideal / green EVM guide"
    old["tx_constellation"]["parameters"][
        "name"
    ] = "TX before RRC: blue symbols / black ideal / green guide"
    # Keep every RF-derived quantity with the header controls rather than
    # scattering variables between signal/plot branches.
    for name, x in [
        ("tx_amplitude", 16),
        ("path_gain", 216),
        ("expected_rx_dbm", 416),
        ("noise_volt", 616),
        ("snr_rx_db", 816),
        ("esno_rx_db", 1016),
        ("ebno_rx_db", 1216),
    ]:
        old[name]["states"]["coordinate"] = [x, 64]
    for name, x in [
        ("evm_guide_percent", 520),
        ("reference_delay", 760),
        ("ber_window", 980),
        ("warmup_bits", 1160),
    ]:
        old[name]["states"]["coordinate"] = [x, 120]
    if old["const"]["id"] == "variable_constellation_rect":
        old["const"]["states"]["coordinate"] = [1400, 8]
    from receiver_updates import update

    return update(graph)


if __name__ == "__main__":
    if not LAYOUT.exists():
        bpsk = yaml.safe_load((ROOT / "grc/single_carrier_bpsk.grc").read_text())
        LAYOUT.write_text(
            json.dumps(
                {
                    b["name"]: b["states"]["coordinate"]
                    for b in bpsk["blocks"]
                    if b["id"] in ["variable", "parameter", "variable_constellation"]
                },
                indent=2,
            )
            + "\n"
        )
    for file in (ROOT / "grc").glob("*.grc"):
        graph = improve(yaml.safe_load(file.read_text()))
        file.write_text(yaml.safe_dump(graph, sort_keys=False, width=110))
        profile = file.stem.replace("single_carrier_", "")
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/pack_controls.py"),
                "--modulation",
                profile,
            ],
            check=True,
        )
    print("Updated and tightly packed six saved flowcharts")
