#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: SISO Wi-Fi PHY: waveform -> FIR/CFO/AWGN -> trained RX -> BER/EVM
# Author: Antenna benchmark project
# Description: Complete known-burst SISO PHY with fixed active TX power and live pre-FEC BER/EVM. No autonomous acquisition or MAC.
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import analog
from gnuradio import blocks
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
import math
import numpy as np
from antenna_bench.paths import ROOT
from antenna_bench.live import test_bits, wlan_reference, burst_waveform, reference_symbols, parse_taps
from antenna_bench.wlan import wlan_constellation
import sip
import siso_wlan_lab_ber_meter as ber_meter  # embedded python block
import siso_wlan_lab_burst_receiver as burst_receiver  # embedded python block
import siso_wlan_lab_evm_meter as evm_meter  # embedded python block
import threading



class siso_wlan_lab(gr.top_block, Qt.QWidget):

    def __init__(self, rate_index=2, snr_db=25, path_loss_db=0, packet_count=0, pace=1000000, cfo_hz=0, channel_taps='1+0j', correct_cfo=1, pilot_tracking=1):
        gr.top_block.__init__(self, "SISO Wi-Fi PHY: waveform -> FIR/CFO/AWGN -> trained RX -> BER/EVM", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("SISO Wi-Fi PHY: waveform -> FIR/CFO/AWGN -> trained RX -> BER/EVM")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "siso_wlan_lab")

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
        self.rate_index = rate_index
        self.snr_db = snr_db
        self.path_loss_db = path_loss_db
        self.packet_count = packet_count
        self.pace = pace
        self.cfo_hz = cfo_hz
        self.channel_taps = channel_taps
        self.correct_cfo = correct_cfo
        self.pilot_tracking = pilot_tracking

        ##################################################
        # Variables
        ##################################################
        self.reference = reference = wlan_reference(rate_index)
        self.order = order = int(reference['order'])
        self.sample_rate = sample_rate = 20e6
        self.noise_voltage = noise_voltage = 10**(-snr_db/20)
        self.k = k = int(math.log2(order))
        self.constellation_object = constellation_object = digital.constellation_calcdist(wlan_constellation(order).tolist(),list(range(order)),1,1,digital.constellation.NO_NORMALIZATION).base()
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
        self.tx_waveform = blocks.vector_source_c(burst_waveform(rate_index).tolist(), True, 1, [])
        self.tx_scope = qtgui.sink_c(
            1024, #fftsize
            window.WIN_HANN, #wintype
            0, #fc
            sample_rate, #bw
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
        self.tx_reference = blocks.vector_source_c(reference_symbols(rate_index).tolist(), True, 1, [])
        self.tx_decisions = digital.constellation_decoder_cb(constellation_object)
        self.tx_bits = blocks.unpack_k_bits_bb(k)
        self.siso_fir = filter.fir_filter_ccc(1, [channel_gain*t for t in parse_taps(channel_taps)])
        self.siso_fir.declare_sample_delay(0)
        self.rx_scope = qtgui.sink_c(
            1024, #fftsize
            window.WIN_HANN, #wintype
            0, #fc
            sample_rate, #bw
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
        self.rx_bits = blocks.unpack_k_bits_bb(k)
        self.pace_tx = blocks.throttle( gr.sizeof_gr_complex*1, pace, True, 0 if "auto" == "auto" else max( int(float(0.1) * pace) if "auto" == "time" else int(0.1), 1) )
        self.finite_tx = blocks.head(gr.sizeof_gr_complex*1, (packet_count*len(burst_waveform(rate_index)) if packet_count>0 else 2**60))
        self.finite_reference = blocks.head(gr.sizeof_gr_complex*1, (packet_count*reference_symbols(rate_index).size if packet_count>0 else 2**60))
        self.extract_bursts = blocks.keep_m_in_n(gr.sizeof_gr_complex, reference['tx_packet'].size, len(burst_waveform(rate_index)), 0)
        self.evm_meter = evm_meter.blk(report_path=str(ROOT / 'results/live/siso_wlan_evm.json'), run_config=dict(model='SISO known-burst Wi-Fi',rate_index=rate_index,tx_reference_snr_db=snr_db,path_loss_db=path_loss_db,cfo_hz=cfo_hz,channel_taps=channel_taps,correct_cfo=correct_cfo,pilot_tracking=pilot_tracking))
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
        self.demap = digital.constellation_decoder_cb(constellation_object)
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
        self.channel_output = blocks.add_vcc(1)
        self.carrier_offset = blocks.rotator_cc((2*math.pi*cfo_hz/sample_rate), False)
        self.burst_receiver = burst_receiver.blk(rate_index=rate_index, correct_cfo=bool(correct_cfo), pilot_tracking=bool(pilot_tracking), report_path=str(ROOT / 'results/live/siso_wlan_receiver.json'))
        self.ber_meter = ber_meter.blk(report_path=str(ROOT / 'results/live/siso_wlan_ber.json'), run_config=dict(model='SISO known-burst Wi-Fi',rate_index=rate_index,tx_reference_snr_db=snr_db,path_loss_db=path_loss_db,cfo_hz=cfo_hz,channel_taps=channel_taps,correct_cfo=correct_cfo,pilot_tracking=pilot_tracking))
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
        self.awgn = analog.noise_source_c(analog.GR_GAUSSIAN, noise_voltage, 20261017)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.awgn, 0), (self.channel_output, 1))
        self.connect((self.ber_meter, 0), (self.ber_display, 0))
        self.connect((self.burst_receiver, 0), (self.constellation, 0))
        self.connect((self.burst_receiver, 0), (self.demap, 0))
        self.connect((self.burst_receiver, 0), (self.evm_meter, 1))
        self.connect((self.carrier_offset, 0), (self.channel_output, 0))
        self.connect((self.channel_output, 0), (self.extract_bursts, 0))
        self.connect((self.channel_output, 0), (self.rx_scope, 0))
        self.connect((self.demap, 0), (self.rx_bits, 0))
        self.connect((self.evm_meter, 0), (self.evm_display, 0))
        self.connect((self.extract_bursts, 0), (self.burst_receiver, 0))
        self.connect((self.finite_reference, 0), (self.constellation, 1))
        self.connect((self.finite_reference, 0), (self.evm_meter, 0))
        self.connect((self.finite_reference, 0), (self.tx_decisions, 0))
        self.connect((self.finite_tx, 0), (self.pace_tx, 0))
        self.connect((self.pace_tx, 0), (self.siso_fir, 0))
        self.connect((self.pace_tx, 0), (self.tx_scope, 0))
        self.connect((self.rx_bits, 0), (self.ber_meter, 1))
        self.connect((self.siso_fir, 0), (self.carrier_offset, 0))
        self.connect((self.tx_bits, 0), (self.ber_meter, 0))
        self.connect((self.tx_decisions, 0), (self.tx_bits, 0))
        self.connect((self.tx_reference, 0), (self.finite_reference, 0))
        self.connect((self.tx_waveform, 0), (self.finite_tx, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "siso_wlan_lab")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_rate_index(self):
        return self.rate_index

    def set_rate_index(self, rate_index):
        self.rate_index = rate_index
        self.set_reference(wlan_reference(self.rate_index))
        self.tx_waveform.set_data(burst_waveform(self.rate_index).tolist(), [])
        self.finite_tx.set_length((self.packet_count*len(burst_waveform(self.rate_index)) if self.packet_count>0 else 2**60))
        self.extract_bursts.set_n(len(burst_waveform(self.rate_index)))
        self.tx_reference.set_data(reference_symbols(self.rate_index).tolist(), [])
        self.finite_reference.set_length((self.packet_count*reference_symbols(self.rate_index).size if self.packet_count>0 else 2**60))

    def get_snr_db(self):
        return self.snr_db

    def set_snr_db(self, snr_db):
        self.snr_db = snr_db
        self.set_noise_voltage(10**(-self.snr_db/20))

    def get_path_loss_db(self):
        return self.path_loss_db

    def set_path_loss_db(self, path_loss_db):
        self.path_loss_db = path_loss_db
        self.set_channel_gain(10**(-self.path_loss_db/20))

    def get_packet_count(self):
        return self.packet_count

    def set_packet_count(self, packet_count):
        self.packet_count = packet_count
        self.finite_tx.set_length((self.packet_count*len(burst_waveform(self.rate_index)) if self.packet_count>0 else 2**60))
        self.finite_reference.set_length((self.packet_count*reference_symbols(self.rate_index).size if self.packet_count>0 else 2**60))

    def get_pace(self):
        return self.pace

    def set_pace(self, pace):
        self.pace = pace
        self.pace_tx.set_sample_rate(self.pace)

    def get_cfo_hz(self):
        return self.cfo_hz

    def set_cfo_hz(self, cfo_hz):
        self.cfo_hz = cfo_hz
        self.carrier_offset.set_phase_inc((2*math.pi*self.cfo_hz/self.sample_rate))

    def get_channel_taps(self):
        return self.channel_taps

    def set_channel_taps(self, channel_taps):
        self.channel_taps = channel_taps
        self.siso_fir.set_taps([self.channel_gain*t for t in parse_taps(self.channel_taps)])

    def get_correct_cfo(self):
        return self.correct_cfo

    def set_correct_cfo(self, correct_cfo):
        self.correct_cfo = correct_cfo

    def get_pilot_tracking(self):
        return self.pilot_tracking

    def set_pilot_tracking(self, pilot_tracking):
        self.pilot_tracking = pilot_tracking

    def get_reference(self):
        return self.reference

    def set_reference(self, reference):
        self.reference = reference
        self.set_order(int(self.reference['order']))
        self.extract_bursts.set_m(self.reference['tx_packet'].size)

    def get_order(self):
        return self.order

    def set_order(self, order):
        self.order = order
        self.set_k(int(math.log2(self.order)))
        self.set_constellation_object(digital.constellation_calcdist(wlan_constellation(self.order).tolist(),list(range(self.order)),1,1,digital.constellation.NO_NORMALIZATION).base())

    def get_sample_rate(self):
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
        self.carrier_offset.set_phase_inc((2*math.pi*self.cfo_hz/self.sample_rate))
        self.tx_scope.set_frequency_range(0, self.sample_rate)
        self.rx_scope.set_frequency_range(0, self.sample_rate)

    def get_noise_voltage(self):
        return self.noise_voltage

    def set_noise_voltage(self, noise_voltage):
        self.noise_voltage = noise_voltage
        self.awgn.set_amplitude(self.noise_voltage)

    def get_k(self):
        return self.k

    def set_k(self, k):
        self.k = k

    def get_constellation_object(self):
        return self.constellation_object

    def set_constellation_object(self, constellation_object):
        self.constellation_object = constellation_object
        self.demap.set_constellation(self.constellation_object)
        self.tx_decisions.set_constellation(self.constellation_object)

    def get_channel_gain(self):
        return self.channel_gain

    def set_channel_gain(self, channel_gain):
        self.channel_gain = channel_gain
        self.siso_fir.set_taps([self.channel_gain*t for t in parse_taps(self.channel_taps)])



def argument_parser():
    description = 'Complete known-burst SISO PHY with fixed active TX power and live pre-FEC BER/EVM. No autonomous acquisition or MAC.'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--rate-index", dest="rate_index", type=intx, default=2,
        help="Set Legacy rate index (0-7) [default=%(default)r]")
    parser.add_argument(
        "--snr-db", dest="snr_db", type=eng_float, default=eng_notation.num_to_str(float(25)),
        help="Set TX active-PPDU reference SNR (dB) [default=%(default)r]")
    parser.add_argument(
        "--path-loss-db", dest="path_loss_db", type=eng_float, default=eng_notation.num_to_str(float(0)),
        help="Set SISO power loss (dB) [default=%(default)r]")
    parser.add_argument(
        "--packet-count", dest="packet_count", type=intx, default=0,
        help="Set PHY bursts (0 = continuous) [default=%(default)r]")
    parser.add_argument(
        "--pace", dest="pace", type=eng_float, default=eng_notation.num_to_str(float(1000000)),
        help="Set Playback samples per wall-clock second [default=%(default)r]")
    parser.add_argument(
        "--cfo-hz", dest="cfo_hz", type=eng_float, default=eng_notation.num_to_str(float(0)),
        help="Set Carrier offset (Hz) [default=%(default)r]")
    parser.add_argument(
        "--channel-taps", dest="channel_taps", type=str, default='1+0j',
        help="Set Causal SISO FIR taps [default=%(default)r]")
    parser.add_argument(
        "--correct-cfo", dest="correct_cfo", type=intx, default=1,
        help="Set STF/LTF CFO correction (0/1) [default=%(default)r]")
    parser.add_argument(
        "--pilot-tracking", dest="pilot_tracking", type=intx, default=1,
        help="Set Pilot phase correction (0/1) [default=%(default)r]")
    return parser


def main(top_block_cls=siso_wlan_lab, options=None):
    if options is None:
        options = argument_parser().parse_args()

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(rate_index=options.rate_index, snr_db=options.snr_db, path_loss_db=options.path_loss_db, packet_count=options.packet_count, pace=options.pace, cfo_hz=options.cfo_hz, channel_taps=options.channel_taps, correct_cfo=options.correct_cfo, pilot_tracking=options.pilot_tracking)

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
