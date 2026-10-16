#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: USRP legacy Wi-Fi transmit reference IQ
# Author: Antenna benchmark project
# Description: UHD hardware integration graph. RF/streaming, timed acquisition and antenna control require hardware commissioning.
# GNU Radio version: 3.10.12.0

from antenna_bench.paths import ROOT
from antenna_bench.math import make_symbols
import math
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
from gnuradio import uhd
import time
import threading




class usrp_wifi_tx(gr.top_block):

    def __init__(self, center_frequency=5180000000.0, gain_db=0, device_args='type=x300,addr=192.168.10.2', rate_index=2):
        gr.top_block.__init__(self, "USRP legacy Wi-Fi transmit reference IQ", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Parameters
        ##################################################
        self.center_frequency = center_frequency
        self.gain_db = gain_db
        self.device_args = device_args
        self.rate_index = rate_index

        ##################################################
        # Variables
        ##################################################
        self.sample_rate = sample_rate = 20e6

        ##################################################
        # Blocks
        ##################################################

        self.wifi_reference = blocks.file_source(gr.sizeof_gr_complex*1, str(ROOT / ('results/reference/wlan_rate_%d_tx.c64' % rate_index)), False, 0, 0)
        self.wifi_reference.set_begin_tag(pmt.PMT_NIL)
        self.usrp_sink = uhd.usrp_sink(
            ",".join((device_args, '')),
            uhd.stream_args(
                cpu_format="fc32",
                otw_format="sc16",
                args='',
                channels=list(range(0,1)),
            ),
            "",
        )
        self.usrp_sink.set_clock_source('internal', 0)
        self.usrp_sink.set_samp_rate(sample_rate)
        # No synchronization enforced.

        self.usrp_sink.set_center_freq(center_frequency, 0)
        self.usrp_sink.set_antenna("TX/RX", 0)
        self.usrp_sink.set_gain(gain_db, 0)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.wifi_reference, 0), (self.usrp_sink, 0))


    def get_center_frequency(self):
        return self.center_frequency

    def set_center_frequency(self, center_frequency):
        self.center_frequency = center_frequency
        self.usrp_sink.set_center_freq(self.center_frequency, 0)

    def get_gain_db(self):
        return self.gain_db

    def set_gain_db(self, gain_db):
        self.gain_db = gain_db
        self.usrp_sink.set_gain(self.gain_db, 0)

    def get_device_args(self):
        return self.device_args

    def set_device_args(self, device_args):
        self.device_args = device_args

    def get_rate_index(self):
        return self.rate_index

    def set_rate_index(self, rate_index):
        self.rate_index = rate_index
        self.wifi_reference.open(str(ROOT / ('results/reference/wlan_rate_%d_tx.c64' % self.rate_index)), False)

    def get_sample_rate(self):
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
        self.usrp_sink.set_samp_rate(self.sample_rate)



def argument_parser():
    description = 'UHD hardware integration graph. RF/streaming, timed acquisition and antenna control require hardware commissioning.'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--center-frequency", dest="center_frequency", type=eng_float, default=eng_notation.num_to_str(float(5180000000.0)),
        help="Set RF center frequency (Hz) [default=%(default)r]")
    parser.add_argument(
        "--gain-db", dest="gain_db", type=eng_float, default=eng_notation.num_to_str(float(0)),
        help="Set USRP gain (dB) [default=%(default)r]")
    parser.add_argument(
        "--device-args", dest="device_args", type=str, default='type=x300,addr=192.168.10.2',
        help="Set UHD device address [default=%(default)r]")
    parser.add_argument(
        "--rate-index", dest="rate_index", type=intx, default=2,
        help="Set Legacy rate index (0-7) [default=%(default)r]")
    return parser


def main(top_block_cls=usrp_wifi_tx, options=None):
    if options is None:
        options = argument_parser().parse_args()
    tb = top_block_cls(center_frequency=options.center_frequency, gain_db=options.gain_db, device_args=options.device_args, rate_index=options.rate_index)

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
