"""Figures for the over-the-air campaign (results/n210_campaign/summary.csv)."""

import csv
import numpy as np
from scipy.spatial import cKDTree
from matplotlib.lines import Line2D
from matplotlib.ticker import LogLocator, MultipleLocator, NullFormatter

from ber_theory import BITS, coherent_gray_ber
from paper_style import (ROOT, SINGLE_COLUMN_IN, DOUBLE_COLUMN_IN, PROFILES, LABELS, COLORS,
                         MARKERS, LINESTYLES, MUTED, plt, save)

with (ROOT / "results/n210_campaign/summary.csv").open() as file:
    rows = [r for r in csv.DictReader(file)]
sweep = [r for r in rows if r["kind"] == "sweep" and r["synced"] == "True"]
for r in sweep:
    for key in ("bits", "errors", "ber", "ber_ci_low", "ber_ci_high", "rx_adc_dbfs", "mer_db",
                "tx_level_dbfs"):
        r[key] = float(r[key])


def natural_ask_ber(m, ebno_db, bits=4_000_000):
    """Coherent M-ASK with the stock natural (non-Gray) symbol order, no differential."""
    rng = np.random.default_rng(3)
    k = int(np.log2(m))
    points = np.arange(-(m - 1), m, 2, dtype=float)
    idx = rng.integers(0, m, bits // k)
    es = np.mean(points ** 2)
    out = []
    for e in np.atleast_1d(ebno_db):
        n0 = es / (k * 10 ** (e / 10))
        rx = points[idx] + np.sqrt(n0 / 2) * rng.standard_normal(idx.size)
        dec = cKDTree(points[:, None]).query(rx[:, None])[1]
        shifts = np.arange(k - 1, -1, -1)
        out.append(np.mean(((idx[:, None] >> shifts) & 1) != ((dec[:, None] >> shifts) & 1)))
    return np.array(out)


def reference_ber(profile, ebno_db):
    if profile in ("4ask", "8ask"):
        return natural_ask_ber(2 ** BITS[profile], ebno_db)
    return coherent_gray_ber(profile, ebno_db)


def log_axis(axis, low=1e-7):
    axis.set_yscale("log")
    axis.set_ylim(low, 1)
    axis.yaxis.set_major_locator(LogLocator(base=10, numticks=10))
    axis.yaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10), numticks=100))
    axis.yaxis.set_minor_formatter(NullFormatter())
    axis.grid(which="minor", alpha=0.35, linewidth=0.3)


def points(profile):
    return sorted((r for r in sweep if r["modulation"] == profile), key=lambda r: r["rx_adc_dbfs"])


def draw(axis, profile, x_of):
    data = points(profile)
    hit = [r for r in data if r["errors"] > 0]
    zero = [r for r in data if r["errors"] == 0]
    style = dict(color=COLORS[profile], marker=MARKERS[profile], markersize=3.5)
    if hit:
        ber = np.array([r["ber"] for r in hit])
        axis.errorbar([x_of(r) for r in hit], ber,
                      yerr=[ber - np.array([r["ber_ci_low"] for r in hit]),
                            np.array([r["ber_ci_high"] for r in hit]) - ber],
                      linestyle=LINESTYLES[profile], linewidth=0.9, elinewidth=0.6, capsize=1.5,
                      label=LABELS[profile], **style)
    if zero:
        axis.plot([x_of(r) for r in zero], [r["ber_ci_high"] for r in zero], linestyle="none",
                  markerfacecolor="white", **style)


# 1) BER versus received level at fixed RX gain.
figure, axis = plt.subplots(figsize=(SINGLE_COLUMN_IN, 3.0), layout="constrained")
for profile in PROFILES:
    draw(axis, profile, lambda r: r["rx_adc_dbfs"])
log_axis(axis)
axis.set(xlabel="Received level at the ADC (dBFS, fixed RX gain)", ylabel="Bit error ratio")
handles, labels = axis.get_legend_handles_labels()
handles.append(Line2D([], [], marker="o", linestyle="none", color=MUTED,
                      markerfacecolor="white", markersize=3.5))
labels.append("0 errors (95% bound)")
figure.legend(handles, labels, loc="outside upper center", ncol=4, columnspacing=0.9)
save(figure, "n210_ber_vs_level")

# 2) MER versus received level (radio linearity and receiver floor).
figure, axis = plt.subplots(figsize=(SINGLE_COLUMN_IN, 2.6), layout="constrained")
for profile in PROFILES:
    data = points(profile)
    axis.plot([r["rx_adc_dbfs"] for r in data], [r["mer_db"] for r in data],
              color=COLORS[profile], marker=MARKERS[profile], markersize=3.5,
              linestyle=LINESTYLES[profile], linewidth=0.9, label=LABELS[profile])
x = np.array([r["rx_adc_dbfs"] for r in sweep])
y = np.array([r["mer_db"] for r in sweep])
linear = (y > 8) & (y < 24)  # 1:1 region, above decision-error bias, below the floor
if linear.sum() >= 3:
    floor = np.median(x[linear] - y[linear])
    xs = np.linspace(x.min(), x.max(), 50)
    axis.plot(xs, xs - floor, color=MUTED, linewidth=0.8,
              label=f"1 dB/dB, noise floor {floor:.1f} dBFS")
axis.set(xlabel="Received level at the ADC (dBFS, fixed RX gain)", ylabel="MER (dB)")
axis.legend(ncol=2, fontsize=6.5, loc="upper left")
save(figure, "n210_mer_vs_level")

# 3) BER versus Eb/N0 estimated from MER, against theory for this receiver.
figure, axes = plt.subplots(2, 3, figsize=(DOUBLE_COLUMN_IN, 4.4), sharey=True,
                            layout="constrained")
for axis, profile in zip(axes.flat, PROFILES):
    data = points(profile)
    k = BITS[profile]
    if data:
        lo = min(r["mer_db"] for r in data) - 10 * np.log10(k) - 1
        hi = max(r["mer_db"] for r in data) - 10 * np.log10(k) + 1
        grid = np.linspace(max(lo, -2), min(hi, 24), 60)
        ref = reference_ber(profile, grid)
        if profile in ("4ask", "8ask"):  # simulated reference: hide the few-error tail
            ref = np.where(ref >= 2e-6, ref, np.nan)
        axis.plot(grid, ref, color=MUTED, linewidth=0.8, label="Theory, coherent, this mapping")
    draw(axis, profile, lambda r, k=k: r["mer_db"] - 10 * np.log10(k))
    axis.text(0.96, 0.95, LABELS[profile], transform=axis.transAxes, ha="right", va="top",
              fontweight="bold")
    log_axis(axis)
    axis.xaxis.set_major_locator(MultipleLocator(2))
for axis in axes[1]:
    axis.set_xlabel(r"$E_b/N_0$ estimate from MER (dB)")
for axis in axes[:, 0]:
    axis.set_ylabel("Bit error ratio")
axes[0, 0].legend(loc="lower left", fontsize=6.5)
save(figure, "n210_ber_vs_mer")
print("wrote n210_ber_vs_level, n210_mer_vs_level, n210_ber_vs_mer")
