"""Stock LMS equalization and compact 2x2 dashboards. Preserves saved controls."""


def update(graph):
    nodes = graph["blocks"]
    edges = graph["connections"]
    by = {b["name"]: b for b in nodes}

    def add(block_id, kind, x, y, **params):
        if block_id not in by:
            b = dict(
                name=block_id,
                id=kind,
                parameters={k: str(v) for k, v in params.items()},
                states=dict(coordinate=[x, y], rotation=0, state="enabled"),
            )
            nodes.append(b)
            by[block_id] = b
        else:
            by[block_id]["states"]["coordinate"] = [x, y]

    def wire(a, b, port=0):
        e = [a, "0", b, str(port)]
        if e not in edges:
            edges.append(e)

    add(
        "eq_taps",
        "parameter",
        16,
        100,
        value=11,
        type="intx",
        label="Adaptive equalizer taps",
        short_id="",
        hide="none",
    )
    add(
        "eq_step",
        "parameter",
        200,
        100,
        value=0.01,
        type="eng_float",
        label="LMS adaptation step",
        short_id="",
        hide="none",
    )
    add(
        "channel_echo",
        "parameter",
        400,
        100,
        value=0,
        type="eng_float",
        label="One-symbol echo voltage ratio",
        short_id="",
        hide="none",
    )
    add(
        "eq_algorithm",
        "variable_adaptive_algorithm",
        16,
        200,
        type="lms",
        cons="const",
        step_size="eq_step/(eq_taps*symbol_rms**2)",
    )
    add(
        "equalizer",
        "digital_linear_equalizer",
        1330,
        280,
        num_taps="eq_taps",
        sps=1,
        alg="eq_algorithm",
        adapt_after_training="True",
        training_sequence="[]",
        training_start_tag="",
    )
    edges[:] = [
        [
            (
                "equalizer"
                if a == "rx_scale" and b not in ["equalizer", "pre_eq_link"]
                else a
            ),
            ap,
            b,
            bp,
        ]
        for a, ap, b, bp in edges
    ]
    wire("rx_scale", "equalizer")
    add("pre_eq_link", "virtual_sink", 1170, 460, stream_id="pre_eq_symbols")
    wire("rx_scale", "pre_eq_link")
    by["decoder"]["states"]["coordinate"] = [1530, 280]
    by["decoded_link"]["states"]["coordinate"] = [1730, 280]
    # A power-normalized, one-symbol delayed echo makes ISI reproducible while
    # retaining the nominal average link loss for random data.
    by["channel"]["parameters"][
        "taps"
    ] = "[path_gain/(1+channel_echo**2)**0.5]+[0j]*(sps-1)+[path_gain*channel_echo/(1+channel_echo**2)**0.5]"
    add("before_eq_input", "virtual_source", 16, 2920, stream_id="pre_eq_symbols")
    add(
        "before_eq_constellation",
        "qtgui_const_sink_x",
        200,
        2920,
        type="complex",
        name="Middle: timed symbols before adaptive EQ",
        size=1024,
        nconnections=1,
        grid="True",
        autoscale="False",
        xmin=-2,
        xmax=2,
        ymin=-2,
        ymax=2,
        gui_hint="views@0:1,0,1,1",
    )
    wire("before_eq_input", "before_eq_constellation")
    # Display-only RRC synthesis reconstructs eye traces from symbol streams.
    add(
        "eye_synthesis_taps",
        "variable",
        600,
        200,
        value="firdes.root_raised_cosine(sps,sps,1.0,alpha,11*sps)",
    )
    for stage, stream, y in [
        ("middle", "pre_eq_symbols", 3080),
        ("after", "rx_symbols", 3260),
        ("tx_eye", "tx_iq", 3440),
    ]:
        add(stage + "_input", "virtual_source", 16, y, stream_id=stream)
        source = stage + "_input"
        if stage != "tx_eye":
            add(
                stage + "_eye_reconstruction",
                "interp_fir_filter_xxx",
                180,
                y,
                type="ccf",
                interp="sps",
                taps="eye_synthesis_taps",
                samp_delay=0,
            )
            wire(source, stage + "_eye_reconstruction")
            source = stage + "_eye_reconstruction"
        for iq, kind, x in [
            ("i", "blocks_complex_to_real", 420),
            ("q", "blocks_complex_to_imag", 880),
        ]:
            name = stage + "_" + iq
            add(name, kind, x, y, vlen=1)
            wire(source, name)
            add(
                name + "_eye",
                "qtgui_eye_sink_x",
                x + 180,
                y,
                type="float",
                size=1024,
                samp_per_symbol="sps",
                srate="samp_rate",
                nconnections=1,
                grid="True",
                autoscale="True",
                ylabel=(
                    stage.upper()
                    + " "
                    + iq.upper()
                    + " | "
                    + ("reconstructed" if stage != "tx_eye" else "TX shaped")
                ),
                gui_hint="",
            )
            wire(name, name + "_eye")
    # Timing-error history becomes the fourth waveform panel.
    add("tx_wave_input", "virtual_source", 16, 3620, stream_id="tx_iq")
    add(
        "tx_waveform",
        "qtgui_time_sink_x",
        200,
        3620,
        type="complex",
        name="Clean TX waveform | I/Q",
        size=512,
        srate="samp_rate",
        nconnections=1,
        gui_hint="",
    )
    wire("tx_wave_input", "tx_waveform")
    add("evm_meter_history_input", "virtual_source", 600, 3620, stream_id="evm_history")
    add(
        "eq_evm_history",
        "qtgui_time_sink_x",
        800,
        3620,
        type="float",
        name="Equalized decision-directed RMS EVM (%)",
        size=128,
        srate="symbol_rate",
        nconnections=1,
        autoscale="True",
        gui_hint="",
    )
    wire("evm_meter_history_input", "eq_evm_history")
    by["views"]["parameters"].update(
        num_tabs="6",
        label0="Constellations: TX / middle / equalized",
        label1="Waveform / spectrum / timing",
        label2="I eyes: TX / RX / middle / equalized",
        label3="Link budget",
        label4="Q eyes: TX / RX / middle / equalized",
        label5="BER and EVM histories",
    )
    groups = {
        0: [
            "tx_constellation",
            "before_eq_constellation",
            "constellation",
            "eq_evm_history",
        ],
        1: ["tx_waveform", "waveform", "spectrum", "timing_error"],
        2: ["tx_eye_i_eye", "eye", "middle_i_eye", "after_i_eye"],
        3: [
            "power_history",
            "envelope_plot",
            "spectrum_budget",
            "power_reference_chart",
        ],
        4: ["tx_eye_q_eye", "eye_quadrature", "middle_q_eye", "after_q_eye"],
        5: ["ber_history", "evm_history", "eq_error_trace", "timing_history_copy"],
    }
    # Two useful link-budget plots complete its dashboard: RX waveform and
    # expected-vs-measured power are represented without adding DSP estimators.
    for new_name, kind, source, title, rate, y in [
        (
            "spectrum_budget",
            "qtgui_freq_sink_x",
            "channel",
            "RX spectrum | relative level",
            "samp_rate",
            3800,
        ),
        (
            "power_reference_chart",
            "qtgui_time_sink_x",
            "rx_snr",
            "RX SNR over Fs | known reference",
            "samp_rate/4096",
            3960,
        ),
        (
            "eq_error_trace",
            "qtgui_time_sink_x",
            "evm",
            "Per-symbol equalized EVM (%)",
            "symbol_rate",
            4120,
        ),
        (
            "timing_history_copy",
            "qtgui_time_sink_x",
            "clock_sync",
            "Timing-loop error",
            "symbol_rate",
            4280,
        ),
    ]:
        params = dict(
            type="complex" if kind == "qtgui_freq_sink_x" else "float",
            name=title,
            nconnections=1,
            gui_hint="",
        )
        if kind == "qtgui_freq_sink_x":
            params.update(fftsize=1024, wintype="window.WIN_HANN", fc=0, bw=rate)
        else:
            params.update(size=128, srate=rate, autoscale="True")
        add(new_name, kind, 800, y, **params)
        e = [source, "1" if source == "clock_sync" else "0", new_name, "0"]
        if e not in edges:
            edges.append(e)
    for tab, names in groups.items():
        for index, name in enumerate(names):
            # Row zero is reserved for numbers; charts occupy a complete 2x2.
            by[name]["parameters"][
                "gui_hint"
            ] = f"views@{tab}:{1+index//2},{index%2},1,1"
    # Show the adaptive coefficients themselves while the equalizer runs.
    # Tap vectors are decimated only for display; the equalizer still adapts
    # on every symbol and the decision stream is unaffected.
    nodes[:] = [node for node in nodes if node["name"] != "timing_history_copy"]
    edges[:] = [edge for edge in edges if edge[2] != "timing_history_copy"]
    add(
        "eq_tap_decimator",
        "blocks_keep_one_in_n",
        16,
        4440,
        type="complex",
        vlen="eq_taps",
        n=1000,
    )
    add("eq_tap_magnitudes", "blocks_complex_to_mag", 260, 4440, vlen="eq_taps")
    add(
        "eq_tap_plot",
        "qtgui_vector_sink_f",
        500,
        4440,
        name="Adaptive LMS tap magnitudes | updated during convergence",
        vlen="eq_taps",
        x_start=0,
        x_step=1,
        x_axis_label="Tap index",
        y_axis_label="Magnitude",
        nconnections=1,
        autoscale="True",
        grid="True",
        gui_hint="views@5:2,1,1,1",
    )
    edge = ["equalizer", "1", "eq_tap_decimator", "0"]
    if edge not in edges:
        edges.append(edge)
    wire("eq_tap_decimator", "eq_tap_magnitudes")
    wire("eq_tap_magnitudes", "eq_tap_plot")
    for name, title in {
        "tx_eye_i_eye": "TX I | shaped waveform",
        "tx_eye_q_eye": "TX Q | shaped waveform",
        "eye": "RX I | raw channel output",
        "eye_quadrature": "RX Q | raw channel output",
        "middle_i_eye": "Middle I | before EQ, reconstructed",
        "middle_q_eye": "Middle Q | before EQ, reconstructed",
        "after_i_eye": "After EQ I | reconstructed",
        "after_q_eye": "After EQ Q | reconstructed",
    }.items():
        by[name]["parameters"]["label1"] = title
    # Keep diagnostic wires local on the editable canvas as well as in the GUI.
    # These stock virtual links carry the same stream, including tap vectors.
    for source, source_port, target, stream, link_x, link_y, input_x, input_y in [
        ("channel", "0", "spectrum_budget", "rx_iq", None, None, 16, 3800),
        ("rx_snr", "0", "power_reference_chart", "snr_history", 350, 2390, 620, 3800),
        ("evm", "0", "eq_error_trace", "evm_per_symbol", 160, 1170, 16, 4000),
        (
            "equalizer",
            "1",
            "eq_tap_decimator",
            "adaptive_tap_vectors",
            1430,
            440,
            600,
            4000,
        ),
    ]:
        if link_x is not None:
            add(stream + "_link", "virtual_sink", link_x, link_y, stream_id=stream)
            edge = [source, source_port, stream + "_link", "0"]
            if edge not in edges:
                edges.append(edge)
        edges[:] = [e for e in edges if e != [source, source_port, target, "0"]]
        add(target + "_input", "virtual_source", input_x, input_y, stream_id=stream)
        wire(target + "_input", target)
    for name, position in {
        "spectrum_budget": (200, 3800),
        "power_reference_chart": (800, 3800),
        "eq_error_trace": (200, 4000),
        "eq_tap_decimator": (780, 4000),
        "eq_tap_magnitudes": (1010, 4000),
        "eq_tap_plot": (1210, 4000),
    }.items():
        by[name]["states"]["coordinate"] = list(position)
    # Keep the receiver signal path on one compact row.
    for name, position in {
        "rx_scale": (1170, 280),
        "equalizer": (1330, 280),
        "decoder": (1530, 280),
        "decoded_link": (1730, 280),
    }.items():
        by[name]["states"]["coordinate"] = list(position)
    # Remove square constraints. Native plot widgets now stretch with each tile.
    by["square_plot_panels"]["parameters"][
        "code"
    ] = """# Plot layout is a resizable 2x2 grid, not a square-canvas constraint.
for index in range(self.views.count()):
    layout = getattr(self, "views_grid_layout_"+str(index))
    if layout is not None:
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(1, 1)
        layout.setRowStretch(2, 1)
        # Native sinks otherwise request a large minimum and force scrolling.
        for row in (1, 2):
            for column in (0, 1):
                panel = layout.itemAtPosition(row, column).widget()
                panel.setMinimumSize(0, 0)
                panel.setSizePolicy(Qt.QSizePolicy.Ignored, Qt.QSizePolicy.Ignored)
self.views.setMinimumSize(0, 0)
self.views.setSizePolicy(Qt.QSizePolicy.Ignored, Qt.QSizePolicy.Ignored)
self.resize(1180, 900)
"""
    by["square_plot_panels"]["parameters"][
        "comment"
    ] = "UI layout only: resizable 2x2 dashboards."
    by["constellation"]["parameters"][
        "name"
    ] = "After adaptive LMS equalization | symbols and guides"
    for name, row, col in [
        ("tx_power_display", 3, 0),
        ("rx_power_display", 3, 1),
        ("peak_display", 4, 0),
        ("snr_display", 4, 1),
        ("ebno_display", 5, 0),
    ]:
        by[name]["parameters"]["gui_hint"] = f"views@3:{row},{col},1,1"
    for index, title in enumerate(
        [
            "Constellations",
            "Waveforms",
            "I eyes",
            "Link budget",
            "Q eyes",
            "BER / EVM / taps",
        ]
    ):
        by["views"]["parameters"][f"label{index}"] = title
    for name in ("evm_history", "eq_evm_history", "eq_error_trace"):
        by[name]["parameters"].update(
            ylabel="EVM", yunit="%", label1="Decision-directed EVM"
        )
    by["ber_history"]["parameters"].update(
        ylabel="Bit error ratio", yunit="", label1="BER", ymin="0", ymax="1"
    )
    if "eq_delay_symbols" not in by:
        # A centred identity tap adds five symbols at the default 11 taps.
        current = by["reference_delay"]["parameters"]["value"]
        k = {
            "single_carrier_bpsk": 1,
            "single_carrier_qpsk": 2,
            "single_carrier_8psk": 3,
            "single_carrier_4ask": 2,
            "single_carrier_8ask": 3,
            "single_carrier_16qam": 4,
        }[graph["options"]["parameters"]["id"]]
        by["reference_delay"]["parameters"]["value"] = str(int(float(current)) + 5 * k)
        add("eq_delay_symbols", "variable", 600, 100, value="(eq_taps-1)//2")
    by["eq_algorithm"]["parameters"].update(
        type="lms", step_size="eq_step/(eq_taps*symbol_rms**2)"
    )
    # Stock LMS starts with all-zero taps; initialize an identity path at the
    # centre tap through the block's public API, rather than a custom DSP block.
    add(
        "equalizer_initial_taps",
        "snippet",
        1200,
        2920,
        section="main_after_init",
        priority=0,
        code="self.equalizer.set_taps([0j]*((self.eq_taps-1)//2)+[1+0j]+[0j]*(self.eq_taps//2))",
    )
    return graph
