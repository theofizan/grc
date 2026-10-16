"""Run complete finite Qt SISO graphs and archive a deterministic case matrix."""
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]


def main():
    env=os.environ.copy(); env['QT_QPA_PLATFORM']='offscreen'
    cases=[]
    def run(name,*arguments):
        print(name,flush=True)
        subprocess.run([sys.executable,str(ROOT/'scripts/run_live_case.py'),'--case-id',name,*arguments],
                       env=env,cwd=ROOT,check=True,timeout=45)
        report=json.loads((ROOT/'results/live/cases'/name/'metrics.json').read_text())
        cases.append(report)
        return report
    for order in (2,4,16,64):
        run(f'modem_{order}','--order',str(order),*(['--snapshot'] if order==16 else []))
    run('modem_16_loss6','--order','16','--path-loss-db','6')
    for rate in range(8):
        # No tracking needed in AWGN; this mode cross-validates native GRC DATA
        # against the independent WLAN Toolbox receiver on identical raw IQ.
        run(f'wlan_{rate}','--mode','wlan','--rate-index',str(rate),'--correct-cfo','0','--pilot-tracking','0')
    for rate in (0,2,4,6):
        for loss in (6,12,18):
            run(f'wlan_{rate}_loss{loss}','--mode','wlan','--rate-index',str(rate),'--path-loss-db',str(loss),
                '--correct-cfo','0','--pilot-tracking','0')
        clean=run(f'wlan_{rate}_clean','--mode','wlan','--rate-index',str(rate),'--snr-db','180')
        assert clean['ber']['errors']==0 and clean['evm']['evm_rms']<1e-5
        corrected=run(f'wlan_{rate}_impaired','--mode','wlan','--rate-index',str(rate),
            '--snr-db','35','--path-loss-db','3','--cfo-hz','20000','--channel-taps','1,0.2+0.15j,0,-0.1j',
            *(['--snapshot'] if rate==4 else []))
        assert corrected['evm']['evm_rms']<.08
    bad=run('wlan_4_uncorrected','--mode','wlan','--rate-index','4','--snr-db','35',
        '--path-loss-db','3','--cfo-hz','20000','--channel-taps','1,0.2+0.15j,0,-0.1j',
        '--correct-cfo','0','--pilot-tracking','0','--snapshot','--replay-capture',
        str(ROOT/'results/live/cases/wlan_4_impaired/capture.npz'))
    assert bad['ber']['ber']>.1 and bad['evm']['evm_rms']>.5
    manifest=dict(status='passed',cases=[r['case']['case_id'] for r in cases],
        number_of_cases=len(cases),tx_channels=1,rx_channels=1,
        gui_test='Actual Qt sinks and event loop; offscreen platform for finite automated tests',
        power='Wi-Fi PPDU active mean power=1 for every rate; fixed AWGN variance across path-loss sweeps',
        timing='known burst boundaries/rate/length; no autonomous acquisition',
        hardware_executed=False)
    (ROOT/'results/live/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Passed {len(cases)} complete Qt SISO cases')


if __name__=='__main__': main()
