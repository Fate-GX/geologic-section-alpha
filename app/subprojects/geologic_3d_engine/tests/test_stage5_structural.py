import json
import math
import unittest
from pathlib import Path

from geologic_3d_engine.config import load_config
from geologic_3d_engine.events.event_spec import load_event_spec
from geologic_3d_engine.physics.compaction_spec import load_compaction_spec
from geologic_3d_engine.physics.structural_3d import StructuralOperation, deform_model
from geologic_3d_engine.physics.structural_3d import fold_displacement_at
from geologic_3d_engine.physics.structural_spec import StructuralSpec, load_structural_spec
from geologic_3d_engine.stage4 import run_stage_four
from geologic_3d_engine.stage5 import run_stage_five, stage_five_manifest
from geologic_3d_engine.stratigraphy.stack_spec import load_stack_spec

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "examples/stage5_small_config.json"
STACK = ROOT / "examples/stage3_stack_spec.json"
EVENTS = ROOT / "examples/stage3_event_spec.json"
COMPACTION = ROOT / "examples/stage5_compaction_spec.json"
STRUCTURAL = ROOT / "examples/stage5_structural_spec.json"


class Stage5StructuralTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(CONFIG); self.stack = load_stack_spec(STACK)
        self.events = load_event_spec(EVENTS); self.compaction = load_compaction_spec(COMPACTION)
        self.structural = load_structural_spec(STRUCTURAL)

    def run_valid(self):
        return run_stage_five(self.config, self.stack, self.events,
                              self.compaction, self.structural)

    def test_fold_and_fault_pipeline_passes(self):
        result = self.run_valid()
        self.assertTrue(result["passed"])
        self.assertGreater(result["modelSummary"]["sampleCount"], 0)
        self.assertEqual(len(result["gates"][0]["operationGates"]), 2)

    def test_fold_jacobian_is_positive(self):
        gate = self.run_valid()["gates"][0]["operationGates"][0]
        self.assertEqual(gate["minimumJacobian"], 1.0)

    def test_fold_field_is_continuously_interpolated(self):
        stage4 = run_stage_four(self.config, self.stack, self.events, self.compaction)
        values = self.structural.materialize(self.config, stage4["compactedModel"])[0].parameters["verticalDisplacement"]
        left = fold_displacement_at(29.999999, 50, values, stage4["compactedModel"].grid)
        right = fold_displacement_at(30.000001, 50, values, stage4["compactedModel"].grid)
        self.assertLess(abs(left - right), 1e-5)

    def test_fault_displaces_both_sides_symmetrically(self):
        records = self.run_valid()["structuralModel"].samples_by_unit["FILL"]
        offsets = {round(item["target"][2] - item["source"][2], 6) for item in records}
        self.assertTrue(any(value < 0 for value in offsets))
        self.assertTrue(any(value > 0 for value in offsets))

    def test_missing_evidence_rejected(self):
        data = json.loads(STRUCTURAL.read_text()); data["operations"][0]["evidenceSourceIds"] = []
        self.assertFalse(run_stage_five(self.config, self.stack, self.events, self.compaction,
                         StructuralSpec.from_dict(data))["passed"])

    def test_event_type_mismatch_rejected(self):
        data = json.loads(STRUCTURAL.read_text()); data["operations"][0]["eventId"] = "FAULT1"
        self.assertFalse(run_stage_five(self.config, self.stack, self.events, self.compaction,
                         StructuralSpec.from_dict(data))["passed"])

    def test_reverse_event_order_rejected(self):
        data = json.loads(STRUCTURAL.read_text()); data["operations"].reverse()
        self.assertFalse(run_stage_five(self.config, self.stack, self.events, self.compaction,
                         StructuralSpec.from_dict(data))["passed"])

    def test_affected_unit_mismatch_rejected(self):
        data = json.loads(STRUCTURAL.read_text()); data["operations"][1]["affectedUnitIds"].pop()
        self.assertFalse(run_stage_five(self.config, self.stack, self.events, self.compaction,
                         StructuralSpec.from_dict(data))["passed"])

    def test_invalid_fault_vector_rejected(self):
        data = json.loads(STRUCTURAL.read_text()); data["operations"][1]["slipVector"] = [0,0,0]
        self.assertFalse(run_stage_five(self.config, self.stack, self.events, self.compaction,
                         StructuralSpec.from_dict(data))["passed"])

    def test_nonfinite_fold_field_rejected(self):
        stage4 = run_stage_four(self.config, self.stack, self.events, self.compaction)
        op = StructuralOperation("FOLD1", "FoldDisplacementField",
             ("FILL","OLD_UPPER","OLD_LOWER"), {"verticalDisplacement":[[math.nan]*5 for _ in range(5)]})
        self.assertFalse(deform_model(stage4["compactedModel"], (op,)).validation["passed"])

    def test_manifest_authorizes_intrusion(self):
        self.assertEqual(stage_five_manifest(self.run_valid())["nextAuthorizedStage"],
                         "intrusion_crosscutting")


if __name__ == "__main__": unittest.main()
