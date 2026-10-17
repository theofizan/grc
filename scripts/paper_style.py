"""Shared publication style for every exported figure.

Sizes follow IEEE two-column layout (3.5 in single column, 7.16 in double
column). Fonts are serif (STIX, Times-compatible) and embedded as TrueType so
PDFs pass journal font checks. Series identity never relies on color alone:
each modulation has a fixed color (Okabe-Ito, colorblind-safe), marker, and
line style, so figures also read correctly in grayscale print.
"""

from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SINGLE_COLUMN_IN = 3.5
DOUBLE_COLUMN_IN = 7.16

PROFILES = ["bpsk", "qpsk", "8psk", "4ask", "8ask", "16qam"]
LABELS = {"bpsk": "BPSK", "qpsk": "QPSK", "8psk": "8-PSK", "4ask": "4-ASK",
          "8ask": "8-ASK", "16qam": "16-QAM"}
# Fixed order: color follows the modulation, never its rank in a plot.
COLORS = {"bpsk": "#0072B2", "qpsk": "#D55E00", "8psk": "#009E73",
          "4ask": "#CC79A7", "8ask": "#E69F00", "16qam": "#56B4E9"}
MARKERS = {"bpsk": "o", "qpsk": "s", "8psk": "^", "4ask": "D", "8ask": "v", "16qam": "P"}
LINESTYLES = {"bpsk": "-", "qpsk": "--", "8psk": "-.", "4ask": ":",
              "8ask": (0, (5, 1, 1, 1)), "16qam": (0, (3, 1, 1, 1, 1, 1))}
INK = "#222222"
MUTED = "#6b6b6b"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["STIXGeneral", "Times New Roman", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8,
    "axes.titlesize": 8,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "legend.frameon": False,
    "axes.linewidth": 0.6,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.top": True,
    "ytick.right": True,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.minor.width": 0.4,
    "ytick.minor.width": 0.4,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": "#d9d9d9",
    "grid.linewidth": 0.4,
    "lines.linewidth": 1.0,
    "lines.markersize": 4,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})


def save(figure, name, folder="results"):
    """Vector PDF/SVG for the manuscript, 600-dpi PNG for previews."""
    for extension in ("pdf", "svg", "png"):
        figure.savefig(ROOT / folder / f"{name}.{extension}")
    plt.close(figure)
