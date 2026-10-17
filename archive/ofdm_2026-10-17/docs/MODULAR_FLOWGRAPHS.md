# Editing the benchmark as an RF engineer

Start with the two labs in `grc/`. Change a Parameter value, generate (F5), run (F6), and stop (F7). Each run uses fixed settings so its accumulated BER and EVM describe one condition.

## Which control should I change?

| RF task | Where to edit | Meaning |
| --- | --- | --- |
| BPSK / QPSK / 16-QAM / 64-QAM | Modem lab: `order` | 2 / 4 / 16 / 64 |
| Legacy Wi-Fi modulation and coding | Wi-Fi lab: `rate_index` | 0 through 7; see SISO_LABS.md |
| Sweep path loss at fixed transmitted power | Either lab: `path_loss_db` | Power loss in dB; noise stays fixed |
| Set noise in the symbol experiment | Modem: `ebno_db` | TX-reference uncoded Eb/N0, dB |
| Set noise in the Wi-Fi experiment | Wi-Fi: `snr_db` | TX active-burst average power / noise power, dB |
| Add multipath | Wi-Fi: `channel_taps` | Causal complex voltage taps, e.g. `1, 0.2+0.15j, 0, -0.1j` |
| Add carrier offset | Wi-Fi: `cfo_hz` | Hz at the logical 20 MHz sample rate |
| Choose a different noise realization | Either lab: `noise_seed` | Integer seed; repeat the seed for repeatable conditions |
| Choose run length | `symbol_count` or `packet_count` | Positive = finite; zero = run until Stop |
| Slow the displays down | `pace` | Playback speed; Wi-Fi's logical sample rate remains 20 MHz |
| Change electronic steering | `antenna_steering.py` | Replace the hardware backend; command, await ready, settle, then capture |

A positive 6 dB loss multiplies voltage by approximately 0.501, hence power by approximately 0.251. FIR tap values are voltage ratios and are not automatically normalized. Complex noise voltage is RMS magnitude: `E[|noise|²] = noise_voltage²`.

## Reusable flowchart modules

The main labs now use four normal GNU Radio hierarchical blocks. A hierarchical block is simply a smaller flowchart inside a block; its processing is built from stock GNU Radio blocks. Open the source below to change its internals.

| Editable source | Input → output | Contents / controls |
| --- | --- | --- |
| [Symbol mapper](../grc/modules/bench_symbol_mapper.grc) | Unpacked 0/1 bytes → complex symbols | Pack k bits, Chunks to Symbols; `order` |
| [Hard-decision decoder](../grc/modules/bench_symbol_demapper.grc) | Complex symbols → unpacked 0/1 bytes | Constellation Decoder, Unpack k bits; `order`; reused for received and reference streams |
| [Scalar channel](../grc/modules/bench_scalar_channel.grc) | Complex samples → complex samples | Multiply Const, Noise Source, Add; voltage gain, noise RMS, seed |
| [Multipath channel](../grc/modules/bench_fir_channel.grc) | Complex samples → complex samples | FIR Filter, Rotator, Noise Source, Add; taps, voltage gain, offset Hz, sample rate Hz, noise RMS, seed |

The mapper consumes `log2(order)` bit bytes per symbol. The decoder produces the same number per symbol. Channels preserve sample count and sample rate. A replacement must preserve these contracts or the reference alignment and BER counts must also change.

The five smaller supporting flowcharts remain direct stock-block chains. The Wi-Fi burst receiver and exact cumulative BER/EVM counters remain Python blocks: the receiver implements the experiment's known-burst training/normalization convention, and the meters archive exact counts and pooled energies. Their implementations are in `antenna_bench/live.py` and `antenna_bench/gr_metrics.py`.

## Edit, compile, run

Open the labs and any module you want to change:

```sh
antenna-grc grc/siso_modem_lab.grc grc/siso_wlan_lab.grc grc/modules/bench_fir_channel.grc
```

The launcher compiles the saved modules and configures their project-local search path. They appear under **Antenna benchmark** in the block library. No global GNU Radio installation changes are required.

After saving a module edit, compile modules and parent graphs:

```sh
python scripts/compile_flowgraphs.py
```

Then reopen the parent through `antenna-grc`, generate, and run. Reopening refreshes the block library, including changes to module parameters or ports. To make an independent experiment, use GRC **Save As** with a new filename and change the Options block ID to match it. The compiler processes top-level `.grc` files in `grc/` and modules in `grc/modules/`; the fixed validation suite exercises the original benchmark labs.

To validate the saved benchmark sources and update the report:

```sh
python scripts/run_all.py
```

**This now preserves your GRC source edits.** It recompiles saved files and replaces generated results. The validation cases supply their own settings, so changing a GUI default does not redefine the published test sweep.

`python scripts/build_flowgraphs.py` explicitly recreates all seven top-level flowcharts and four module sources from the Python templates. It overwrites manual edits in those files. Use it only when deliberately restoring/updating the templates. The equivalent full validation option is `python scripts/run_all.py --regenerate-sources`.

## If you want to edit Python or MATLAB

| File | What it controls |
| --- | --- |
| `antenna_bench/live.py` | Wi-Fi receiver equations, explained in six numbered stages; taps and normalized burst references |
| `antenna_bench/gr_metrics.py` | BER = errors / compared bits; EVM from accumulated error/reference energies; saving on Stop |
| `antenna_bench/math.py` | Independent uncoded BER theory and confidence limits |
| `antenna_bench/wlan.py` | WLAN constellation labeling and the independent AWGN receiver |
| `antenna_steering.py` | Steering command interface and mock hardware |
| `matlab/run_theory.m` | MATLAB uncoded BER/EbN0 and EVM charts; `symbolsPerPoint` controls simulation count |
| `matlab/run_wlan_awgn.m` | Optional coded Wi-Fi BER/PER sweep; `packetsPerPoint` controls count |
| `matlab/export_wlan_reference.m` | WLAN Toolbox waveform export; reads `configs/wifi_nonht_defaults.json` |
| `matlab/validate_live_labs.m` | Independent MATLAB comparison against actual GNU Radio captures |
| `scripts/build_siso_labs.py` | Original lab templates: controls, blocks, displays and connections |
| `scripts/modular_flowgraphs.py` | Packages stock-block stages into reusable GRC modules |
| `scripts/flowgraph_layout.py` | Canvas placement and section labels |
| `scripts/plot_live_results.py` | Report figures, legends and axis labels |

`grc/generated/` is machine-generated Python: edit the `.grc` sources rather than these outputs. `results/` contains generated evidence, not experiment source settings. GRC's `work`/`general_work` functions receive chunks of samples from its scheduler; a chunk need not be a complete burst. The receiver buffers a full known burst before processing it.

The current Wi-Fi receiver needs known timing, rate, and length. These are software simulations, and the two USRP graphs have only been compiled. Hardware commissioning remains separate.

Reference: GNU Radio's [Hier Blocks and Parameters tutorial](https://wiki.gnuradio.org/index.php/Hier_Blocks_and_Parameters) explains the standard hierarchy mechanism used here.
