#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: QPSK BER vs Eb/N0 | stock blocks
# Author: Antenna benchmark
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import blocks
import numpy
from gnuradio import channels
from gnuradio.filter import firdes
from gnuradio import digital
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


def snipfcn_equalizer_initial_taps(self):
    # Start every row's adaptive equalizer at a centered identity filter.
    for i in range(8):
        getattr(self, 'equalizer_%d' % i).set_taps([0j]*((self.eq_taps-1)//2)+[1+0j]+[0j]*(self.eq_taps//2))

def snipfcn_curve_title(self):
    self.ber_curve.set_title('QPSK BER vs Eb/N0 (x axis: Eb/N0 in dB per bit). Red: BPSK/QPSK theory')
    self.resize(1000, 700)


def snippets_main_after_init(tb):
    snipfcn_equalizer_initial_taps(tb)
    snipfcn_curve_title(tb)

class ber_curve_qpsk(gr.top_block, Qt.QWidget):

    def __init__(self, symbol_rate=1e6, eq_taps=11, eq_step=0.01, reference_delay=68, tx_power_dbm=0, path_loss_db=0, min_errors=100, ber_floor_log10=(-7), sim_speed=100):
        gr.top_block.__init__(self, "QPSK BER vs Eb/N0 | stock blocks", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("QPSK BER vs Eb/N0 | stock blocks")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "ber_curve_qpsk")

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
        self.symbol_rate = symbol_rate
        self.eq_taps = eq_taps
        self.eq_step = eq_step
        self.reference_delay = reference_delay
        self.tx_power_dbm = tx_power_dbm
        self.path_loss_db = path_loss_db
        self.min_errors = min_errors
        self.ber_floor_log10 = ber_floor_log10
        self.sim_speed = sim_speed

        ##################################################
        # Variables
        ##################################################
        self.const = const = digital.constellation_qpsk().base()
        self.const.set_npwr(1.0)
        self.sps = sps = 4
        self.k = k = const.bits_per_symbol()
        self.tx_amplitude = tx_amplitude = 10**(tx_power_dbm/20.0)
        self.symbol_rms = symbol_rms = (sum(abs(p)**2 for p in const.points())/len(const.points()))**0.5
        self.samp_rate = samp_rate = symbol_rate*sps
        self.path_gain = path_gain = 10**(-path_loss_db/20.0)
        self.nfilts = nfilts = 32
        self.ebno_db = ebno_db = [0, 2, 4, 6, 8, 10, 12, 14]
        self.bit_rate = bit_rate = symbol_rate*k
        self.alpha = alpha = 0.35
        self.warmup_bits = warmup_bits = 50000
        self.timing_bw = timing_bw = 0.0628
        self.rrc_taps = rrc_taps = firdes.root_raised_cosine(nfilts, nfilts*sps, 1.0, alpha, 11*sps*nfilts)
        self.noise_volts = noise_volts = list(tx_amplitude*path_gain*10**(-(numpy.array(ebno_db) - 10*math.log10(samp_rate/bit_rate))/20))
        self.eq_delay_symbols = eq_delay_symbols = (eq_taps-1)//2
        self.eq_algorithm = eq_algorithm = digital.adaptive_algorithm_lms( const, eq_step/(eq_taps*symbol_rms**2)).base()

        ##################################################
        # Blocks
        ##################################################

        self.unpack_tx = blocks.unpack_k_bits_bb(8)
        self.unpack_rx_7 = blocks.unpack_k_bits_bb(k)
        self.unpack_rx_6 = blocks.unpack_k_bits_bb(k)
        self.unpack_rx_5 = blocks.unpack_k_bits_bb(k)
        self.unpack_rx_4 = blocks.unpack_k_bits_bb(k)
        self.unpack_rx_3 = blocks.unpack_k_bits_bb(k)
        self.unpack_rx_2 = blocks.unpack_k_bits_bb(k)
        self.unpack_rx_1 = blocks.unpack_k_bits_bb(k)
        self.unpack_rx_0 = blocks.unpack_k_bits_bb(k)
        self.tx_power = blocks.multiply_const_cc(tx_amplitude/symbol_rms)
        self.throttle = blocks.throttle( gr.sizeof_gr_complex*1, (samp_rate*sim_speed), True, 0 if "auto" == "auto" else max( int(float(0.1) * (samp_rate*sim_speed)) if "auto" == "time" else int(0.1), 1) )
        self.skip_tx = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.skip_rx_7 = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.skip_rx_6 = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.skip_rx_5 = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.skip_rx_4 = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.skip_rx_3 = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.skip_rx_2 = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.skip_rx_1 = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.skip_rx_0 = blocks.skiphead(gr.sizeof_char*1, warmup_bits)
        self.rx_scale_7 = blocks.multiply_const_cc(symbol_rms)
        self.rx_scale_6 = blocks.multiply_const_cc(symbol_rms)
        self.rx_scale_5 = blocks.multiply_const_cc(symbol_rms)
        self.rx_scale_4 = blocks.multiply_const_cc(symbol_rms)
        self.rx_scale_3 = blocks.multiply_const_cc(symbol_rms)
        self.rx_scale_2 = blocks.multiply_const_cc(symbol_rms)
        self.rx_scale_1 = blocks.multiply_const_cc(symbol_rms)
        self.rx_scale_0 = blocks.multiply_const_cc(symbol_rms)
        self.rx_level_7 = blocks.multiply_const_cc(1.0/(tx_amplitude*path_gain))
        self.rx_level_6 = blocks.multiply_const_cc(1.0/(tx_amplitude*path_gain))
        self.rx_level_5 = blocks.multiply_const_cc(1.0/(tx_amplitude*path_gain))
        self.rx_level_4 = blocks.multiply_const_cc(1.0/(tx_amplitude*path_gain))
        self.rx_level_3 = blocks.multiply_const_cc(1.0/(tx_amplitude*path_gain))
        self.rx_level_2 = blocks.multiply_const_cc(1.0/(tx_amplitude*path_gain))
        self.rx_level_1 = blocks.multiply_const_cc(1.0/(tx_amplitude*path_gain))
        self.rx_level_0 = blocks.multiply_const_cc(1.0/(tx_amplitude*path_gain))
        self.random_bytes = blocks.vector_source_b(list(map(int, numpy.random.randint(0, 256, 32768))), True)
        self.pack_tx = blocks.pack_k_bits_bb(8)
        self.pack_rx_7 = blocks.pack_k_bits_bb(8)
        self.pack_rx_6 = blocks.pack_k_bits_bb(8)
        self.pack_rx_5 = blocks.pack_k_bits_bb(8)
        self.pack_rx_4 = blocks.pack_k_bits_bb(8)
        self.pack_rx_3 = blocks.pack_k_bits_bb(8)
        self.pack_rx_2 = blocks.pack_k_bits_bb(8)
        self.pack_rx_1 = blocks.pack_k_bits_bb(8)
        self.pack_rx_0 = blocks.pack_k_bits_bb(8)
        self.modulator = digital.generic_mod(
            constellation=const,
            differential=True,
            samples_per_symbol=sps,
            pre_diff_code=True,
            excess_bw=alpha,
            verbose=False,
            log=False,
            truncate=False)
        self.equalizer_7 = digital.linear_equalizer(eq_taps, 1, eq_algorithm, True, [], '')
        self.equalizer_6 = digital.linear_equalizer(eq_taps, 1, eq_algorithm, True, [], '')
        self.equalizer_5 = digital.linear_equalizer(eq_taps, 1, eq_algorithm, True, [], '')
        self.equalizer_4 = digital.linear_equalizer(eq_taps, 1, eq_algorithm, True, [], '')
        self.equalizer_3 = digital.linear_equalizer(eq_taps, 1, eq_algorithm, True, [], '')
        self.equalizer_2 = digital.linear_equalizer(eq_taps, 1, eq_algorithm, True, [], '')
        self.equalizer_1 = digital.linear_equalizer(eq_taps, 1, eq_algorithm, True, [], '')
        self.equalizer_0 = digital.linear_equalizer(eq_taps, 1, eq_algorithm, True, [], '')
        self.diff_decoder_7 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.diff_decoder_6 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.diff_decoder_5 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.diff_decoder_4 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.diff_decoder_3 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.diff_decoder_2 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.diff_decoder_1 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.diff_decoder_0 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.delay = blocks.delay(gr.sizeof_char*1, reference_delay)
        self.decoder_7 = digital.constellation_decoder_cb(const)
        self.decoder_6 = digital.constellation_decoder_cb(const)
        self.decoder_5 = digital.constellation_decoder_cb(const)
        self.decoder_4 = digital.constellation_decoder_cb(const)
        self.decoder_3 = digital.constellation_decoder_cb(const)
        self.decoder_2 = digital.constellation_decoder_cb(const)
        self.decoder_1 = digital.constellation_decoder_cb(const)
        self.decoder_0 = digital.constellation_decoder_cb(const)
        self.clock_sync_7 = digital.pfb_clock_sync_ccf(sps, timing_bw, rrc_taps, nfilts, 16, 1.5, 1)
        self.clock_sync_6 = digital.pfb_clock_sync_ccf(sps, timing_bw, rrc_taps, nfilts, 16, 1.5, 1)
        self.clock_sync_5 = digital.pfb_clock_sync_ccf(sps, timing_bw, rrc_taps, nfilts, 16, 1.5, 1)
        self.clock_sync_4 = digital.pfb_clock_sync_ccf(sps, timing_bw, rrc_taps, nfilts, 16, 1.5, 1)
        self.clock_sync_3 = digital.pfb_clock_sync_ccf(sps, timing_bw, rrc_taps, nfilts, 16, 1.5, 1)
        self.clock_sync_2 = digital.pfb_clock_sync_ccf(sps, timing_bw, rrc_taps, nfilts, 16, 1.5, 1)
        self.clock_sync_1 = digital.pfb_clock_sync_ccf(sps, timing_bw, rrc_taps, nfilts, 16, 1.5, 1)
        self.clock_sync_0 = digital.pfb_clock_sync_ccf(sps, timing_bw, rrc_taps, nfilts, 16, 1.5, 1)
        self.channel_7 = channels.channel_model(
            noise_voltage=noise_volts[7],
            frequency_offset=0,
            epsilon=1,
            taps=[path_gain],
            noise_seed=107,
            block_tags=False)
        self.channel_6 = channels.channel_model(
            noise_voltage=noise_volts[6],
            frequency_offset=0,
            epsilon=1,
            taps=[path_gain],
            noise_seed=106,
            block_tags=False)
        self.channel_5 = channels.channel_model(
            noise_voltage=noise_volts[5],
            frequency_offset=0,
            epsilon=1,
            taps=[path_gain],
            noise_seed=105,
            block_tags=False)
        self.channel_4 = channels.channel_model(
            noise_voltage=noise_volts[4],
            frequency_offset=0,
            epsilon=1,
            taps=[path_gain],
            noise_seed=104,
            block_tags=False)
        self.channel_3 = channels.channel_model(
            noise_voltage=noise_volts[3],
            frequency_offset=0,
            epsilon=1,
            taps=[path_gain],
            noise_seed=103,
            block_tags=False)
        self.channel_2 = channels.channel_model(
            noise_voltage=noise_volts[2],
            frequency_offset=0,
            epsilon=1,
            taps=[path_gain],
            noise_seed=102,
            block_tags=False)
        self.channel_1 = channels.channel_model(
            noise_voltage=noise_volts[1],
            frequency_offset=0,
            epsilon=1,
            taps=[path_gain],
            noise_seed=101,
            block_tags=False)
        self.channel_0 = channels.channel_model(
            noise_voltage=noise_volts[0],
            frequency_offset=0,
            epsilon=1,
            taps=[path_gain],
            noise_seed=100,
            block_tags=False)
        self.ber_curve = qtgui.ber_sink_b(
            ebno_db, #range of esnos
            1, #number of curves
            min_errors, #ensure at least
            ber_floor_log10, #cutoff
            [], #indiv. curve names
            None # parent
        )
        self.ber_curve.set_update_time(0.25)
        self.ber_curve.set_y_axis((-7), 0)
        self.ber_curve.set_x_axis(ebno_db[0], ebno_db[-1])

        labels = ["QPSK measured", '', '', '', '',
            '', '', '', '', '']
        widths = [2, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.ber_curve.set_line_label(i, "Data {0}".format(i))
            else:
                self.ber_curve.set_line_label(i, labels[i])
            self.ber_curve.set_line_width(i, widths[i])
            self.ber_curve.set_line_color(i, colors[i])
            self.ber_curve.set_line_style(i, styles[i])
            self.ber_curve.set_line_marker(i, markers[i])
            self.ber_curve.set_line_alpha(i, alphas[i])

        self._ber_curve_win = sip.wrapinstance(self.ber_curve.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._ber_curve_win)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.channel_0, 0), (self.rx_level_0, 0))
        self.connect((self.channel_1, 0), (self.rx_level_1, 0))
        self.connect((self.channel_2, 0), (self.rx_level_2, 0))
        self.connect((self.channel_3, 0), (self.rx_level_3, 0))
        self.connect((self.channel_4, 0), (self.rx_level_4, 0))
        self.connect((self.channel_5, 0), (self.rx_level_5, 0))
        self.connect((self.channel_6, 0), (self.rx_level_6, 0))
        self.connect((self.channel_7, 0), (self.rx_level_7, 0))
        self.connect((self.clock_sync_0, 0), (self.rx_scale_0, 0))
        self.connect((self.clock_sync_1, 0), (self.rx_scale_1, 0))
        self.connect((self.clock_sync_2, 0), (self.rx_scale_2, 0))
        self.connect((self.clock_sync_3, 0), (self.rx_scale_3, 0))
        self.connect((self.clock_sync_4, 0), (self.rx_scale_4, 0))
        self.connect((self.clock_sync_5, 0), (self.rx_scale_5, 0))
        self.connect((self.clock_sync_6, 0), (self.rx_scale_6, 0))
        self.connect((self.clock_sync_7, 0), (self.rx_scale_7, 0))
        self.connect((self.decoder_0, 0), (self.diff_decoder_0, 0))
        self.connect((self.decoder_1, 0), (self.diff_decoder_1, 0))
        self.connect((self.decoder_2, 0), (self.diff_decoder_2, 0))
        self.connect((self.decoder_3, 0), (self.diff_decoder_3, 0))
        self.connect((self.decoder_4, 0), (self.diff_decoder_4, 0))
        self.connect((self.decoder_5, 0), (self.diff_decoder_5, 0))
        self.connect((self.decoder_6, 0), (self.diff_decoder_6, 0))
        self.connect((self.decoder_7, 0), (self.diff_decoder_7, 0))
        self.connect((self.delay, 0), (self.skip_tx, 0))
        self.connect((self.diff_decoder_0, 0), (self.unpack_rx_0, 0))
        self.connect((self.diff_decoder_1, 0), (self.unpack_rx_1, 0))
        self.connect((self.diff_decoder_2, 0), (self.unpack_rx_2, 0))
        self.connect((self.diff_decoder_3, 0), (self.unpack_rx_3, 0))
        self.connect((self.diff_decoder_4, 0), (self.unpack_rx_4, 0))
        self.connect((self.diff_decoder_5, 0), (self.unpack_rx_5, 0))
        self.connect((self.diff_decoder_6, 0), (self.unpack_rx_6, 0))
        self.connect((self.diff_decoder_7, 0), (self.unpack_rx_7, 0))
        self.connect((self.equalizer_0, 0), (self.decoder_0, 0))
        self.connect((self.equalizer_1, 0), (self.decoder_1, 0))
        self.connect((self.equalizer_2, 0), (self.decoder_2, 0))
        self.connect((self.equalizer_3, 0), (self.decoder_3, 0))
        self.connect((self.equalizer_4, 0), (self.decoder_4, 0))
        self.connect((self.equalizer_5, 0), (self.decoder_5, 0))
        self.connect((self.equalizer_6, 0), (self.decoder_6, 0))
        self.connect((self.equalizer_7, 0), (self.decoder_7, 0))
        self.connect((self.modulator, 0), (self.tx_power, 0))
        self.connect((self.pack_rx_0, 0), (self.ber_curve, 1))
        self.connect((self.pack_rx_1, 0), (self.ber_curve, 3))
        self.connect((self.pack_rx_2, 0), (self.ber_curve, 5))
        self.connect((self.pack_rx_3, 0), (self.ber_curve, 7))
        self.connect((self.pack_rx_4, 0), (self.ber_curve, 9))
        self.connect((self.pack_rx_5, 0), (self.ber_curve, 11))
        self.connect((self.pack_rx_6, 0), (self.ber_curve, 13))
        self.connect((self.pack_rx_7, 0), (self.ber_curve, 15))
        self.connect((self.pack_tx, 0), (self.ber_curve, 10))
        self.connect((self.pack_tx, 0), (self.ber_curve, 14))
        self.connect((self.pack_tx, 0), (self.ber_curve, 8))
        self.connect((self.pack_tx, 0), (self.ber_curve, 0))
        self.connect((self.pack_tx, 0), (self.ber_curve, 12))
        self.connect((self.pack_tx, 0), (self.ber_curve, 2))
        self.connect((self.pack_tx, 0), (self.ber_curve, 4))
        self.connect((self.pack_tx, 0), (self.ber_curve, 6))
        self.connect((self.random_bytes, 0), (self.modulator, 0))
        self.connect((self.random_bytes, 0), (self.unpack_tx, 0))
        self.connect((self.rx_level_0, 0), (self.clock_sync_0, 0))
        self.connect((self.rx_level_1, 0), (self.clock_sync_1, 0))
        self.connect((self.rx_level_2, 0), (self.clock_sync_2, 0))
        self.connect((self.rx_level_3, 0), (self.clock_sync_3, 0))
        self.connect((self.rx_level_4, 0), (self.clock_sync_4, 0))
        self.connect((self.rx_level_5, 0), (self.clock_sync_5, 0))
        self.connect((self.rx_level_6, 0), (self.clock_sync_6, 0))
        self.connect((self.rx_level_7, 0), (self.clock_sync_7, 0))
        self.connect((self.rx_scale_0, 0), (self.equalizer_0, 0))
        self.connect((self.rx_scale_1, 0), (self.equalizer_1, 0))
        self.connect((self.rx_scale_2, 0), (self.equalizer_2, 0))
        self.connect((self.rx_scale_3, 0), (self.equalizer_3, 0))
        self.connect((self.rx_scale_4, 0), (self.equalizer_4, 0))
        self.connect((self.rx_scale_5, 0), (self.equalizer_5, 0))
        self.connect((self.rx_scale_6, 0), (self.equalizer_6, 0))
        self.connect((self.rx_scale_7, 0), (self.equalizer_7, 0))
        self.connect((self.skip_rx_0, 0), (self.pack_rx_0, 0))
        self.connect((self.skip_rx_1, 0), (self.pack_rx_1, 0))
        self.connect((self.skip_rx_2, 0), (self.pack_rx_2, 0))
        self.connect((self.skip_rx_3, 0), (self.pack_rx_3, 0))
        self.connect((self.skip_rx_4, 0), (self.pack_rx_4, 0))
        self.connect((self.skip_rx_5, 0), (self.pack_rx_5, 0))
        self.connect((self.skip_rx_6, 0), (self.pack_rx_6, 0))
        self.connect((self.skip_rx_7, 0), (self.pack_rx_7, 0))
        self.connect((self.skip_tx, 0), (self.pack_tx, 0))
        self.connect((self.throttle, 0), (self.channel_0, 0))
        self.connect((self.throttle, 0), (self.channel_1, 0))
        self.connect((self.throttle, 0), (self.channel_2, 0))
        self.connect((self.throttle, 0), (self.channel_3, 0))
        self.connect((self.throttle, 0), (self.channel_4, 0))
        self.connect((self.throttle, 0), (self.channel_5, 0))
        self.connect((self.throttle, 0), (self.channel_6, 0))
        self.connect((self.throttle, 0), (self.channel_7, 0))
        self.connect((self.tx_power, 0), (self.throttle, 0))
        self.connect((self.unpack_rx_0, 0), (self.skip_rx_0, 0))
        self.connect((self.unpack_rx_1, 0), (self.skip_rx_1, 0))
        self.connect((self.unpack_rx_2, 0), (self.skip_rx_2, 0))
        self.connect((self.unpack_rx_3, 0), (self.skip_rx_3, 0))
        self.connect((self.unpack_rx_4, 0), (self.skip_rx_4, 0))
        self.connect((self.unpack_rx_5, 0), (self.skip_rx_5, 0))
        self.connect((self.unpack_rx_6, 0), (self.skip_rx_6, 0))
        self.connect((self.unpack_rx_7, 0), (self.skip_rx_7, 0))
        self.connect((self.unpack_tx, 0), (self.delay, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "ber_curve_qpsk")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_symbol_rate(self):
        return self.symbol_rate

    def set_symbol_rate(self, symbol_rate):
        self.symbol_rate = symbol_rate
        self.set_samp_rate(self.symbol_rate*self.sps)
        self.set_bit_rate(self.symbol_rate*self.k)

    def get_eq_taps(self):
        return self.eq_taps

    def set_eq_taps(self, eq_taps):
        self.eq_taps = eq_taps
        self.set_eq_delay_symbols((self.eq_taps-1)//2)

    def get_eq_step(self):
        return self.eq_step

    def set_eq_step(self, eq_step):
        self.eq_step = eq_step

    def get_reference_delay(self):
        return self.reference_delay

    def set_reference_delay(self, reference_delay):
        self.reference_delay = reference_delay
        self.delay.set_dly(int(self.reference_delay))

    def get_tx_power_dbm(self):
        return self.tx_power_dbm

    def set_tx_power_dbm(self, tx_power_dbm):
        self.tx_power_dbm = tx_power_dbm
        self.set_tx_amplitude(10**(self.tx_power_dbm/20.0))

    def get_path_loss_db(self):
        return self.path_loss_db

    def set_path_loss_db(self, path_loss_db):
        self.path_loss_db = path_loss_db
        self.set_path_gain(10**(-self.path_loss_db/20.0))

    def get_min_errors(self):
        return self.min_errors

    def set_min_errors(self, min_errors):
        self.min_errors = min_errors

    def get_ber_floor_log10(self):
        return self.ber_floor_log10

    def set_ber_floor_log10(self, ber_floor_log10):
        self.ber_floor_log10 = ber_floor_log10

    def get_sim_speed(self):
        return self.sim_speed

    def set_sim_speed(self, sim_speed):
        self.sim_speed = sim_speed
        self.throttle.set_sample_rate((self.samp_rate*self.sim_speed))

    def get_const(self):
        return self.const

    def set_const(self, const):
        self.const = const
        self.decoder_0.set_constellation(self.const)
        self.decoder_1.set_constellation(self.const)
        self.decoder_2.set_constellation(self.const)
        self.decoder_3.set_constellation(self.const)
        self.decoder_4.set_constellation(self.const)
        self.decoder_5.set_constellation(self.const)
        self.decoder_6.set_constellation(self.const)
        self.decoder_7.set_constellation(self.const)

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.alpha, 11*self.sps*self.nfilts))
        self.set_samp_rate(self.symbol_rate*self.sps)

    def get_k(self):
        return self.k

    def set_k(self, k):
        self.k = k
        self.set_bit_rate(self.symbol_rate*self.k)

    def get_tx_amplitude(self):
        return self.tx_amplitude

    def set_tx_amplitude(self, tx_amplitude):
        self.tx_amplitude = tx_amplitude
        self.set_noise_volts(list(self.tx_amplitude*self.path_gain*10**(-(numpy.array(self.ebno_db) - 10*math.log10(self.samp_rate/self.bit_rate))/20)))
        self.tx_power.set_k(self.tx_amplitude/self.symbol_rms)
        self.rx_level_0.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.rx_level_1.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.rx_level_2.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.rx_level_3.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.rx_level_4.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.rx_level_5.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.rx_level_6.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.rx_level_7.set_k(1.0/(self.tx_amplitude*self.path_gain))

    def get_symbol_rms(self):
        return self.symbol_rms

    def set_symbol_rms(self, symbol_rms):
        self.symbol_rms = symbol_rms
        self.tx_power.set_k(self.tx_amplitude/self.symbol_rms)
        self.rx_scale_0.set_k(self.symbol_rms)
        self.rx_scale_1.set_k(self.symbol_rms)
        self.rx_scale_2.set_k(self.symbol_rms)
        self.rx_scale_3.set_k(self.symbol_rms)
        self.rx_scale_4.set_k(self.symbol_rms)
        self.rx_scale_5.set_k(self.symbol_rms)
        self.rx_scale_6.set_k(self.symbol_rms)
        self.rx_scale_7.set_k(self.symbol_rms)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_noise_volts(list(self.tx_amplitude*self.path_gain*10**(-(numpy.array(self.ebno_db) - 10*math.log10(self.samp_rate/self.bit_rate))/20)))
        self.throttle.set_sample_rate((self.samp_rate*self.sim_speed))

    def get_path_gain(self):
        return self.path_gain

    def set_path_gain(self, path_gain):
        self.path_gain = path_gain
        self.set_noise_volts(list(self.tx_amplitude*self.path_gain*10**(-(numpy.array(self.ebno_db) - 10*math.log10(self.samp_rate/self.bit_rate))/20)))
        self.channel_0.set_taps([self.path_gain])
        self.rx_level_0.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.channel_1.set_taps([self.path_gain])
        self.rx_level_1.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.channel_2.set_taps([self.path_gain])
        self.rx_level_2.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.channel_3.set_taps([self.path_gain])
        self.rx_level_3.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.channel_4.set_taps([self.path_gain])
        self.rx_level_4.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.channel_5.set_taps([self.path_gain])
        self.rx_level_5.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.channel_6.set_taps([self.path_gain])
        self.rx_level_6.set_k(1.0/(self.tx_amplitude*self.path_gain))
        self.channel_7.set_taps([self.path_gain])
        self.rx_level_7.set_k(1.0/(self.tx_amplitude*self.path_gain))

    def get_nfilts(self):
        return self.nfilts

    def set_nfilts(self, nfilts):
        self.nfilts = nfilts
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.alpha, 11*self.sps*self.nfilts))

    def get_ebno_db(self):
        return self.ebno_db

    def set_ebno_db(self, ebno_db):
        self.ebno_db = ebno_db
        self.set_noise_volts(list(self.tx_amplitude*self.path_gain*10**(-(numpy.array(self.ebno_db) - 10*math.log10(self.samp_rate/self.bit_rate))/20)))

    def get_bit_rate(self):
        return self.bit_rate

    def set_bit_rate(self, bit_rate):
        self.bit_rate = bit_rate
        self.set_noise_volts(list(self.tx_amplitude*self.path_gain*10**(-(numpy.array(self.ebno_db) - 10*math.log10(self.samp_rate/self.bit_rate))/20)))

    def get_alpha(self):
        return self.alpha

    def set_alpha(self, alpha):
        self.alpha = alpha
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.alpha, 11*self.sps*self.nfilts))

    def get_warmup_bits(self):
        return self.warmup_bits

    def set_warmup_bits(self, warmup_bits):
        self.warmup_bits = warmup_bits

    def get_timing_bw(self):
        return self.timing_bw

    def set_timing_bw(self, timing_bw):
        self.timing_bw = timing_bw
        self.clock_sync_0.set_loop_bandwidth(self.timing_bw)
        self.clock_sync_1.set_loop_bandwidth(self.timing_bw)
        self.clock_sync_2.set_loop_bandwidth(self.timing_bw)
        self.clock_sync_3.set_loop_bandwidth(self.timing_bw)
        self.clock_sync_4.set_loop_bandwidth(self.timing_bw)
        self.clock_sync_5.set_loop_bandwidth(self.timing_bw)
        self.clock_sync_6.set_loop_bandwidth(self.timing_bw)
        self.clock_sync_7.set_loop_bandwidth(self.timing_bw)

    def get_rrc_taps(self):
        return self.rrc_taps

    def set_rrc_taps(self, rrc_taps):
        self.rrc_taps = rrc_taps
        self.clock_sync_0.update_taps(self.rrc_taps)
        self.clock_sync_1.update_taps(self.rrc_taps)
        self.clock_sync_2.update_taps(self.rrc_taps)
        self.clock_sync_3.update_taps(self.rrc_taps)
        self.clock_sync_4.update_taps(self.rrc_taps)
        self.clock_sync_5.update_taps(self.rrc_taps)
        self.clock_sync_6.update_taps(self.rrc_taps)
        self.clock_sync_7.update_taps(self.rrc_taps)

    def get_noise_volts(self):
        return self.noise_volts

    def set_noise_volts(self, noise_volts):
        self.noise_volts = noise_volts
        self.channel_0.set_noise_voltage(self.noise_volts[0])
        self.channel_1.set_noise_voltage(self.noise_volts[1])
        self.channel_2.set_noise_voltage(self.noise_volts[2])
        self.channel_3.set_noise_voltage(self.noise_volts[3])
        self.channel_4.set_noise_voltage(self.noise_volts[4])
        self.channel_5.set_noise_voltage(self.noise_volts[5])
        self.channel_6.set_noise_voltage(self.noise_volts[6])
        self.channel_7.set_noise_voltage(self.noise_volts[7])

    def get_eq_delay_symbols(self):
        return self.eq_delay_symbols

    def set_eq_delay_symbols(self, eq_delay_symbols):
        self.eq_delay_symbols = eq_delay_symbols

    def get_eq_algorithm(self):
        return self.eq_algorithm

    def set_eq_algorithm(self, eq_algorithm):
        self.eq_algorithm = eq_algorithm



def argument_parser():
    parser = ArgumentParser()
    parser.add_argument(
        "--symbol-rate", dest="symbol_rate", type=eng_float, default=eng_notation.num_to_str(float(1e6)),
        help="Set Symbol rate (symbols/s) [default=%(default)r]")
    parser.add_argument(
        "--eq-taps", dest="eq_taps", type=intx, default=11,
        help="Set Adaptive equalizer taps [default=%(default)r]")
    parser.add_argument(
        "--eq-step", dest="eq_step", type=eng_float, default=eng_notation.num_to_str(float(0.01)),
        help="Set NLMS adaptation step [default=%(default)r]")
    parser.add_argument(
        "--reference-delay", dest="reference_delay", type=intx, default=68,
        help="Set TX reference delay (bits) [default=%(default)r]")
    parser.add_argument(
        "--tx-power-dbm", dest="tx_power_dbm", type=eng_float, default=eng_notation.num_to_str(float(0)),
        help="Set TX average conducted power (dBm) [default=%(default)r]")
    parser.add_argument(
        "--path-loss-db", dest="path_loss_db", type=eng_float, default=eng_notation.num_to_str(float(0)),
        help="Set Net path loss including gains/losses (dB) [default=%(default)r]")
    parser.add_argument(
        "--min-errors", dest="min_errors", type=intx, default=100,
        help="Set Bit errors to collect per point [default=%(default)r]")
    parser.add_argument(
        "--ber-floor-log10", dest="ber_floor_log10", type=eng_float, default=eng_notation.num_to_str(float((-7))),
        help="Set Stop a point below BER 10^x [default=%(default)r]")
    parser.add_argument(
        "--sim-speed", dest="sim_speed", type=eng_float, default=eng_notation.num_to_str(float(100)),
        help="Set Simulation speed limit (x real time) [default=%(default)r]")
    return parser


def main(top_block_cls=ber_curve_qpsk, options=None):
    if options is None:
        options = argument_parser().parse_args()

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(symbol_rate=options.symbol_rate, eq_taps=options.eq_taps, eq_step=options.eq_step, reference_delay=options.reference_delay, tx_power_dbm=options.tx_power_dbm, path_loss_db=options.path_loss_db, min_errors=options.min_errors, ber_floor_log10=options.ber_floor_log10, sim_speed=options.sim_speed)
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
