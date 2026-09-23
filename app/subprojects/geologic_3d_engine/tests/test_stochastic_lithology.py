import pathlib
import sys
import unittest

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from geologic_3d_engine.stochastic_lithology import (
    classify_surface_constraint, compare_training_image_signatures,
    experimental_semivariance, indicator_vector, select_stochastic_method,
    training_image_signature, validate_hierarchical_records,
)


class StochasticLithologyTests(unittest.TestCase):
    def test_indicator_is_one_hot(self):
        self.assertEqual(indicator_vector("sand", ["mud", "sand", "gravel"]), [0, 1, 0])

    def test_contact_inequality_is_preserved(self):
        self.assertEqual(classify_surface_constraint(lower_bound=10)["constraintType"], "LowerBound")
        self.assertEqual(classify_surface_constraint()["constraintType"], "Unresolved")

    def test_same_facies_in_two_units_is_partitioned(self):
        report = validate_hierarchical_records([
            {"unitId": "U1", "faciesId": "sand"},
            {"unitId": "U2", "faciesId": "sand"},
        ])
        self.assertTrue(report["faciesPartitions"][0]["mustSimulateSeparatelyByUnit"])

    def test_training_image_signature_is_directional(self):
        grid = [[[0, 0, 1], [0, 1, 1]]]
        signature = training_image_signature(grid, [0, 1])
        self.assertNotEqual(signature["directionalTransitions"]["x"],
                            signature["directionalTransitions"]["y"])

    def test_training_image_comparison_never_auto_authorizes(self):
        signature = training_image_signature([[[0, 1]]], [0, 1])
        report = compare_training_image_signatures(signature, signature)
        self.assertEqual(report["proportionL1"], 0)
        self.assertFalse(report["automaticallyAuthorized"])

    def test_semivariance_uses_supplied_pairs(self):
        result = experimental_semivariance([0, 2, 4], {1: [(0, 1), (1, 2)]})
        self.assertEqual(result["1"], 2)

    def test_mps_requires_applicable_training_image(self):
        report = select_stochastic_method({"unitDomainDefined": True, "trainingImage": "ti"})
        self.assertNotIn("MultiplePointStatistics", report["authorizedMethods"])
        self.assertIn("TrainingImageApplicabilityUnverified", report["blockers"])

    def test_full_mps_evidence_authorizes_method(self):
        evidence = {key: True for key in (
            "unitDomainDefined", "trainingImage", "trainingImageProvenance",
            "scaleCompatibility", "orientationCompatibility", "environmentCompatibility",
            "trainingImageDiagnosticsPassed")}
        self.assertIn("MultiplePointStatistics",
                      select_stochastic_method(evidence)["authorizedMethods"])

    def test_undefined_unit_domain_blocks_all_facies_simulation(self):
        report = select_stochastic_method({"singleFaciesOnly": True})
        self.assertEqual(report["authorizedMethods"], [])


if __name__ == "__main__":
    unittest.main()
