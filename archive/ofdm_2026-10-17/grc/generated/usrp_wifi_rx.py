#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: USRP legacy Wi-Fi finite raw IQ capture
# Author: Antenna benchmark project
# Description: UHD hardware integration graph. RF/streaming, timed acquisition and antenna control require hardware commissioning.
# GNU Radio version: 3.10.12.0

from antenna_bench.paths import ROOT
from antenna_bench.math import make_symbols
import math
from gnuradio import blocks
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




class usrp_wifi_rx(gr.top_block):

    def __init__(self, center_frequency=5180000000.0, gain_db=20, device_args='type=x300,addr=192.168.10.2', capture_samples=2000000):
        gr.top_block.__init__(self, "USRP legacy Wi-Fi finite raw IQ capture", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Parameters
        ##################################################
        self.center_frequency = center_frequency
        self.gain_db = gain_db
        self.device_args = device_args
        self.capture_samples = capture_samples

        ##################################################
        # Variables
        ##################################################
        self.sample_rate = sample_rate = 20e6

        ##################################################
        # Blocks
        ##################################################

        self.usrp_source = uhd.usrp_source(
            ",".join((device_args, '')),
            uhd.stream_args(
                cpu_format="fc32",
                otw_format="sc16",
                args='',
                channels=list(range(0,1)),
            ),
        )
        self.usrp_source.set_clock_source('internal', 0)
        self.usrp_source.set_samp_rate(sample_rate)
        # No synchronization enforced.

        self.usrp_source.set_center_freq(center_frequency, 0)
        self.usrp_source.set_antenna("RX2", 0)
        self.usrp_source.set_gain(gain_db, 0)
        self.raw_iq = blocks.file_sink(gr.sizeof_gr_complex*1, str(ROOT / 'results/grc/usrp_rx.c64'), False)
        self.raw_iq.set_unbuffered(False)
        self.finite_capture = blocks.head(gr.sizeof_gr_complex*1, capture_samples)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.finite_capture, 0), (self.raw_iq, 0))
        self.connect((self.usrp_source, 0), (self.finite_capture, 0))


    def get_center_frequency(self):
        return self.center_frequency

    def set_center_frequency(self, center_frequency):
        self.center_frequency = center_frequency
        self.usrp_source.set_center_freq(self.center_frequency, 0)

    def get_gain_db(self):
        return self.gain_db

    def set_gain_db(self, gain_db):
        self.gain_db = gain_db
        self.usrp_source.set_gain(self.gain_db, 0)

    def get_device_args(self):
        return self.device_args

    def set_device_args(self, device_args):
        self.device_args = device_args

    def get_capture_samples(self):
        return self.capture_samples

    def set_capture_samples(self, capture_samples):
        self.capture_samples = capture_samples
        self.finite_capture.set_length(self.capture_samples)

    def get_sample_rate(self):
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
        self.usrp_source.set_samp_rate(self.sample_rate)



def argument_parser():
    description = 'UHD hardware integration graph. RF/streaming, timed acquisition and antenna control require hardware commissioning.'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--center-frequency", dest="center_frequency", type=eng_float, default=eng_notation.num_to_str(float(5180000000.0)),
        help="Set RF center frequency (Hz) [default=%(default)r]")
    parser.add_argument(
        "--gain-db", dest="gain_db", type=eng_float, default=eng_notation.num_to_str(float(20)),
        help="Set USRP gain (dB) [default=%(default)r]")
    parser.add_argument(
        "--device-args", dest="device_args", type=str, default='type=x300,addr=192.168.10.2',
        help="Set UHD device address [default=%(default)r]")
    parser.add_argument(
        "--capture-samples", dest="capture_samples", type=intx, default=2000000,
        help="Set Complex samples to capture [default=%(default)r]")
    return parser


def main(top_block_cls=usrp_wifi_rx, options=None):
    if options is None:
        options = argument_parser().parse_args()
    tb = top_block_cls(center_frequency=options.center_frequency, gain_db=options.gain_db, device_args=options.device_args, capture_samples=options.capture_samples)

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
