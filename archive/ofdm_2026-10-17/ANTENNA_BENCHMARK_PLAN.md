# Antenna BER and EVM benchmark plan

Current agreed scope: **fixed average TX power, one TX stream / one RX stream, known-rate PHY bursts, primary pre-FEC BER + EVM + received power**. No Wi-Fi networking stack or MIMO processing is required. Two complete live SISO GRC labs now cover modulation/channel/reception and in-graph metrics with Qt constellation, spectrum, waterfall and time plots. See [SISO_LABS.md](docs/SISO_LABS.md) and the [primary report](results/REPORT.md); broader post-FEC/PER and adaptive acquisition ideas below are optional extensions.

Status: revised October 16, 2026. Software package implemented: cited equations and bibliography, exact AWGN theory/charts, Python/MATLAB metric validation, MATLAB-generated non-HT reference packets, seven GRC graphs, known-schedule OFDM analysis, and mock steering. RF commissioning, autonomous acquisition/tracking, and the real steering adapter remain future work. Start with [README.md](README.md) and [docs/VALIDATION.md](docs/VALIDATION.md) for current execution evidence.

## 1. Objective and measurement scope

Build a repeatable USRP link that compares the antenna under test (AUT) with a reference antenna using pre-FEC and post-FEC BER, packet error rate, and reference-based RMS EVM. Use a legacy IEEE 802.11a/g non-HT OFDM PHY baseline with configurable beam steering. Support Python automation, inspectable GNU Radio Companion (GRC) flowgraphs, and independent MATLAB validation of the same recorded data.

BER and EVM characterize the complete communications link. Attribute differences to the AUT by substituting one antenna at a time while controlling waveform, transmitted power, radios, cables, position, polarization, and receiver settings. Record received power as well: symbol amplitude normalization used for EVM removes absolute link gain. Absolute antenna gain, efficiency, impedance match, and radiation pattern require additional measurements or calibration beyond BER/EVM.

## 2. Initial waveform contract

Use legacy non-HT OFDM as the primary paper profile, targeting the legacy OFDM provisions in IEEE Std 802.11-2020, Clause 17. This provides BPSK, QPSK, 16-QAM, and 64-QAM without the additional complexity of HT/VHT/HE/EHT formats. Retain single-carrier uncoded experiments for algorithm debugging and theory checks. Keep 8-PSK optional and explicitly outside the Wi-Fi profile.

Proposed initial parameters, subject to the antenna bandwidth and radio capabilities:

| Parameter | Initial choice |
| --- | --- |
| Channel bandwidth / baseband sampling | 20 MHz / 20 MS/s |
| FFT / DATA cyclic prefix | 64 / 16 samples |
| Data / pilot subcarriers | 48 / 4; signed pilot bins -21, -7, 7, 21 |
| Subcarrier spacing | 312.5 kHz |
| Useful OFDM symbol / guard interval | 3.2 / 0.8 microseconds |
| Total DATA symbol duration | 4 microseconds |
| Coding | Constraint-length-7 BCC with rate-specific puncturing |
| Framing | L-STF, L-LTF, L-SIG, DATA |
| PSDU size | 1000 bytes; distinguish PSDU length from application payload |
| Center frequency | 5.18 GHz placeholder; replace for the actual antenna band |
| Steering | Azimuth -60 to +60 degrees in 10-degree steps; elevation 0 |
| Settling / command deadline | Additional 0.25 s / total 5 s, provisional |
| Acquisition | 1000 packets per point, 3 repetitions; fixed receiver gain |

The machine-readable defaults are in `configs/wifi_nonht_defaults.json`. They configure the experiment but do not themselves generate a waveform; the current reference exporter uses MATLAB WLAN Toolbox. The zero TX gain and 20 dB RX gain are placeholders, not calibrated powers. A 0.5 digital peak-amplitude limit provides provisional headroom; the reference exporter uses a common scale across rates. Hardware geometry and daughterboard selection remain unset rather than invented. The smaller software-validation packet counts and the 2000-sample replay idle gap are documented separately in `docs/VALIDATION.md`; they are not the proposed RF acquisition counts or MAC timing.

| Local rate index | Modulation | Code rate | PHY rate at 20 MHz |
| --- | --- | --- | --- |
| 0 | BPSK | 1/2 | 6 Mbit/s |
| 1 | BPSK | 3/4 | 9 Mbit/s |
| 2 | QPSK | 1/2 | 12 Mbit/s |
| 3 | QPSK | 3/4 | 18 Mbit/s |
| 4 | 16-QAM | 1/2 | 24 Mbit/s |
| 5 | 16-QAM | 3/4 | 36 Mbit/s |
| 6 | 64-QAM | 2/3 | 48 Mbit/s |
| 7 | 64-QAM | 3/4 | 54 Mbit/s |

The local indices match MATLAB `wlanNonHTConfig.MCS`; they are not the transmitted L-SIG RATE bit field or HT/VHT MCS numbering. Start with indices 0, 2, 4, 6, then cover all eight rates. These are PHY rates, not application throughput. Compare antennas at the same selected rate, bandwidth, and transmitted average power.

Implement and independently verify scrambling, convolutional coding/puncturing, interleaving, bit-to-constellation mapping, pilot polarity progression, training fields, L-SIG encoding, SERVICE/tail/pad handling, OFDM bin placement, FFT scaling, and waveform windowing. A generic GNU Radio OFDM block chain is not automatically an IEEE 802.11 PHY. Do not add custom on-air PHY headers for experiment metadata; keep metadata out of band or in a documented PSDU payload.

Use the description **"legacy IEEE 802.11 OFDM-based experimental PHY"** until golden-vector and packet cross-decoding validation is complete. Full Wi-Fi interoperability or certification is outside the initial scope. MAC contention, association, acknowledgements, and retransmissions are not implemented by a fixed laboratory packet schedule. Formal conformance statements require the selected edition's complete normative measurement procedures; published transmitter EVM limits are not automatic pass/fail limits for an antenna measured through a radio channel.

Store exact payload bits, symbol indices, constellation points, and training sequences in portable golden vectors. Do not assume equal random seeds produce the same sequence in Python and MATLAB.

## 3. Hardware and physical setup

Preferred arrangement: two X310-class radios, one TX and one RX, with suitable RF daughterboards. The X310 motherboard does not determine the frequency range on its own; daughterboard selection depends on the antenna band, bandwidth, and required TX/RX functionality.

One X310 with suitable transceiver hardware can support an initial local TX/RX setup. Treat common-clock operation and transmitter leakage as characteristics of that setup. A physically separated, independently clocked link is a later validation condition.

Use shared 10 MHz reference and PPS when available to reduce clock uncertainty and support repeatable timing. They do not eliminate RF phase ambiguity or all residual synchronization work. Also verify operation without shared references if that matches the intended application.

Verify streaming before collecting RF data. At 20 MS/s, sc16 transport carries approximately 80 MB/s per complex stream before overhead; host complex float32 storage uses 160 MB/s per stream. Prefer a verified 10 Gigabit Ethernet connection for margin, especially for simultaneous streams. A single 1 Gigabit Ethernet stream may fit but needs measured validation. If the host cannot sustain this, first use file-based simulation or a separately labeled reduced-rate debug profile; do not silently slow a 20 MHz waveform and retain its timing/rate claims.

Measurement sequence:

1. Software-only loopback with a known channel.
2. TX-to-RX coaxial connection through calculated attenuation, respecting the selected receiver's input rating. Establish radio/receiver EVM floor, clipping limits, linear operating range, and packet reliability.
3. Reference antenna over the air with fixed geometry.
4. Substitute the AUT at one end; retain the same counterpart antenna, mounting reference, cables, and settings.
5. Interleave reference and AUT runs to estimate environmental drift and repeatability.

Define distance from antenna dimensions and wavelength, then assess reflections and interference in the available test environment. For an appropriate far-field measurement, use the conventional 2D^2/lambda boundary as one design check, together with wavelength-scale separation and the actual antenna geometry. A chamber or controlled line-of-sight range is preferable for attributing differences to the antenna.

Calibrate conducted TX power and cable/attenuator losses when reporting dBm. Otherwise label USRP gain settings and measured sample power honestly as settings and dBFS/relative measurements. Keep normalized waveform power consistent across modulation formats, with sufficient headroom for waveform peaks.

## 4. Software architecture

Use GRC for signal-chain visibility and interactive operation; use Python to automate runs and maintain shared GNU Radio processing blocks. Generated Python from GRC is a build product; retain the .grc sources as the editable flowgraph definitions.

Current software entry points:

```text
configs/wifi_nonht_defaults.json  PHY and proposed RF study defaults
antenna_bench/math.py             Exact theory, mapping, BER/EVM/confidence
antenna_bench/wlan.py             Independent known-schedule OFDM scoring
grc/awgn_symbol_benchmark.grc      Uncoded finite symbol/noise diagnostic
grc/wlan_reference_channel.grc    True reference PPDU through AWGN
grc/wlan_ofdm_fft.grc             Visible DATA extraction, CP removal, FFT
grc/usrp_wifi_tx.grc              UHD reference transmitter; compiled only
grc/usrp_wifi_rx.grc              UHD finite capture; compiled only
scripts/run_all.py                Reproduce all software evidence
scripts/analyze_symbols.py        Score symbol-rate GRC files
scripts/analyze_wlan.py           OFDM EVM and mapped pre-FEC BER
antenna_steering.py               Backend interface, mock controller, JSONL CLI
matlab/run_theory.m               Exact theory and uncoded Monte Carlo charts
matlab/validate_python_results.m  Shared-symbol metric validation
matlab/export_wlan_reference.m    Generate all eight legacy reference rates
matlab/analyze_wlan_capture.m     Independent OFDM/post-FEC validation
matlab/run_wlan_awgn.m            Separate coded WLAN BER/PER simulation
docs/                            Equations, sources, methods, commands, limits
references.bib                   Paper bibliography
results/                         Logs, hashes, figures, CSV/MAT/JSON, IQ
```

Target hardware receiver processing (the current software scorer instead uses supplied packet boundaries/rate/length):

```text
IQ input -> L-STF detection/coarse CFO -> L-LTF timing/fine CFO/channel estimate
         -> L-SIG decode -> CP removal / FFT -> per-subcarrier equalization
         -> pilot phase tracking -> DATA symbols -> reference-based EVM
         -> demapping / deinterleaving -> pre-FEC coded-bit BER
         -> depuncturing / Viterbi / descrambling -> post-FEC payload BER
         -> frame integrity checks / packet statistics
```

Treat this as a functional diagram; actual acquisition and tracking stages may be interleaved. Validate packet detection, pilot tracking, frequency correction, and equalization over the planned OFDM operating range rather than reusing a single-carrier Costas loop unchanged.

Resolve sample/FFT timing, frequency offset, phase ambiguity, frame number, and bit order explicitly. Use L-LTF channel estimates and pilot-derived common phase correction. Begin with a fixed documented one-tap-per-subcarrier equalizer, and keep payload-driven adaptive corrections out of the primary metric. Save channel estimates, per-subcarrier noise enhancement and received power so equalization does not hide steering-dependent attenuation or nulls.

## 5. Metric definitions

### BER

Post-FEC BER = erroneous descrambled payload bits / compared payload bits. Pre-FEC BER compares hard decisions at a defined coded-bit stage with the exact transmitted coded bits. Align both sides consistently around interleaving and puncturing; never count punctured, untransmitted positions as received bits. Exclude SERVICE/tail/pad bits from payload BER and state the scored PSDU/application bit interval.

Compare aligned payloads against the transmitted bits using frame identifiers. Count bits from aligned frames regardless of payload CRC outcome. Do not discard corrupted payloads before computing BER.

For frames that cannot be aligned or acquired, record erasures and missed frames separately; do not silently remove these failures from the report. Report BER together with packet error rate, acquisition success, expected/received frame counts, CRC failures, and useful throughput. State that payload BER is conditional on having an alignable payload. Lost frames have unknown bit contents, so do not arbitrarily assign them a BER of zero or one-half.

Choose fixed packet counts for reportable measurement points: initially 1000 transmitted packets with 1000-byte PSDUs per point and repetition. This transmits 8 million PSDU bits before excluding unscored headers/FCS or unalignable packets. Keep expected, observed, and scored denominators distinct. Increase counts where the desired BER sensitivity requires it. For independent bit errors, use binomial confidence intervals. With zero errors, the one-sided 95% upper bound is 1 - 0.05^(1/N), approximately 3/N; label the observation as zero errors in N bits with an upper bound, rather than proof of zero BER.

Over-the-air errors may be correlated. Preserve per-frame statistics and use repeated runs or block-based uncertainty estimates rather than relying solely on an independent-bit model.

### EVM

For the aligned, equalized DATA symbols r[k] and actual transmitted reference symbols s[k], scored on the 48 data subcarriers across the selected DATA OFDM symbols:

EVM_rms = sqrt(sum(abs(r - s)^2) / sum(abs(s)^2))

EVM_percent = 100 * EVM_rms

EVM_dB = 20 * log10(EVM_rms)

Normalize by average reference-signal power, with identical payload masks and normalization in all implementations. Apply nuisance delay, frequency, phase, and scalar channel corrections according to a documented receiver policy using preamble/training/pilots. Do not fit the receiver to the known payload or allow arbitrary payload equalization to minimize the reported error.

Use transmitted references rather than nearest-decision constellation estimates for the primary EVM measurement; wrong decisions must remain errors. Report the compensation/equalization mode with every result. Retain per-packet, per-subcarrier, and per-OFDM-symbol EVM. Aggregate by summing squared error and reference energies before taking the square root; do not average EVM percentages or dB values indiscriminately. Report pre-equalizer diagnostics separately from the primary equalized EVM, which is a receiver/link metric rather than a transmitter certification measurement.

Record received power independently of EVM. Do not infer calibrated SNR or Eb/N0 from USRP gain settings or EVM alone. In AWGN simulation, define whether SNR refers to time-domain samples or active DATA subcarriers. An Eb/N0 axis must explicitly account for modulation, code rate, pilot/guard occupancy, CP, and the selected treatment of preamble/header energy. Do not compare coded OFDM post-FEC BER directly against uncoded single-carrier theory.

## 6. MATLAB verification

MATLAB is an independent reference, with two levels of validation:

1. **Metric validation:** load exactly the same reference bits, recovered bits, aligned RX symbols, TX symbols, and scoring masks used by Python/GRC. Independently reproduce error counts, denominators, EVM normalization, and conversions. This validates calculations but does not validate the receiver DSP that produced those symbols.
2. **Receiver validation:** independently replay selected raw IQ captures through MATLAB acquisition and synchronization, then compare recovered payloads and metric results. Allow documented numerical and estimator differences; inspect mismatches at each processing stage.

Implement the fundamental metric equations directly in MATLAB. If Communications Toolbox is available, cross-check against comm.EVM, bit-error calculations, berconfint, and applicable berawgn results for the uncoded diagnostic baseline. If WLAN Toolbox is available, use wlanNonHTConfig, wlanWaveformGenerator, and corresponding recovery functions as an independent packet reference. Match PSDU bits, scrambler state, mapping, FFT scaling, windowing, and padding before demanding sample-level equality. Cross-decode Python-generated packets in MATLAB and MATLAB-generated packets in the Python/GRC receiver. Without WLAN Toolbox, retain basic MATLAB metric checks and independently sourced packet vectors, and state the reduced validation scope.

`matlab/validate_wifi_profile.m` checks configured timings, subcarriers, and rate tables. `run_theory.m` validates exact uncoded theory, `validate_python_results.m` independently checks shared symbol metrics, and the reference exporter plus `analyze_wlan_capture.m` validate all eight rates with a known packet schedule. Python's independent OFDM metrics, MATLAB's hard WLAN demapper, and MATLAB's post-FEC decoder are checked on the same GRC captures. Autonomous acquisition/tracking and a Python-generated PPDU remain unimplemented.

Portable recordings: JSON metadata, CSV run/frame summaries, and HDF5 arrays using explicit real/imaginary datasets for complex values. Raw GNU Radio IQ files may also be retained with declared dtype, endianness, sample rate, and sample indexing. Save waveform/configuration hashes and library versions.

Verification gates:

- Noiseless golden vectors: exact mapping and recovered bit agreement; EVM limited by the documented numerical precision and filter/transient handling.
- Controlled symbol perturbations: Python and MATLAB reproduce known EVM, including gain/phase cases under the specified compensation policy.
- AWGN: BER agrees statistically with the applicable coherent modulation theory; symbol-rate EVM follows the expected noise scaling under the stated normalization.
- Impairments: delay, fractional timing offset, carrier-frequency offset, phase rotations, sample-rate offset, clipping, IQ imbalance, and multipath expose expected behavior and acquisition failures.
- Capture replay: results are reproducible without radio hardware.
- Cabled RF baseline: stable operation with no unaccounted stream loss or clipping across the planned operating region.

Set numerical tolerances from stored precision and the exact operation being compared. Require identical error counts when both implementations score the same bit vectors; do not use an arbitrary percent tolerance for BER counts.

## 7. Experiment matrix and outputs

Begin with non-HT BPSK rate 0 at one frequency and boresight. Then cover one rate per modulation and the full legacy rate set, followed by beam-angle, frequency, transmit-power/attenuation, distance, and physical-orientation sweeps. Avoid expanding all dimensions simultaneously before the receiver is proven.

Use two distinct comparison modes:

- **Fixed transmitted power and geometry:** compares practical link performance, including antenna link gain and sensitivity.
- **Matched calibrated received power:** a secondary diagnostic to investigate signal distortion versus signal-strength differences. Record the adjustment and keep this separate from the fixed-power comparison.

For each point, retain modulation, rate, actual RF/sample settings, reference/AUT identity, mount/orientation/polarization, distance, power information, payload counts, confidence limits, packet outcomes, EVM, synchronization estimates, clipping statistics, USRP overflows/underflows, and run timestamps. Add steering command ID, requested angle, reported angle when available, beam/codebook ID, frequency-dependent calibration ID, readiness and settling timestamps, and simulated/hardware status. Flag affected intervals and rerun invalid hardware-stream points; keep these distinct from genuine radio-link packet losses.

Begin with at least three interleaved A/B repetitions per selected point; refine repetition counts after measuring variability. Export BER and packet-error curves, EVM versus test condition, constellation/spectrum diagnostics, received-power comparisons, and a combined summary table. Add angle-by-frequency heatmaps and per-subcarrier EVM/channel-response plots to inspect steering loss and beam squint. Include uncertainty and instrument/receiver baseline information.

### Steering and measurement sequencing

Use antenna-local coordinates: +x is boresight, positive azimuth turns toward +y, positive elevation toward +z. Record physical orientation separately from electronic beam direction. The backend converts beam angles and RF frequency into calibrated controller states; a mechanical positioner may use a different adapter implementing the same contract.

For each point: stop scoring/acquisition, issue the command, await its correlated acknowledgement and ready indication, wait the additional settling interval, clear stale buffered samples or schedule a new timed capture, reacquire the packet/channel, then collect a fixed measurement block. Do not change the beam mid-packet. Failed steering must invalidate/skip the point rather than reuse the previous direction under a new label.

The command framework currently uses a mock backend; its readback is explicitly simulated. Controller readback is not proof of measured radiation direction. Adapter transport timeouts must be implemented by the real driver. Host UTC timestamps support traceability but are not USRP hardware timestamps or calibrated beam-switch latency measurements.

Sweep a fixed, declared angle grid. If beam selection is optimized, select on separate training packets and score on held-out packets; do not report the minimum BER/EVM selected from the evaluation data. Record sweep order and use forward/reverse or randomized repeated scans to assess drift/hysteresis. Revalidate settling time and codebook calibration with the actual controller and frequency band.

## 8. Implementation milestones

| Milestone | Deliverable | Completion criterion |
| --- | --- | --- |
| 1. Freeze definitions | Legacy OFDM specification, defaults, steering contract, mapping vectors, capture schema | Conventions explicit; defaults/framework now present, golden vectors and mappings now validated |
| 2. Prove calculations | Python simulation and MATLAB verification | Noiseless, known-error, and AWGN checks pass |
| 3. Prove receiver | Non-HT GRC link, packet vectors, and replay tools | Synchronization, impairments, and independent packet cross-decoding pass |
| 4. Commission radios | USRP TX/RX flowgraphs and cabled results | Stable RF baseline with stream integrity |
| 5. Benchmark AUT | Automated reference/AUT and beam scans | Repeatable comparisons with steering/capture metadata |
| 6. Expand study | Additional bands/rates/orientations as needed | Changes retain verification and calibration |

Software theory, reference generation, and all eight replay rates now have validation evidence. The next development step is autonomous/timed acquisition and independently clocked tracking, followed by a commissioned cabled radio baseline and actual steering integration. No software-only result substitutes for those RF steps.

## 9. Inputs needed before implementation is finalized

1. Antenna frequency range, usable bandwidth, dimensions, polarization, and whether it will be tested as TX, RX, or both.
2. Available USRPs and daughterboards, radio count, reference antennas, attenuators, power measurement equipment, and clock distribution.
3. Test environment and separation: bench, indoor/outdoor line of sight, chamber, and whether position/orientation can be repeated.
4. Primary objective and target: compare designs, show an application BER threshold, determine useful range, or characterize distortion across bandwidth.
5. Intended host(s), Ethernet connectivity, MATLAB toolbox availability, and desired measurement duration/BER sensitivity.
6. Steering interface/protocol, mechanical versus electronic control, angular limits, readiness/readback capabilities, and available calibration/codebook.

Unknown hardware and antenna values remain configurable; they are not implementation blockers for software-only validation.

## References

- [Ettus X3x0 hardware and interface documentation](https://files.ettus.com/manual/page_usrp_x3x0.html)
- [Ettus daughterboard selection](https://kb.ettus.com/Selecting_an_RF_Daughterboard)
- [Ettus synchronization guidance](https://kb.ettus.com/Synchronization_and_MIMO_Capability_with_USRP_Devices)
- [MathWorks RMS EVM definitions and normalization](https://www.mathworks.com/help/comm/ref/comm.evm-system-object.html)
- [MathWorks error-rate confidence intervals](https://www.mathworks.com/help/comm/ref/berconfint.html)
- [MathWorks antenna field regions](https://www.mathworks.com/help/antenna/ug/field-analysis.html)
- [IEEE 802.11a-1999, archived standard PDF, legacy PHY baseline](https://labs.ece.uw.edu/funlab/802/802.11a-1999.pdf)
- [MathWorks legacy non-HT rates and timing](https://www.mathworks.com/help/wlan/ref/wlannonhtconfig.html)
- [MathWorks non-HT OFDM bin and sample conventions](https://www.mathworks.com/help/wlan/ref/wlannonhtofdminfo.html)
- [MathWorks WLAN SNR definitions](https://www.mathworks.com/help/wlan/ug/snr-definition-used-in-end-to-end-simulations.html)
