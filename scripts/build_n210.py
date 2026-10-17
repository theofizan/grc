"""Derive Ettus USRP N210 over-the-air flowcharts from the saved simulations.

Reads grc/single_carrier_<mod>.grc (never modified) and writes
grc/n210_<mod>.grc. Only stock GNU Radio / gr-uhd blocks are used, and the
flowchart stays flat. Changes relative to the simulation:

* Throttle + Channel Model are replaced by a UHD USRP Sink (TX/RX port) and a
  UHD USRP Source (RX2 port) on the same N210. The USRP sample clock paces
  the flowchart, so no Throttle is needed.
* TX level is set in dBFS (0 dBFS = DAC full scale), not dBm. The N210 is
  not power-calibrated; conducted dBm depends on daughterboard and gain.
* RX uses a fixed digital gain (no AGC) instead of the known path-loss gain,
  so RX level tracks antenna performance, plus a
  stock Costas loop for carrier phase/frequency. A manual phase-ambiguity
  rotation after the equalizer picks the correct one of the constellation's
  symmetric lock points (needed for every format except BPSK).
* BER is self-referenced: the transmitted data repeats every 262,144 bits
  (32,768 random bytes), so RX bits are XORed with the RX bits one data
  period earlier. Each real bit error produces two mismatches, so the count
  is scaled by 1/2. No TX-to-RX latency needs to be known, and the
  measurement re-aligns itself one period after any USRP overflow/underflow.
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
    options["title"] = f"{label} over the air | USRP N210 loopback"

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
        ("usrp_address", "parameter", dict(value="addr=192.168.10.2", type="str",
         label="N210 device address", short_id="", hide="none")),
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
        ("phase_fix_deg", "variable_qtgui_range", dict(value="0", start="0", stop="270",
         step=str(360 // COSTAS_ORDER[profile]), label="Phase-ambiguity rotation (deg)",
         widget="counter_slider", rangeType="float", orient="QtCore.Qt.Horizontal",
         min_len="200", gui_hint="")),
        ("rx_gain_db", "parameter", dict(value="75", type="eng_float",
         label="Fixed RX digital gain (dB) = -(RX ADC dBFS)", short_id="", hide="none")),
        ("carrier_loop_bw", "variable", dict(value=f"2*math.pi/200")),
        ("data_period_bits", "variable", dict(value="8*32768")),
    ]
    for index, (name, kind, parameters) in enumerate(controls):
        add(name, kind, 16 + 200 * index, 176, **parameters)

    # --- TX: modulator output scaled to dBFS goes straight to the N210 ------
    add("usrp_tx", "uhd_usrp_sink", 1400, 600,
        type="fc32", otw="sc16", stream_args="", stream_chans="[]",
        dev_addr="usrp_address", dev_args='""', sync="none", start_time="-1.0",
        clock_rate="0e0", num_mboards="1", clock_source0="", time_source0="",
        sd_spec0="", nchan="1", samp_rate="samp_rate",
        center_freq0="center_freq_hz", gain0="tx_gain_norm", gain_type0="normalized",
        ant0='"TX/RX"', bw0="0", lo_source0="internal", lo_export0="False",
        show_lo_controls="False", len_tag_name='""')
    wire("tx_power", "usrp_tx")

    # --- RX: N210 -> fixed gain -> timing -> Costas -> EQ -> phase fix --------
    add("usrp_rx", "uhd_usrp_source", 16, 760,
        type="fc32", otw="sc16", stream_args="", stream_chans="[]",
        dev_addr="usrp_address", dev_args='""', sync="none", start_time="-1.0",
        clock_rate="0e0", num_mboards="1", clock_source0="", time_source0="",
        sd_spec0="", nchan="1", samp_rate="samp_rate",
        center_freq0="center_freq_hz", rx_agc0="Disabled", gain0="rx_gain_norm",
        gain_type0="normalized", ant0='"RX2"', bw0="0", lo_source0="internal",
        lo_export0="False", dc_offs_enb0="auto", dc_offs0="0+0j",
        iq_imbal_enb0="auto", iq_imbal0="0+0j", show_lo_controls="False")
    # Fixed RX gain, no AGC: the RX level stays proportional to the received
    # power, so antennas can be compared directly. Set rx_gain_db once to
    # -(RX ADC level in dBFS) so symbols arrive near unit RMS, then leave it
    # unchanged for the whole antenna comparison.
    rx_level = blocks["rx_level"]
    rx_level["parameters"]["const"] = "10**(rx_gain_db/20.0)"
    wire("usrp_rx", "rx_level")
    wire("usrp_rx", "rx_iq_link")

    unwire("clock_sync", "rx_scale")
    x, y = blocks["clock_sync"]["states"]["coordinate"]
    add("carrier_sync", "digital_costas_loop_cc", x + 220, y,
        w="carrier_loop_bw", order=COSTAS_ORDER[profile], use_snr="False")
    add("phase_fix", "blocks_multiply_const_vxx", x + 440, y,
        type="complex", const="complex(math.cos(math.radians(phase_fix_deg)),"
        "math.sin(math.radians(phase_fix_deg)))", vlen="1")
    wire("clock_sync", "carrier_sync")
    wire("carrier_sync", "rx_scale")
    # The decision-directed LMS equalizer can settle on any rotation the
    # constellation is symmetric to, so the operator's rotation goes after it,
    # right before the symbol decisions and EVM.
    for edge in edges:
        if edge[0] == "equalizer" and edge[1] == "0":
            edge[0] = "phase_fix"
    wire("equalizer", "phase_fix")

    # --- Self-referenced BER: RX bits vs RX bits one data period earlier ----
    wire("unpack_rx", "delay")
    blocks["delay"]["parameters"]["delay"] = "data_period_bits"
    for name in ("skip_rx", "skip_tx"):
        blocks[name]["parameters"]["num_items"] = "warmup_bits+data_period_bits"
    blocks["ber_scale"]["parameters"]["const"] = "0.5/ber_window"
    blocks["ber_display"]["parameters"].update(
        name="BER estimate | RX vs RX one data period earlier, /2")
    blocks["ber_history"]["parameters"]["name"] = "Self-referenced BER estimate per window"

    # --- MER replaces known-link-budget SNR / Eb/N0 -------------------------
    for name, offset, title in [
        ("rx_snr", "40", "MER from decision-directed EVM (Es/N0 estimate)"),
        ("rx_ebno", "40-10*math.log10(k)", "Eb/N0 estimate from MER"),
    ]:
        blocks[name]["id"] = "blocks_nlog10_ff"
        blocks[name]["parameters"] = dict(n="-20", k=offset, vlen="1")
        blocks[name + "_input"]["parameters"]["stream_id"] = "evm_history"
        display = "snr_display" if name == "rx_snr" else "ebno_display"
        blocks[display]["parameters"].update(name=title, label1=title)
    blocks["power_reference_chart"]["parameters"]["name"] = "MER history (dB)"

    # --- Levels are digital full-scale, not calibrated dBm -----------------
    relabel = {
        "tx_power_display": ("TX digital average level", "dBFS"),
        "rx_power_display": ("RX ADC level: signal + noise", "dBFS"),
        "peak_display": ("TX sampled peak (must stay below 0 dBFS)", "dBFS"),
    }
    for name, (title, unit) in relabel.items():
        blocks[name]["parameters"].update(name=title, label1=title, unit1=unit)
    blocks["power_history"]["parameters"].update(
        name="Digital levels | TX average and RX ADC (dBFS)",
        label1="TX average (dBFS)", label2="RX ADC total (dBFS)")
    blocks["envelope_plot"]["parameters"]["name"] = "TX sampled power envelope (dBFS)"
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
