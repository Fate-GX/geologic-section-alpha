import unittest
from dataclasses import replace
from copy import deepcopy
from pathlib import Path

from geologic_3d_engine.config import load_config
from geologic_3d_engine.events.event_spec import load_event_spec
from geologic_3d_engine.events.intrusion_spec import load_intrusion_spec
from geologic_3d_engine.export.autocad_contract import build_autocad_contract
from geologic_3d_engine.export.contract_integrity import verify_integrity_envelope
from geologic_3d_engine.export.export_spec import UnitDraftingSpec, load_export_spec
from geologic_3d_engine.geometry.mesh_spec import load_mesh_spec
from geologic_3d_engine.geometry.refinement_spec import load_refinement_spec
from geologic_3d_engine.physics.compaction_spec import load_compaction_spec
from geologic_3d_engine.physics.structural_spec import load_structural_spec
from geologic_3d_engine.section.section_spec import load_section_spec
from geologic_3d_engine.stage11 import run_stage_eleven, stage_eleven_manifest
from geologic_3d_engine.stratigraphy.stack_spec import load_stack_spec
from geologic_3d_engine.uncertainty.ensemble_spec import load_ensemble_spec

ROOT=Path(__file__).resolve().parents[1]


class Stage11ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        e=ROOT/"examples"
        cls.args=(load_config(e/"stage6_small_config.json"),load_stack_spec(e/"stage6_stack_spec.json"),
          load_event_spec(e/"stage3_event_spec.json"),load_compaction_spec(e/"stage6_compaction_spec.json"),
          load_structural_spec(e/"stage6_structural_spec.json"),load_intrusion_spec(e/"stage6_intrusion_spec.json"),
          load_mesh_spec(e/"stage7_mesh_spec.json"),load_refinement_spec(e/"stage8_refinement_spec.json"),
          load_ensemble_spec(e/"stage9_ensemble_spec.json"),load_section_spec(e/"stage10_section_spec.json"))
        cls.spec=load_export_spec(e/"stage11_export_spec.json")
        cls.result=run_stage_eleven(*cls.args,cls.spec); cls.contract=cls.result["contract"]

    def test_canonical_contract_passes(self): self.assertTrue(self.result["passed"])
    def test_contract_contains_all_section_polygons(self): self.assertEqual(len(self.contract["polygons"]),5)
    def test_every_hatch_is_solid_and_associative(self):
        self.assertTrue(all(p["hatchPattern"]=="SOLID" and p["associative"] for p in self.contract["polygons"]))
    def test_every_polygon_uses_direct_rgb(self):
        self.assertTrue(all(len(p["trueColorRGB"])==3 for p in self.contract["polygons"]))
    def test_contract_records_standard_native_api_plan(self):
        self.assertIn("Hatch.AppendLoop",self.contract["nativeApiPlan"])
        self.assertIn("Hatch.EvaluateHatch",self.contract["nativeApiPlan"])
    def test_uncertainty_is_a_separate_non_cad_diagnostic_artifact(self):
        overlay=self.contract["uncertaintyVisualization"]
        self.assertEqual(overlay["artifactRole"],"DiagnosticOverlay_NotLithologyGeometry")
        self.assertEqual(overlay["cadEntityAuthorization"],"None_DiagnosticDataOnly")
        self.assertTrue(overlay["mustNotCreateLithologyBoundaries"])
        self.assertTrue(overlay["mustNotCreateLithologyHatches"])
        self.assertTrue(self.contract["validation"]["uncertaintySeparatedFromLithologyGeometry"])
        self.assertTrue(all("uncertainty" not in key.lower() for polygon in self.contract["polygons"] for key in polygon))
    def test_contract_is_marked_synthetic_and_not_for_design(self):
        self.assertTrue(self.contract["notForDesign"]); self.assertIn("Synthetic",self.contract["syntheticDisclosure"])
    def test_missing_unit_style_is_rejected(self):
        bad=replace(self.spec,units=self.spec.units[:-1])
        self.assertFalse(run_stage_eleven(*self.args,bad)["passed"])
    def test_invalid_rgb_is_rejected(self):
        first=replace(self.spec.units[0],rgb=(300,0,0)); bad=replace(self.spec,units=(first,)+self.spec.units[1:])
        self.assertFalse(run_stage_eleven(*self.args,bad)["passed"])
    def test_wrong_dwg_version_is_rejected(self):
        self.assertFalse(run_stage_eleven(*self.args,replace(self.spec,dwg_version="AC1027"))["passed"])
    def test_manifest_requires_writer_execution_next(self):
        self.assertEqual(stage_eleven_manifest(self.result)["nextAuthorizedStage"],"native_dwg_writer_execution")

    def test_envelope_verifies_and_contains_complete_stage_path(self):
        payload,validation=verify_integrity_envelope(self.result["contractEnvelope"])
        self.assertTrue(validation["passed"])
        self.assertEqual(payload["lineageManifest"]["stagePath"],
                         ["Stage{0}".format(index) for index in range(1,12)])

    def test_every_exported_unit_has_source_linkage(self):
        payload,_=verify_integrity_envelope(self.result["contractEnvelope"])
        lineage={item["unitId"]:item for item in payload["lineageManifest"]["unitLineage"]}
        for polygon in payload["polygons"]:
            self.assertTrue(lineage[polygon["unitId"]]["sourceIds"])

    def test_nonfinite_polygon_coordinate_is_rejected(self):
        section=deepcopy(self.result["stageTen"]["section"])
        section["unitSections"][0]["polygons"][0]["verticesUV"][0][0]=float("nan")
        with self.assertRaisesRegex(ValueError,"finite UV coordinates"):
            build_autocad_contract(section,self.spec,"test")

    def test_infinite_polygon_coordinate_is_rejected(self):
        section=deepcopy(self.result["stageTen"]["section"])
        section["unitSections"][0]["polygons"][0]["verticesUV"][0][1]=float("inf")
        with self.assertRaisesRegex(ValueError,"finite UV coordinates"):
            build_autocad_contract(section,self.spec,"test")


if __name__=="__main__": unittest.main()
