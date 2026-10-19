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
    "BER is the fraction of errors in each nonoverlapping 10,000-bit window. It is not a cumulative counter. Differential encoding is enabled. Receiver noise is input-referred and integrated across Fs. Comparison with theory is in the BER test section above.\n",
    "The stock EVM block is decision-directed. Its RMS-smoothed display can underestimate error at poor SNR because the nearest constellation point can be the wrong transmitted point. The exported data-aided constellation figures additionally compare the actual transmitted and received symbols without decision bias.\n",
]
def ber_validation_section():
    """BER-test results and sanity checks (from scripts/ber_validation.py)."""
    folder = ROOT / "results/ber_tests"
    if not (folder / "summary.json").exists():
        return []
    import csv

    summary = json.loads((folder / "summary.json").read_text())
    with (folder / "ber_validation.csv").open() as file:
        points = list(csv.DictReader(file))
    names = {"bpsk": "BPSK", "qpsk": "QPSK", "8psk": "8-PSK", "4ask": "4-ASK",
             "8ask": "8-ASK", "16qam": "16-QAM"}
    formats = summary["formats"]
    total = sum(f["total_bits"] for f in formats.values())
    clean = summary["noiseless"]

    def db(value):
        return "—" if value is None else f"{value:.2f}"

    def signed(value):
        return "—" if value is None else f"{value:+.2f}"

    out = [
        "## BER test results and sanity checks\n",
        f"These results come from the BER test built into each single-carrier flowchart, run by [scripts/ber_validation.py](../scripts/ber_validation.py) (the same test you get with [run_ber_test.py](../scripts/run_ber_test.py) or by pressing Run in GRC). In total {total:,} bits were compared across {sum(f['points'] for f in formats.values())} Eb/N0 points. Each point ran until it had at least ~300 bit errors, or until it reached 20 million bits. Every error count was cross-checked against the flowchart's raw 10,000-bit error sums. Eb/N0 is per uncoded bit, with receiver noise integrated over Fs = 4 MHz. TX is 0 dBm with 80 dB net loss.\n",
        "Two references:\n",
        "- **Ideal sync, same coding:** a NumPy receiver with perfect timing and gain, the same constellation, the same bit mapping and the same differential coding. A correctly working receiver should match it; any excess is implementation loss.\n",
        "- **Coherent Gray theory:** the textbook curve. The gap between it and the ideal-sync reference is the known cost of differential coding, and for ASK, of the stock natural (non-Gray) symbol order.\n",
        "![BER test results with references](ber_test_validation.png)\n",
        "![Equivalent Eb/N0 loss against the ideal-sync reference](ber_test_ratio.png)\n",
        "### Do the results make sense?\n",
    ]
    zero_ok = all(v["errors"] == 0 for v in clean.values())
    out.append(f"- **Noise off:** {'PASS' if zero_ok else 'FAIL'}. "
               + ", ".join(f"{names[p]} {v['errors']} errors in {v['bits']:,} bits"
                           for p, v in clean.items()) + ".")
    mono = all(f["monotonic"] for f in formats.values())
    out.append(f"- **BER falls as Eb/N0 rises:** {'PASS' if mono else 'CHECK'} for every format, "
               "within 95% confidence intervals (excluding the loss-of-lock points below).")
    out.append("- **Close to the ideal-sync reference:** each point's equivalent Eb/N0 loss "
               "(how far the ideal receiver could back off and still reach the same BER) is "
               + ", ".join(f"{names[p]} {f['equivalent_loss_db_range'][0]:.2f}–"
                           f"{f['equivalent_loss_db_range'][1]:.2f} dB"
                           for p, f in formats.items() if f["equivalent_loss_db_range"])
               + ". A working timing loop and LMS equalizer should cost a few tenths of a dB, "
               "which PSK and 16-QAM do across the whole curve. The larger ASK values sit at "
               "two edges explained below: next to the loss-of-lock threshold, and for 8-ASK "
               "at high Eb/N0.")
    out.append("- **Agreement with the earlier, independently scored 250,000-bit sweep:** "
               + ", ".join(f"{names[p]} {f['agree_with_250k_sweep']}" for p, f in formats.items())
               + " points with at least 10 sweep errors (95% intervals overlap; because "
               "differential decoding produces errors in pairs, intervals use half counts). "
               "The few exceptions differ by about 20%.")
    lock = {p: f["low_snr_lock_loss_points"] for p, f in formats.items()
            if f["low_snr_lock_loss_points"]}
    if lock:
        out.append("- **Loss of lock at the lowest Eb/N0:** "
                   + "; ".join(f"{names[p]} at {', '.join(f'{e:g}' for e in v)} dB"
                               for p, v in lock.items())
                   + ". BER reads about 0.5 while an ideal receiver would still be below 0.2. "
                   "There the timing loop and decision-directed equalizer cannot hold lock, so "
                   "every bit is random. This is real receiver behaviour, not a counting error, "
                   "and it is below any useful operating point. Loss of lock starts at a random "
                   "moment, so these long runs catch it at slightly higher Eb/N0 than the "
                   "earlier 250,000-bit sweep did (BPSK at 2 dB read 0.08 there).")
    out.append("- **Why ASK loses more at high Eb/N0.** With noise off, every format decodes "
               "error-free, but specific symbol patterns leave a small steady-state residual "
               "(timing and equalizer pattern noise), about 0.1 of the RMS amplitude at worst. "
               "PSK and 16-QAM have plenty of distance to their decision boundaries, so it costs "
               "them little. 8-ASK puts eight levels on one axis, only 0.22 RMS from each "
               "boundary, so those rare patterns close its eye noticeably. At low BER only those "
               "patterns fail, which is why 8-ASK's loss rises from about 0.3 dB at 14 dB to "
               "about 0.9 dB at 20 dB. This is a real receiver property, not a counting error. "
               "A narrower timing loop would reduce it.")
    out.append("\n| Modulation | Noise-off RMS EVM | Half decision spacing (× RMS) | "
               "Worst residual, 99.99% (× RMS) | Eye closure | Asymptotic loss limit (dB) |")
    out.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for p, f in formats.items():
        r = f["noise_off_residual"]
        out.append(f"| {names[p]} | {r['rms_evm_percent']:.2f}% | {r['half_spacing_rms']:.3f} | "
                   f"{r['worst_error_rms']:.4f} | {r['eye_closure_percent']:.1f}% | "
                   f"{r['asymptotic_loss_db']:.2f} |")
    out.append("\nThe last column is the loss approached only at extremely low BER, if the "
               "worst residual pattern lined up with the noise. The measured losses down to "
               "10⁻⁶ stay well below it.")
    out.append("\n### Required Eb/N0 and implementation loss\n")
    out.append("| Modulation | BER | GRC BER test (dB) | Ideal sync, same coding (dB) | "
               "Gray theory (dB) | Implementation loss (dB) | Coding + mapping penalty (dB) |")
    out.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for p, f in formats.items():
        for tag in ("1e-03", "1e-04"):
            v = f[f"ebno_at_{tag}"]
            out.append(f"| {names[p]} | {tag.replace('e-0', 'e-')} | {db(v['measured'])} | "
                       f"{db(v['ideal_same_coding'])} | {db(v['gray_theory'])} | "
                       f"{signed(v['implementation_loss_db'])} | "
                       f"{signed(v['coding_and_mapping_penalty_db'])} |")
    bpsk = formats["bpsk"]["ebno_at_1e-04"]
    out.append("\nSpacing at BER 1e-4, relative to BPSK. The measured spacing should track "
               "the ideal-sync spacing; Gray theory is listed for comparison:\n")
    out.append("| Modulation | GRC BER test (dB) | Ideal sync, same coding (dB) | Gray theory (dB) |")
    out.append("| --- | ---: | ---: | ---: |")
    for p, f in formats.items():
        v = f["ebno_at_1e-04"]
        rel = [None if None in (v[key], bpsk[key]) else v[key] - bpsk[key]
               for key in ("measured", "ideal_same_coding", "gray_theory")]
        out.append(f"| {names[p]} | {signed(rel[0])} | {signed(rel[1])} | {signed(rel[2])} |")
    out.append("\nExpected physics, all visible above:\n")
    out.append("- BPSK and QPSK need the same Eb/N0 per bit.")
    out.append("- 8-PSK, 16-QAM and 4-ASK need roughly 3.5–4 dB more.")
    out.append("- 8-ASK needs about 8 dB more, because its levels are packed onto one axis.")
    out.append("- Differential coding roughly doubles the BER at high Eb/N0, because each symbol error corrupts two decoded symbols.")
    out.append("- For 16-QAM and ASK, differential coding on symbol indices also undoes Gray labelling, and the stock ASK constellations use natural order. Each symbol error therefore costs more bits.")
    out.append("- Together, the coding + mapping penalty is about 0.4–0.8 dB for PSK and up to 1.2 dB for 16-QAM, as in the table.")
    out.append("\n### Every point\n")
    out.append("| Modulation | Eb/N0 (dB) | Bits | Errors | BER | 95% CI | Ideal sync | Measured / ideal | Gray theory |")
    out.append("| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |")
    for r in points:
        ratio = r["ratio_to_ideal"]
        out.append(
            f"| {names[r['modulation']]} | {float(r['ebno_db']):g} | {int(float(r['bits'])):,} | "
            f"{int(float(r['errors'])):,} | {float(r['ber']):.3e} | "
            f"{float(r['ci_low']):.2e} – {float(r['ci_high']):.2e} | {float(r['ideal_ber']):.3e} | "
            f"{'—' if ratio in ('', 'None') else format(float(ratio), '.2f')} | "
            f"{float(r['gray_theory_ber']):.2e} |")
    out.append("\n[All points (CSV)](ber_tests/ber_validation.csv), [summary (JSON)](ber_tests/summary.json).\n")
    return out


# BER results first: they are what the report is mainly read for.
text[1:1] = ber_validation_section() + ["## Flowchart validation cases\n"]
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
