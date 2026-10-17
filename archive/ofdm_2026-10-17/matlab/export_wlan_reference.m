function manifest = export_wlan_reference(outputDirectory, packetsPerRate)
% Editing guide: docs/MODULAR_FLOWGRAPHS.md. Inputs/outputs use the units stated below.
%EXPORT_WLAN_REFERENCE Export true non-HT WLAN Toolbox PPDUs for GNU Radio.
% Repeats a known synthetic PSDU; no MAC header/FCS is implied. Timing/scale
% metadata is exported out-of-band. See docs/FLOWGRAPHS.md [MW-WAVE, MW-NHT].
root=fileparts(fileparts(mfilename('fullpath')));
if nargin<1, outputDirectory=fullfile(root,'results','reference'); end
if nargin<2, packetsPerRate=16; end
assert(packetsPerRate>=1 && mod(packetsPerRate,1)==0);
if ~exist(outputDirectory,'dir'), mkdir(outputDirectory); end
% Edit sample rate / payload settings in configs/wifi_nonht_defaults.json.
% The current receiver assumes legacy 20 MHz OFDM; bandwidth changes need matching receiver changes.
config=jsondecode(fileread(fullfile(root,'configs','wifi_nonht_defaults.json')));
fs=config.phy.sample_rate_hz; psduLength=config.phy.psdu_length_bytes;
rng(config.measurement.payload_seed,'twister'); bits=randi([0 1],8*psduLength,1);
waveforms=cell(8,1); globalPeak=0;
for rate=0:7
    cfg=wlanNonHTConfig('MCS',rate,'PSDULength',psduLength,'ChannelBandwidth','CBW20');
    waveforms{rate+1}=wlanWaveformGenerator(bits,cfg,'ScramblerInitialization',93,'WindowTransitionTime',0);
    globalPeak=max(globalPeak,max(abs(waveforms{rate+1})));
end
scale=config.radio.tx_peak_amplitude_limit/globalPeak;
rates=[6 9 12 18 24 36 48 54]; orders=[2 2 4 4 16 16 64 64];
idleSamples=2000; leadSamples=512;
for rate=0:7
    cfg=wlanNonHTConfig('MCS',rate,'PSDULength',psduLength,'ChannelBandwidth','CBW20');
    fields=wlanFieldIndices(cfg); info=wlanNonHTOFDMInfo('NonHT-Data',cfg);
    unscaled=waveforms{rate+1}; packet=unscaled*scale;
    ltfDemod=wlanLLTFDemodulate(packet(fields.LLTF(1):fields.LLTF(2)),cfg,1);
    channel=wlanLLTFChannelEstimate(ltfDemod,cfg,1);
    [decoded,reference_symbols]=wlanNonHTDataRecover(packet(fields.NonHTData(1):fields.NonHTData(2)), ...
        channel,1e-12,cfg,'EqualizationMethod','ZF','PilotPhaseTracking','None','OFDMSymbolOffset',1);
    assert(isequal(decoded,bits),'Noiseless WLAN reference must decode exactly');
    tx_packet=packet; tx_bits=bits; order=orders(rate+1); rate_index=rate;
    reference_coded_bits=wlanConstellationDemap(reference_symbols,1,log2(order),'hard');
    data_start=fields.NonHTData(1)-1; data_length=diff(fields.NonHTData)+1;
    ltf_start=fields.LLTF(1)-1;
    packet_starts=leadSamples+(0:packetsPerRate-1)'*(numel(packet)+idleSamples);
    frame=[packet;zeros(idleSamples,1)]; waveform=[zeros(leadSamples,1);repmat(frame,packetsPerRate,1)];
    iq=zeros(2*numel(waveform),1,'single'); iq(1:2:end)=real(waveform); iq(2:2:end)=imag(waveform);
    stem=fullfile(outputDirectory,sprintf('wlan_rate_%d',rate));
    fid=fopen([stem '_tx.c64'],'w','ieee-le'); assert(fid>=0); fwrite(fid,iq,'single'); fclose(fid);
    save([stem '.mat'],'tx_packet','tx_bits','reference_symbols','reference_coded_bits','order','rate_index', ...
        'packet_starts','data_start','data_length','ltf_start','fs','scale','-v7');
    active=packet(fields.NonHTData(1):fields.NonHTData(2));
    meta=struct('schema_version',1,'rate_index',rate,'order',order,'phy_rate_mbps',rates(rate+1), ...
        'sample_rate_hz',fs,'psdu_length_bytes',psduLength,'packets',packetsPerRate, ...
        'packet_samples',numel(packet),'leading_samples',leadSamples,'idle_samples',idleSamples, ...
        'active_time_power',mean(abs(active).^2),'common_tx_scale',scale, ...
        'peak_amplitude',max(abs(packet)),'window_transition_s',0,'scrambler_initial_state',93, ...
        'payload_kind','synthetic PSDU, no MAC/FCS','source','MATLAB WLAN Toolbox', ...
        'timing_scope','schedule-assisted finite reference, not a tested autonomous receiver');
    fid=fopen([stem '.json'],'w'); assert(fid>=0); fprintf(fid,'%s\n',jsonencode(meta,PrettyPrint=true)); fclose(fid);
end
manifest=struct('status','passed','rates',8,'packetsPerRate',packetsPerRate, ...
    'matlabVersion',version,'commonTxScale',scale,'source','wlanWaveformGenerator', ...
    'noiselessPsduRecovery','passed_all_8_rates');
fid=fopen(fullfile(outputDirectory,'manifest.json'),'w'); assert(fid>=0);
fprintf(fid,'%s\n',jsonencode(manifest,PrettyPrint=true)); fclose(fid); disp(manifest);
end
