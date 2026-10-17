#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: 16-QAM over the air | USRP N210 loopback
# Author: Antenna benchmark
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import blocks
import numpy
from gnuradio import digital
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import uhd
import time
import math
import sip
import threading


def snipfcn_equalizer_initial_taps(self):
    self.equalizer.set_taps([0j]*((self.eq_taps-1)//2)+[1+0j]+[0j]*(self.eq_taps//2))

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


def snippets_main_after_init(tb):
    snipfcn_equalizer_initial_taps(tb)
    snipfcn_square_plot_panels(tb)

class n210_16qam(gr.top_block, Qt.QWidget):

    def __init__(self, eq_step=0.01, eq_taps=11, evm_guide_percent=5, symbol_rate=1e6, tx_level_dbfs=(-15), usrp_address='addr=192.168.10.2', center_freq_hz=915e6, rx_gain_db=75):
        gr.top_block.__init__(self, "16-QAM over the air | USRP N210 loopback", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("16-QAM over the air | USRP N210 loopback")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "n210_16qam")

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
        self.eq_step = eq_step
        self.eq_taps = eq_taps
        self.evm_guide_percent = evm_guide_percent
        self.symbol_rate = symbol_rate
        self.tx_level_dbfs = tx_level_dbfs
        self.usrp_address = usrp_address
        self.center_freq_hz = center_freq_hz
        self.rx_gain_db = rx_gain_db

        ##################################################
        # Variables
        ##################################################
        self.const = const = digital.constellation_16qam().base()
        self.const.set_npwr(1.0)
        self.symbol_rms = symbol_rms = (sum(abs(p)**2 for p in const.points())/len(const.points()))**0.5
        self.sps = sps = 4
        self.nfilts = nfilts = 32
        self.k = k = const.bits_per_symbol()
        self.alpha = alpha = 0.35
        self.warmup_bits = warmup_bits = 4096
        self.tx_gain_norm = tx_gain_norm = 0.5
        self.tx_amplitude = tx_amplitude = 10**(tx_level_dbfs/20.0)
        self.timing_bw = timing_bw = 0.0628
        self.samp_rate = samp_rate = symbol_rate*sps
        self.rx_gain_norm = rx_gain_norm = 0.5
        self.rrc_taps = rrc_taps = firdes.root_raised_cosine(nfilts, nfilts*sps, 1.0, alpha, 11*sps*nfilts)
        self.rrc_bandwidth = rrc_bandwidth = symbol_rate*(1+alpha)
        self.phase_fix_deg = phase_fix_deg = 0
        self.eye_synthesis_taps = eye_synthesis_taps = firdes.root_raised_cosine(sps,sps,1.0,alpha,11*sps)
        self.eq_delay_symbols = eq_delay_symbols = (eq_taps-1)//2
        self.eq_algorithm = eq_algorithm = digital.adaptive_algorithm_lms( const, eq_step/(eq_taps*symbol_rms**2)).base()
        self.data_period_bits = data_period_bits = 8*32768
        self.carrier_loop_bw = carrier_loop_bw = 2*math.pi/200
        self.bit_rate = bit_rate = symbol_rate*k
        self.ber_window = ber_window = 10000

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
        self.views.addTab(self.views_widget_3, 'RF levels')
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
        self._tx_gain_norm_range = qtgui.Range(0, 1, 0.01, 0.5, 200)
        self._tx_gain_norm_win = qtgui.RangeWidget(self._tx_gain_norm_range, self.set_tx_gain_norm, "TX gain (normalized 0-1)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._tx_gain_norm_win)
        self._rx_gain_norm_range = qtgui.Range(0, 1, 0.01, 0.5, 200)
        self._rx_gain_norm_win = qtgui.RangeWidget(self._rx_gain_norm_range, self.set_rx_gain_norm, "RX gain (normalized 0-1)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._rx_gain_norm_win)
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
        self.usrp_tx = uhd.usrp_sink(
            ",".join((usrp_address, "")),
            uhd.stream_args(
                cpu_format="fc32",
                otw_format="sc16",
                args='',
                channels=list(range(0,1)),
            ),
            "",
        )
        self.usrp_tx.set_samp_rate(samp_rate)
        # No synchronization enforced.

        self.usrp_tx.set_center_freq(center_freq_hz, 0)
        self.usrp_tx.set_antenna("TX/RX", 0)
        self.usrp_tx.set_normalized_gain(tx_gain_norm, 0)
        self.usrp_rx = uhd.usrp_source(
            ",".join((usrp_address, "")),
            uhd.stream_args(
                cpu_format="fc32",
                otw_format="sc16",
                args='',
                channels=list(range(0,1)),
            ),
        )
        self.usrp_rx.set_samp_rate(samp_rate)
        # No synchronization enforced.

        self.usrp_rx.set_center_freq(center_freq_hz, 0)
        self.usrp_rx.set_antenna("RX2", 0)
        self.usrp_rx.set_rx_agc(False, 0)
        self.usrp_rx.set_normalized_gain(rx_gain_norm, 0)
        self.usrp_rx.set_auto_dc_offset(True, 0)
        self.usrp_rx.set_auto_iq_balance(True, 0)
        self.unused_timing_states = blocks.null_sink(gr.sizeof_float*1)
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
        self.tx_symbol_diff = digital.diff_encoder_bb(16, digital.DIFF_DIFFERENTIAL)
        self.tx_symbol_chunks = blocks.packed_to_unpacked_bb(k, gr.GR_MSB_FIRST)
        self.tx_power_sum = blocks.integrate_ff(4096, 1)
        self.tx_power_mean = blocks.multiply_const_ff((1.0/4096))
        self.tx_power_display = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.tx_power_display.set_update_time(0.10)
        self.tx_power_display.set_title('TX digital average level')

        labels = ['TX digital average level', '', '', '', '',
            '', '', '', '', '']
        units = ['dBFS', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.tx_power_display.set_min(i, -200)
            self.tx_power_display.set_max(i, 100)
            self.tx_power_display.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.tx_power_display.set_label(i, "Data {0}".format(i))
            else:
                self.tx_power_display.set_label(i, labels[i])
            self.tx_power_display.set_unit(i, units[i])
            self.tx_power_display.set_factor(i, factor[i])

        self.tx_power_display.enable_autoscale(False)
        self._tx_power_display_win = sip.wrapinstance(self.tx_power_display.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._tx_power_display_win, 3, 0, 1, 1)
        for r in range(3, 4):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_3.setColumnStretch(c, 1)
        self.tx_power = blocks.multiply_const_cc(tx_amplitude/symbol_rms)
        self.tx_peak_vectors = blocks.stream_to_vector(gr.sizeof_float*1, 4096)
        self.tx_peak_mw = blocks.max_ff(4096, 1)
        self.tx_peak_dbm = blocks.nlog10_ff(10, 1, 0)
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
                self.spectrum_budget.set_line_label(i, "Data {0}".format(i))
            else:
                self.spectrum_budget.set_line_label(i, labels[i])
            self.spectrum_budget.set_line_width(i, widths[i])
            self.spectrum_budget.set_line_color(i, colors[i])
            self.spectrum_budget.set_line_alpha(i, alphas[i])

        self._spectrum_budget_win = sip.wrapinstance(self.spectrum_budget.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._spectrum_budget_win, 2, 0, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
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
        self.snr_display = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.snr_display.set_update_time(0.10)
        self.snr_display.set_title('MER from decision-directed EVM (Es/N0 estimate)')

        labels = ['MER from decision-directed EVM (Es/N0 estimate)', '', '', '', '',
            '', '', '', '', '']
        units = ['dB', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.snr_display.set_min(i, -100)
            self.snr_display.set_max(i, 100)
            self.snr_display.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.snr_display.set_label(i, "Data {0}".format(i))
            else:
                self.snr_display.set_label(i, labels[i])
            self.snr_display.set_unit(i, units[i])
            self.snr_display.set_factor(i, factor[i])

        self.snr_display.enable_autoscale(False)
        self._snr_display_win = sip.wrapinstance(self.snr_display.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._snr_display_win, 4, 1, 1, 1)
        for r in range(4, 5):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_3.setColumnStretch(c, 1)
        self.skip_tx = blocks.skiphead(gr.sizeof_char*1, (warmup_bits+data_period_bits))
        self.skip_rx = blocks.skiphead(gr.sizeof_char*1, (warmup_bits+data_period_bits))
        self.rx_snr = blocks.nlog10_ff((-20), 1, 40)
        self.rx_scale = blocks.multiply_const_cc(symbol_rms)
        self.rx_power_sum = blocks.integrate_ff(4096, 1)
        self.rx_power_mean = blocks.multiply_const_ff((1.0/4096))
        self.rx_power_display = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.rx_power_display.set_update_time(0.10)
        self.rx_power_display.set_title('RX ADC level: signal + noise')

        labels = ['RX ADC level: signal + noise', '', '', '', '',
            '', '', '', '', '']
        units = ['dBFS', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.rx_power_display.set_min(i, -200)
            self.rx_power_display.set_max(i, 100)
            self.rx_power_display.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.rx_power_display.set_label(i, "Data {0}".format(i))
            else:
                self.rx_power_display.set_label(i, labels[i])
            self.rx_power_display.set_unit(i, units[i])
            self.rx_power_display.set_factor(i, factor[i])

        self.rx_power_display.enable_autoscale(False)
        self._rx_power_display_win = sip.wrapinstance(self.rx_power_display.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._rx_power_display_win, 3, 1, 1, 1)
        for r in range(3, 4):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_3.setColumnStretch(c, 1)
        self.rx_milliwatts = blocks.complex_to_mag_squared(1)
        self.rx_level = blocks.multiply_const_cc(10**(rx_gain_db/20.0))
        self.rx_ebno = blocks.nlog10_ff((-20), 1, (40-10*math.log10(k)))
        self.rx_dbm = blocks.nlog10_ff(10, 1, 0)
        self.random_bytes = blocks.vector_source_b(list(map(int, numpy.random.randint(0, 256, 32768))), True)
        self.power_reference_chart = qtgui.time_sink_f(
            128, #size
            samp_rate/4096, #samp_rate
            'MER history (dB)', #name
            1, #number of inputs
            None # parent
        )
        self.power_reference_chart.set_update_time(0.10)
        self.power_reference_chart.set_y_axis(-1, 1)

        self.power_reference_chart.set_y_label('Amplitude', "")

        self.power_reference_chart.enable_tags(True)
        self.power_reference_chart.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.power_reference_chart.enable_autoscale(True)
        self.power_reference_chart.enable_grid(False)
        self.power_reference_chart.enable_axis_labels(True)
        self.power_reference_chart.enable_control_panel(False)
        self.power_reference_chart.enable_stem_plot(False)


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
                self.power_reference_chart.set_line_label(i, "Data {0}".format(i))
            else:
                self.power_reference_chart.set_line_label(i, labels[i])
            self.power_reference_chart.set_line_width(i, widths[i])
            self.power_reference_chart.set_line_color(i, colors[i])
            self.power_reference_chart.set_line_style(i, styles[i])
            self.power_reference_chart.set_line_marker(i, markers[i])
            self.power_reference_chart.set_line_alpha(i, alphas[i])

        self._power_reference_chart_win = sip.wrapinstance(self.power_reference_chart.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._power_reference_chart_win, 2, 1, 1, 1)
        for r in range(2, 3):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_3.setColumnStretch(c, 1)
        self.power_history = qtgui.time_sink_f(
            128, #size
            samp_rate/4096, #samp_rate
            'Digital levels | TX average and RX ADC (dBFS)', #name
            2, #number of inputs
            None # parent
        )
        self.power_history.set_update_time(0.10)
        self.power_history.set_y_axis(-1, 1)

        self.power_history.set_y_label('Amplitude', "")

        self.power_history.enable_tags(True)
        self.power_history.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.power_history.enable_autoscale(True)
        self.power_history.enable_grid(False)
        self.power_history.enable_axis_labels(True)
        self.power_history.enable_control_panel(False)
        self.power_history.enable_stem_plot(False)


        labels = ['TX average (dBFS)', 'RX ADC total (dBFS)', 'Signal 3', 'Signal 4', 'Signal 5',
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
                self.power_history.set_line_label(i, "Data {0}".format(i))
            else:
                self.power_history.set_line_label(i, labels[i])
            self.power_history.set_line_width(i, widths[i])
            self.power_history.set_line_color(i, colors[i])
            self.power_history.set_line_style(i, styles[i])
            self.power_history.set_line_marker(i, markers[i])
            self.power_history.set_line_alpha(i, alphas[i])

        self._power_history_win = sip.wrapinstance(self.power_history.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._power_history_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_3.setColumnStretch(c, 1)
        self._phase_fix_deg_range = qtgui.Range(0, 270, 90, 0, 200)
        self._phase_fix_deg_win = qtgui.RangeWidget(self._phase_fix_deg_range, self.set_phase_fix_deg, "Phase-ambiguity rotation (deg)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._phase_fix_deg_win)
        self.phase_fix = blocks.multiply_const_cc(complex(math.cos(math.radians(phase_fix_deg)),math.sin(math.radians(phase_fix_deg))))
        self.peak_display = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.peak_display.set_update_time(0.10)
        self.peak_display.set_title('TX sampled peak (must stay below 0 dBFS)')

        labels = ['TX sampled peak (must stay below 0 dBFS)', '', '', '', '',
            '', '', '', '', '']
        units = ['dBFS', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.peak_display.set_min(i, -200)
            self.peak_display.set_max(i, 100)
            self.peak_display.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.peak_display.set_label(i, "Data {0}".format(i))
            else:
                self.peak_display.set_label(i, labels[i])
            self.peak_display.set_unit(i, units[i])
            self.peak_display.set_factor(i, factor[i])

        self.peak_display.enable_autoscale(False)
        self._peak_display_win = sip.wrapinstance(self.peak_display.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._peak_display_win, 4, 0, 1, 1)
        for r in range(4, 5):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_3.setColumnStretch(c, 1)
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


        labels = ['RX Q | raw N210 RX output', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
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


        labels = ['RX I | raw N210 RX output', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
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
        self.envelope_plot = qtgui.time_sink_f(
            512, #size
            samp_rate, #samp_rate
            'TX sampled power envelope (dBFS)', #name
            1, #number of inputs
            None # parent
        )
        self.envelope_plot.set_update_time(0.10)
        self.envelope_plot.set_y_axis(-1, 1)

        self.envelope_plot.set_y_label('Amplitude', "")

        self.envelope_plot.enable_tags(True)
        self.envelope_plot.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.envelope_plot.enable_autoscale(True)
        self.envelope_plot.enable_grid(False)
        self.envelope_plot.enable_axis_labels(True)
        self.envelope_plot.enable_control_panel(False)
        self.envelope_plot.enable_stem_plot(False)


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
                self.envelope_plot.set_line_label(i, "Data {0}".format(i))
            else:
                self.envelope_plot.set_line_label(i, labels[i])
            self.envelope_plot.set_line_width(i, widths[i])
            self.envelope_plot.set_line_color(i, colors[i])
            self.envelope_plot.set_line_style(i, styles[i])
            self.envelope_plot.set_line_marker(i, markers[i])
            self.envelope_plot.set_line_alpha(i, alphas[i])

        self._envelope_plot_win = sip.wrapinstance(self.envelope_plot.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._envelope_plot_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(1, 2):
            self.views_grid_layout_3.setColumnStretch(c, 1)
        self.envelope_floor = blocks.add_const_ff((1e-30))
        self.envelope_dbm = blocks.nlog10_ff(10, 1, 0)
        self.ebno_display = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.ebno_display.set_update_time(0.10)
        self.ebno_display.set_title('Eb/N0 estimate from MER')

        labels = ['Eb/N0 estimate from MER', '', '', '', '',
            '', '', '', '', '']
        units = ['dB', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.ebno_display.set_min(i, -100)
            self.ebno_display.set_max(i, 100)
            self.ebno_display.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.ebno_display.set_label(i, "Data {0}".format(i))
            else:
                self.ebno_display.set_label(i, labels[i])
            self.ebno_display.set_unit(i, units[i])
            self.ebno_display.set_factor(i, factor[i])

        self.ebno_display.enable_autoscale(False)
        self._ebno_display_win = sip.wrapinstance(self.ebno_display.qwidget(), Qt.QWidget)
        self.views_grid_layout_3.addWidget(self._ebno_display_win, 5, 0, 1, 1)
        for r in range(5, 6):
            self.views_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.views_grid_layout_3.setColumnStretch(c, 1)
        self.diff_decoder = digital.diff_decoder_bb(16, digital.DIFF_DIFFERENTIAL)
        self.delay = blocks.delay(gr.sizeof_char*1, data_period_bits)
        self.decoder = digital.constellation_decoder_cb(const)
        self.clock_sync = digital.pfb_clock_sync_ccf(sps, timing_bw, rrc_taps, nfilts, 16, 1.5, 1)
        self.carrier_sync = digital.costas_loop_cc(carrier_loop_bw, 4, False)
        self.ber_scale = blocks.multiply_const_ff((0.5/ber_window))
        self.ber_history = qtgui.time_sink_f(
            128, #size
            bit_rate/ber_window, #samp_rate
            'Self-referenced BER estimate per window', #name
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
        self.ber_display.set_title('BER estimate | RX vs RX one data period earlier, /2')

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
        self.connect((self.carrier_sync, 0), (self.rx_scale, 0))
        self.connect((self.clock_sync, 0), (self.carrier_sync, 0))
        self.connect((self.clock_sync, 1), (self.timing_error, 0))
        self.connect((self.clock_sync, 3), (self.unused_timing_states, 1))
        self.connect((self.clock_sync, 2), (self.unused_timing_states, 0))
        self.connect((self.decoder, 0), (self.diff_decoder, 0))
        self.connect((self.delay, 0), (self.skip_tx, 0))
        self.connect((self.diff_decoder, 0), (self.unpack_rx, 0))
        self.connect((self.envelope_dbm, 0), (self.envelope_plot, 0))
        self.connect((self.envelope_floor, 0), (self.envelope_dbm, 0))
        self.connect((self.eq_tap_decimator, 0), (self.eq_tap_magnitudes, 0))
        self.connect((self.eq_tap_magnitudes, 0), (self.eq_tap_plot, 0))
        self.connect((self.equalizer, 1), (self.eq_tap_decimator, 0))
        self.connect((self.equalizer, 0), (self.phase_fix, 0))
        self.connect((self.errors_float, 0), (self.integrate, 0))
        self.connect((self.evm, 0), (self.eq_error_trace, 0))
        self.connect((self.evm, 0), (self.evm_rms, 0))
        self.connect((self.evm_circles, 0), (self.constellation, 2))
        self.connect((self.evm_circles, 0), (self.tx_constellation, 2))
        self.connect((self.evm_rms, 0), (self.eq_evm_history, 0))
        self.connect((self.evm_rms, 0), (self.evm_display, 0))
        self.connect((self.evm_rms, 0), (self.evm_history, 0))
        self.connect((self.evm_rms, 0), (self.rx_ebno, 0))
        self.connect((self.evm_rms, 0), (self.rx_snr, 0))
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
        self.connect((self.phase_fix, 0), (self.after_eye_reconstruction, 0))
        self.connect((self.phase_fix, 0), (self.constellation, 0))
        self.connect((self.phase_fix, 0), (self.decoder, 0))
        self.connect((self.phase_fix, 0), (self.evm, 0))
        self.connect((self.random_bytes, 0), (self.modulator, 0))
        self.connect((self.random_bytes, 0), (self.tx_symbol_chunks, 0))
        self.connect((self.rx_dbm, 0), (self.power_history, 1))
        self.connect((self.rx_dbm, 0), (self.rx_power_display, 0))
        self.connect((self.rx_ebno, 0), (self.ebno_display, 0))
        self.connect((self.rx_level, 0), (self.clock_sync, 0))
        self.connect((self.rx_milliwatts, 0), (self.rx_power_sum, 0))
        self.connect((self.rx_power_mean, 0), (self.rx_dbm, 0))
        self.connect((self.rx_power_sum, 0), (self.rx_power_mean, 0))
        self.connect((self.rx_scale, 0), (self.before_eq_constellation, 0))
        self.connect((self.rx_scale, 0), (self.equalizer, 0))
        self.connect((self.rx_scale, 0), (self.middle_eye_reconstruction, 0))
        self.connect((self.rx_snr, 0), (self.power_reference_chart, 0))
        self.connect((self.rx_snr, 0), (self.snr_display, 0))
        self.connect((self.skip_rx, 0), (self.xor, 0))
        self.connect((self.skip_tx, 0), (self.xor, 1))
        self.connect((self.tx_dbm, 0), (self.power_history, 0))
        self.connect((self.tx_dbm, 0), (self.tx_power_display, 0))
        self.connect((self.tx_eye_i, 0), (self.tx_eye_i_eye, 0))
        self.connect((self.tx_eye_q, 0), (self.tx_eye_q_eye, 0))
        self.connect((self.tx_milliwatts, 0), (self.envelope_floor, 0))
        self.connect((self.tx_milliwatts, 0), (self.tx_peak_vectors, 0))
        self.connect((self.tx_milliwatts, 0), (self.tx_power_sum, 0))
        self.connect((self.tx_peak_dbm, 0), (self.peak_display, 0))
        self.connect((self.tx_peak_mw, 0), (self.tx_peak_dbm, 0))
        self.connect((self.tx_peak_vectors, 0), (self.tx_peak_mw, 0))
        self.connect((self.tx_power, 0), (self.spectrum, 1))
        self.connect((self.tx_power, 0), (self.tx_eye_i, 0))
        self.connect((self.tx_power, 0), (self.tx_eye_q, 0))
        self.connect((self.tx_power, 0), (self.tx_milliwatts, 0))
        self.connect((self.tx_power, 0), (self.tx_waveform, 0))
        self.connect((self.tx_power, 0), (self.usrp_tx, 0))
        self.connect((self.tx_power, 0), (self.waveform, 1))
        self.connect((self.tx_power_mean, 0), (self.tx_dbm, 0))
        self.connect((self.tx_power_sum, 0), (self.tx_power_mean, 0))
        self.connect((self.tx_symbol_chunks, 0), (self.tx_symbol_diff, 0))
        self.connect((self.tx_symbol_diff, 0), (self.tx_symbols, 0))
        self.connect((self.tx_symbols, 0), (self.tx_constellation, 0))
        self.connect((self.unpack_rx, 0), (self.delay, 0))
        self.connect((self.unpack_rx, 0), (self.skip_rx, 0))
        self.connect((self.usrp_rx, 0), (self.eye_i, 0))
        self.connect((self.usrp_rx, 0), (self.eye_q, 0))
        self.connect((self.usrp_rx, 0), (self.rx_level, 0))
        self.connect((self.usrp_rx, 0), (self.rx_milliwatts, 0))
        self.connect((self.usrp_rx, 0), (self.spectrum, 0))
        self.connect((self.usrp_rx, 0), (self.spectrum_budget, 0))
        self.connect((self.usrp_rx, 0), (self.waveform, 0))
        self.connect((self.xor, 0), (self.errors_float, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "n210_16qam")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_eq_step(self):
        return self.eq_step

    def set_eq_step(self, eq_step):
        self.eq_step = eq_step

    def get_eq_taps(self):
        return self.eq_taps

    def set_eq_taps(self, eq_taps):
        self.eq_taps = eq_taps
        self.set_eq_delay_symbols((self.eq_taps-1)//2)

    def get_evm_guide_percent(self):
        return self.evm_guide_percent

    def set_evm_guide_percent(self, evm_guide_percent):
        self.evm_guide_percent = evm_guide_percent
        self.evm_circles.set_data([p+self.symbol_rms*self.evm_guide_percent/100*complex(math.cos(t),math.sin(t)) for p in const.points() for t in numpy.linspace(0,2*math.pi,64,endpoint=False)], [])

    def get_symbol_rate(self):
        return self.symbol_rate

    def set_symbol_rate(self, symbol_rate):
        self.symbol_rate = symbol_rate
        self.set_bit_rate(self.symbol_rate*self.k)
        self.set_rrc_bandwidth(self.symbol_rate*(1+self.alpha))
        self.set_samp_rate(self.symbol_rate*self.sps)
        self.eq_error_trace.set_samp_rate(self.symbol_rate)
        self.eq_evm_history.set_samp_rate(self.symbol_rate)
        self.evm_history.set_samp_rate(self.symbol_rate)
        self.timing_error.set_samp_rate(self.symbol_rate)

    def get_tx_level_dbfs(self):
        return self.tx_level_dbfs

    def set_tx_level_dbfs(self, tx_level_dbfs):
        self.tx_level_dbfs = tx_level_dbfs
        self.set_tx_amplitude(10**(self.tx_level_dbfs/20.0))

    def get_usrp_address(self):
        return self.usrp_address

    def set_usrp_address(self, usrp_address):
        self.usrp_address = usrp_address

    def get_center_freq_hz(self):
        return self.center_freq_hz

    def set_center_freq_hz(self, center_freq_hz):
        self.center_freq_hz = center_freq_hz
        self.usrp_tx.set_center_freq(self.center_freq_hz, 0)
        self.usrp_rx.set_center_freq(self.center_freq_hz, 0)

    def get_rx_gain_db(self):
        return self.rx_gain_db

    def set_rx_gain_db(self, rx_gain_db):
        self.rx_gain_db = rx_gain_db
        self.rx_level.set_k(10**(self.rx_gain_db/20.0))

    def get_const(self):
        return self.const

    def set_const(self, const):
        self.const = const
        self.decoder.set_constellation(self.const)

    def get_symbol_rms(self):
        return self.symbol_rms

    def set_symbol_rms(self, symbol_rms):
        self.symbol_rms = symbol_rms
        self.evm_circles.set_data([p+self.symbol_rms*self.evm_guide_percent/100*complex(math.cos(t),math.sin(t)) for p in const.points() for t in numpy.linspace(0,2*math.pi,64,endpoint=False)], [])
        self.rx_scale.set_k(self.symbol_rms)
        self.tx_power.set_k(self.tx_amplitude/self.symbol_rms)

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_eye_synthesis_taps(firdes.root_raised_cosine(self.sps,self.sps,1.0,self.alpha,11*self.sps))
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.alpha, 11*self.sps*self.nfilts))
        self.set_samp_rate(self.symbol_rate*self.sps)
        self.after_i_eye.set_samp_per_symbol(self.sps)
        self.after_q_eye.set_samp_per_symbol(self.sps)
        self.eye.set_samp_per_symbol(self.sps)
        self.eye_quadrature.set_samp_per_symbol(self.sps)
        self.middle_i_eye.set_samp_per_symbol(self.sps)
        self.middle_q_eye.set_samp_per_symbol(self.sps)
        self.tx_eye_i_eye.set_samp_per_symbol(self.sps)
        self.tx_eye_q_eye.set_samp_per_symbol(self.sps)

    def get_nfilts(self):
        return self.nfilts

    def set_nfilts(self, nfilts):
        self.nfilts = nfilts
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.alpha, 11*self.sps*self.nfilts))

    def get_k(self):
        return self.k

    def set_k(self, k):
        self.k = k
        self.set_bit_rate(self.symbol_rate*self.k)

    def get_alpha(self):
        return self.alpha

    def set_alpha(self, alpha):
        self.alpha = alpha
        self.set_eye_synthesis_taps(firdes.root_raised_cosine(self.sps,self.sps,1.0,self.alpha,11*self.sps))
        self.set_rrc_bandwidth(self.symbol_rate*(1+self.alpha))
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.alpha, 11*self.sps*self.nfilts))

    def get_warmup_bits(self):
        return self.warmup_bits

    def set_warmup_bits(self, warmup_bits):
        self.warmup_bits = warmup_bits

    def get_tx_gain_norm(self):
        return self.tx_gain_norm

    def set_tx_gain_norm(self, tx_gain_norm):
        self.tx_gain_norm = tx_gain_norm
        self.usrp_tx.set_normalized_gain(self.tx_gain_norm, 0)

    def get_tx_amplitude(self):
        return self.tx_amplitude

    def set_tx_amplitude(self, tx_amplitude):
        self.tx_amplitude = tx_amplitude
        self.tx_power.set_k(self.tx_amplitude/self.symbol_rms)

    def get_timing_bw(self):
        return self.timing_bw

    def set_timing_bw(self, timing_bw):
        self.timing_bw = timing_bw
        self.clock_sync.set_loop_bandwidth(self.timing_bw)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.after_i_eye.set_samp_rate(self.samp_rate)
        self.after_q_eye.set_samp_rate(self.samp_rate)
        self.envelope_plot.set_samp_rate(self.samp_rate)
        self.eye.set_samp_rate(self.samp_rate)
        self.eye_quadrature.set_samp_rate(self.samp_rate)
        self.middle_i_eye.set_samp_rate(self.samp_rate)
        self.middle_q_eye.set_samp_rate(self.samp_rate)
        self.power_history.set_samp_rate(self.samp_rate/4096)
        self.power_reference_chart.set_samp_rate(self.samp_rate/4096)
        self.spectrum.set_frequency_range(0, self.samp_rate)
        self.spectrum_budget.set_frequency_range(0, self.samp_rate)
        self.tx_eye_i_eye.set_samp_rate(self.samp_rate)
        self.tx_eye_q_eye.set_samp_rate(self.samp_rate)
        self.tx_waveform.set_samp_rate(self.samp_rate)
        self.waveform.set_samp_rate(self.samp_rate)
        self.usrp_tx.set_samp_rate(self.samp_rate)
        self.usrp_rx.set_samp_rate(self.samp_rate)

    def get_rx_gain_norm(self):
        return self.rx_gain_norm

    def set_rx_gain_norm(self, rx_gain_norm):
        self.rx_gain_norm = rx_gain_norm
        self.usrp_rx.set_normalized_gain(self.rx_gain_norm, 0)

    def get_rrc_taps(self):
        return self.rrc_taps

    def set_rrc_taps(self, rrc_taps):
        self.rrc_taps = rrc_taps
        self.clock_sync.update_taps(self.rrc_taps)

    def get_rrc_bandwidth(self):
        return self.rrc_bandwidth

    def set_rrc_bandwidth(self, rrc_bandwidth):
        self.rrc_bandwidth = rrc_bandwidth

    def get_phase_fix_deg(self):
        return self.phase_fix_deg

    def set_phase_fix_deg(self, phase_fix_deg):
        self.phase_fix_deg = phase_fix_deg
        self.phase_fix.set_k(complex(math.cos(math.radians(self.phase_fix_deg)),math.sin(math.radians(self.phase_fix_deg))))

    def get_eye_synthesis_taps(self):
        return self.eye_synthesis_taps

    def set_eye_synthesis_taps(self, eye_synthesis_taps):
        self.eye_synthesis_taps = eye_synthesis_taps
        self.after_eye_reconstruction.set_taps(self.eye_synthesis_taps)
        self.middle_eye_reconstruction.set_taps(self.eye_synthesis_taps)

    def get_eq_delay_symbols(self):
        return self.eq_delay_symbols

    def set_eq_delay_symbols(self, eq_delay_symbols):
        self.eq_delay_symbols = eq_delay_symbols

    def get_eq_algorithm(self):
        return self.eq_algorithm

    def set_eq_algorithm(self, eq_algorithm):
        self.eq_algorithm = eq_algorithm

    def get_data_period_bits(self):
        return self.data_period_bits

    def set_data_period_bits(self, data_period_bits):
        self.data_period_bits = data_period_bits
        self.delay.set_dly(int(self.data_period_bits))

    def get_carrier_loop_bw(self):
        return self.carrier_loop_bw

    def set_carrier_loop_bw(self, carrier_loop_bw):
        self.carrier_loop_bw = carrier_loop_bw
        self.carrier_sync.set_loop_bandwidth(self.carrier_loop_bw)

    def get_bit_rate(self):
        return self.bit_rate

    def set_bit_rate(self, bit_rate):
        self.bit_rate = bit_rate
        self.ber_history.set_samp_rate(self.bit_rate/self.ber_window)

    def get_ber_window(self):
        return self.ber_window

    def set_ber_window(self, ber_window):
        self.ber_window = ber_window
        self.ber_history.set_samp_rate(self.bit_rate/self.ber_window)
        self.ber_scale.set_k((0.5/self.ber_window))



def argument_parser():
    parser = ArgumentParser()
    parser.add_argument(
        "--eq-step", dest="eq_step", type=eng_float, default=eng_notation.num_to_str(float(0.01)),
        help="Set NLMS adaptation step [default=%(default)r]")
    parser.add_argument(
        "--eq-taps", dest="eq_taps", type=intx, default=11,
        help="Set Adaptive equalizer taps [default=%(default)r]")
    parser.add_argument(
        "--evm-guide-percent", dest="evm_guide_percent", type=eng_float, default=eng_notation.num_to_str(float(5)),
        help="Set Constellation guide radius (% RMS) [default=%(default)r]")
    parser.add_argument(
        "--symbol-rate", dest="symbol_rate", type=eng_float, default=eng_notation.num_to_str(float(1e6)),
        help="Set Symbol rate (symbols/s) [default=%(default)r]")
    parser.add_argument(
        "--tx-level-dbfs", dest="tx_level_dbfs", type=eng_float, default=eng_notation.num_to_str(float((-15))),
        help="Set TX digital RMS level (dBFS, keep peaks < 0) [default=%(default)r]")
    parser.add_argument(
        "--usrp-address", dest="usrp_address", type=str, default='addr=192.168.10.2',
        help="Set N210 device address [default=%(default)r]")
    parser.add_argument(
        "--center-freq-hz", dest="center_freq_hz", type=eng_float, default=eng_notation.num_to_str(float(915e6)),
        help="Set RF center frequency (Hz) [default=%(default)r]")
    parser.add_argument(
        "--rx-gain-db", dest="rx_gain_db", type=eng_float, default=eng_notation.num_to_str(float(75)),
        help="Set Fixed RX digital gain (dB) = -(RX ADC dBFS) [default=%(default)r]")
    return parser


def main(top_block_cls=n210_16qam, options=None):
    if options is None:
        options = argument_parser().parse_args()

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(eq_step=options.eq_step, eq_taps=options.eq_taps, evm_guide_percent=options.evm_guide_percent, symbol_rate=options.symbol_rate, tx_level_dbfs=options.tx_level_dbfs, usrp_address=options.usrp_address, center_freq_hz=options.center_freq_hz, rx_gain_db=options.rx_gain_db)
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
