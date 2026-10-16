"""Independent uncoded AWGN reference; see docs/THEORY.md, equations T1-T8.

These Gray constellations are a diagnostic mapping, not the WLAN on-air bit
mapping. Exact square-QAM BER integrates all PAM decision regions and weights
transitions by Hamming distance; it is not the nearest-neighbour approximation.
"""
from __future__ import annotations

import numpy as np
from scipy.special import ndtr
from scipy.stats import beta


ORDERS = (2, 4, 16, 64)


def bits_per_symbol(order: int) -> int:
    if order not in ORDERS:
        raise ValueError(f"Supported diagnostic constellation orders: {ORDERS}")
    return int(np.log2(order))


def _gray_decode(values):
    values = np.asarray(values, dtype=np.int64).copy()
    shift = 1
    while shift < 8:
        values ^= values >> shift
        shift *= 2
    return values


def constellation(order: int) -> np.ndarray:
    k = bits_per_symbol(order)
    if order == 2:
        return np.array([-1, 1], dtype=np.complex128)
    half = k // 2
    side = int(np.sqrt(order))
    labels = np.arange(order)
    levels_i = 2 * _gray_decode(labels >> half) - side + 1
    levels_q = 2 * _gray_decode(labels & (side - 1)) - side + 1
    return (levels_i + 1j * levels_q) / np.sqrt(2 * (order - 1) / 3)


def symbol_indices(order: int, symbols: np.ndarray) -> np.ndarray:
    k = bits_per_symbol(order)
    symbols = np.asarray(symbols).ravel()
    if not np.all(np.isfinite(symbols)):
        raise ValueError("Symbols must be finite")
    if order == 2:
        return (symbols.real >= 0).astype(np.int64)
    side = int(np.sqrt(order))
    scaled = symbols * np.sqrt(2 * (order - 1) / 3)
    i = np.clip(np.floor((scaled.real + side) / 2), 0, side - 1).astype(np.int64)
    q = np.clip(np.floor((scaled.imag + side) / 2), 0, side - 1).astype(np.int64)
    return ((i ^ (i >> 1)) << (k // 2)) | (q ^ (q >> 1))


def index_bits(indices, order: int) -> np.ndarray:
    k = bits_per_symbol(order)
    return ((np.asarray(indices, dtype=np.int64).ravel()[:, None]
             >> np.arange(k - 1, -1, -1)) & 1).astype(np.uint8).ravel()


def make_symbols(order=16, count=100000, seed=20261016) -> np.ndarray:
    if count <= 0:
        raise ValueError("count must be positive")
    rng = np.random.default_rng(seed)
    return constellation(order)[rng.integers(order, size=count)].astype(np.complex64)


def exact_ber(order: int, ebno_db) -> np.ndarray:
    """Coherent Gray BPSK/QPSK or exact square-QAM BER, uncoded AWGN."""
    k = bits_per_symbol(order)
    ebno = np.asarray(ebno_db, dtype=float)
    if not np.all(np.isfinite(ebno)):
        raise ValueError("Eb/N0 must be finite")
    gamma = 10 ** (ebno / 10)
    if order in (2, 4):
        return ndtr(-np.sqrt(2 * gamma))
    side = int(np.sqrt(order))
    width = k // 2
    levels = (2 * np.arange(side) - side + 1) / np.sqrt(2 * (order - 1) / 3)
    edges = np.r_[-np.inf, (levels[:-1] + levels[1:]) / 2, np.inf]
    gray = np.arange(side) ^ (np.arange(side) >> 1)
    distance = np.array([[(int(a) ^ int(b)).bit_count() for b in gray] for a in gray])
    output = np.empty(gamma.size)
    for n, value in enumerate(gamma.ravel()):
        sigma = np.sqrt(1 / (2 * k * value))
        lo = (edges[:-1][None, :] - levels[:, None]) / sigma
        hi = (edges[1:][None, :] - levels[:, None]) / sigma
        # Survival form avoids cancellation for positive-tail intervals.
        transition = np.where(lo > 0, ndtr(-lo) - ndtr(-hi), ndtr(hi) - ndtr(lo))
        output[n] = np.sum(transition * distance) / (side * width)
    return output.reshape(gamma.shape)


def binomial_interval(errors: int, count: int, confidence=0.95) -> tuple[float, float]:
    """Two-sided Clopper-Pearson interval; independent Bernoulli assumption."""
    if count <= 0 or not 0 <= errors <= count or not 0 < confidence < 1:
        raise ValueError("Require 0 <= errors <= count, count > 0, and 0 < confidence < 1")
    alpha = 1 - confidence
    lower = 0.0 if errors == 0 else beta.ppf(alpha / 2, errors, count - errors + 1)
    upper = 1.0 if errors == count else beta.ppf(1 - alpha / 2, errors + 1, count - errors)
    return float(lower), float(upper)


def zero_error_upper_bound(count: int, confidence=0.95) -> float:
    """One-sided bound, distinct from the two-sided interval above."""
    if count <= 0 or not 0 < confidence < 1:
        raise ValueError("Invalid count/confidence")
    return float(-np.expm1(np.log1p(-confidence) / count))


def score(reference_symbols, received_symbols, order: int) -> dict:
    """Score aligned symbols without fitting gain or phase to the payload."""
    reference = np.asarray(reference_symbols, dtype=np.complex128).ravel()
    received = np.asarray(received_symbols, dtype=np.complex128).ravel()
    if reference.size == 0 or reference.shape != received.shape:
        raise ValueError("Nonempty equally sized symbol vectors are required")
    if not np.all(np.isfinite(reference)) or not np.all(np.isfinite(received)):
        raise ValueError("Symbols must be finite")
    energy = float(np.sum(np.abs(reference) ** 2, dtype=np.float64))
    if energy == 0:
        raise ValueError("Reference energy must be nonzero")
    tx_bits = index_bits(symbol_indices(order, reference), order)
    rx_bits = index_bits(symbol_indices(order, received), order)
    errors = int(np.count_nonzero(tx_bits != rx_bits))
    error_energy = float(np.sum(np.abs(received - reference) ** 2, dtype=np.float64))
    evm = np.sqrt(error_energy / energy)
    lo, hi = binomial_interval(errors, tx_bits.size)
    return dict(order=order, symbols=int(reference.size), bits=int(tx_bits.size),
                errors=errors, ber=errors / tx_bits.size, ci95_lower=lo, ci95_upper=hi,
                evm_rms=float(evm), evm_percent=float(100 * evm),
                evm_db=float(20 * np.log10(evm)) if evm > 0 else None,
                error_energy=error_energy, reference_energy=energy)
