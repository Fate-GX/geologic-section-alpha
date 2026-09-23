import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from universal_compaction_diagenesis import (
    athy_porosity, classify_diagenetic_evidence, compact_stack,
    transform_thickness, validate_compacted_stack,
)


class UniversalCompactionDiagenesisTests(unittest.TestCase):
    def test_athy_porosity_decreases_with_depth(self):
        self.assertLess(athy_porosity(1000, 0.6, 0.0005), athy_porosity(0, 0.6, 0.0005))

    def test_solid_volume_is_preserved(self):
        result = transform_thickness(100, 0.5, 0.25)
        self.assertAlmostEqual(result["targetThickness"], 100 * 0.5 / 0.75)
        self.assertEqual(result["solidThickness"], 50)

    def test_decompaction_is_inverse_when_porosity_states_are_reversed(self):
        compacted = transform_thickness(100, 0.5, 0.2)
        restored = transform_thickness(compacted["targetThickness"], 0.2, 0.5)
        self.assertAlmostEqual(restored["targetThickness"], 100)

    def test_differential_compaction_changes_relief_but_preserves_shared_contacts(self):
        units = compact_stack([100, 100], [[20, 20], [10, 10]],
                              [[0.5, 0.5], [0.4, 0.4]],
                              [[0.2, 0.35], [0.2, 0.2]])
        self.assertNotEqual(units[0]["bottom"][0], units[0]["bottom"][1])
        self.assertEqual(units[0]["bottom"], units[1]["top"])
        self.assertTrue(validate_compacted_stack(units)["passed"])

    def test_porosity_increase_is_not_compaction(self):
        with self.assertRaises(ValueError):
            compact_stack([100], [[10]], [[0.3]], [[0.5]])

    def test_lithology_name_does_not_authorize_diagenesis(self):
        result = classify_diagenetic_evidence({"lithologyName": "mudstone"})
        self.assertEqual(result["state"], "Unresolved")
        self.assertFalse(result["lithologyNameAloneIsSufficient"])

    def test_overpressure_requires_history_dependent_model(self):
        result = classify_diagenetic_evidence({"overpressureObserved": True})
        self.assertTrue(result["requiresHistoryDependentModel"])


if __name__ == "__main__":
    unittest.main()
