"""BER reference curves shared by the plotting and validation scripts."""

import numpy as np
from scipy.special import erfc
from scipy.stats import beta

BITS = {"bpsk": 1, "qpsk": 2, "8psk": 3, "4ask": 2, "8ask": 3, "16qam": 4}


def q(x):
    return 0.5 * erfc(x / np.sqrt(2))


def coherent_gray_ber(profile, ebno_db):
    """Textbook coherent, Gray-coded, non-differential AWGN BER (reference only)."""
    g = 10 ** (np.asarray(ebno_db, dtype=float) / 10)
    k = BITS[profile]
    m = 2 ** k
    if profile in ("bpsk", "qpsk"):
        return q(np.sqrt(2 * g))
    if profile == "8psk":
        return 2 / k * q(np.sqrt(2 * k * g) * np.sin(np.pi / m))
    if profile in ("4ask", "8ask"):
        return 2 * (m - 1) / (m * k) * q(np.sqrt(6 * k * g / (m**2 - 1)))
    return 4 / k * (1 - 1 / np.sqrt(m)) * q(np.sqrt(3 * k * g / (m - 1)))


def clopper_pearson(errors, n, confidence=0.95):
    a = 1 - confidence
    low = 0.0 if errors == 0 else float(beta.ppf(a / 2, errors, n - errors + 1))
    high = 1.0 if errors == n else float(beta.ppf(1 - a / 2, errors + 1, n - errors))
    return low, high


def ebno_at_ber(ebno_db, ber, target):
    """Eb/N0 where a measured curve crosses `target` (log-linear interpolation)."""
    pairs = [(e, b) for e, b in zip(ebno_db, ber) if b > 0]
    for (e0, b0), (e1, b1) in zip(pairs, pairs[1:]):
        if b0 >= target >= b1 and b0 != b1:
            t = (np.log10(target) - np.log10(b0)) / (np.log10(b1) - np.log10(b0))
            return float(e0 + t * (e1 - e0))
    return None
