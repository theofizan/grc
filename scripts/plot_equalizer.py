"""Four-stage eye and equalizer dashboards from captured GNU Radio samples."""

from pathlib import Path
import json
import numpy as np
from scipy.io import loadmat
from paper_style import ROOT, DOUBLE_COLUMN_IN, COLORS, MUTED, plt, save

CASE = ROOT / "results/equalizer_checks/16qam_noise_0.1"
data = loadmat(str(CASE) + ".mat", squeeze_me=True)
record = json.loads(Path(str(CASE) + ".json").read_text())
SPS = int(data["sample_rate_hz"] / data["symbol_rate_hz"])


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
        2, 2, figsize=(DOUBLE_COLUMN_IN, 4.6), layout="constrained", sharex=True, sharey=True
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
                color=COLORS["16qam"],
                alpha=0.15,
                linewidth=0.5,
                rasterized=True,
            )
        axis.set(
            title=title,
            xlabel="Time (symbol periods)",
            ylabel=f"{component} / RMS symbol amplitude",
            ylim=(-2, 2),
        )
        axis.grid(alpha=0.25)
    save(figure, f"equalizer_eyes_{component.lower()}")

figure, axes = plt.subplots(2, 2, figsize=(DOUBLE_COLUMN_IN, 6.2), layout="constrained")
pre = np.ravel(data["pre_eq_symbols"])[1024:]
post = np.ravel(data["received_symbols"])[1024:]
for axis, samples, title, evm in [
    (axes[0, 0], pre, "Middle: before EQ", record["pre_reference_evm_percent"]),
    (axes[0, 1], post, "After adaptive LMS EQ", record["reference_evm_percent"]),
]:
    symbols = samples[:6000] / rms
    axis.scatter(symbols.real, symbols.imag, s=1.2, alpha=0.25, linewidths=0,
                 color=COLORS["16qam"], rasterized=True, label="Captured symbols")
    axis.scatter(
        points.real / rms,
        points.imag / rms,
        c="black",
        marker="+",
        s=28,
        linewidths=0.8,
        label="Ideal positions",
    )
    axis.set(
        title=f"{title}: data-aided RMS EVM {evm:.2f}%",
        xlabel="I / RMS symbol amplitude",
        ylabel="Q / RMS symbol amplitude",
        xlim=(-2, 2),
        ylim=(-2, 2),
    )
    axis.set_aspect("equal", adjustable="box")
    axis.legend(loc="upper right", markerscale=2.5)
taps = np.asarray(data["eq_tap_history"])
axis = axes[1, 0]
# Only the taps that move visibly get their own color; the rest stay muted.
magnitudes = abs(taps)
moving = np.argsort(magnitudes[-1])[::-1][:3]
palette = [COLORS["bpsk"], COLORS["qpsk"], COLORS["8psk"]]
time_ms = np.arange(len(taps)) / float(data["symbol_rate_hz"]) * 1000
for tap in range(taps.shape[1]):
    if tap in moving:
        index = list(moving).index(tap)
        axis.plot(time_ms, magnitudes[:, tap], color=palette[index], linewidth=1.0,
                  label=f"Tap {tap}")
    else:
        axis.plot(time_ms, magnitudes[:, tap], color=MUTED, linewidth=0.5, alpha=0.6,
                  label="Other taps" if tap == min(set(range(taps.shape[1])) - set(moving)) else None)
axis.set(
    title="Actual LMS tap magnitudes during acquisition",
    xlabel="Time since start (ms)",
    ylabel="Tap magnitude",
)
axis.legend(loc="center right")
axis = axes[1, 1]
axis.bar(
    ["Before EQ", "After EQ"],
    [record["pre_reference_evm_percent"], record["reference_evm_percent"]],
    color=["#9a9a9a", COLORS["16qam"]],
    width=0.55,
)
axis.set(title="Data-aided EVM | after 1,024-symbol warmup", ylabel="RMS EVM (%)")
axis.grid(axis="x", visible=False)
axis.text(
    0.75,
    0.95,
    f"Observed BER: {record['aligned_ber']:.3g}\n{record['compared_bits']:,} compared bits",
    transform=axis.transAxes,
    ha="center",
    va="top",
)
save(figure, "equalizer_dashboard")
