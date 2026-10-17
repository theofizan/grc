"""Square RF charts from actual GNU Radio captures; no fitted RX corrections."""

from pathlib import Path
import csv
import json
import numpy as np
from scipy.io import loadmat
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

ROOT = Path(__file__).resolve().parents[1]
profiles = ["bpsk", "qpsk", "8psk", "4ask", "8ask", "16qam"]
labels = ["BPSK", "QPSK", "8-PSK", "4-ASK", "8-ASK", "16-QAM"]
records = [
    json.loads((ROOT / "results" / f"{p}_noise_0.3.json").read_text()) for p in profiles
]


def chart(title, xlabel, ylabel):
    figure, axis = plt.subplots(figsize=(7, 7), layout="constrained")
    axis.set(title=title, xlabel=xlabel, ylabel=ylabel)
    axis.set_box_aspect(1)
    axis.grid(alpha=0.2)
    axis.set_axisbelow(True)
    return figure, axis


def save(figure, name):
    for extension in ["png", "pdf", "svg"]:
        figure.savefig(ROOT / "results" / f"{name}.{extension}", dpi=180)
    plt.close(figure)


fig, ax = chart(
    "Gross uncoded data rate at 1 Msymbol/s\n4 Msamples/s; excludes packet overhead and FEC",
    "Modulation",
    "Gross rate (Mbit/s)",
)
rates = [r["gross_bit_rate_bps"] / 1e6 for r in records]
bars = ax.bar(labels, rates, color="#31688e")
ax.bar_label(bars, labels=[f"{r:g}" for r in rates], padding=4)
ax.set_ylim(0, 4.7)
ax.tick_params(axis="x", rotation=30)
save(fig, "data_rate")
with (ROOT / "results/data_rate.csv").open("w") as file:
    writer = csv.writer(file)
    writer.writerow(
        [
            "modulation",
            "bits_per_symbol",
            "symbol_rate_symbols_s",
            "sample_rate_samples_s",
            "gross_bit_rate_bps",
            "ideal_rrc_bandwidth_hz",
        ]
    )
    for label, r in zip(labels, records):
        writer.writerow(
            [
                label,
                int(round(r["gross_bit_rate_bps"] / r["symbol_rate_hz"])),
                r["symbol_rate_hz"],
                r["sample_rate_hz"],
                r["gross_bit_rate_bps"],
                1.35 * r["symbol_rate_hz"],
            ]
        )

for metric, name, title, ylabel in [
    (
        "display_ber_mean",
        "ber_comparison",
        "Measured BER | RX noise −90.46 dBm over Fs",
        "Bit error ratio",
    ),
    (
        "reference_evm_percent",
        "evm_comparison",
        "Data-aided EVM against actual TX symbols",
        "RMS EVM (%)",
    ),
]:
    fig, ax = chart(
        title + "\n1 Msymbol/s; TX 0 dBm; net loss 80 dB", "Modulation", ylabel
    )
    values = [r[metric] for r in records]
    bars = ax.bar(labels, values, color="#31688e")
    ax.bar_label(
        bars,
        labels=["0 observed" if v == 0 else f"{v:.3g}" for v in values],
        padding=4,
        fontsize=9,
    )
    ax.margins(y=0.18)
    ax.tick_params(axis="x", rotation=30)
    save(fig, name)

fig, ax = chart(
    "RX noise and bit-energy ratios\nKnown-TX link budget; noise bandwidth Fs = 4 MHz",
    "Modulation",
    "Ratio (dB)",
)
x = np.arange(6)
ax.bar(x - 0.18, [r["nominal_rx_snr_db"] for r in records], 0.36, label="SNR over Fs")
ax.bar(
    x + 0.18,
    [r["nominal_rx_ebno_db"] for r in records],
    0.36,
    label="Eb/N₀ per uncoded bit",
)
ax.set_xticks(x, labels, rotation=30)
ax.legend()
save(fig, "rx_ratios")

for profile, label, r in zip(profiles, labels, records):
    data = loadmat(ROOT / "results" / f"{profile}_noise_0.3.mat", squeeze_me=True)
    points = np.ravel(data["constellation_points"]).astype(complex)
    rms = np.sqrt(np.mean(abs(points) ** 2))
    points /= rms
    guide = float(data["evm_guide_percent"]) / 100
    measured = r["reference_evm_percent"] / 100
    for is_rx in [False, True]:
        symbols = (
            np.ravel(data["aligned_rx_symbols" if is_rx else "tx_symbols"])[:6000] / rms
        )
        title = (
            f'{label} RX symbols | data-aided EVM {100*measured:.2f}%\nSNR(Fs) {r["nominal_rx_snr_db"]:.2f} dB; Eb/N₀ {r["nominal_rx_ebno_db"]:.2f} dB'
            if is_rx
            else f"{label} actual TX encoded symbols\nBefore RRC shaping; normalized RMS symbol amplitude = 1"
        )
        fig, ax = chart(
            title,
            "In-phase / RMS symbol amplitude",
            "Quadrature / RMS symbol amplitude",
        )
        ax.scatter(
            symbols.real,
            symbols.imag,
            s=5,
            alpha=0.16,
            label="Received symbols" if is_rx else "TX encoded symbols",
        )
        ax.scatter(
            points.real,
            points.imag,
            c="black",
            marker="+",
            s=70,
            label="Ideal symbol positions",
            zorder=4,
        )
        for index, point in enumerate(points):
            ax.add_patch(
                Circle(
                    (point.real, point.imag),
                    guide,
                    fill=False,
                    color="#16803d",
                    linestyle="--",
                    linewidth=1,
                    label=f"{guide*100:g}% RMS-radius guide" if index == 0 else None,
                )
            )
            if is_rx:
                ax.add_patch(
                    Circle(
                        (point.real, point.imag),
                        measured,
                        fill=False,
                        color="#e38215",
                        linewidth=0.8,
                        label="Measured RMS-error radius" if index == 0 else None,
                    )
                )
        if is_rx:
            tx = np.ravel(data["aligned_tx_symbols"])[:6000] / rms
            for i in np.linspace(0, len(symbols) - 1, 20, dtype=int):
                ax.plot(
                    [tx[i].real, symbols[i].real],
                    [tx[i].imag, symbols[i].imag],
                    color="#e38215",
                    alpha=0.55,
                    lw=0.7,
                )
        limit = max(abs(points.real).max(), abs(points.imag).max()) + max(
            0.3, measured * 2
        )
        ax.set(xlim=(-limit, limit), ylim=(-limit, limit))
        ax.set_aspect("equal", adjustable="box")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=8, ncol=2)
        save(fig, f'{profile}_{"rx" if is_rx else "tx"}_constellation')
# Retire the former wide two-panel comparison.
for extension in ["png", "pdf"]:
    old = ROOT / "results" / f"performance.{extension}"
    if old.exists():
        old.unlink()
