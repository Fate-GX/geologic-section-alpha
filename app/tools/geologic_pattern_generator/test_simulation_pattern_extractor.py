import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from simulation_pattern_extractor import evaluate_adoption, extract_section_patterns


class SimulationPatternExtractorTests(unittest.TestCase):
    def setUp(self):
        self.model = {"x": [0, 10, 20, 30, 40], "units": [{
            "unitId": "U1", "processId": "channel", "lithology": "sand",
            "top": [10, 10, 10, 10, 10], "bottom": [10, 8, 7, 8, 10]
        }, {
            "unitId": "U2", "processId": "drape", "lithology": "mud",
            "top": [0, 0, 0, 0, 0], "bottom": [-1, -1, -1, -1, -1]
        }]}

    def test_extracts_finite_body_and_transition_statistics(self):
        result = extract_section_patterns(self.model, tool_id="Example",
                                          scenario_id="S1", parameter_manifest_id="P1")
        channel = result["unitMetrics"][0]
        self.assertEqual(channel["connectedBodyCount"], 1)
        self.assertEqual(channel["pinchoutBoundaryCount"], 2)
        self.assertEqual(channel["maximumConnectedLength"], 30)
        self.assertEqual(result["verticalTransitionCounts"][0]["to"], "mud")

    def test_simulation_alone_cannot_be_adopted(self):
        metrics = extract_section_patterns(self.model, tool_id="Example",
                                           scenario_id="S1", parameter_manifest_id="P1")
        self.assertFalse(evaluate_adoption(metrics, None)["adoptable"])
        calibration = {"passed": True, "independentObservedDatasetId": "OBS-1",
                       "applicabilityScope": "Environment:Fluvial"}
        self.assertTrue(evaluate_adoption(metrics, calibration)["adoptable"])


if __name__ == "__main__":
    unittest.main()
