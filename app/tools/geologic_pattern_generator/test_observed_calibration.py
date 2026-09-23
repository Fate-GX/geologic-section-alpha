import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from observed_calibration import (compare_buried_valley_candidate,
                                  load_observed_calibration, make_calibration_report)


class ObservedCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_observed_calibration(
            ROOT / "research/geologic_dwg_generation/datasets/observed_calibration_kujukuri_buried_valley.json")

    def test_exact_published_dimensions_preserve_evidence_but_do_not_auto_pass(self):
        result = compare_buried_valley_candidate(
            self.data, width_m=200, depth_m=10,
            observation_id="COASTAL-CENTRAL-SMALL-VALLEY")
        self.assertEqual(result["candidateAspectRatio"], 20)
        self.assertFalse(result["passed"])
        self.assertEqual(result["decision"], "RequiresExplicitToleranceFromStudyDesign")

    def test_no_observed_dataset_can_be_promoted_without_tolerance_policy(self):
        comparison = compare_buried_valley_candidate(
            self.data, width_m=200, depth_m=10,
            observation_id="COASTAL-CENTRAL-SMALL-VALLEY")
        report = make_calibration_report(self.data, [comparison])
        self.assertFalse(report["passed"])
        self.assertEqual(report["state"], "ObservedButNotYetThresholdCalibrated")


if __name__ == "__main__":
    unittest.main()
