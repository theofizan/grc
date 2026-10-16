"""Schedule-assisted legacy OFDM metric receiver, not an autonomous WLAN PHY.

Uses known packet boundaries and rate/length from reference metadata, L-LTF
channel estimation, CP removal and FFT, and no payload fitting. CFO/pilot
tracking is deliberately absent in the AWGN cross-check. See docs/THEORY.md.
"""
import numpy as np
from antenna_bench.math import bits_per_symbol, index_bits

ACTIVE = np.r_[np.arange(-26, 0), np.arange(1, 27)]
PILOTS = np.array([-21, -7, 7, 21])
DATA = np.array([value for value in ACTIVE if value not in PILOTS])


def wlan_constellation(order):
    """IEEE 802.11a-1999 Tables 82-85, b0 first, I bits then Q bits."""
    k = bits_per_symbol(order)
    if order == 2:
        return np.array([-1, 1], dtype=complex)
    axis = np.array({4: [-1, 1], 16: [-3, -1, 3, 1],
                     64: [-7, -5, -1, -3, 7, 5, 1, 3]}[order])
    labels = np.arange(order)
    i = axis[labels >> (k // 2)]
    q = axis[labels & (len(axis) - 1)]
    return (i + 1j * q) / np.sqrt({4:2, 16:10, 64:42}[order])


def demap(symbols, order):
    points = wlan_constellation(order)
    index = np.argmin(abs(np.asarray(symbols).ravel()[:, None] - points[None, :])**2, axis=1)
    return index_bits(index, order)


def recover_symbols(packet, reference):
    """Return equalized DATA tones using only the known training field for H."""
    tx = np.asarray(reference['tx_packet']).ravel()
    packet = np.asarray(packet).ravel()
    ltf = int(reference['ltf_start'])
    data = int(reference['data_start']); length = int(reference['data_length'])
    if packet.size != tx.size:
        raise ValueError('Require a complete, schedule-aligned packet')
    # L-LTF is 32 sample guard then two identical 64-sample training symbols.
    tx_training = np.fft.fft(tx[ltf+32:ltf+160].reshape(2,64), axis=1).mean(axis=0)
    rx_training = np.fft.fft(packet[ltf+32:ltf+160].reshape(2,64), axis=1).mean(axis=0)
    channel = rx_training[DATA % 64] / tx_training[DATA % 64]
    if np.any(abs(channel) < 1e-12):
        raise ValueError('Channel null prevents stable ZF scoring')
    tx_grid = np.fft.fft(tx[data:data+length].reshape(-1,80)[:,16:],axis=1)[:,DATA % 64].T
    rx_grid = np.fft.fft(packet[data:data+length].reshape(-1,80)[:,16:],axis=1)[:,DATA % 64].T
    ideal = reference['reference_symbols']
    # Fixed TX normalization from the exported clean waveform, never RX payload.
    scale = np.mean(tx_grid / ideal)
    if np.max(abs(tx_grid / ideal - scale)) > 1e-6:
        raise ValueError('Unexpected reference FFT/mapping normalization')
    return rx_grid / channel[:,None] / scale
