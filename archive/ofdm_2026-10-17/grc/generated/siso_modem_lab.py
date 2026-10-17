#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: SISO modem: bits -> modulation -> channel -> decisions -> BER/EVM
# Author: Antenna benchmark project
# Description: Complete uncoded symbol-rate SISO chain, ideal scalar receiver, live BER/EVM and Qt plots.
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
import os
import sys
import logging as log

def get_state_directory() -> str:
    oldpath = os.path.expanduser("~/.grc_gnuradio")
    try:
        from gnuradio.gr import paths
        newpath = paths.persistent()
        if os.path.exists(newpath):
            return newpath
        if os.path.exists(oldpath):
            log.warning(f"Found persistent state path '{newpath}', but file does not exist. " +
                     f"Old default persistent state path '{oldpath}' exists; using that. " +
                     "Please consider moving state to new location.")
            return oldpath
        # Default to the correct path if both are configured.
        # neither old, nor new path exist: create new path, return that
        os.makedirs(newpath, exist_ok=True)
        return newpath
    except (ImportError, NameError):
        log.warning("Could not retrieve GNU Radio persistent state directory from GNU Radio. " +
                 "Trying defaults.")
        xdgstate = os.getenv("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
        xdgcand = os.path.join(xdgstate, "gnuradio")
        if os.path.exists(xdgcand):
            return xdgcand
        if os.path.exists(oldpath):
            log.warning(f"Using legacy state path '{oldpath}'. Please consider moving state " +
                     f"files to '{xdgcand}'.")
            return oldpath
        # neither old, nor new path exist: create new path, return that
        os.makedirs(xdgcand, exist_ok=True)
        return xdgcand

sys.path.append(os.environ.get('GRC_HIER_PATH', get_state_directory()))

from bench_scalar_channel import bench_scalar_channel  # grc-generated hier_block
from bench_symbol_demapper import bench_symbol_demapper  # grc-generated hier_block
from bench_symbol_mapper import bench_symbol_mapper  # grc-generated hier_block
from gnuradio import blocks
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import math
import numpy as np
from antenna_bench.paths import ROOT
from antenna_bench.live import test_bits, wlan_reference, burst_waveform, reference_symbols, parse_taps
from antenna_bench.wlan import wlan_constellation
from gnuradio import digital
import sip
import siso_modem_lab_ber_meter as ber_meter  # embedded python block
import siso_modem_lab_evm_meter as evm_meter  # embedded python block
import threading



class siso_modem_lab(gr.top_block, Qt.QWidget):

    def __init__(self, order=16, ebno_db=20, path_loss_db=0, symbol_count=0, pace=200000, noise_seed=20261017):
        gr.top_block.__init__(self, "SISO modem: bits -> modulation -> channel -> decisions -> BER/EVM", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("SISO modem: bits -> modulation -> channel -> decisions -> BER/EVM")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "siso_modem_lab")

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
        self.order = order
        self.ebno_db = ebno_db
        self.path_loss_db = path_loss_db
        self.symbol_count = symbol_count
        self.pace = pace
        self.noise_seed = noise_seed

        ##################################################
        # Variables
        ##################################################
        self.k = k = int(math.log2(order))
        self.noise_voltage = noise_voltage = math.sqrt(1/(k*10**(ebno_db/10)))
        self.channel_gain = channel_gain = 10**(-path_loss_db/20)

        ##################################################
        # Blocks
        ##################################################

        self.views = Qt.QTabWidget()
        self.views_widget_0 = Qt.QWidget()
        self.views_layout_0 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.views_widget_0)
        self.views_grid_layout_0 = Qt.QGridLayout()
        self.views_layout_0.addLayout(self.views_grid_layout_0)
        self.views.addTab(self.views_widget_0, 'Metrics and constellation')
        self.views_widget_1 = Qt.QWidget()
        self.views_layout_1 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.views_widget_1)
        self.views_grid_layout_1 = Qt.QGridLayout()
        self.views_layout_1.addLayout(self.views_grid_layout_1)
        self.views.addTab(self.views_widget_1, 'TX waveform: spectrum / waterfall / time')
        self.views_widget_2 = Qt.QWidget()
        self.views_layout_2 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.views_widget_2)
        self.views_grid_layout_2 = Qt.QGridLayout()
        self.views_layout_2.addLayout(self.views_grid_layout_2)
        self.views.addTab(self.views_widget_2, 'RX waveform: spectrum / waterfall / time')
        self.top_layout.addWidget(self.views)
        self.tx_scope = qtgui.sink_c(
            1024, #fftsize
            window.WIN_HANN, #wintype
            0, #fc
            pace, #bw
            'TX waveform | complex baseband; relative FFT level', #name
            True, #plotfreq
            True, #plotwaterfall
            True, #plottime
            False, #plotconst
            None # parent
        )
        self.tx_scope.set_update_time(1.0/5)
        self._tx_scope_win = sip.wrapinstance(self.tx_scope.qwidget(), Qt.QWidget)

        self.tx_scope.enable_rf_freq(False)

        self.views_grid_layout_1.addWidget(self._tx_scope_win, 0, 0, 1, 2)
        for r in range(0, 1):
            self.views_grid_layout_1.setRowStretch(r, 1)
        for c in range(0, 2):
            self.views_grid_layout_1.setColumnStretch(c, 1)
        self.rx_scope = qtgui.sink_c(
            1024, #fftsize
            window.WIN_HANN, #wintype
            0, #fc
            pace, #bw
            'RX waveform | before equalization; relative FFT level', #name
            True, #plotfreq
            True, #plotwaterfall
            True, #plottime
            False, #plotconst
            None # parent
        )
        self.rx_scope.set_update_time(1.0/5)
        self._rx_scope_win = sip.wrapinstance(self.rx_scope.qwidget(), Qt.QWidget)

        self.rx_scope.enable_rf_freq(False)

        self.views_grid_layout_2.addWidget(self._rx_scope_win, 0, 0, 1, 2)
        for r in range(0, 1):
            self.views_grid_layout_2.setRowStretch(r, 1)
        for c in range(0, 2):
            self.views_grid_layout_2.setColumnStretch(c, 1)
        self.rx_bits = bench_symbol_demapper(
            order=order,
        )
        self.pace_tx = blocks.throttle( gr.sizeof_gr_complex*1, pace, True, 0 if "auto" == "auto" else max( int(float(0.1) * pace) if "auto" == "time" else int(0.1), 1) )
        self.mapper = bench_symbol_mapper(
            order=order,
        )
        self.known_bits = blocks.vector_source_b(test_bits(order).tolist(), True, 1, [])
        self.finite_bits = blocks.head(gr.sizeof_char*1, (symbol_count*k if symbol_count>0 else 2**60))
        self.evm_meter = evm_meter.blk(report_path=str(ROOT / 'results/live/siso_modem_evm.json'), run_config=dict(model='SISO symbol-rate',order=order,ebno_db=ebno_db,path_loss_db=path_loss_db,noise_seed=noise_seed))
        self.evm_display = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.evm_display.set_update_time(0.10)
        self.evm_display.set_title('Pooled RMS EVM')

        labels = ['Pooled RMS EVM', '', '', '', '',
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
        self.equalize = blocks.multiply_const_cc(1/channel_gain)
        self.constellation = qtgui.const_sink_c(
            1024, #size
            'SISO equalized symbols and known reference', #name
            2, #number of inputs
            None # parent
        )
        self.constellation.set_update_time(0.10)
        self.constellation.set_y_axis((-2.0), 2.0)
        self.constellation.set_x_axis((-2.0), 2.0)
        self.constellation.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.constellation.enable_autoscale(False)
        self.constellation.enable_grid(True)
        self.constellation.enable_axis_labels(True)


        labels = ['RX equalized DATA', 'TX reference DATA', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 8, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [0.5, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(2):
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
        self.views_grid_layout_0.addWidget(self._constellation_win, 1, 0, 1, 2)
        for r in range(1, 2):
            self.views_grid_layout_0.setRowStretch(r, 1)
        for c in range(0, 2):
            self.views_grid_layout_0.setColumnStretch(c, 1)
        self.channel_output = bench_scalar_channel(
            channel_gain=channel_gain,
            noise_voltage=noise_voltage,
            noise_seed=noise_seed,
        )
        self.ber_meter = ber_meter.blk(report_path=str(ROOT / 'results/live/siso_modem_ber.json'), run_config=dict(model='SISO symbol-rate',order=order,ebno_db=ebno_db,path_loss_db=path_loss_db,noise_seed=noise_seed))
        self.ber_display = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.ber_display.set_update_time(0.10)
        self.ber_display.set_title('Cumulative pre-FEC BER')

        labels = ['Cumulative pre-FEC BER', '', '', '', '',
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


        ##################################################
        # Connections
        ##################################################
        self.connect((self.ber_meter, 0), (self.ber_display, 0))
        self.connect((self.channel_output, 0), (self.equalize, 0))
        self.connect((self.channel_output, 0), (self.rx_scope, 0))
        self.connect((self.equalize, 0), (self.constellation, 0))
        self.connect((self.equalize, 0), (self.evm_meter, 1))
        self.connect((self.equalize, 0), (self.rx_bits, 0))
        self.connect((self.evm_meter, 0), (self.evm_display, 0))
        self.connect((self.finite_bits, 0), (self.ber_meter, 0))
        self.connect((self.finite_bits, 0), (self.mapper, 0))
        self.connect((self.known_bits, 0), (self.finite_bits, 0))
        self.connect((self.mapper, 0), (self.constellation, 1))
        self.connect((self.mapper, 0), (self.evm_meter, 0))
        self.connect((self.mapper, 0), (self.pace_tx, 0))
        self.connect((self.pace_tx, 0), (self.channel_output, 0))
        self.connect((self.pace_tx, 0), (self.tx_scope, 0))
        self.connect((self.rx_bits, 0), (self.ber_meter, 1))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "siso_modem_lab")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_order(self):
        return self.order

    def set_order(self, order):
        self.order = order
        self.set_k(int(math.log2(self.order)))
        self.known_bits.set_data(test_bits(self.order).tolist(), [])
        self.mapper.set_order(self.order)
        self.rx_bits.set_order(self.order)

    def get_ebno_db(self):
        return self.ebno_db

    def set_ebno_db(self, ebno_db):
        self.ebno_db = ebno_db
        self.set_noise_voltage(math.sqrt(1/(self.k*10**(self.ebno_db/10))))

    def get_path_loss_db(self):
        return self.path_loss_db

    def set_path_loss_db(self, path_loss_db):
        self.path_loss_db = path_loss_db
        self.set_channel_gain(10**(-self.path_loss_db/20))

    def get_symbol_count(self):
        return self.symbol_count

    def set_symbol_count(self, symbol_count):
        self.symbol_count = symbol_count
        self.finite_bits.set_length((self.symbol_count*self.k if self.symbol_count>0 else 2**60))

    def get_pace(self):
        return self.pace

    def set_pace(self, pace):
        self.pace = pace
        self.pace_tx.set_sample_rate(self.pace)
        self.tx_scope.set_frequency_range(0, self.pace)
        self.rx_scope.set_frequency_range(0, self.pace)

    def get_noise_seed(self):
        return self.noise_seed

    def set_noise_seed(self, noise_seed):
        self.noise_seed = noise_seed
        self.channel_output.set_noise_seed(self.noise_seed)

    def get_k(self):
        return self.k

    def set_k(self, k):
        self.k = k
        self.set_noise_voltage(math.sqrt(1/(self.k*10**(self.ebno_db/10))))
        self.finite_bits.set_length((self.symbol_count*self.k if self.symbol_count>0 else 2**60))

    def get_noise_voltage(self):
        return self.noise_voltage

    def set_noise_voltage(self, noise_voltage):
        self.noise_voltage = noise_voltage
        self.channel_output.set_noise_voltage(self.noise_voltage)

    def get_channel_gain(self):
        return self.channel_gain

    def set_channel_gain(self, channel_gain):
        self.channel_gain = channel_gain
        self.equalize.set_k(1/self.channel_gain)
        self.channel_output.set_channel_gain(self.channel_gain)



def argument_parser():
    description = 'Complete uncoded symbol-rate SISO chain, ideal scalar receiver, live BER/EVM and Qt plots.'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--order", dest="order", type=intx, default=16,
        help="Set Constellation order M [default=%(default)r]")
    parser.add_argument(
        "--ebno-db", dest="ebno_db", type=eng_float, default=eng_notation.num_to_str(float(20)),
        help="Set TX-reference uncoded Eb/N0 (dB) [default=%(default)r]")
    parser.add_argument(
        "--path-loss-db", dest="path_loss_db", type=eng_float, default=eng_notation.num_to_str(float(0)),
        help="Set SISO power loss (dB) [default=%(default)r]")
    parser.add_argument(
        "--symbol-count", dest="symbol_count", type=intx, default=0,
        help="Set Number of symbols [default=%(default)r]")
    parser.add_argument(
        "--pace", dest="pace", type=eng_float, default=eng_notation.num_to_str(float(200000)),
        help="Set Playback samples per wall-clock second [default=%(default)r]")
    parser.add_argument(
        "--noise-seed", dest="noise_seed", type=intx, default=20261017,
        help="Set noise_seed [default=%(default)r]")
    return parser


def main(top_block_cls=siso_modem_lab, options=None):
    if options is None:
        options = argument_parser().parse_args()

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(order=options.order, ebno_db=options.ebno_db, path_loss_db=options.path_loss_db, symbol_count=options.symbol_count, pace=options.pace, noise_seed=options.noise_seed)

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
