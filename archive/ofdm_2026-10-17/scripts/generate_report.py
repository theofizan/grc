"""Build the Markdown results report from the current run's measured artifacts."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RATES = (6, 9, 12, 18, 24, 36, 48, 54)
MODS = ("BPSK", "BPSK", "QPSK", "QPSK", "16-QAM", "16-QAM", "64-QAM", "64-QAM")
CODING = ("1/2", "3/4", "1/2", "3/4", "1/2", "3/4", "2/3", "3/4")


def read(path):
    return json.loads((RESULTS / path).read_text())


def rows(path):
    with (RESULTS / path).open() as f:
        return list(csv.DictReader(f))


def number(x):
    x = float(x)
    return "0" if x == 0 else f"{x:.5g}"


def main():
    manifest = read("validation/status.json")
    mismatches = [
        name
        for name, digest in manifest["source_sha256"].items()
        if not (ROOT / name).is_file()
        or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest
    ]
    assert not mismatches, f"Rerun validation after source changes: {mismatches}"
    installation = read("validation/install_check.json")
    theory = read("theory/validation.json")
    coded = read("wlan_awgn/manifest.json")
    wifi = [read(f"grc/wlan_rate_{i}_matlab.json") for i in range(8)]
    fft = [read(f"grc/wlan_rate_{i}_fft_validation.json") for i in range(8)]
    grc = read("grc/symbol_runtime_validation.json")
    output = []

    def p(text=""):
        output.append(text + "\n")

    def table(headers, data):
        p("| " + " | ".join(headers) + " |")
        p("| " + " | ".join("---" for _ in headers) + " |")
        for row in data:
            p("| " + " | ".join(str(x) for x in row) + " |")
        p()

    def figure(path, caption):
        p(f'![{caption.split(".")[0]}]({path}.png)\n')
        p(caption + f" [Vector PDF]({path}.pdf).\n")

    p("# SISO benchmark: supporting reference-validation appendix\n")
    p(
        "Start with the [primary SISO results report](REPORT.md) and [live lab guide](../docs/SISO_LABS.md). "
        "This appendix retains the original reference baselines, theory figures and complete numerical tables.\n"
    )
    p(
        f'Run completed **{manifest["utc"]}**. Overall status: **{manifest["status"].upper()}**; '
        f'**{len(manifest["runs"])} command stages** completed. All source hashes match this report generation. '
        "[Run manifest](validation/status.json) records exact commands, elapsed times, versions, and SHA-256 hashes.\n"
    )
    p(
        "These results validate the software measurement chain in simulation. They do not measure the developed antenna. "
        "The three supporting software flowgraphs were executed alongside the two new complete SISO labs; the two UHD graphs were compiled. "
        "Default UHD discovery found **no USRP device**. No RF streaming or live steering was performed.\n"
    )
    p("## 1. Installation and reproducibility\n")
    table(
        ["Component", "Validated installation"],
        [
            ["Python", f'{manifest["python"]}; `{installation["interpreter"]}`'],
            ["GNU Radio / UHD", f'{installation["gnuradio"]} / {installation["uhd"]}'],
            [
                "MATLAB",
                theory["matlabVersion"]
                + "; Communications Toolbox + WLAN Toolbox exercised",
            ],
            [
                "NumPy / SciPy / Matplotlib",
                " / ".join(
                    installation["packages"][x]
                    for x in ("numpy", "scipy", "matplotlib")
                ),
            ],
            ["Platform", manifest["platform"]],
        ],
    )
    p(
        "**Installation fix:** installed this source tree as the editable `antenna-benchmark` package into radioconda "
        "with `--no-deps --no-build-isolation`; existing scientific/radio packages were retained. "
        "A subprocess running from `/tmp` with `PYTHONPATH` removed successfully imported the project, GNU Radio/UHD, "
        "GTK, Cairo, and scientific dependencies. The `antenna-grc` launcher selects that interpreter and executable path. "
        "[Diagnostic details](validation/install_check.json).\n"
    )
    p(
        "**Qt installation fix:** added the compatible conda-forge `pyqtwebengine`, `qt-webengine`, `giflib`, and `libwebp` packages. "
        "The package transaction replaced no existing packages. Importing `PyQt5.QtWebEngineWidgets.QWebEngineView` succeeds, "
        "fixing the missing documentation-browser component found during the Qt frontend startup check. "
        "[Transaction plan](validation/qt_webengine_plan.json), [installation log](validation/qt_webengine_install.log).\n"
        if installation["qt_document_browser_available"]
        else "The optional Qt documentation browser is unavailable.\n"
    )
    p(
        "Open the five flowgraphs by double-clicking [Open Benchmark GRC.command](../Open%20Benchmark%20GRC.command), "
        "or run `/Users/ofi/radioconda/bin/antenna-grc`. The launcher uses the installed GTK frontend. "
        "The system Xcode command-line tools separately report an unaccepted Xcode license; no license was accepted, and this validation uses radioconda executables.\n"
    )
    p(
        "**Folder-local environment:** `.venv` shares the installed radioconda native/scientific libraries via "
        "`--system-site-packages`; direnv activates it automatically in interactive project terminals. "
        "The interpreter recorded above identifies the environment used for this run. "
        "[Environment setup and verification](../docs/ENVIRONMENT.md), "
        "[executed shell-transition checks](validation/project_environment_check.json).\n"
    )
    p(
        "Reproduce everything from the repository:\n\n```sh\n"
        "cd /Users/ofi/repos/grc\n/Users/ofi/repos/grc/.venv/bin/python scripts/run_all.py\n```\n"
    )
    p(
        "On another machine, install the project into that machine's GNU Radio Python using "
        "`python -m pip install --no-deps --no-build-isolation -e .`, then use `antenna-grc`. "
        "The double-click `.command` file is specific to this Mac. MATLAB needs licensed Communications and WLAN Toolboxes. "
        "Results are replaced on rerun; archive `results/` before changing the experiment.\n"
    )
    p("## 2. Flowgraph execution evidence\n")
    table(
        ["Editable GRC source", "Validation performed", "Result"],
        [
            [
                "[awgn_symbol_benchmark.grc](../grc/awgn_symbol_benchmark.grc)",
                "Compiled; finite execution at M = 2, 4, 16, 64; counts, noise power, BER envelope; independent MATLAB fixture scoring",
                "PASS",
            ],
            [
                "[wlan_reference_channel.grc](../grc/wlan_reference_channel.grc)",
                "Compiled; all 8 rates; exact expected packet availability; Python pre-FEC BER/EVM and MATLAB post-FEC decoding",
                "PASS",
            ],
            [
                "[wlan_ofdm_fft.grc](../grc/wlan_ofdm_fft.grc)",
                "Compiled; all 8 rates; vector counts and every FFT bin compared with NumPy on identical IQ",
                "PASS",
            ],
            [
                "[usrp_wifi_tx.grc](../grc/usrp_wifi_tx.grc)",
                "Native UHD blocks compiled; no radio found; no transmission",
                "COMPILE ONLY",
            ],
            [
                "[usrp_wifi_rx.grc](../grc/usrp_wifi_rx.grc)",
                "Native UHD blocks compiled; no radio found; no streaming",
                "COMPILE ONLY",
            ],
        ],
    )
    p(
        "The compiler's “no flow control” warning on finite software graphs is expected: finite files/vectors run to completion as quickly as possible. "
        "Their termination and output lengths are checked. UHD supplies the sample clock in hardware graphs. "
        "CLI compilation/runtime and GTK import checks are automated; interactive toolbar operation is not asserted by the test suite.\n"
    )
    p("### Native GNU Radio symbol graph, 8 dB uncoded Eb/N0\n")
    table(
        [
            "Modulation",
            "Compared bits",
            "Bit errors",
            "Observed BER",
            "Exact BER",
            "RMS EVM (%)",
            "Noise power / target",
        ],
        [
            [
                label,
                r["bits"],
                r["errors"],
                number(r["ber"]),
                number(r["theory_ber"]),
                f'{r["evm_percent"]:.3f}',
                f'{r["measured_noise_power"]/r["expected_noise_power"]:.5f}',
            ]
            for label, r in zip(("BPSK", "QPSK", "16-QAM", "64-QAM"), grc["cases"])
        ],
    )
    p(
        "Every case contains exactly 100,000 TX/RX symbols. The noise-power tolerance is ±3%; "
        "the BER check uses a conservative six-standard-deviation envelope with a symbol-based variance bound "
        "to allow correlated QAM bit decisions. [Per-case results](grc/symbol_runtime_validation.json); "
        "[MATLAB cross-check](grc/matlab_cross_validation.json).\n"
    )
    p("## 3. Uncoded theory, Monte Carlo, and uncertainty\n")
    p(
        "BPSK/QPSK use the coherent exact BER expression; square QAM integrates every PAM decision region and Hamming distance. "
        "Each implementation uses unit average symbol energy and complex AWGN power `N0 = 1/(log2(M) × 10^(EbNo_dB/10))`. "
        "Python and MATLAB use independently generated samples, so their observed BER need not be identical. "
        "The MATLAB exact calculation agrees with `berawgn` to a worst relative error of "
        f'**{max(theory["maxRelativeErrorAgainstBerawgn"]):.3g}** where the oracle BER exceeds 1e-14. '
        "[Derivation](../docs/THEORY.md), [MathWorks analytical expressions](https://www.mathworks.com/help/comm/ug/analytical-expressions-used-in-berawgn-function-and-bit-error-rate-analysis-app.html).\n"
    )
    figure(
        "theory/ber_vs_ebno",
        "**Figure 1. Exact uncoded BER and MATLAB Monte Carlo.** "
        "Blue solid: BPSK; orange dashed: QPSK; green dotted: 16-QAM; purple dash-dot: 64-QAM. "
        "Circles show BER estimates with nominal two-sided 95% bit-binomial confidence bars. Downward triangles show one-sided 95% upper limits when zero errors occur; they are not BER estimates. "
        "BPSK and QPSK exact curves overlap. 100,000 symbols per simulated point.",
    )
    figure(
        "theory/evm_vs_ebno",
        "**Figure 2. RMS EVM versus uncoded Eb/N0.** "
        "Colors and line styles identify the same four modulations as Figure 1; lines predict `100/sqrt(log2(M) × Eb/N0)`, circles are MATLAB estimates. "
        "EVM is normalized by the total known reference-symbol energy, with no payload gain/phase fit. "
        "[EVM definition](https://www.mathworks.com/help/comm/ref/comm.evm-system-object.html).",
    )
    figure(
        "theory/ofdm_snr_conventions",
        "**Figure 3. Two different OFDM energy conventions.** "
        "(a) Constellation reference: `SNR_sc = EbNo_ref + 10log10(k Rc)`. "
        "(b) DATA-inclusive reference: `SNR_sample = EbNo_DATA + 10log10(48 k Rc / 80)`. "
        "Legends state modulation and code rate. DATA energy includes pilots and CP; preamble, header, idle, and padding efficiency are excluded. "
        "The two x-axis quantities have different definitions and must not be interchanged. "
        "[WLAN SNR definitions](https://www.mathworks.com/help/wlan/ug/snr-definition-used-in-end-to-end-simulations.html).",
    )
    figure(
        "theory/zero_error_confidence",
        "**Figure 4. Zero-error detection sensitivity.** "
        "Solid: exact one-sided 95% bound `1 - 0.05^(1/N)`; dashed: `3/N` approximation. "
        "This assumes independent Bernoulli trials. Multiple bit errors within a QAM symbol and post-FEC bursts can be correlated; bit-binomial bounds for those cases are nominal. "
        "[Clopper–Pearson reference](https://doi.org/10.1093/biomet/26.4.404).",
    )
    p("## 4. Coded legacy Wi-Fi AWGN sweep\n")
    p(
        f'This separate MATLAB experiment covers **{coded["points"]} rate/EbNo points**, **{coded["packetsPerPoint"]} '
        "independently noised 1000-byte PSDUs per point. Timing/rate/length are supplied. The receiver uses a noisy, "
        "unsmoothed L-LTF channel estimate and ZF equalization, with no CFO or pilot tracking in this AWGN case. "
        "These are decoded payload BER and packet error fraction, not the uncoded formulas of Figure 1.\n"
    )
    figure(
        "wlan_awgn/coded_wlan_ber_per",
        "**Figure 5. Coded Wi-Fi BER and PER.** "
        "Both legends state modulation, coding rate, and PHY rate. Circles are observed estimates; lines only join sampled estimates. "
        "BER triangles show nominal independent-bit one-sided 95% zero-error limits. PER counts payload mismatch or L-SIG failure. "
        "With only 12 packets per point, PER increments are 1/12, and observing zero failed packets still gives a one-sided 95% independent-packet PER upper limit of about 0.221. "
        "Coincident zero-error upper limits overlap. This exploratory sweep is insufficient for a low-PER paper claim.",
    )
    p("## 5. Cross-language and native FFT results\n")
    figure(
        "figures/python_matlab_comparison",
        "**Figure 6. Independent uncoded software implementations.** "
        "Color/line style identifies modulation and exact theory; circles identify Python, crosses MATLAB, squares GNU Radio at 8 dB. "
        "Downward triangles identify nominal one-sided 95% zero-error upper limits in either Monte Carlo implementation. "
        "(a) BER; (b) RMS EVM. All simulations use 100,000 symbols per point. See Appendix A for exact error counts.",
    )
    p(
        "The Wi-Fi replay uses 20 Msamples/s, FFT length 64, CP length 16, 48 DATA tones, 4 pilots, "
        "16 repeated 1000-byte PSDUs per rate, 512 leading samples, and 2000 idle samples per PPDU. "
        "The waveform comes from MATLAB WLAN Toolbox with scrambler state 93, zero window transition, "
        "and one common TX scale across all rates to cap peak magnitude at 0.5. "
        "GNU Radio adds complex AWGN at **25 dB active-DATA time-sample SNR**. "
        "The training-based equalizer adds estimation error, so equalized EVM is not simply `100 × 10^(-25/20)`. "
        "[PPDU generator](https://www.mathworks.com/help/wlan/ref/wlanwaveformgenerator.html), "
        "[rate configuration](https://www.mathworks.com/help/wlan/ref/wlannonhtconfig.html).\n"
    )
    figure(
        "figures/wlan_cross_validation",
        "**Figure 7. Identical-capture validation across all eight legacy rates.** "
        "The x-axis is PHY data rate in Mb/s. (a) Python circles/line and MATLAB crosses: RMS DATA EVM. "
        "(b) Blue bars: maximum equalized-symbol difference; symbols are dimensionless, normalized constellation values. "
        "(c) Green bars: maximum native GRC FFT difference from NumPy; FFT units retain the unnormalized forward transform. "
        "The FFT operates after removing all 16 CP samples, without a window or frequency shift. "
        "Single-precision FFT rounding in (c) is distinct from receiver double-precision agreement in (b).",
    )
    table(
        [
            "Rate (Mb/s)",
            "Modulation / code",
            "EVM Python (%)",
            "EVM MATLAB (%)",
            "Pre-FEC errors / mapped bits",
            "Post-FEC errors / PSDU bits",
            "Failed / expected packets",
        ],
        [
            [
                RATES[i],
                f"{MODS[i]} {CODING[i]}",
                f'{100*read(f"grc/wlan_rate_{i}_python.json")["evm_rms"]:.6f}',
                f'{100*r["evmRms"]:.6f}',
                f'{r["preFecErrors"]} / {r["preFecBits"]}',
                f'{r["errors"]} / {r["bits"]}',
                f'{r["packetErrors"]} / {r["expectedPackets"]}',
            ]
            for i, r in enumerate(wifi)
        ],
    )
    p(
        "Pre-FEC compares hard decisions for transmitted mapped DATA bits, including encoded SERVICE/tail/pad. "
        "Post-FEC compares decoded PSDU payload bits. All expected packets were available in this schedule-assisted replay. "
        "Zero post-FEC errors are finite observations, not proof of BER = 0; error dependence prevents treating "
        "a simple bit-binomial bound as a calibrated post-FEC confidence interval.\n"
    )
    table(
        [
            "Rate (Mb/s)",
            "FFT vectors × 64 bins",
            "Maximum absolute error",
            "Relative L2 error",
            "Result",
        ],
        [
            [
                RATES[i],
                r["vectors"],
                number(r["max_absolute_error"]),
                number(r["relative_l2_error"]),
                r["status"],
            ]
            for i, r in enumerate(fft)
        ],
    )
    p(
        f'Worst shared-capture equalized-symbol difference: **{max(r["pythonMaxSymbolDifference"] for r in wifi):.4g}**; '
        f'worst pooled EVM difference: **{max(r["pythonEvmDifference"] for r in wifi):.4g}**. '
        "Python and MATLAB assert identical pre-FEC error and bit counts. Native FFT checks require identical vector shapes "
        "and bin-wise `atol=2e-6, rtol=2e-5`. [Validation tolerances](../docs/VALIDATION.md).\n"
    )
    figure(
        "figures/flowgraph_overview",
        "**Figure 8. Flowgraph architecture and execution scope.** "
        "Boxes are processing stages; arrows carry complex samples or OFDM vectors. The first three rows were executed; "
        "the UHD rows were compiled. These diagrams summarize the actual editable native `.grc` files.",
    )
    p("## 6. Boundaries for the antenna paper\n")
    p(
        "The reference waveform follows legacy non-HT OFDM settings; this package is not a completed IEEE conformance audit "
        "or an associated Wi-Fi MAC. The synthetic PSDU has no implied MAC header/FCS. "
        "Autonomous packet acquisition, L-SIG-driven configuration, independent-clock synchronization, "
        "RF calibration, UHD stream health, live steering, and antenna comparisons remain unmeasured. "
        "Steering has a command/readiness/settling framework with a tested mock backend; a real hardware adapter is still required.\n"
    )
    p(
        "For RF data, use a calibrated cabled baseline, then compare reference antenna and AUT at controlled power, geometry, "
        "polarization, and environment. Archive beam commands, readiness/settling, actual radio settings, "
        "stream errors, packet availability, BER denominators, and repeat measurements. "
        "[Paper methods](../docs/PAPER_METHODS.md), [steering contract](../docs/WIFI_AND_STEERING.md).\n"
    )
    p(
        "The historical normative source is "
        "[IEEE Std 802.11a-1999, Clause 17](https://labs.ece.uw.edu/funlab/802/802.11a-1999.pdf); "
        "the final paper should identify the chosen consolidated IEEE edition. "
        "[Citations and claim traceability](../docs/REFERENCES.md) and [BibTeX](../references.bib) separate standards, "
        "implementation documentation, and mathematical references.\n"
    )
    p("## Appendix A. All uncoded Monte Carlo points\n")
    py = rows("python/awgn_results.csv")
    ml = {
        (int(float(r["order"])), float(r["ebno_db"])): r
        for r in rows("theory/matlab_awgn_results.csv")
    }
    for order, label in zip((2, 4, 16, 64), ("BPSK", "QPSK", "16-QAM", "64-QAM")):
        p(f"### {label}\n")
        data = []
        for r in py:
            if int(r["order"]) != order:
                continue
            m = ml[order, float(r["ebno_db"])]
            data.append(
                [
                    r["ebno_db"],
                    number(r["theory_ber"]),
                    f'{r["errors"]} / {r["bits"]}',
                    number(r["ber"]),
                    f'{100*float(r["evm_rms"]):.3f}',
                    f'{m["errors"]} / {m["bits"]}',
                    number(m["ber"]),
                    f'{100*float(m["evm_rms"]):.3f}',
                ]
            )
        table(
            [
                "Eb/N0 (dB)",
                "Exact BER",
                "Python errors / bits",
                "Python BER",
                "Python EVM (%)",
                "MATLAB errors / bits",
                "MATLAB BER",
                "MATLAB EVM (%)",
            ],
            data,
        )
    p(
        "Raw counts of zero in these tables are observations. Figure triangles plot the associated upper limits instead of zero on a log axis. "
        "Full confidence bounds and energies: [Python CSV](python/awgn_results.csv), "
        "[MATLAB CSV](theory/matlab_awgn_results.csv), [dense exact theory CSV](theory/exact_theory.csv).\n"
    )
    p("## Appendix B. All coded Wi-Fi sweep points\n")
    table(
        [
            "Rate (Mb/s)",
            "Eb/N0 DATA (dB)",
            "Time SNR (dB)",
            "Errors / payload bits",
            "Post-FEC BER",
            "Failed / packets",
            "PER",
            "RMS EVM (%)",
        ],
        [
            [
                RATES[int(r["rate_index"])],
                r["data_inclusive_ebno_db"],
                number(r["sample_snr_db"]),
                f'{r["errors"]} / {r["bits"]}',
                number(r["post_fec_ber"]),
                f'{r["packet_errors"]} / {r["packets"]}',
                number(r["per"]),
                f'{100*float(r["evm_rms"]):.3f}',
            ]
            for r in rows("wlan_awgn/coded_wlan_awgn.csv")
        ],
    )
    p(
        "[Full coded sweep CSV](wlan_awgn/coded_wlan_awgn.csv), [settings manifest](wlan_awgn/manifest.json).\n"
    )
    p("## Appendix C. Command log index\n")
    table(
        ["Stage", "Exit code", "Elapsed (s)", "Log"],
        [
            [
                r["label"],
                r["exit_code"],
                f'{r["elapsed_seconds"]:.2f}',
                f'[stdout/stderr](validation/{i:02d}_{r["label"]}.log)',
            ]
            for i, r in enumerate(manifest["runs"], 1)
        ],
    )
    p(
        "This index uses the current manifest only; older log files may remain after runner changes. "
        "Generated Python is in `grc/generated/`; reference and received IQ are little-endian complex64 `.c64` files. "
        "Per-rate `.mat`/`.json` files retain reference symbols, schedule, recovery outputs, and capture hashes. "
        "[File formats and commands](../docs/FLOWGRAPHS.md).\n"
    )
    (RESULTS / "VALIDATION_APPENDIX.md").write_text("".join(output))
    from generate_siso_report import main as siso_report

    siso_report()


if __name__ == "__main__":
    main()
