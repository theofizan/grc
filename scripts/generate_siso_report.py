"""Write the primary readable report around the fixed-power SISO experiment."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'
RATES=[6,9,12,18,24,36,48,54]


def read(path): return json.loads((RESULTS/path).read_text())
def case(name): return read(f'live/cases/{name}/metrics.json')


def main():
    status=read('validation/status.json'); live=read('live/manifest.json'); matlab=read('live/matlab_validation.json')
    assert status['status']==live['status']==matlab['status']=='passed'
    out=[]
    def p(s=''): out.append(s+'\n')
    def table(head,rows):
        p('| '+' | '.join(head)+' |'); p('| '+' | '.join(['---']*len(head))+' |')
        for row in rows: p('| '+' | '.join(map(str,row))+' |')
        p()
    def fig(name,caption):
        p(f'![{caption.split(".")[0]}](live/figures/{name}.png)\n')
        p(caption+f' [PDF](live/figures/{name}.pdf) · [SVG](live/figures/{name}.svg).\n')
    p('# SISO antenna benchmark — results and operating guide\n')
    p(f'**Software validation: PASS · {live["number_of_cases"]} complete live-GRC cases · '
      f'{len(status["runs"])} command stages · one TX stream / one RX stream.** '
      f'Run completed {status["utc"]}. [Commands, versions and source hashes](validation/status.json).\n')
    p('This report focuses on the agreed **fixed-power SISO experiment**: transmit a repeatable waveform, '
      'change only the SISO channel/antenna condition, and calculate **pre-FEC BER, RMS EVM and received power**. '
      'All results below are simulations. No antenna or USRP RF measurement has yet been performed.\n')
    p('## Read the results\n')
    good=case('wlan_4_impaired'); bad=case('wlan_4_uncorrected')
    p(f'The in-graph modem counter agrees with coherent uncoded theory across BPSK, QPSK, 16-QAM and 64-QAM. '
      f'The Wi-Fi lab recovers all eight legacy rates with exact expected symbol and bit counts. '
      f'With a four-tap channel and 20 kHz CFO, the 16-QAM example reports '
      f'**{good["ber"]["errors"]}/{good["ber"]["bits"]} bit errors and {good["evm"]["evm_percent"]:.2f}% EVM**. '
      f'Replaying the identical received IQ with CFO/pilot corrections disabled gives '
      f'**BER {bad["ber"]["ber"]:.3f} and {bad["evm"]["evm_percent"]:.2f}% EVM**. '
      'This demonstrates why receiver corrections remain necessary even in a simplified measurement.\n')
    p('## Open the flowgraphs\n')
    p('From a new terminal in this folder:\n\n```sh\ncd /Users/ofi/repos/grc\n'
      'antenna-grc grc/siso_modem_lab.grc grc/siso_wlan_lab.grc\n```\n')
    p('Generate (**F5**), Execute (**F6**), Stop (**F7**). Settings are fixed per run; edit Parameter blocks and restart '
      'for a new condition. Zero counts mean continuous operation; positive counts make finite runs. '
      'The [detailed SISO guide](../docs/SISO_LABS.md) explains every block, parameter, view and output file.\n')
    table(['Graph','Use it for','Receiver assumption'],[
        ['[SISO modem lab](../grc/siso_modem_lab.grc)','Transparent bits → mapping → channel → hard decisions → BER/EVM','Symbol timing and scalar channel are known'],
        ['[SISO Wi-Fi lab](../grc/siso_wlan_lab.grc)','Actual OFDM bursts → FIR/CFO/AWGN → trained receiver → BER/EVM','Burst timing, rate and length are supplied; channel/CFO estimated from training']])
    fig('siso_flowgraphs','**Figure S1. The two complete SISO signal paths.** Both calculate BER/EVM inside GNU Radio. '
        'The first isolates mapping and counting. The second uses legacy Wi-Fi PHY bursts and training-based reception. '
        'There is no Wi-Fi networking/MAC, MIMO processing, acknowledgment or retry logic.')
    p('## Live displays and saved evidence\n')
    p('The running window has a metrics/constellation tab and separate TX and RX waveform tabs. Each waveform tab contains '
      'frequency, waterfall and I/Q time views. The numerical readouts are cumulative BER and pooled RMS EVM. '
      'The overlaid constellation distinguishes the recovered DATA symbols from the known reference points. '
      'Raw OFDM waveform samples are not mislabeled as decoded constellation symbols.\n')
    p('On Stop, exact integer errors/bits, EVM energies, configuration and recovered burst/CFO information are written '
      'to `results/live/siso_*_{ber,evm,receiver}.json` as applicable. These latest-session files are overwritten. '
      'The report instead reads archived [finite cases](live/manifest.json), each containing metrics and a MATLAB fixture; '
      'selected cases also retain raw/reference/equalized arrays in `capture.npz`.\n')
    fig('siso_dashboard','**Figure S2. Diagnostics from an actual finite execution of the generated SISO Wi-Fi GRC graph.** '
        '(a) Recovered 16-QAM DATA symbols and exact constellation points. (b) TX/RX Welch PSD at logical 20 Msps. '
        '(c) First 40 µs of the clean and received I waveform. (d) In-graph cumulative BER versus compared bits. '
        'Zero-error observations use nominal one-sided 95% upper limits. These are exported data plots, not GUI screenshots. '
        'PSD is relative power/Hz, not calibrated dBm/Hz; native Qt frequency displays use their own relative FFT-level scale.')
    p('## Modem calibration against theory\n')
    fig('siso_modem_theory','**Figure S3. Complete symbol-rate GRC modem versus theory.** '
        'Circles are in-graph measurements; crosses are exact uncoded BER and AWGN EVM predictions. '
        'Nominal BER confidence bars assume independent bits. Each case compares 100,000 symbols. '
        'TX nominal Es and TX-reference Eb/N0 remain fixed; the final 16-QAM case adds 6 dB loss. '
        'Noise variance varies with bits/symbol to hold Eb/N0 fixed across modulations; this is a diagnostic distinct from the Wi-Fi fixed-noise sweep.')
    modem_rows=[]
    for name in ('modem_2','modem_4','modem_16','modem_64','modem_16_loss6'):
        r=case(name); label={2:'BPSK',4:'QPSK',16:'16-QAM',64:'64-QAM'}[r['case']['order']]
        modem_rows.append([f'{label} / {r["case"]["path_loss_db"]:g} dB',f'{r["ber"]["errors"]}/{r["ber"]["bits"]}',
            f'{r["ber"]["ber"]:.6g}',f'{r["theory_ber"]:.6g}',f'{r["evm"]["evm_percent"]:.3f}'])
    table(['Modulation / loss','Errors / bits','GRC BER','Exact BER','RMS EVM (%)'],modem_rows)
    p('## Fixed power and the channel\n')
    p('In the Wi-Fi lab, **mean power over the complete active PPDU is exactly one**, separately for every rate. '
      'Idle zeros are excluded. The channel applies causal FIR taps, scalar attenuation and optional CFO, then adds complex AWGN. '
      'For the loss sweep, taps stay `[1]`, CFO stays zero, and noise variance stays **10^(-25/10)**. '
      'Only the scalar signal attenuation changes; the noise is never rescaled to hide the loss. '
      'With this flat path, nominal received active-PPDU SNR is `25 dB − path_loss_db`.\n')
    p('The `snr_db` label means **TX-reference active-PPDU power / noise power**. It differs from the older '
      'DATA-only SNR convention in the validation appendix. These normalized powers are not conducted watts or dBm. '
      'Hardware measurements still require TX power/headroom calibration at the radio port and fixed RX gain. '
      'An unchanged USRP gain setting alone does not prove equal transmitted average power across modulations.\n')
    fig('siso_fixed_power','**Figure S4. Fixed-power, fixed-noise SISO channel-loss sweep.** '
        'Colors/legends specify modulation, coding rate and PHY rate. Each point uses eight 1000-byte PHY bursts. '
        '(a) Mapped pre-FEC DATA BER; downward triangles represent nominal zero-error 95% upper limits, not measured nonzero BER. '
        '(b) Pooled DATA EVM after noisy L-LTF channel correction. Timing is supplied and CFO/pilot tracking is disabled '
        'for this AWGN-only comparison. These are simulated channel losses, not measured antenna steering angles.')
    sweep=[]
    for rate in (0,2,4,6):
        for loss in (0,6,12,18):
            r=case(f'wlan_{rate}'+(f'_loss{loss}' if loss else ''))
            b=r['ber']; sweep.append([RATES[rate],loss,f'{b["errors"]}/{b["bits"]}',f'{b["ber"]:.6g}',f'{r["evm"]["evm_percent"]:.3f}',f'{r["power"]["tx_active_mean"]:.6f}'])
    table(['Rate (Mb/s)','Channel loss (dB)','Errors / mapped bits','BER','RMS EVM (%)','Active TX power'],sweep)
    p('## Receiver controls and independent checks\n')
    fig('siso_receiver_controls','**Figure S5. Receiver correction control using identical recorded received IQ.** '
        'The disabled-corrections GRC run replays the enabled run’s stored waveform; an exact array comparison verifies this. '
        'Both use 16-QAM, a four-tap SISO channel, 20 kHz CFO, 3 dB attenuation and TX-reference SNR 35 dB. '
        'Axes have different scales. CFO is estimated from STF/LTF; common phase is estimated from pilots. '
        'No RX DATA reference fitting is used to lower EVM. Zero errors in the enabled case are a finite observation.')
    p(f'MATLAB independently checked **{matlab["cases"]}** cases with WLAN Toolbox hard bit labels and `comm.EVM`. '
      f'It independently recovered raw IQ for **{matlab["receiverCases"]}** flat AWGN/no-tracking cases. '
      f'Worst EVM difference: **{matlab["worstEvmDifference"]:.3g}**; worst receiver symbol difference: '
      f'**{matlab["worstReceiverSymbolDifference"]:.3g}**, against the 2e-6 complex64/double tolerance. '
      '[MATLAB result](live/matlab_validation.json). The older offline double-precision receiver check remains separately documented.\n')
    p('The current checks include exact finite counts, no channel sample loss, fixed active TX power, noise calibration, '
      'noiseless recovery, multipath/CFO recovery and a deliberately failing receiver control. Qt tests construct the actual '
      'GNU Radio plotting sinks and run their event loop with the **offscreen** backend; they are not hardware or performance-throughput tests.\n')
    p('## Installation finding and fix\n')
    p('Runtime GUI testing found a real **Qt 5 / Qt 6 Qwt mismatch**: the installed GNU Radio plotting module required Qt 5, '
      'but the selected Qwt build loaded Qt 6 and aborted. Qwt 6.3.0 was replaced with Qt 5 build `h4ff56cd_0` and pinned '
      'in radioconda’s `conda-meta/pinned`. No GNU Radio, UHD, NumPy or MATLAB version was changed. '
      '[Transaction plan](validation/qwt_qt5_plan.json), [installation log](validation/qwt_qt5_install.log). '
      'The installation check now constructs a real Qt constellation widget in a subprocess, catching this failure before the full suite. '
      '[Environment check](validation/install_check.json).\n')
    p('## What this establishes for the antenna paper\n')
    p('The simulated **SISO measurement chain** works, with traceable counts and independent validation. '
      'The antenna experiment can remain: **set beam → settle → capture a fixed block → calculate BER/EVM and received power**. '
      'Keep post-FEC/PER work as an optional baseline. The receiver currently knows burst boundaries, rate and length; '
      'it does not establish autonomous acquisition sensitivity, sample-clock tracking, USRP stream integrity, live steering, '
      'antenna gain or an IEEE conformance result. No measured antenna improvement is claimed.\n')
    p('For the first RF experiment, commission an attenuated cabled SISO link, then substitute reference antenna/AUT '
      'while holding conducted TX power, RX gain, waveform, geometry and polarization fixed. Record received power alongside '
      'BER/EVM and compare commanded beam direction with the actual measured radiation pattern. '
      '[Methods](../docs/PAPER_METHODS.md), [steering contract](../docs/WIFI_AND_STEERING.md).\n')
    p('## Baselines, data and citations\n')
    p('The [validation appendix](VALIDATION_APPENDIX.md) retains all eight earlier theory/reference figures, '
      'complete uncoded/coded tables and the current command-log index. '
      '[Mathematical definitions](../docs/THEORY.md), [reference traceability](../docs/REFERENCES.md), '
      '[BibTeX](../references.bib), [SISO lab guide](../docs/SISO_LABS.md).\n')
    p('Waveform and receiver references: [legacy non-HT configuration](https://www.mathworks.com/help/wlan/ref/wlannonhtconfig.html), '
      '[WLAN recovery and EVM symbols](https://www.mathworks.com/help/wlan/ref/wlannonhtdatarecover.html), '
      '[EVM normalization](https://www.mathworks.com/help/comm/ref/comm.evm-system-object.html), '
      '[GNU Radio Qt displays](https://wiki.gnuradio.org/index.php/QT_GUI). '
      'An experimental precedent for USRP EVM versus steering angle is '
      '[Cho et al., EuMC 2024](https://doi.org/10.23919/EuMC61614.2024.10732723); it does not validate this implementation.\n')
    p('### Every archived live case\n')
    table(['Case','Compared bits','Bit errors','BER','RMS EVM (%)','Evidence'],[
        [name,(r:=case(name))['ber']['bits'],r['ber']['errors'],f'{r["ber"]["ber"]:.6g}',f'{r["evm"]["evm_percent"]:.4f}',f'[JSON](live/cases/{name}/metrics.json)'] for name in live['cases']])
    (RESULTS/'REPORT.md').write_text(''.join(out))
    print('Wrote primary fixed-power SISO report; legacy numerical evidence retained in VALIDATION_APPENDIX.md')


if __name__=='__main__': main()
