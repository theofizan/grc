"""Figures for the BER-test validation (results/ber_tests/ber_validation.csv)."""

import csv
import numpy as np
from matplotlib.ticker import LogLocator, MultipleLocator, NullFormatter

from ber_theory import coherent_gray_ber
from paper_style import (ROOT, SINGLE_COLUMN_IN, DOUBLE_COLUMN_IN, PROFILES, LABELS, COLORS,
                         MARKERS, LINESTYLES, MUTED, plt, save)

with (ROOT / "results/ber_tests/ber_validation.csv").open() as file:
    rows = list(csv.DictReader(file))
for row in rows:
    for key in row:
        if key != "modulation" and row[key] not in ("True", "False", ""):
            row[key] = float(row[key])


def log_axis(axis, low=1e-7):
    axis.set_yscale("log")
    axis.set_ylim(low, 1)
    axis.yaxis.set_major_locator(LogLocator(base=10, numticks=10))
    axis.yaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10), numticks=100))
    axis.yaxis.set_minor_formatter(NullFormatter())
    axis.grid(which="minor", alpha=0.35, linewidth=0.3)


def series(profile):
    return [r for r in rows if r["modulation"] == profile]


figure, axes = plt.subplots(2, 3, figsize=(DOUBLE_COLUMN_IN, 4.6), sharey=True,
                            layout="constrained")
for axis, profile in zip(axes.flat, PROFILES):
    data = series(profile)
    e = np.array([r["ebno_db"] for r in data])
    fine = np.linspace(e.min() - 1, e.max() + 1, 200)
    axis.plot(fine, coherent_gray_ber(profile, fine), color=MUTED, linewidth=0.8,
              label="Coherent Gray theory")
    ref = [(r["ebno_db"], r["ideal_ber"]) for r in data if r["ideal_ber"] > 0]
    axis.plot(*zip(*ref), color=COLORS[profile], linestyle=(0, (2, 1.5)), linewidth=0.9,
              label="Ideal sync, same coding")
    hit = [r for r in data if r["errors"] > 0]
    ber = np.array([r["ber"] for r in hit])
    axis.errorbar([r["ebno_db"] for r in hit], ber,
                  yerr=[ber - np.array([r["ci_low"] for r in hit]),
                        np.array([r["ci_high"] for r in hit]) - ber],
                  linestyle="none", color=COLORS[profile], marker=MARKERS[profile],
                  markersize=3.5, elinewidth=0.6, capsize=1.5,
                  label="GRC BER test (95% CI)")
    zero = [r for r in data if r["errors"] == 0]
    if zero:
        axis.plot([r["ebno_db"] for r in zero], [r["ci_high"] for r in zero], linestyle="none",
                  color=COLORS[profile], marker=MARKERS[profile], markersize=3.5,
                  markerfacecolor="white", label="0 errors (95% bound)")
    axis.text(0.96, 0.95, LABELS[profile], transform=axis.transAxes, ha="right", va="top",
              fontweight="bold")
    log_axis(axis)
    axis.set_xlim(e.min() - 0.5, e.max() + 0.5)
    axis.xaxis.set_major_locator(MultipleLocator(2))
for axis in axes[1]:
    axis.set_xlabel(r"$E_b/N_0$ per uncoded bit (dB)")
for axis in axes[:, 0]:
    axis.set_ylabel("Bit error ratio")
handles, labels = [], []
for axis in axes.flat:
    for h, l in zip(*axis.get_legend_handles_labels()):
        if l not in labels:
            handles.append(h)
            labels.append(l)
figure.legend(handles, labels, loc="outside upper center", ncol=4, handlelength=2.2)
save(figure, "ber_test_validation")

import json  # noqa: E402

summary = json.loads((ROOT / "results/ber_tests/summary.json").read_text())
figure, axis = plt.subplots(figsize=(SINGLE_COLUMN_IN, 2.6), layout="constrained")
axis.axhline(0, color=MUTED, linewidth=0.8)
for profile in PROFILES:
    losses = summary["formats"][profile]["equivalent_loss_db_per_point"]
    axis.plot([float(e) for e in losses], list(losses.values()), color=COLORS[profile],
              marker=MARKERS[profile], markersize=3.5, linestyle=LINESTYLES[profile],
              linewidth=0.9, label=LABELS[profile])
axis.set(xlabel=r"$E_b/N_0$ per uncoded bit (dB)",
         ylabel="Loss vs ideal sync, same coding (dB)", ylim=(-0.2, 1.6))
axis.xaxis.set_major_locator(MultipleLocator(2))
axis.legend(ncol=3, loc="upper left", columnspacing=0.8)
save(figure, "ber_test_ratio")
print("wrote ber_test_validation and ber_test_ratio (equivalent loss)")
