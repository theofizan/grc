function report=validate_live_labs
%VALIDATE_LIVE_LABS Independently validate in-graph bit counts/EVM and WLAN RX.
root=fileparts(fileparts(mfilename('fullpath')));
manifest=jsondecode(fileread(fullfile(root,'results','live','manifest.json')));
report=struct('status','passed','cases',numel(manifest.cases),'receiverCases',0, ...
    'worstEvmDifference',0,'worstReceiverSymbolDifference',0);
for n=1:numel(manifest.cases)
    name=manifest.cases{n}; folder=fullfile(root,'results','live','cases',name);
    d=load(fullfile(folder,'live_fixture.mat')); metrics=jsondecode(fileread(fullfile(folder,'metrics.json')));
    tx=double(d.tx(:)); rx=double(d.rx(:)); order=double(d.order);
    % WLAN Toolbox demapper independently supplies the IEEE bit labels.
    txBits=wlanConstellationDemap(tx,1,log2(order),'hard');
    rxBits=wlanConstellationDemap(rx,1,log2(order),'hard');
    errors=sum(txBits(:)~=rxBits(:)); assert(errors==d.python_errors && numel(txBits)==d.python_bits);
    evm=sqrt(sum(abs(rx-tx).^2)/sum(abs(tx).^2));
    oracle=comm.EVM('Normalization','Average reference signal power');
    difference=max(abs([evm-double(d.python_evm),oracle(tx,rx)/100-evm]));
    assert(difference<1e-10); report.worstEvmDifference=max(report.worstEvmDifference,difference);
    % Flat AWGN cases (all eight rates) also independently recover raw IQ.
    if isfield(d,'reference') && ~d.correct_cfo && ~d.pilot_tracking && metrics.case.cfo_hz==0
        ref=d.reference; result=recover_reference_packet(d.received_packet,ref);
        count=numel(ref.reference_symbols); first=rx(1:count);
        delta=max(abs(first-result.equalizedSymbols(:)));
        fprintf('%s: independent receiver max difference %.12g\n',name,delta);
        % The streaming GRC output and references are complex64. This differs
        % from the old offline complex128-to-double comparison (~1e-15).
        assert(delta<2e-6,'Independent WLAN receiver disagrees with live GRC chain');
        report.worstReceiverSymbolDifference=max(report.worstReceiverSymbolDifference,delta);
        report.receiverCases=report.receiverCases+1;
    end
end
fid=fopen(fullfile(root,'results','live','matlab_validation.json'),'w'); assert(fid>=0);
fprintf(fid,'%s\n',jsonencode(report,PrettyPrint=true)); fclose(fid); disp(report);
end
