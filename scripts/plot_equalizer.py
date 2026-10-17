"""Four-stage eye and equalizer dashboards from captured GNU Radio samples."""

from pathlib import Path
import json
import numpy as np
from scipy.io import loadmat
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "results/equalizer_checks/16qam_noise_0.1"
data = loadmat(str(CASE) + ".mat", squeeze_me=True)
record = json.loads(Path(str(CASE) + ".json").read_text())
SPS = int(data["sample_rate_hz"] / data["symbol_rate_hz"])


def save(figure, name):
    for extension in ("png", "pdf", "svg"):
        figure.savefig(ROOT / "results" / f"{name}.{extension}", dpi=150)
    plt.close(figure)


# Raw waveforms are physical power waves; scale to RMS symbol units using
# the known TX setting/path. This is a reference conversion, not an RX fit.
points = np.ravel(data["constellation_points"])
rms = np.sqrt(np.mean(abs(points) ** 2))
tx_amplitude = 10 ** (float(data["tx_power_dbm"]) / 20)
path_amplitude = 10 ** (-float(data["path_loss_db"]) / 20)
stages = [
    ("TX: shaped waveform", data["tx_iq"] / tx_amplitude),
    (
        "RX: channel output, before timing / EQ",
        data["rx_iq"] / (tx_amplitude * path_amplitude),
    ),
    (
        "Middle: after timing, before EQ\nRRC reconstruction of 1-SPS symbols",
        data["middle_eye_waveform"] / rms,
    ),
    (
        "After LMS EQ\nRRC reconstruction of 1-SPS symbols",
        data["after_eye_waveform"] / rms,
    ),
]
for component in ("I", "Q"):
    figure, axes = plt.subplots(
        2, 2, figsize=(11, 9), layout="constrained", sharex=True, sharey=True
    )
    figure.suptitle(
        f"16-QAM {component} eyes | 1 Msymbol/s, 4 samples/symbol\nOne-symbol echo = 0.25 voltage ratio; normalized input noise = 0.10",
        fontsize=14,
    )
    for axis, (title, waveform) in zip(axes.flat, stages):
        samples = np.ravel(waveform)
        samples = samples.real if component == "I" else samples.imag
        # Display post-startup data, with two-symbol traces. The acquisition phase
        # differs by stage, so this is not an estimate of eye-opening metrics.
        start = 8192
        for offset in range(start, min(start + 800, len(samples) - 2 * SPS), SPS):
            axis.plot(
                np.arange(2 * SPS + 1) / SPS,
                samples[offset : offset + 2 * SPS + 1],
                color="#31688e",
                alpha=0.12,
                linewidth=0.8,
            )
        axis.set(
            title=title,
            xlabel="Time (symbol periods)",
            ylabel=f"{component} / RMS symbol amplitude",
            ylim=(-2, 2),
        )
        axis.grid(alpha=0.25)
    save(figure, f"equalizer_eyes_{component.lower()}")

figure, axes = plt.subplots(2, 2, figsize=(11, 9), layout="constrained")
figure.suptitle(
    "16-QAM adaptive LMS equalization | same echo test\nActual captured symbols and time-varying native equalizer taps",
    fontsize=14,
)
pre = np.ravel(data["pre_eq_symbols"])[1024:]
post = np.ravel(data["received_symbols"])[1024:]
for axis, samples, title, evm in [
    (axes[0, 0], pre, "Middle: before EQ", record["pre_reference_evm_percent"]),
    (axes[0, 1], post, "After adaptive LMS EQ", record["reference_evm_percent"]),
]:
    symbols = samples[:6000] / rms
    axis.scatter(symbols.real, symbols.imag, s=3, alpha=0.15, label="Captured symbols")
    axis.scatter(
        points.real / rms,
        points.imag / rms,
        c="black",
        marker="+",
        s=50,
        label="Ideal positions",
    )
    axis.set(
        title=f"{title} | data-aided RMS EVM {evm:.2f}%",
        xlabel="I / RMS symbol amplitude",
        ylabel="Q / RMS symbol amplitude",
        xlim=(-2, 2),
        ylim=(-2, 2),
    )
    axis.set_aspect("equal", adjustable="box")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
taps = np.asarray(data["eq_tap_history"])
axis = axes[1, 0]
for tap in range(taps.shape[1]):
    axis.plot(
        np.arange(len(taps)) / float(data["symbol_rate_hz"]) * 1000,
        abs(taps[:, tap]),
        label=str(tap),
    )
axis.set(
    title="Actual LMS tap magnitudes during acquisition",
    xlabel="Time since start (ms)",
    ylabel="Tap magnitude",
)
axis.legend(title="Tap index", ncol=4, fontsize=7)
axis.grid(alpha=0.25)
axis = axes[1, 1]
axis.bar(
    ["Before EQ", "After EQ"],
    [record["pre_reference_evm_percent"], record["reference_evm_percent"]],
    color=["#888888", "#31688e"],
)
axis.set(title="Data-aided EVM | after 1,024-symbol warmup", ylabel="RMS EVM (%)")
axis.grid(axis="y", alpha=0.25)
axis.set_axisbelow(True)
axis.text(
    0.5,
    0.88,
    f"Observed BER: {record['aligned_ber']:.3g}\n{record['compared_bits']:,} compared bits",
    transform=axis.transAxes,
    ha="center",
    fontsize=10,
)
save(figure, "equalizer_dashboard")
