# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Hard decisions | IQ to unpacked bits
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







class bench_symbol_demapper(gr.hier_block2):
    def __init__(self, order=16):
        gr.hier_block2.__init__(
            self, "Hard decisions | IQ to unpacked bits",
                gr.io_signature(1, 1, gr.sizeof_gr_complex*1),
                gr.io_signature(1, 1, gr.sizeof_char*1),
        )

        ##################################################
        # Parameters
        ##################################################
        self.order = order

        ##################################################
        # Variables
        ##################################################
        self.k = k = int(math.log2(order))
        self.constellation_object = constellation_object = digital.constellation_calcdist(wlan_constellation(order).tolist(),list(range(order)),1,1,digital.constellation.NO_NORMALIZATION).base()

        ##################################################
        # Blocks
        ##################################################

        self.rx_bits = blocks.unpack_k_bits_bb(k)
        self.demap = digital.constellation_decoder_cb(constellation_object)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.demap, 0), (self.rx_bits, 0))
        self.connect((self, 0), (self.demap, 0))
        self.connect((self.rx_bits, 0), (self, 0))


    def get_order(self):
        return self.order

    def set_order(self, order):
        self.order = order
        self.set_k(int(math.log2(self.order)))
        self.set_constellation_object(digital.constellation_calcdist(wlan_constellation(self.order).tolist(),list(range(self.order)),1,1,digital.constellation.NO_NORMALIZATION).base())

    def get_k(self):
        return self.k

    def set_k(self, k):
        self.k = k

    def get_constellation_object(self):
        return self.constellation_object

    def set_constellation_object(self, constellation_object):
        self.constellation_object = constellation_object
        self.demap.set_constellation(self.constellation_object)

