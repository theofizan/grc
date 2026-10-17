# BER, Eb/N0, EVM, and uncertainty

The primary experiment is fixed-power **SISO**. [SISO_LABS.md](SISO_LABS.md) specifies the two full-chain live graphs and distinguishes their power conventions from the older reference graphs below. In particular, the new Wi-Fi lab uses **unit average active PPDU power**, with complex noise variance independent of channel loss. Its TX-reference `snr_db` is not the older active-DATA SNR or an Eb/N0 label. The symbol lab uses T1 and ideal scalar correction; the Wi-Fi lab estimates CFO/channel/pilot phase from training and known pilots. Only timing/rate/length remain supplied.

This document defines the quantities used by the scripts. Source identifiers link to [REFERENCES.md](REFERENCES.md), with BibTeX keys in `references.bib`. Equations below are mathematical descriptions and derivations; the code is an independent implementation. No numeric simulation curve is an antenna measurement.

## T1. Signal and noise convention

For the uncoded diagnostic, one complex sample represents one perfectly synchronized constellation symbol. The constellation has unit average energy, equally likely symbols, and Gray labels. With `k = log2(M)` and `gamma_b = 10^(EbNo_dB/10)`:

\[
y=s+n,\quad E_s=1,\quad N_0=\frac{1}{k\gamma_b},\quad
n=\sqrt{N_0/2}(u+jv),\quad u,v\sim\mathcal N(0,1).
\tag{T1}
\]

Thus `E[|n|^2] = N0` and each real component has variance `N0/2`. GNU Radio's complex Gaussian noise amplitude is calibrated as `sqrt(N0)` in the executed graph. Confusing complex noise power with per-axis variance creates a 3 dB error. This graph has no pulse shaping, packet overhead, coding, timing recovery, or RF calibration. [MW-BER, MW-SNR, GR-CHANNEL]

The Python diagnostic uses an explicitly defined Cartesian Gray mapping. MATLAB's independent simulations use `pskmod` and `qammod`. Equivalent Gray mappings have the same AWGN BER but do not necessarily use the same on-air bit ordering. Shared-capture validation reconstructs the Python mapping explicitly. The separate WLAN receiver uses legacy WLAN mapping equations. [IEEE-A, MW-BER]

## T2. Exact BPSK and QPSK BER

For coherent detection with perfect synchronization in AWGN:

\[
Q(x)=\frac12\operatorname{erfc}(x/\sqrt2),\qquad
P_b=Q(\sqrt{2\gamma_b}).
\tag{T2}
\]

This is exact for both BPSK and Gray QPSK under these assumptions; their BER curves overlap at equal energy per uncoded bit. It does not imply equal bandwidth or equal throughput. At 0 dB the probability is approximately 0.0786496. [MW-ANALYTIC, MW-BER]

## T3. Exact square-QAM BER by decision-region integration

For `M = L^2`, each independent real axis is L-PAM with `b = log2(L)` Gray-coded bits. Define normalized axis levels `a_i = (2i-L+1)/sqrt(2(M-1)/3)` for `i=0,...,L-1`. Decision edges are the midpoints, with outer edges at negative and positive infinity. With `sigma^2=N0/2`, the probability of deciding level j after transmitting level i is:

\[
P(j\mid i)=\Phi\!\left(\frac{t_{j+1}-a_i}{\sigma}\right)
             -\Phi\!\left(\frac{t_j-a_i}{\sigma}\right).
\tag{T3}
\]

Let `h(i,j)` be the Hamming distance between the Gray labels at levels i and j. The exact uncoded bit error probability is:

\[
P_b=\frac{1}{L b}\sum_{i=0}^{L-1}\sum_{j=0}^{L-1}h(i,j)P(j\mid i).
\tag{T4}
\]

The two axes have identical error statistics, so averaging bit errors over both axes gives this same expression. All transitions, including nonadjacent decisions, are included. Positive-tail probabilities use a survival-function form to avoid cancellation. Implementations: `antenna_bench/math.py::exact_ber` and `matlab/gray_awgn_ber.m`. The independent MATLAB oracle is `berawgn`; this is not a transcription of its implementation. [MW-ANALYTIC, MW-BER; CHO-YOON is related literature]

The frequently used approximation

\[
P_b\approx\frac4k(1-M^{-1/2})Q\!\left(\sqrt{\frac{3k\gamma_b}{M-1}}\right)
\]

keeps dominant nearest-neighbour contributions. It is not used as the exact low-SNR benchmark here. An exact uncoded formula is also not the theoretical post-FEC BER of a coded Wi-Fi packet.

## T4. Two different coded OFDM energy conventions

Keep modulation order `M`, bits per mapped symbol `k`, and coding rate `R_c` distinct. For the selected non-HT waveform, `NFFT=64`, `NSD=48`, `NSP=4`, `NST=52`, and `NCP=16`. DATA symbols have 80 time samples. [IEEE-A, MW-NHT, MW-OFDM]

**Useful-constellation reference convention:** define information-bit energy as `Eb_ref = Es/(k Rc)`. It excludes energy assigned to pilots and cyclic prefix. Then:

\[
\mathrm{SNR}_{SC,dB}=(E_{b,ref}/N_0)_{dB}+10\log_{10}(kR_c),
\]
\[
\mathrm{SNR}_{sample,dB}=\mathrm{SNR}_{SC,dB}+10\log_{10}(52/64).
\tag{T5}
\]

The subcarrier-to-time-domain relation follows Parseval's theorem with equal expected energy on the 52 active tones. The other FFT bins carry no signal but still contain noise. [MW-SNR, MW-CONVERT]

**Nominal DATA-inclusive convention:** count total expected DATA-field energy, including pilots and CP, against the nominal `NDBPS = 48 k Rc` information-bit capacity per OFDM symbol:

\[
\frac{E_{b,DATA}}{N_0}=\frac{\mathrm{SNR}_{SC}}{kR_c}
\frac{52}{48}\frac{80}{64},\qquad
\mathrm{SNR}_{sample}=\frac{E_{b,DATA}}{N_0}\frac{48kR_c}{80}.
\tag{T6}
\]

The coded WLAN simulation uses T6 and measures signal power over the active DATA waveform, excluding its idle gap. Its x-axis does **not** include preamble/L-SIG energy, nor exact PSDU overhead from SERVICE, tail, padding, MAC headers, FCS, or idle time. It is not application energy per delivered bit. For an application-energy study, calculate total burst energy directly and divide by the stated payload bit count; report that as a different axis.

The symbol-rate theory uses T1, not T6. The GRC Wi-Fi replay parameter `snr_db` is DATA **time-sample SNR**, not Eb/N0 and not active-subcarrier SNR. Every chart states its convention.

## T5. Reference-based EVM

For the selected aligned reference symbols `s_i` and recovered symbols `r_i`:

\[
\epsilon=\sqrt{\frac{\sum_i|r_i-s_i|^2}{\sum_i|s_i|^2}},\qquad
\mathrm{EVM}_{\%}=100\epsilon,\qquad
\mathrm{EVM}_{dB}=20\log_{10}\epsilon.
\tag{T7}
\]

This matches average-reference-signal-power normalization in `comm.EVM`. The denominator is the actual selected reference energy, not peak constellation power. Zero error has EVM=0 and dB EVM=-infinity; JSON represents the latter as null rather than emitting nonstandard Infinity values. [MW-EVM]

For the diagnostic AWGN model with known channel and no fitted correction, expected normalized squared EVM is approximately `1/(k gamma_b)` for a long balanced capture. Equivalently, EVM is approximately `1/sqrt(SNR_SC)` in this restricted model. BPSK's detector ignores quadrature noise, but complex EVM still counts it. A noisy channel estimate, residual phase error, interference, equalizer noise enhancement, or nonlinear distortion breaks a simple EVM-to-SNR interpretation.

The WLAN scorer uses 48 DATA tones, excluding pilots and training from the primary EVM mask. It reports L-LTF-based ZF correction and the precise FFT window. **Both L-LTF and DATA use offset 1.0, at the end of the CP.** MATLAB's default offset is different; identical clean signals can agree while differing noisy sample windows do not. The AWGN cross-check disables CFO and pilot tracking because neither impairment is injected. A hardware receiver needs independently validated tracking before use. No RX-payload least-squares fitting is allowed in these primary metrics. [MW-LLTF, MW-RECOVER]

For pooling packets, sum error energies and reference energies first, then apply T7. Averaging EVM dB or percentages produces a different statistic. Keep received power and the estimated channel response separately; equalization removes link gain from EVM.

## T6. BER, packet loss, and uncertainty

\[
\widehat P_b=N_{errors}/N_{compared}.
\tag{T8}
\]

The diagnostic compares k hard bits per aligned symbol. The WLAN Python scorer reports mapped pre-FEC DATA bits, including transmitted coded SERVICE/tail/pad content. MATLAB separately compares recovered PSDU bits after FEC and descrambling. These denominators differ by design; do not compare their raw bit counts as if they were the same metric.

Packet errors include a PSDU mismatch or a failed L-SIG check in the current schedule-assisted example. Truncated/unavailable expected packets remain in the packet denominator. Synthetic PSDUs have no MAC FCS; do not call this an FCS-based PER or claim association with a Wi-Fi access point.

For independent Bernoulli bit errors, use a two-sided 95% Clopper-Pearson interval, as calculated by `berconfint` and by SciPy beta quantiles. With zero errors in N independent trials, the **one-sided** 95% upper bound is:

\[
p_U=1-0.05^{1/N}\approx2.996/N.
\tag{T9}
\]

A two-sided 95% interval instead has upper endpoint `1-0.025^(1/N)`, approximately `3.689/N`. The charts deliberately use the one-sided bound for downward triangle markers on zero-error observations. Such points are censored upper limits, not measured nonzero BER. [MW-CI, CLOPPER-PEARSON]

Independence is an assumption: Gray-QAM bit errors within one symbol can be correlated, and decoded/post-FEC or fading-link errors can be strongly bursty. Bit-binomial confidence bars are therefore labeled nominal. For paper data, retain errors/counts per packet and independent repetition, and use packet/repetition-level uncertainty or an appropriately justified clustered analysis. Twelve coded packets per point in the demonstration are exploratory, not a precision study.

## Source-to-code map

| Equation / definition | Python | MATLAB | Reference |
| --- | --- | --- | --- |
| T1 | `scripts/run_python_reference.py`, GRC noise expression | `run_theory.m` | MW-BER, MW-SNR |
| T2-T4 | `exact_ber` | `gray_awgn_ber.m`, oracle `berawgn` | MW-ANALYTIC, MW-BER |
| T5-T6 | GRC replay uses sample-SNR directly | `run_theory.m`, `run_wlan_awgn.m` | MW-SNR, MW-CONVERT; explicit energy derivation above |
| T7 | `score`, `recover_symbols` | `validate_python_results.m`, `recover_reference_packet.m` | MW-EVM, MW-LLTF, MW-RECOVER |
| T8-T9 | `binomial_interval`, `zero_error_upper_bound` | `berconfint`, explicit one-sided expression | MW-CI, CLOPPER-PEARSON |

See [validation evidence](VALIDATION.md) and the generated `results/validation/status.json` for what was actually executed.
