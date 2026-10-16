"""Independent Python OFDM EVM/pre-FEC analysis for schedule-aligned captures."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.io import loadmat, savemat
from antenna_bench.wlan import recover_symbols, demap


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rate-index',type=int,default=2)
    parser.add_argument('--capture',type=Path)
    parser.add_argument('--sample-offset',type=int,default=0)
    parser.add_argument('--require-complete',action='store_true',
                        help='Assert exact finite reference length and no unavailable packets (software replay)')
    args=parser.parse_args()
    stem=f'wlan_rate_{args.rate_index}'
    capture=args.capture or ROOT/'results/grc'/f'{stem}_rx.c64'
    fixture=ROOT/'results/reference'/f'{stem}.mat'
    ref=loadmat(fixture,squeeze_me=True)
    samples=np.fromfile(capture,dtype='<c8').astype(np.complex128)
    if args.require_complete:
        expected_bytes=(ROOT/'results/reference'/f'{stem}_tx.c64').stat().st_size
        assert capture.stat().st_size==expected_bytes, 'Replay changed the finite sample count'
        assert args.sample_offset==0, 'Strict replay check requires zero sample offset'
    reference_symbols=ref['reference_symbols']; order=int(ref['order'])
    transmitted=demap(reference_symbols.ravel(order='F'),order)
    np.testing.assert_array_equal(transmitted,ref['reference_coded_bits'].ravel(order='F'))
    all_symbols=[]; rows=[]; error_energy=0; reference_energy=0; errors=0; bits=0; missing=0
    for n,start in enumerate(np.atleast_1d(ref['packet_starts'])):
        first=int(start)+args.sample_offset; last=first+ref['tx_packet'].size
        if first<0 or last>samples.size:
            missing+=1; continue
        eq=recover_symbols(samples[first:last],ref)
        recovered=demap(eq.ravel(order='F'),order)
        count=int(np.count_nonzero(recovered!=transmitted))
        energy=float(np.sum(abs(eq-reference_symbols)**2))
        ref_energy=float(np.sum(abs(reference_symbols)**2))
        errors+=count; bits+=transmitted.size; error_energy+=energy; reference_energy+=ref_energy
        all_symbols.append(eq)
        rows.append(dict(packet=n+1,coded_errors=count,coded_bits=int(transmitted.size),evm_rms=float(np.sqrt(energy/ref_energy))))
    if not bits:
        raise ValueError('No complete packets available')
    if args.require_complete:
        assert missing==0, 'Software replay lost expected packets'
    out=ROOT/'results/grc'/f'{stem}_python'
    report=dict(rate_index=args.rate_index,timing='known_schedule_and_rate',
        expected_packets=len(np.atleast_1d(ref['packet_starts'])),unavailable_packets=missing,
        capture_samples=int(samples.size),strict_finite_replay=args.require_complete,
        pre_fec_errors=errors,pre_fec_bits=bits,pre_fec_ber=errors/bits,
        pre_fec_scope='all transmitted mapped DATA bits including encoded SERVICE/tail/pad',
        evm_rms=float(np.sqrt(error_energy/reference_energy)),
        evm_correction='unsmoothed L-LTF ZF; no CFO/pilot tracking; no RX payload fit',
        capture_sha256=hashlib.sha256(capture.read_bytes()).hexdigest(),
        reference_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest())
    out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    with out.with_suffix('.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    savemat(str(out)+'_symbols.mat',{'python_eq':np.stack(all_symbols,axis=2),
                                  'python_evm':report['evm_rms']})
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
