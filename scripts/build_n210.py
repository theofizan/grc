"""Derive Ettus USRP N210 over-the-air flowcharts from the saved simulations.

Reads grc/single_carrier_<mod>.grc (never modified) and writes
grc/n210_<mod>.grc. Only stock GNU Radio / gr-uhd blocks are used, and the
flowchart stays flat. Changes relative to the simulation:

* Throttle + Channel Model are replaced by a UHD USRP Sink on the TX N210
  (TX/RX port) and a UHD USRP Source on the RX N210 (RX2 port), both driven
  from this one flowchart. The USRP sample clocks pace it; no Throttle.
* TX level is set in dBFS (0 dBFS = DAC full scale), not dBm. The N210 is
  not power-calibrated; conducted dBm depends on daughterboard and gain.
* RX level meters read the raw N210 samples at fixed RF gain, so they track
  antenna performance. Demodulation then uses: AGC2 -> polyphase timing
  recovery -> Costas loop (pulls in the kHz-level offset between two
  free-running N210 oscillators) -> preamble detector -> trained LMS.
* Known preamble: the TX data is a fixed, repeating 32,766-byte block
  (262,128 bits) with differential coding off. A stock Correlation Estimator
  finds its first 128 symbols once per period, and its corr_est tag starts
  LMS training on the full known symbol sequence. Training rotates the
  equalizer onto the absolute carrier phase, so whichever of its symmetric
  states the Costas loop locks to, decisions and bits come out right.
* BER: RX bits are XORed with the RX bits one data period earlier; each real
  error produces two mismatches, so the count is scaled by 1/2. Because the
  known-sequence training rules out a rotated (wrong-mapping) lock, this
  equals BER against the transmitted data; check_n210_loopback.py verifies
  that against the true TX bits. No TX-to-RX latency needs to be known.
* Known-link-budget SNR readouts become MER (modulation error ratio) from the
  decision-directed EVM, i.e. an Es/N0 estimate that is optimistic at low SNR.

Run explicitly: python scripts/build_n210.py
"""

from pathlib import Path
import copy
import math
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ["bpsk", "qpsk", "8psk", "4ask", "8ask", "16qam"]
# Costas order = number of phase states its detector expects.
COSTAS_ORDER = {"bpsk": 2, "qpsk": 4, "8psk": 8, "4ask": 2, "8ask": 2, "16qam": 4}
# Costas loop bandwidth = 2*pi/N rad/symbol. 16-QAM uses a narrower loop
# because a 4th-order Costas detector adds phase jitter on its inner/outer
# rings; 2*pi/1600 still pulls in a 3 kHz offset at 1 Msymbol/s.
COSTAS_BW_DIVISOR = {"bpsk": 200, "qpsk": 200, "8psk": 200, "4ask": 800, "8ask": 800,
                     "16qam": 1600}
# Known data block length. 32,766 bytes = 262,128 bits is a whole number of
# symbols for 1, 2, 3 and 4 bits/symbol, so the symbol sequence itself repeats
# every block. (With 32,768 bytes, 3-bit formats repeat the bits shifted by one
# bit every third of a block, which falsely matches the preamble.)
DATA_BYTES = 32766
LABELS = {"bpsk": "BPSK", "qpsk": "QPSK", "8psk": "8-PSK", "4ask": "4-ASK",
          "8ask": "8-ASK", "16qam": "16-QAM"}
# Simulation-only link-budget items with no meaning on real hardware.
SIMULATION_ONLY = [
    "throttle", "channel", "channel_echo", "noise_enabled", "rx_noise_dbm",
    "path_loss_db", "noise_volt", "path_gain", "expected_rx_dbm", "snr_rx_db",
    "esno_rx_db", "ebno_rx_db", "reference_delay", "reference_source", "unpack_tx",
]


def rename_symbol(graph, old, new):
    pattern = re.compile(r"\b" + old + r"\b")
    for block in graph["blocks"]:
        if block["name"] == old:
            block["name"] = new
        for key, value in block["parameters"].items():
            if isinstance(value, str):
                block["parameters"][key] = pattern.sub(new, value)
    graph["connections"][:] = [
        [new if c[0] == old else c[0], c[1], new if c[2] == old else c[2], c[3]]
        for c in graph["connections"]
    ]


def build(profile):
    source = ROOT / f"grc/single_carrier_{profile}.grc"
    graph = copy.deepcopy(yaml.safe_load(source.read_text()))
    label = LABELS[profile]
    options = graph["options"]["parameters"]
    options["id"] = f"n210_{profile}"
    options["title"] = f"{label} over the air | two USRP N210s"

    graph["blocks"] = [b for b in graph["blocks"] if b["name"] not in SIMULATION_ONLY]
    graph["connections"][:] = [
        c for c in graph["connections"]
        if c[0] not in SIMULATION_ONLY and c[2] not in SIMULATION_ONLY
    ]
    rename_symbol(graph, "tx_power_dbm", "tx_level_dbfs")
    blocks = {b["name"]: b for b in graph["blocks"]}
    edges = graph["connections"]

    def add(name, kind, x, y, **parameters):
        node = dict(
            name=name, id=kind,
            parameters={k: str(v) for k, v in parameters.items()},
            states=dict(coordinate=[x, y], rotation=0, state="enabled"),
        )
        graph["blocks"].append(node)
        blocks[name] = node
        return node

    def wire(src, dst, src_port=0, dst_port=0):
        edges.append([src, str(src_port), dst, str(dst_port)])

    def unwire(src, dst):
        edges[:] = [c for c in edges if not (c[0] == src and c[2] == dst)]

    # --- Controls (top row, beside the existing ones) -----------------------
    blocks["tx_level_dbfs"]["parameters"].update(
        value="-15", label="TX digital RMS level (dBFS, keep peaks < 0)"
    )
    controls = [
        ("tx_usrp_address", "parameter", dict(value="addr=192.168.10.2", type="str",
         label="TX N210 device address", short_id="", hide="none")),
        ("rx_usrp_address", "parameter", dict(value="addr=192.168.10.3", type="str",
         label="RX N210 device address", short_id="", hide="none")),
        ("center_freq_hz", "parameter", dict(value="915e6", type="eng_float",
         label="RF center frequency (Hz)", short_id="", hide="none")),
        ("tx_gain_norm", "variable_qtgui_range", dict(value="0.5", start="0", stop="1",
         step="0.01", label="TX gain (normalized 0-1)", widget="counter_slider",
         rangeType="float", orient="QtCore.Qt.Horizontal", min_len="200",
         gui_hint="")),
        ("rx_gain_norm", "variable_qtgui_range", dict(value="0.5", start="0", stop="1",
         step="0.01", label="RX gain (normalized 0-1)", widget="counter_slider",
         rangeType="float", orient="QtCore.Qt.Horizontal", min_len="200",
         gui_hint="")),
        ("carrier_loop_bw", "variable",
         dict(value=f"2*math.pi/{COSTAS_BW_DIVISOR[profile]}")),
        ("data_period_bits", "variable", dict(value="8*len(tx_data)")),
        # Fixed known data: the same DATA_BYTES random bytes every period.
        ("tx_data", "variable", dict(
            value=f"list(numpy.random.RandomState(42).randint(0, 256, {DATA_BYTES}))")),
        # Known TX symbols for one data block (data_period_bits/k symbols).
        ("training_symbols", "variable", dict(value=(
            "list(numpy.asarray(const.points())[numpy.packbits(numpy.hstack(["
            "numpy.zeros((data_period_bits // k, 8-k), dtype=numpy.uint8), "
            "numpy.unpackbits(numpy.array(tx_data, dtype=numpy.uint8))"
            ".reshape(-1, k)]), axis=1).ravel()])"))),
        ("preamble_len", "variable", dict(value="128")),
    ]
    for index, (name, kind, parameters) in enumerate(controls):
        add(name, kind, 16 + 200 * index, 176, **parameters)

    # --- TX: modulator output scaled to dBFS goes straight to the N210 ------
    add("usrp_tx", "uhd_usrp_sink", 1400, 600,
        type="fc32", otw="sc16", stream_args="", stream_chans="[]",
        dev_addr="tx_usrp_address", dev_args='""', sync="none", start_time="-1.0",
        clock_rate="0e0", num_mboards="1", clock_source0="", time_source0="",
        sd_spec0="", nchan="1", samp_rate="samp_rate",
        center_freq0="center_freq_hz", gain0="tx_gain_norm", gain_type0="normalized",
        ant0='"TX/RX"', bw0="0", lo_source0="internal", lo_export0="False",
        show_lo_controls="False", len_tag_name='""')
    wire("tx_power", "usrp_tx")

    # --- RX: N210 -> AGC -> timing -> Costas -> preamble -> trained EQ --
    add("usrp_rx", "uhd_usrp_source", 16, 760,
        type="fc32", otw="sc16", stream_args="", stream_chans="[]",
        dev_addr="rx_usrp_address", dev_args='""', sync="none", start_time="-1.0",
        clock_rate="0e0", num_mboards="1", clock_source0="", time_source0="",
        sd_spec0="", nchan="1", samp_rate="samp_rate",
        center_freq0="center_freq_hz", rx_agc0="Disabled", gain0="rx_gain_norm",
        gain_type0="normalized", ant0='"RX2"', bw0="0", lo_source0="internal",
        lo_export0="False", dc_offs_enb0="auto", dc_offs0="0+0j",
        iq_imbal_enb0="auto", iq_imbal0="0+0j", show_lo_controls="False")
    # The RX level meters stay on the raw N210 samples (fixed RF gain), so
    # they compare antennas. Demodulation gets its own slow AGC2 (rate 1e-3:
    # about a 250-symbol time constant near unity gain, so it does not follow
    # the symbol-to-symbol amplitude of ASK/QAM).
    rx_level = blocks["rx_level"]
    rx_level["id"] = "analog_agc2_xx"
    rx_level["parameters"] = dict(type="complex", attack_rate="1e-3", decay_rate="1e-3",
                                  reference="1.0", gain="1.0", max_gain="65536")
    wire("usrp_rx", "rx_level")
    wire("usrp_rx", "rx_iq_link")

    # AGC -> timing -> Costas -> preamble detector -> trained EQ.
    unwire("clock_sync", "rx_scale")
    x, y = blocks["clock_sync"]["states"]["coordinate"]
    add("preamble_detect", "digital_corr_est_cc", x + 440, y,
        symbols="list(numpy.array(training_symbols[:preamble_len])/symbol_rms)", sps="1",
        mark_delay="eq_delay_symbols+1", threshold="0.9999", threshold_method="digital.THRESHOLD_DYNAMIC")
    add("carrier_sync", "digital_costas_loop_cc", x + 220, y,
        w="carrier_loop_bw", order=COSTAS_ORDER[profile], use_snr="False")
    wire("clock_sync", "carrier_sync")
    wire("carrier_sync", "preamble_detect")
    wire("preamble_detect", "rx_scale")
    # The tag is placed one symbol past the equalizer's centre tap so training
    # lines up with its output; the 11-tap LMS absorbs residual offsets.
    blocks["equalizer"]["parameters"].update(
        training_sequence="training_symbols", training_start_tag="corr_est",
        adapt_after_training="True")

    # --- TX: fixed known data, no differential coding -----------------------
    blocks["random_bytes"]["id"] = "blocks_vector_source_x"
    blocks["random_bytes"]["parameters"] = dict(
        type="byte", vector="tx_data", repeat="True", vlen="1", tags="[]")
    blocks["modulator"]["parameters"]["differential"] = "False"
    graph["blocks"][:] = [b for b in graph["blocks"]
                          if b["name"] not in ("diff_decoder", "tx_symbol_diff")]
    edges[:] = [c for c in edges if "diff_decoder" not in (c[0], c[2])
                and "tx_symbol_diff" not in (c[0], c[2])]
    wire("decoded_source", "unpack_rx")
    wire("tx_symbol_chunks", "tx_symbols")

    # --- Self-referenced BER: RX bits vs RX bits one data period earlier ----
    wire("unpack_rx", "delay")
    blocks["delay"]["parameters"]["delay"] = "data_period_bits"
    for name in ("skip_rx", "skip_tx"):
        # One block fills the RX-vs-RX delay line; one more lets the AGC,
        # Costas loop and first equalizer training settle before counting.
        blocks[name]["parameters"]["num_items"] = "warmup_bits+2*data_period_bits"
    blocks["ber_scale"]["parameters"]["const"] = "0.5/ber_window"
    blocks["ber_display"]["parameters"].update(
        name="BER | RX vs RX one data period earlier, /2 (preamble-trained)")
    blocks["ber_history"]["parameters"]["name"] = "BER per window (preamble-trained, RX vs RX one period earlier)"

    # --- Link-budget tables: digital full-scale levels and MER ---------------
    # MER (= Es/N0 estimate) and Eb/N0 come from the decision-directed EVM.
    # EVM is per symbol; keeping one in 4096/sps puts it at the same rate as
    # the 4096-sample power meters, so all rows of the table update together.
    graph["blocks"][:] = [b for b in graph["blocks"] if b["name"] != "rx_ebno_input"]
    edges[:] = [c for c in edges if c[0] not in ("rx_ebno_input", "rx_snr_input")]
    blocks["rx_snr_input"]["parameters"]["stream_id"] = "evm_history"
    x, y = blocks["rx_snr_input"]["states"]["coordinate"]
    add("evm_table_rate", "blocks_keep_one_in_n", x + 150, y, type="float",
        n="4096//sps", vlen="1")
    wire("rx_snr_input", "evm_table_rate")
    for name, offset in [("rx_snr", "40"), ("rx_ebno", "40-10*math.log10(k)")]:
        blocks[name]["id"] = "blocks_nlog10_ff"
        blocks[name]["parameters"] = dict(n="-20", k=offset, vlen="1")
        wire("evm_table_rate", name)
    rx_table = blocks["link_rx_table"]["parameters"]
    rx_table.update(name="Receive (fixed RF gain, uncalibrated)", nconnections="4",
                    label1="ADC level", unit1="dBFS", label2="MER", unit2="dB",
                    label3="Eb/N0 est.", unit3="dB", label4="EVM", unit4="%",
                    color4='("black", "black")', factor4="1")
    wire("evm_table_rate", "link_rx_table", 0, 3)
    blocks["link_tx_table"]["parameters"].update(
        name="Transmit (digital full scale)", unit1="dBFS", label2="Sampled peak (keep < 0)",
        unit2="dBFS")
    # Self-referenced error count: each real bit error appears twice.
    blocks["ber_test_scale"]["parameters"]["const"] = "0.5/(10000*ber_test_blocks)"
    blocks["ber_test_seconds"]["parameters"]["value"] = (
        "(warmup_bits + 3*data_period_bits + ber_test_bits) / bit_rate")
    blocks["views"]["parameters"]["label3"] = "RF levels"
    for name, axis in [("eye", "I"), ("eye_quadrature", "Q")]:
        blocks[name]["parameters"]["label1"] = f"RX {axis} | raw N210 RX output"
    if "section_channel" in blocks:
        blocks["section_channel"]["parameters"]["note"] = "N210 RF FRONT END"

    leftovers = [n for n in SIMULATION_ONLY
                 if any(re.search(r"\b" + n + r"\b", str(b["parameters"]))
                        for b in graph["blocks"] if b["id"] != "note")]
    assert not leftovers, f"{profile}: still references {leftovers}"
    target = ROOT / f"grc/n210_{profile}.grc"
    target.write_text(yaml.safe_dump(graph, sort_keys=False, width=110))
    return target


if __name__ == "__main__":
    for profile in PROFILES:
        print("wrote", build(profile).relative_to(ROOT))
