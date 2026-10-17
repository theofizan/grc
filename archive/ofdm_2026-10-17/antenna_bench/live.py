"""SISO live-lab references and training-only OFDM recovery.

The Wi-Fi lab uses fixed burst boundaries/rate, not packet discovery or a MAC.
No channel gain is fitted to received DATA symbols. See docs/SISO_LABS.md.
"""

from functools import lru_cache
import ast
import numpy as np
from scipy.io import loadmat
from antenna_bench.paths import ROOT
from antenna_bench.math import index_bits
from antenna_bench.wlan import ACTIVE, DATA, PILOTS


def parse_taps(value="1+0j"):
    """Read comma-separated causal voltage taps, e.g. '1, 0.2+0.15j'."""
    taps = np.asarray(ast.literal_eval("[" + value + "]"), dtype=complex)
    if (
        taps.size < 1
        or taps.size > 16
        or not np.all(np.isfinite(taps))
        or not np.any(abs(taps) > 0)
    ):
        raise ValueError("Use 1..16 finite causal SISO taps, at least one nonzero")
    return taps.tolist()


def test_bits(order=16, count=16384, seed=20261016):
    """Make repeatable 0/1 bytes: count symbols times log2(order) bits."""
    return index_bits(np.random.default_rng(seed).integers(order, size=count), order)


@lru_cache(maxsize=8)
def wlan_reference(rate_index=2):
    """Load one rate and normalize mean active-burst power to one."""
    ref = loadmat(
        ROOT / "results/reference" / f"wlan_rate_{int(rate_index)}.mat", squeeze_me=True
    )
    # Fixed average power DURING the complete active PPDU, at every rate.
    # Idle zeros do not define the transmitted burst power.
    ref["tx_packet"] = np.asarray(ref["tx_packet"], dtype=complex).ravel().copy()
    ref["tx_packet"] /= np.sqrt(np.mean(abs(ref["tx_packet"]) ** 2))
    return ref


def burst_waveform(rate_index=2, idle_samples=2000):
    """Return one active burst followed by idle_samples complex zeros."""
    return np.r_[
        wlan_reference(rate_index)["tx_packet"], np.zeros(int(idle_samples))
    ].astype(np.complex64)


def reference_symbols(rate_index=2):
    """Flatten known DATA symbols in transmission order for EVM/BER."""
    return (
        wlan_reference(rate_index)["reference_symbols"]
        .ravel(order="F")
        .astype(np.complex64)
    )


def recover_burst(packet, reference, correct_cfo=True, pilot_tracking=True):
    """Known-boundary SISO reception: STF/LTF CFO, LTF ZF, pilot common phase.

    Pilot expectations and training come from the clean TX fixture. Receiver
    normalization uses that fixture and training only, never fitted RX payload.
    """
    # 1. Read the known burst boundaries. Indices are samples; fs is in Hz.
    received = np.asarray(packet, dtype=complex).copy()
    transmitted = reference["tx_packet"]
    sample_rate_hz = float(reference["fs"])
    training_start = int(reference["ltf_start"])
    data_start = int(reference["data_start"])
    data_length = int(reference["data_length"])
    if received.shape != transmitted.shape:
        raise ValueError("One complete known-boundary burst is required")

    # 2. Remove carrier offset using repeated training sequences.
    # STF repetition: 16 samples. LTF repetition: 64 samples.
    # Phase difference / elapsed time gives the offset in Hz.
    estimated_cfo_hz = 0.0
    if correct_cfo:
        short_training = received[32:160]
        coarse_cfo_hz = (
            np.angle(np.vdot(short_training[:-16], short_training[16:]))
            * sample_rate_hz
            / (2 * np.pi * 16)
        )
        received *= np.exp(
            -2j * np.pi * coarse_cfo_hz * np.arange(received.size) / sample_rate_hz
        )
        first_ltf = received[training_start + 32 : training_start + 96]
        second_ltf = received[training_start + 96 : training_start + 160]
        fine_cfo_hz = (
            np.angle(np.vdot(first_ltf, second_ltf)) * sample_rate_hz / (2 * np.pi * 64)
        )
        received *= np.exp(
            -2j * np.pi * fine_cfo_hz * np.arange(received.size) / sample_rate_hz
        )
        estimated_cfo_hz = float(coarse_cfo_hz + fine_cfo_hz)

    # 3. Estimate H[k] = received LTF / transmitted LTF on active tones.
    # LTF contains a 32-sample guard followed by two 64-sample symbols.
    tx_training_fft = np.fft.fft(
        transmitted[training_start + 32 : training_start + 160].reshape(2, 64), axis=1
    ).mean(axis=0)
    rx_training_fft = np.fft.fft(
        received[training_start + 32 : training_start + 160].reshape(2, 64), axis=1
    ).mean(axis=0)
    channel_estimate = rx_training_fft[ACTIVE % 64] / tx_training_fft[ACTIVE % 64]
    if not np.all(np.isfinite(channel_estimate)) or np.any(
        abs(channel_estimate) < 1e-12
    ):
        raise ValueError("Training estimate has an unusable channel null")
    channel_all_bins = np.ones(64, dtype=complex)
    channel_all_bins[ACTIVE % 64] = channel_estimate

    # 4. Each DATA symbol is 80 samples: remove 16 CP samples, FFT 64.
    # Rows in the resulting grid are subcarriers; columns are OFDM symbols.
    rx_grid = np.fft.fft(
        received[data_start : data_start + data_length].reshape(-1, 80)[:, 16:], axis=1
    ).T
    tx_grid = np.fft.fft(
        transmitted[data_start : data_start + data_length].reshape(-1, 80)[:, 16:],
        axis=1,
    ).T
    equalized = rx_grid / channel_all_bins[:, None]

    # 5. Correct residual common phase using the four known pilot tones.
    if pilot_tracking:
        pilot_phase_rad = np.angle(
            np.sum(equalized[PILOTS % 64] * np.conj(tx_grid[PILOTS % 64]), axis=0)
        )
        equalized *= np.exp(-1j * pilot_phase_rad)[None, :]

    # 6. Restore the known TX constellation scale and keep DATA tones only.
    # This scale comes from clean TX samples, never a fit to received DATA.
    tx_constellation_scale = np.mean(
        tx_grid[DATA % 64] / reference["reference_symbols"]
    )
    return equalized[DATA % 64] / tx_constellation_scale, estimated_cfo_hz
