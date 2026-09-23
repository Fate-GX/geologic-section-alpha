import json
import unittest
from pathlib import Path

from geologic_3d_engine.config import load_config
from geologic_3d_engine.events.event_spec import load_event_spec
from geologic_3d_engine.events.intrusion_spec import IntrusionSpec, load_intrusion_spec
from geologic_3d_engine.physics.compaction_spec import load_compaction_spec
from geologic_3d_engine.physics.structural_spec import load_structural_spec
from geologic_3d_engine.stage6 import run_stage_six, stage_six_manifest
from geologic_3d_engine.stratigraphy.stack_spec import load_stack_spec

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "examples/stage6_small_config.json"
STACK = ROOT / "examples/stage6_stack_spec.json"
EVENTS = ROOT / "examples/stage3_event_spec.json"
COMPACTION = ROOT / "examples/stage6_compaction_spec.json"
STRUCTURAL = ROOT / "examples/stage6_structural_spec.json"
INTRUSION = ROOT / "examples/stage6_intrusion_spec.json"


class Stage6IntrusionTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(CONFIG); self.stack = load_stack_spec(STACK)
        self.events = load_event_spec(EVENTS); self.compaction = load_compaction_spec(COMPACTION)
        self.structural = load_structural_spec(STRUCTURAL); self.intrusion = load_intrusion_spec(INTRUSION)

    def run_spec(self, spec=None):
        return run_stage_six(self.config, self.stack, self.events, self.compaction,
                             self.structural, spec or self.intrusion)

    def test_crosscutting_dike_replaces_two_hosts(self):
        result = self.run_spec(); self.assertTrue(result["passed"])
        report = result["gates"][0]["operationReports"][0]
        self.assertEqual(report["crosscutHostCount"], 2)
        self.assertEqual(set(report["replacedHostCellCounts"]), {"FILL", "OLD_LOWER"})

    def test_material_cell_count_is_conserved_by_replacement(self):
        result = self.run_spec(); counts = result["gates"][0]["unitCellCounts"]
        self.assertEqual(sum(counts.values()), 125)
        self.assertEqual(result["gates"][0]["overlapCount"], 0)

    def test_unauthorized_boundary_exit_rejected(self):
        data = json.loads(INTRUSION.read_text()); data["operations"][0]["allowDomainBoundaryExit"] = False
        result = self.run_spec(IntrusionSpec.from_dict(data)); self.assertFalse(result["passed"])
        self.assertEqual(result["gates"][0]["errors"][0]["code"], "UnauthorizedDomainBoundaryExit")

    def test_intrusion_missing_hosts_rejected(self):
        data = json.loads(INTRUSION.read_text()); data["operations"][0]["planeOffset"] = 1000
        result = self.run_spec(IntrusionSpec.from_dict(data)); self.assertFalse(result["passed"])
        self.assertEqual(result["gates"][0]["errors"][0]["code"], "IntrusionDoesNotIntersectDeclaredHosts")

    def test_sill_without_concordance_evidence_rejected(self):
        data = json.loads(INTRUSION.read_text()); data["operations"][0]["intrusionStyle"] = "Sill"
        self.assertFalse(self.run_spec(IntrusionSpec.from_dict(data))["passed"])

    def test_geometry_style_mismatch_rejected(self):
        data = json.loads(INTRUSION.read_text()); data["operations"][0]["geometryType"] = "Ellipsoid"
        self.assertFalse(self.run_spec(IntrusionSpec.from_dict(data))["passed"])

    def test_missing_evidence_rejected(self):
        data = json.loads(INTRUSION.read_text()); data["operations"][0]["evidenceSourceIds"] = []
        self.assertFalse(self.run_spec(IntrusionSpec.from_dict(data))["passed"])

    def test_unknown_host_rejected(self):
        data = json.loads(INTRUSION.read_text()); data["operations"][0]["hostUnitIds"] = ["UNKNOWN"]
        self.assertFalse(self.run_spec(IntrusionSpec.from_dict(data))["passed"])

    def test_contained_plug_is_supported(self):
        data = json.loads(INTRUSION.read_text()); op = data["operations"][0]
        op.update({"intrusionStyle":"Plug","geometryType":"Ellipsoid",
                   "center":[50,50,0],"semiAxes":[15,15,25],
                   "allowDomainBoundaryExit":False})
        result = self.run_spec(IntrusionSpec.from_dict(data))
        self.assertTrue(result["passed"])
        self.assertFalse(result["gates"][0]["operationReports"][0]["touchesDomainBoundary"])

    def test_manifest_authorizes_mesh_stage(self):
        self.assertEqual(stage_six_manifest(self.run_spec())["nextAuthorizedStage"],
                         "closed_mesh_and_brep")


if __name__ == "__main__": unittest.main()
