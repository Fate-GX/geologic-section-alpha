import copy
import json
import unittest
from pathlib import Path

from geologic_3d_engine.config import load_config
from geologic_3d_engine.events.event_spec import Stage3EventSpec, load_event_spec
from geologic_3d_engine.events.stratigraphic_events import (
    apply_erosion, build_deposit_on_surface, build_lens_in_host,
    build_stratified_erosion_fill, classify_interval_evidence, from_conformable_stack,
    voxelize_event_model)
from geologic_3d_engine.stage3 import run_stage_three, stage_three_manifest
from geologic_3d_engine.stratigraphy.stack_spec import StackBuildSpec, load_stack_spec

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "examples" / "stage3_small_config.json"
STACK = ROOT / "examples" / "stage3_stack_spec.json"
EVENTS = ROOT / "examples" / "stage3_event_spec.json"


class Stage3EventTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(CONFIG)
        self.stack_spec = load_stack_spec(STACK)
        self.base = self.stack_spec.build(self.config)

    def test_erosion_fill_pipeline_passes(self):
        result = run_stage_three(self.config, self.stack_spec, load_event_spec(EVENTS))
        self.assertTrue(result["passed"])
        self.assertEqual(result["eventModel"].primary_bodies[0].unit_id, "FILL")
        self.assertEqual(result["eventModel"].primary_bodies[0].bottom[0][0], 15.0)
        self.assertFalse(result["eventModel"].primary_bodies[1].active[0][0])
        self.assertEqual(result["eventModel"].primary_bodies[2].top[0][0], 15.0)
        self.assertEqual(result["voxelization"]["overlapCount"], 0)

    def test_fill_without_erosion_is_rejected(self):
        spec = Stage3EventSpec.from_dict({"operations": [{"eventId": "D3",
            "operation": "ErosionFill", "unitId": "FILL",
            "thicknessField": {"constant": 5}}]})
        result = run_stage_three(self.config, self.stack_spec, spec)
        self.assertFalse(result["passed"])
        self.assertIn("preceding erosion", result["errors"][0]["message"])

    def test_erosion_surface_above_old_top_uses_retained_top_for_fill(self):
        spec = Stage3EventSpec.from_dict({"operations": [
            {"eventId": "E1", "operation": "Erosion", "surface": {"constant": 45}},
            {"eventId": "D3", "operation": "ErosionFill", "unitId": "FILL",
             "thicknessField": {"constant": 5}}]})
        result = run_stage_three(self.config, self.stack_spec, spec)
        self.assertTrue(result["passed"])
        self.assertEqual(result["eventModel"].primary_bodies[0].bottom[0][0], 40.0)

    def test_operation_event_type_mismatch_is_rejected(self):
        spec = Stage3EventSpec.from_dict({"operations": [{"eventId": "D3",
            "operation": "Erosion", "surface": {"constant": 5}}]})
        self.assertFalse(run_stage_three(self.config, self.stack_spec, spec)["passed"])

    def test_operation_order_is_rejected(self):
        data = json.loads(EVENTS.read_text(encoding="utf-8"))
        data["operations"].reverse()
        result = run_stage_three(self.config, self.stack_spec, Stage3EventSpec.from_dict(data))
        self.assertFalse(result["passed"])

    def test_missing_field_is_rejected(self):
        spec = Stage3EventSpec.from_dict({"operations": [{"eventId": "E1",
            "operation": "Erosion"}]})
        self.assertFalse(run_stage_three(self.config, self.stack_spec, spec)["passed"])

    def test_onlap_preserves_existing_bodies_and_records_pinchout(self):
        model = from_conformable_stack(self.base)
        thickness = [[0, 0, 5, 5, 5] for _ in range(5)]
        onlap = build_deposit_on_surface(model, "FILL", thickness, "D3", "Onlap")
        self.assertEqual(onlap.primary_bodies[1:], model.primary_bodies)
        self.assertGreater(onlap.event_log[-1]["pinchoutFaceCount"], 0)
        self.assertTrue(voxelize_event_model(onlap)["passed"])

    def test_stratified_fill_uses_exact_predecessor_tops_without_overlap(self):
        erosion = [[15.0] * 5 for _ in range(5)]
        model = apply_erosion(from_conformable_stack(self.base), erosion, "E1")
        gravel = [[5.0] * 5 for _ in range(5)]
        sand = [[8.0] * 5 for _ in range(5)]
        result = build_stratified_erosion_fill(model, [
            ("GRAVEL", gravel, "D1"), ("SAND", sand, "D2")])
        youngest, oldest = result.primary_bodies[:2]
        self.assertEqual(oldest.bottom[0][0], 15.0)
        self.assertEqual(oldest.top[0][0], 20.0)
        self.assertIs(youngest.bottom, oldest.top)
        self.assertEqual(youngest.top[0][0], 28.0)
        self.assertEqual(voxelize_event_model(result)["overlapCount"], 0)

    def test_stratified_fill_clips_to_ceiling_and_allows_pinchout(self):
        model = apply_erosion(from_conformable_stack(self.base),
                              [[15.0] * 5 for _ in range(5)], "E1")
        ceiling = [[20.0, 20.0, 20.0, 20.0, 20.0] for _ in range(5)]
        first = [[5.0, 4.0, 3.0, 4.0, 5.0] for _ in range(5)]
        second = [[3.0] * 5 for _ in range(5)]
        result = build_stratified_erosion_fill(model, [
            ("LOWER", first, "D1"), ("UPPER", second, "D2")],
            accommodation_ceiling=ceiling)
        upper, lower = result.primary_bodies[:2]
        self.assertEqual(list(upper.thickness[0]), [0.0, 1.0, 2.0, 1.0, 0.0])
        self.assertEqual(upper.bottom, lower.top)
        self.assertGreater(result.event_log[-1]["pinchoutFaceCount"], 0)
        self.assertEqual(voxelize_event_model(result)["overlapCount"], 0)

    def test_stratified_fill_rejects_duplicate_identity_and_missing_erosion(self):
        field = [[1.0] * 5 for _ in range(5)]
        with self.assertRaisesRegex(ValueError, "preceding erosion"):
            build_stratified_erosion_fill(from_conformable_stack(self.base),
                                          [("A", field, "D1")])
        model = apply_erosion(from_conformable_stack(self.base),
                              [[15.0] * 5 for _ in range(5)], "E1")
        with self.assertRaisesRegex(ValueError, "unique"):
            build_stratified_erosion_fill(model,
                [("A", field, "D1"), ("A", field, "D2")])

    def test_internal_lens_replaces_only_host(self):
        model = from_conformable_stack(self.base)
        bottom = [[25.0] * 5 for _ in range(5)]
        thickness = [[0.0] * 5 for _ in range(5)]
        thickness[2][2] = 10.0
        lens = build_lens_in_host(model, "OLD_UPPER", "FILL", bottom, thickness, "D3")
        gate = voxelize_event_model(lens)
        self.assertTrue(gate["passed"])
        self.assertGreater(gate["unitCellCounts"]["FILL"], 0)
        self.assertEqual(lens.event_log[-1]["connectedComponentCount"], 1)

    def test_lens_outside_host_is_rejected(self):
        model = from_conformable_stack(self.base)
        bottom = [[45.0] * 5 for _ in range(5)]
        thickness = [[0.0] * 5 for _ in range(5)]; thickness[2][2] = 2.0
        with self.assertRaisesRegex(ValueError, "contained"):
            build_lens_in_host(model, "OLD_UPPER", "FILL", bottom, thickness, "D3")

    def test_internal_lens_touching_domain_boundary_is_rejected(self):
        model = from_conformable_stack(self.base)
        bottom = [[25.0] * 5 for _ in range(5)]
        thickness = [[0.0] * 5 for _ in range(5)]; thickness[0][2] = 5.0
        with self.assertRaisesRegex(ValueError, "close"):
            build_lens_in_host(model, "OLD_UPPER", "FILL", bottom, thickness, "D3")

    def test_deferred_units_must_cover_configuration(self):
        data = json.loads(STACK.read_text(encoding="utf-8")); data["deferredUnitIds"] = []
        with self.assertRaisesRegex(ValueError, "must equal configured"):
            StackBuildSpec.from_dict(data).build(self.config)

    def test_manifest_authorizes_compaction(self):
        result = run_stage_three(self.config, self.stack_spec, load_event_spec(EVENTS))
        self.assertEqual(stage_three_manifest(result)["nextAuthorizedStage"], "compaction")

    def test_absence_without_positive_evidence_remains_ambiguous(self):
        self.assertEqual(classify_interval_evidence({})["state"], "Ambiguous")

    def test_nonpenetration_is_an_evidence_limit_not_a_geological_event(self):
        result = classify_interval_evidence({"nonpenetration": True})
        self.assertEqual(result["category"], "EvidenceLimitState")
        self.assertIsNone(result["geologicalEvent"])

    def test_missing_record_is_a_data_quality_state(self):
        result = classify_interval_evidence({"missingRecord": True})
        self.assertEqual(result["category"], "DataQualityState")
        self.assertIsNone(result["geologicalEvent"])

    def test_conflicting_event_evidence_remains_unresolved(self):
        result = classify_interval_evidence({"positiveTruncation": True,
                                             "thicknessConvergesToZero": True})
        self.assertEqual(result["state"], "UnresolvedConflict")
        self.assertIsNone(result["geologicalEvent"])

    def test_nondeposition_requires_positive_elapsed_time_evidence(self):
        result = classify_interval_evidence({"elapsedTimeWithoutRemoval": True})
        self.assertEqual(result["geologicalEvent"], "Nondeposition")

    def test_erosion_requires_at_least_one_declared_positive_indicator(self):
        self.assertEqual(classify_interval_evidence({"erosionalSurface": True})["geologicalEvent"], "Erosion")


if __name__ == "__main__":
    unittest.main()
