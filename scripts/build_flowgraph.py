"""Recreate the tutorial-style single-carrier lab. Overwrites its .grc source."""

from pathlib import Path
import yaml
import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--modulation",
    choices=["bpsk", "qpsk", "8psk", "4ask", "8ask", "16qam"],
    default="16qam",
)
profile = parser.parse_args().modulation
order = {"bpsk": 2, "qpsk": 4, "8psk": 8, "4ask": 4, "8ask": 8, "16qam": 16}[profile]
bits_per_symbol = (order - 1).bit_length()
graph_id = "single_carrier_" + profile

ROOT = Path(__file__).resolve().parents[1]
blocks = []
connections = []


def add(block_id, kind, x, y, **settings):
    blocks.append(
        dict(
            name=block_id,
            id=kind,
            parameters={k: str(v) for k, v in settings.items()},
            states=dict(coordinate=[x, y], rotation=0, state="enabled"),
        )
    )


def wire(source, destination, port=0):
    connections.append([source, "0", destination, str(port)])


# Controls across the top, like the GNU Radio tutorial.
for name, value, x in [
    ("samp_rate", "symbol_rate*sps", 220),
    ("sps", 4, 400),
    ("alpha", 0.35, 540),
    ("nfilts", 32, 680),
    ("timing_bw", 0.0628, 820),
]:
    add(name, "variable", x, 12, value=value)
add(
    "rrc_taps",
    "variable",
    1040,
    12,
    value="firdes.root_raised_cosine(nfilts, nfilts*sps, 1.0, alpha, 11*sps*nfilts)",
)
if profile.endswith("ask"):
    # Use the page's equally spaced ASK levels and sector width of two.
    # GNU Radio internally normalizes both the points and decision sectors.
    levels = list(range(-order + 1, order, 2))
    add(
        "const",
        "variable_constellation_rect",
        1390,
        12,
        sym_map=str(list(range(order))),
        const_points=str(levels),
        rot_sym=1,
        real_sect=order,
        imag_sect=1,
        w_real_sect=2,
        w_imag_sect=1,
    )
else:
    add("const", "variable_constellation", 1390, 12, type=profile)
add(
    "noise_volt",
    "parameter",
    220,
    120,
    value="0.02",
    type="eng_float",
    label="Channel noise RMS voltage",
    short_id="",
    hide="none",
)
add(
    "reference_delay",
    "parameter",
    520,
    120,
    value=str(29 * bits_per_symbol),
    type="intx",
    label="TX reference delay (bits)",
    short_id="",
    hide="none",
)
add("ber_window", "variable", 840, 120, value="10000")
add("warmup_bits", "variable", 1050, 120, value="4096")
add("k", "variable", 1250, 120, value="const.bits_per_symbol()")

# RF rates: one million symbols/s, with four waveform samples per symbol.
add(
    "symbol_rate",
    "parameter",
    16,
    170,
    value="1e6",
    type="eng_float",
    label="Symbol rate (symbols/s)",
    short_id="",
    hide="none",
)
add("bit_rate", "variable", 300, 170, value="symbol_rate*k")
add("rrc_bandwidth", "variable", 540, 170, value="symbol_rate*(1+alpha)")

# Main signal path: all blocks come with GNU Radio.
add(
    "random_bytes",
    "analog_random_source_x",
    16,
    300,
    type="byte",
    min=0,
    max=256,
    num_samps=32768,
    repeat="True",
)
add(
    "modulator",
    "digital_constellation_modulator",
    240,
    300,
    constellation="const",
    differential="True",
    samples_per_symbol="sps",
    excess_bw="alpha",
    truncate="False",
)
add(
    "throttle",
    "blocks_throttle2",
    520,
    300,
    type="complex",
    samples_per_second="samp_rate",
    vlen=1,
    ignoretag="True",
    limit="auto",
)
add(
    "channel",
    "channels_channel_model",
    740,
    300,
    noise_voltage="noise_volt",
    freq_offset=0,
    epsilon=1,
    taps="[1.0]",
    seed=42,
    block_tags="False",
)
add(
    "clock_sync",
    "digital_pfb_clock_sync_xxx",
    1000,
    300,
    type="ccf",
    sps="sps",
    loop_bw="timing_bw",
    taps="rrc_taps",
    filter_size="nfilts",
    init_phase=16,
    max_dev=1.5,
    osps=1,
)
add("decoder", "digital_constellation_decoder_cb", 1330, 300, constellation="const")
add("decoded_link", "virtual_sink", 1580, 300, stream_id="decoded")
for a, b in zip(
    ["random_bytes", "modulator", "throttle", "channel", "clock_sync", "decoder"],
    ["modulator", "throttle", "channel", "clock_sync", "decoder", "decoded_link"],
):
    wire(a, b)
add("reference_link", "virtual_sink", 240, 470, stream_id="reference")
wire("random_bytes", "reference_link")

# Bit alignment and BER. The denominator is the number of compared bits.
add("decoded_source", "virtual_source", 16, 650, stream_id="decoded")
add(
    "diff_decoder",
    "digital_diff_decoder_bb",
    210,
    650,
    modulus=str(order),
    coding="digital.DIFF_DIFFERENTIAL",
)
add("unpack_rx", "blocks_unpack_k_bits_bb", 420, 650, k="k")
add(
    "skip_rx", "blocks_skiphead", 650, 650, type="byte", vlen=1, num_items="warmup_bits"
)
add("reference_source", "virtual_source", 16, 800, stream_id="reference")
add("unpack_tx", "blocks_unpack_k_bits_bb", 240, 800, k=8)
add("delay", "blocks_delay", 480, 800, type="byte", vlen=1, delay="reference_delay")
add(
    "skip_tx", "blocks_skiphead", 700, 800, type="byte", vlen=1, num_items="warmup_bits"
)
add("xor", "blocks_xor_xx", 940, 700, type="byte", num_inputs=2)
add("errors_float", "blocks_uchar_to_float", 1130, 700)
add(
    "integrate",
    "blocks_integrate_xx",
    1330,
    700,
    type="float",
    decim="ber_window",
    vlen=1,
)
add(
    "ber_scale",
    "blocks_multiply_const_vxx",
    1550,
    700,
    type="float",
    const="1.0/ber_window",
    vlen=1,
)
add(
    "ber_display",
    "qtgui_number_sink",
    1750,
    700,
    type="float",
    name="BER | latest 10000 compared bits",
    nconnections=1,
    autoscale="False",
    avg=0,
    graph_type="qtgui.NUM_GRAPH_NONE",
    min=0,
    max=1,
    label1="Bit error ratio",
    unit1="errors/bit",
    gui_hint="0,0,1,2",
)
for a, b in [
    ("decoded_source", "diff_decoder"),
    ("diff_decoder", "unpack_rx"),
    ("unpack_rx", "skip_rx"),
    ("reference_source", "unpack_tx"),
    ("unpack_tx", "delay"),
    ("delay", "skip_tx"),
    ("skip_rx", "xor"),
    ("xor", "errors_float"),
    ("errors_float", "integrate"),
    ("integrate", "ber_scale"),
    ("ber_scale", "ber_display"),
]:
    wire(a, b)
wire("skip_tx", "xor", 1)

# Plot blocks are grouped below the processing rows.
add(
    "constellation",
    "qtgui_const_sink_x",
    16,
    1080,
    type="complex",
    name="Received symbols after clock sync",
    size=1024,
    nconnections=1,
    grid="True",
    autoscale="False",
    xmin=-2,
    xmax=2,
    ymin=-2,
    ymax=2,
    gui_hint="1,0,1,1",
)
wire("clock_sync", "constellation")
add(
    "spectrum",
    "qtgui_freq_sink_x",
    420,
    1080,
    type="complex",
    name="RX baseband spectrum (relative dB)",
    fftsize=1024,
    wintype="window.WIN_HANN",
    fc=0,
    bw="samp_rate",
    nconnections=1,
    gui_hint="1,1,1,1",
)
wire("channel", "spectrum")
add(
    "waveform",
    "qtgui_time_sink_x",
    820,
    1080,
    type="complex",
    name="RX waveform: I and Q",
    size=512,
    srate="samp_rate",
    nconnections=1,
    gui_hint="2,0,1,2",
)
wire("channel", "waveform")
# Stock EVM estimator uses nearest constellation decisions, not known TX symbols.
add(
    "evm",
    "digital_meas_evm_cc",
    16,
    1260,
    cons="const",
    meas_type="digital.evm_measurement_t.EVM_PERCENT",
)
add("evm_rms", "blocks_rms_xx", 400, 1260, type="float", alpha="0.001")
add(
    "evm_display",
    "qtgui_number_sink",
    700,
    1260,
    type="float",
    name="Decision-directed RMS EVM",
    nconnections=1,
    autoscale="False",
    avg=0,
    graph_type="qtgui.NUM_GRAPH_NONE",
    min=0,
    max=100,
    label1="Decision-directed EVM",
    unit1="%",
    gui_hint="0,2,1,1",
)
wire("clock_sync", "evm")
wire("evm", "evm_rms")
wire("evm_rms", "evm_display")
add(
    "scope",
    "note",
    16,
    1480,
    note=f"SISO single carrier, RRC pulse shaping. {profile.upper()}, 4 samples/symbol. No carrier recovery: leave frequency offset=0 and epsilon=1 for scored BER. Delay calibrated for this filter/clock configuration. See README.md.",
)

# Virtual links keep display wires from crossing the BER branch.
connections[:] = [
    edge
    for edge in connections
    if not (
        edge[0] in ("channel", "clock_sync")
        and edge[2] in ("constellation", "spectrum", "waveform", "evm")
    )
]
add("rx_iq_link", "virtual_sink", 740, 490, stream_id="rx_iq")
add("symbols_link", "virtual_sink", 1100, 490, stream_id="rx_symbols")
wire("channel", "rx_iq_link")
wire("clock_sync", "symbols_link")
for name, stream, target, x, y in [
    ("symbols_plot", "rx_symbols", "constellation", 16, 1030),
    ("spectrum_input", "rx_iq", "spectrum", 650, 1030),
    ("waveform_input", "rx_iq", "waveform", 1250, 1030),
    ("evm_input", "rx_symbols", "evm", 16, 1240),
]:
    add(name, "virtual_source", x, y, stream_id=stream)
    wire(name, target)
positions = {
    "constellation": (240, 1030),
    "spectrum": (870, 1030),
    "waveform": (1470, 1030),
    "evm": (240, 1240),
    "evm_rms": (600, 1240),
    "evm_display": (870, 1240),
    "scope": (16, 1440),
}
for item in blocks:
    if item["name"] in positions:
        item["states"]["coordinate"] = list(positions[item["name"]])

add(
    "symbol_rms",
    "variable",
    1700,
    120,
    value="(sum(abs(p)**2 for p in const.points())/len(const.points()))**0.5",
)
add(
    "tx_power",
    "blocks_multiply_const_vxx",
    500,
    300,
    type="complex",
    const="1.0/symbol_rms",
    vlen=1,
)
add(
    "rx_scale",
    "blocks_multiply_const_vxx",
    1300,
    300,
    type="complex",
    const="symbol_rms",
    vlen=1,
)
connections[:] = [
    [
        ("rx_scale" if source == "clock_sync" else source),
        sp,
        ("tx_power" if target == "throttle" and source == "modulator" else target),
        tp,
    ]
    for source, sp, target, tp in connections
]
wire("tx_power", "throttle")
wire("clock_sync", "rx_scale")
# Processing row remains left-to-right; virtual sinks sit immediately below taps.
positions = {
    "random_bytes": (16, 300),
    "modulator": (230, 300),
    "tx_power": (490, 300),
    "throttle": (710, 300),
    "channel": (940, 300),
    "clock_sync": (1210, 300),
    "rx_scale": (1500, 300),
    "decoder": (1740, 300),
    "decoded_link": (1980, 300),
    "rx_iq_link": (940, 500),
    "symbols_link": (1510, 500),
}
for item in blocks:
    if item["name"] in positions:
        item["states"]["coordinate"] = list(positions[item["name"]])

# Extra stock displays. Virtual links keep their cables local to each row.
add(
    "views",
    "qtgui_tab_widget",
    1100,
    170,
    num_tabs=3,
    label0="Metrics and constellation",
    label1="TX / RX waveforms",
    label2="Timing and eye",
    gui_hint="",
)
add("tx_plot_link", "virtual_sink", 500, 430, stream_id="tx_iq")
wire("tx_power", "tx_plot_link")
add("timing_link", "virtual_sink", 800, 430, stream_id="timing_error")
connections.append(["clock_sync", "1", "timing_link", "0"])
add("ber_link", "virtual_sink", 1100, 700, stream_id="ber_history")
wire("ber_scale", "ber_link")
add("evm_link", "virtual_sink", 1100, 1200, stream_id="evm_history")
wire("evm_rms", "evm_link")
for name, stream, target in [
    ("tx_spectrum", "tx_iq", "spectrum"),
    ("tx_time", "tx_iq", "waveform"),
]:
    add(name, "virtual_source", 0, 0, stream_id=stream)
    wire(name, target, 1)
for source, stream, sink, rate, title, tab in [
    (
        "ber_plot_input",
        "ber_history",
        "ber_history",
        "bit_rate/ber_window",
        "BER per compared-bit window",
        0,
    ),
    (
        "evm_plot_input",
        "evm_history",
        "evm_history",
        "symbol_rate",
        "Smoothed decision-directed RMS EVM (%)",
        0,
    ),
    (
        "timing_input",
        "timing_error",
        "timing_error",
        "symbol_rate",
        "Clock sync timing error",
        2,
    ),
]:
    add(source, "virtual_source", 0, 0, stream_id=stream)
    add(
        sink,
        "qtgui_time_sink_x",
        0,
        0,
        type="float",
        name=title,
        size=128 if tab == 0 else 512,
        srate=rate,
        nconnections=1,
        autoscale="True",
        gui_hint=(
            f"views@{tab}:1,0,1,1" if sink == "ber_history" else f"views@{tab}:1,1,1,1"
        ),
    )
    wire(source, sink)
add("eye_input", "virtual_source", 0, 0, stream_id="rx_iq")
add(
    "eye",
    "qtgui_eye_sink_x",
    0,
    0,
    type="complex",
    size=1024,
    samp_per_symbol="sps",
    srate="samp_rate",
    nconnections=1,
    grid="True",
    autoscale="True",
    gui_hint="views@2:0,0,1,2",
)
wire("eye_input", "eye")
by_name = {item["name"]: item for item in blocks}
for name, tab, hint in [
    ("ber_display", 0, "0,0,1,1"),
    ("evm_display", 0, "0,1,1,1"),
    ("constellation", 0, "2,0,1,2"),
    ("spectrum", 1, "0,0,1,2"),
    ("waveform", 1, "1,0,1,2"),
]:
    by_name[name]["parameters"]["gui_hint"] = f"views@{tab}:{hint}"
for name, title in [
    ("spectrum", "TX and RX baseband spectrum | relative dB"),
    ("waveform", "TX and RX waveform | I/Q"),
]:
    by_name[name]["parameters"].update(
        nconnections="2", name=title, label1="RX", label2="TX"
    )
# Compact, explicit positions: short gaps between blocks, controls above.
positions = {
    "samp_rate": (210, 12),
    "sps": (360, 12),
    "alpha": (460, 12),
    "nfilts": (570, 12),
    "timing_bw": (690, 12),
    "rrc_taps": (850, 12),
    "const": (1080, 12),
    "noise_volt": (16, 125),
    "reference_delay": (230, 125),
    "ber_window": (440, 125),
    "warmup_bits": (610, 125),
    "k": (790, 125),
    "symbol_rms": (1320, 12),
    "random_bytes": (16, 280),
    "modulator": (150, 280),
    "tx_power": (320, 280),
    "throttle": (490, 280),
    "channel": (630, 280),
    "clock_sync": (790, 280),
    "rx_scale": (980, 280),
    "decoder": (1140, 280),
    "decoded_link": (1330, 280),
    "reference_link": (150, 440),
    "tx_plot_link": (330, 440),
    "rx_iq_link": (630, 440),
    "timing_link": (790, 470),
    "symbols_link": (980, 440),
    "decoded_source": (16, 570),
    "diff_decoder": (150, 570),
    "unpack_rx": (330, 570),
    "skip_rx": (480, 570),
    "reference_source": (16, 710),
    "unpack_tx": (150, 710),
    "delay": (330, 710),
    "skip_tx": (480, 710),
    "xor": (680, 620),
    "errors_float": (760, 620),
    "integrate": (910, 620),
    "ber_scale": (1070, 620),
    "ber_display": (1240, 620),
    "ber_link": (1070, 710),
    "symbols_plot": (16, 860),
    "constellation": (160, 860),
    "spectrum_input": (410, 860),
    "tx_spectrum": (410, 940),
    "spectrum": (560, 860),
    "waveform_input": (850, 860),
    "tx_time": (850, 940),
    "waveform": (1000, 860),
    "evm_input": (16, 1060),
    "evm": (160, 1060),
    "evm_rms": (340, 1060),
    "evm_display": (500, 1060),
    "evm_link": (340, 1150),
    "ber_plot_input": (730, 1060),
    "ber_history": (880, 1060),
    "evm_plot_input": (1090, 1060),
    "evm_history": (1240, 1060),
    "eye_input": (16, 1250),
    "eye": (160, 1250),
    "timing_input": (410, 1250),
    "timing_error": (560, 1250),
    "scope": (850, 1250),
    "views": (1220, 180),
    "symbol_rate": (16, 198),
    "bit_rate": (300, 210),
    "rrc_bandwidth": (540, 210),
}
for name, coordinate in positions.items():
    by_name[name]["states"]["coordinate"] = list(coordinate)

# A complex time input produces separate I and Q traces.
by_name["waveform"]["parameters"].update(
    label1="RX I", label2="RX Q", label3="TX I", label4="TX Q"
)

# This GNU Radio clock-sync implementation requires all four output ports
# when diagnostics are enabled. Drain unused rate/phase states explicitly.
add(
    "unused_timing_states",
    "blocks_null_sink",
    820,
    520,
    type="float",
    vlen=1,
    num_inputs=2,
)
connections.extend(
    [
        ["clock_sync", "2", "unused_timing_states", "0"],
        ["clock_sync", "3", "unused_timing_states", "1"],
    ]
)

# Link-budget convention: |IQ| squared is power in milliwatts.
# A unit-mean-power complex waveform therefore represents 0 dBm.
# Existing normalization becomes an explicit average conducted TX setting.
by_name = {item["name"]: item for item in blocks}
blocks.remove(by_name["noise_volt"])
for name, value, label, x in [
    ("tx_power_dbm", 0, "TX average conducted power (dBm)", 16),
    ("path_loss_db", 80, "Net path loss including gains/losses (dB)", 280),
    ("rx_noise_dbm", -100, "RX noise over sample bandwidth (dBm)", 620),
    ("noise_enabled", 1, "Receiver noise enabled (0/1)", 980),
]:
    add(
        name,
        "parameter",
        x,
        1380,
        value=value,
        type="intx" if name == "noise_enabled" else "eng_float",
        label=label,
        short_id="",
        hide="none",
    )
for name, value, x in [
    ("tx_amplitude", "10**(tx_power_dbm/20.0)", 16),
    ("path_gain", "10**(-path_loss_db/20.0)", 280),
    ("expected_rx_dbm", "tx_power_dbm-path_loss_db", 620),
    ("noise_volt", "10**(rx_noise_dbm/20.0) if noise_enabled else 0.0", 980),
]:
    add(name, "variable", x, 1490, value=value)
by_name["tx_power"]["parameters"]["const"] = "tx_amplitude/symbol_rms"
by_name["channel"]["parameters"]["taps"] = "[path_gain]"
# A known receiver gain restores timing-detector level, while amplifying noise
# equally. It does not improve SNR or model sensitivity, clipping or AGC.
connections[:] = [
    [a, ap, "rx_level" if a == "channel" and b == "clock_sync" else b, bp]
    for a, ap, b, bp in connections
]
add(
    "rx_level",
    "blocks_multiply_const_vxx",
    790,
    280,
    type="complex",
    const="1.0/(tx_amplitude*path_gain)",
    vlen=1,
)
wire("rx_level", "clock_sync")
by_name["clock_sync"]["states"]["coordinate"] = [980, 280]
by_name["rx_scale"]["states"]["coordinate"] = [1170, 280]
by_name["decoder"]["states"]["coordinate"] = [1330, 280]
by_name["decoded_link"]["states"]["coordinate"] = [1520, 280]
by_name["views"]["parameters"].update(num_tabs="4", label3="Link budget: dBm")

# Power meters average LINEAR milliwatts before converting to dBm.
for prefix, stream, column in [("tx", "tx_iq", 0), ("rx", "rx_iq", 1)]:
    x = 16
    y = 1640 + column * 130
    add(prefix + "_meter_input", "virtual_source", x, y, stream_id=stream)
    add(prefix + "_milliwatts", "blocks_complex_to_mag_squared", 160, y, vlen=1)
    add(
        prefix + "_power_sum",
        "blocks_integrate_xx",
        370,
        y,
        type="float",
        decim=4096,
        vlen=1,
    )
    add(
        prefix + "_power_mean",
        "blocks_multiply_const_vxx",
        570,
        y,
        type="float",
        const="1.0/4096",
        vlen=1,
    )
    add(prefix + "_dbm", "blocks_nlog10_ff", 780, y, n=10, k=0, vlen=1)
    add(
        prefix + "_power_display",
        "qtgui_number_sink",
        950,
        y,
        type="float",
        name=(
            "TX average conducted power"
            if prefix == "tx"
            else "RX total power: signal + noise"
        ),
        nconnections=1,
        autoscale="False",
        avg=0,
        graph_type="qtgui.NUM_GRAPH_NONE",
        min=-200,
        max=100,
        label1="TX average" if prefix == "tx" else "RX signal + noise",
        unit1="dBm",
        gui_hint=f"views@3:0,{column},1,1",
    )
    for a, b in zip(
        [
            prefix + "_meter_input",
            prefix + "_milliwatts",
            prefix + "_power_sum",
            prefix + "_power_mean",
            prefix + "_dbm",
        ],
        [
            prefix + "_milliwatts",
            prefix + "_power_sum",
            prefix + "_power_mean",
            prefix + "_dbm",
            prefix + "_power_display",
        ],
    ):
        wire(a, b)
add(
    "power_history",
    "qtgui_time_sink_x",
    1180,
    1700,
    type="float",
    name="Measured power | TX average and RX signal + noise (dBm)",
    size=128,
    srate="samp_rate/4096",
    nconnections=2,
    autoscale="True",
    label1="TX average (dBm)",
    label2="RX total (dBm)",
    gui_hint="views@3:1,0,1,2",
)
wire("tx_dbm", "power_history")
wire("rx_dbm", "power_history", 1)

# Sampled envelope and peak power use the same milliwatt reference.
add(
    "tx_peak_vectors",
    "blocks_stream_to_vector",
    16,
    1910,
    type="float",
    vlen=1,
    num_items=4096,
)
add(
    "tx_peak_mw",
    "blocks_max_xx",
    260,
    1910,
    type="float",
    vlen=4096,
    vlen_out=1,
    num_inputs=1,
)
add("tx_peak_dbm", "blocks_nlog10_ff", 440, 1910, n=10, k=0, vlen=1)
add(
    "peak_display",
    "qtgui_number_sink",
    620,
    1910,
    type="float",
    name="TX sampled peak envelope power",
    nconnections=1,
    autoscale="False",
    avg=0,
    graph_type="qtgui.NUM_GRAPH_NONE",
    min=-200,
    max=100,
    label1="TX peak per 4096 samples",
    unit1="dBm",
    gui_hint="views@3:0,2,1,1",
)
wire("tx_milliwatts", "tx_peak_vectors")
wire("tx_peak_vectors", "tx_peak_mw")
wire("tx_peak_mw", "tx_peak_dbm")
wire("tx_peak_dbm", "peak_display")
# The tiny display-only offset prevents log(0); it is not added to the IQ path.
add(
    "envelope_floor",
    "blocks_add_const_vxx",
    16,
    2050,
    type="float",
    const="1e-30",
    vlen=1,
)
add("envelope_dbm", "blocks_nlog10_ff", 260, 2050, n=10, k=0, vlen=1)
add(
    "envelope_plot",
    "qtgui_time_sink_x",
    440,
    2050,
    type="float",
    name="TX sampled power envelope (dBm)",
    size=512,
    srate="samp_rate",
    nconnections=1,
    autoscale="True",
    gui_hint="views@3:2,0,1,3",
)
wire("tx_milliwatts", "envelope_floor")
wire("envelope_floor", "envelope_dbm")
wire("envelope_dbm", "envelope_plot")
by_name = {item["name"]: item for item in blocks}
by_name["power_history"]["parameters"]["gui_hint"] = "views@3:1,0,1,3"
for name, position in {
    "tx_power_dbm": (16, 125),
    "path_loss_db": (280, 125),
    "rx_noise_dbm": (620, 125),
    "noise_enabled": (980, 125),
    "reference_delay": (16, 1380),
    "ber_window": (280, 1380),
    "warmup_bits": (620, 1380),
}.items():
    by_name[name]["states"]["coordinate"] = list(position)

# Continue the TX power stream through local links rather than crossing rows.
connections[:] = [
    edge
    for edge in connections
    if not (
        edge[0] == "tx_milliwatts" and edge[2] in ("tx_peak_vectors", "envelope_floor")
    )
]
add("tx_mw_link", "virtual_sink", 160, 1710, stream_id="tx_power_mw")
wire("tx_milliwatts", "tx_mw_link")
add("peak_input", "virtual_source", 16, 1910, stream_id="tx_power_mw")
add("envelope_input", "virtual_source", 16, 2050, stream_id="tx_power_mw")
wire("peak_input", "tx_peak_vectors")
wire("envelope_input", "envelope_floor")
by_name = {item["name"]: item for item in blocks}
for name, position in {
    "tx_peak_vectors": (160, 1910),
    "tx_peak_mw": (400, 1910),
    "tx_peak_dbm": (580, 1910),
    "peak_display": (760, 1910),
    "envelope_floor": (160, 2050),
    "envelope_dbm": (400, 2050),
    "envelope_plot": (580, 2050),
}.items():
    by_name[name]["states"]["coordinate"] = list(position)

graph = dict(
    options=dict(
        parameters=dict(
            id=graph_id,
            title=profile.upper() + " single carrier | stock blocks",
            generate_options="qt_gui",
            output_language="python",
            author="Antenna benchmark",
        ),
        states=dict(coordinate=[16, 12], rotation=0, state="enabled"),
    ),
    blocks=blocks,
    connections=connections,
    metadata=dict(file_format=1, grc_version="3.10.12.0"),
)
from improve_charts import improve

graph = improve(graph)
(ROOT / "grc" / f"{graph_id}.grc").write_text(
    yaml.safe_dump(graph, sort_keys=False, width=110)
)
print("Wrote grc/" + graph_id + ".grc")

import subprocess,sys
subprocess.run([sys.executable,str(ROOT/'scripts/pack_controls.py'),'--modulation',profile],check=True)
