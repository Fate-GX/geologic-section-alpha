import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from geologic_3d_engine.config import load_config
from geologic_3d_engine.events.event_spec import load_event_spec
from geologic_3d_engine.events.intrusion_spec import load_intrusion_spec
from geologic_3d_engine.geometry.mesh_spec import load_mesh_spec
from geologic_3d_engine.geometry.refinement_spec import RefinementSpec, load_refinement_spec
from geologic_3d_engine.physics.compaction_spec import load_compaction_spec
from geologic_3d_engine.physics.structural_spec import load_structural_spec
from geologic_3d_engine.stage8 import run_stage_eight, stage_eight_manifest
from geologic_3d_engine.stratigraphy.stack_spec import load_stack_spec

ROOT = Path(__file__).resolve().parents[1]


class Stage8RefinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        e = ROOT / "examples"
        cls.args = (load_config(e / "stage6_small_config.json"),
                    load_stack_spec(e / "stage6_stack_spec.json"),
                    load_event_spec(e / "stage3_event_spec.json"),
                    load_compaction_spec(e / "stage6_compaction_spec.json"),
                    load_structural_spec(e / "stage6_structural_spec.json"),
                    load_intrusion_spec(e / "stage6_intrusion_spec.json"),
                    load_mesh_spec(e / "stage7_mesh_spec.json"))
        cls.spec = load_refinement_spec(e / "stage8_refinement_spec.json")
        cls.result = run_stage_eight(*cls.args, cls.spec)

    def test_canonical_refinement_passes(self):
        self.assertTrue(self.result["passed"])

    def test_only_risk_region_is_refined(self):
        gate = self.result["gates"][0]
        self.assertGreater(gate["refinedCoarseCellCount"], 0)
        self.assertLess(gate["refinedFraction"], 1.0)

    def test_adaptive_leaves_cover_domain_exactly(self):
        gate = self.result["gates"][0]
        self.assertAlmostEqual(gate["leafCoverageVolume"], gate["domainVolume"], places=8)

    def test_convergence_and_topology_gates_pass(self):
        gate = self.result["gates"][0]
        self.assertTrue(gate["topologyStable"])
        self.assertTrue(all(v <= gate["volumeRelativeTolerance"]
                            for v in gate["unitVolumeRelativeChanges"].values()))

    def test_refined_brep_is_closed_and_manifold(self):
        model = self.result["adaptiveModel"]
        self.assertFalse(model.validation["refinedBrepSkipped"])
        self.assertTrue(model.refined_brep.validation["passed"])
        self.assertTrue(all(m.validation["closed"] and m.validation["manifold"]
                            for m in model.refined_brep.unit_meshes))

    def test_preflight_brep_disagreement_is_rejected(self):
        failed_brep=SimpleNamespace(validation={
            "passed":False,"gate":"ClosedOrientedManifoldBrep",
            "errors":[{"code":"InjectedBrepValidationFailure","unitId":"TEST"}],
            "unitDiagnostics":[]})
        with patch("geologic_3d_engine.geometry.adaptive_refinement.build_closed_breps",
                   return_value=failed_brep) as constructor:
            result=run_stage_eight(*self.args,self.spec)
        self.assertEqual(constructor.call_count,1)
        self.assertFalse(result["passed"])
        gate=result["gates"][0]
        self.assertTrue(gate["voxelTopologyPreflight"]["passed"])
        self.assertFalse(gate["refinedBrepSkipped"])
        codes=[error["code"] for error in gate["errors"]]
        self.assertIn("RefinedBrepFailed",codes)
        self.assertIn("PreflightBrepDisagreement",codes)

    def test_unsupported_factor_is_rejected(self):
        self.assertFalse(run_stage_eight(*self.args,
            RefinementSpec(3, 1.0, 0.2, True, 2))["passed"])

    def test_invalid_refined_fraction_is_rejected(self):
        self.assertFalse(run_stage_eight(*self.args,
            RefinementSpec(2, 0.0, 0.2, True, 2))["passed"])

    def test_negative_tolerance_is_rejected(self):
        self.assertFalse(run_stage_eight(*self.args,
            RefinementSpec(2, 1.0, -0.1, True, 2))["passed"])

    def test_unsupported_convergence_level_is_rejected(self):
        self.assertFalse(run_stage_eight(*self.args,
            RefinementSpec(2, 1.0, 0.2, True, 1))["passed"])

    def test_manifest_authorizes_uncertainty_stage(self):
        self.assertEqual(stage_eight_manifest(self.result)["nextAuthorizedStage"],
                         "uncertainty_ensemble")


if __name__ == "__main__":
    unittest.main()
