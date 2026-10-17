# Antenna experiment methods and reporting framework

This is a methods framework to adapt once hardware and antenna details are known. It does not assert empirical findings. Current charts demonstrate a reproducible software baseline. Equation/source identifiers refer to [THEORY.md](THEORY.md) and [REFERENCES.md](REFERENCES.md).

## Agreed initial experiment: fixed-power SISO

Use one transmit stream and one receive stream. Compare reference antenna and AUT at fixed **average conducted TX power**, fixed RX gain, waveform, geometry and polarization. At each commanded beam: settle, capture a fixed block of known-rate PHY bursts, then calculate **pre-FEC mapped-bit BER, reference RMS EVM, and received power**. Keep expected/recovered burst counts visible as integrity information. There is no requirement to implement Wi-Fi association, MAC acknowledgements, retransmission, or a general packet networking stack.

The [two live GRC labs](SISO_LABS.md) support this scoped workflow in simulation. The Wi-Fi lab fixes average active PPDU power across rates, keeps AWGN power independent of channel loss, and estimates CFO/channel/phase from training and pilots. It still receives timing/rate/length from the experiment. Post-FEC BER, PER, automatic rate discovery and adaptive beam selection remain optional extensions below, rather than prerequisites for the initial antenna comparison. For RF work, validate the physical timing/acquisition arrangement and clock mismatch before interpreting a capture as an antenna measurement.

## Research questions

State which effect the experiment estimates, for example:

1. At the same transmitted average power, geometry, and PHY rate, does the AUT improve payload reliability over a reference antenna?
2. How do commanded scan angle and RF frequency affect received power, pre/post-FEC BER, PER, and DATA EVM?
3. How much of a scan-dependent loss is explained by reduced received power, and how much remains when a separate diagnostic matches received power?
4. Does beam selection on independent training packets improve subsequent held-out packet performance?

Avoid using a single EVM number as an antenna-only characteristic. It contains transmitter, channel, receiver, synchronization, and equalization effects. Matching EVM after gain normalization can coexist with materially different link budgets.

## PHY and simulation baselines

Use the legacy 20 MHz non-HT OFDM profile and rate table in `configs/wifi_nonht_defaults.json`, with BPSK, QPSK, 16-QAM, and 64-QAM. The historical normative basis is IEEE 802.11a-1999 Clause 17, with implementation references to the corresponding legacy OFDM provisions of IEEE 802.11-2020. [IEEE-A, MW-NHT]

The supplied actual PPDU generator is MATLAB WLAN Toolbox, not a newly developed transmitter. GNU Radio replays the generated IQ and supplies the channel or USRP interface. State that provenance in the paper. The synthetic 1000-byte PSDUs and fixed idle schedule do not implement Wi-Fi association, contention, MAC acknowledgement, retransmission, or MAC-FCS-based validation. [MW-WAVE]

Present uncoded analytical curves as an algorithm sanity check, separately from coded WLAN receiver simulations and RF measurements. The exact square-QAM curve integrates decision regions and includes multiple-bit transitions. State coherent perfect-synchronization assumptions and the Eb/N0 convention. [MW-BER, MW-ANALYTIC]

The initial coded curve uses known packet boundaries/rates, noisy L-LTF channel estimation, ZF, no injected CFO/sample-clock offset, and no pilot/CFO correction. It is a schedule-assisted receiver baseline. It does not measure acquisition sensitivity or field link performance. The default 12 packets per point are exploratory; increase independent packets/repetitions before drawing fine performance distinctions.

## Hardware baseline and antenna substitution

Document the exact USRP models, serial numbers, UHD/FPGA versions, daughterboards, RF ports, host interfaces, rates, gains, clock/time sources, and measured actual settings. Confirm desired RF coverage from the daughterboard, rather than from the X310 motherboard name. [UHD-X3X0]

First establish an attenuated cabled baseline. Characterize received level, radio EVM floor, clipping/linearity, waveform PAPR/headroom, underflows/overflows, and repeatability. Use measured cable/attenuator losses and conducted power when reporting dBm. Document the actual input rating and attenuation for the selected RF board.

Then fix the counterpart antenna and substitute only the AUT/reference at the evaluated end. Control the mount reference, feed cable, distance, polarization, physical orientation, surrounding objects, radio settings, packet waveform, and average transmitted power. Interleave reference and AUT measurements in time. Record available antenna S-parameters/calibration separately; BER/EVM does not directly establish absolute gain, radiation efficiency, or impedance match.

Select separation and measurement environment from antenna dimensions, wavelength, and desired far-field/line-of-sight interpretation. Reflections or near-field operation may be part of an application experiment, but must be described instead of generalized to a free-space antenna pattern.

## Steering, orientation, and capture timing

Use antenna-local coordinates: +x is boresight, positive azimuth rotates toward +y, and positive elevation toward +z. Record the transform to the room/range coordinate system. Electronic steering angle is distinct from physical antenna rotation and from the direction of the counterpart antenna.

For each point:

1. Stop scoring, retaining the planned expected-packet schedule.
2. Send a uniquely identified steering command containing azimuth, elevation, frequency, and calibration/codebook identifier.
3. Await the matching acceptance and ready condition. Record readback if available; do not label a requested angle as a measured beam direction.
4. Wait a validated additional settling interval and discard stale buffers or schedule a new timed capture.
5. Reacquire the PHY/channel and collect a fixed packet block with unchanged beam settings.
6. Save raw IQ, expected/transmitted references, settings, steering results, sample/UTC timestamps, stream health, and outcomes.

`antenna_steering.py` implements the command contract with a mock backend. The provisional 0.25 s extra settling interval and 5 s total deadline are not measured controller characteristics. A real adapter must implement bounded transport calls and a validated readiness policy. Electronic arrays may use beam codebook/phase-state readback instead of physical encoder angles.

If a command fails, mark that point invalid rather than acquiring under the previous beam and assigning it the new angle. Serialize the whole steering-plus-capture interval; the current controller lock covers steering requests only. Reject mock results for hardware acquisition. Host UTC times alone do not measure beam-switch latency or establish sample-level synchronization.

Start with azimuth -60 to +60 degrees in 10-degree steps at zero elevation. Test both scan directions or randomized order across repetitions. Save frequency-dependent calibration and beam IDs to support beam-squint/scan-loss analysis. Optimize on separate training captures and evaluate on held-out packets; avoid selecting the minimum BER/EVM from the evaluation data itself.

## Outcomes and denominators

| Outcome | Required denominator / policy |
| --- | --- |
| Post-FEC payload BER | Erroneous compared descrambled payload bits / compared payload bits; do not remove CRC-failed payloads from the comparison |
| Pre-FEC BER | Clearly specified transmitted coded-bit stage; the supplied Python scorer includes mapped DATA SERVICE/tail/pad bits |
| Packet error rate | Failed or missing packets / expected transmitted packets; define whether failure is payload mismatch, L-SIG failure, FCS failure, or acquisition loss |
| EVM | Sum squared error / sum reference energy, square-rooted; state DATA mask, receiver corrections, equalizer, and pooling rule |
| Received power | Calibrated dBm if supported; otherwise honest relative/dBFS units and fixed gain |
| Throughput | Delivered application payload bits / elapsed time; distinguish from nominal PHY rate |
| Stream integrity | Counts/intervals of UHD underflow/overflow/clipping; invalidate instrument failures separately from radio-channel packet loss |

Keep unalignable payloads out of a conditional BER denominator but include their packets in failure accounting. Do not assign unknown bits an invented BER of zero or one-half. Keep conditional EVM, acquisition success, and PER visible together to avoid survivor bias.

Choose transmitted packet counts in advance and report observed/scored bit counts separately. Use repeated independent captures to quantify drift and burstiness. Bit-binomial intervals assume independence and are nominal for correlated QAM/FEC/fading errors; consider packet/repetition-level intervals or clustered resampling for the actual study. Report zero-error sensitivity as an upper bound, not proof of zero BER. [MW-CI, CLOPPER-PEARSON]

## Paper figures and captions

Suggested figure sequence:

1. Annotated test setup and steering coordinates, with reference/AUT substitution and cabled baseline.
2. Exact uncoded BER versus Eb/N0 and independent simulations, explicitly labeled as validation.
3. Coded non-HT BER/PER with a stated energy convention and receiver assumptions.
4. Controlled RF reference/AUT BER, PER, EVM, and received power at matching PHY settings.
5. Scan-angle-by-frequency maps, with beam selection policy and confidence/repetition information.
6. Per-subcarrier EVM/channel response to inspect frequency-selective loss or beam squint.

Example caption for the supplied analytical plot: “Coherent uncoded Gray BPSK, QPSK, 16-QAM, and 64-QAM over complex AWGN. Lines denote exact bit-error probabilities; circles show independent MATLAB Monte Carlo results. Error bars use nominal bit-binomial 95% intervals. Downward triangles denote one-sided zero-error upper limits. This plot validates the software and is not an antenna measurement.”

Use vector PDF/SVG exports for the paper and CSV/MAT data for analysis. Cite the actual standard edition, mathematical definitions, packet-generator provenance, software versions, and archived source/configuration hashes. Retain separate language for experimental PHY results and formal standards-conformance measurements.
