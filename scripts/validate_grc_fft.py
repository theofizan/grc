"""Verify native GRC CP removal/FFT against NumPy on the same IQ samples."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rate-index',type=int,default=2)
    args=parser.parse_args(); stem=f'wlan_rate_{args.rate_index}'
    reference=loadmat(ROOT/'results/reference'/f'{stem}.mat',squeeze_me=True)
    raw=np.fromfile(ROOT/'results/grc'/f'{stem}_rx.c64',dtype='<c8').astype(complex)
    actual=np.fromfile(ROOT/'results/grc'/f'{stem}_fft.c64',dtype='<c8').reshape(-1,64).astype(complex)
    expected=[]
    for first in np.atleast_1d(reference['packet_starts']):
        start=int(first)+int(reference['data_start']); length=int(reference['data_length'])
        data=raw[start:start+length].reshape(-1,80)[:,16:]
        expected.append(np.fft.fft(data,axis=1))
    expected=np.concatenate(expected)
    np.testing.assert_allclose(actual,expected,atol=2e-6,rtol=2e-5)
    report=dict(status='passed',rate_index=args.rate_index,vectors=int(actual.shape[0]),
        max_absolute_error=float(np.max(abs(actual-expected))),
        relative_l2_error=float(np.linalg.norm(actual-expected)/np.linalg.norm(expected)),
        precision='GRC complex64 FFT vs NumPy complex128 FFT on the same complex64 input')
    (ROOT/'results/grc'/f'{stem}_fft_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
