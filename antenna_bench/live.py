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


def parse_taps(value='1+0j'):
    taps=np.asarray(ast.literal_eval('['+value+']'),dtype=complex)
    if taps.size<1 or taps.size>16 or not np.all(np.isfinite(taps)) or not np.any(abs(taps)>0):
        raise ValueError('Use 1..16 finite causal SISO taps, at least one nonzero')
    return taps.tolist()


def test_bits(order=16, count=16384, seed=20261016):
    return index_bits(np.random.default_rng(seed).integers(order, size=count), order)


@lru_cache(maxsize=8)
def wlan_reference(rate_index=2):
    ref=loadmat(ROOT/'results/reference'/f'wlan_rate_{int(rate_index)}.mat', squeeze_me=True)
    # Fixed average power DURING the complete active PPDU, at every rate.
    # Idle zeros do not define the transmitted burst power.
    ref['tx_packet']=np.asarray(ref['tx_packet'],dtype=complex).ravel().copy()
    ref['tx_packet']/=np.sqrt(np.mean(abs(ref['tx_packet'])**2))
    return ref


def burst_waveform(rate_index=2, idle_samples=2000):
    return np.r_[wlan_reference(rate_index)['tx_packet'],np.zeros(int(idle_samples))].astype(np.complex64)


def reference_symbols(rate_index=2):
    return wlan_reference(rate_index)['reference_symbols'].ravel(order='F').astype(np.complex64)


def recover_burst(packet, reference, correct_cfo=True, pilot_tracking=True):
    """Known-boundary SISO reception: STF/LTF CFO, LTF ZF, pilot common phase.

    Pilot expectations and training come from the clean TX fixture. Receiver
    normalization uses that fixture and training only, never fitted RX payload.
    """
    rx=np.asarray(packet,dtype=complex).copy()
    tx=reference['tx_packet']; fs=float(reference['fs']); ltf=int(reference['ltf_start'])
    start=int(reference['data_start']); length=int(reference['data_length'])
    if rx.shape != tx.shape: raise ValueError('One complete known-boundary burst is required')
    frequency=0.0
    if correct_cfo:
        stf=rx[32:160]
        coarse=np.angle(np.vdot(stf[:-16],stf[16:]))*fs/(2*np.pi*16)
        rx*=np.exp(-2j*np.pi*coarse*np.arange(rx.size)/fs)
        fine=np.angle(np.vdot(rx[ltf+32:ltf+96],rx[ltf+96:ltf+160]))*fs/(2*np.pi*64)
        rx*=np.exp(-2j*np.pi*fine*np.arange(rx.size)/fs)
        frequency=float(coarse+fine)
    tx_ltf=np.fft.fft(tx[ltf+32:ltf+160].reshape(2,64),axis=1).mean(axis=0)
    rx_ltf=np.fft.fft(rx[ltf+32:ltf+160].reshape(2,64),axis=1).mean(axis=0)
    channel=rx_ltf[ACTIVE%64]/tx_ltf[ACTIVE%64]
    if not np.all(np.isfinite(channel)) or np.any(abs(channel)<1e-12):
        raise ValueError('Training estimate has an unusable channel null')
    full_channel=np.ones(64,dtype=complex); full_channel[ACTIVE%64]=channel
    rx_grid=np.fft.fft(rx[start:start+length].reshape(-1,80)[:,16:],axis=1).T
    tx_grid=np.fft.fft(tx[start:start+length].reshape(-1,80)[:,16:],axis=1).T
    equalized=rx_grid/full_channel[:,None]
    if pilot_tracking:
        phase=np.angle(np.sum(equalized[PILOTS%64]*np.conj(tx_grid[PILOTS%64]),axis=0))
        equalized*=np.exp(-1j*phase)[None,:]
    scale=np.mean(tx_grid[DATA%64]/reference['reference_symbols'])
    return equalized[DATA%64]/scale, frequency
