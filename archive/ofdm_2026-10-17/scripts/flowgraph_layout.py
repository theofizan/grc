"""Presentation-only layout shared by the seven generated GRC canvases."""

import textwrap

ROWS = {
    "awgn_symbol_benchmark": [
        ("TRANSMIT REFERENCE", ["reference_symbols", "transmitted_symbols"]),
        ("AWGN CHANNEL AND CAPTURE", ["complex_awgn", "add_noise", "received_symbols"]),
    ],
    "wlan_reference_channel": [
        ("REFERENCE WAVEFORM", ["wifi_reference"]),
        ("AWGN CHANNEL AND CAPTURE", ["complex_awgn", "add_noise", "wifi_capture"]),
    ],
    "wlan_ofdm_fft": [
        (
            "CAPTURE AND KNOWN-SCHEDULE DATA EXTRACTION",
            ["aligned_capture", "remove_leading_samples", "extract_data_fields"],
        ),
        (
            "OFDM DEMODULATION AND CAPTURE",
            ["remove_cyclic_prefix", "ofdm_vectors", "fft_64", "fft_capture"],
        ),
    ],
    "usrp_wifi_tx": [("SISO TRANSMITTER", ["wifi_reference", "usrp_sink"])],
    "usrp_wifi_rx": [
        (
            "SISO RECEIVER AND FINITE CAPTURE",
            ["usrp_source", "finite_capture", "raw_iq"],
        )
    ],
    "siso_modem_lab": [
        (
            "TRANSMITTER | known bits to complex symbols",
            ["known_bits", "finite_bits", "pack_bits", "mapper", "pace_tx"],
        ),
        (
            "SISO CHANNEL | fixed TX power, independent noise",
            ["siso_path", "awgn", "channel_output"],
        ),
        (
            "RECEIVER | ideal scalar equalization and decisions",
            ["equalize", "demap", "rx_bits"],
        ),
        (
            "METRICS | aligned reference and received streams",
            ["ber_meter", "ber_display", "evm_meter", "evm_display"],
        ),
        (
            "DISPLAYS | TX / RX waveform and constellation",
            ["tx_scope", "rx_scope", "constellation", "views"],
        ),
    ],
    "siso_wlan_lab": [
        (
            "TRANSMITTER | reference PHY waveform",
            ["tx_waveform", "finite_tx", "pace_tx"],
        ),
        (
            "SISO CHANNEL | attenuation, multipath, CFO and AWGN",
            ["siso_fir", "carrier_offset", "channel_output"],
        ),
        (
            "RECEIVER | known burst schedule and training-based recovery",
            ["extract_bursts", "burst_receiver", "demap", "rx_bits"],
        ),
        (
            "REFERENCE | mapped DATA symbols and bits for scoring",
            ["tx_reference", "finite_reference", "tx_decisions", "tx_bits"],
        ),
        (
            "METRICS | pre-FEC BER and RMS EVM",
            ["ber_meter", "ber_display", "evm_meter", "evm_display"],
        ),
        (
            "DISPLAYS | TX / RX waveform and constellation",
            ["tx_scope", "rx_scope", "constellation", "views"],
        ),
    ],
}


def arrange(name, items):
    """Change only canvas coordinates and notes; preserve all DSP parameters."""
    by_name = {item["name"]: item for item in items}
    annotations = [item for item in items if item["id"] == "note"]

    def place(key, x, y):
        by_name[key]["states"]["coordinate"] = [x, y]

    def heading(key, text, y):
        items.append(
            dict(
                name="layout_" + key,
                id="note",
                parameters=dict(note=text),
                states=dict(
                    coordinate=[240, y],
                    rotation=0,
                    state="enabled",
                    bus_sink=False,
                    bus_source=False,
                    bus_structure=None,
                ),
            )
        )

    place("project_imports", 2200, 16)
    heading("controls", "RUN PARAMETERS", 240)
    y = 304
    for kind, title in [("parameter", "DERIVED CONSTANTS"), ("variable", None)]:
        group = [item for item in items if item["id"] == kind]
        for index, item in enumerate(group):
            place(item["name"], 240 + (index % 4) * 440, y + (index // 4) * 144)
        y += ((len(group) + 3) // 4) * 144 + 80
        if title:
            heading("constants", title, y - 48)

    for index, (title, names) in enumerate(ROWS[name]):
        heading(str(index), title, y)
        names = [key for key in names if key in by_name]
        for column, key in enumerate(names):
            place(key, 240 + column * 440, y + 72)
        if name == "siso_modem_lab" and index == 1 and "awgn" in by_name:
            # Put the independent noise source underneath the signal branch.
            place("awgn", 680, y + 216)
        if name == "siso_wlan_lab" and index == 1 and "awgn" in by_name:
            place("awgn", 680, y + 216)
        y += (
            400
            if ("CHANNEL" in title or "DISPLAYS" in title or "usrp" in name)
            else 280
        )

    heading("notes", "MODEL ASSUMPTIONS AND OPERATING NOTES", y)
    y += 64
    for item in annotations:
        item["parameters"]["note"] = textwrap.fill(
            item["parameters"]["note"], width=100
        )
        place(item["name"], 240, y)
        y += 64 + 24 * len(item["parameters"]["note"].splitlines())
