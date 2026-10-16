"""Regenerate annotated, native-block GRC sources for GNU Radio 3.10.

Generated Python is deliberately kept in grc/generated; .grc files are the
editable deliverables. UHD graphs are compiled, never launched by this script.
"""
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]


def block(name, kind, parameters, x, y):
    return dict(name=name, id=kind, parameters=parameters,
                states=dict(bus_sink=False,bus_source=False,bus_structure=None,
                            coordinate=[x,y],rotation=0,state='enabled'))


def parameter(name, value, kind, x, y):
    labels={'order':'Constellation order M','ebno_db':'Uncoded Eb/N0 (dB)',
            'symbol_count':'Number of symbols','rate_index':'Legacy rate index (0-7)',
            'snr_db':'Active DATA sample SNR (dB)','center_frequency':'RF center frequency (Hz)',
            'gain_db':'USRP gain (dB)','device_args':'UHD device address',
            'capture_samples':'Complex samples to capture','seed':'Noise/reference seed',
            'path_loss_db':'SISO power loss (dB)','pace':'Playback samples per wall-clock second',
            'packet_count':'PHY bursts (0 = continuous)','cfo_hz':'Carrier offset (Hz)',
            'channel_taps':'Causal SISO FIR taps','correct_cfo':'STF/LTF CFO correction (0/1)',
            'pilot_tracking':'Pilot phase correction (0/1)'}
    return block(name,'parameter',dict(value=str(value),type=kind,label=labels.get(name,name),short_id='',hide='none'),x,y)


def variable(name,value,x,y):
    return block(name,'variable',dict(value=str(value),comment=''),x,y)


def note(name,text,x,y):
    return block(name,'note',dict(note=text),x,y)


def file_source(name,path,x,y):
    return block(name,'blocks_file_source',dict(type='complex',file=path,repeat='False',
        vlen='1',begin_tag='pmt.PMT_NIL',offset='0',length='0'),x,y)


def file_sink(name,path,x,y):
    return block(name,'blocks_file_sink',dict(type='complex',file=path,append='False',
        vlen='1',unbuffered='False'),x,y)


def write_graph(name,title,items,connections,description,generate_options='no_gui'):
    graph=dict(options=dict(parameters=dict(id=name,title=title,author='Antenna benchmark project',
        description=description,generate_options=generate_options,output_language='python',
        run_options='run',catch_exceptions='True',run='True'),
        states=dict(coordinate=[8,8],rotation=0,state='enabled')),
        blocks=items,connections=connections,metadata=dict(file_format=1,grc_version='3.10.12.0'))
    (ROOT/'grc'/f'{name}.grc').write_text(yaml.safe_dump(graph,sort_keys=False,width=110))


def imports():
    return block('project_imports','import',dict(imports=
        'from antenna_bench.paths import ROOT\nfrom antenna_bench.math import make_symbols\nimport math'),240,12)


def awgn():
    items=[imports(),parameter('order',16,'intx',240,90),
        parameter('ebno_db',8,'eng_float',440,90),parameter('symbol_count',100000,'intx',640,90),
        parameter('seed',20261016,'intx',840,90),
        variable('noise_voltage','math.sqrt(1/(math.log2(order)*10**(ebno_db/10)))',240,180),
        block('reference_symbols','blocks_vector_source_x',dict(type='complex',
            vector='make_symbols(order, symbol_count, seed).tolist()',repeat='False',vlen='1',tags='[]'),240,300),
        block('complex_awgn','analog_noise_source_x',dict(type='complex',noise_type='analog.GR_GAUSSIAN',
            amp='noise_voltage',seed='seed+1'),240,440),
        block('add_noise','blocks_add_xx',dict(type='complex',num_inputs='2',vlen='1'),650,350),
        file_sink('received_symbols',"str(ROOT / 'results/grc/symbol_rx.c64')",900,350),
        file_sink('transmitted_symbols',"str(ROOT / 'results/grc/symbol_tx.c64')",650,240),
        note('scope','UNCODED SYMBOL-RATE DIAGNOSTIC: perfect alignment, Es=1, no RF waveform or FEC.',240,570),
        note('noise','E|n|^2 = noise_voltage^2 = 1/(log2(M)*EbNo). Complex Gaussian convention is validated.',240,610),
        note('analysis','Run scripts/analyze_symbols.py then MATLAB validate_python_results(results/grc). See docs/FLOWGRAPHS.md.',240,650)]
    edges=[['reference_symbols','0','add_noise','0'],['complex_awgn','0','add_noise','1'],
           ['reference_symbols','0','transmitted_symbols','0'],['add_noise','0','received_symbols','0']]
    write_graph('awgn_symbol_benchmark','Uncoded BER and EVM: aligned symbol AWGN',items,edges,
                'Exact uncoded-theory diagnostic with finite captures and external metrics. Not an 802.11 PHY.')


def wlan_sim():
    items=[imports(),parameter('rate_index',2,'intx',240,90),parameter('snr_db',25,'eng_float',440,90),
        variable('sample_rate','20e6',640,90),
        variable('tx_file',"str(ROOT / ('results/reference/wlan_rate_%d_tx.c64' % rate_index))",240,180),
        variable('noise_voltage',"math.sqrt(__import__('json').loads((ROOT / ('results/reference/wlan_rate_%d.json' % rate_index)).read_text())['active_time_power']/10**(snr_db/10))",640,180),
        file_source('wifi_reference', 'tx_file',240,320),
        block('complex_awgn','analog_noise_source_x',dict(type='complex',noise_type='analog.GR_GAUSSIAN',amp='noise_voltage',seed='20261017'),240,450),
        block('add_noise','blocks_add_xx',dict(type='complex',num_inputs='2',vlen='1'),650,350),
        file_sink('wifi_capture',"str(ROOT / ('results/grc/wlan_rate_%d_rx.c64' % rate_index))",900,350),
        note('scope','WLAN TOOLBOX REFERENCE PPDU -> GNU RADIO AWGN -> RAW IQ. No packet/coding approximation.',240,570),
        note('axis','snr_db is active-DATA time-sample SNR, not EbNo. Idle samples are excluded from signal-power calibration.',240,610),
        note('analysis','Offline Python: known-schedule pre-FEC BER/EVM. MATLAB: independent equalizer, decoder and post-FEC BER.',240,650)]
    edges=[['wifi_reference','0','add_noise','0'],['complex_awgn','0','add_noise','1'],['add_noise','0','wifi_capture','0']]
    write_graph('wlan_reference_channel','Legacy Wi-Fi reference: finite IQ AWGN replay',items,edges,
                'Replay actual MATLAB-generated non-HT PPDU samples. See docs/FLOWGRAPHS.md for export and analysis.')


def wlan_fft():
    items=[imports(),parameter('rate_index',2,'intx',240,90),
        variable('reference',"__import__('scipy.io', fromlist=['loadmat']).loadmat(str(ROOT / ('results/reference/wlan_rate_%d.mat' % rate_index)), squeeze_me=True)",440,90),
        variable('metadata',"__import__('json').loads((ROOT / ('results/reference/wlan_rate_%d.json' % rate_index)).read_text())",240,180),
        file_source('aligned_capture',"str(ROOT / ('results/grc/wlan_rate_%d_rx.c64' % rate_index))",240,320),
        block('remove_leading_samples','blocks_skiphead',dict(type='complex',vlen='1',num_items="metadata['leading_samples']"),600,320),
        block('extract_data_fields','blocks_keep_m_in_n',dict(type='complex',m="int(reference['data_length'])",n="metadata['packet_samples']+metadata['idle_samples']",offset="int(reference['data_start'])"),940,320),
        block('remove_cyclic_prefix','blocks_keep_m_in_n',dict(type='complex',m='64',n='80',offset='16'),240,500),
        block('ofdm_vectors','blocks_stream_to_vector',dict(type='complex',num_items='64',vlen='1'),570,500),
        block('fft_64','fft_vxx',dict(type='complex',fft_size='64',forward='True',window='[]',shift='False',nthreads='1'),850,500),
        block('fft_capture','blocks_file_sink',dict(type='complex',file="str(ROOT / ('results/grc/wlan_rate_%d_fft.c64' % rate_index))",append='False',vlen='64',unbuffered='False'),1120,500),
        note('scope','KNOWN-SCHEDULE OFDM EXTRACTION: timing/rate/length are supplied; this is not autonomous packet acquisition.',240,680),
        note('convention','DATA FFT window starts after all 16 CP samples. Forward FFT, no shift, no window; all 64 bins stored.',240,720),
        note('analysis','Run scripts/validate_grc_fft.py. Channel estimation, EVM, and demapping are independently checked offline.',240,760)]
    edges=[['aligned_capture','0','remove_leading_samples','0'],['remove_leading_samples','0','extract_data_fields','0'],
           ['extract_data_fields','0','remove_cyclic_prefix','0'],['remove_cyclic_prefix','0','ofdm_vectors','0'],
           ['ofdm_vectors','0','fft_64','0'],['fft_64','0','fft_capture','0']]
    write_graph('wlan_ofdm_fft','Legacy Wi-Fi: visible CP removal and FFT',items,edges,
                'Explicit GNU Radio DATA extraction, CP removal, vectorization and FFT; known-schedule software verification.')


def hardware(transmit):
    name='usrp_wifi_tx' if transmit else 'usrp_wifi_rx'
    items=[imports(),parameter('center_frequency',5.18e9,'eng_float',240,90),
        parameter('gain_db',0 if transmit else 20,'eng_float',440,90),
        parameter('device_args','type=x300,addr=192.168.10.2','str',640,90),
        variable('sample_rate','20e6',240,180)]
    common=dict(type='fc32',otw='sc16',dev_addr='device_args',dev_args='',
                sync='none',clock_source0='internal',time_source0='',sd_spec0='',
                nchan='1',samp_rate='sample_rate',center_freq0='center_frequency',
                gain0='gain_db',ant0='"TX/RX"' if transmit else '"RX2"')
    if transmit:
        items += [parameter('rate_index',2,'intx',840,90),
            file_source('wifi_reference',"str(ROOT / ('results/reference/wlan_rate_%d_tx.c64' % rate_index))",240,340),
            block('usrp_sink','uhd_usrp_sink',common,700,340)]
        edges=[['wifi_reference','0','usrp_sink','0']]
    else:
        items += [parameter('capture_samples',2000000,'intx',840,90),
            block('usrp_source','uhd_usrp_source',common,240,340),
            block('finite_capture','blocks_head',dict(type='complex',num_items='capture_samples',vlen='1'),700,340),
            file_sink('raw_iq',"str(ROOT / 'results/grc/usrp_rx.c64')",960,340)]
        edges=[['usrp_source','0','finite_capture','0'],['finite_capture','0','raw_iq','0']]
    items += [note('scope','HARDWARE GRAPH: compiled only; not radio-tested. Configure actual daughterboard, addresses, ports and gains.',240,600),
        note('steering','Steer/await ready/settle BEFORE starting capture; keep beam fixed throughout every scored packet.',240,640),
        note('metadata','Standalone graph does not archive UHD errors/settings or enforce steering. Paper runs require the documented acquisition ledger.',240,680)]
    write_graph(name,'USRP legacy Wi-Fi '+('transmit reference IQ' if transmit else 'finite raw IQ capture'),items,edges,
                'UHD hardware integration graph. RF/streaming, timed acquisition and antenna control require hardware commissioning.')


if __name__=='__main__':
    (ROOT/'grc/generated').mkdir(parents=True,exist_ok=True)
    (ROOT/'results/grc').mkdir(parents=True,exist_ok=True)
    awgn(); wlan_sim(); wlan_fft(); hardware(True); hardware(False)
    from build_siso_labs import build
    build()
    print('Wrote seven annotated GRC flowgraphs (including two live SISO labs)')
