import copy
import json
import unittest
from pathlib import Path

from geologic_3d_engine.config import load_config
from geologic_3d_engine.events.event_spec import load_event_spec
from geologic_3d_engine.events.stratigraphic_events import from_conformable_stack, build_lens_in_host
from geologic_3d_engine.physics.compaction_3d import UnitPorosityState, compact_event_model
from geologic_3d_engine.physics.compaction_spec import CompactionSpec, load_compaction_spec
from geologic_3d_engine.stage4 import run_stage_four, stage_four_manifest
from geologic_3d_engine.stratigraphy.stack_spec import load_stack_spec

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "examples" / "stage4_small_config.json"
STACK = ROOT / "examples" / "stage3_stack_spec.json"
EVENTS = ROOT / "examples" / "stage3_event_spec.json"
COMPACTION = ROOT / "examples" / "stage4_compaction_spec.json"


class Stage4CompactionTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(CONFIG)
        self.stack_spec = load_stack_spec(STACK)
        self.event_spec = load_event_spec(EVENTS)
        self.compaction_spec = load_compaction_spec(COMPACTION)

    def test_differential_compaction_pipeline_passes(self):
        result = run_stage_four(self.config, self.stack_spec, self.event_spec,
                                self.compaction_spec)
        self.assertTrue(result["passed"])
        fill = result["compactedModel"].primary_bodies[0]
        self.assertNotEqual(fill.bottom[0][0], fill.bottom[0][2])
        self.assertTrue(all(item["passed"] for item in
                            result["gates"][0]["unitConservation"]))

    def test_shared_contacts_survive_inactive_eroded_unit(self):
        result = run_stage_four(self.config, self.stack_spec, self.event_spec,
                                self.compaction_spec)
        fill, inactive, lower = result["compactedModel"].primary_bodies
        self.assertEqual(fill.bottom, inactive.top)
        self.assertEqual(inactive.bottom, lower.top)
        self.assertFalse(inactive.active[0][0])

    def test_target_porosity_above_source_is_rejected(self):
        data = json.loads(COMPACTION.read_text(encoding="utf-8"))
        data["units"][0]["targetPorosity"] = {"constant": 0.6}
        result = run_stage_four(self.config, self.stack_spec, self.event_spec,
                                CompactionSpec.from_dict(data))
        self.assertFalse(result["passed"])

    def test_missing_evidence_is_rejected(self):
        data = json.loads(COMPACTION.read_text(encoding="utf-8"))
        data["units"][0]["evidenceSourceIds"] = []
        result = run_stage_four(self.config, self.stack_spec, self.event_spec,
                                CompactionSpec.from_dict(data))
        self.assertFalse(result["passed"])

    def test_unknown_evidence_is_rejected(self):
        data = json.loads(COMPACTION.read_text(encoding="utf-8"))
        data["units"][0]["evidenceSourceIds"] = ["UNKNOWN"]
        self.assertFalse(run_stage_four(self.config, self.stack_spec, self.event_spec,
                         CompactionSpec.from_dict(data))["passed"])

    def test_affected_unit_mismatch_is_rejected(self):
        data = json.loads(COMPACTION.read_text(encoding="utf-8")); data["units"].pop()
        self.assertFalse(run_stage_four(self.config, self.stack_spec, self.event_spec,
                         CompactionSpec.from_dict(data))["passed"])

    def test_unsupported_anchor_is_rejected(self):
        data = json.loads(COMPACTION.read_text(encoding="utf-8")); data["anchor"] = "BaseFixed"
        self.assertFalse(run_stage_four(self.config, self.stack_spec, self.event_spec,
                         CompactionSpec.from_dict(data))["passed"])

    def test_wrong_event_type_is_rejected(self):
        data = json.loads(COMPACTION.read_text(encoding="utf-8")); data["eventId"] = "D3"
        self.assertFalse(run_stage_four(self.config, self.stack_spec, self.event_spec,
                         CompactionSpec.from_dict(data))["passed"])

    def test_lens_follows_host_when_strain_matches(self):
        base = from_conformable_stack(self.stack_spec.build(self.config))
        bottom = [[25.0] * 5 for _ in range(5)]
        thickness = [[0.0] * 5 for _ in range(5)]; thickness[2][2] = 10.0
        model = build_lens_in_host(base, "OLD_UPPER", "FILL", bottom, thickness, "D3")
        constant = lambda value: tuple(tuple(value for _ in range(5)) for _ in range(5))
        states = (UnitPorosityState("OLD_UPPER", constant(.4), constant(.2), ("S",)),
                  UnitPorosityState("OLD_LOWER", constant(.35), constant(.15), ("S",)),
                  UnitPorosityState("FILL", constant(.4), constant(.2), ("S",)))
        compacted, gate = compact_event_model(model, states, "C1")
        self.assertTrue(gate["passed"])
        self.assertAlmostEqual(compacted.replacement_bodies[0].thickness[2][2], 7.5)

    def test_differential_lens_host_strain_requires_coupled_solver(self):
        base = from_conformable_stack(self.stack_spec.build(self.config))
        bottom = [[25.0] * 5 for _ in range(5)]
        thickness = [[0.0] * 5 for _ in range(5)]; thickness[2][2] = 10.0
        model = build_lens_in_host(base, "OLD_UPPER", "FILL", bottom, thickness, "D3")
        constant = lambda value: tuple(tuple(value for _ in range(5)) for _ in range(5))
        states = (UnitPorosityState("OLD_UPPER", constant(.4), constant(.2), ("S",)),
                  UnitPorosityState("OLD_LOWER", constant(.35), constant(.15), ("S",)),
                  UnitPorosityState("FILL", constant(.5), constant(.2), ("S",)))
        with self.assertRaisesRegex(ValueError, "coupled solver"):
            compact_event_model(model, states, "C1")

    def test_manifest_authorizes_structural_kinematics(self):
        result = run_stage_four(self.config, self.stack_spec, self.event_spec,
                                self.compaction_spec)
        self.assertEqual(stage_four_manifest(result)["nextAuthorizedStage"],
                         "fold_fault_kinematics")


if __name__ == "__main__":
    unittest.main()
