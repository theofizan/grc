"""Build complete SISO modem and Wi-Fi PHY labs with native Qt GUI displays."""

from build_flowgraphs import block, parameter, variable, note, write_graph


def import_block():
    return block(
        "project_imports",
        "import",
        dict(
            imports="import math\nimport numpy as np\nfrom antenna_bench.paths import ROOT\n"
            "from antenna_bench.live import test_bits, wlan_reference, burst_waveform, reference_symbols, parse_taps\n"
            "from antenna_bench.wlan import wlan_constellation\nfrom gnuradio import digital"
        ),
        230,
        10,
    )


def embedded(name, cls, args, x, y):
    defaults = {
        "BitErrorMeter": 'report_path="", run_config=None',
        "EvmMeter": 'report_path="", run_config=None',
        "BurstReceiver": 'rate_index=2, correct_cfo=True, pilot_tracking=True, report_path=""',
    }[cls]
    keys = [part.split("=")[0].strip() for part in defaults.split(",")]
    source = (
        f"import antenna_bench.gr_metrics as metrics\n\nclass blk(metrics.{cls}):\n"
        f"    def __init__(self, {defaults}):\n"
        f'        super().__init__({", ".join(keys)})\n'
    )
    return block(name, "epy_block", dict(_source_code=source, **args), x, y)


def gui(items, edges, tx, rx, equalized, reference, fs, base_y):
    items.append(
        block(
            "views",
            "qtgui_tab_widget",
            dict(
                num_tabs="3",
                label0="Metrics and constellation",
                label1="TX waveform: spectrum / waterfall / time",
                label2="RX waveform: spectrum / waterfall / time",
                label3="Equalized DATA symbols",
                label4="TX reference symbols",
                gui_hint="",
            ),
            230,
            base_y,
        )
    )
    for name, source, label, tab in [
        ("tx_scope", tx, "TX waveform | complex baseband; relative FFT level", 1),
        ("rx_scope", rx, "RX waveform | before equalization; relative FFT level", 2),
    ]:
        items.append(
            block(
                name,
                "qtgui_sink_x",
                dict(
                    type="complex",
                    name=label,
                    fftsize="1024",
                    wintype="window.WIN_HANN",
                    fc="0",
                    bw=fs,
                    rate="5",
                    plotfreq="True",
                    plotwaterfall="True",
                    plottime="True",
                    plotconst="False",
                    showrf="False",
                    gui_hint=f"views@{tab}:0,0,1,2",
                ),
                500,
                base_y + 110 * tab,
            )
        )
        edges.append([source, "0", name, "0"])
    items.append(
        block(
            "constellation",
            "qtgui_const_sink_x",
            dict(
                type="complex",
                name="SISO equalized symbols and known reference",
                size="1024",
                grid="True",
                autoscale="False",
                xmin="-2.0",
                xmax="2.0",
                ymin="-2.0",
                ymax="2.0",
                nconnections="2",
                label1="RX equalized DATA",
                label2="TX reference DATA",
                color1='"blue"',
                color2='"red"',
                style1="0",
                style2="0",
                marker1="0",
                marker2="8",
                alpha1="0.5",
                alpha2="1.0",
                gui_hint="views@0:1,0,1,2",
            ),
            850,
            base_y + 100,
        )
    )
    edges.extend(
        [[equalized, "0", "constellation", "0"], [reference, "0", "constellation", "1"]]
    )
    for name, source, title, unit, column, maximum in [
        ("ber_display", "ber_meter", "Cumulative pre-FEC BER", "errors/bit", 0, "1"),
        ("evm_display", "evm_meter", "Pooled RMS EVM", "%", 1, "100"),
    ]:
        items.append(
            block(
                name,
                "qtgui_number_sink",
                dict(
                    type="float",
                    name=title,
                    autoscale="False",
                    avg="0",
                    graph_type="qtgui.NUM_GRAPH_NONE",
                    nconnections="1",
                    min="0",
                    max=maximum,
                    label1=title,
                    unit1=unit,
                    gui_hint=f"views@0:0,{column},1,1",
                ),
                500 + column * 400,
                base_y + 550,
            )
        )
        edges.append([source, "0", name, "0"])


def meters(items, edges, tx_bits, rx_bits, reference, equalized, stem, y):
    context = (
        "dict(model='SISO symbol-rate',order=order,ebno_db=ebno_db,path_loss_db=path_loss_db,noise_seed=noise_seed)"
        if stem == "siso_modem"
        else "dict(model='SISO known-burst Wi-Fi',rate_index=rate_index,tx_reference_snr_db=snr_db,path_loss_db=path_loss_db,cfo_hz=cfo_hz,channel_taps=channel_taps,correct_cfo=correct_cfo,pilot_tracking=pilot_tracking,noise_seed=noise_seed)"
    )
    items.extend(
        [
            embedded(
                "ber_meter",
                "BitErrorMeter",
                dict(
                    report_path=f"str(ROOT / 'results/live/{stem}_ber.json')",
                    run_config=context,
                ),
                1100,
                y,
            ),
            embedded(
                "evm_meter",
                "EvmMeter",
                dict(
                    report_path=f"str(ROOT / 'results/live/{stem}_evm.json')",
                    run_config=context,
                ),
                1100,
                y + 140,
            ),
        ]
    )
    edges.extend(
        [
            [tx_bits, "0", "ber_meter", "0"],
            [rx_bits, "0", "ber_meter", "1"],
            [reference, "0", "evm_meter", "0"],
            [equalized, "0", "evm_meter", "1"],
        ]
    )


def modem():
    items = [
        import_block(),
        parameter("order", 16, "intx", 230, 100),
        parameter("ebno_db", 20, "eng_float", 440, 100),
        parameter("path_loss_db", 0, "eng_float", 650, 100),
        parameter("symbol_count", 0, "intx", 860, 100),
        parameter("pace", 200000, "eng_float", 1070, 100),
        variable("k", "int(math.log2(order))", 230, 200),
        variable("channel_gain", "10**(-path_loss_db/20)", 440, 200),
        variable("noise_voltage", "math.sqrt(1/(k*10**(ebno_db/10)))", 650, 200),
        variable(
            "constellation_object",
            "digital.constellation_calcdist(wlan_constellation(order).tolist(),list(range(order)),1,1,digital.constellation.NO_NORMALIZATION).base()",
            860,
            200,
        ),
        block(
            "known_bits",
            "blocks_vector_source_x",
            dict(
                type="byte",
                vector="test_bits(order).tolist()",
                repeat="True",
                vlen="1",
                tags="[]",
            ),
            230,
            330,
        ),
        block(
            "finite_bits",
            "blocks_head",
            dict(
                type="byte",
                num_items="symbol_count*k if symbol_count>0 else 2**60",
                vlen="1",
            ),
            500,
            330,
        ),
        block("pack_bits", "blocks_pack_k_bits_bb", dict(k="k"), 770, 330),
        block(
            "mapper",
            "digital_chunks_to_symbols_xx",
            dict(
                in_type="byte",
                out_type="complex",
                symbol_table="wlan_constellation(order).tolist()",
                dimension="1",
            ),
            1040,
            330,
        ),
        block(
            "pace_tx",
            "blocks_throttle2",
            dict(
                type="complex",
                samples_per_second="pace",
                vlen="1",
                ignoretag="True",
                limit="auto",
            ),
            230,
            490,
        ),
        block(
            "siso_path",
            "blocks_multiply_const_vxx",
            dict(type="complex", const="channel_gain", vlen="1"),
            510,
            490,
        ),
        block(
            "awgn",
            "analog_noise_source_x",
            dict(
                type="complex",
                noise_type="analog.GR_GAUSSIAN",
                amp="noise_voltage",
                seed="20261017",
            ),
            510,
            630,
        ),
        block(
            "channel_output",
            "blocks_add_xx",
            dict(type="complex", num_inputs="2", vlen="1"),
            790,
            490,
        ),
        block(
            "equalize",
            "blocks_multiply_const_vxx",
            dict(type="complex", const="1/channel_gain", vlen="1"),
            1060,
            490,
        ),
        block(
            "demap",
            "digital_constellation_decoder_cb",
            dict(constellation="constellation_object"),
            230,
            780,
        ),
        block("rx_bits", "blocks_unpack_k_bits_bb", dict(k="k"), 520, 780),
    ]
    edges = [
        ["known_bits", "0", "finite_bits", "0"],
        ["finite_bits", "0", "pack_bits", "0"],
        ["pack_bits", "0", "mapper", "0"],
        ["mapper", "0", "pace_tx", "0"],
        ["pace_tx", "0", "siso_path", "0"],
        ["siso_path", "0", "channel_output", "0"],
        ["awgn", "0", "channel_output", "1"],
        ["channel_output", "0", "equalize", "0"],
        ["equalize", "0", "demap", "0"],
        ["demap", "0", "rx_bits", "0"],
    ]
    meters(
        items, edges, "finite_bits", "rx_bits", "mapper", "equalize", "siso_modem", 780
    )
    gui(items, edges, "pace_tx", "channel_output", "equalize", "mapper", "pace", 1050)
    items.extend(
        [
            note(
                "scope",
                "SISO UNCODED SYMBOL LAB: 1 TX / 1 RX. Perfect timing, known scalar channel. Symbol-rate diagnostic, no RF pulse shaping.",
                230,
                1760,
            ),
            note(
                "power",
                "Fixed TX Es=1; path loss reduces received SNR. AWGN is fixed relative to TX Eb/N0; it does NOT follow path loss.",
                230,
                1800,
            ),
            note(
                "use",
                "symbol_count=0 runs until Stop (F7). Set >0 for finite checks. Stop writes exact BER counts / EVM JSON under results/live/.",
                230,
                1840,
            ),
        ]
    )
    next(b for b in items if b["name"] == "ebno_db")["parameters"][
        "label"
    ] = "TX-reference uncoded Eb/N0 (dB)"
    write_graph(
        "siso_modem_lab",
        "SISO modem: bits -> modulation -> channel -> decisions -> BER/EVM",
        items,
        edges,
        "Complete uncoded symbol-rate SISO chain, ideal scalar receiver, live BER/EVM and Qt plots.",
        generate_options="qt_gui",
    )


def wlan():
    items = [
        import_block(),
        parameter("rate_index", 2, "intx", 230, 100),
        parameter("snr_db", 25, "eng_float", 440, 100),
        parameter("path_loss_db", 0, "eng_float", 650, 100),
        parameter("packet_count", 0, "intx", 860, 100),
        parameter("pace", 1000000, "eng_float", 1070, 100),
        parameter("cfo_hz", 0, "eng_float", 230, 200),
        parameter("channel_taps", "1+0j", "str", 440, 200),
        parameter("correct_cfo", 1, "intx", 1400, 100),
        parameter("pilot_tracking", 1, "intx", 1400, 200),
        variable("reference", "wlan_reference(rate_index)", 650, 200),
        variable("sample_rate", "20e6", 860, 200),
        variable("order", "int(reference['order'])", 1070, 200),
        variable("k", "int(math.log2(order))", 230, 290),
        variable("channel_gain", "10**(-path_loss_db/20)", 440, 290),
        variable("noise_voltage", "10**(-snr_db/20)", 650, 290),
        variable(
            "constellation_object",
            "digital.constellation_calcdist(wlan_constellation(order).tolist(),list(range(order)),1,1,digital.constellation.NO_NORMALIZATION).base()",
            860,
            290,
        ),
        block(
            "tx_waveform",
            "blocks_vector_source_x",
            dict(
                type="complex",
                vector="burst_waveform(rate_index).tolist()",
                repeat="True",
                vlen="1",
                tags="[]",
            ),
            230,
            410,
        ),
        block(
            "finite_tx",
            "blocks_head",
            dict(
                type="complex",
                num_items="packet_count*len(burst_waveform(rate_index)) if packet_count>0 else 2**60",
                vlen="1",
            ),
            520,
            410,
        ),
        block(
            "pace_tx",
            "blocks_throttle2",
            dict(
                type="complex",
                samples_per_second="pace",
                vlen="1",
                ignoretag="True",
                limit="auto",
            ),
            820,
            410,
        ),
        block(
            "siso_fir",
            "fir_filter_xxx",
            dict(
                type="ccc",
                decim="1",
                taps="[channel_gain*t for t in parse_taps(channel_taps)]",
                samp_delay="0",
            ),
            230,
            570,
        ),
        block(
            "carrier_offset",
            "blocks_rotator_cc",
            dict(phase_inc="2*math.pi*cfo_hz/sample_rate"),
            520,
            570,
        ),
        block(
            "awgn",
            "analog_noise_source_x",
            dict(
                type="complex",
                noise_type="analog.GR_GAUSSIAN",
                amp="noise_voltage",
                seed="20261017",
            ),
            520,
            710,
        ),
        block(
            "channel_output",
            "blocks_add_xx",
            dict(type="complex", num_inputs="2", vlen="1"),
            820,
            570,
        ),
        block(
            "extract_bursts",
            "blocks_keep_m_in_n",
            dict(
                type="complex",
                m="reference['tx_packet'].size",
                n="len(burst_waveform(rate_index))",
                offset="0",
            ),
            230,
            850,
        ),
        embedded(
            "burst_receiver",
            "BurstReceiver",
            dict(
                rate_index="rate_index",
                correct_cfo="bool(correct_cfo)",
                pilot_tracking="bool(pilot_tracking)",
                report_path="str(ROOT / 'results/live/siso_wlan_receiver.json')",
            ),
            550,
            850,
        ),
        block(
            "demap",
            "digital_constellation_decoder_cb",
            dict(constellation="constellation_object"),
            230,
            1040,
        ),
        block("rx_bits", "blocks_unpack_k_bits_bb", dict(k="k"), 520, 1040),
        block(
            "tx_reference",
            "blocks_vector_source_x",
            dict(
                type="complex",
                vector="reference_symbols(rate_index).tolist()",
                repeat="True",
                vlen="1",
                tags="[]",
            ),
            230,
            1210,
        ),
        block(
            "finite_reference",
            "blocks_head",
            dict(
                type="complex",
                num_items="packet_count*reference_symbols(rate_index).size if packet_count>0 else 2**60",
                vlen="1",
            ),
            520,
            1210,
        ),
        block(
            "tx_decisions",
            "digital_constellation_decoder_cb",
            dict(constellation="constellation_object"),
            800,
            1210,
        ),
        block("tx_bits", "blocks_unpack_k_bits_bb", dict(k="k"), 1100, 1210),
    ]
    edges = [
        ["tx_waveform", "0", "finite_tx", "0"],
        ["finite_tx", "0", "pace_tx", "0"],
        ["pace_tx", "0", "siso_fir", "0"],
        ["siso_fir", "0", "carrier_offset", "0"],
        ["carrier_offset", "0", "channel_output", "0"],
        ["awgn", "0", "channel_output", "1"],
        ["channel_output", "0", "extract_bursts", "0"],
        ["extract_bursts", "0", "burst_receiver", "0"],
        ["burst_receiver", "0", "demap", "0"],
        ["demap", "0", "rx_bits", "0"],
        ["tx_reference", "0", "finite_reference", "0"],
        ["finite_reference", "0", "tx_decisions", "0"],
        ["tx_decisions", "0", "tx_bits", "0"],
    ]
    meters(
        items,
        edges,
        "tx_bits",
        "rx_bits",
        "finite_reference",
        "burst_receiver",
        "siso_wlan",
        1040,
    )
    gui(
        items,
        edges,
        "pace_tx",
        "channel_output",
        "burst_receiver",
        "finite_reference",
        "sample_rate",
        1440,
    )
    items.extend(
        [
            note(
                "scope",
                "SISO LEGACY Wi-Fi PHY LAB: 1 TX / 1 RX; fixed rate/length and known burst schedule. No MAC, ACK or retries.",
                230,
                2150,
            ),
            note(
                "power",
                "TX active-PPDU mean |x|^2=1 at every rate; snr_db sets fixed noise power against that TX reference, not measured RX SNR.",
                230,
                2190,
            ),
            note(
                "receiver_note",
                "Receiver contains STF/LTF CFO correction, LTF-only ZF, CP removal/FFT and pilot phase tracking. Double-click Python block; see docs/SISO_LABS.md.",
                230,
                2230,
            ),
            note(
                "pacing",
                "Logical sample rate=20 Msps. pace controls wall-clock playback only. packet_count=0 is continuous. Stop saves BER/EVM and receiver JSON.",
                230,
                2270,
            ),
        ]
    )
    next(b for b in items if b["name"] == "snr_db")["parameters"][
        "label"
    ] = "TX active-PPDU reference SNR (dB)"
    write_graph(
        "siso_wlan_lab",
        "SISO Wi-Fi PHY: waveform -> FIR/CFO/AWGN -> trained RX -> BER/EVM",
        items,
        edges,
        "Complete known-burst SISO PHY with fixed active TX power and live pre-FEC BER/EVM. No autonomous acquisition or MAC.",
        generate_options="qt_gui",
    )


def build():
    modem()
    wlan()


if __name__ == "__main__":
    build()
