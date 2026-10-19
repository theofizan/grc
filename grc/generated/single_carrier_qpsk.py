#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: QPSK single carrier | stock blocks
# Author: Antenna benchmark
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import blocks
import numpy
from gnuradio import channels
from gnuradio.filter import firdes
from gnuradio import digital
from gnuradio import filter
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import math
import sip
import threading


def snipfcn_square_plot_panels(self):
    # Plot layout is a resizable 2x2 grid, not a square-canvas constraint.
    for index in range(self.views.count()):
        layout = getattr(self, "views_grid_layout_"+str(index))
        if layout is not None:
            layout.setColumnStretch(0, 1)
            layout.setColumnStretch(1, 1)
            layout.setRowStretch(1, 1)
            layout.setRowStretch(2, 1)
            # Native sinks otherwise request a large minimum and force scrolling.
            for row in (1, 2):
                for column in (0, 1):
                    panel = layout.itemAtPosition(row, column).widget()
                    panel.setMinimumSize(0, 0)
                    panel.setSizePolicy(Qt.QSizePolicy.Ignored, Qt.QSizePolicy.Ignored)
    self.views.setMinimumSize(0, 0)
    self.views.setSizePolicy(Qt.QSizePolicy.Ignored, Qt.QSizePolicy.Ignored)
    self.resize(1180, 900)

def snipfcn_equalizer_initial_taps(self):
    self.equalizer.set_taps([0j]*((self.eq_taps-1)//2)+[1+0j]+[0j]*(self.eq_taps//2))

def snipfcn_link_table(self):
    # Link budget and BER test as a spreadsheet-style table (display only).
    # Values come from stock Probe Signal blocks; edit rows here to change it.
    rows = [
        ('Transmit', 'Average power', self.probe_tx_dbm, 'dBm', 'dB'),
        ('', 'Sampled peak power', self.probe_tx_peak_dbm, 'dBm', 'dB'),
        ('', 'Peak / average', self.probe_tx_papr, 'dB', 'dB'),
        ('Receive', 'Signal + noise power', self.probe_rx_dbm, 'dBm', 'dB'),
        ('', 'SNR (noise over Fs)', self.probe_rx_snr, 'dB', 'dB'),
        ('', 'Eb/N0 per uncoded bit', self.probe_rx_ebno, 'dB', 'dB'),
        ('', 'EVM (decision-directed)', self.probe_evm_rms, '%', 'dB'),
        ('BER', 'Latest 10,000 bits', self.probe_ber_scale, 'errors/bit', 'ber'),
        ('BER test', 'Test length', None, 'bits', "f'{10000 * self.ber_test_blocks:,}'"),
        ('', 'Estimated time', None, 's', "f'{self.ber_test_seconds:.2f}'"),
        ('', 'Status', self.probe_ber_test_count, '', 'status'),
        ('', 'Bits compared', self.probe_ber_test_count, 'bits', 'count'),
        ('', 'Bit errors', self.probe_ber_test_errors, 'errors', 'count'),
        ('', 'BER', self.probe_ber_test_ratio, 'errors/bit', 'ber'),
    ]
    table = Qt.QTableWidget(len(rows), 4)
    table.setHorizontalHeaderLabels(["Section", "Quantity", "Value", "Unit"])
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(Qt.QAbstractItemView.NoEditTriggers)
    table.setSelectionMode(Qt.QAbstractItemView.NoSelection)
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    bold = Qt.QFont(table.font())
    bold.setBold(True)
    for row, (section, quantity, probe, unit, fmt) in enumerate(rows):
        for column, text in ((0, section), (1, quantity), (3, unit)):
            item = Qt.QTableWidgetItem(text)
            if column == 0:
                item.setFont(bold)
            table.setItem(row, column, item)
        value = Qt.QTableWidgetItem("" if probe else str(eval(fmt)))
        value.setTextAlignment(Qt.Qt.AlignRight | Qt.Qt.AlignVCenter)
        table.setItem(row, 2, value)
    header = table.horizontalHeader()
    header.setSectionResizeMode(Qt.QHeaderView.ResizeToContents)
    header.setStretchLastSection(True)
    test_bits = 10000 * self.ber_test_blocks

    def refresh_link_table():
        for row, (section, quantity, probe, unit, fmt) in enumerate(rows):
            if probe is None:
                continue
            level = probe.level()
            if fmt == "dB":
                text = f"{level:.2f}"
            elif fmt == "count":
                text = f"{level:,.0f}"
            elif fmt == "ber":
                text = f"{level:.3e}"
            else:
                text = "complete" if level >= test_bits else (
                    "counting" if level > 0 else "waiting for warm-up")
            table.item(row, 2).setText(text)

    self.link_table = table
    self.link_table_timer = Qt.QTimer()
    self.link_table_timer.timeout.connect(refresh_link_table)
    self.link_table_timer.start(250)
    self.views_grid_layout_3.addWidget(table, 1, 0, 2, 1)


def snippets_main_after_init(tb):
    snipfcn_link_table(tb)
    snipfcn_square_plot_panels(tb)
    snipfcn_equalizer_initial_taps(tb)

class single_carrier_qpsk(gr.top_block, Qt.QWidget):

    def __init__(self, reference_delay=68, symbol_rate=1e6, tx_power_dbm=0, path_loss_db=80, rx_noise_dbm=(-100), noise_enabled=1, evm_guide_percent=5, eq_taps=11, eq_step=0.01, channel_echo=0, ber_test_bits=1000000):
        gr.top_block.__init__(self, "QPSK single carrier | stock blocks", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("QPSK single carrier | stock blocks")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "single_carrier_qpsk")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Parameters
        ##################################################
        self.reference_delay = reference_delay
        self.symbol_rate = symbol_rate
        self.tx_power_dbm = tx_power_dbm
        self.path_loss_db = path_loss_db
        self.rx_noise_dbm = rx_noise_dbm
        self.noise_enabled = noise_enabled
        self.evm_guide_percent = evm_guide_percent
        self.eq_taps = eq_taps
        self.eq_step = eq_step
        self.channel_echo = channel_echo
        self.ber_test_bits = ber_test_bits

        ##################################################
        # Variables
        ##################################################
        self.const = const = digital.constellation_qpsk().base()
        self.const.set_npwr(1.0)
        self.sps = sps = 4
        self.k = k = const.bits_per_symbol()
        self.expected_rx_dbm = expected_rx_dbm = tx_power_dbm-path_loss_db
        self.warmup_bits = warmup_bits = 4096
        self.symbol_rms = symbol_rms = (sum(abs(p)**2 for p in const.points())/len(const.points()))**0.5
        self.snr_rx_db = snr_rx_db = expected_rx_dbm-rx_noise_dbm if noise_enabled else float('inf')
        self.samp_rate = samp_rate = symbol_rate*sps
        self.nfilts = nfilts = 32
        self.bit_rate = bit_rate = symbol_rate*k
        self.ber_test_blocks = ber_test_blocks = max(1, int(ber_test_bits) // 10000)
        self.alpha = alpha = 0.35
        self.tx_amplitude = tx_amplitude = 10**(tx_power_dbm/20.0)
        self.timing_bw = timing_bw = 0.0628
        self.rrc_taps = rrc_taps = firdes.root_raised_cosine(nfilts, nfilts*sps, 1.0, alpha, 11*sps*nfilts)
        self.rrc_bandwidth = rrc_bandwidth = symbol_rate*(1+alpha)
        self.path_gain = path_gain = 10**(-path_loss_db/20.0)
        self.noise_volt = noise_volt = 10**(rx_noise_dbm/20.0) if noise_enabled else 0.0
        self.eye_synthesis_taps = eye_synthesis_taps = firdes.root_raised_cosine(sps,sps,1.0,alpha,11*sps)
        self.esno_rx_db = esno_rx_db = snr_rx_db+10*math.log10(samp_rate/symbol_rate)
        self.eq_delay_symbols = eq_delay_symbols = (eq_taps-1)//2
        self.eq_algorithm = eq_algorithm = digital.adaptive_algorithm_lms( const, eq_step/(eq_taps*symbol_rms**2)).base()
        self.ebno_rx_db = ebno_rx_db = snr_rx_db+10*math.log10(samp_rate/bit_rate)
        self.ber_window = ber_window = 10000
        self.ber_test_seconds = ber_test_seconds = (warmup_bits + 10000*ber_test_blocks) / bit_rate
        self.ber_error_weight = ber_error_weight = 1.0

        ##################################################
        # Blocks
        ##################################################

        self.views = Qt.QTabWidget()
        self.views_widget_0 = Qt.QWidget()
        self.views_layout_0 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.views_widget_0)
        self.views_grid_layout_0 = Qt.QGridLayout()
        self.views_layout_0.addLayout(self.views_grid_layout_0)
        self.views.addTab(self.views_widget_0, 'Constellations')
        self.views_widget_1 = Qt.QWidget()
        self.views_layout_1 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.views_widget_1)
        self.views_grid_layout_1 = Qt.QGridLayout()
        self.views_layout_1.addLayout(self.views_grid_layout_1)
        self.views.addTab(self.views_widget_1, 'Waveforms')
        self.views_widget_2 = Qt.QWidget()
        self.views_layout_2 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.views_widget_2)
        self.views_grid_layout_2 = Qt.QGridLayout()
        self.views_layout_2.addLayout(self.views_grid_layout_2)
        self.views.addTab(self.views_widget_2, 'I eyes')
        self.views_widget_3 = Qt.QWidget()
        self.views_layout_3 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.views_widget_3)
        self.views_grid_layout_3 = Qt.QGridLayout()
        self.views_layout_3.addLayout(self.views_grid_layout_3)
        self.views.addTab(self.views_widget_3, 'Link budget')
        self.views_widget_4 = Qt.QWidget()
        self.views_layout_4 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.views_widget_4)
        self.views_grid_layout_4 = Qt.QGridLayout()
        self.views_layout_4.addLayout(self.views_grid_layout_4)
        self.views.addTab(self.views_widget_4, 'Q eyes')
        self.views_widget_5 = Qt.QWidget()
        self.views_layout_5 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.views_widget_5)
        self.views_grid_layout_5 = Qt.QGridLayout()
        self.views_layout_5.addLayout(self.views_grid_layout_5)
        self.views.addTab(self.views_widget_5, 'BER / EVM / taps')
        self.top_layout.addWidget(self.views)
        self.constellation = qtgui.const_sink_c(
            1024, #size
            'After adaptive LMS equalization | symbols and guides', #name
            3, #number of inputs
            None # parent
        )
        self.constellation.set_update_time(0.10)
        self.constellation.set_y_axis((-2), 2)
        self.constellation.set_x_axis((-2), 2)
        self.constellation.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.constellation.enable_autoscale(False)
        self.constellation.enable_grid(True)
        self.constellation.enable_axis_labels(True)


        labels = ['RX symbols', 'Ideal reference', 'EVM radius guide (% RMS)', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "black", "dark green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 8, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [0.3, 1.0, 0.5, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(3):
            if len(labels[i]) == 0:
                self.constellation.set_line_label(i, "Data {0}".format(i))
            else:
                self.constellation.set_line_label(i, labels[i])
            self.constellation.set_line_width(i, widths[i])
            self.constellation.set_line_color(i, colors[i])
            self.constellation.set_line_style(i, styles[i])
            self.constellation.set_line_marker(i, markers[i])
            self.constellation.set_line_alpha(i, alphas[i])

        self._constellation_win = sip.wrapinstance(self.constellation.qwidget(), Qt.QWidget)
        self.views_grid_layout_0.addWidget(self._constellation_win, 2, 0, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_0.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_0.setColumnStretch(c, 1)
        self.xor = blocks.xor_bb()
        self.waveform = qtgui.time_sink_c(
            512, #size
            samp_rate, #samp_rate
            'TX and RX waveform | I/Q', #name
            2, #number of inputs
            None # parent
        )
        self.waveform.set_update_time(0.10)
        self.waveform.set_y_axis(-1, 1)

        self.waveform.set_y_label('Amplitude', "")

        self.waveform.enable_tags(True)
        self.waveform.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.waveform.enable_autoscale(False)
        self.waveform.enable_grid(False)
        self.waveform.enable_axis_labels(True)
        self.waveform.enable_control_panel(False)
        self.waveform.enable_stem_plot(False)


        labels = ['RX I', 'RX Q', 'TX I', 'TX Q', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(4):
            if len(labels[i]) == 0:
                if (i % 2 == 0):
                    self.waveform.set_line_label(i, "Re{{Data {0}}}".format(i/2))
                else:
                    self.waveform.set_line_label(i, "Im{{Data {0}}}".format(i/2))
            else:
                self.waveform.set_line_label(i, labels[i])
            self.waveform.set_line_width(i, widths[i])
            self.waveform.set_line_color(i, colors[i])
            self.waveform.set_line_style(i, styles[i])
            self.waveform.set_line_marker(i, markers[i])
            self.waveform.set_line_alpha(i, alphas[i])

        self._waveform_win = sip.wrapinstance(self.waveform.qwidget(), Qt.QWidget)
        self.views_grid_layout_1.addWidget(self._waveform_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_1.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_1.setColumnStretch(c, 1)
        self.unused_timing_states = blocks.null_sink(gr.sizeof_float*1)
        self.unpack_tx = blocks.unpack_k_bits_bb(8)
        self.unpack_rx = blocks.unpack_k_bits_bb(k)
        self.tx_waveform = qtgui.time_sink_c(
            512, #size
            samp_rate, #samp_rate
            'Clean TX waveform | I/Q', #name
            1, #number of inputs
            None # parent
        )
        self.tx_waveform.set_update_time(0.10)
        self.tx_waveform.set_y_axis(-1, 1)

        self.tx_waveform.set_y_label('Amplitude', "")

        self.tx_waveform.enable_tags(True)
        self.tx_waveform.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.tx_waveform.enable_autoscale(False)
        self.tx_waveform.enable_grid(False)
        self.tx_waveform.enable_axis_labels(True)
        self.tx_waveform.enable_control_panel(False)
        self.tx_waveform.enable_stem_plot(False)


        labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(2):
            if len(labels[i]) == 0:
                if (i % 2 == 0):
                    self.tx_waveform.set_line_label(i, "Re{{Data {0}}}".format(i/2))
                else:
                    self.tx_waveform.set_line_label(i, "Im{{Data {0}}}".format(i/2))
            else:
                self.tx_waveform.set_line_label(i, labels[i])
            self.tx_waveform.set_line_width(i, widths[i])
            self.tx_waveform.set_line_color(i, colors[i])
            self.tx_waveform.set_line_style(i, styles[i])
            self.tx_waveform.set_line_marker(i, markers[i])
            self.tx_waveform.set_line_alpha(i, alphas[i])

        self._tx_waveform_win = sip.wrapinstance(self.tx_waveform.qwidget(), Qt.QWidget)
        self.views_grid_layout_1.addWidget(self._tx_waveform_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_1.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_1.setColumnStretch(c, 1)
        self.tx_symbols = digital.chunks_to_symbols_bc(const.points(), 1)
        self.tx_symbol_diff = digital.diff_encoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.tx_symbol_chunks = blocks.packed_to_unpacked_bb(k, gr.GR_MSB_FIRST)
        self.tx_power_sum = blocks.integrate_ff(4096, 1)
        self.tx_power_mean = blocks.multiply_const_ff((1.0/4096))
        self.tx_power = blocks.multiply_const_cc(tx_amplitude/symbol_rms)
        self.tx_peak_vectors = blocks.stream_to_vector(gr.sizeof_float*1, 4096)
        self.tx_peak_mw = blocks.max_ff(4096, 1)
        self.tx_peak_dbm = blocks.nlog10_ff(10, 1, 0)
        self.tx_papr = blocks.sub_ff(1)
        self.tx_milliwatts = blocks.complex_to_mag_squared(1)
        self.tx_eye_q_eye = qtgui.eye_sink_f(
            1024, #size
            samp_rate, #samp_rate
            1, #number of inputs
            None
        )
        self.tx_eye_q_eye.set_update_time(0.10)
        self.tx_eye_q_eye.set_samp_per_symbol(sps)
        self.tx_eye_q_eye.set_y_axis(-1, 1)

        self.tx_eye_q_eye.set_y_label('TX_EYE Q | TX shaped', "")

        self.tx_eye_q_eye.enable_tags(True)
        self.tx_eye_q_eye.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.tx_eye_q_eye.enable_autoscale(True)
        self.tx_eye_q_eye.enable_grid(True)
        self.tx_eye_q_eye.enable_axis_labels(True)
        self.tx_eye_q_eye.enable_control_panel(False)


        labels = ['TX Q | shaped waveform', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'blue', 'blue', 'blue', 'blue',
            'blue', 'blue', 'blue', 'blue', 'blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.tx_eye_q_eye.set_line_label(i, "Eye[Data {0}]".format(i))
            else:
                self.tx_eye_q_eye.set_line_label(i, labels[i])
            self.tx_eye_q_eye.set_line_width(i, widths[i])
            self.tx_eye_q_eye.set_line_color(i, colors[i])
            self.tx_eye_q_eye.set_line_style(i, styles[i])
            self.tx_eye_q_eye.set_line_marker(i, markers[i])
            self.tx_eye_q_eye.set_line_alpha(i, alphas[i])

        self._tx_eye_q_eye_win = sip.wrapinstance(self.tx_eye_q_eye.qwidget(), Qt.QWidget)
        self.views_grid_layout_4.addWidget(self._tx_eye_q_eye_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_4.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_4.setColumnStretch(c, 1)
        self.tx_eye_q = blocks.complex_to_imag(1)
        self.tx_eye_i_eye = qtgui.eye_sink_f(
            1024, #size
            samp_rate, #samp_rate
            1, #number of inputs
            None
        )
        self.tx_eye_i_eye.set_update_time(0.10)
        self.tx_eye_i_eye.set_samp_per_symbol(sps)
        self.tx_eye_i_eye.set_y_axis(-1, 1)

        self.tx_eye_i_eye.set_y_label('TX_EYE I | TX shaped', "")

        self.tx_eye_i_eye.enable_tags(True)
        self.tx_eye_i_eye.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.tx_eye_i_eye.enable_autoscale(True)
        self.tx_eye_i_eye.enable_grid(True)
        self.tx_eye_i_eye.enable_axis_labels(True)
        self.tx_eye_i_eye.enable_control_panel(False)


        labels = ['TX I | shaped waveform', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'blue', 'blue', 'blue', 'blue',
            'blue', 'blue', 'blue', 'blue', 'blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.tx_eye_i_eye.set_line_label(i, "Eye[Data {0}]".format(i))
            else:
                self.tx_eye_i_eye.set_line_label(i, labels[i])
            self.tx_eye_i_eye.set_line_width(i, widths[i])
            self.tx_eye_i_eye.set_line_color(i, colors[i])
            self.tx_eye_i_eye.set_line_style(i, styles[i])
            self.tx_eye_i_eye.set_line_marker(i, markers[i])
            self.tx_eye_i_eye.set_line_alpha(i, alphas[i])

        self._tx_eye_i_eye_win = sip.wrapinstance(self.tx_eye_i_eye.qwidget(), Qt.QWidget)
        self.views_grid_layout_2.addWidget(self._tx_eye_i_eye_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_2.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_2.setColumnStretch(c, 1)
        self.tx_eye_i = blocks.complex_to_real(1)
        self.tx_dbm = blocks.nlog10_ff(10, 1, 0)
        self.tx_constellation = qtgui.const_sink_c(
            1024, #size
            'TX before RRC: blue symbols / black ideal / green guide', #name
            3, #number of inputs
            None # parent
        )
        self.tx_constellation.set_update_time(0.10)
        self.tx_constellation.set_y_axis((-2), 2)
        self.tx_constellation.set_x_axis((-2), 2)
        self.tx_constellation.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.tx_constellation.enable_autoscale(False)
        self.tx_constellation.enable_grid(True)
        self.tx_constellation.enable_axis_labels(True)


        labels = ['TX encoded symbols', 'Ideal reference', 'EVM radius guide (% RMS)', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "black", "dark green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 8, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [0.3, 1.0, 0.5, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(3):
            if len(labels[i]) == 0:
                self.tx_constellation.set_line_label(i, "Data {0}".format(i))
            else:
                self.tx_constellation.set_line_label(i, labels[i])
            self.tx_constellation.set_line_width(i, widths[i])
            self.tx_constellation.set_line_color(i, colors[i])
            self.tx_constellation.set_line_style(i, styles[i])
            self.tx_constellation.set_line_marker(i, markers[i])
            self.tx_constellation.set_line_alpha(i, alphas[i])

        self._tx_constellation_win = sip.wrapinstance(self.tx_constellation.qwidget(), Qt.QWidget)
        self.views_grid_layout_0.addWidget(self._tx_constellation_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_0.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_0.setColumnStretch(c, 1)
        self.timing_error = qtgui.time_sink_f(
            512, #size
            symbol_rate, #samp_rate
            'Clock sync timing error', #name
            1, #number of inputs
            None # parent
        )
        self.timing_error.set_update_time(0.10)
        self.timing_error.set_y_axis(-1, 1)

        self.timing_error.set_y_label('Amplitude', "")

        self.timing_error.enable_tags(True)
        self.timing_error.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.timing_error.enable_autoscale(True)
        self.timing_error.enable_grid(False)
        self.timing_error.enable_axis_labels(True)
        self.timing_error.enable_control_panel(False)
        self.timing_error.enable_stem_plot(False)


        labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.timing_error.set_line_label(i, "Data {0}".format(i))
            else:
                self.timing_error.set_line_label(i, labels[i])
            self.timing_error.set_line_width(i, widths[i])
            self.timing_error.set_line_color(i, colors[i])
            self.timing_error.set_line_style(i, styles[i])
            self.timing_error.set_line_marker(i, markers[i])
            self.timing_error.set_line_alpha(i, alphas[i])

        self._timing_error_win = sip.wrapinstance(self.timing_error.qwidget(), Qt.QWidget)
        self.views_grid_layout_1.addWidget(self._timing_error_win, 2, 1, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_1.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_1.setColumnStretch(c, 1)
        self.throttle = blocks.throttle( gr.sizeof_gr_complex*1, samp_rate, True, 0 if "auto" == "auto" else max( int(float(0.1) * samp_rate) if "auto" == "time" else int(0.1), 1) )
        self.spectrum_budget = qtgui.freq_sink_c(
            1024, #size
            window.WIN_HANN, #wintype
            0, #fc
            samp_rate, #bw
            'RX spectrum | relative level', #name
            1,
            None # parent
        )
        self.spectrum_budget.set_update_time(0.10)
        self.spectrum_budget.set_y_axis((-140), 10)
        self.spectrum_budget.set_y_label('Relative Gain', 'dB')
        self.spectrum_budget.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.spectrum_budget.enable_autoscale(False)
        self.spectrum_budget.enable_grid(False)
        self.spectrum_budget.set_fft_average(1.0)
        self.spectrum_budget.enable_axis_labels(True)
        self.spectrum_budget.enable_control_panel(False)
        self.spectrum_budget.set_fft_window_normalized(False)



        labels = ['RX', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.spectrum_budget.set_line_label(i, "Data {0}".format(i))
            else:
                self.spectrum_budget.set_line_label(i, labels[i])
            self.spectrum_budget.set_line_width(i, widths[i])
            self.spectrum_budget.set_line_color(i, colors[i])
            self.spectrum_budget.set_line_alpha(i, alphas[i])

        self._spectrum_budget_win = sip.wrapinstance(self.spectrum_budget.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._spectrum_budget_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_3.setColumnStretch(c, 1)
        self.spectrum = qtgui.freq_sink_c(
            1024, #size
            window.WIN_HANN, #wintype
            0, #fc
            samp_rate, #bw
            'TX and RX baseband spectrum | relative dB', #name
            2,
            None # parent
        )
        self.spectrum.set_update_time(0.10)
        self.spectrum.set_y_axis((-140), 10)
        self.spectrum.set_y_label('Relative Gain', 'dB')
        self.spectrum.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.spectrum.enable_autoscale(False)
        self.spectrum.enable_grid(False)
        self.spectrum.set_fft_average(1.0)
        self.spectrum.enable_axis_labels(True)
        self.spectrum.enable_control_panel(False)
        self.spectrum.set_fft_window_normalized(False)



        labels = ['RX', 'TX', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(2):
            if len(labels[i]) == 0:
                self.spectrum.set_line_label(i, "Data {0}".format(i))
            else:
                self.spectrum.set_line_label(i, labels[i])
            self.spectrum.set_line_width(i, widths[i])
            self.spectrum.set_line_color(i, colors[i])
            self.spectrum.set_line_alpha(i, alphas[i])

        self._spectrum_win = sip.wrapinstance(self.spectrum.qwidget(), Qt.QWidget)
        self.views_grid_layout_1.addWidget(self._spectrum_win, 2, 0, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_1.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_1.setColumnStretch(c, 1)
        self.skip_tx = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.skip_rx = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.rx_snr = blocks.add_const_ff((-path_loss_db-rx_noise_dbm if noise_enabled else float('inf')))
        self.rx_scale = blocks.multiply_const_cc(symbol_rms)
        self.rx_power_sum = blocks.integrate_ff(4096, 1)
        self.rx_power_mean = blocks.multiply_const_ff((1.0/4096))
        self.rx_milliwatts = blocks.complex_to_mag_squared(1)
        self.rx_level = blocks.multiply_const_cc(1.0/(tx_amplitude*path_gain))
        self.rx_ebno = blocks.add_const_ff((-path_loss_db-rx_noise_dbm+10*math.log10(samp_rate/bit_rate) if noise_enabled else float('inf')))
        self.rx_dbm = blocks.nlog10_ff(10, 1, 0)
        self.rf_constellation = qtgui.const_sink_c(
            1024, #size
            'Received symbols (after equalizer)', #name
            1, #number of inputs
            None # parent
        )
        self.rf_constellation.set_update_time(0.10)
        self.rf_constellation.set_y_axis((-2), 2)
        self.rf_constellation.set_x_axis((-2), 2)
        self.rf_constellation.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.rf_constellation.enable_autoscale(False)
        self.rf_constellation.enable_grid(True)
        self.rf_constellation.enable_axis_labels(True)

        self.rf_constellation.disable_legend()

        labels = ['RX', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [0.4, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.rf_constellation.set_line_label(i, "Data {0}".format(i))
            else:
                self.rf_constellation.set_line_label(i, labels[i])
            self.rf_constellation.set_line_width(i, widths[i])
            self.rf_constellation.set_line_color(i, colors[i])
            self.rf_constellation.set_line_style(i, styles[i])
            self.rf_constellation.set_line_marker(i, markers[i])
            self.rf_constellation.set_line_alpha(i, alphas[i])

        self._rf_constellation_win = sip.wrapinstance(self.rf_constellation.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._rf_constellation_win, 2, 1, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_3.setColumnStretch(c, 1)
        self.random_bytes = blocks.vector_source_b(list(map(int, numpy.random.randint(0, 256, 32768))), True)
        self.probe_tx_peak_dbm = blocks.probe_signal_f()
        self.probe_tx_papr = blocks.probe_signal_f()
        self.probe_tx_dbm = blocks.probe_signal_f()
        self.probe_rx_snr = blocks.probe_signal_f()
        self.probe_rx_ebno = blocks.probe_signal_f()
        self.probe_rx_dbm = blocks.probe_signal_f()
        self.probe_evm_rms = blocks.probe_signal_f()
        self.probe_ber_test_ratio = blocks.probe_signal_f()
        self.probe_ber_test_errors = blocks.probe_signal_f()
        self.probe_ber_test_count = blocks.probe_signal_f()
        self.probe_ber_scale = blocks.probe_signal_f()
        self.modulator = digital.generic_mod(
            constellation=const,
            differential=True,
            samples_per_symbol=sps,
            pre_diff_code=True,
            excess_bw=alpha,
            verbose=False,
            log=False,
            truncate=False)
        self.middle_q_eye = qtgui.eye_sink_f(
            1024, #size
            samp_rate, #samp_rate
            1, #number of inputs
            None
        )
        self.middle_q_eye.set_update_time(0.10)
        self.middle_q_eye.set_samp_per_symbol(sps)
        self.middle_q_eye.set_y_axis(-1, 1)

        self.middle_q_eye.set_y_label('MIDDLE Q | reconstructed', "")

        self.middle_q_eye.enable_tags(True)
        self.middle_q_eye.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.middle_q_eye.enable_autoscale(True)
        self.middle_q_eye.enable_grid(True)
        self.middle_q_eye.enable_axis_labels(True)
        self.middle_q_eye.enable_control_panel(False)


        labels = ['Middle Q | before EQ, reconstructed', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'blue', 'blue', 'blue', 'blue',
            'blue', 'blue', 'blue', 'blue', 'blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.middle_q_eye.set_line_label(i, "Eye[Data {0}]".format(i))
            else:
                self.middle_q_eye.set_line_label(i, labels[i])
            self.middle_q_eye.set_line_width(i, widths[i])
            self.middle_q_eye.set_line_color(i, colors[i])
            self.middle_q_eye.set_line_style(i, styles[i])
            self.middle_q_eye.set_line_marker(i, markers[i])
            self.middle_q_eye.set_line_alpha(i, alphas[i])

        self._middle_q_eye_win = sip.wrapinstance(self.middle_q_eye.qwidget(), Qt.QWidget)
        self.views_grid_layout_4.addWidget(self._middle_q_eye_win, 2, 0, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_4.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_4.setColumnStretch(c, 1)
        self.middle_q = blocks.complex_to_imag(1)
        self.middle_i_eye = qtgui.eye_sink_f(
            1024, #size
            samp_rate, #samp_rate
            1, #number of inputs
            None
        )
        self.middle_i_eye.set_update_time(0.10)
        self.middle_i_eye.set_samp_per_symbol(sps)
        self.middle_i_eye.set_y_axis(-1, 1)

        self.middle_i_eye.set_y_label('MIDDLE I | reconstructed', "")

        self.middle_i_eye.enable_tags(True)
        self.middle_i_eye.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.middle_i_eye.enable_autoscale(True)
        self.middle_i_eye.enable_grid(True)
        self.middle_i_eye.enable_axis_labels(True)
        self.middle_i_eye.enable_control_panel(False)


        labels = ['Middle I | before EQ, reconstructed', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'blue', 'blue', 'blue', 'blue',
            'blue', 'blue', 'blue', 'blue', 'blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.middle_i_eye.set_line_label(i, "Eye[Data {0}]".format(i))
            else:
                self.middle_i_eye.set_line_label(i, labels[i])
            self.middle_i_eye.set_line_width(i, widths[i])
            self.middle_i_eye.set_line_color(i, colors[i])
            self.middle_i_eye.set_line_style(i, styles[i])
            self.middle_i_eye.set_line_marker(i, markers[i])
            self.middle_i_eye.set_line_alpha(i, alphas[i])

        self._middle_i_eye_win = sip.wrapinstance(self.middle_i_eye.qwidget(), Qt.QWidget)
        self.views_grid_layout_2.addWidget(self._middle_i_eye_win, 2, 0, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_2.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_2.setColumnStretch(c, 1)
        self.middle_i = blocks.complex_to_real(1)
        self.middle_eye_reconstruction = filter.interp_fir_filter_ccf(sps, eye_synthesis_taps)
        self.middle_eye_reconstruction.declare_sample_delay(0)
        self.integrate = blocks.integrate_ff(ber_window, 1)
        self.ideal_symbols = blocks.vector_source_c(const.points(), True, 1, [])
        self.eye_quadrature = qtgui.eye_sink_f(
            1024, #size
            samp_rate, #samp_rate
            1, #number of inputs
            None
        )
        self.eye_quadrature.set_update_time(0.10)
        self.eye_quadrature.set_samp_per_symbol(sps)
        self.eye_quadrature.set_y_axis(-1, 1)

        self.eye_quadrature.set_y_label('RX quadrature amplitude', "")

        self.eye_quadrature.enable_tags(True)
        self.eye_quadrature.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.eye_quadrature.enable_autoscale(True)
        self.eye_quadrature.enable_grid(True)
        self.eye_quadrature.enable_axis_labels(True)
        self.eye_quadrature.enable_control_panel(False)


        labels = ['RX Q | raw channel output', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'blue', 'blue', 'blue', 'blue',
            'blue', 'blue', 'blue', 'blue', 'blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.eye_quadrature.set_line_label(i, "Eye[Data {0}]".format(i))
            else:
                self.eye_quadrature.set_line_label(i, labels[i])
            self.eye_quadrature.set_line_width(i, widths[i])
            self.eye_quadrature.set_line_color(i, colors[i])
            self.eye_quadrature.set_line_style(i, styles[i])
            self.eye_quadrature.set_line_marker(i, markers[i])
            self.eye_quadrature.set_line_alpha(i, alphas[i])

        self._eye_quadrature_win = sip.wrapinstance(self.eye_quadrature.qwidget(), Qt.QWidget)
        self.views_grid_layout_4.addWidget(self._eye_quadrature_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_4.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_4.setColumnStretch(c, 1)
        self.eye_q = blocks.complex_to_imag(1)
        self.eye_i = blocks.complex_to_real(1)
        self.eye = qtgui.eye_sink_f(
            1024, #size
            samp_rate, #samp_rate
            1, #number of inputs
            None
        )
        self.eye.set_update_time(0.10)
        self.eye.set_samp_per_symbol(sps)
        self.eye.set_y_axis(-1, 1)

        self.eye.set_y_label('RX in-phase amplitude', "")

        self.eye.enable_tags(True)
        self.eye.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.eye.enable_autoscale(True)
        self.eye.enable_grid(True)
        self.eye.enable_axis_labels(True)
        self.eye.enable_control_panel(False)


        labels = ['RX I | raw channel output', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'blue', 'blue', 'blue', 'blue',
            'blue', 'blue', 'blue', 'blue', 'blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.eye.set_line_label(i, "Eye[Data {0}]".format(i))
            else:
                self.eye.set_line_label(i, labels[i])
            self.eye.set_line_width(i, widths[i])
            self.eye.set_line_color(i, colors[i])
            self.eye.set_line_style(i, styles[i])
            self.eye.set_line_marker(i, markers[i])
            self.eye.set_line_alpha(i, alphas[i])

        self._eye_win = sip.wrapinstance(self.eye.qwidget(), Qt.QWidget)
        self.views_grid_layout_2.addWidget(self._eye_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_2.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_2.setColumnStretch(c, 1)
        self.evm_rms = blocks.rms_ff(0.001)
        self.evm_history = qtgui.time_sink_f(
            128, #size
            symbol_rate, #samp_rate
            'Smoothed decision-directed RMS EVM (%)', #name
            1, #number of inputs
            None # parent
        )
        self.evm_history.set_update_time(0.10)
        self.evm_history.set_y_axis(-1, 1)

        self.evm_history.set_y_label('EVM', '%')

        self.evm_history.enable_tags(True)
        self.evm_history.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.evm_history.enable_autoscale(True)
        self.evm_history.enable_grid(False)
        self.evm_history.enable_axis_labels(True)
        self.evm_history.enable_control_panel(False)
        self.evm_history.enable_stem_plot(False)


        labels = ['Decision-directed EVM', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.evm_history.set_line_label(i, "Data {0}".format(i))
            else:
                self.evm_history.set_line_label(i, labels[i])
            self.evm_history.set_line_width(i, widths[i])
            self.evm_history.set_line_color(i, colors[i])
            self.evm_history.set_line_style(i, styles[i])
            self.evm_history.set_line_marker(i, markers[i])
            self.evm_history.set_line_alpha(i, alphas[i])

        self._evm_history_win = sip.wrapinstance(self.evm_history.qwidget(), Qt.QWidget)
        self.views_grid_layout_5.addWidget(self._evm_history_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_5.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_5.setColumnStretch(c, 1)
        self.evm_display = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.evm_display.set_update_time(0.10)
        self.evm_display.set_title('Decision-directed RMS EVM')

        labels = ['Decision-directed EVM', '', '', '', '',
            '', '', '', '', '']
        units = ['%', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.evm_display.set_min(i, 0)
            self.evm_display.set_max(i, 100)
            self.evm_display.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.evm_display.set_label(i, "Data {0}".format(i))
            else:
                self.evm_display.set_label(i, labels[i])
            self.evm_display.set_unit(i, units[i])
            self.evm_display.set_factor(i, factor[i])

        self.evm_display.enable_autoscale(False)
        self._evm_display_win = sip.wrapinstance(self.evm_display.qwidget(), Qt.QWidget)
        self.views_grid_layout_0.addWidget(self._evm_display_win, 0, 1, 1, 1)
        for r in range(0, 1):
            self.views_grid_layout_0.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_0.setColumnStretch(c, 1)
        self.evm_circles = blocks.vector_source_c([p+symbol_rms*evm_guide_percent/100*complex(math.cos(t),math.sin(t)) for p in const.points() for t in numpy.linspace(0,2*math.pi,64,endpoint=False)], True, 1, [])
        self.evm = digital.meas_evm_cc(const,digital.evm_measurement_t.EVM_PERCENT)
        self.errors_float = blocks.uchar_to_float()
        self.equalizer = digital.linear_equalizer(eq_taps, 1, eq_algorithm, True, [], '')
        self.eq_tap_plot = qtgui.vector_sink_f(
            eq_taps,
            0,
            1,
            'Tap index',
            'Magnitude',
            'Adaptive LMS tap magnitudes | updated during convergence',
            1, # Number of inputs
            None # parent
        )
        self.eq_tap_plot.set_update_time(0.10)
        self.eq_tap_plot.set_y_axis((-140), 10)
        self.eq_tap_plot.enable_autoscale(True)
        self.eq_tap_plot.enable_grid(True)
        self.eq_tap_plot.set_x_axis_units("")
        self.eq_tap_plot.set_y_axis_units("")
        self.eq_tap_plot.set_ref_level(0)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.eq_tap_plot.set_line_label(i, "Data {0}".format(i))
            else:
                self.eq_tap_plot.set_line_label(i, labels[i])
            self.eq_tap_plot.set_line_width(i, widths[i])
            self.eq_tap_plot.set_line_color(i, colors[i])
            self.eq_tap_plot.set_line_alpha(i, alphas[i])

        self._eq_tap_plot_win = sip.wrapinstance(self.eq_tap_plot.qwidget(), Qt.QWidget)
        self.views_grid_layout_5.addWidget(self._eq_tap_plot_win, 2, 1, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_5.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_5.setColumnStretch(c, 1)
        self.eq_tap_magnitudes = blocks.complex_to_mag(eq_taps)
        self.eq_tap_decimator = blocks.keep_one_in_n(gr.sizeof_gr_complex*eq_taps, 1000)
        self.eq_evm_history = qtgui.time_sink_f(
            128, #size
            symbol_rate, #samp_rate
            'Equalized decision-directed RMS EVM (%)', #name
            1, #number of inputs
            None # parent
        )
        self.eq_evm_history.set_update_time(0.10)
        self.eq_evm_history.set_y_axis(-1, 1)

        self.eq_evm_history.set_y_label('EVM', '%')

        self.eq_evm_history.enable_tags(True)
        self.eq_evm_history.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.eq_evm_history.enable_autoscale(True)
        self.eq_evm_history.enable_grid(False)
        self.eq_evm_history.enable_axis_labels(True)
        self.eq_evm_history.enable_control_panel(False)
        self.eq_evm_history.enable_stem_plot(False)


        labels = ['Decision-directed EVM', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.eq_evm_history.set_line_label(i, "Data {0}".format(i))
            else:
                self.eq_evm_history.set_line_label(i, labels[i])
            self.eq_evm_history.set_line_width(i, widths[i])
            self.eq_evm_history.set_line_color(i, colors[i])
            self.eq_evm_history.set_line_style(i, styles[i])
            self.eq_evm_history.set_line_marker(i, markers[i])
            self.eq_evm_history.set_line_alpha(i, alphas[i])

        self._eq_evm_history_win = sip.wrapinstance(self.eq_evm_history.qwidget(), Qt.QWidget)
        self.views_grid_layout_0.addWidget(self._eq_evm_history_win, 2, 1, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_0.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_0.setColumnStretch(c, 1)
        self.eq_error_trace = qtgui.time_sink_f(
            128, #size
            symbol_rate, #samp_rate
            'Per-symbol equalized EVM (%)', #name
            1, #number of inputs
            None # parent
        )
        self.eq_error_trace.set_update_time(0.10)
        self.eq_error_trace.set_y_axis(-1, 1)

        self.eq_error_trace.set_y_label('EVM', '%')

        self.eq_error_trace.enable_tags(True)
        self.eq_error_trace.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.eq_error_trace.enable_autoscale(True)
        self.eq_error_trace.enable_grid(False)
        self.eq_error_trace.enable_axis_labels(True)
        self.eq_error_trace.enable_control_panel(False)
        self.eq_error_trace.enable_stem_plot(False)


        labels = ['Decision-directed EVM', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.eq_error_trace.set_line_label(i, "Data {0}".format(i))
            else:
                self.eq_error_trace.set_line_label(i, labels[i])
            self.eq_error_trace.set_line_width(i, widths[i])
            self.eq_error_trace.set_line_color(i, colors[i])
            self.eq_error_trace.set_line_style(i, styles[i])
            self.eq_error_trace.set_line_marker(i, markers[i])
            self.eq_error_trace.set_line_alpha(i, alphas[i])

        self._eq_error_trace_win = sip.wrapinstance(self.eq_error_trace.qwidget(), Qt.QWidget)
        self.views_grid_layout_5.addWidget(self._eq_error_trace_win, 2, 0, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_5.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_5.setColumnStretch(c, 1)
        self.diff_decoder = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.delay = blocks.delay(gr.sizeof_char*1, reference_delay)
        self.decoder = digital.constellation_decoder_cb(const)
        self.clock_sync = digital.pfb_clock_sync_ccf(sps, timing_bw, rrc_taps, nfilts, 16, 1.5, 1)
        self.channel = channels.channel_model(
            noise_voltage=noise_volt,
            frequency_offset=0,
            epsilon=1,
            taps=[path_gain/(1+channel_echo**2)**0.5]+[0j]*(sps-1)+[path_gain*channel_echo/(1+channel_echo**2)**0.5],
            noise_seed=42,
            block_tags=False)
        self.ber_test_zero = blocks.multiply_const_ff(0)
        self.ber_test_window_sum = filter.iir_filter_ffd([1.0], [0.0, 1.0], True)
        self.ber_test_unit = blocks.add_const_ff(1)
        self.ber_test_sum_10k = blocks.integrate_ff(10000, 1)
        self.ber_test_ratio = blocks.divide_ff(1)
        self.ber_test_not_done = blocks.multiply_const_ff((-1))
        self.ber_test_index = filter.iir_filter_ffd([1.0], [0.0, 1.0], True)
        self.ber_test_gated_errors = blocks.multiply_vff(1)
        self.ber_test_gate = blocks.add_const_ff(1)
        self.ber_test_errors = blocks.multiply_const_ff(ber_error_weight)
        self.ber_test_error_sum = filter.iir_filter_ffd([1.0], [0.0, 1.0], True)
        self.ber_test_done = blocks.threshold_ff((ber_test_blocks + 0.5), (ber_test_blocks + 0.5), 0)
        self.ber_test_count = blocks.multiply_const_ff(10000)
        self.ber_scale = blocks.multiply_const_ff((1.0/ber_window))
        self.ber_history = qtgui.time_sink_f(
            128, #size
            bit_rate/ber_window, #samp_rate
            'BER per compared-bit window', #name
            1, #number of inputs
            None # parent
        )
        self.ber_history.set_update_time(0.10)
        self.ber_history.set_y_axis(0, 1)

        self.ber_history.set_y_label('Bit error ratio', '')

        self.ber_history.enable_tags(True)
        self.ber_history.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.ber_history.enable_autoscale(True)
        self.ber_history.enable_grid(False)
        self.ber_history.enable_axis_labels(True)
        self.ber_history.enable_control_panel(False)
        self.ber_history.enable_stem_plot(False)


        labels = ['BER', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.ber_history.set_line_label(i, "Data {0}".format(i))
            else:
                self.ber_history.set_line_label(i, labels[i])
            self.ber_history.set_line_width(i, widths[i])
            self.ber_history.set_line_color(i, colors[i])
            self.ber_history.set_line_style(i, styles[i])
            self.ber_history.set_line_marker(i, markers[i])
            self.ber_history.set_line_alpha(i, alphas[i])

        self._ber_history_win = sip.wrapinstance(self.ber_history.qwidget(), Qt.QWidget)
        self.views_grid_layout_5.addWidget(self._ber_history_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_5.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_5.setColumnStretch(c, 1)
        self.ber_display = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.ber_display.set_update_time(0.10)
        self.ber_display.set_title('BER | latest 10000 compared bits')

        labels = ['Bit error ratio', '', '', '', '',
            '', '', '', '', '']
        units = ['errors/bit', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.ber_display.set_min(i, 0)
            self.ber_display.set_max(i, 1)
            self.ber_display.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.ber_display.set_label(i, "Data {0}".format(i))
            else:
                self.ber_display.set_label(i, labels[i])
            self.ber_display.set_unit(i, units[i])
            self.ber_display.set_factor(i, factor[i])

        self.ber_display.enable_autoscale(False)
        self._ber_display_win = sip.wrapinstance(self.ber_display.qwidget(), Qt.QWidget)
        self.views_grid_layout_0.addWidget(self._ber_display_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.views_grid_layout_0.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_0.setColumnStretch(c, 1)
        self.before_eq_constellation = qtgui.const_sink_c(
            1024, #size
            'Middle: timed symbols before adaptive EQ', #name
            1, #number of inputs
            None # parent
        )
        self.before_eq_constellation.set_update_time(0.10)
        self.before_eq_constellation.set_y_axis((-2), 2)
        self.before_eq_constellation.set_x_axis((-2), 2)
        self.before_eq_constellation.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.before_eq_constellation.enable_autoscale(False)
        self.before_eq_constellation.enable_grid(True)
        self.before_eq_constellation.enable_axis_labels(True)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.before_eq_constellation.set_line_label(i, "Data {0}".format(i))
            else:
                self.before_eq_constellation.set_line_label(i, labels[i])
            self.before_eq_constellation.set_line_width(i, widths[i])
            self.before_eq_constellation.set_line_color(i, colors[i])
            self.before_eq_constellation.set_line_style(i, styles[i])
            self.before_eq_constellation.set_line_marker(i, markers[i])
            self.before_eq_constellation.set_line_alpha(i, alphas[i])

        self._before_eq_constellation_win = sip.wrapinstance(self.before_eq_constellation.qwidget(), Qt.QWidget)
        self.views_grid_layout_0.addWidget(self._before_eq_constellation_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_0.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_0.setColumnStretch(c, 1)
        self.after_q_eye = qtgui.eye_sink_f(
            1024, #size
            samp_rate, #samp_rate
            1, #number of inputs
            None
        )
        self.after_q_eye.set_update_time(0.10)
        self.after_q_eye.set_samp_per_symbol(sps)
        self.after_q_eye.set_y_axis(-1, 1)

        self.after_q_eye.set_y_label('AFTER Q | reconstructed', "")

        self.after_q_eye.enable_tags(True)
        self.after_q_eye.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.after_q_eye.enable_autoscale(True)
        self.after_q_eye.enable_grid(True)
        self.after_q_eye.enable_axis_labels(True)
        self.after_q_eye.enable_control_panel(False)


        labels = ['After EQ Q | reconstructed', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'blue', 'blue', 'blue', 'blue',
            'blue', 'blue', 'blue', 'blue', 'blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.after_q_eye.set_line_label(i, "Eye[Data {0}]".format(i))
            else:
                self.after_q_eye.set_line_label(i, labels[i])
            self.after_q_eye.set_line_width(i, widths[i])
            self.after_q_eye.set_line_color(i, colors[i])
            self.after_q_eye.set_line_style(i, styles[i])
            self.after_q_eye.set_line_marker(i, markers[i])
            self.after_q_eye.set_line_alpha(i, alphas[i])

        self._after_q_eye_win = sip.wrapinstance(self.after_q_eye.qwidget(), Qt.QWidget)
        self.views_grid_layout_4.addWidget(self._after_q_eye_win, 2, 1, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_4.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_4.setColumnStretch(c, 1)
        self.after_q = blocks.complex_to_imag(1)
        self.after_i_eye = qtgui.eye_sink_f(
            1024, #size
            samp_rate, #samp_rate
            1, #number of inputs
            None
        )
        self.after_i_eye.set_update_time(0.10)
        self.after_i_eye.set_samp_per_symbol(sps)
        self.after_i_eye.set_y_axis(-1, 1)

        self.after_i_eye.set_y_label('AFTER I | reconstructed', "")

        self.after_i_eye.enable_tags(True)
        self.after_i_eye.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.after_i_eye.enable_autoscale(True)
        self.after_i_eye.enable_grid(True)
        self.after_i_eye.enable_axis_labels(True)
        self.after_i_eye.enable_control_panel(False)


        labels = ['After EQ I | reconstructed', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'blue', 'blue', 'blue', 'blue',
            'blue', 'blue', 'blue', 'blue', 'blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.after_i_eye.set_line_label(i, "Eye[Data {0}]".format(i))
            else:
                self.after_i_eye.set_line_label(i, labels[i])
            self.after_i_eye.set_line_width(i, widths[i])
            self.after_i_eye.set_line_color(i, colors[i])
            self.after_i_eye.set_line_style(i, styles[i])
            self.after_i_eye.set_line_marker(i, markers[i])
            self.after_i_eye.set_line_alpha(i, alphas[i])

        self._after_i_eye_win = sip.wrapinstance(self.after_i_eye.qwidget(), Qt.QWidget)
        self.views_grid_layout_2.addWidget(self._after_i_eye_win, 2, 1, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_2.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_2.setColumnStretch(c, 1)
        self.after_i = blocks.complex_to_real(1)
        self.after_eye_reconstruction = filter.interp_fir_filter_ccf(sps, eye_synthesis_taps)
        self.after_eye_reconstruction.declare_sample_delay(0)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.after_eye_reconstruction, 0), (self.after_i, 0))
        self.connect((self.after_eye_reconstruction, 0), (self.after_q, 0))
        self.connect((self.after_i, 0), (self.after_i_eye, 0))
        self.connect((self.after_q, 0), (self.after_q_eye, 0))
        self.connect((self.ber_scale, 0), (self.ber_display, 0))
        self.connect((self.ber_scale, 0), (self.ber_history, 0))
        self.connect((self.ber_scale, 0), (self.probe_ber_scale, 0))
        self.connect((self.ber_test_count, 0), (self.ber_test_ratio, 1))
        self.connect((self.ber_test_count, 0), (self.probe_ber_test_count, 0))
        self.connect((self.ber_test_done, 0), (self.ber_test_not_done, 0))
        self.connect((self.ber_test_error_sum, 0), (self.ber_test_errors, 0))
        self.connect((self.ber_test_errors, 0), (self.ber_test_ratio, 0))
        self.connect((self.ber_test_errors, 0), (self.probe_ber_test_errors, 0))
        self.connect((self.ber_test_gate, 0), (self.ber_test_gated_errors, 1))
        self.connect((self.ber_test_gate, 0), (self.ber_test_window_sum, 0))
        self.connect((self.ber_test_gated_errors, 0), (self.ber_test_error_sum, 0))
        self.connect((self.ber_test_index, 0), (self.ber_test_done, 0))
        self.connect((self.ber_test_not_done, 0), (self.ber_test_gate, 0))
        self.connect((self.ber_test_ratio, 0), (self.probe_ber_test_ratio, 0))
        self.connect((self.ber_test_sum_10k, 0), (self.ber_test_gated_errors, 0))
        self.connect((self.ber_test_sum_10k, 0), (self.ber_test_zero, 0))
        self.connect((self.ber_test_unit, 0), (self.ber_test_index, 0))
        self.connect((self.ber_test_window_sum, 0), (self.ber_test_count, 0))
        self.connect((self.ber_test_zero, 0), (self.ber_test_unit, 0))
        self.connect((self.channel, 0), (self.eye_i, 0))
        self.connect((self.channel, 0), (self.eye_q, 0))
        self.connect((self.channel, 0), (self.rx_level, 0))
        self.connect((self.channel, 0), (self.rx_milliwatts, 0))
        self.connect((self.channel, 0), (self.spectrum, 0))
        self.connect((self.channel, 0), (self.spectrum_budget, 0))
        self.connect((self.channel, 0), (self.waveform, 0))
        self.connect((self.clock_sync, 0), (self.rx_scale, 0))
        self.connect((self.clock_sync, 1), (self.timing_error, 0))
        self.connect((self.clock_sync, 2), (self.unused_timing_states, 0))
        self.connect((self.clock_sync, 3), (self.unused_timing_states, 1))
        self.connect((self.decoder, 0), (self.diff_decoder, 0))
        self.connect((self.delay, 0), (self.skip_tx, 0))
        self.connect((self.diff_decoder, 0), (self.unpack_rx, 0))
        self.connect((self.eq_tap_decimator, 0), (self.eq_tap_magnitudes, 0))
        self.connect((self.eq_tap_magnitudes, 0), (self.eq_tap_plot, 0))
        self.connect((self.equalizer, 0), (self.after_eye_reconstruction, 0))
        self.connect((self.equalizer, 0), (self.constellation, 0))
        self.connect((self.equalizer, 0), (self.decoder, 0))
        self.connect((self.equalizer, 1), (self.eq_tap_decimator, 0))
        self.connect((self.equalizer, 0), (self.evm, 0))
        self.connect((self.equalizer, 0), (self.rf_constellation, 0))
        self.connect((self.errors_float, 0), (self.ber_test_sum_10k, 0))
        self.connect((self.errors_float, 0), (self.integrate, 0))
        self.connect((self.evm, 0), (self.eq_error_trace, 0))
        self.connect((self.evm, 0), (self.evm_rms, 0))
        self.connect((self.evm_circles, 0), (self.constellation, 2))
        self.connect((self.evm_circles, 0), (self.tx_constellation, 2))
        self.connect((self.evm_rms, 0), (self.eq_evm_history, 0))
        self.connect((self.evm_rms, 0), (self.evm_display, 0))
        self.connect((self.evm_rms, 0), (self.evm_history, 0))
        self.connect((self.evm_rms, 0), (self.probe_evm_rms, 0))
        self.connect((self.eye_i, 0), (self.eye, 0))
        self.connect((self.eye_q, 0), (self.eye_quadrature, 0))
        self.connect((self.ideal_symbols, 0), (self.constellation, 1))
        self.connect((self.ideal_symbols, 0), (self.tx_constellation, 1))
        self.connect((self.integrate, 0), (self.ber_scale, 0))
        self.connect((self.middle_eye_reconstruction, 0), (self.middle_i, 0))
        self.connect((self.middle_eye_reconstruction, 0), (self.middle_q, 0))
        self.connect((self.middle_i, 0), (self.middle_i_eye, 0))
        self.connect((self.middle_q, 0), (self.middle_q_eye, 0))
        self.connect((self.modulator, 0), (self.tx_power, 0))
        self.connect((self.random_bytes, 0), (self.modulator, 0))
        self.connect((self.random_bytes, 0), (self.tx_symbol_chunks, 0))
        self.connect((self.random_bytes, 0), (self.unpack_tx, 0))
        self.connect((self.rx_dbm, 0), (self.probe_rx_dbm, 0))
        self.connect((self.rx_ebno, 0), (self.probe_rx_ebno, 0))
        self.connect((self.rx_level, 0), (self.clock_sync, 0))
        self.connect((self.rx_milliwatts, 0), (self.rx_power_sum, 0))
        self.connect((self.rx_power_mean, 0), (self.rx_dbm, 0))
        self.connect((self.rx_power_sum, 0), (self.rx_power_mean, 0))
        self.connect((self.rx_scale, 0), (self.before_eq_constellation, 0))
        self.connect((self.rx_scale, 0), (self.equalizer, 0))
        self.connect((self.rx_scale, 0), (self.middle_eye_reconstruction, 0))
        self.connect((self.rx_snr, 0), (self.probe_rx_snr, 0))
        self.connect((self.skip_rx, 0), (self.xor, 0))
        self.connect((self.skip_tx, 0), (self.xor, 1))
        self.connect((self.throttle, 0), (self.channel, 0))
        self.connect((self.tx_dbm, 0), (self.probe_tx_dbm, 0))
        self.connect((self.tx_dbm, 0), (self.rx_ebno, 0))
        self.connect((self.tx_dbm, 0), (self.rx_snr, 0))
        self.connect((self.tx_dbm, 0), (self.tx_papr, 1))
        self.connect((self.tx_eye_i, 0), (self.tx_eye_i_eye, 0))
        self.connect((self.tx_eye_q, 0), (self.tx_eye_q_eye, 0))
        self.connect((self.tx_milliwatts, 0), (self.tx_peak_vectors, 0))
        self.connect((self.tx_milliwatts, 0), (self.tx_power_sum, 0))
        self.connect((self.tx_papr, 0), (self.probe_tx_papr, 0))
        self.connect((self.tx_peak_dbm, 0), (self.probe_tx_peak_dbm, 0))
        self.connect((self.tx_peak_dbm, 0), (self.tx_papr, 0))
        self.connect((self.tx_peak_mw, 0), (self.tx_peak_dbm, 0))
        self.connect((self.tx_peak_vectors, 0), (self.tx_peak_mw, 0))
        self.connect((self.tx_power, 0), (self.spectrum, 1))
        self.connect((self.tx_power, 0), (self.throttle, 0))
        self.connect((self.tx_power, 0), (self.tx_eye_i, 0))
        self.connect((self.tx_power, 0), (self.tx_eye_q, 0))
        self.connect((self.tx_power, 0), (self.tx_milliwatts, 0))
        self.connect((self.tx_power, 0), (self.tx_waveform, 0))
        self.connect((self.tx_power, 0), (self.waveform, 1))
        self.connect((self.tx_power_mean, 0), (self.tx_dbm, 0))
        self.connect((self.tx_power_sum, 0), (self.tx_power_mean, 0))
        self.connect((self.tx_symbol_chunks, 0), (self.tx_symbol_diff, 0))
        self.connect((self.tx_symbol_diff, 0), (self.tx_symbols, 0))
        self.connect((self.tx_symbols, 0), (self.tx_constellation, 0))
        self.connect((self.unpack_rx, 0), (self.skip_rx, 0))
        self.connect((self.unpack_tx, 0), (self.delay, 0))
        self.connect((self.xor, 0), (self.errors_float, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "single_carrier_qpsk")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_reference_delay(self):
        return self.reference_delay

    def set_reference_delay(self, reference_delay):
        self.reference_delay = reference_delay
        self.delay.set_dly(int(self.reference_delay))

    def get_symbol_rate(self):
        return self.symbol_rate

    def set_symbol_rate(self, symbol_rate):
        self.symbol_rate = symbol_rate
        self.set_samp_rate(self.symbol_rate*self.sps)
        self.set_bit_rate(self.symbol_rate*self.k)
        self.set_rrc_bandwidth(self.symbol_rate*(1+self.alpha))
        self.evm_history.set_samp_rate(self.symbol_rate)
        self.timing_error.set_samp_rate(self.symbol_rate)
        self.set_esno_rx_db(self.snr_rx_db+10*math.log10(self.samp_rate/self.symbol_rate))
        self.eq_evm_history.set_samp_rate(self.symbol_rate)
        self.eq_error_trace.set_samp_rate(self.symbol_rate)

    def get_tx_power_dbm(self):
        return self.tx_power_dbm

    def set_tx_power_dbm(self, tx_power_dbm):
        self.tx_power_dbm = tx_power_dbm
        self.set_tx_amplitude(10**(self.tx_power_dbm/20.0))
        self.set_expected_rx_dbm(self.tx_power_dbm-self.path_loss_db)

    def get_path_loss_db(self):
        return self.path_loss_db

    def set_path_loss_db(self, path_loss_db):
        self.path_loss_db = path_loss_db
        self.set_path_gain(10**(-self.path_loss_db/20.0))
        self.set_expected_rx_dbm(self.tx_power_dbm-self.path_loss_db)
        self.rx_snr.set_k((-self.path_loss_db-self.rx_noise_dbm if self.noise_enabled else float('inf')))
        self.rx_ebno.set_k((-self.path_loss_db-self.rx_noise_dbm+10*math.log10(self.samp_rate/self.bit_rate) if self.noise_enabled else float('inf')))

    def get_rx_noise_dbm(self):
        return self.rx_noise_dbm

    def set_rx_noise_dbm(self, rx_noise_dbm):
        self.rx_noise_dbm = rx_noise_dbm
        self.set_noise_volt(10**(self.rx_noise_dbm/20.0) if self.noise_enabled else 0.0)
        self.set_snr_rx_db(self.expected_rx_dbm-self.rx_noise_dbm if self.noise_enabled else float('inf'))
        self.rx_snr.set_k((-self.path_loss_db-self.rx_noise_dbm if self.noise_enabled else float('inf')))
        self.rx_ebno.set_k((-self.path_loss_db-self.rx_noise_dbm+10*math.log10(self.samp_rate/self.bit_rate) if self.noise_enabled else float('inf')))

    def get_noise_enabled(self):
        return self.noise_enabled

    def set_noise_enabled(self, noise_enabled):
        self.noise_enabled = noise_enabled
        self.set_noise_volt(10**(self.rx_noise_dbm/20.0) if self.noise_enabled else 0.0)
        self.set_snr_rx_db(self.expected_rx_dbm-self.rx_noise_dbm if self.noise_enabled else float('inf'))
        self.rx_snr.set_k((-self.path_loss_db-self.rx_noise_dbm if self.noise_enabled else float('inf')))
        self.rx_ebno.set_k((-self.path_loss_db-self.rx_noise_dbm+10*math.log10(self.samp_rate/self.bit_rate) if self.noise_enabled else float('inf')))

    def get_evm_guide_percent(self):
        return self.evm_guide_percent

    def set_evm_guide_percent(self, evm_guide_percent):
        self.evm_guide_percent = evm_guide_percent
        self.evm_circles.set_data([p+self.symbol_rms*self.evm_guide_percent/100*complex(math.cos(t),math.sin(t)) for p in const.points() for t in numpy.linspace(0,2*math.pi,64,endpoint=False)], [])

    def get_eq_taps(self):
        return self.eq_taps

    def set_eq_taps(self, eq_taps):
        self.eq_taps = eq_taps
        self.set_eq_delay_symbols((self.eq_taps-1)//2)

    def get_eq_step(self):
        return self.eq_step

    def set_eq_step(self, eq_step):
        self.eq_step = eq_step

    def get_channel_echo(self):
        return self.channel_echo

    def set_channel_echo(self, channel_echo):
        self.channel_echo = channel_echo
        self.channel.set_taps([self.path_gain/(1+self.channel_echo**2)**0.5]+[0j]*(self.sps-1)+[self.path_gain*self.channel_echo/(1+self.channel_echo**2)**0.5])

    def get_ber_test_bits(self):
        return self.ber_test_bits

    def set_ber_test_bits(self, ber_test_bits):
        self.ber_test_bits = ber_test_bits
        self.set_ber_test_blocks(max(1, int(self.ber_test_bits) // 10000))

    def get_const(self):
        return self.const

    def set_const(self, const):
        self.const = const
        self.decoder.set_constellation(self.const)

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_samp_rate(self.symbol_rate*self.sps)
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.alpha, 11*self.sps*self.nfilts))
        self.channel.set_taps([self.path_gain/(1+self.channel_echo**2)**0.5]+[0j]*(self.sps-1)+[self.path_gain*self.channel_echo/(1+self.channel_echo**2)**0.5])
        self.eye.set_samp_per_symbol(self.sps)
        self.eye_quadrature.set_samp_per_symbol(self.sps)
        self.set_eye_synthesis_taps(firdes.root_raised_cosine(self.sps,self.sps,1.0,self.alpha,11*self.sps))
        self.middle_i_eye.set_samp_per_symbol(self.sps)
        self.middle_q_eye.set_samp_per_symbol(self.sps)
        self.after_i_eye.set_samp_per_symbol(self.sps)
        self.after_q_eye.set_samp_per_symbol(self.sps)
        self.tx_eye_i_eye.set_samp_per_symbol(self.sps)
        self.tx_eye_q_eye.set_samp_per_symbol(self.sps)

    def get_k(self):
        return self.k

    def set_k(self, k):
        self.k = k
        self.set_bit_rate(self.symbol_rate*self.k)

    def get_expected_rx_dbm(self):
        return self.expected_rx_dbm

    def set_expected_rx_dbm(self, expected_rx_dbm):
        self.expected_rx_dbm = expected_rx_dbm
        self.set_snr_rx_db(self.expected_rx_dbm-self.rx_noise_dbm if self.noise_enabled else float('inf'))

    def get_warmup_bits(self):
        return self.warmup_bits

    def set_warmup_bits(self, warmup_bits):
        self.warmup_bits = warmup_bits
        self.set_ber_test_seconds((self.warmup_bits + 10000*self.ber_test_blocks) / self.bit_rate)

    def get_symbol_rms(self):
        return self.symbol_rms

    def set_symbol_rms(self, symbol_rms):
        self.symbol_rms = symbol_rms
        self.tx_power.set_k(self.tx_amplitude/self.symbol_rms)
        self.rx_scale.set_k(self.symbol_rms)
        self.evm_circles.set_data([p+self.symbol_rms*self.evm_guide_percent/100*complex(math.cos(t),math.sin(t)) for p in const.points() for t in numpy.linspace(0,2*math.pi,64,endpoint=False)], [])

    def get_snr_rx_db(self):
        return self.snr_rx_db

    def set_snr_rx_db(self, snr_rx_db):
        self.snr_rx_db = snr_rx_db
        self.set_esno_rx_db(self.snr_rx_db+10*math.log10(self.samp_rate/self.symbol_rate))
        self.set_ebno_rx_db(self.snr_rx_db+10*math.log10(self.samp_rate/self.bit_rate))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.throttle.set_sample_rate(self.samp_rate)
        self.spectrum.set_frequency_range(0, self.samp_rate)
        self.waveform.set_samp_rate(self.samp_rate)
        self.eye.set_samp_rate(self.samp_rate)
        self.set_esno_rx_db(self.snr_rx_db+10*math.log10(self.samp_rate/self.symbol_rate))
        self.set_ebno_rx_db(self.snr_rx_db+10*math.log10(self.samp_rate/self.bit_rate))
        self.rx_ebno.set_k((-self.path_loss_db-self.rx_noise_dbm+10*math.log10(self.samp_rate/self.bit_rate) if self.noise_enabled else float('inf')))
        self.eye_quadrature.set_samp_rate(self.samp_rate)
        self.middle_i_eye.set_samp_rate(self.samp_rate)
        self.middle_q_eye.set_samp_rate(self.samp_rate)
        self.after_i_eye.set_samp_rate(self.samp_rate)
        self.after_q_eye.set_samp_rate(self.samp_rate)
        self.tx_eye_i_eye.set_samp_rate(self.samp_rate)
        self.tx_eye_q_eye.set_samp_rate(self.samp_rate)
        self.tx_waveform.set_samp_rate(self.samp_rate)
        self.spectrum_budget.set_frequency_range(0, self.samp_rate)

    def get_nfilts(self):
        return self.nfilts

    def set_nfilts(self, nfilts):
        self.nfilts = nfilts
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.alpha, 11*self.sps*self.nfilts))

    def get_bit_rate(self):
        return self.bit_rate

    def set_bit_rate(self, bit_rate):
        self.bit_rate = bit_rate
        self.ber_history.set_samp_rate(self.bit_rate/self.ber_window)
        self.set_ebno_rx_db(self.snr_rx_db+10*math.log10(self.samp_rate/self.bit_rate))
        self.rx_ebno.set_k((-self.path_loss_db-self.rx_noise_dbm+10*math.log10(self.samp_rate/self.bit_rate) if self.noise_enabled else float('inf')))
        self.set_ber_test_seconds((self.warmup_bits + 10000*self.ber_test_blocks) / self.bit_rate)

    def get_ber_test_blocks(self):
        return self.ber_test_blocks

    def set_ber_test_blocks(self, ber_test_blocks):
        self.ber_test_blocks = ber_test_blocks
        self.set_ber_test_seconds((self.warmup_bits + 10000*self.ber_test_blocks) / self.bit_rate)
        self.ber_test_done.set_hi((self.ber_test_blocks + 0.5))
        self.ber_test_done.set_lo((self.ber_test_blocks + 0.5))

    def get_alpha(self):
        return self.alpha

    def set_alpha(self, alpha):
        self.alpha = alpha
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.alpha, 11*self.sps*self.nfilts))
        self.set_rrc_bandwidth(self.symbol_rate*(1+self.alpha))
        self.set_eye_synthesis_taps(firdes.root_raised_cosine(self.sps,self.sps,1.0,self.alpha,11*self.sps))

    def get_tx_amplitude(self):
        return self.tx_amplitude

    def set_tx_amplitude(self, tx_amplitude):
        self.tx_amplitude = tx_amplitude
        self.tx_power.set_k(self.tx_amplitude/self.symbol_rms)
        self.rx_level.set_k(1.0/(self.tx_amplitude*self.path_gain))

    def get_timing_bw(self):
        return self.timing_bw

    def set_timing_bw(self, timing_bw):
        self.timing_bw = timing_bw
        self.clock_sync.set_loop_bandwidth(self.timing_bw)

    def get_rrc_taps(self):
        return self.rrc_taps

    def set_rrc_taps(self, rrc_taps):
        self.rrc_taps = rrc_taps
        self.clock_sync.update_taps(self.rrc_taps)

    def get_rrc_bandwidth(self):
        return self.rrc_bandwidth

    def set_rrc_bandwidth(self, rrc_bandwidth):
        self.rrc_bandwidth = rrc_bandwidth

    def get_path_gain(self):
        return self.path_gain

    def set_path_gain(self, path_gain):
        self.path_gain = path_gain
        self.channel.set_taps([self.path_gain/(1+self.channel_echo**2)**0.5]+[0j]*(self.sps-1)+[self.path_gain*self.channel_echo/(1+self.channel_echo**2)**0.5])
        self.rx_level.set_k(1.0/(self.tx_amplitude*self.path_gain))

    def get_noise_volt(self):
        return self.noise_volt

    def set_noise_volt(self, noise_volt):
        self.noise_volt = noise_volt
        self.channel.set_noise_voltage(self.noise_volt)

    def get_eye_synthesis_taps(self):
        return self.eye_synthesis_taps

    def set_eye_synthesis_taps(self, eye_synthesis_taps):
        self.eye_synthesis_taps = eye_synthesis_taps
        self.middle_eye_reconstruction.set_taps(self.eye_synthesis_taps)
        self.after_eye_reconstruction.set_taps(self.eye_synthesis_taps)

    def get_esno_rx_db(self):
        return self.esno_rx_db

    def set_esno_rx_db(self, esno_rx_db):
        self.esno_rx_db = esno_rx_db

    def get_eq_delay_symbols(self):
        return self.eq_delay_symbols

    def set_eq_delay_symbols(self, eq_delay_symbols):
        self.eq_delay_symbols = eq_delay_symbols

    def get_eq_algorithm(self):
        return self.eq_algorithm

    def set_eq_algorithm(self, eq_algorithm):
        self.eq_algorithm = eq_algorithm

    def get_ebno_rx_db(self):
        return self.ebno_rx_db

    def set_ebno_rx_db(self, ebno_rx_db):
        self.ebno_rx_db = ebno_rx_db

    def get_ber_window(self):
        return self.ber_window

    def set_ber_window(self, ber_window):
        self.ber_window = ber_window
        self.ber_scale.set_k((1.0/self.ber_window))
        self.ber_history.set_samp_rate(self.bit_rate/self.ber_window)

    def get_ber_test_seconds(self):
        return self.ber_test_seconds

    def set_ber_test_seconds(self, ber_test_seconds):
        self.ber_test_seconds = ber_test_seconds

    def get_ber_error_weight(self):
        return self.ber_error_weight

    def set_ber_error_weight(self, ber_error_weight):
        self.ber_error_weight = ber_error_weight
        self.ber_test_errors.set_k(self.ber_error_weight)



def argument_parser():
    parser = ArgumentParser()
    parser.add_argument(
        "--reference-delay", dest="reference_delay", type=intx, default=68,
        help="Set TX reference delay (bits) [default=%(default)r]")
    parser.add_argument(
        "--symbol-rate", dest="symbol_rate", type=eng_float, default=eng_notation.num_to_str(float(1e6)),
        help="Set Symbol rate (symbols/s) [default=%(default)r]")
    parser.add_argument(
        "--tx-power-dbm", dest="tx_power_dbm", type=eng_float, default=eng_notation.num_to_str(float(0)),
        help="Set TX average conducted power (dBm) [default=%(default)r]")
    parser.add_argument(
        "--path-loss-db", dest="path_loss_db", type=eng_float, default=eng_notation.num_to_str(float(80)),
        help="Set Net path loss including gains/losses (dB) [default=%(default)r]")
    parser.add_argument(
        "--rx-noise-dbm", dest="rx_noise_dbm", type=eng_float, default=eng_notation.num_to_str(float((-100))),
        help="Set RX noise over sample bandwidth (dBm) [default=%(default)r]")
    parser.add_argument(
        "--noise-enabled", dest="noise_enabled", type=intx, default=1,
        help="Set Receiver noise enabled (0/1) [default=%(default)r]")
    parser.add_argument(
        "--evm-guide-percent", dest="evm_guide_percent", type=eng_float, default=eng_notation.num_to_str(float(5)),
        help="Set Constellation guide radius (% RMS) [default=%(default)r]")
    parser.add_argument(
        "--eq-taps", dest="eq_taps", type=intx, default=11,
        help="Set Adaptive equalizer taps [default=%(default)r]")
    parser.add_argument(
        "--eq-step", dest="eq_step", type=eng_float, default=eng_notation.num_to_str(float(0.01)),
        help="Set NLMS adaptation step [default=%(default)r]")
    parser.add_argument(
        "--channel-echo", dest="channel_echo", type=eng_float, default=eng_notation.num_to_str(float(0)),
        help="Set One-symbol echo voltage ratio [default=%(default)r]")
    parser.add_argument(
        "--ber-test-bits", dest="ber_test_bits", type=intx, default=1000000,
        help="Set BER test length (compared bits) [default=%(default)r]")
    return parser


def main(top_block_cls=single_carrier_qpsk, options=None):
    if options is None:
        options = argument_parser().parse_args()

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(reference_delay=options.reference_delay, symbol_rate=options.symbol_rate, tx_power_dbm=options.tx_power_dbm, path_loss_db=options.path_loss_db, rx_noise_dbm=options.rx_noise_dbm, noise_enabled=options.noise_enabled, evm_guide_percent=options.evm_guide_percent, eq_taps=options.eq_taps, eq_step=options.eq_step, channel_echo=options.channel_echo, ber_test_bits=options.ber_test_bits)
    snippets_main_after_init(tb)
    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
