function summary = run_wlan_awgn(outputDirectory, packetsPerPoint)
%RUN_WLAN_AWGN Coded non-HT receiver simulation, explicitly schedule-assisted.
% Eb/N0 is DATA-inclusive (pilots+CP), excluding preamble/header/idle/pad costs.
% These are finite Monte Carlo results, not uncoded theory or RF measurements.
root=fileparts(fileparts(mfilename('fullpath')));
if nargin<1, outputDirectory=fullfile(root,'results','wlan_awgn'); end
if nargin<2, packetsPerPoint=12; end
if ~exist(outputDirectory,'dir'), mkdir(outputDirectory); end
selected=[0 2 4 6]; ebnoDB=0:4:24; dataBits=[24 48 96 192]; rows=[];
for r=1:4
    ref=load(fullfile(root,'results','reference',sprintf('wlan_rate_%d.mat',selected(r))));
    data=ref.tx_packet(ref.data_start+(1:ref.data_length)); signalPower=mean(abs(data).^2);
    for e=1:numel(ebnoDB)
        rng(20261016+100*selected(r)+e,'twister');
        sampleSNR=ebnoDB(e)+10*log10(dataBits(r)/80);
        variance=signalPower/10^(sampleSNR/10);
        errors=0; bits=0; packetErrors=0; sumError=0; sumReference=0;
        for n=1:packetsPerPoint
            noisy=ref.tx_packet+sqrt(variance/2)*(randn(size(ref.tx_packet))+1j*randn(size(ref.tx_packet)));
            result=recover_reference_packet(noisy,ref);
            errors=errors+result.errors; bits=bits+result.bits;
            packetErrors=packetErrors+(result.errors>0 || result.signalFailed);
            sumError=sumError+result.errorEnergy; sumReference=sumReference+result.referenceEnergy;
        end
        rows=[rows;selected(r) ebnoDB(e) sampleSNR errors bits errors/bits packetErrors ...
            packetsPerPoint packetErrors/packetsPerPoint sqrt(sumError/sumReference)]; %#ok<AGROW>
    end
end
results=array2table(rows,'VariableNames',{'rate_index','data_inclusive_ebno_db','sample_snr_db', ...
    'errors','bits','post_fec_ber','packet_errors','packets','per','evm_rms'});
writetable(results,fullfile(outputDirectory,'coded_wlan_awgn.csv'));
fig=figure('Visible','off','Color','w','Position',[100 100 1300 650]); tiledlayout(1,2);
colors=[0 0.447 0.741; 0.850 0.325 0.098; 0.2 0.6 0.3; 0.494 0.184 0.556];
styles={'-','--',':','-.'};
labels={'BPSK 1/2, 6 Mb/s','QPSK 1/2, 12 Mb/s','16-QAM 1/2, 24 Mb/s','64-QAM 2/3, 48 Mb/s'};
nexttile; hold on;
for r=1:4
    s=results(results.rate_index==selected(r),:); nonzero=s.errors>0;
    semilogy(s.data_inclusive_ebno_db(nonzero),s.post_fec_ber(nonzero),'-o', ...
        'Color',colors(r,:),'LineStyle',styles{r},'LineWidth',1.5,'DisplayName',labels{r});
    zero=~nonzero;
    semilogy(s.data_inclusive_ebno_db(zero),-expm1(log(0.05)./s.bits(zero)), ...
        'v','Color',colors(r,:),'LineStyle','none','HandleVisibility','off');
end
set(gca,'YScale','log'); grid on; ylim([1e-6 1]);
xlabel('DATA-inclusive E_b/N_0 (dB)'); ylabel('Post-FEC payload BER');
semilogy(nan,nan,'kv','DisplayName','Zero errors: nominal 95% upper limit');
title({'(a) Decoded payload bit errors', 'Circle = estimate; triangle = upper limit'});
legend('Location','southwest');
nexttile; hold on;
for r=1:4
    s=results(results.rate_index==selected(r),:);
    plot(s.data_inclusive_ebno_db,s.per,'-o','Color',colors(r,:),'LineStyle',styles{r},'LineWidth',1.5,'DisplayName',labels{r});
end
grid on; ylim([0 1]); xlabel('DATA-inclusive E_b/N_0 (dB)'); ylabel('Packet error fraction');
title({'(b) Payload mismatch or L-SIG failure',sprintf('%d packets/point; PER resolution = 1/%d',packetsPerPoint,packetsPerPoint)});
legend('Location','southwest');
sgtitle({'Figure 5. Coded legacy Wi-Fi in AWGN: 1000-byte PSDU', ...
    'Known timing/rate; noisy L-LTF ZF; no CFO or pilot tracking'});
set(findall(fig,'Type','axes'),'FontSize',11);
exportgraphics(fig,fullfile(outputDirectory,'coded_wlan_ber_per.png'),'Resolution',180);
exportgraphics(fig,fullfile(outputDirectory,'coded_wlan_ber_per.pdf'),'ContentType','vector'); close(fig);
summary=struct('kind','coded_WLAN_simulation_not_measurement','timing','known_boundary_and_rate', ...
    'packetsPerPoint',packetsPerPoint,'seedBase',20261016,'rates',selected,'points',height(results), ...
    'receiver','noisy L-LTF unsmoothed estimate; ZF; no CFO or pilot tracking in AWGN', ...
    'uncertainty','post-FEC errors are correlated; bit-binomial bounds are nominal only');
fid=fopen(fullfile(outputDirectory,'manifest.json'),'w'); assert(fid>=0);
fprintf(fid,'%s\n',jsonencode(summary,PrettyPrint=true)); fclose(fid); disp(summary);
end
