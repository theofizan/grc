function report = validate_wifi_profile(configPath)
% Editing guide: docs/MODULAR_FLOWGRAPHS.md. Inputs/outputs use the units stated below.
%VALIDATE_WIFI_PROFILE Check the planned legacy OFDM profile against PHY tables.
% This checks configuration, not waveform generation, BER/EVM, or compliance.
% wlanNonHTConfig rate indices are MATLAB labels, not on-air L-SIG RATE bits.
% Sources: IEEE 802.11a-1999 Tables 78/79; wlanNonHTConfig and wlanNonHTOFDMInfo.

if nargin < 1
    projectRoot = fileparts(fileparts(mfilename('fullpath')));
    configPath = fullfile(projectRoot, 'configs', 'wifi_nonht_defaults.json');
end
config = jsondecode(fileread(configPath));
phy = config.phy;
assert(phy.sample_rate_hz == 20e6 && phy.channel_bandwidth_hz == 20e6);
assert(phy.fft_length == 64 && phy.cyclic_prefix_samples == 16);
assert(phy.data_subcarriers == 48 && phy.pilot_subcarriers == 4);
assert(isequal(phy.pilot_subcarrier_indices(:), [-21; -7; 7; 21]));
assert(isequal(phy.active_subcarrier_ranges, [-26 -1; 1 26]));
assert(abs(phy.sample_rate_hz / phy.fft_length - phy.subcarrier_spacing_hz) < 1e-6);
assert(abs(phy.fft_length / phy.sample_rate_hz - phy.useful_symbol_duration_s) < 1e-12);
assert(abs(phy.cyclic_prefix_samples / phy.sample_rate_hz - phy.guard_interval_s) < 1e-12);
assert(abs((phy.fft_length + phy.cyclic_prefix_samples) / phy.sample_rate_hz ...
    - phy.ofdm_symbol_duration_s) < 1e-12);
assert(phy.psdu_length_bytes >= 1 && phy.psdu_length_bytes <= 4095 ...
    && mod(phy.psdu_length_bytes, 1) == 0);
assert(phy.scrambler_initial_state >= 1 && phy.scrambler_initial_state <= 127 ...
    && mod(phy.scrambler_initial_state, 1) == 0);

modulations = {'BPSK','BPSK','QPSK','QPSK','16-QAM','16-QAM','64-QAM','64-QAM'};
codeRates = {'1/2','3/4','1/2','3/4','1/2','3/4','2/3','3/4'};
expectedMbps = [6 9 12 18 24 36 48 54];
expectedDataBits = [24 36 48 72 96 144 192 216];
assert(numel(phy.rates) == 8);
for index = 1:8
    row = phy.rates(index);
    assert(row.rate_index == index - 1);
    assert(strcmp(row.modulation, modulations{index}));
    assert(strcmp(row.code_rate, codeRates{index}));
    assert(row.data_bits_per_ofdm_symbol == expectedDataBits(index));
    assert(row.phy_rate_mbps == expectedMbps(index));
    assert(abs(row.data_bits_per_ofdm_symbol / phy.ofdm_symbol_duration_s ...
        - row.phy_rate_mbps * 1e6) < 1e-6);
end

report = struct('profile', config.profile, 'configurationChecksPassed', true, ...
    'wlanToolboxCrossCheck', 'not available', 'waveformValidated', false);
if exist('wlanNonHTConfig', 'class') == 8 && exist('wlanNonHTOFDMInfo', 'file') == 2
    for rate = 0:7
        cfg = wlanNonHTConfig('Modulation', 'OFDM', 'ChannelBandwidth', 'CBW20', ...
            'MCS', rate, 'PSDULength', phy.psdu_length_bytes);
        info = wlanNonHTOFDMInfo('NonHT-Data', cfg);
        assert(info.FFTLength == phy.fft_length && info.CPLength == phy.cyclic_prefix_samples);
        assert(info.SampleRate == phy.sample_rate_hz);
        assert(numel(info.DataIndices) == phy.data_subcarriers);
        assert(numel(info.PilotIndices) == phy.pilot_subcarriers);
        pilotBins = info.ActiveFrequencyIndices(info.PilotIndices);
        assert(isequal(pilotBins(:), phy.pilot_subcarrier_indices(:)));
    end
    report.wlanToolboxCrossCheck = 'passed';
end
disp(report);
end
