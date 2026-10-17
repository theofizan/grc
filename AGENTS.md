# Project preferences

- Active scope: SISO single-carrier modulation. OFDM/Wi-Fi work stays in archive/ofdm_2026-10-17 until the user asks to resume it.
- The user is an RF engineer, not a programmer. Keep normal changes in GRC parameters, use descriptive names and units, and explain RF meaning.
- Use installed stock GNU Radio blocks. Keep flowcharts flat and similar to the downloaded M-ASK/M-PSK/QAM tutorial, without project custom or hierarchical blocks.
- Keep controls across the top, processing left-to-right, BER below, and displays connected through short virtual links. Inspect GRC's actual exported canvas after layout edits.
- Preserve manual GRC edits during validation. Builders overwrite templates only when explicitly invoked.
- Keep one TX and one RX stream. Compare modulation formats at consistent nominal transmitted energy and report noise conventions explicitly.

- Baseline symbol rate is 1 Msymbol/s with four samples/symbol (4 Msamples/s). Keep plot axes consistent with each stream rate. Gross data rate is symbol rate times log2(M), not measured packet goodput. Maintain MATLAB validation against captured bit/symbol arrays.

- Power convention: |IQ|² is milliwatts. TX setting is nominal average conducted dBm; net loss includes antenna gains/cable losses. Receiver noise dBm is integrated across Fs, and stays fixed in physical link-budget sweeps. Preserve sampled-peak versus average distinctions and RF calibration limits.

- Use the user's BPSK control grouping saved in configs/control_layout.json. Preserve manually edited DSP settings when changing presentation.
- Use resizable 2x2 dashboards with four useful charts per tab. Do not force individual plot widgets or canvases to square sizes. Keep equal I/Q axis scales for constellation figures. Pack controls by their actual rendered sizes with 8 px gaps; configs/packed_controls.json records positions.
- Show real adaptive LMS equalization, pre-EQ and post-EQ symbols, and raw RX plus middle/post-EQ eyes. Symbol-rate eyes must be clearly labeled as display-only RRC reconstructions. Validate the actual FIR outputs and tap history independently in MATLAB.
- Label RX SNR with noise bandwidth Fs, distinguish known-reference calculations from blind estimation, and label Eb/N0 per uncoded bit. EVM guide circles are RMS-radius references, not compliance or confidence bounds. Data-aided EVM uses actual TX/RX symbol alignment without fitting away errors.

- Keep the editable boxed section Notes (section_*), with the header title only and no description/subtitle or comment underneath. The project GTK launcher renders these as large blue banners through antenna_bench/section_notes.py, without custom DSP blocks or changes to installed GNU Radio. Preserve banner positions in normal validation; explicit layout tools can repack them.
