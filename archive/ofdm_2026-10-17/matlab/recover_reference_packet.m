function result = recover_reference_packet(packet, reference, correctCFO)
% Editing guide: docs/MODULAR_FLOWGRAPHS.md. Inputs/outputs use the units stated below.
%RECOVER_REFERENCE_PACKET Known-rate/known-boundary non-HT receiver reference.
% Training-only channel estimate, ZF, no pilot tracking in AWGN comparison.
% This is intentionally schedule-assisted, not an autonomous WLAN receiver.
if nargin<3, correctCFO=false; end
cfg=wlanNonHTConfig('MCS',double(reference.rate_index),'PSDULength',numel(reference.tx_bits)/8);
fields=wlanFieldIndices(cfg);
if correctCFO
    coarse=wlanCoarseCFOEstimate(packet(fields.LSTF(1):fields.LSTF(2)),'CBW20');
    packet=packet.*exp(-1j*2*pi*coarse*(0:numel(packet)-1)'/reference.fs);
    fine=wlanFineCFOEstimate(packet(fields.LLTF(1):fields.LLTF(2)),'CBW20');
    packet=packet.*exp(-1j*2*pi*fine*(0:numel(packet)-1)'/reference.fs);
end
ltf=wlanLLTFDemodulate(packet(fields.LLTF(1):fields.LLTF(2)),cfg,1);
channel=wlanLLTFChannelEstimate(ltf,cfg,1);
variance=max(wlanLLTFNoiseEstimate(ltf),1e-12);
[~,signalFailed]=wlanLSIGRecover(packet(fields.LSIG(1):fields.LSIG(2)),channel,variance,'CBW20');
[bits,eq]=wlanNonHTDataRecover(packet(fields.NonHTData(1):fields.NonHTData(2)),channel,variance,cfg, ...
    'EqualizationMethod','ZF','PilotPhaseTracking','None','OFDMSymbolOffset',1);
referenceEq=double(reference.reference_symbols);
errorEnergy=sum(abs(eq(:)-referenceEq(:)).^2); referenceEnergy=sum(abs(referenceEq(:)).^2);
result=struct('errors',sum(bits~=reference.tx_bits),'bits',numel(bits), ...
    'signalFailed',logical(signalFailed),'errorEnergy',errorEnergy,'referenceEnergy',referenceEnergy, ...
    'evmRms',sqrt(errorEnergy/referenceEnergy),'equalizedSymbols',eq,'noiseVariance',variance);
mapped=wlanConstellationDemap(eq,1,log2(double(reference.order)),'hard');
result.preFecErrors=sum(mapped(:)~=reference.reference_coded_bits(:));
result.preFecBits=numel(mapped);
end
