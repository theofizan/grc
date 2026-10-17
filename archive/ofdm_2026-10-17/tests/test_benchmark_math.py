"""Mathematical checks that catch normalization, mapping, and scoring errors."""

import unittest
import numpy as np
from scipy.special import erfc
from antenna_bench.math import (
    constellation,
    symbol_indices,
    index_bits,
    exact_ber,
    score,
    binomial_interval,
    zero_error_upper_bound,
)
from antenna_bench.wlan import wlan_constellation, demap


class BenchmarkMathTests(unittest.TestCase):
    def test_unit_energy_and_bit_round_trip(self):
        for order in (2, 4, 16, 64):
            points = constellation(order)
            self.assertAlmostEqual(float(np.mean(abs(points) ** 2)), 1)
            np.testing.assert_array_equal(
                symbol_indices(order, points), np.arange(order)
            )

    def test_bpsk_and_qpsk_exact_known_probability(self):
        for order in (2, 4):
            self.assertAlmostEqual(float(exact_ber(order, 0)), 0.07864960352514257)
            np.testing.assert_allclose(
                exact_ber(order, [0, 5, 10]),
                0.5 * erfc(np.sqrt(10 ** (np.array([0, 5, 10]) / 10))),
            )

    def test_qam_theory_includes_low_snr_non_nearest_errors(self):
        for order in (16, 64):
            values = exact_ber(order, [-80, 0, 10, 20])
            self.assertAlmostEqual(values[0], 0.5, places=3)
            self.assertTrue(np.all(np.diff(values) < 0))

    def test_known_symbol_errors_and_evm(self):
        tx = np.array([-1, 1, -1, 1], dtype=complex)
        rx = np.array([1, 1, -1, 1], dtype=complex)
        result = score(tx, rx, 2)
        self.assertEqual((result["errors"], result["bits"]), (1, 4))
        self.assertEqual(result["ber"], 0.25)
        self.assertAlmostEqual(result["evm_rms"], 1)

    def test_no_payload_fitting_removes_gain_error(self):
        tx = constellation(16)
        result = score(tx, 1.1 * tx, 16)
        self.assertAlmostEqual(result["evm_rms"], 0.1)
        self.assertEqual(result["errors"], 0)

    def test_one_and_two_sided_zero_error_bounds_are_distinct(self):
        lo, hi = binomial_interval(0, 1000000)
        self.assertEqual(lo, 0)
        self.assertAlmostEqual(zero_error_upper_bound(1000000), 2.995727786352544e-6)
        self.assertGreater(hi, zero_error_upper_bound(1000000))

    def test_misaligned_or_nonfinite_data_is_rejected(self):
        for tx, rx in (
            ([1], [1, 1]),
            ([1], [complex(float("nan"), 0)]),
            ([], []),
            ([0], [0]),
        ):
            with self.assertRaises(ValueError):
                score(tx, rx, 2)

    def test_wlan_normalization_mapping_and_gray_neighbours(self):
        for order in (2, 4, 16, 64):
            points = wlan_constellation(order)
            self.assertAlmostEqual(float(np.mean(abs(points) ** 2)), 1)
            np.testing.assert_array_equal(
                demap(points, order), index_bits(np.arange(order), order)
            )
            distances = abs(points[:, None] - points[None, :])
            np.fill_diagonal(distances, np.inf)
            separation = distances.min()
            for i, j in np.argwhere(np.isclose(distances, separation)):
                self.assertEqual((int(i) ^ int(j)).bit_count(), 1)

    def test_wlan_table82_and_table84_label_examples(self):
        self.assertEqual(wlan_constellation(2)[0], -1)
        self.assertAlmostEqual(wlan_constellation(16)[0], (-3 - 3j) / np.sqrt(10))
        self.assertAlmostEqual(wlan_constellation(16)[15], (1 + 1j) / np.sqrt(10))


if __name__ == "__main__":
    unittest.main()
