import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from quantitative_scaling import (
    UnverifiedRelationError,
    calibrated_power_law,
    meander_radius_width_diagnostic,
    relative_lava_length_from_effusion_rate,
    relative_lava_length_from_volume,
    tephra_thickness_half_distance,
    unverified_alluvial_fan_volume_area_relation,
)


class QuantitativeScalingTests(unittest.TestCase):
    def test_tephra_halves_at_each_half_distance(self):
        self.assertAlmostEqual(tephra_thickness_half_distance(8, 10, 10).value, 4)
        self.assertAlmostEqual(tephra_thickness_half_distance(8, 20, 10).value, 2)

    def test_lava_scaling_is_reference_calibrated(self):
        self.assertAlmostEqual(relative_lava_length_from_volume(1000, 2e6, 1e6).value,
                               1000 * 2 ** 0.67)
        self.assertAlmostEqual(relative_lava_length_from_effusion_rate(1000, 20, 10).value,
                               1000 * 2 ** 0.60)

    def test_invalid_or_untraceable_values_are_blocked(self):
        with self.assertRaises(ValueError):
            tephra_thickness_half_distance(8, 10, 0)
        with self.assertRaises(ValueError):
            calibrated_power_law(10, 2, .5, input_unit="", output_unit="m",
                                 source_id="S", rule_id="R", scope="Domain")

    def test_meander_ratio_is_a_soft_diagnostic(self):
        self.assertEqual(meander_radius_width_diagnostic(25, 10)["status"],
                         "WithinReportedModalRange")
        result = meander_radius_width_diagnostic(10, 10)
        self.assertFalse(result["hardGate"])
        self.assertEqual(result["status"], "OutsideModalRange_NotRejected")

    def test_unverified_fan_formula_cannot_execute(self):
        with self.assertRaises(UnverifiedRelationError):
            unverified_alluvial_fan_volume_area_relation(10)


if __name__ == "__main__":
    unittest.main()
