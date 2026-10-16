function summary = run_theory(outputDirectory, symbolsPerPoint)
%RUN_THEORY Produce cited uncoded AWGN BER/EbNo, EVM, and uncertainty charts.
% Output: PNG, vector PDF, CSV, MAT, JSON. See docs/THEORY.md and references.bib.
% Requires Communications Toolbox for independent modulation/berawgn checks.
if nargin < 1
    root = fileparts(fileparts(mfilename('fullpath')));
    outputDirectory = fullfile(root, 'results', 'theory');
end
if nargin < 2, symbolsPerPoint = 100000; end
assert(symbolsPerPoint > 0 && mod(symbolsPerPoint,1) == 0);
if ~exist(outputDirectory,'dir'), mkdir(outputDirectory); end
orders = [2 4 16 64]; labels = {'BPSK','QPSK','16-QAM','64-QAM'};
ebnoDB = (0:0.25:20)'; mcEbno = (0:2:18)';
theory = zeros(numel(ebnoDB),4); rows = [];
oracleRelativeError = zeros(1,4);
% Same modulation colors as scripts/plot_validation.py; line styles survive grayscale.
colors = [0 0.447 0.741; 0.850 0.325 0.098; 0.2 0.6 0.3; 0.494 0.184 0.556];
for m = 1:4
    order = orders(m); k = log2(order);
    theory(:,m) = gray_awgn_ber(order,ebnoDB);
    if order <= 4
        oracle = berawgn(ebnoDB,'psk',order,'nondiff');
    else
        oracle = berawgn(ebnoDB,'qam',order);
    end
    scored = oracle > 1e-14;
    oracleRelativeError(m) = max(abs(theory(scored,m)-oracle(scored))./oracle(scored));
    assert(oracleRelativeError(m) < 1e-5, 'Independent theory disagrees with berawgn');
    for n = 1:numel(mcEbno)
        rng(20261016 + 100*order + n,'twister');
        input = randi([0 order-1],symbolsPerPoint,1);
        if order <= 4
            phase = (order==4)*pi/4;
            tx = pskmod(input,order,phase,'gray');
        else
            tx = qammod(input,order,'gray','UnitAveragePower',true);
        end
        noiseVariance = 1/(k*10^(mcEbno(n)/10));
        rx = tx + sqrt(noiseVariance/2)*(randn(size(tx))+1j*randn(size(tx)));
        if order <= 4
            decisions = pskdemod(rx,order,phase,'gray');
        else
            decisions = qamdemod(rx,order,'gray','UnitAveragePower',true);
        end
        differences = bitxor(uint32(input),uint32(decisions));
        errors = 0;
        for b = 1:k, errors = errors + sum(bitget(differences,b)); end
        bits = k*symbolsPerPoint;
        [ber,interval] = berconfint(errors,bits,0.95);
        evm = sqrt(sum(abs(rx-tx).^2)/sum(abs(tx).^2));
        upperOneSided = -expm1(log(0.05)/bits);
        rows = [rows; order mcEbno(n) bits errors ber interval(:)' evm 100*evm ...
            gray_awgn_ber(order,mcEbno(n)) sqrt(noiseVariance) upperOneSided]; %#ok<AGROW>
    end
end
results = array2table(rows,'VariableNames',{'order','ebno_db','bits','errors','ber', ...
    'ci95_lower','ci95_upper','evm_rms','evm_percent','theory_ber','theory_evm_rms', ...
    'zero_error_upper95_one_sided'});
writetable(results,fullfile(outputDirectory,'matlab_awgn_results.csv'));
writetable(array2table([ebnoDB theory],'VariableNames', ...
    {'ebno_db','BPSK','QPSK','QAM16','QAM64'}),fullfile(outputDirectory,'exact_theory.csv'));

fig = figure('Visible','off','Color','w','Position',[100 100 1000 650]);
axesHandle = axes(fig); hold(axesHandle,'on');
for m=1:4
    semilogy(axesHandle,ebnoDB,theory(:,m),'Color',colors(m,:),'LineWidth',1.8, ...
        'LineStyle',charStyle(m),'DisplayName',[labels{m} ' exact theory']);
    subset = results(results.order==orders(m),:);
    visible = subset.errors > 0;
    errorbar(axesHandle,subset.ebno_db(visible),subset.ber(visible), ...
        subset.ber(visible)-subset.ci95_lower(visible), ...
        subset.ci95_upper(visible)-subset.ber(visible),'o','LineStyle','none', ...
        'Color',colors(m,:),'HandleVisibility','off');
    zero = ~visible;
    semilogy(axesHandle,subset.ebno_db(zero),subset.zero_error_upper95_one_sided(zero), ...
        'v','LineStyle','none','Color',colors(m,:),'HandleVisibility','off');
end
set(axesHandle,'YScale','log'); grid(axesHandle,'on'); ylim(axesHandle,[1e-7 1]); xlim(axesHandle,[0 20]);
xlabel(axesHandle,'E_b/N_0 per uncoded bit (dB)'); ylabel(axesHandle,'Bit error probability');
semilogy(axesHandle,nan,nan,'ko','DisplayName','MATLAB estimate + nominal 95% CI');
semilogy(axesHandle,nan,nan,'kv','DisplayName','Zero errors: one-sided 95% upper limit');
title(axesHandle,{'Figure 1. Uncoded BER in coherent AWGN', ...
    sprintf('%d symbols/point; BPSK and QPSK theory overlap',symbolsPerPoint)});
legend(axesHandle,'Location','southwest');
saveFigure(fig,outputDirectory,'ber_vs_ebno');

fig = figure('Visible','off','Color','w','Position',[100 100 1000 650]);
hold on;
for m=1:4
    expected = 100./sqrt(log2(orders(m))*10.^(ebnoDB/10));
    semilogy(ebnoDB,expected,'Color',colors(m,:),'LineStyle',charStyle(m), ...
        'LineWidth',1.8,'DisplayName',[labels{m} ' prediction']);
    subset = results(results.order==orders(m),:);
    semilogy(subset.ebno_db,subset.evm_percent,'o','Color',colors(m,:),'HandleVisibility','off');
end
set(gca,'YScale','log'); grid on;
xlabel('E_b/N_0 per uncoded bit (dB)'); ylabel('RMS EVM (%)');
semilogy(nan,nan,'ko','DisplayName','MATLAB Monte Carlo estimate');
title({'Figure 2. Reference-based EVM in complex AWGN', ...
    'Unit average symbol energy; no payload gain/phase fitting'});
legend('Location','northeast'); saveFigure(fig,outputDirectory,'evm_vs_ebno');

fig = figure('Visible','off','Color','w','Position',[100 100 1200 650]);
tiledlayout(1,2);
nexttile; hold on;
rates = [1/2 1/2 1/2 2/3];
for m=1:4
    snrSC = ebnoDB + 10*log10(log2(orders(m))*rates(m));
    plot(ebnoDB,snrSC,'Color',colors(m,:),'LineStyle',charStyle(m),'LineWidth',1.6, ...
        'DisplayName',sprintf('%s, R_c = %.3g',labels{m},rates(m)));
end
grid on; xlabel('Reference information-bit E_b/N_0 (dB)'); ylabel('Active-subcarrier SNR (dB)');
title({'(a) Useful constellation energy', 'E_{b,ref}=E_s/(kR_c); overhead excluded'}); legend('Location','northwest');
nexttile; hold on;
for m=1:4
    snrSample = ebnoDB + 10*log10(48*log2(orders(m))*rates(m)/80);
    plot(ebnoDB,snrSample,'Color',colors(m,:),'LineStyle',charStyle(m),'LineWidth',1.6, ...
        'DisplayName',sprintf('%s, R_c = %.3g',labels{m},rates(m)));
end
grid on; xlabel('DATA-inclusive E_b/N_0 (dB)'); ylabel('Time-sample SNR (dB)');
title({'(b) DATA energy includes pilots and CP', 'Preamble/header/idle costs excluded'});
legend('Location','northwest'); sgtitle('Figure 3. OFDM energy conventions: 64-point FFT, 16-sample CP, 48 DATA tones');
saveFigure(fig,outputDirectory,'ofdm_snr_conventions');

fig = figure('Visible','off','Color','w','Position',[100 100 900 600]);
counts = logspace(3,9,200);
loglog(counts,-expm1(log(0.05)./counts),'LineWidth',1.8, ...
    'DisplayName','Exact bound: 1 - 0.05^{1/N}'); hold on; grid on;
loglog(counts,3./counts,'--','LineWidth',1.2,'DisplayName','Rule-of-three approximation: 3/N');
xlabel('Compared independent bits with zero observed errors'); ylabel('One-sided 95% BER upper bound');
title({'Figure 4. Sensitivity when zero errors are observed', ...
    'Independent Bernoulli bits; bounds are not measured BER values'});
legend('Location','southwest');
saveFigure(fig,outputDirectory,'zero_error_confidence');

summary = struct('status','passed','kind','simulation_and_theory_not_antenna_measurement', ...
    'seedBase',20261016,'symbolsPerPoint',symbolsPerPoint, ...
    'maxRelativeErrorAgainstBerawgn',oracleRelativeError,'matlabVersion',version, ...
    'confidence','two-sided 95% Clopper-Pearson; zero-error markers use one-sided 95%', ...
    'sources',{{'MW-BER','MW-ANALYTIC','MW-SNR','MW-CI'}});
save(fullfile(outputDirectory,'theory_results.mat'),'results','theory','ebnoDB','summary');
writeText(fullfile(outputDirectory,'validation.json'),jsonencode(summary,PrettyPrint=true));
disp(summary);
end

function style = charStyle(index)
styles={'-','--',':','-.'}; style=styles{index};
end

function saveFigure(fig,folder,name)
set(findall(fig,'Type','axes'),'FontSize',11);
exportgraphics(fig,fullfile(folder,[name '.png']),'Resolution',180);
exportgraphics(fig,fullfile(folder,[name '.pdf']),'ContentType','vector');
close(fig);
end

function writeText(path,text)
file=fopen(path,'w'); assert(file>=0); cleaner=onCleanup(@()fclose(file));
fprintf(file,'%s\n',text);
end
