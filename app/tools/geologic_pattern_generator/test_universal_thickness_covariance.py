import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from universal_thickness_covariance import (
    cholesky_psd, correlated_lognormal_thickness, exponential_spatial_correlation,
    stack_from_thickness_fields, validate_shared_contact_stack,
)


class UniversalThicknessCovarianceTests(unittest.TestCase):
    def test_correlation_couples_layers_and_preserves_nonnegative_thickness(self):
        values = correlated_lognormal_thickness(
            [10, 20], [.3, .3], [[1, .8], [.8, 1]], [1, 0])
        self.assertTrue(all(x > 0 for x in values))
        self.assertGreater(values[1], 20 * __import__("math").exp(-.5 * .3 ** 2))

    def test_zero_thickness_is_explicit_pinchout(self):
        values = correlated_lognormal_thickness(
            [10, 20], [.2, .2], [[1, 0], [0, 1]], [0, 0], active=[False, True])
        self.assertEqual(values[0], 0)
        self.assertGreater(values[1], 0)

    def test_invalid_covariance_is_rejected(self):
        with self.assertRaises(ValueError):
            cholesky_psd([[1, 2], [2, 1]])

    def test_spatial_correlation_uses_normalized_range(self):
        self.assertAlmostEqual(exponential_spatial_correlation(10, 10),
                               __import__("math").exp(-1))

    def test_stacking_guarantees_shared_non_crossing_contacts(self):
        units = stack_from_thickness_fields([100, 110], [[10, 0], [5, 6]])
        report = validate_shared_contact_stack(units)
        self.assertTrue(report["passed"])
        self.assertEqual(units[0]["bottom"], units[1]["top"])
        self.assertFalse(report["independentBoundaryPerturbationAllowed"])


if __name__ == "__main__":
    unittest.main()
