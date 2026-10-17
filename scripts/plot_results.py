"""Publication figures from actual GNU Radio captures; no fitted RX corrections.

Figures use the shared style in paper_style.py (IEEE column widths, embedded
serif fonts, colorblind-safe colors with redundant markers/line styles).
BER uncertainty is the exact Clopper-Pearson 95% interval. Points with zero
observed errors are drawn as open markers at their one-sided 95% upper bound.
"""

import csv
import json
import numpy as np
from scipy.io import loadmat
from scipy.special import erfc
from scipy.stats import beta
from matplotlib.patches import Circle
from matplotlib.lines import Line2D
from matplotlib.ticker import LogLocator, MultipleLocator, NullFormatter

from paper_style import (ROOT, SINGLE_COLUMN_IN, DOUBLE_COLUMN_IN, PROFILES, LABELS,
                         COLORS, MARKERS, LINESTYLES, MUTED, plt, save)

RESULTS = ROOT / "results"
BITS = {"bpsk": 1, "qpsk": 2, "8psk": 3, "4ask": 2, "8ask": 3, "16qam": 4}
ROLLOFF = 0.35
records = {p: json.loads((RESULTS / f"{p}_noise_0.3.json").read_text()) for p in PROFILES}


def clopper_pearson(errors, n, confidence=0.95):
    a = 1 - confidence
    low = 0.0 if errors == 0 else beta.ppf(a / 2, errors, n - errors + 1)
    high = 1.0 if errors == n else beta.ppf(1 - a / 2, errors + 1, n - errors)
    return low, high


def zero_error_bound(n, confidence=0.95):
    return 1 - (1 - confidence) ** (1 / n)  # ≈ 3/n


def q(x):
    return 0.5 * erfc(x / np.sqrt(2))


def coherent_gray_ber(profile, ebno_db):
    """Textbook coherent, Gray-coded, non-differential AWGN BER (reference only)."""
    g = 10 ** (np.asarray(ebno_db) / 10)
    k = BITS[profile]
    m = 2 ** k
    if profile in ("bpsk", "qpsk"):
        return q(np.sqrt(2 * g))
    if profile == "8psk":
        return 2 / k * q(np.sqrt(2 * k * g) * np.sin(np.pi / m))
    if profile in ("4ask", "8ask"):
        return 2 * (m - 1) / (m * k) * q(np.sqrt(6 * k * g / (m**2 - 1)))
    return 4 / k * (1 - 1 / np.sqrt(m)) * q(np.sqrt(3 * k * g / (m - 1)))


def read_rows(name):
    with (RESULTS / "ber_sweep" / name).open() as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        for key in row:
            if key != "modulation":
                row[key] = float(row[key])
    return rows


def log_axis(axis, low=1e-6):
    axis.set_yscale("log")
    axis.set_ylim(low, 1)
    axis.yaxis.set_major_locator(LogLocator(base=10, numticks=10))
    axis.yaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10), numticks=100))
    axis.yaxis.set_minor_formatter(NullFormatter())
    axis.grid(which="minor", alpha=0.35, linewidth=0.3)


def draw_measured(axis, rows, profile, connect=True, label=None):
    rows = [r for r in rows if r["modulation"] == profile]
    x = np.array([r["ebno_db"] for r in rows])
    errors = np.array([r["bit_errors"] for r in rows])
    n = np.array([r["compared_bits"] for r in rows])
    hit = errors > 0
    ber = errors[hit] / n[hit]
    bounds = np.array([clopper_pearson(e, m) for e, m in zip(errors[hit], n[hit])])
    style = dict(color=COLORS[profile], marker=MARKERS[profile], markersize=3.5,
                 markeredgewidth=0.6)
    axis.errorbar(x[hit], ber, yerr=[ber - bounds[:, 0], bounds[:, 1] - ber],
                  linestyle=LINESTYLES[profile] if connect else "none", linewidth=0.9,
                  elinewidth=0.6, capsize=1.5, label=label, **style)
    if (~hit).any():
        axis.plot(x[~hit], [zero_error_bound(m) for m in n[~hit]], linestyle="none",
                  markerfacecolor="white", **style)


# --- BER versus Eb/N0 ----------------------------------------------------------
measured = read_rows("ber_sweep.csv")
ideal = read_rows("ideal_reference.csv")
theory_x = np.linspace(0, 24, 241)

figure, axis = plt.subplots(figsize=(SINGLE_COLUMN_IN, 3.1), layout="constrained")
for profile in PROFILES:
    draw_measured(axis, measured, profile, label=LABELS[profile])
log_axis(axis)
axis.set(xlim=(0, 22), xlabel=r"$E_b/N_0$ per uncoded bit (dB)", ylabel="Bit error ratio")
handles, labels = axis.get_legend_handles_labels()
handles.append(Line2D([], [], marker="o", linestyle="none", color=MUTED,
                      markerfacecolor="white", markersize=3.5))
labels.append("0 errors (95% upper bound)")
axis.xaxis.set_major_locator(MultipleLocator(5))
axis.xaxis.set_minor_locator(MultipleLocator(1))
figure.legend(handles, labels, loc="outside upper center", ncol=4, handlelength=2.4,
              columnspacing=0.9)
save(figure, "ber_vs_ebno")

figure, axes = plt.subplots(2, 3, figsize=(DOUBLE_COLUMN_IN, 4.4), sharex=True, sharey=True,
                            layout="constrained")
for axis, profile in zip(axes.flat, PROFILES):
    axis.plot(theory_x, coherent_gray_ber(profile, theory_x), color=MUTED, linewidth=0.8,
              label="Coherent Gray theory")
    reference = [r for r in ideal if r["modulation"] == profile and r["bit_errors"] > 0]
    axis.plot([r["ebno_db"] for r in reference], [r["ber"] for r in reference],
              color=COLORS[profile], linestyle=(0, (2, 1.5)), linewidth=0.9,
              label="Ideal sync, same mapping + diff. coding")
    draw_measured(axis, measured, profile, connect=False, label="GNU Radio flowchart (95% CI)")
    axis.text(0.96, 0.95, LABELS[profile], transform=axis.transAxes, ha="right", va="top",
              fontweight="bold")
    log_axis(axis)
    axis.set_xlim(0, 22)
for axis in axes[1]:
    axis.set_xlabel(r"$E_b/N_0$ per uncoded bit (dB)")
for axis in axes[:, 0]:
    axis.set_ylabel("Bit error ratio")
    axis.xaxis.set_major_locator(MultipleLocator(5))
    axis.xaxis.set_minor_locator(MultipleLocator(1))
handles, labels = axes[0, 0].get_legend_handles_labels()
handles.append(Line2D([], [], marker="o", linestyle="none", color=MUTED,
                      markerfacecolor="white", markersize=3.5))
labels.append("0 errors (95% upper bound)")
figure.legend(handles, labels, loc="outside upper center", ncol=4, handlelength=2.4)
save(figure, "ber_vs_ebno_panels")

# --- Data-aided EVM versus Es/N0 against the AWGN prediction -------------------
figure, axis = plt.subplots(figsize=(SINGLE_COLUMN_IN, 2.6), layout="constrained")
esno = np.linspace(-2, 32, 200)
axis.plot(esno, 100 / np.sqrt(10 ** (esno / 10)), color=MUTED, linewidth=0.9,
          label=r"AWGN: $100/\sqrt{E_s/N_0}$")
for profile in PROFILES:
    rows = [r for r in measured if r["modulation"] == profile]
    axis.plot([r["ebno_db"] + 10 * np.log10(BITS[profile]) for r in rows],
              [r["data_aided_evm_percent"] for r in rows], linestyle="none",
              color=COLORS[profile], marker=MARKERS[profile], markersize=3.5,
              markerfacecolor="none", markeredgewidth=0.7, label=LABELS[profile])
axis.set_yscale("log")
axis.set(xlim=(-2, 32), ylim=(2, 200), xlabel=r"$E_s/N_0$ per symbol (dB)",
         ylabel="Data-aided RMS EVM (%)")
axis.legend(ncol=2, loc="upper right", columnspacing=1)
save(figure, "evm_vs_esno")

# --- Fixed receiver-noise comparison (single operating point) ------------------
noise_dbm = records["bpsk"]["rx_noise_dbm"]
figure, axis = plt.subplots(figsize=(SINGLE_COLUMN_IN, 2.4), layout="constrained")
x = np.arange(len(PROFILES))
for index, profile in enumerate(PROFILES):
    r = records[profile]
    n = r["compared_bits"]
    errors = int(round(r["display_ber_mean"] * n))
    if errors:
        low, high = clopper_pearson(errors, n)
        axis.errorbar(index, errors / n, yerr=[[errors / n - low], [high - errors / n]],
                      color=COLORS[profile], marker=MARKERS[profile], capsize=2,
                      elinewidth=0.7, markersize=4.5)
        axis.annotate(f"{errors / n:.2g}", (index, errors / n), xytext=(5, 0),
                      textcoords="offset points", va="center", fontsize=6.5)
    else:
        bound = zero_error_bound(n)
        axis.plot(index, bound, color=COLORS[profile], marker=MARKERS[profile],
                  markerfacecolor="white", markersize=4.5)
        axis.annotate(f"0 errors\n< {bound:.1g}", (index, bound), xytext=(0, 6),
                      textcoords="offset points", ha="center", fontsize=6)
log_axis(axis, 1e-6)
axis.set_ylim(1e-6, 1e-1)
axis.set_xticks(x, [LABELS[p] for p in PROFILES])
axis.set_xlim(-0.6, len(PROFILES) - 0.1)
axis.grid(axis="x", visible=False)
axis.set_ylabel("Bit error ratio")
save(figure, "ber_comparison")

figure, axis = plt.subplots(figsize=(SINGLE_COLUMN_IN, 2.2), layout="constrained")
values = [records[p]["reference_evm_percent"] for p in PROFILES]
bars = axis.bar(x, values, width=0.62, color=[COLORS[p] for p in PROFILES],
                edgecolor="white", linewidth=0.5)
axis.bar_label(bars, labels=[f"{v:.1f}" for v in values], padding=2, fontsize=6.5)
axis.set_xticks(x, [LABELS[p] for p in PROFILES])
axis.set(ylabel="Data-aided RMS EVM (%)", ylim=(0, max(values) * 1.18))
axis.grid(axis="x", visible=False)
save(figure, "evm_comparison")

figure, axis = plt.subplots(figsize=(SINGLE_COLUMN_IN, 2.2), layout="constrained")
snr = [records[p]["nominal_rx_snr_db"] for p in PROFILES]
ebno = [records[p]["nominal_rx_ebno_db"] for p in PROFILES]
axis.bar(x - 0.19, snr, 0.36, color="#9a9a9a", edgecolor="white", linewidth=0.5,
         label=r"SNR over $F_s$ = 4 MHz")
axis.bar(x + 0.19, ebno, 0.36, color="#0072B2", edgecolor="white", linewidth=0.5,
         hatch="////", label=r"$E_b/N_0$ per uncoded bit")
axis.set_xticks(x, [LABELS[p] for p in PROFILES])
axis.set(ylabel="Ratio (dB)", ylim=(0, max(ebno) * 1.25))
axis.grid(axis="x", visible=False)
axis.legend(loc="upper right", ncol=2)
save(figure, "rx_ratios")

# --- Gross data rate and spectral efficiency -----------------------------------
figure, axis = plt.subplots(figsize=(SINGLE_COLUMN_IN, 2.2), layout="constrained")
rates = [records[p]["gross_bit_rate_bps"] / 1e6 for p in PROFILES]
bars = axis.bar(x, rates, width=0.62, color=[COLORS[p] for p in PROFILES],
                edgecolor="white", linewidth=0.5)
axis.bar_label(bars, labels=[f"{r:g} Mbit/s\n{r / (1 + ROLLOFF):.2f} b/s/Hz" for r in rates],
               padding=2, fontsize=6)
axis.set_xticks(x, [LABELS[p] for p in PROFILES])
axis.set(ylabel="Gross uncoded rate (Mbit/s)", ylim=(0, 5.2))
axis.grid(axis="x", visible=False)
save(figure, "data_rate")
with (RESULTS / "data_rate.csv").open("w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["modulation", "bits_per_symbol", "symbol_rate_symbols_s",
                     "sample_rate_samples_s", "gross_bit_rate_bps", "ideal_rrc_bandwidth_hz",
                     "spectral_efficiency_bps_per_hz"])
    for profile in PROFILES:
        r = records[profile]
        writer.writerow([LABELS[profile], BITS[profile], r["symbol_rate_hz"], r["sample_rate_hz"],
                         r["gross_bit_rate_bps"], (1 + ROLLOFF) * r["symbol_rate_hz"],
                         round(BITS[profile] / (1 + ROLLOFF), 4)])

# --- Constellations -----------------------------------------------------------


def constellation(axis, profile, is_rx, legend=False):
    data = loadmat(RESULTS / f"{profile}_noise_0.3.mat", squeeze_me=True)
    points = np.ravel(data["constellation_points"]).astype(complex)
    rms = np.sqrt(np.mean(abs(points) ** 2))
    points /= rms
    key = "aligned_rx_symbols" if is_rx else "tx_symbols"
    symbols = np.ravel(data[key])[:6000] / rms
    axis.scatter(symbols.real, symbols.imag, s=1.2, color=COLORS[profile], alpha=0.25,
                 linewidths=0, rasterized=True, label="Received" if is_rx else "Transmitted")
    axis.scatter(points.real, points.imag, marker="+", s=28, color="black", linewidths=0.8,
                 zorder=4, label="Ideal")
    if is_rx:
        measured_evm = records[profile]["reference_evm_percent"] / 100
        for index, point in enumerate(points):
            axis.add_patch(Circle((point.real, point.imag), measured_evm, fill=False,
                                  color="black", linewidth=0.5, linestyle=(0, (2, 1.5)),
                                  label="RMS error radius" if index == 0 else None))
    limit = max(abs(points.real).max(), abs(points.imag).max()) + 0.45
    axis.set(xlim=(-limit, limit), ylim=(-limit, limit))
    axis.set_aspect("equal", adjustable="box")
    if legend:
        axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, markerscale=2.5)


for profile in PROFILES:
    for is_rx in (False, True):
        figure, axis = plt.subplots(figsize=(SINGLE_COLUMN_IN, SINGLE_COLUMN_IN),
                                    layout="constrained")
        constellation(axis, profile, is_rx, legend=True)
        axis.set(xlabel="In-phase / RMS symbol amplitude",
                 ylabel="Quadrature / RMS symbol amplitude")
        save(figure, f'{profile}_{"rx" if is_rx else "tx"}_constellation')

figure, axes = plt.subplots(2, 3, figsize=(DOUBLE_COLUMN_IN, 4.9), layout="constrained")
for axis, profile in zip(axes.flat, PROFILES):
    constellation(axis, profile, True)
    r = records[profile]
    axis.set_title(f"{LABELS[profile]}:  $E_b/N_0$ = {r['nominal_rx_ebno_db']:.1f} dB, "
                   f"EVM = {r['reference_evm_percent']:.1f}%")
for axis in axes[1]:
    axis.set_xlabel("In-phase / RMS amplitude")
for axis in axes[:, 0]:
    axis.set_ylabel("Quadrature / RMS amplitude")
save(figure, "constellation_grid")
