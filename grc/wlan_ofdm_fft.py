#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Legacy Wi-Fi: visible CP removal and FFT
# Author: Antenna benchmark project
# Description: Explicit GNU Radio DATA extraction, CP removal, vectorization and FFT; known-schedule software verification.
# GNU Radio version: 3.10.12.0

from antenna_bench.paths import ROOT
from antenna_bench.math import make_symbols
import math
from gnuradio import blocks
import pmt
from gnuradio import fft
from gnuradio.fft import window
from gnuradio import gr
from gnuradio.filter import firdes
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import threading




class wlan_ofdm_fft(gr.top_block):

    def __init__(self, rate_index=2):
        gr.top_block.__init__(self, "Legacy Wi-Fi: visible CP removal and FFT", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Parameters
        ##################################################
        self.rate_index = rate_index

        ##################################################
        # Variables
        ##################################################
        self.reference = reference = __import__('scipy.io', fromlist=['loadmat']).loadmat(str(ROOT / ('results/reference/wlan_rate_%d.mat' % rate_index)), squeeze_me=True)
        self.metadata = metadata = __import__('json').loads((ROOT / ('results/reference/wlan_rate_%d.json' % rate_index)).read_text())

        ##################################################
        # Blocks
        ##################################################

        self.remove_leading_samples = blocks.skiphead(gr.sizeof_gr_complex*1, metadata['leading_samples'])
        self.remove_cyclic_prefix = blocks.keep_m_in_n(gr.sizeof_gr_complex, 64, 80, 16)
        self.ofdm_vectors = blocks.stream_to_vector(gr.sizeof_gr_complex*1, 64)
        self.fft_capture = blocks.file_sink(gr.sizeof_gr_complex*64, str(ROOT / ('results/grc/wlan_rate_%d_fft.c64' % rate_index)), False)
        self.fft_capture.set_unbuffered(False)
        self.fft_64 = fft.fft_vcc(64, True, [], False, 1)
        self.extract_data_fields = blocks.keep_m_in_n(gr.sizeof_gr_complex, int(reference['data_length']), (metadata['packet_samples']+metadata['idle_samples']), int(reference['data_start']))
        self.aligned_capture = blocks.file_source(gr.sizeof_gr_complex*1, str(ROOT / ('results/grc/wlan_rate_%d_rx.c64' % rate_index)), False, 0, 0)
        self.aligned_capture.set_begin_tag(pmt.PMT_NIL)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.aligned_capture, 0), (self.remove_leading_samples, 0))
        self.connect((self.extract_data_fields, 0), (self.remove_cyclic_prefix, 0))
        self.connect((self.fft_64, 0), (self.fft_capture, 0))
        self.connect((self.ofdm_vectors, 0), (self.fft_64, 0))
        self.connect((self.remove_cyclic_prefix, 0), (self.ofdm_vectors, 0))
        self.connect((self.remove_leading_samples, 0), (self.extract_data_fields, 0))


    def get_rate_index(self):
        return self.rate_index

    def set_rate_index(self, rate_index):
        self.rate_index = rate_index
        self.set_reference(__import__('scipy.io', fromlist=['loadmat']).loadmat(str(ROOT / ('results/reference/wlan_rate_%d.mat' % self.rate_index)), squeeze_me=True))
        self.set_metadata(__import__('json').loads((ROOT / ('results/reference/wlan_rate_%d.json' % self.rate_index)).read_text()))
        self.aligned_capture.open(str(ROOT / ('results/grc/wlan_rate_%d_rx.c64' % self.rate_index)), False)
        self.fft_capture.open(str(ROOT / ('results/grc/wlan_rate_%d_fft.c64' % self.rate_index)))

    def get_reference(self):
        return self.reference

    def set_reference(self, reference):
        self.reference = reference
        self.extract_data_fields.set_offset(int(self.reference['data_start']))
        self.extract_data_fields.set_m(int(self.reference['data_length']))

    def get_metadata(self):
        return self.metadata

    def set_metadata(self, metadata):
        self.metadata = metadata
        self.extract_data_fields.set_n((self.metadata['packet_samples']+self.metadata['idle_samples']))



def argument_parser():
    description = 'Explicit GNU Radio DATA extraction, CP removal, vectorization and FFT; known-schedule software verification.'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--rate-index", dest="rate_index", type=intx, default=2,
        help="Set Legacy rate index (0-7) [default=%(default)r]")
    return parser


def main(top_block_cls=wlan_ofdm_fft, options=None):
    if options is None:
        options = argument_parser().parse_args()
    tb = top_block_cls(rate_index=options.rate_index)

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
