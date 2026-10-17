"""Extract reusable, editable stock-block stages from the lab definitions."""

from copy import deepcopy
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def extract(
    items,
    edges,
    module_id,
    title,
    names,
    entry,
    exit,
    types,
    arguments,
    defaults,
    dependencies=(),
):
    from build_flowgraphs import block, parameter, note

    selected = set(names)
    lookup = {b["name"]: b for b in items}
    inner = [deepcopy(lookup[n]) for n in names]
    controls = [
        parameter(
            k, defaults[k][0], defaults[k][1], 240 + i % 3 * 400, 224 + i // 3 * 144
        )
        for i, k in enumerate(arguments)
    ]
    support = [deepcopy(lookup[n]) for n in dependencies]
    for i, b in enumerate(support):
        b["states"]["coordinate"] = [240 + i * 440, 64]
    y = 384 + ((len(controls) + 2) // 3) * 144
    for i, b in enumerate(inner):
        b["states"]["coordinate"] = [560 + i * 400, y]
    for b in inner:
        if b["id"] == "analog_noise_source_x":
            b["states"]["coordinate"] = [960, y + 176]
    pads = [
        block(
            "input_stream",
            "pad_source",
            dict(
                label="bits" if types[0] == "byte" else "samples",
                type=types[0],
                vlen="1",
                num_streams="1",
                optional="False",
            ),
            240,
            y,
        ),
        block(
            "output_stream",
            "pad_sink",
            dict(
                label="bits" if types[1] == "byte" else "samples",
                type=types[1],
                vlen="1",
                num_streams="1",
                optional="False",
            ),
            560 + len(inner) * 400,
            y,
        ),
    ]
    internal = [e[:] for e in edges if e[0] in selected and e[2] in selected]
    internal += [["input_stream", "0", entry, "0"], [exit, "0", "output_stream", "0"]]
    graph = dict(
        options=dict(
            parameters=dict(
                id=module_id,
                title=title,
                category="[Antenna benchmark]",
                generate_options="hb",
                output_language="python",
                description="Editable stock-block stage. See docs/MODULAR_FLOWGRAPHS.md.",
            ),
            states=dict(coordinate=[8, 8], rotation=0, state="enabled"),
        ),
        blocks=support
        + controls
        + inner
        + pads
        + [
            note(
                "contract",
                "STREAM CONTRACT: "
                + ("unpacked 0/1 bytes" if types[0] == "byte" else "complex64 samples")
                + " -> "
                + ("unpacked 0/1 bytes" if types[1] == "byte" else "complex64 samples")
                + ". Edit this module, generate it, then regenerate its parent lab.",
                240,
                y + 352,
            )
        ],
        connections=internal,
        metadata=dict(file_format=1, grc_version="3.10.12.0"),
    )
    destination = ROOT / "grc/modules"
    destination.mkdir(exist_ok=True)
    (destination / f"{module_id}.grc").write_text(
        yaml.safe_dump(graph, sort_keys=False, width=110)
    )
    rewritten = []
    for source, sp, target, tp in edges:
        if source in selected and target in selected:
            continue
        if source in selected:
            if source != exit or sp != "0":
                raise ValueError(f"Unexposed output: {source}:{sp}")
            source = exit
        if target in selected:
            if target != entry or tp != "0":
                raise ValueError(f"Unexposed input: {target}:{tp}")
            target = exit
        rewritten.append([source, sp, target, tp])
    edges[:] = rewritten
    items[:] = [b for b in items if b["name"] not in selected]
    items.append(block(exit, module_id, arguments, 240, y))


def modularize(name, items, edges):
    if name not in ("siso_modem_lab", "siso_wlan_lab"):
        return
    from build_flowgraphs import parameter

    items.append(parameter("noise_seed", 20261017, "intx", 0, 0))
    next(b for b in items if b["name"] == "awgn")["parameters"]["seed"] = "noise_seed"
    common = dict(
        noise_voltage=(0.1, "eng_float"),
        noise_seed=(20261017, "intx"),
        channel_gain=(1, "eng_float"),
    )
    if name == "siso_modem_lab":
        extract(
            items,
            edges,
            "bench_symbol_mapper",
            "Symbol mapper | unpacked bits to IQ",
            ["pack_bits", "mapper"],
            "pack_bits",
            "mapper",
            ("byte", "complex"),
            dict(order="order"),
            dict(order=(16, "intx")),
            ("project_imports", "k"),
        )
        extract(
            items,
            edges,
            "bench_scalar_channel",
            "SISO scalar channel | loss + AWGN",
            ["siso_path", "awgn", "channel_output"],
            "siso_path",
            "channel_output",
            ("complex", "complex"),
            dict(
                channel_gain="channel_gain",
                noise_voltage="noise_voltage",
                noise_seed="noise_seed",
            ),
            common,
        )
    else:
        extract(
            items,
            edges,
            "bench_fir_channel",
            "SISO channel | FIR + CFO + AWGN",
            ["siso_fir", "carrier_offset", "awgn", "channel_output"],
            "siso_fir",
            "channel_output",
            ("complex", "complex"),
            dict(
                channel_gain="channel_gain",
                channel_taps="channel_taps",
                cfo_hz="cfo_hz",
                sample_rate="sample_rate",
                noise_voltage="noise_voltage",
                noise_seed="noise_seed",
            ),
            dict(
                common,
                channel_taps=("1+0j", "str"),
                cfo_hz=(0, "eng_float"),
                sample_rate=(20e6, "eng_float"),
            ),
            ("project_imports",),
        )
    extract(
        items,
        edges,
        "bench_symbol_demapper",
        "Hard decisions | IQ to unpacked bits",
        ["demap", "rx_bits"],
        "demap",
        "rx_bits",
        ("complex", "byte"),
        dict(order="order"),
        dict(order=(16, "intx")),
        ("project_imports", "k", "constellation_object"),
    )
    if name == "siso_wlan_lab":
        # Reuse exactly the same decoder module on the known reference branch.
        selected = {"tx_decisions", "tx_bits"}
        edges[:] = [
            [s, sp, "tx_bits" if t == "tx_decisions" else t, tp]
            for s, sp, t, tp in edges
            if not (s in selected and t in selected)
        ]
        items[:] = [b for b in items if b["name"] not in selected]
        from build_flowgraphs import block

        items.append(
            block("tx_bits", "bench_symbol_demapper", dict(order="order"), 0, 0)
        )
    items[:] = [b for b in items if b["name"] != "constellation_object"]
