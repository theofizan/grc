"""Plot cross-language validation and a readable overview of actual GRC graphs."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D
from antenna_bench.math import exact_ber, zero_error_upper_bound

ORDERS = (2, 4, 16, 64)
LABELS = ("BPSK", "QPSK", "16-QAM", "64-QAM")
COLORS = ("#0072BD", "#D95319", "#33994D", "#7E2F8E")
STYLES = ("-", "--", ":", "-.")


def save(fig, name):
    output = ROOT / "results/figures"
    output.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "pdf", "svg"):
        fig.savefig(output / f"{name}.{extension}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    plt.rcParams.update(
        {"font.size": 11, "axes.spines.top": False, "axes.spines.right": False}
    )
    python = np.genfromtxt(
        ROOT / "results/python/awgn_results.csv", names=True, delimiter=","
    )
    matlab = np.genfromtxt(
        ROOT / "results/theory/matlab_awgn_results.csv", names=True, delimiter=","
    )
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.2))
    dense = np.linspace(0, 18, 200)
    for order, label, color, style in zip(ORDERS, LABELS, COLORS, STYLES):
        p = python[python["order"] == order]
        m = matlab[matlab["order"] == order]
        axes[0].semilogy(dense, exact_ber(order, dense), color=color, ls=style, lw=1.6)
        axes[1].semilogy(
            dense,
            100 / np.sqrt(np.log2(order) * 10 ** (dense / 10)),
            color=color,
            ls=style,
            lw=1.6,
        )
        for data, marker in ((p, "o"), (m, "x")):
            mask = data["errors"] > 0
            axes[0].semilogy(
                data["ebno_db"][mask],
                data["ber"][mask],
                marker,
                ls="none",
                color=color,
                ms=6,
                mfc="none",
            )
            zero = ~mask
            axes[0].semilogy(
                data["ebno_db"][zero],
                [zero_error_upper_bound(int(n)) for n in data["bits"][zero]],
                "v",
                ls="none",
                color=color,
                ms=6,
                mfc="none",
            )
            axes[1].semilogy(
                data["ebno_db"],
                100 * data["evm_rms"],
                marker,
                ls="none",
                color=color,
                ms=6,
                mfc="none",
            )
        grc = json.loads(
            (ROOT / "results/grc" / f"symbol_order_{order}.json").read_text()
        )
        axes[0].semilogy(8, grc["ber"], "s", color=color, mfc="none", ms=9)
        axes[1].semilogy(8, 100 * grc["evm_rms"], "s", color=color, mfc="none", ms=9)
    axes[0].set(
        ylabel="Uncoded bit error ratio (errors / bits)",
        xlabel=r"$E_b/N_0$ per uncoded bit (dB)",
        ylim=(1e-6, 1),
        title="(a) BER: exact theory and three implementations",
    )
    axes[1].set(
        ylabel="RMS EVM (%)",
        xlabel=r"$E_b/N_0$ per uncoded bit (dB)",
        title="(b) EVM: AWGN prediction and estimates",
    )
    for ax in axes:
        ax.grid(alpha=0.25)
        ax.set_xlim(-0.25, 18.25)
        ax.set_xticks(range(0, 19, 2))
    handles = [
        Line2D([], [], color=c, ls=s, label=l + " theory")
        for l, c, s in zip(LABELS, COLORS, STYLES)
    ]
    handles += [
        Line2D([], [], color="black", marker=mark, mfc="none", ls="none", label=label)
        for mark, label in [
            ("o", "Python Monte Carlo"),
            ("x", "MATLAB Monte Carlo"),
            ("s", "GNU Radio at 8 dB"),
            ("v", "Zero errors: 95% upper limit"),
        ]
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.045),
        ncol=4,
        fontsize=10,
    )
    fig.suptitle(
        "Figure 6. Uncoded software cross-check: 100,000 symbols per point",
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.012,
        "Independent noise samples; BPSK/QPSK BER theory overlaps. Upper limits assume independent bits (nominal for QAM).",
        ha="center",
        fontsize=9,
    )
    fig.subplots_adjust(bottom=0.28, top=0.86, wspace=0.27)
    save(fig, "python_matlab_comparison")

    reports = [
        json.loads((ROOT / "results/grc" / f"wlan_rate_{rate}_matlab.json").read_text())
        for rate in range(8)
    ]
    py = [
        json.loads((ROOT / "results/grc" / f"wlan_rate_{rate}_python.json").read_text())
        for rate in range(8)
    ]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.7))
    axes[0].plot(range(8), [100 * r["evm_rms"] for r in py], "o-", label="Python")
    axes[0].plot(
        range(8),
        [100 * r["evmRms"] for r in reports],
        "x",
        markersize=10,
        label="MATLAB",
    )
    axes[0].set(
        xlabel="Legacy PHY data rate (Mb/s)",
        ylabel="RMS DATA EVM (%)",
        title="(a) Equalized DATA constellation",
    )
    axes[0].legend()
    axes[0].grid(alpha=0.25)
    axes[1].bar(
        range(8), [r["pythonMaxSymbolDifference"] for r in reports], color="#326a9b"
    )
    axes[1].set(
        xlabel="Legacy PHY data rate (Mb/s)",
        ylabel=r"Max. $|s_{Python}-s_{MATLAB}|$ (normalized)",
        title="(b) Equalizer agreement on identical IQ",
    )
    axes[1].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].set_ylim(0, 2.1e-15)
    axes[1].legend(
        [Line2D([], [], color="#326a9b", lw=8)],
        ["Maximum over all DATA symbols"],
        fontsize=9,
    )
    fft = [
        json.loads(
            (ROOT / "results/grc" / f"wlan_rate_{r}_fft_validation.json").read_text()
        )
        for r in range(8)
    ]
    axes[2].bar(
        range(8),
        [r["max_absolute_error"] for r in fft],
        color="#33994D",
        label="Maximum over all FFT bins",
    )
    axes[2].set(
        xlabel="Legacy PHY data rate (Mb/s)",
        ylabel=r"Max. $|X_{GRC}-X_{NumPy}|$ (FFT units)",
        title="(c) Native GRC CP removal and FFT",
    )
    axes[2].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    axes[2].grid(axis="y", alpha=0.25)
    axes[2].legend(fontsize=9)
    axes[2].set_ylim(0, max(r["max_absolute_error"] for r in fft) * 1.3)
    for ax in axes:
        ax.set_xticks(range(8), [6, 9, 12, 18, 24, 36, 48, 54])
    fig.suptitle(
        "Figure 7. Legacy Wi-Fi replay through GNU Radio: all eight PHY rates",
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.035,
        "25 dB active-DATA time-sample SNR; 16 × 1000-byte PSDUs/rate; known timing/rate; noisy L-LTF ZF, no payload fitting.",
        ha="center",
        fontsize=10,
    )
    fig.text(
        0.5,
        0.003,
        "Panel (b): complex128/double receivers. Panel (c): complex64 GRC FFT versus complex128 NumPy FFT; forward FFT without 1/N scaling.",
        ha="center",
        fontsize=9,
    )
    fig.subplots_adjust(bottom=0.21, top=0.83, wspace=0.34)
    save(fig, "wlan_cross_validation")

    fig, ax = plt.subplots(figsize=(13, 11))
    ax.set(xlim=(0, 13), ylim=(0, 11))
    ax.axis("off")
    rows = [
        (
            9.6,
            "awgn_symbol_benchmark.grc",
            ["Gray symbol source", "Complex AWGN +", "TX/RX symbol files"],
            "Executed: uncoded diagnostic. Python metrics + independent MATLAB score.",
        ),
        (
            7.6,
            "wlan_reference_channel.grc",
            ["WLAN reference IQ", "Complex AWGN +", "Raw IQ capture"],
            "Executed: all eight legacy rates. Offline Python EVM/pre-FEC BER; MATLAB post-FEC decode.",
        ),
        (
            5.6,
            "wlan_ofdm_fft.grc",
            ["DATA extraction", "CP removal", "64-point FFT", "Frequency-bin file"],
            "Executed: explicit native OFDM processing. Known schedule; output checked independently against NumPy.",
        ),
        (
            3.6,
            "usrp_wifi_tx.grc",
            ["WLAN reference IQ", "UHD USRP Sink"],
            "Compiled only. Finite TX reference; configure actual RF hardware before use.",
        ),
        (
            1.6,
            "usrp_wifi_rx.grc",
            ["UHD USRP Source", "Finite sample Head", "Raw IQ capture"],
            "Compiled only. Steering readiness and full capture metadata belong in the measurement runner.",
        ),
    ]
    for y, title, boxes, caption in rows:
        ax.text(0.3, y + 0.63, title, fontsize=12, fontweight="bold")
        width = 2.6 if len(boxes) == 4 else 3.3
        xpositions = np.linspace(0.4, 12.5 - width, len(boxes))
        for j, (x, text) in enumerate(zip(xpositions, boxes)):
            ax.add_patch(
                FancyBboxPatch(
                    (x, y - 0.15),
                    width,
                    0.65,
                    boxstyle="round,pad=.08",
                    facecolor="#eaf2f8",
                    edgecolor="#326a9b",
                )
            )
            ax.text(
                x + width / 2, y + 0.17, text, ha="center", va="center", fontsize=11
            )
            if j:
                previous = xpositions[j - 1] + width + 0.1
                ax.annotate(
                    "",
                    xy=(x - 0.1, y + 0.17),
                    xytext=(previous, y + 0.17),
                    arrowprops=dict(arrowstyle="->", lw=1.6, color="#326a9b"),
                )
        ax.text(0.4, y - 0.52, caption, fontsize=9, color="#444444")
    ax.text(
        0.3,
        10.7,
        "Figure 8. Supporting reference and UHD flowgraphs",
        fontsize=18,
        fontweight="bold",
    )
    ax.text(
        0.3,
        0.35,
        "Native editable .grc files are in grc/; generated Python is in grc/generated/. RF graphs have not been run.",
        fontsize=9,
    )
    save(fig, "flowgraph_overview")
    print("Wrote comparison charts and flowgraph overview (PNG/PDF/SVG)")


if __name__ == "__main__":
    main()
