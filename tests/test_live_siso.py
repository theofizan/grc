"""End-to-end SISO receiver gates beyond ideal aligned AWGN scoring."""
import unittest
import numpy as np
from scipy.signal import lfilter
from antenna_bench.live import wlan_reference, burst_waveform, recover_burst, parse_taps
from antenna_bench.wlan import demap


class SisoReceiverTests(unittest.TestCase):
    def test_fixed_active_burst_power_all_rates(self):
        for rate in range(8):
            ref=wlan_reference(rate)
            self.assertAlmostEqual(float(np.mean(abs(ref['tx_packet'])**2)),1,places=12)
            np.testing.assert_array_equal(burst_waveform(rate)[-2000:],0)

    def test_noiseless_data_recovery_all_rates(self):
        for rate in range(8):
            ref=wlan_reference(rate)
            recovered,_=recover_burst(ref['tx_packet'],ref,False,False)
            np.testing.assert_allclose(recovered,ref['reference_symbols'],atol=1e-7)

    def test_cfo_and_multipath_recovery_uses_training(self):
        ref=wlan_reference(4); fs=float(ref['fs']); frequency=20000
        received=lfilter([.7,.2+.15j,0,-.1j],[1],ref['tx_packet'])
        received*=np.exp(2j*np.pi*frequency*np.arange(received.size)/fs)
        recovered,estimate=recover_burst(received,ref,True,True)
        self.assertAlmostEqual(estimate,frequency,places=5)
        np.testing.assert_allclose(recovered,ref['reference_symbols'],atol=1e-6)
        np.testing.assert_array_equal(demap(recovered.ravel(order='F'),16),
                                      ref['reference_coded_bits'].ravel(order='F'))

    def test_uncorrected_cfo_is_a_failing_control(self):
        ref=wlan_reference(4); rx=ref['tx_packet']*np.exp(2j*np.pi*20000*np.arange(ref['tx_packet'].size)/ref['fs'])
        good,_=recover_burst(rx,ref,True,True); bad,_=recover_burst(rx,ref,False,False)
        self.assertLess(float(np.mean(abs(good-ref['reference_symbols'])**2)),1e-10)
        self.assertGreater(float(np.mean(abs(bad-ref['reference_symbols'])**2)),.1)

    def test_taps_are_bounded_finite_causal(self):
        self.assertEqual(parse_taps('1, 0.2+0.1j'),[1+0j,.2+.1j])
        for taps in ('0','nan','1,'*17+'1'):
            with self.assertRaises((ValueError,SyntaxError)): parse_taps(taps)


if __name__=='__main__': unittest.main()
