# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: SISO scalar channel | loss + AWGN
# Description: Editable stock-block stage. See docs/MODULAR_FLOWGRAPHS.md.
# GNU Radio version: 3.10.12.0

from gnuradio import analog
from gnuradio import blocks
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
import threading







class bench_scalar_channel(gr.hier_block2):
    def __init__(self, channel_gain=1, noise_voltage=0.1, noise_seed=20261017):
        gr.hier_block2.__init__(
            self, "SISO scalar channel | loss + AWGN",
                gr.io_signature(1, 1, gr.sizeof_gr_complex*1),
                gr.io_signature(1, 1, gr.sizeof_gr_complex*1),
        )

        ##################################################
        # Parameters
        ##################################################
        self.channel_gain = channel_gain
        self.noise_voltage = noise_voltage
        self.noise_seed = noise_seed

        ##################################################
        # Blocks
        ##################################################

        self.siso_path = blocks.multiply_const_cc(channel_gain)
        self.channel_output = blocks.add_vcc(1)
        self.awgn = analog.noise_source_c(analog.GR_GAUSSIAN, noise_voltage, noise_seed)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.awgn, 0), (self.channel_output, 1))
        self.connect((self.channel_output, 0), (self, 0))
        self.connect((self, 0), (self.siso_path, 0))
        self.connect((self.siso_path, 0), (self.channel_output, 0))


    def get_channel_gain(self):
        return self.channel_gain

    def set_channel_gain(self, channel_gain):
        self.channel_gain = channel_gain
        self.siso_path.set_k(self.channel_gain)

    def get_noise_voltage(self):
        return self.noise_voltage

    def set_noise_voltage(self, noise_voltage):
        self.noise_voltage = noise_voltage
        self.awgn.set_amplitude(self.noise_voltage)

    def get_noise_seed(self):
        return self.noise_seed

    def set_noise_seed(self, noise_seed):
        self.noise_seed = noise_seed

