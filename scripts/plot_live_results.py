"""Publication-quality SISO lab figures generated from actual GRC captures."""
import json
from pathlib import Path
import numpy as np
from scipy.signal import welch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch
from antenna_bench.wlan import wlan_constellation
ROOT=Path(__file__).resolve().parents[1]
COLORS=('#0072BD','#D95319','#33994D','#7E2F8E')
LABELS=('BPSK 1/2 · 6 Mb/s','QPSK 1/2 · 12 Mb/s','16-QAM 1/2 · 24 Mb/s','64-QAM 2/3 · 48 Mb/s')


def case(name): return json.loads((ROOT/'results/live/cases'/name/'metrics.json').read_text())


def save(fig,name):
    dest=ROOT/'results/live/figures'; dest.mkdir(parents=True,exist_ok=True)
    for ext in ('png','pdf','svg'): fig.savefig(dest/f'{name}.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)


def main():
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(14,6)); ax.axis('off'); ax.set(xlim=(0,14),ylim=(0,6))
    chains=[(4.5,'siso_modem_lab.grc',['Known bits','Pack / map','Flat loss + AWGN','Known-gain correction','Decisions / unpack','BER + EVM']),
            (2.0,'siso_wlan_lab.grc',['Wi-Fi reference PPDU','SISO FIR + CFO','Add fixed AWGN','STF/LTF / FFT / ZF','Pilot phase / decisions','BER + EVM'])]
    for y,title,labels in chains:
        ax.text(.1,y+.7,title,fontsize=13,fontweight='bold')
        for i,label in enumerate(labels):
            x=.1+i*2.32
            ax.add_patch(FancyBboxPatch((x,y),2.05,.55,boxstyle='round,pad=.06',facecolor='#eaf2f8',edgecolor='#326a9b'))
            ax.text(x+1.025,y+.275,label,ha='center',va='center',fontsize=9)
            if i<5: ax.annotate('',xy=(x+2.26,y+.275),xytext=(x+2.10,y+.275),arrowprops=dict(arrowstyle='->'))
        ax.text(.1,y-.4,'Live plots: TX/RX spectrum + waterfall + I/Q time; equalized/reference constellation; numerical BER and EVM.',fontsize=10)
    ax.text(.1,5.75,'Figure S1. Complete SISO GNU Radio labs — one TX stream, one RX stream',fontsize=16,fontweight='bold')
    ax.text(.1,.65,'Wi-Fi receiver uses known burst timing/rate/length. No MAC, acknowledgements, retries or MIMO processing.',fontsize=11)
    ax.text(.1,.2,'The TX reference branch supplies the exact aligned bits and symbols to the metrics. Both labs save integer counts on Stop.',fontsize=10)
    save(fig,'siso_flowgraphs')

    r=case('wlan_4_impaired'); data=np.load(ROOT/'results/live/cases/wlan_4_impaired/capture.npz')
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    eq=data['equalized'][:5000]; points=wlan_constellation(16)
    axes[0,0].scatter(eq.real,eq.imag,s=3,alpha=.3,label='Recovered DATA')
    axes[0,0].scatter(points.real,points.imag,s=55,marker='x',color='#D95319',label='Known 16-QAM points')
    axes[0,0].set(xlabel='In-phase (normalized)',ylabel='Quadrature (normalized)',title='(a) Equalized constellation',xlim=(-1.5,1.5),ylim=(-1.5,1.5),aspect='equal')
    for key,label,color in [('tx_waveform','TX',COLORS[0]),('rx_waveform','RX before correction',COLORS[1])]:
        f,p=welch(data[key],fs=20e6,nperseg=2048,return_onesided=False,scaling='density')
        axes[0,1].plot(np.fft.fftshift(f)/1e6,10*np.log10(np.maximum(np.fft.fftshift(p),1e-20)),color=color,label=label,lw=1)
    axes[0,1].set(xlabel='Complex baseband frequency (MHz)',ylabel='PSD (dB relative to unit power/Hz)',title='(b) Stored waveform PSD; Hann / Welch')
    count=800; t=np.arange(count)/20e6*1e6
    for key,label,color in [('tx_waveform','TX I',COLORS[0]),('rx_waveform','RX I',COLORS[1])]:
        axes[1,0].plot(t,data[key][:count].real,color=color,label=label,lw=.8)
    axes[1,0].set(xlabel='Signal time (µs)',ylabel='In-phase amplitude (normalized)',title='(c) Active burst start: training and DATA')
    history=np.asarray(r['ber']['history']); bound=-np.expm1(np.log(.05)/history[:,0])
    nonzero=history[:,1]>0
    if np.any(nonzero): axes[1,1].semilogy(history[nonzero,0],history[nonzero,1]/history[nonzero,0],color=COLORS[1],label='Observed cumulative BER')
    if np.any(~nonzero): axes[1,1].semilogy(history[~nonzero,0],bound[~nonzero],'--',color=COLORS[0],label='Zero errors: nominal 95% upper limit')
    axes[1,1].set(xlabel='Compared mapped DATA bits',ylabel='BER / nominal upper limit',title='(d) BER accumulation in the running GRC graph')
    for a in axes.flat: a.grid(alpha=.2); a.legend(fontsize=9)
    fig.suptitle(f'Figure S2. Actual SISO GRC capture: 16-QAM, 8 bursts, BER={r["ber"]["ber"]:.3g}, RMS EVM={r["evm"]["evm_percent"]:.2f}%\n'
        'Unit active TX power; TX-reference SNR 35 dB; 3 dB path loss; 20 kHz CFO; four-tap channel',fontweight='bold')
    save(fig,'siso_dashboard')

    names=['modem_2','modem_4','modem_16','modem_64','modem_16_loss6']; reports=[case(n) for n in names]
    labels=['BPSK','QPSK','16-QAM','64-QAM','16-QAM\n6 dB loss']
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for i,r in enumerate(reports):
        b=r['ber']; color=COLORS[i%4]
        axes[0].errorbar(i,b['ber'],yerr=[[b['ber']-b['ci95_lower']],[b['ci95_upper']-b['ber']]],fmt='o',color=color,capsize=4)
        axes[0].plot(i,r['theory_ber'],'kx',ms=9)
        axes[1].plot(i,r['evm']['evm_percent'],'o',color=color)
        expected=100/np.sqrt(np.log2(r['case']['order'])*10**((8-r['case']['path_loss_db'])/10))
        axes[1].plot(i,expected,'kx',ms=9)
    axes[0].set(yscale='log',ylabel='Uncoded BER',title='(a) Native decisions and cumulative bit counter')
    axes[1].set(ylabel='RMS EVM (%)',title='(b) Reference-based EVM, no payload fit')
    handles=[Line2D([],[],color=COLORS[0],marker='o',ls='none',label='GRC estimate (nominal 95% BER CI)'),Line2D([],[],color='black',marker='x',ls='none',label='Exact BER / AWGN EVM prediction')]
    for a in axes: a.set_xticks(range(5),labels); a.grid(alpha=.2); a.legend(handles=handles,fontsize=8,loc='upper left')
    axes[1].legend(handles=handles,fontsize=8,loc='upper center')
    fig.suptitle('Figure S3. Complete SISO modem: fixed TX Es = 1 and TX-reference Eb/N0 = 8 dB\n100,000 symbols/case; the last case changes only channel loss',fontweight='bold')
    save(fig,'siso_modem_theory')

    fig,axes=plt.subplots(1,2,figsize=(12,5.4),layout='constrained')
    losses=np.array([0,6,12,18])
    for i,rate in enumerate((0,2,4,6)):
        rs=[case(f'wlan_{rate}'+(f'_loss{loss}' if loss else '')) for loss in losses]
        ber=np.array([r['ber']['ber'] for r in rs]); nonzero=ber>0
        axes[0].semilogy(losses,np.where(nonzero,ber,np.nan),'o-',color=COLORS[i],label=LABELS[i])
        axes[0].semilogy(losses[~nonzero],[r['ber']['zero_error_upper95'] for r in rs if not r['ber']['errors']],'v',ls='none',mfc='none',color=COLORS[i])
        axes[1].plot(losses,[r['evm']['evm_percent'] for r in rs],'o-',color=COLORS[i],label=LABELS[i])
    for a in axes: a.set(xlabel='Additional SISO channel power loss (dB)',xticks=losses); a.grid(alpha=.2); a.legend(fontsize=9)
    handles,labels=axes[0].get_legend_handles_labels()
    handles.append(Line2D([],[],color='black',marker='v',mfc='none',ls='none'))
    axes[0].legend(handles,labels+['Zero errors: nominal 95% upper limit'],fontsize=8)
    axes[0].set(ylabel='Pre-FEC mapped DATA BER / upper limit',ylim=(1e-6,1),title='(a) Bit errors; triangles mark zero-error limits')
    axes[1].set(ylabel='Pooled RMS DATA EVM (%)',title='(b) Noisy L-LTF ZF equalization')
    fig.suptitle('Figure S4. Fixed-power SISO Wi-Fi: channel-loss sweep\nTX active PPDU power = 1; fixed noise power = 10⁻²·⁵; 8 bursts/point; known timing',fontweight='bold')
    save(fig,'siso_fixed_power')

    bad=case('wlan_4_uncorrected'); good=case('wlan_4_impaired')
    b=np.load(ROOT/'results/live/cases/wlan_4_uncorrected/capture.npz'); g=data
    np.testing.assert_array_equal(b['rx_waveform'],g['rx_waveform'])
    fig,axes=plt.subplots(1,2,figsize=(12,5.6),layout='constrained')
    for a,d,r,title in zip(axes,(b,g),(bad,good),('Corrections disabled','STF/LTF CFO + pilot phase enabled')):
        e=d['equalized'][:5000]
        a.scatter(e.real,e.imag,s=3,alpha=.25,label='Recovered DATA')
        a.scatter(points.real,points.imag,color='#D95319',marker='x',s=40,label='Known reference')
        a.set(xlabel='In-phase (normalized)',ylabel='Quadrature (normalized)',aspect='equal',
            title=f'{title}\nBER={r["ber"]["ber"]:.3g}; RMS EVM={r["evm"]["evm_percent"]:.2f}%')
        a.grid(alpha=.2); a.legend(fontsize=9)
    fig.suptitle('Figure S5. Same received IQ, different SISO receiver corrections\n20 kHz CFO + four-tap FIR; 3 dB loss; TX-reference SNR 35 dB; axis scales differ',fontweight='bold')
    save(fig,'siso_receiver_controls')
    print('Wrote five SISO result figures (PNG / vector PDF / SVG)')


if __name__=='__main__': main()
