# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: SISO channel | FIR + CFO + AWGN
# Description: Editable stock-block stage. See docs/MODULAR_FLOWGRAPHS.md.
# GNU Radio version: 3.10.12.0

from gnuradio import analog
from gnuradio import blocks
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
import math
import numpy as np
from antenna_bench.paths import ROOT
from antenna_bench.live import test_bits, wlan_reference, burst_waveform, reference_symbols, parse_taps
from antenna_bench.wlan import wlan_constellation
from gnuradio import digital
import threading







class bench_fir_channel(gr.hier_block2):
    def __init__(self, channel_gain=1, channel_taps='1+0j', cfo_hz=0, sample_rate=20000000.0, noise_voltage=0.1, noise_seed=20261017):
        gr.hier_block2.__init__(
            self, "SISO channel | FIR + CFO + AWGN",
                gr.io_signature(1, 1, gr.sizeof_gr_complex*1),
                gr.io_signature(1, 1, gr.sizeof_gr_complex*1),
        )

        ##################################################
        # Parameters
        ##################################################
        self.channel_gain = channel_gain
        self.channel_taps = channel_taps
        self.cfo_hz = cfo_hz
        self.sample_rate = sample_rate
        self.noise_voltage = noise_voltage
        self.noise_seed = noise_seed

        ##################################################
        # Blocks
        ##################################################

        self.siso_fir = filter.fir_filter_ccc(1, [channel_gain*t for t in parse_taps(channel_taps)])
        self.siso_fir.declare_sample_delay(0)
        self.channel_output = blocks.add_vcc(1)
        self.carrier_offset = blocks.rotator_cc((2*math.pi*cfo_hz/sample_rate), False)
        self.awgn = analog.noise_source_c(analog.GR_GAUSSIAN, noise_voltage, noise_seed)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.awgn, 0), (self.channel_output, 1))
        self.connect((self.carrier_offset, 0), (self.channel_output, 0))
        self.connect((self.channel_output, 0), (self, 0))
        self.connect((self, 0), (self.siso_fir, 0))
        self.connect((self.siso_fir, 0), (self.carrier_offset, 0))


    def get_channel_gain(self):
        return self.channel_gain

    def set_channel_gain(self, channel_gain):
        self.channel_gain = channel_gain
        self.siso_fir.set_taps([self.channel_gain*t for t in parse_taps(self.channel_taps)])

    def get_channel_taps(self):
        return self.channel_taps

    def set_channel_taps(self, channel_taps):
        self.channel_taps = channel_taps
        self.siso_fir.set_taps([self.channel_gain*t for t in parse_taps(self.channel_taps)])

    def get_cfo_hz(self):
        return self.cfo_hz

    def set_cfo_hz(self, cfo_hz):
        self.cfo_hz = cfo_hz
        self.carrier_offset.set_phase_inc((2*math.pi*self.cfo_hz/self.sample_rate))

    def get_sample_rate(self):
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
        self.carrier_offset.set_phase_inc((2*math.pi*self.cfo_hz/self.sample_rate))

    def get_noise_voltage(self):
        return self.noise_voltage

    def set_noise_voltage(self, noise_voltage):
        self.noise_voltage = noise_voltage
        self.awgn.set_amplitude(self.noise_voltage)

    def get_noise_seed(self):
        return self.noise_seed

    def set_noise_seed(self, noise_seed):
        self.noise_seed = noise_seed

