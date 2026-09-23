import math
import unittest

from geologic_3d_engine.section.resistivity_evidence import (
    assess_resistivity_interpretation,
    schlumberger_apparent_resistivity,
)


def interpretation(**changes):
    value = {
        "sourceId": "SYNTHETIC-VES",
        "method": "SchlumbergerVES",
        "rawMeasurementsAvailable": True,
        "soundingCoordinatesAvailable": True,
        "inversionDetailsAvailable": True,
        "horizontalReferenceStatus": "Verified",
        "verticalReferenceStatus": "Verified",
        "interpretedLayers": [
            {"topDepthM": 0.0, "bottomDepthM": 4.0, "resistivityOhmM": 120.0},
            {"topDepthM": 4.0, "bottomDepthM": 20.0, "resistivityOhmM": 600.0},
        ],
        "lithologyCalibrationStatus": "CollocatedObservedLithology",
        "independentReviewStatus": "IndependentlyVerified",
    }
    value.update(changes)
    return value


class ResistivityEvidenceTests(unittest.TestCase):
    def test_schlumberger_formula_matches_direct_calculation(self):
        result = schlumberger_apparent_resistivity(
            potential_difference_v=0.1, current_a=0.01,
            current_electrode_spacing_m=10.0,
            potential_electrode_spacing_m=2.0)
        self.assertAlmostEqual(result["geometricFactorM"], 12.0 * math.pi)
        self.assertAlmostEqual(result["apparentResistivityOhmM"], 120.0 * math.pi)

    def test_invalid_array_geometry_and_nonfinite_inputs_reject(self):
        with self.assertRaises(ValueError):
            schlumberger_apparent_resistivity(
                potential_difference_v=0.1, current_a=0.01,
                current_electrode_spacing_m=9.9,
                potential_electrode_spacing_m=2.0)
        with self.assertRaises(ValueError):
            schlumberger_apparent_resistivity(
                potential_difference_v=float("nan"), current_a=0.01,
                current_electrode_spacing_m=10.0,
                potential_electrode_spacing_m=2.0)

    def test_complete_calibration_and_review_can_authorize_lithology(self):
        result = assess_resistivity_interpretation(interpretation())
        self.assertTrue(result["physicalPropertyConstraintAuthorized"])
        self.assertTrue(result["lithologyBoundaryAuthorized"])

    def test_summary_without_raw_coordinates_or_inversion_is_context_only(self):
        result = assess_resistivity_interpretation(interpretation(
            rawMeasurementsAvailable=False,
            soundingCoordinatesAvailable=False,
            inversionDetailsAvailable=False,
            interpretedLayers=[],
            horizontalReferenceStatus="Unverified",
            verticalReferenceStatus="Unverified",
            lithologyCalibrationStatus="InterpretiveAnalogyOnly",
            independentReviewStatus="Unreviewed"))
        self.assertFalse(result["physicalPropertyConstraintAuthorized"])
        self.assertFalse(result["lithologyBoundaryAuthorized"])
        self.assertIn("RawMeasurementsUnavailable", result["blockingReasons"])
        self.assertIn("InterpretedLayerGeometryUnavailable", result["blockingReasons"])

    def test_physical_boundary_never_becomes_lithology_without_collocated_calibration(self):
        result = assess_resistivity_interpretation(interpretation(
            lithologyCalibrationStatus="RegionalInterpretationOnly"))
        self.assertTrue(result["physicalPropertyConstraintAuthorized"])
        self.assertFalse(result["lithologyBoundaryAuthorized"])

    def test_layer_gap_and_negative_resistivity_reject(self):
        bad = interpretation()
        bad["interpretedLayers"][1]["topDepthM"] = 5.0
        with self.assertRaises(ValueError):
            assess_resistivity_interpretation(bad)
        bad = interpretation()
        bad["interpretedLayers"][0]["resistivityOhmM"] = -1.0
        with self.assertRaises(ValueError):
            assess_resistivity_interpretation(bad)


if __name__ == "__main__":
    unittest.main()
