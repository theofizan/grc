#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Uncoded BER and EVM: aligned symbol AWGN
# Author: Antenna benchmark project
# Description: Exact uncoded-theory diagnostic with finite captures and external metrics. Not an 802.11 PHY.
# GNU Radio version: 3.10.12.0

from antenna_bench.paths import ROOT
from antenna_bench.math import make_symbols
import math
from gnuradio import analog
from gnuradio import blocks
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import threading




class awgn_symbol_benchmark(gr.top_block):

    def __init__(self, order=16, ebno_db=8, symbol_count=100000, seed=20261016):
        gr.top_block.__init__(self, "Uncoded BER and EVM: aligned symbol AWGN", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Parameters
        ##################################################
        self.order = order
        self.ebno_db = ebno_db
        self.symbol_count = symbol_count
        self.seed = seed

        ##################################################
        # Variables
        ##################################################
        self.noise_voltage = noise_voltage = math.sqrt(1/(math.log2(order)*10**(ebno_db/10)))

        ##################################################
        # Blocks
        ##################################################

        self.transmitted_symbols = blocks.file_sink(gr.sizeof_gr_complex*1, str(ROOT / 'results/grc/symbol_tx.c64'), False)
        self.transmitted_symbols.set_unbuffered(False)
        self.reference_symbols = blocks.vector_source_c(make_symbols(order, symbol_count, seed).tolist(), False, 1, [])
        self.received_symbols = blocks.file_sink(gr.sizeof_gr_complex*1, str(ROOT / 'results/grc/symbol_rx.c64'), False)
        self.received_symbols.set_unbuffered(False)
        self.complex_awgn = analog.noise_source_c(analog.GR_GAUSSIAN, noise_voltage, (seed+1))
        self.add_noise = blocks.add_vcc(1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.add_noise, 0), (self.received_symbols, 0))
        self.connect((self.complex_awgn, 0), (self.add_noise, 1))
        self.connect((self.reference_symbols, 0), (self.add_noise, 0))
        self.connect((self.reference_symbols, 0), (self.transmitted_symbols, 0))


    def get_order(self):
        return self.order

    def set_order(self, order):
        self.order = order
        self.set_noise_voltage(math.sqrt(1/(math.log2(self.order)*10**(self.ebno_db/10))))
        self.reference_symbols.set_data(make_symbols(self.order, self.symbol_count, self.seed).tolist(), [])

    def get_ebno_db(self):
        return self.ebno_db

    def set_ebno_db(self, ebno_db):
        self.ebno_db = ebno_db
        self.set_noise_voltage(math.sqrt(1/(math.log2(self.order)*10**(self.ebno_db/10))))

    def get_symbol_count(self):
        return self.symbol_count

    def set_symbol_count(self, symbol_count):
        self.symbol_count = symbol_count
        self.reference_symbols.set_data(make_symbols(self.order, self.symbol_count, self.seed).tolist(), [])

    def get_seed(self):
        return self.seed

    def set_seed(self, seed):
        self.seed = seed
        self.reference_symbols.set_data(make_symbols(self.order, self.symbol_count, self.seed).tolist(), [])

    def get_noise_voltage(self):
        return self.noise_voltage

    def set_noise_voltage(self, noise_voltage):
        self.noise_voltage = noise_voltage
        self.complex_awgn.set_amplitude(self.noise_voltage)



def argument_parser():
    description = 'Exact uncoded-theory diagnostic with finite captures and external metrics. Not an 802.11 PHY.'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--order", dest="order", type=intx, default=16,
        help="Set Constellation order M [default=%(default)r]")
    parser.add_argument(
        "--ebno-db", dest="ebno_db", type=eng_float, default=eng_notation.num_to_str(float(8)),
        help="Set Uncoded Eb/N0 (dB) [default=%(default)r]")
    parser.add_argument(
        "--symbol-count", dest="symbol_count", type=intx, default=100000,
        help="Set Number of symbols [default=%(default)r]")
    parser.add_argument(
        "--seed", dest="seed", type=intx, default=20261016,
        help="Set Noise/reference seed [default=%(default)r]")
    return parser


def main(top_block_cls=awgn_symbol_benchmark, options=None):
    if options is None:
        options = argument_parser().parse_args()
    tb = top_block_cls(order=options.order, ebno_db=options.ebno_db, symbol_count=options.symbol_count, seed=options.seed)

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
