"""Refresh the Markdown report from existing verified captures and MATLAB results."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
profiles = {"bpsk": 34, "qpsk": 68, "8psk": 102, "4ask": 68, "8ask": 102, "16qam": 136}
rows = [
    json.loads((ROOT / "results" / f"{name}_noise_{noise:g}.json").read_text())
    for name in profiles
    for noise in (0, 0.3)
]
zero_noise = [row for row in rows if row["noise_voltage"] == 0]
matlab_results = json.loads((ROOT / "results/matlab_validation.json").read_text())
power_text = [
    "## Link-budget power reference\n",
    "[Three fixed-noise link-budget tests](link_budget_checks/summary.json) also verify that adding 10 dB TX power and 10 dB path loss preserves received power/BER, while reducing TX power at fixed loss/noise worsens BER.\n",
    "IQ uses a power-wave convention: |IQ|² is milliwatts. TX average power defaults to 0 dBm, net path loss to 80 dB, and default RX noise to −100 dBm across the 4 MHz complex sample bandwidth. Received signal power is TX − net loss. The RX meter measures signal + noise. Validation cases explicitly set noise to their test values.\n",
    "| Modulation | Set TX average (dBm) | Measured TX (dBm) | RX signal expectation (dBm) | RX total measured (dBm) | Sampled TX peak (dBm) | PAPR (dB) |",
    "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
]
for row in zero_noise:
    power_text.append(
        f"| {row['modulation'].upper()} | {row['tx_power_dbm']:.2f} | {row['tx_measured_dbm']:.3f} | {row['expected_rx_signal_dbm']:.2f} | {row['rx_measured_dbm']:.3f} | {row['tx_sample_peak_dbm']:.3f} | {row['papr_db']:.3f} |"
    )
power_text.append(
    "\nAverage and sampled peak meters use stock magnitude-squared, integration/max, and Log10 blocks. MATLAB independently validates their outputs and absolute TX/RX powers. Sample peaks at four samples/symbol are estimates of continuous-time PEP. These are simulated powers; no USRP output calibration has been performed. [Power controls and equations](../README.md#power-in-dbm-and-link-budgets).\n"
)
text = [
    "# Single-carrier simulation checks\n",
    "Baseline: **1 Msymbol/s, four samples/symbol, 4 Msamples/s**. Six flat flowcharts containing only installed GNU Radio blocks. These are software simulations with zero carrier offset and no sample-rate mismatch.\n",
    "| Modulation | RX noise (dBm over Fs) | Reference delay (bits) | Compared bits | Display BER, mean of windows | TX mean power (mW) |",
    "| --- | ---: | ---: | ---: | ---: | ---: |",
]
for row in rows:
    text.append(
        f"| {row['modulation'].upper()} | {'off' if not row['noise_enabled'] else format(row['rx_noise_dbm'], '.2f')} | {row['configured_delay_bits']} | {row['compared_bits']} | {row['display_ber_mean']:.6g} | {row['tx_mean_sample_power']:.5g} |"
    )
text += [
    "\nEach case verifies every XOR output bit against an independent TX/RX comparison and checks each Integrate/Multiply BER window. All six noiseless cases must have zero bit errors. The first 4096 output bits are excluded for filter and timing-loop startup.\n",
    "BER is the fraction of errors in each nonoverlapping 10,000-bit window. It is not a cumulative counter. Differential encoding is enabled. Receiver noise is input-referred and integrated across Fs. Nominal energy ratios can be computed from the documented bandwidth convention; theoretical BER agreement is not claimed here.\n",
    "The stock EVM block is decision-directed. Its RMS-smoothed display can underestimate error at poor SNR because the nearest constellation point can be the wrong transmitted point. The exported data-aided constellation figures additionally compare the actual transmitted and received symbols without decision bias.\n",
]
canvas_text = ["## Actual GRC canvas exports\n"]
for profile in profiles:
    canvas_text.append(
        f"### {profile.upper()}\n\n![{profile.upper()} GRC canvas]({profile}_flowchart.png)\n"
    )
echo = json.loads((ROOT / "results/equalizer_checks/16qam_noise_0.1.json").read_text())
text += [
    "## Adaptive equalizer and 2×2 dashboards\n",
    "All six live flowcharts use six resizable tabs with four charts per tab in a 2×2 grid. Controls are packed using their actual native GRC sizes with 8 px gaps. No plot canvas has a forced square size. Editable blue boxed section headings identify the transmitter, channel, receiver, BER measurement, and diagnostic areas in GRC; open with antenna-grc for the large heading style.\n",
    "The receiver now includes a stock 11-tap, one-sample/symbol, decision-directed LMS Linear Equalizer after timing recovery. A centered identity initialization adds five symbols to the reference delay. A stock Python Snippet initializes the taps through the public API; all filtering/adaptation uses native GNU Radio blocks. The live tap-magnitude chart displays the actual adapting coefficients. Defaults: channel_echo=0, eq_step=0.01, native LMS step=eq_step/(eq_taps*symbol_rms²).\n",
    f"A 16-QAM case with a power-normalized one-symbol echo of 0.25 voltage ratio and normalized input noise 0.10 measured **{echo['pre_reference_evm_percent']:.2f}% before EQ → {echo['reference_evm_percent']:.2f}% after EQ**, with observed BER {echo['aligned_ber']:.3g} over {echo['compared_bits']:,} compared bits. EVM uses actual aligned TX symbols after a 1,024-symbol warmup, with no amplitude/phase fit; its averaging interval can include remaining LMS convergence. This single controlled case does not establish performance for arbitrary multipath or carrier offsets. [Capture values](equalizer_checks/16qam_noise_0.1.json).\n",
    "![Four-panel equalizer dashboard](equalizer_dashboard.png)\n",
    "Each I/Q eye dashboard shows TX, raw channel RX, middle (after timing/before EQ), and after EQ. TX/RX use actual 4-SPS waveform samples. Middle/post eyes are explicitly **display-only RRC reconstructions of 1-SPS symbol streams**, not measured oversampled receiver signals. Their interpolation branches never feed BER decoding. Raw waveforms in these exported dashboards are converted to RMS symbol units using known TX/path levels.\n",
    "![I-eye dashboard](equalizer_eyes_i.png)\n\n![Q-eye dashboard](equalizer_eyes_q.png)\n",
    "Native GNU Radio Qt renders: [I-eye tab](live_dashboard_2.png), [constellations](live_dashboard_0.png), [BER/EVM/tap tab](live_dashboard_5.png). These show the actual resizable layout. Finite captures can finish before all live-sink refreshes; the numerical values above use the captured streams.\n",
    "MATLAB independently recomputes native adaptive FIR outputs from captured per-symbol tap vectors and input samples, and reconstructs both RRC eye streams from saved symbols/taps. Sources: [GNU Radio Linear Equalizer](https://wiki.gnuradio.org/index.php/Linear_Equalizer), [GNU Radio LMS source](https://github.com/gnuradio/gnuradio/blob/v3.10.12.0/gr-digital/include/gnuradio/digital/adaptive_algorithm_lms.h).\n",
]
text += power_text
text += [
    "## Data rate at 1 Msymbol/s\n",
    "![Gross bit rate](data_rate.png)\n",
    "Gross uncoded bit rate is symbol rate × log2(M). Rates are 1, 2, 3, 2, 3, and 4 Mbit/s respectively. These are not measured packet goodput. With rolloff 0.35, ideal RRC null-to-null bandwidth is 1.35 MHz (complex baseband edges ±0.675 MHz). [CSV](data_rate.csv), [vector PDF](data_rate.pdf), [independent MATLAB chart](matlab_data_rate.png).\n",
    "## BER versus Eb/N0\n",
    "![Measured BER versus Eb/N0](ber_vs_ebno.png)\n",
    "Each point is one finite capture of the saved flowchart (about 250,000 compared bits) with receiver noise set from the requested Eb/N0 under the Fs noise-bandwidth convention. Error bars are exact 95% Clopper-Pearson intervals; open markers had zero errors and sit at the one-sided 95% upper bound. [Data](ber_sweep/ber_sweep.csv), [vector PDF](ber_vs_ebno.pdf).\n",
    "![BER panels with references](ber_vs_ebno_panels.png)\n",
    "Dashed: ideal synchronization with the same constellation, bit mapping and differential coding (NumPy). Grey: textbook coherent Gray-coded AWGN theory. Above a few dB the flowchart measurements lie on the ideal-sync reference; the gap to Gray theory is the cost of differential coding and the stock (non-Gray) ASK symbol order. At the lowest Eb/N0, BPSK, 4-ASK and 8-ASK lose timing/equalizer lock (BER near 0.5), which is real receiver behavior.\n",
    "![EVM versus Es/N0](evm_vs_esno.png)\n",
    "Data-aided EVM follows 100/sqrt(Es/N0) for every format wherever the receiver is locked, an independent check of the noise convention.\n",
    "## BER and EVM at one receiver-noise setting\n",
    "![Measured BER](ber_comparison.png)\n\n![Data-aided EVM](evm_comparison.png)\n",
    "All baseline runs use 0 dBm nominal conducted TX power, 80 dB net loss, and the same receiver noise power; decision-directed EVM can be optimistic when decisions are wrong. Noise and energy ratios use the documented Fs convention. Error bars are 95% Clopper-Pearson intervals; zero-error cases show the 95% upper bound.\n",
    "## Independent MATLAB validation\n",
    f"MATLAB passed {matlab_results['cases']} actual capture cases: every XOR bit, BER window, stock per-symbol EVM, RMS smoothing, sample rate, gross bit rate, ideal RRC bandwidth, actual time-varying equalizer FIR output, and reconstructed eye waveforms. Maximum BER difference: {matlab_results['maxBerDifference']:.3g}; maximum per-symbol EVM difference: {matlab_results['maxEvmPercentDifference']:.3g} percentage points. [MATLAB source](../matlab/validate_single_carrier.m), [machine-readable results](matlab_validation.json).\n",
    "Stock EVM formula: [GNU Radio 3.10.12 source](https://github.com/gnuradio/gnuradio/blob/v3.10.12.0/gr-digital/lib/meas_evm_cc_impl.cc).\n",
]
text += [
    "## RX SNR and Eb/N0\n",
    "Live SNR uses measured TX average power minus known path loss and configured noise power over Fs. Eb/N0 adds 10 log10(Fs/bit_rate). These are known-reference link-budget readouts, not blind estimates from noisy RX samples. Noise disabled displays infinity. Defaults: SNR(Fs)=20 dB; Eb/N0=26.02, 23.01, 21.25, 23.01, 21.25, 20.00 dB across the six formats. The finite noisy test below uses −90.46 dBm noise and therefore different ratios.\n",
    "![Configured RX ratios](rx_ratios.png)\n",
    "## TX and RX constellation figures\n",
    "TX symbols are the actual stock packing/differential-mapping monitor before pulse shaping. RX points are aligned with those TX symbols using the known latency, with no amplitude/phase fit. Dashed circles show the measured data-aided RMS error radius; they are not confidence contours or compliance limits.\n",
    "![All six RX constellations](constellation_grid.png)\n",
]
for profile in profiles:
    text.append(
        f"### {profile.upper()} symbols\n\n![TX constellation]({profile}_tx_constellation.png)\n\n![RX constellation]({profile}_rx_constellation.png)\n"
    )
text.append(
    "MATLAB checks TX symbol encoding, data-aided EVM, and SNR/Eb/N0 readouts in addition to the stock meters. SNR conversion: [MathWorks convertSNR](https://www.mathworks.com/help/comm/ref/convertsnr.html). EVM normalization: [MathWorks EVM](https://www.mathworks.com/help/comm/ref/comm.evm-system-object.html).\n"
)
n210_file = ROOT / "results/n210_loopback_check.json"
if n210_file.exists():
    n210 = json.loads(n210_file.read_text())
    channel = n210["channel"]
    text += [
        "## Two-N210 flowcharts: software loopback check\n",
        f"The generated n210_* flowcharts were run with both UHD blocks replaced by a software channel modelling two free-running radios: {channel['cfo_hz']:g} Hz carrier offset, {channel['clock_offset_ppm']:g} ppm sample-clock offset, {channel['delay_samples']:g}-sample delay, {channel['phase_deg']:g} deg carrier phase, {channel['gain_db']:g} dB path, Es/N0 {channel['esno_db']:g} dB. Bits are scored against the true transmitted data after acquisition. This is not a hardware measurement.\n",
        "| Modulation | BER vs TX data | Flowchart BER display | MER (dB) | TX sampled peak (dBFS) | Pass |\n| --- | ---: | ---: | ---: | ---: | --- |\n"
        + "".join(
            f"| {r['modulation'].upper()} | {r['ber_vs_true_tx']:.3g} | {r['displayed_ber']:.3g} | "
            f"{r['mer_db_settled']:.1f} | {r['tx_sample_peak_dbfs']:.1f} | {'yes' if r['passed'] else 'NO'} |\n"
            for r in n210["results"]
        ),
    ]
text += canvas_text
text.append(
    "Reference: [GNU Radio tutorial](https://wiki.gnuradio.org/index.php?title=M-ASK_Mod_and_Demod_and_QAM-M_Mod_and_Demod), read from the locally downloaded HTML and figures.\n"
)
(ROOT / "results/REPORT.md").write_text("\n".join(text))
