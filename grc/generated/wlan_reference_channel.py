#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Legacy Wi-Fi reference: finite IQ AWGN replay
# Author: Antenna benchmark project
# Description: Replay actual MATLAB-generated non-HT PPDU samples. See docs/FLOWGRAPHS.md for export and analysis.
# GNU Radio version: 3.10.12.0

from antenna_bench.paths import ROOT
from antenna_bench.math import make_symbols
import math
from gnuradio import analog
from gnuradio import blocks
import pmt
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import threading




class wlan_reference_channel(gr.top_block):

    def __init__(self, rate_index=2, snr_db=25):
        gr.top_block.__init__(self, "Legacy Wi-Fi reference: finite IQ AWGN replay", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Parameters
        ##################################################
        self.rate_index = rate_index
        self.snr_db = snr_db

        ##################################################
        # Variables
        ##################################################
        self.tx_file = tx_file = str(ROOT / ('results/reference/wlan_rate_%d_tx.c64' % rate_index))
        self.sample_rate = sample_rate = 20e6
        self.noise_voltage = noise_voltage = math.sqrt(__import__('json').loads((ROOT / ('results/reference/wlan_rate_%d.json' % rate_index)).read_text())['active_time_power']/10**(snr_db/10))

        ##################################################
        # Blocks
        ##################################################

        self.wifi_reference = blocks.file_source(gr.sizeof_gr_complex*1, tx_file, False, 0, 0)
        self.wifi_reference.set_begin_tag(pmt.PMT_NIL)
        self.wifi_capture = blocks.file_sink(gr.sizeof_gr_complex*1, str(ROOT / ('results/grc/wlan_rate_%d_rx.c64' % rate_index)), False)
        self.wifi_capture.set_unbuffered(False)
        self.complex_awgn = analog.noise_source_c(analog.GR_GAUSSIAN, noise_voltage, 20261017)
        self.add_noise = blocks.add_vcc(1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.add_noise, 0), (self.wifi_capture, 0))
        self.connect((self.complex_awgn, 0), (self.add_noise, 1))
        self.connect((self.wifi_reference, 0), (self.add_noise, 0))


    def get_rate_index(self):
        return self.rate_index

    def set_rate_index(self, rate_index):
        self.rate_index = rate_index
        self.set_tx_file(str(ROOT / ('results/reference/wlan_rate_%d_tx.c64' % self.rate_index)))
        self.set_noise_voltage(math.sqrt(__import__('json').loads((ROOT / ('results/reference/wlan_rate_%d.json' % self.rate_index)).read_text())['active_time_power']/10**(self.snr_db/10)))
        self.wifi_capture.open(str(ROOT / ('results/grc/wlan_rate_%d_rx.c64' % self.rate_index)))

    def get_snr_db(self):
        return self.snr_db

    def set_snr_db(self, snr_db):
        self.snr_db = snr_db
        self.set_noise_voltage(math.sqrt(__import__('json').loads((ROOT / ('results/reference/wlan_rate_%d.json' % self.rate_index)).read_text())['active_time_power']/10**(self.snr_db/10)))

    def get_tx_file(self):
        return self.tx_file

    def set_tx_file(self, tx_file):
        self.tx_file = tx_file
        self.wifi_reference.open(self.tx_file, False)

    def get_sample_rate(self):
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate

    def get_noise_voltage(self):
        return self.noise_voltage

    def set_noise_voltage(self, noise_voltage):
        self.noise_voltage = noise_voltage
        self.complex_awgn.set_amplitude(self.noise_voltage)



def argument_parser():
    description = 'Replay actual MATLAB-generated non-HT PPDU samples. See docs/FLOWGRAPHS.md for export and analysis.'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--rate-index", dest="rate_index", type=intx, default=2,
        help="Set Legacy rate index (0-7) [default=%(default)r]")
    parser.add_argument(
        "--snr-db", dest="snr_db", type=eng_float, default=eng_notation.num_to_str(float(25)),
        help="Set Active DATA sample SNR (dB) [default=%(default)r]")
    return parser


def main(top_block_cls=wlan_reference_channel, options=None):
    if options is None:
        options = argument_parser().parse_args()
    tb = top_block_cls(rate_index=options.rate_index, snr_db=options.snr_db)

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()

    tb.wait()


if __name__ == '__main__':
    main()
