import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from geologic_3d_engine.section.reproducible_section_run import build_bundle_document,execute_reproducible_section_bundle

class ReproducibleRunTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.files={}
        for key in ("plan","boreholeIntake","correlationReview"):
            path=self.root/f"{key}.json";path.write_text(json.dumps({"role":key}),encoding="utf-8");self.files[key]=path
        bundle=build_bundle_document("RUN-1",self.files,self.root);self.bundle=self.root/"bundle.json"
        self.bundle.write_text(json.dumps(bundle),encoding="utf-8")
    def tearDown(self):self.temp.cleanup()
    @patch("geologic_3d_engine.section.reproducible_section_run.execute_reviewed_section")
    def test_hash_bound_inputs_are_copied_and_outputs_manifested(self,execute):
        def fake(plan,intake,review,output,*args):
            folder=Path(output)/"reviewed_borehole_section";folder.mkdir(parents=True)
            js=folder/"interpreted_section.json";png=folder/"interpreted_section.png";js.write_text("{}",encoding="utf-8");png.write_bytes(b"PNG")
            return {"validation":{"finite":True,"ordered":True}},js,png
        execute.side_effect=fake;manifest,run=execute_reproducible_section_bundle(self.bundle,self.root/"out")
        self.assertTrue(manifest["passed"]);self.assertEqual(manifest["decision"],"Experimental")
        self.assertTrue((run/manifest["outputs"]["sectionPng"]["path"]).is_file())
        self.assertFalse(manifest["realRegionAuthorized"])
    def test_tamper_escape_missing_and_unknown_role_are_rejected(self):
        self.files["plan"].write_text("changed",encoding="utf-8")
        with self.assertRaises(ValueError):execute_reproducible_section_bundle(self.bundle,self.root/"out")
        data=json.loads(self.bundle.read_text());data["inputs"]["plan"]["path"]="../outside.json";self.bundle.write_text(json.dumps(data))
        with self.assertRaises(ValueError):execute_reproducible_section_bundle(self.bundle,self.root/"out")
        with self.assertRaises(ValueError):build_bundle_document("R",{"unknown":self.files["plan"]},self.root)
    @patch("geologic_3d_engine.section.reproducible_section_run.execute_reviewed_section")
    def test_qualitative_constraint_is_hash_bound_and_forwarded(self,execute):
        qualitative=self.root/"qualitative.json";qualitative.write_text("{}",encoding="utf-8")
        files={**self.files,"qualitativeStratigraphy":qualitative}
        self.bundle.write_text(json.dumps(build_bundle_document("RUN-Q",files,self.root)),encoding="utf-8")
        def fake(plan,intake,review,output,*args):
            self.assertEqual(Path(args[-1]).read_text(encoding="utf-8"),"{}")
            folder=Path(output)/"reviewed_borehole_section";folder.mkdir(parents=True)
            js=folder/"interpreted_section.json";png=folder/"interpreted_section.png"
            js.write_text("{}",encoding="utf-8");png.write_bytes(b"PNG")
            return {"validation":{"ok":True}},js,png
        execute.side_effect=fake
        manifest,_=execute_reproducible_section_bundle(self.bundle,self.root/"out")
        self.assertTrue(manifest["passed"])
        self.assertIn("qualitativeStratigraphy",manifest["inputSha256"])
    @patch("geologic_3d_engine.section.reproducible_section_run.execute_reviewed_section",side_effect=ValueError("bad geology"))
    def test_failure_has_no_success_outputs(self,execute):
        manifest,run=execute_reproducible_section_bundle(self.bundle,self.root/"out")
        self.assertFalse(manifest["passed"]);self.assertEqual(manifest["outputs"],{})
        self.assertTrue((run/"run_manifest.json").is_file())
if __name__=="__main__":unittest.main()
