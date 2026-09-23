import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from universal_stratigraphic_events import (
    classify_missing_interval, deposit_on_surface, truncate_by_erosion,
    validate_erosional_event, validate_event_sequence,
)


class UniversalStratigraphicEventTests(unittest.TestCase):
    def test_erosion_truncates_old_units_before_deposition(self):
        units = [{"unitId": "young-old", "top": [100], "bottom": [90]},
                 {"unitId": "old", "top": [90], "bottom": [70]}]
        result = truncate_by_erosion(units, [85])
        self.assertFalse(result["units"][0]["active"][0])
        self.assertEqual(result["units"][1]["top"], [85])
        self.assertEqual(result["totalRemovedThickness"], [15])
        self.assertTrue(validate_erosional_event(result)["passed"])

    def test_younger_unit_uses_event_surface_as_its_base(self):
        unit = deposit_on_surface("basal-gravel", [85, 80], [5, 0])
        self.assertEqual(unit["bottom"], [85, 80])
        self.assertEqual(unit["top"], [90, 80])
        self.assertEqual(unit["active"], [True, False])

    def test_absence_alone_remains_ambiguous(self):
        result = classify_missing_interval({})
        self.assertEqual(result["state"], "Ambiguous")
        self.assertFalse(result["absenceAloneProvesErosion"])

    def test_nonpenetration_and_erosion_evidence_are_distinguished(self):
        self.assertEqual(classify_missing_interval(
            {"penetratedExpectedDepth": False})["state"], "Nonpenetration")
        self.assertEqual(classify_missing_interval(
            {"erosionalSurfaceObserved": True, "basalLagObserved": True})["state"],
            "ErosionSupported")

    def test_conflicting_evidence_is_not_forced(self):
        result = classify_missing_interval(
            {"erosionalSurfaceObserved": True, "lateralThicknessConvergence": True})
        self.assertEqual(result["state"], "ConflictingEvidence")

    def test_invalid_event_chronology_is_rejected(self):
        report = validate_event_sequence([
            {"eventId": "E1", "eventType": "Erosion"},
            {"eventId": "D1", "eventType": "Deposition"},
        ])
        self.assertFalse(report["passed"])
        self.assertEqual(report["errors"][0]["code"], "ErosionBeforeAnyDeposition")

    def test_negative_depositional_thickness_is_rejected(self):
        with self.assertRaises(ValueError):
            deposit_on_surface("bad", [0], [-1])


if __name__ == "__main__":
    unittest.main()
