# Single-carrier simulation checks

Baseline: **1 Msymbol/s, four samples/symbol, 4 Msamples/s**. Six flat flowcharts containing only installed GNU Radio blocks. These are software simulations with zero carrier offset and no sample-rate mismatch.

| Modulation | RX noise (dBm over Fs) | Reference delay (bits) | Compared bits | Display BER, mean of windows | TX mean power (mW) |
| --- | ---: | ---: | ---: | ---: | ---: |
| BPSK | off | 34 | 250000 | 0 | 0.99963 |
| BPSK | -90.46 | 34 | 250000 | 0 | 0.99963 |
| QPSK | off | 68 | 250000 | 0 | 0.99963 |
| QPSK | -90.46 | 68 | 250000 | 0 | 0.99963 |
| 8PSK | off | 102 | 250000 | 0 | 0.99963 |
| 8PSK | -90.46 | 102 | 250000 | 0.000356 | 0.99963 |
| 4ASK | off | 68 | 250000 | 0 | 1.0009 |
| 4ASK | -90.46 | 68 | 250000 | 3.6e-05 | 1.0009 |
| 8ASK | off | 102 | 250000 | 0 | 1.0004 |
| 8ASK | -90.46 | 102 | 250000 | 0.05188 | 1.0004 |
| 16QAM | off | 136 | 250000 | 0 | 1.0022 |
| 16QAM | -90.46 | 136 | 250000 | 0.00678 | 1.0022 |

Each case verifies every XOR output bit against an independent TX/RX comparison and checks each Integrate/Multiply BER window. All six noiseless cases must have zero bit errors. The first 4096 output bits are excluded for filter and timing-loop startup.

BER is the fraction of errors in each nonoverlapping 10,000-bit window. It is not a cumulative counter. Differential encoding is enabled. Receiver noise is input-referred and integrated across Fs. Nominal energy ratios can be computed from the documented bandwidth convention; theoretical BER agreement is not claimed here.

The stock EVM block is decision-directed. Its RMS-smoothed display can underestimate error at poor SNR because the nearest constellation point can be the wrong transmitted point. The exported data-aided constellation figures additionally compare the actual transmitted and received symbols without decision bias.

## Adaptive equalizer and 2×2 dashboards

All six live flowcharts use six resizable tabs with four charts per tab in a 2×2 grid. Controls are packed using their actual native GRC sizes with 8 px gaps. No plot canvas has a forced square size. Editable blue boxed section headings identify the transmitter, channel, receiver, BER measurement, and diagnostic areas in GRC; open with antenna-grc for the large heading style.

The receiver now includes a stock 11-tap, one-sample/symbol, decision-directed LMS Linear Equalizer after timing recovery. A centered identity initialization adds five symbols to the reference delay. A stock Python Snippet initializes the taps through the public API; all filtering/adaptation uses native GNU Radio blocks. The live tap-magnitude chart displays the actual adapting coefficients. Defaults: channel_echo=0, eq_step=0.01, native LMS step=eq_step/(eq_taps*symbol_rms²).

A 16-QAM case with a power-normalized one-symbol echo of 0.25 voltage ratio and normalized input noise 0.10 measured **24.67% before EQ → 5.64% after EQ**, with observed BER 0 over 250,000 compared bits. EVM uses actual aligned TX symbols after a 1,024-symbol warmup, with no amplitude/phase fit; its averaging interval can include remaining LMS convergence. This single controlled case does not establish performance for arbitrary multipath or carrier offsets. [Capture values](equalizer_checks/16qam_noise_0.1.json).

![Four-panel equalizer dashboard](equalizer_dashboard.png)

Each I/Q eye dashboard shows TX, raw channel RX, middle (after timing/before EQ), and after EQ. TX/RX use actual 4-SPS waveform samples. Middle/post eyes are explicitly **display-only RRC reconstructions of 1-SPS symbol streams**, not measured oversampled receiver signals. Their interpolation branches never feed BER decoding. Raw waveforms in these exported dashboards are converted to RMS symbol units using known TX/path levels.

![I-eye dashboard](equalizer_eyes_i.png)

![Q-eye dashboard](equalizer_eyes_q.png)

Native GNU Radio Qt renders: [I-eye tab](live_dashboard_2.png), [constellations](live_dashboard_0.png), [BER/EVM/tap tab](live_dashboard_5.png). These show the actual resizable layout. Finite captures can finish before all live-sink refreshes; the numerical values above use the captured streams.

MATLAB independently recomputes native adaptive FIR outputs from captured per-symbol tap vectors and input samples, and reconstructs both RRC eye streams from saved symbols/taps. Sources: [GNU Radio Linear Equalizer](https://wiki.gnuradio.org/index.php/Linear_Equalizer), [GNU Radio LMS source](https://github.com/gnuradio/gnuradio/blob/v3.10.12.0/gr-digital/include/gnuradio/digital/adaptive_algorithm_lms.h).

## Link-budget power reference

[Three fixed-noise link-budget tests](link_budget_checks/summary.json) also verify that adding 10 dB TX power and 10 dB path loss preserves received power/BER, while reducing TX power at fixed loss/noise worsens BER.

IQ uses a power-wave convention: |IQ|² is milliwatts. TX average power defaults to 0 dBm, net path loss to 80 dB, and default RX noise to −100 dBm across the 4 MHz complex sample bandwidth. Received signal power is TX − net loss. The RX meter measures signal + noise. Validation cases explicitly set noise to their test values.

| Modulation | Set TX average (dBm) | Measured TX (dBm) | RX signal expectation (dBm) | RX total measured (dBm) | Sampled TX peak (dBm) | PAPR (dB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BPSK | 0.00 | -0.002 | -80.00 | -80.002 | 4.133 | 4.135 |
| QPSK | 0.00 | -0.002 | -80.00 | -80.002 | 3.937 | 3.939 |
| 8PSK | 0.00 | -0.002 | -80.00 | -80.002 | 3.854 | 3.855 |
| 4ASK | 0.00 | 0.004 | -80.00 | -79.996 | 6.464 | 6.460 |
| 8ASK | 0.00 | 0.002 | -80.00 | -79.998 | 7.395 | 7.393 |
| 16QAM | 0.00 | 0.009 | -80.00 | -79.991 | 6.290 | 6.280 |

Average and sampled peak meters use stock magnitude-squared, integration/max, and Log10 blocks. MATLAB independently validates their outputs and absolute TX/RX powers. Sample peaks at four samples/symbol are estimates of continuous-time PEP. These are simulated powers; no USRP output calibration has been performed. [Power controls and equations](../README.md#power-in-dbm-and-link-budgets).

## Data rate at 1 Msymbol/s

![Gross bit rate](data_rate.png)

Gross uncoded bit rate is symbol rate × log2(M). Rates are 1, 2, 3, 2, 3, and 4 Mbit/s respectively. These are not measured packet goodput. With rolloff 0.35, ideal RRC null-to-null bandwidth is 1.35 MHz (complex baseband edges ±0.675 MHz). [CSV](data_rate.csv), [vector PDF](data_rate.pdf), [independent MATLAB chart](matlab_data_rate.png).

## BER versus Eb/N0

![Measured BER versus Eb/N0](ber_vs_ebno.png)

Each point is one finite capture of the saved flowchart (about 250,000 compared bits) with receiver noise set from the requested Eb/N0 under the Fs noise-bandwidth convention. Error bars are exact 95% Clopper-Pearson intervals; open markers had zero errors and sit at the one-sided 95% upper bound. [Data](ber_sweep/ber_sweep.csv), [vector PDF](ber_vs_ebno.pdf).

![BER panels with references](ber_vs_ebno_panels.png)

Dashed: ideal synchronization with the same constellation, bit mapping and differential coding (NumPy). Grey: textbook coherent Gray-coded AWGN theory. Above a few dB the flowchart measurements lie on the ideal-sync reference; the gap to Gray theory is the cost of differential coding and the stock (non-Gray) ASK symbol order. At the lowest Eb/N0, BPSK, 4-ASK and 8-ASK lose timing/equalizer lock (BER near 0.5), which is real receiver behavior.

![EVM versus Es/N0](evm_vs_esno.png)

Data-aided EVM follows 100/sqrt(Es/N0) for every format wherever the receiver is locked, an independent check of the noise convention.

## BER and EVM at one receiver-noise setting

![Measured BER](ber_comparison.png)

![Data-aided EVM](evm_comparison.png)

All baseline runs use 0 dBm nominal conducted TX power, 80 dB net loss, and the same receiver noise power; decision-directed EVM can be optimistic when decisions are wrong. Noise and energy ratios use the documented Fs convention. Error bars are 95% Clopper-Pearson intervals; zero-error cases show the 95% upper bound.

## Independent MATLAB validation

MATLAB passed 16 actual capture cases: every XOR bit, BER window, stock per-symbol EVM, RMS smoothing, sample rate, gross bit rate, ideal RRC bandwidth, actual time-varying equalizer FIR output, and reconstructed eye waveforms. Maximum BER difference: 2.6e-09; maximum per-symbol EVM difference: 1.6e-05 percentage points. [MATLAB source](../matlab/validate_single_carrier.m), [machine-readable results](matlab_validation.json).

Stock EVM formula: [GNU Radio 3.10.12 source](https://github.com/gnuradio/gnuradio/blob/v3.10.12.0/gr-digital/lib/meas_evm_cc_impl.cc).

## RX SNR and Eb/N0

Live SNR uses measured TX average power minus known path loss and configured noise power over Fs. Eb/N0 adds 10 log10(Fs/bit_rate). These are known-reference link-budget readouts, not blind estimates from noisy RX samples. Noise disabled displays infinity. Defaults: SNR(Fs)=20 dB; Eb/N0=26.02, 23.01, 21.25, 23.01, 21.25, 20.00 dB across the six formats. The finite noisy test below uses −90.46 dBm noise and therefore different ratios.

![Configured RX ratios](rx_ratios.png)

## TX and RX constellation figures

TX symbols are the actual stock packing/differential-mapping monitor before pulse shaping. RX points are aligned with those TX symbols using the known latency, with no amplitude/phase fit. Dashed circles show the measured data-aided RMS error radius; they are not confidence contours or compliance limits.

![All six RX constellations](constellation_grid.png)

### BPSK symbols

![TX constellation](bpsk_tx_constellation.png)

![RX constellation](bpsk_rx_constellation.png)

### QPSK symbols

![TX constellation](qpsk_tx_constellation.png)

![RX constellation](qpsk_rx_constellation.png)

### 8PSK symbols

![TX constellation](8psk_tx_constellation.png)

![RX constellation](8psk_rx_constellation.png)

### 4ASK symbols

![TX constellation](4ask_tx_constellation.png)

![RX constellation](4ask_rx_constellation.png)

### 8ASK symbols

![TX constellation](8ask_tx_constellation.png)

![RX constellation](8ask_rx_constellation.png)

### 16QAM symbols

![TX constellation](16qam_tx_constellation.png)

![RX constellation](16qam_rx_constellation.png)

MATLAB checks TX symbol encoding, data-aided EVM, and SNR/Eb/N0 readouts in addition to the stock meters. SNR conversion: [MathWorks convertSNR](https://www.mathworks.com/help/comm/ref/convertsnr.html). EVM normalization: [MathWorks EVM](https://www.mathworks.com/help/comm/ref/comm.evm-system-object.html).

## Two-N210 flowcharts: software loopback check

The generated n210_* flowcharts were run with both UHD blocks replaced by a software channel modelling two free-running radios: 3000 Hz carrier offset, 2 ppm sample-clock offset, 12345.4-sample delay, 137 deg carrier phase, -40 dB path, Es/N0 25 dB. Bits are scored against the true transmitted data after acquisition. This is not a hardware measurement.

| Modulation | BER vs TX data | Flowchart BER display | MER (dB) | TX sampled peak (dBFS) | Pass |
| --- | ---: | ---: | ---: | ---: | --- |
| BPSK | 0 | 0 | 24.4 | -10.9 | yes |
| QPSK | 0 | 0 | 24.5 | -11.0 | yes |
| 8PSK | 0 | 0 | 24.6 | -11.1 | yes |
| 4ASK | 0 | 0 | 24.6 | -8.4 | yes |
| 8ASK | 0 | 0 | 24.6 | -7.5 | yes |
| 16QAM | 0 | 0 | 23.7 | -8.9 | yes |

## Actual GRC canvas exports

### BPSK

![BPSK GRC canvas](bpsk_flowchart.png)

### QPSK

![QPSK GRC canvas](qpsk_flowchart.png)

### 8PSK

![8PSK GRC canvas](8psk_flowchart.png)

### 4ASK

![4ASK GRC canvas](4ask_flowchart.png)

### 8ASK

![8ASK GRC canvas](8ask_flowchart.png)

### 16QAM

![16QAM GRC canvas](16qam_flowchart.png)

Reference: [GNU Radio tutorial](https://wiki.gnuradio.org/index.php?title=M-ASK_Mod_and_Demod_and_QAM-M_Mod_and_Demod), read from the locally downloaded HTML and figures.
