function report = analyze_wlan_capture(rateIndex, capturePath, referenceDirectory, sampleOffset)
%ANALYZE_WLAN_CAPTURE Independently decode a schedule-aligned GRC IQ capture.
% A known rate/length and schedule are supplied. Missed/truncated packets are
% included in the packet denominator; no CRC success filtering of bit counts.
root=fileparts(fileparts(mfilename('fullpath')));
if nargin<1, rateIndex=2; end
if nargin<2, capturePath=fullfile(root,'results','grc',sprintf('wlan_rate_%d_rx.c64',rateIndex)); end
if nargin<3, referenceDirectory=fullfile(root,'results','reference'); end
if nargin<4, sampleOffset=0; end
reference=load(fullfile(referenceDirectory,sprintf('wlan_rate_%d.mat',rateIndex)));
fid=fopen(capturePath,'r','ieee-le'); assert(fid>=0); raw=fread(fid,[2 Inf],'single=>double'); fclose(fid);
assert(size(raw,1)==2,'Truncated complex sample'); rx=complex(raw(1,:),raw(2,:)).';
errors=0; bits=0; packetErrors=0; unavailable=0; energy=0; refEnergy=0; rows=[]; allEq=[];
preFecErrors=0; preFecBits=0;
for n=1:numel(reference.packet_starts)
    first=double(reference.packet_starts(n))+sampleOffset+1; last=first+numel(reference.tx_packet)-1;
    if first<1 || last>numel(rx)
        unavailable=unavailable+1; packetErrors=packetErrors+1; continue
    end
    result=recover_reference_packet(rx(first:last),reference);
    errors=errors+result.errors; bits=bits+result.bits;
    preFecErrors=preFecErrors+result.preFecErrors; preFecBits=preFecBits+result.preFecBits;
    packetErrors=packetErrors+(result.errors>0 || result.signalFailed);
    energy=energy+result.errorEnergy; refEnergy=refEnergy+result.referenceEnergy;
    allEq=cat(3,allEq,result.equalizedSymbols);
    rows=[rows;n result.errors result.bits result.evmRms result.signalFailed]; %#ok<AGROW>
end
assert(bits>0,'No complete packets to analyze');
report=struct('rateIndex',rateIndex,'timingMode','known_schedule_and_rate', ...
    'errors',errors,'bits',bits,'postFecBer',errors/bits, ...
    'preFecErrors',preFecErrors,'preFecBits',preFecBits,'preFecBer',preFecErrors/preFecBits, ...
    'expectedPackets',numel(reference.packet_starts),'unavailablePackets',unavailable, ...
    'packetErrors',packetErrors,'packetErrorRate',packetErrors/numel(reference.packet_starts), ...
    'evmRms',sqrt(energy/refEnergy),'capturePath',capturePath, ...
    'status','analyzed_not_hardware_validated');
pythonPath=fullfile(root,'results','grc',sprintf('wlan_rate_%d_python_symbols.mat',rateIndex));
if exist(pythonPath,'file')
    python=load(pythonPath);
    assert(isequal(size(python.python_eq),size(allEq)),'Python/MATLAB packet sets differ');
    report.pythonMaxSymbolDifference=max(abs(python.python_eq(:)-allEq(:)));
    report.pythonEvmDifference=abs(python.python_evm-report.evmRms);
    assert(report.pythonMaxSymbolDifference<1e-9 && report.pythonEvmDifference<1e-10, ...
        'Python/MATLAB OFDM receiver metrics disagree');
    pythonMetrics=jsondecode(fileread(fullfile(root,'results','grc',sprintf('wlan_rate_%d_python.json',rateIndex))));
    assert(pythonMetrics.pre_fec_errors==preFecErrors && pythonMetrics.pre_fec_bits==preFecBits, ...
        'Python/MATLAB coded-bit mapping/counts disagree');
end
out=fullfile(root,'results','grc',sprintf('wlan_rate_%d_matlab',rateIndex));
writetable(array2table(rows,'VariableNames',{'packet','errors','bits','evmRms','signalFailed'}),[out '.csv']);
fid=fopen([out '.json'],'w'); assert(fid>=0); fprintf(fid,'%s\n',jsonencode(report,PrettyPrint=true)); fclose(fid);
disp(report);
end
