"""Build BER-versus-Eb/N0 flowcharts: grc/ber_curve_<modulation>.grc.

Each flowchart is flat and uses only stock GNU Radio blocks:

    one transmitter (same modulator, pulse shaping and power as the
    single-carrier simulation)
      -> one channel + receiver row per Eb/N0 point (AWGN Channel Model with
         its own noise seed, then the same timing recovery, LMS equalizer,
         decisions and differential decoding as the simulation)
      -> QT GUI Bercurve Sink, which compares each row's received bits with
         the delayed transmitted bits and plots BER against Eb/N0 live.

The modem settings (constellation, RRC, timing loop, equalizer, reference
delay) are copied from grc/single_carrier_<modulation>.grc, which is never
modified, so the curve describes the same receiver. Change the Eb/N0 values
in the ebno_db variable (the number of points is fixed per flowchart).

Eb/N0 convention matches the simulations: noise is integrated over
Fs = 4 Msamples/s and Eb/N0 = SNR(Fs) + 10*log10(Fs / bit rate), per uncoded
bit. Each point keeps counting until it has min_errors bit errors (then it
holds) or its BER falls below 10^ber_floor_log10.

The sink's x-axis is labelled "ESNO" by GNU Radio; here it carries Eb/N0.
Its built-in red "BPSK AWGN" curve is then the textbook coherent BPSK/QPSK
BER versus Eb/N0, a common reference for every format.

Run: python scripts/build_ber_curves.py
"""

from pathlib import Path
import copy
import yaml

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"bpsk": "BPSK", "qpsk": "QPSK", "8psk": "8-PSK", "4ask": "4-ASK",
          "8ask": "8-ASK", "16qam": "16-QAM"}
# Eb/N0 points (dB) per format: 8 points, 2 dB apart, spanning the waterfall.
EBNO_START_DB = {"bpsk": 0, "qpsk": 0, "8psk": 2, "4ask": 2, "8ask": 6, "16qam": 2}
POINTS = 8
COPIED = ["const", "k", "sps", "alpha", "nfilts", "rrc_taps", "samp_rate", "symbol_rate",
          "bit_rate", "symbol_rms", "timing_bw", "eq_algorithm", "eq_taps", "eq_step",
          "eq_delay_symbols", "reference_delay", "warmup_bits", "tx_power_dbm",
          "tx_amplitude", "path_loss_db", "path_gain", "chart_math"]
TX_CHAIN = ["random_bytes", "modulator", "tx_power", "throttle"]
REFERENCE_CHAIN = ["unpack_tx", "delay", "skip_tx"]
RX_CHAIN = ["rx_level", "clock_sync", "rx_scale", "equalizer", "decoder", "diff_decoder",
            "unpack_rx", "skip_rx"]
ROW_HEIGHT = 150


def build(profile):
    source = yaml.safe_load((ROOT / f"grc/single_carrier_{profile}.grc").read_text())
    original = {b["name"]: b for b in source["blocks"]}
    label = LABELS[profile]
    blocks, edges = [], []

    def add(name, kind, x, y, **parameters):
        blocks.append(dict(name=name, id=kind,
                           parameters={k: str(v) for k, v in parameters.items()},
                           states=dict(coordinate=[x, y], rotation=0, state="enabled")))

    def copy_block(name, new_name, x, y, **overrides):
        block = copy.deepcopy(original[name])
        block["name"] = new_name
        block["parameters"].update({k: str(v) for k, v in overrides.items()})
        block["states"] = dict(coordinate=[x, y], rotation=0, state="enabled")
        blocks.append(block)

    def wire(src, dst, dst_port=0):
        edges.append([src, "0", dst, str(dst_port)])

    # --- Controls -------------------------------------------------------------
    for index, name in enumerate(COPIED):
        copy_block(name, name, 16 + 190 * (index % 8), 60 + 90 * (index // 8))
    for block in blocks:
        if block["name"] == "path_loss_db":
            block["parameters"]["value"] = "0"
        # Low-Eb/N0 points finish within a few thousand bits, so skip the
        # timing-loop and equalizer acquisition before counting errors.
        if block["name"] == "warmup_bits":
            block["parameters"]["value"] = "50000"
    start = EBNO_START_DB[profile]
    ebno_values = [start + 2 * i for i in range(POINTS)]
    controls = [
        ("ebno_db", "variable", dict(value=str(ebno_values))),
        ("noise_volts", "variable", dict(value=(
            "list(tx_amplitude*path_gain*10**(-(numpy.array(ebno_db)"
            " - 10*math.log10(samp_rate/bit_rate))/20))"))),
        ("min_errors", "parameter", dict(value="100", type="intx",
         label="Bit errors to collect per point", short_id="", hide="none")),
        ("ber_floor_log10", "parameter", dict(value="-7", type="eng_float",
         label="Stop a point below BER 10^x", short_id="", hide="none")),
        ("sim_speed", "parameter", dict(value="100", type="eng_float",
         label="Simulation speed limit (x real time)", short_id="", hide="none")),
    ]
    for index, (name, kind, parameters) in enumerate(controls):
        add(name, kind, 16 + 190 * index, 340, **parameters)
    add("section_controls", "note", 16, 8, note="CONTROLS: EB/N0 POINTS AND MODEM")

    # --- Transmitter and shared bit reference ----------------------------------
    y_tx = 470
    add("section_transmitter", "note", 16, y_tx - 50, note="TRANSMITTER")
    for index, name in enumerate(TX_CHAIN):
        copy_block(name, name, 16 + 230 * index, y_tx)
    for block in blocks:
        if block["name"] == "throttle":
            block["parameters"]["samples_per_second"] = "samp_rate*sim_speed"
    wire("random_bytes", "modulator")
    wire("modulator", "tx_power")
    wire("tx_power", "throttle")
    add("tx_link", "virtual_sink", 16 + 230 * 4, y_tx, stream_id="tx_waveform")
    wire("throttle", "tx_link")
    add("reference_link", "virtual_sink", 230, y_tx + 90, stream_id="tx_bytes")
    wire("random_bytes", "reference_link")
    add("reference_source", "virtual_source", 16, y_tx + 180, stream_id="tx_bytes")
    for index, name in enumerate(REFERENCE_CHAIN):
        copy_block(name, name, 200 + 200 * index, y_tx + 180)
    add("pack_tx", "blocks_pack_k_bits_bb", 800, y_tx + 180, k="8")
    add("tx_bits_link", "virtual_sink", 980, y_tx + 180, stream_id="tx_reference_bytes")
    wire("reference_source", "unpack_tx")
    wire("unpack_tx", "delay")
    wire("delay", "skip_tx")
    wire("skip_tx", "pack_tx")
    wire("pack_tx", "tx_bits_link")

    # --- One channel + receiver row per Eb/N0 point ----------------------------
    y0 = y_tx + 320
    add("section_receivers", "note", 16, y0 - 50,
        note="CHANNEL AND RECEIVER, ONE ROW PER EB/N0 POINT")
    for i in range(POINTS):
        y = y0 + ROW_HEIGHT * i
        add(f"tx_in_{i}", "virtual_source", 16, y, stream_id="tx_waveform")
        copy_block("channel", f"channel_{i}", 170, y, noise_voltage=f"noise_volts[{i}]",
                   taps="[path_gain]", seed=str(100 + i))
        names = [f"channel_{i}"]
        for index, name in enumerate(RX_CHAIN):
            copy_block(name, f"{name}_{i}", 400 + 200 * index, y)
            names.append(f"{name}_{i}")
        add(f"pack_rx_{i}", "blocks_pack_k_bits_bb", 400 + 200 * len(RX_CHAIN), y, k="8")
        names.append(f"pack_rx_{i}")
        wire(f"tx_in_{i}", f"channel_{i}")
        for a, b in zip(names, names[1:]):
            wire(a, b)
        add(f"rx_bits_{i}", "virtual_sink", 600 + 200 * len(RX_CHAIN), y,
            stream_id=f"rx_bytes_{i}")
        wire(f"pack_rx_{i}", f"rx_bits_{i}")

    # --- BER curve sink -----------------------------------------------------------
    y_sink = y0 + ROW_HEIGHT * POINTS + 100
    add("section_ber_curve", "note", 16, y_sink - 50, note="BER CURVE")
    add("ber_curve", "qtgui_bercurve_sink", 600, y_sink,
        esno="ebno_db", berminerrors="min_errors", berlimit="ber_floor_log10",
        num_curves="1", curvenames="[]", ymin="-7", ymax="0", update_time="0.25",
        gui_hint="", label1=f'"{label} measured"', width1="2", color1='"blue"',
        style1="1", marker1="0", alpha1="1.0",
        bus_structure_sink=str([list(range(2 * POINTS))]))
    for i in range(POINTS):
        add(f"tx_ref_{i}", "virtual_source", 16, y_sink + 60 * i,
            stream_id="tx_reference_bytes")
        add(f"rx_out_{i}", "virtual_source", 300, y_sink + 60 * i, stream_id=f"rx_bytes_{i}")
        wire(f"tx_ref_{i}", "ber_curve", 2 * i)
        wire(f"rx_out_{i}", "ber_curve", 2 * i + 1)
    taps = "[0j]*((self.eq_taps-1)//2)+[1+0j]+[0j]*(self.eq_taps//2)"
    add("equalizer_initial_taps", "snippet", 16, y_sink - 140, section="main_after_init",
        priority="0", code=(
            "# Start every row's adaptive equalizer at a centered identity filter.\n"
            f"for i in range({POINTS}):\n"
            f"    getattr(self, 'equalizer_%d' % i).set_taps({taps})"))
    add("curve_title", "snippet", 300, y_sink - 140, section="main_after_init",
        priority="0", code=(
            f"self.ber_curve.set_title('{label} BER vs Eb/N0 (x axis: Eb/N0 in dB per bit). "
            "Red: BPSK/QPSK theory')\n"
            "self.resize(1000, 700)"))

    options = copy.deepcopy(source["options"])
    options["parameters"].update(id=f"ber_curve_{profile}",
                                 title=f"{label} BER vs Eb/N0 | stock blocks")
    options["states"]["coordinate"] = [1600, 8]  # clear of the CONTROLS heading
    graph = dict(options=options, blocks=blocks, connections=edges,
                 metadata=copy.deepcopy(source["metadata"]))
    target = ROOT / f"grc/ber_curve_{profile}.grc"
    target.write_text(yaml.safe_dump(graph, sort_keys=False, width=110))
    return target


if __name__ == "__main__":
    for profile in LABELS:
        print("wrote", build(profile).relative_to(ROOT))
