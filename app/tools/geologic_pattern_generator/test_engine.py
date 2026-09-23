import json
import pathlib
import unittest

from engine import generate, load_catalog
from physics_validator import run as run_physics_validation
from terrain_robustness_validator import run as run_terrain_robustness


HERE = pathlib.Path(__file__).resolve().parent


class PatternGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(HERE / "process_catalog.json")
        cls.terrain = [{"distance_m": i * 10.0, "elevation_m": 100.0 + i}
                       for i in range(11)]

    def test_example_generates_positive_non_crossing_bodies(self):
        config = json.loads((HERE / "example_config.json").read_text(encoding="utf-8"))
        result = generate(config, self.terrain, self.catalog)
        self.assertTrue(result["passed"])
        for unit in result["units"]:
            self.assertTrue(all(bottom <= top for top, bottom in zip(unit["top"], unit["bottom"])))
        lava = next(unit for unit in result["units"] if unit["processId"] == "lava_flow")
        self.assertFalse(lava["active"][0])
        self.assertFalse(lava["active"][-1])

    def test_out_of_range_parameter_is_rejected(self):
        config = json.loads((HERE / "example_config.json").read_text(encoding="utf-8"))
        config["units"][0]["parameters"]["minimum"] = -1.0
        result = generate(config, self.terrain, self.catalog)
        self.assertFalse(result["passed"])
        self.assertTrue(any(error["code"] == "ParameterOutOfRange" for error in result["errors"]))

    def test_structural_model_cannot_use_stack_engine(self):
        config = {"profileId": "NEGATIVE_STRUCTURAL", "units": [{
            "unitId": "folded_bedrock", "processId": "folded_or_faulted_bedrock",
            "parameters": {}, "evidenceTags": ["structural_attitudes", "fault_or_fold_controls"]
        }]}
        result = generate(config, self.terrain, self.catalog)
        self.assertFalse(result["passed"])
        self.assertTrue(any(error["code"] == "RequiresDedicatedTopologyEngine" for error in result["errors"]))

    def test_process_catalog_physics_sweep(self):
        report = run_physics_validation(HERE / "process_catalog.json", cases=20)
        self.assertTrue(report["passed"], json.dumps(report, ensure_ascii=False, indent=2))

    def test_random_terrain_robustness(self):
        report = run_terrain_robustness(HERE / "process_catalog.json", seeds=3)
        self.assertTrue(report["passed"], json.dumps(report["failures"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    unittest.main()
