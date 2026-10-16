# Legacy OFDM profile and antenna steering

## What is available now

- `configs/wifi_nonht_defaults.json`: defaults for a planned 20 MHz legacy non-HT OFDM PHY and steering experiment.
- `antenna_steering.py`: standard-library Python interface, mock backend, angle validation, acknowledgement/readiness checks, settling, and JSONL command logging through the CLI.
- `matlab/validate_wifi_profile.m`: independently checks the profile's timing, bins, and rate table; optionally compares OFDM configuration with WLAN Toolbox.
- `tests/test_antenna_steering.py`: exercises readiness failures and reproducible command records.

The package now also includes MATLAB WLAN Toolbox packet export, coded decoding, BER/EVM theory and charts, independent Python metrics, and five GRC flowgraphs. See [README.md](../README.md) for the complete entry points and [VALIDATION.md](VALIDATION.md) for executed checks. Autonomous acquisition/tracking, a hardware sweep runner, and the real steering adapter remain to be implemented. Existing `test_flow.py` is a separate user flowgraph and is not modified by this framework.

## PHY choice for the paper

Target legacy OFDM in IEEE Std 802.11-2020 Clause 17, retaining the 802.11a/g non-HT numerology. The 5.18 GHz RF default is a placeholder; use the actual antenna band. A carrier at 2.4 GHz can support an ERP-OFDM-oriented experiment, but PHY generation alone does not implement the complete 802.11g MAC/ERP behavior.

The default uses a 64-point FFT and a 16-sample DATA cyclic prefix at 20 MS/s. Forty-eight subcarriers carry data and four carry pilots. The initial rate indices 0, 2, 4, and 6 cover BPSK, QPSK, 16-QAM, and 64-QAM at 6, 12, 24, and 48 Mbit/s. Local indices use MATLAB's non-HT configuration convention; they are not transmitted RATE bits. All eight legacy rates are defined in the JSON profile.

This replaces the earlier single-carrier/RRC recommendation as the main paper waveform. The single-carrier link remains an optional diagnostic; 8-PSK is outside the selected Wi-Fi PHY.

Before calling the implementation standards-compliant, validate the full packet and the selected normative procedures. Training sequences, signal fields, scrambling, coding, interleaving, pilot sequences, mapping, timing, padding, windowing, and scaling all matter. A generic OFDM waveform with Wi-Fi-sized FFT/CP is only a parameter-aligned experiment. Neither a valid PHY packet nor an antenna EVM result alone establishes complete Wi-Fi interoperability or certification.

For EVM, score known transmitted DATA references after documented training/pilot-based correction. Keep pilots and training out of the primary DATA EVM mask. Retain packet/subcarrier/symbol results and combine error/reference energies for the pooled result. Formal transmitter conformance EVM uses the selected standard's prescribed measurement procedure; the over-the-air antenna experiment measures an entire radio link.

Report pre-FEC coded-bit BER, post-FEC payload BER, and packet errors separately. Use uncoded analytic BER curves only for the applicable diagnostic simulation. Code rate, cyclic prefix, pilots, null subcarriers, and packet overhead must be accounted for before putting Eb/N0 on a graph.

At 20 MS/s, each sc16 stream contributes about 80 MB/s before protocol overhead; raw complex float32 recordings use about 160 MB/s. Prefer verified 10GbE connectivity and bounded captures. Keep the true 20 MHz timing in paper results; identify any slower debug waveform separately.

## Try the steering framework

From the repository directory, using the radioconda environment:

```sh
python antenna_steering.py --azimuth 30 --elevation 0
python antenna_steering.py --azimuth -20 --frequency-hz 5180000000 --log /private/tmp/steering-demo.jsonl
python -m unittest discover -s tests -v
```

These commands use the mock backend only. They do not move hardware or transmit RF. The output marks `simulated: true`; the reported angle is simulated as well. Out-of-range angles, nonfinite numbers, rejected/unready commands, mismatched acknowledgements, or insufficient settling time fail instead of returning a ready result.

The config supplies angle limits, pointing tolerance, settling interval, timeout, RF frequency, and optional calibration ID. Defaults are provisional and must match the eventual controller. The Python API accepts a backend implementing:

```python
class MyControllerBackend:
    name = "my-controller"
    simulated = False

    def apply(self, command, *, timeout_seconds):
        # 1. Convert command.pointing and command.center_frequency_hz using
        #    the actual mount calibration or electronic beam codebook.
        # 2. Encode/send the documented serial/Ethernet/SDK command.
        # 3. Enforce transport deadlines; correlate the response to this
        #    command.command_id, including when the wire protocol has no ID.
        # 4. Await a defined controller-ready condition within the deadline.
        # 5. Return SteeringAck with accepted/ready, optional reported_pointing,
        #    beam_id, and diagnostic detail. Return rejected or raise on failure.
        raise NotImplementedError("Implement the actual controller protocol")
```

Import `SteeringAck` and `SteeringController` from `antenna_steering`. Construct a controller with the real backend and call `controller.steer(azimuth_deg, elevation_deg, center_frequency_hz=..., calibration_id=...)`. Persist `result.to_dict()` in the measurement record. `reported_pointing=None` means no readback; never substitute requested angles and label them measured.

The backend's `apply` is synchronous and must use bounded serial/socket/SDK calls. The wrapper checks elapsed time after it returns but cannot forcibly interrupt a blocked driver. A send receipt alone is not a settled/readiness confirmation. For devices with no ready signal, define and validate the adapter's timed readiness policy and document that policy in the returned detail.

## Capture orchestration contract

```text
stop scoring / retain expected packet accounting
  -> send steer command
  -> match acknowledgement and controller-ready state
  -> wait extra settling interval
  -> discard stale buffered samples or schedule a new timed capture
  -> reacquire packet and channel estimates
  -> collect fixed packet block
  -> save steering result + RF timestamps + BER/EVM/packet outcomes
```

A hardware measurement runner must reject mock results, serialize the entire steer-and-capture cycle, and skip/mark failed steering points. The current lock serializes steering commands only. Do not change beams during a scored packet or silently relabel the previous beam after a failed command.

Axes are antenna-local: +x is boresight; positive azimuth turns toward +y, positive elevation toward +z. Physical antenna rotation and electronic beam direction are separate metadata. The framework's controller readback is not a calibrated far-field beam measurement. UTC timestamps are host timestamps, not USRP hardware sample times or measured beam-switch latency.

The default scan is azimuth -60 to +60 degrees in 10-degree steps at zero elevation, with 1000 packets per point and three repetitions. Start with one rate and direction before expanding. Use interleaved reference/AUT runs and repeated scan orders to quantify drift. Frequency-dependent codebook/calibration IDs support analysis of beam squint and scan loss. Tune the provisional 0.25 s extra settling time to the actual antenna/controller.

If selecting the best beam, select using separate training packets and evaluate using held-out packets. Do not select the minimum BER/EVM from the same packets used to report performance.

## MATLAB configuration check

In MATLAB:

```matlab
addpath('matlab');
report = validate_wifi_profile;
```

This configuration validator works without Communications Toolbox or WLAN Toolbox for its basic checks. If WLAN Toolbox is installed, it also compares FFT/CP/sample-rate and pilot/data indexing. The new theory, reference-generation, and capture-analysis scripts provide additional waveform/BER/EVM validation under the supplied packet timing/rate assumptions. A Python PPDU generator and independent packet cross-decoding in both directions remain future milestones.

## Sources and paper traceability

- [IEEE 802.11a-1999 archived standard](https://labs.ece.uw.edu/funlab/802/802.11a-1999.pdf): original OFDM baseline; use the selected consolidated edition for final normative citations.
- [MathWorks wlanNonHTConfig](https://www.mathworks.com/help/wlan/ref/wlannonhtconfig.html): non-HT rates, coding, and timing; references IEEE 802.11-2020 Clause 17.
- [MathWorks wlanNonHTOFDMInfo](https://www.mathworks.com/help/wlan/ref/wlannonhtofdminfo.html): bin indexing, sample rate, and FFT/CP conventions.
- [MathWorks WLAN SNR definitions](https://www.mathworks.com/help/wlan/ug/snr-definition-used-in-end-to-end-simulations.html): time-domain versus subcarrier SNR conventions.

Archive the exact configuration, software versions, waveform hashes, normative standard edition, controller/firmware version, calibration ID, reference antenna data, and run timestamps with the experiment. Keep implementation and validation status explicit in the paper.
