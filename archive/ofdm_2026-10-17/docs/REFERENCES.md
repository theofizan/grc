# References and claim traceability

Accessed October 16, 2026. These are source identifiers used by code and documentation, not IEEE-assigned clause identifiers. `references.bib` contains reusable bibliography entries. Live vendor documentation may describe a newer release than the local installation; the validation manifest records the actual MATLAB and GNU Radio versions used.

| Identifier | Citable source | Supports |
| --- | --- | --- |
| IEEE-A | IEEE, *IEEE Std 802.11a-1999: High-speed Physical Layer in the 5 GHz Band*, 1999. [Archived standard PDF](https://labs.ece.uw.edu/funlab/802/802.11a-1999.pdf) | Historical legacy OFDM PHY; Clause 17, Tables 78-79, mapping in 17.3.5.7. Use the selected consolidated edition for final normative compliance claims. |
| MW-NHT | MathWorks, [wlanNonHTConfig](https://www.mathworks.com/help/wlan/ref/wlannonhtconfig.html) | Non-HT rate/coding table, PSDU configuration, OFDM timing; references IEEE 802.11-2020 Clause 17. |
| MW-OFDM | MathWorks, [wlanNonHTOFDMInfo](https://www.mathworks.com/help/wlan/ref/wlannonhtofdminfo.html) | FFT, CP, sample rate, data/pilot and signed-bin indexing. |
| MW-BER | MathWorks, [berawgn](https://www.mathworks.com/help/comm/ref/berawgn.html) | Uncoded Gray-mapped AWGN BER oracle; scope excludes FEC. |
| MW-ANALYTIC | MathWorks, [Analytical Expressions Used in berawgn](https://www.mathworks.com/help/comm/ug/analytical-expressions-used-in-berawgn-function-and-bit-error-rate-analysis-app.html) | Exact BPSK/QPSK expressions and QAM error-analysis context. |
| MW-EVM | MathWorks, [comm.EVM](https://www.mathworks.com/help/comm/ref/comm.evm-system-object.html) | EVM error/reference energy definitions and normalization options. |
| MW-SNR | MathWorks, [SNR Definition in End-to-End Simulations](https://www.mathworks.com/help/wlan/ug/snr-definition-used-in-end-to-end-simulations.html) | WLAN subcarrier SNR and time-domain noise convention; Parseval relationship. |
| MW-CONVERT | MathWorks, [convertSNR](https://www.mathworks.com/help/comm/ref/convertsnr.html) | Conversion among bit, symbol, sample, and subcarrier SNR with explicit parameters. |
| MW-CI | MathWorks, [berconfint](https://www.mathworks.com/help/comm/ref/berconfint.html) | Error-count estimates and confidence interval interface. |
| MW-WAVE | MathWorks, [wlanWaveformGenerator](https://www.mathworks.com/help/wlan/ref/wlanwaveformgenerator.html) | PPDU generation, scrambler initialization, idle time, and window transition. |
| MW-RECOVER | MathWorks, [wlanNonHTDataRecover](https://www.mathworks.com/help/wlan/ref/wlannonhtdatarecover.html) | Decoding/equalization outputs, ZF/MMSE and pilot-tracking options, FFT offset. |
| MW-DEMAP | MathWorks, [wlanConstellationDemap](https://www.mathworks.com/help/wlan/ref/wlanconstellationdemap.html) | Independent hard-decision bit labels for the legacy WLAN constellation and coded-bit counts. |
| MW-LLTF | MathWorks, [wlanLLTFDemodulate](https://www.mathworks.com/help/wlan/ref/wlanlltfdemodulate.html) | Training-field FFT window; positional sampling-offset argument and default 0.75. |
| GR-CHANNEL | GNU Radio, [channel_model API](https://www.gnuradio.org/doc/doxygen/classgr_1_1channels_1_1channel__model.html) | Channel impairment parameters and externally calibrated noise voltage. Actual delivered graphs use an explicit Gaussian noise source and Add block, preserving finite-file sample alignment. |
| UHD-X3X0 | Ettus Research, [USRP X3x0 manual](https://files.ettus.com/manual/page_usrp_x3x0.html) | Device interfaces, daughterboards, clocks, streaming and hardware configuration. |
| CLOPPER-PEARSON | C. J. Clopper and E. S. Pearson, “The use of confidence or fiducial limits illustrated in the case of the binomial,” *Biometrika*, vol. 26, no. 4, pp. 404-413, 1934. [DOI](https://doi.org/10.1093/biomet/26.4.404) | Foundational binomial interval reference. The zero-error one-sided expression is derived directly from `(1-p)^N=alpha` in THEORY.md. |
| CHO-YOON | K. Cho and D. Yoon, “On the general BER expression of one- and two-dimensional amplitude modulations,” *IEEE Transactions on Communications*, vol. 50, no. 7, pp. 1074-1080, 2002. [DOI](https://doi.org/10.1109/TCOMM.2002.800818) | Related exact Gray-PAM/QAM BER literature, also listed by MathWorks. Full publisher text was not available in this session; no claimed equation/page correspondence beyond verified bibliographic metadata. |

## Citation boundaries for the paper

For the live SISO implementation, [GNU Radio Qt GUI](https://wiki.gnuradio.org/index.php/QT_GUI) documents the plotting facilities, and the [native constellation decoder API](https://www.gnuradio.org/doc/doxygen/classgr_1_1digital_1_1constellation__decoder__cb.html) documents hard symbol decisions. The [SISO lab guide](SISO_LABS.md) states the actual normalization, receiver assumptions and measured software checks. These interfaces do not independently establish implementation correctness.

A related experimental precedent is H. J. Cho, J. H. Lee, K. H. Shin and J. W. Yu, “EVM Analysis of Chip-Integrated Phased Array Antenna Using USRP for 5G Communication,” EuMC 2024, pp. 341–344, [DOI: 10.23919/EuMC61614.2024.10732723](https://doi.org/10.23919/EuMC61614.2024.10732723). The [authors' university record](https://pure.kaist.ac.kr/en/publications/evm-analysis-of-chip-integrated-phased-array-antenna-using-usrp-f/) describes USRP EVM measurements versus steering angle at 28 GHz. This supports the relevance of link-level antenna evaluation; it does not prescribe this project's waveform, calibration, or single-stream implementation.

- Cite the IEEE standard for normative PHY requirements, and cite vendor documentation for implementation interfaces. The current packet generator is MATLAB WLAN Toolbox; do not present it as a newly implemented Python transmitter.
- The exact QAM implementation integrates decision-region probabilities with Hamming weights. Cite the documented derivation and validation; do not call the nearest-neighbour approximation exact.
- Cite tool versions and archive the project's source/configuration hashes with figures. A source link alone does not establish the correctness of a particular implementation.
- These documents support definitions and methods, not empirical performance of the user's antenna. No result in the software package supports an antenna superiority claim until controlled RF data are acquired.
- The target consolidated edition is IEEE 802.11-2020's legacy OFDM provisions. This package includes the historical 802.11a source and MathWorks' documented cross-reference, not a completed clause-by-clause audit of the 2020 text.
