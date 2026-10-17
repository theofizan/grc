# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Symbol mapper | unpacked bits to IQ
# Description: Editable stock-block stage. See docs/MODULAR_FLOWGRAPHS.md.
# GNU Radio version: 3.10.12.0

from gnuradio import blocks
from gnuradio import digital
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
import math
import numpy as np
from antenna_bench.paths import ROOT
from antenna_bench.live import test_bits, wlan_reference, burst_waveform, reference_symbols, parse_taps
from antenna_bench.wlan import wlan_constellation
import threading







class bench_symbol_mapper(gr.hier_block2):
    def __init__(self, order=16):
        gr.hier_block2.__init__(
            self, "Symbol mapper | unpacked bits to IQ",
                gr.io_signature(1, 1, gr.sizeof_char*1),
                gr.io_signature(1, 1, gr.sizeof_gr_complex*1),
        )

        ##################################################
        # Parameters
        ##################################################
        self.order = order

        ##################################################
        # Variables
        ##################################################
        self.k = k = int(math.log2(order))

        ##################################################
        # Blocks
        ##################################################

        self.pack_bits = blocks.pack_k_bits_bb(k)
        self.mapper = digital.chunks_to_symbols_bc(wlan_constellation(order).tolist(), 1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self, 0), (self.pack_bits, 0))
        self.connect((self.mapper, 0), (self, 0))
        self.connect((self.pack_bits, 0), (self.mapper, 0))


    def get_order(self):
        return self.order

    def set_order(self, order):
        self.order = order
        self.set_k(int(math.log2(self.order)))
        self.mapper.set_symbol_table(wlan_constellation(self.order).tolist())

    def get_k(self):
        return self.k

    def set_k(self, k):
        self.k = k

