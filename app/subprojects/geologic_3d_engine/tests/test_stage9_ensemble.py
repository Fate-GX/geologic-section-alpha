import unittest
from pathlib import Path

from geologic_3d_engine.config import load_config
from geologic_3d_engine.events.event_spec import load_event_spec
from geologic_3d_engine.events.intrusion_spec import load_intrusion_spec
from geologic_3d_engine.geometry.mesh_spec import load_mesh_spec
from geologic_3d_engine.geometry.refinement_spec import load_refinement_spec
from geologic_3d_engine.physics.compaction_spec import load_compaction_spec
from geologic_3d_engine.physics.structural_spec import load_structural_spec
from geologic_3d_engine.stage9 import run_stage_nine, stage_nine_manifest
from geologic_3d_engine.stratigraphy.stack_spec import load_stack_spec
from geologic_3d_engine.uncertainty.ensemble_spec import EnsembleSpec, ParameterRange, load_ensemble_spec

ROOT = Path(__file__).resolve().parents[1]


class Stage9EnsembleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        e = ROOT / "examples"
        cls.args = (load_config(e / "stage6_small_config.json"),
                    load_stack_spec(e / "stage6_stack_spec.json"),
                    load_event_spec(e / "stage3_event_spec.json"),
                    load_compaction_spec(e / "stage6_compaction_spec.json"),
                    load_structural_spec(e / "stage6_structural_spec.json"),
                    load_intrusion_spec(e / "stage6_intrusion_spec.json"),
                    load_mesh_spec(e / "stage7_mesh_spec.json"),
                    load_refinement_spec(e / "stage8_refinement_spec.json"))
        cls.spec = load_ensemble_spec(e / "stage9_ensemble_spec.json")
        cls.result = run_stage_nine(*cls.args, cls.spec)

    def test_canonical_ensemble_passes(self):
        self.assertTrue(self.result["passed"])

    def test_all_members_pass_upstream_gates(self):
        self.assertTrue(all(m["passed"] for m in self.result["ensemble"]["members"]))

    def test_samples_stay_inside_evidence_bounds(self):
        for member in self.result["ensemble"]["members"]:
            for p in member["parameters"]:
                self.assertGreaterEqual(p["value"], p["minimum"])
                self.assertLessEqual(p["value"], p["maximum"])

    def test_replay_is_deterministic(self):
        replay = run_stage_nine(*self.args, self.spec)
        self.assertEqual([m["parameters"] for m in self.result["ensemble"]["members"]],
                         [m["parameters"] for m in replay["ensemble"]["members"]])
        self.assertEqual(self.result["ensemble"]["disagreementMaskZYX"],
                         replay["ensemble"]["disagreementMaskZYX"])

    def test_probability_sums_to_one(self):
        fields = self.result["ensemble"]["materialProbabilityZYX"]
        self.assertTrue(all(abs(sum(cell.values()) - 1.0) < 1e-12
            for layer in fields for row in layer for cell in row))

    def test_entropy_is_bounded(self):
        field = self.result["ensemble"]["normalizedEntropyZYX"]
        self.assertTrue(all(0 <= v <= 1 for layer in field for row in layer for v in row))

    def test_too_few_members_rejected(self):
        bad = EnsembleSpec(1, 0, self.spec.parameter_ranges)
        self.assertFalse(run_stage_nine(*self.args, bad)["passed"])

    def test_missing_evidence_rejected(self):
        p = ParameterRange("I1", "planeOffset", 1, 2, "Uniform", ("MISSING",))
        self.assertFalse(run_stage_nine(*self.args, EnsembleSpec(2, 0, (p,)))["passed"])

    def test_invalid_parameter_range_rejected(self):
        p = ParameterRange("I1", "halfThickness", 4, 2, "Uniform",
                           ("SYNTHETIC-INTRUSION-EVIDENCE",))
        self.assertFalse(run_stage_nine(*self.args, EnsembleSpec(2, 0, (p,)))["passed"])

    def test_manifest_authorizes_section_intersection(self):
        self.assertEqual(stage_nine_manifest(self.result)["nextAuthorizedStage"],
                         "section_intersection")


if __name__ == "__main__":
    unittest.main()
