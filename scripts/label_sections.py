"""Add editable section banners without changing any signal parameters/wires.

The stock Notes compile in ordinary GRC. Open with antenna-grc for large blue
boxes. Section labels contain the title only, without a subtitle or comment.
"""

from pathlib import Path
import argparse
import yaml

ROOT = Path(__file__).resolve().parents[1]


def remove_sections(graph):
    """Undo only our heading space before an explicit full diagram repack."""
    headings = [
        b
        for b in graph["blocks"]
        if b["id"] == "note" and b["name"].startswith("section_")
    ]
    if not headings:
        return graph
    rows = sorted({b["states"]["coordinate"][1] for b in headings})
    graph["blocks"] = [b for b in graph["blocks"] if b not in headings]
    for block in graph["blocks"]:
        y = block["states"]["coordinate"][1]
        block["states"]["coordinate"][1] -= 80 * sum(y >= row for row in rows)
    return graph


def label_sections(graph):
    if any(block["name"] == "section_controls" for block in graph["blocks"]):
        # Update wording without moving any hand-positioned banners.
        for block in graph["blocks"]:
            if block["id"] == "note" and block["name"].startswith("section_"):
                block["parameters"]["note"] = block["parameters"]["note"].partition(
                    "\n"
                )[0]
                block["parameters"]["comment"] = ""
        return graph
    blocks = graph["blocks"]
    by = {block["name"]: block for block in blocks}
    # Each boundary creates room for a heading. Relative positions and the
    # tightly packed variable spacing stay unchanged inside each section.
    boundaries = [
        (
            0,
            [
                (
                    "controls",
                    160,
                    "CONTROLS & RF SETTINGS",
                )
            ],
        ),
        (
            by["random_bytes"]["states"]["coordinate"][1],
            [
                (
                    "transmitter",
                    by["random_bytes"]["states"]["coordinate"][0],
                    "TRANSMITTER",
                ),
                (
                    "channel",
                    by["channel"]["states"]["coordinate"][0],
                    "CHANNEL",
                ),
                (
                    "receiver",
                    by["rx_level"]["states"]["coordinate"][0],
                    "RECEIVER",
                ),
            ],
        ),
        (
            by["diff_decoder"]["states"]["coordinate"][1],
            [
                (
                    "ber",
                    16,
                    "BER MEASUREMENT",
                )
            ],
        ),
        (
            by["constellation"]["states"]["coordinate"][1],
            [
                (
                    "rx_diagnostics",
                    16,
                    "RX DIAGNOSTICS",
                )
            ],
        ),
        (
            by["scope"]["states"]["coordinate"][1],
            [
                (
                    "power",
                    16,
                    "LINK BUDGET & POWER METERS",
                )
            ],
        ),
        (
            by["tx_symbol_input"]["states"]["coordinate"][1],
            [
                (
                    "reference",
                    16,
                    "TX SYMBOL REFERENCE & EVM GUIDES",
                )
            ],
        ),
        (
            by["before_eq_input"]["states"]["coordinate"][1],
            [
                (
                    "pre_eq",
                    16,
                    "BEFORE EQUALIZATION",
                )
            ],
        ),
        (
            by["middle_input"]["states"]["coordinate"][1],
            [
                (
                    "eyes",
                    16,
                    "EYE COMPARISON: MIDDLE / AFTER EQ / TX",
                )
            ],
        ),
        (
            by["tx_wave_input"]["states"]["coordinate"][1],
            [
                (
                    "extra_plots",
                    16,
                    "LIVE WAVEFORM & ADAPTATION MONITORS",
                )
            ],
        ),
    ]
    gap = 80
    for block in blocks:
        y = block["states"]["coordinate"][1]
        block["states"]["coordinate"][1] += gap * sum(
            y >= boundary for boundary, _ in boundaries
        )
    for index, (boundary, headings) in enumerate(boundaries):
        y = boundary + gap * index
        for name, x, title in headings:
            blocks.append(
                dict(
                    name="section_" + name,
                    id="note",
                    parameters=dict(
                        note=title,
                        comment="",
                    ),
                    states=dict(coordinate=[x, y], rotation=0, state="enabled"),
                )
            )
    return graph


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--modulation", choices=["bpsk", "qpsk", "8psk", "4ask", "8ask", "16qam"]
    )
    args = parser.parse_args()
    files = (
        [ROOT / "grc" / f"single_carrier_{args.modulation}.grc"]
        if args.modulation
        else sorted((ROOT / "grc").glob("*.grc"))
    )
    for file in files:
        graph = yaml.safe_load(file.read_text())
        file.write_text(
            yaml.safe_dump(label_sections(graph), sort_keys=False, width=110)
        )
        print("Labeled", file.name)
