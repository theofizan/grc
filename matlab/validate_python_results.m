function report = validate_python_results(inputDirectory)
%VALIDATE_PYTHON_RESULTS Independently score shared Python/GRC symbol captures.
% Verifies exact bit counts, direct EVM, and comm.EVM average-reference result.
if nargin < 1
    root=fileparts(fileparts(mfilename('fullpath')));
    inputDirectory=fullfile(root,'results','python');
end
files=dir(fullfile(inputDirectory,'*fixture.mat'));
if isempty(files), files=dir(fullfile(inputDirectory,'symbol_metrics.mat')); end
assert(~isempty(files),'Generate Python/GRC fixtures first');
report=struct('files',numel(files),'status','passed','worstEvmAbsoluteDifference',0);
for f=1:numel(files)
    data=load(fullfile(files(f).folder,files(f).name));
    order=double(data.order); k=log2(order); labels=(0:order-1)';
    if order==2
        points=[-1;1];
    else
        side=sqrt(order); width=k/2;
        iGray=bitshift(uint32(labels),-width); qGray=bitand(uint32(labels),side-1);
        i=iGray; q=qGray;
        for shift=[1 2 4]
            i=bitxor(i,bitshift(i,-shift)); q=bitxor(q,bitshift(q,-shift));
        end
        points=(2*double(i)-side+1+1j*(2*double(q)-side+1))/sqrt(2*(order-1)/3);
    end
    tx=double(data.tx(:)); rx=double(data.rx(:));
    assert(numel(tx)==numel(rx) && all(isfinite(tx)) && all(isfinite(rx)));
    [~,txIndex]=min(abs(tx-points.').^2,[],2);
    [~,rxIndex]=min(abs(rx-points.').^2,[],2);
    difference=bitxor(uint32(txIndex-1),uint32(rxIndex-1)); errors=0;
    for b=1:k, errors=errors+sum(bitget(difference,b)); end
    directEvm=sqrt(sum(abs(rx-tx).^2)/sum(abs(tx).^2));
    oracle=comm.EVM('Normalization','Average reference signal power');
    oracleEvm=oracle(tx,rx)/100;
    assert(errors==data.python_errors && numel(tx)*k==data.python_bits);
    delta=max(abs([directEvm-double(data.python_evm), oracleEvm-directEvm]));
    assert(delta<5e-7,'Shared metric calculation disagrees');
    report.worstEvmAbsoluteDifference=max(report.worstEvmAbsoluteDifference,delta);
end
fid=fopen(fullfile(inputDirectory,'matlab_cross_validation.json'),'w'); assert(fid>=0);
cleaner=onCleanup(@()fclose(fid)); fprintf(fid,'%s\n',jsonencode(report,PrettyPrint=true));
disp(report);
end
