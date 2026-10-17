function summary = validate_single_carrier(resultsDirectory)
%VALIDATE_SINGLE_CARRIER Check captured GNU Radio bits, EVM, and data rates.
% Run after python scripts/run_all.py, or let that runner call this function.
% All comparisons use the actual samples saved by the running GRC flowchart.
if nargin < 1
    projectRoot = fileparts(fileparts(mfilename('fullpath')));
    resultsDirectory = fullfile(projectRoot, 'results');
end
fixtures = dir(fullfile(resultsDirectory, '*_noise_*.mat'));
assert(numel(fixtures) == 12, 'Expected six modulations at two noise settings.');
% Include the three additional fixed-noise physical link-budget scenarios.
physicalCases = dir(fullfile(resultsDirectory,'link_budget_checks','**','*_noise_*.mat'));
equalizerCases = dir(fullfile(resultsDirectory,'equalizer_checks','*_noise_*.mat'));
fixtures = [fixtures; physicalCases; equalizerCases];
maxBerDifference = 0;
maxEvmDifference = 0;
maxRmsDifference = 0;

for caseIndex = 1:numel(fixtures)
    data = load(fullfile(fixtures(caseIndex).folder, fixtures(caseIndex).name));

    % 1. Delay the clean TX reference by the measured receive-chain latency.
    % Convert Python's zero-based start index into MATLAB's one-based index.
    rxStart = double(data.warmup_bits) + 1;
    txStart = rxStart - double(data.reference_delay_bits);
    count = numel(data.xor_errors);
    expectedErrors = data.tx_bits(txStart:txStart+count-1) ~= ...
                     data.rx_bits(rxStart:rxStart+count-1);
    assert(isequal(expectedErrors, logical(data.xor_errors)), ...
        'MATLAB disagrees with the GNU Radio XOR output.');

    % 2. Each Integrate/Multiply output is errors / compared bits in one window.
    windowBits = double(data.ber_window_bits);
    windows = numel(data.ber_windows);
    compared = reshape(expectedErrors(1:windows*windowBits), windowBits, windows);
    expectedBer = mean(compared, 1)';
    berDifference = max(abs(expectedBer-double(data.ber_windows)));
    assert(berDifference < 1e-6, 'BER window calculation differs.');
    maxBerDifference = max(maxBerDifference, berDifference);

    % 3. Reproduce the STOCK decision-directed EVM measurement independently.
    % Reference power is the average power of the complete constellation.
    % This is not EVM against known transmitted symbols at poor SNR.
    received = double(data.received_symbols(:));
    points = double(data.constellation_points(:));
    distanceSquared = abs(received-points.').^2;
    nearestErrorPower = min(distanceSquared, [], 2);
    expectedEvm = 100*sqrt(nearestErrorPower/mean(abs(points).^2));
    evmDifference = max(abs(expectedEvm-double(data.evm_percent)));
    assert(evmDifference < 2e-4, 'Stock EVM calculation differs.');
    maxEvmDifference = max(maxEvmDifference, evmDifference);

    % 4. The RMS block smooths squared EVM: P[n]=a*x[n]^2+(1-a)*P[n-1].
    % GNU Radio uses single precision, MATLAB uses double: allow rounding.
    smoothing = 0.001;
    expectedRms = sqrt(filter(smoothing, [1 -(1-smoothing)], ...
                       double(data.evm_percent).^2));
    rmsDifference = max(abs(expectedRms-double(data.evm_rms_percent)));
    assert(rmsDifference < 0.005, 'RMS smoothing calculation differs.');
    maxRmsDifference = max(maxRmsDifference, rmsDifference);

    % Physical IQ convention: |IQ|^2 is milliwatts, so dBm=10*log10(mW).
    % The native meters average linear power before taking a logarithm.
    streams = {data.tx_iq, data.rx_iq};
    meterValues = {data.tx_power_windows_dbm, data.rx_power_windows_dbm};
    for streamIndex = 1:2
        iq = double(streams{streamIndex});
        meter = double(meterValues{streamIndex});
        powerWindows = reshape(abs(iq(1:numel(meter)*4096)).^2,4096,[]);
        expectedPowerDbm = 10*log10(mean(powerWindows,1))';
        assert(max(abs(expectedPowerDbm-meter)) < 0.001, 'dBm power meter differs.');
    end
    txAverage = 10*log10(mean(abs(double(data.tx_iq(4097:end))).^2));
    rxAverage = 10*log10(mean(abs(double(data.rx_iq(4097:end))).^2));
    assert(abs(txAverage-data.tx_measured_dbm)<1e-5);
    assert(abs(rxAverage-data.rx_measured_dbm)<1e-5);
    assert(abs(txAverage-double(data.tx_power_dbm))<0.05, 'TX power calibration failed.');
    noiseMw = double(data.noise_enabled)*10^(data.rx_noise_dbm/10);
    expectedRxMw = 10^((double(data.tx_power_dbm)-double(data.path_loss_db))/10)+noiseMw;
    assert(abs(rxAverage-10*log10(expectedRxMw))<0.08, 'Link budget failed.');
    peakMeter = double(data.tx_peak_windows_dbm);
    powerWindows = reshape(abs(double(data.tx_iq(1:numel(peakMeter)*4096))).^2,4096,[]);
    assert(max(abs(10*log10(max(powerWindows,[],1))'-peakMeter))<0.001);
    assert(abs(10*log10(max(abs(double(data.tx_iq(4097:end))).^2))-data.tx_sample_peak_dbm)<1e-5);

    % Validate the actual TX symbol monitor from the original bits and the
    % differential-encoding equation, independently of its GNU Radio blocks.
    k = double(data.bits_per_symbol);
    points = double(data.constellation_points(:));
    symbolCount = numel(data.tx_symbols);
    bitGroups = reshape(double(data.tx_bits(1:symbolCount*k)),k,[])';
    words = bitGroups*(2.^(k-1:-1:0))';
    encodedWords = mod(cumsum(words),2^k);
    assert(max(abs(points(encodedWords+1)-double(data.tx_symbols)))<1e-6);
    txReference = double(data.aligned_tx_symbols);
    rxAligned = double(data.aligned_rx_symbols);
    referenceEvm = 100*sqrt(mean(abs(rxAligned-txReference).^2)/mean(abs(txReference).^2));
    assert(abs(referenceEvm-data.reference_evm_percent)<5e-5);
    assert(data.evm_guide_percent>0);
    % SNR is over Fs; Eb/N0 includes the Fs/bit_rate conversion. Readouts
    % use measured TX power and the known loss/noise, not RX total power.
    if data.noise_enabled
        nominalSnr = double(data.tx_power_dbm)-double(data.path_loss_db)-double(data.rx_noise_dbm);
        ebnoOffset = 10*log10(double(data.sample_rate_hz)/double(data.gross_bit_rate_bps));
        assert(abs(data.nominal_rx_snr_db-nominalSnr)<1e-9);
        assert(abs(data.nominal_rx_ebno_db-(nominalSnr+ebnoOffset))<1e-9);
        oracleEbno = convertSNR(nominalSnr,'snr','ebno',SamplesPerSymbol=4,BitsPerSymbol=k);
        assert(abs(oracleEbno-data.nominal_rx_ebno_db)<1e-9);
        expectedSnr = double(data.tx_power_windows_dbm)-double(data.path_loss_db)-double(data.rx_noise_dbm);
        assert(max(abs(expectedSnr-double(data.measured_rx_snr_windows_db)))<1e-4);
        assert(max(abs(expectedSnr+ebnoOffset-double(data.measured_rx_ebno_windows_db)))<1e-4);
    else
        assert(all(isinf(data.measured_rx_snr_windows_db)));
        assert(all(isinf(data.measured_rx_ebno_windows_db)));
    end

    % Recompute the time-varying FIR output using the actual per-symbol
    % adaptive taps. This checks filtering independently of GNU Radio.
    eqInput = double(data.eq_input_excerpt(:));
    tapHistory = double(data.eq_tap_history);
    tapCount = size(tapHistory,2);
    padded = [zeros(tapCount-1,1); eqInput];
    expectedEq = zeros(numel(eqInput),1);
    for tapIndex=1:tapCount
        offset=tapIndex;
        if ~data.eq_taps_oldest_first, offset=tapCount-tapIndex+1; end
        expectedEq=expectedEq+tapHistory(:,tapIndex).*padded(offset:offset+numel(eqInput)-1);
    end
    assert(max(abs(expectedEq-double(data.eq_output_excerpt)))<2e-5);
    % Eye views after timing/EQ are explicitly reconstructed from 1-SPS
    % symbols. Validate the display interpolation, rather than calling it a
    % raw oversampled receiver eye.
    stages={data.pre_eq_symbols,data.received_symbols};
    eyeTraces={data.middle_eye_waveform,data.after_eye_waveform};
    for stage=1:2
        observed=double(eyeTraces{stage});
        samples=zeros(numel(observed),1);
        symbols=double(stages{stage});
        count=numel(samples(1:4:end));samples(1:4:end)=symbols(1:count);
        reconstructed=filter(double(data.eye_reconstruction_taps),1,samples);
        assert(max(abs(reconstructed-observed))<2e-5);
    end

    % 5. Gross bit rate, waveform sampling rate, and ideal RRC bandwidth.
    % There is no FEC or packet overhead in these single-carrier examples.
    assert(data.gross_bit_rate_bps == data.symbol_rate_hz*data.bits_per_symbol);
    assert(data.sample_rate_hz == 4*data.symbol_rate_hz);
    assert(abs(data.rrc_bandwidth_hz-1.35*data.symbol_rate_hz) < 1e-6);
end

% Independently draw the baseline rate chart in MATLAB.
labels = {'BPSK','QPSK','8-PSK','4-ASK','8-ASK','16-QAM'};
bitsPerSymbol = [1 2 3 2 3 4];
symbolRate = 1e6;
grossRateMbps = symbolRate*bitsPerSymbol/1e6;
fig = figure('Visible','off','Color','w','Position',[100 100 720 720]);
bar(categorical(labels,labels),grossRateMbps);
ylabel('Gross uncoded bit rate (Mbit/s)');
xlabel('Modulation'); grid on; pbaspect([1 1 1]);
title({'Single-carrier gross data rate', ...
       '1 Msymbol/s; 4 Msamples/s; payload goodput is not measured'});
exportgraphics(fig,fullfile(resultsDirectory,'matlab_data_rate.png'),'Resolution',180, ...
    'Units','inches','Width',7,'Height',7,'PreserveAspectRatio','on');
exportgraphics(fig,fullfile(resultsDirectory,'matlab_data_rate.pdf'),'ContentType','vector', ...
    'Units','inches','Width',7,'Height',7,'PreserveAspectRatio','on');
close(fig);
summary = struct('status','passed','cases',numel(fixtures), ...
    'maxBerDifference',maxBerDifference,'maxEvmPercentDifference',maxEvmDifference, ...
    'maxRmsPercentDifference',maxRmsDifference,'symbolRateHz',symbolRate);
file = fopen(fullfile(resultsDirectory,'matlab_validation.json'),'w');
assert(file >= 0);
fprintf(file,'%s\n',jsonencode(summary,PrettyPrint=true)); fclose(file);
disp(summary);
end
