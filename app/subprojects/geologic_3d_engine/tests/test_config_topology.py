import copy
import json
import pathlib
import sys
import unittest
from datetime import datetime, timezone

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from geologic_3d_engine.config import EngineConfig, load_config
from geologic_3d_engine.runner import (configuration_fingerprint, create_run_manifest,
                                       validate_stage_one)


EXAMPLE = root / "examples" / "minimal_valid_config.json"


class ConfigTopologyTests(unittest.TestCase):
    def data(self):
        return json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_valid_example_passes_stage_one(self):
        report = validate_stage_one(load_config(EXAMPLE))
        self.assertTrue(report["passed"])
        self.assertEqual(report["decision"], "Experimental")

    def test_invalid_extent_is_rejected(self):
        data = self.data()
        data["extent"]["maximum"][0] = data["extent"]["minimum"][0]
        errors = EngineConfig.from_dict(data).validate_schema()["errors"]
        self.assertIn("InvalidExtent", {item["code"] for item in errors})

    def test_unknown_source_reference_is_rejected(self):
        data = self.data()
        data["units"][0]["sourceIds"] = ["UNKNOWN"]
        errors = EngineConfig.from_dict(data).validate_schema()["errors"]
        self.assertIn("UnknownSourceReference", {item["code"] for item in errors})

    def test_unknown_affected_unit_is_rejected(self):
        data = self.data()
        data["events"][0]["affectedUnitIds"] = ["UNKNOWN"]
        errors = EngineConfig.from_dict(data).validate_schema()["errors"]
        self.assertIn("UnknownAffectedUnit", {item["code"] for item in errors})

    def test_stratigraphic_cycle_is_rejected(self):
        data = self.data()
        data["relations"].append({
            "relationId": "R2", "relationType": "Above", "sourceId": "U2",
            "targetId": "U1", "evidenceSourceIds": ["SYNTHETIC-RULESET-001"],
            "confidence": 1.0})
        report = validate_stage_one(EngineConfig.from_dict(data))
        codes = {error["code"] for gate in report["gates"] for error in gate["errors"]}
        self.assertIn("StratigraphicCycle", codes)

    def test_erosion_before_deposition_is_rejected(self):
        data = self.data()
        data["events"][0]["eventType"] = "Erosion"
        report = validate_stage_one(EngineConfig.from_dict(data))
        codes = {error["code"] for gate in report["gates"] for error in gate["errors"]}
        self.assertIn("EventBeforeMaterialExists", codes)

    def test_configuration_fingerprint_is_order_stable(self):
        config = load_config(EXAMPLE)
        first = configuration_fingerprint(config)
        second = configuration_fingerprint(EngineConfig.from_dict(copy.deepcopy(config.to_dict())))
        self.assertEqual(first, second)

    def test_manifest_authorizes_only_next_stage(self):
        config = load_config(EXAMPLE)
        validation = validate_stage_one(config)
        manifest = create_run_manifest(config, validation,
            datetime(2026, 8, 27, tzinfo=timezone.utc))
        self.assertFalse(manifest["geometryGenerated"])
        self.assertEqual(manifest["nextAuthorizedStage"], "positive_thickness_3d_stack")
        self.assertEqual(len(manifest["configurationSha256"]), 64)

    def test_gui_schema_and_example_are_json(self):
        schema = json.loads((root / "gui_input_schema.json").read_text(encoding="utf-8"))
        self.assertTrue(schema["x-ui"]["futureWizard"])
        self.assertEqual(schema["properties"]["randomSeed"]["type"], "integer")


if __name__ == "__main__":
    unittest.main()
