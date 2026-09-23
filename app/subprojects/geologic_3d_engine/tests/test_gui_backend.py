import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

from geologic_3d_engine.export.contract_integrity import verify_integrity_envelope
from geologic_3d_engine.gui_backend import execute_run_bundle,load_run_bundle

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/"examples"/"stage11_gui_run_bundle.json"


class GuiBackendTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.output=Path(cls.temp.name)
  cls.result=execute_run_bundle(BUNDLE,cls.output)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def test_bundle_runs_the_real_stage11_pipeline(self):
  self.assertTrue(self.result["passed"]);self.assertIn("contractEnvelope",self.result)
 def test_outputs_are_complete_and_integrity_verifiable(self):
  for name in ("run_summary.json","stage11_manifest.json","contract_envelope.json","neutral_contract.json"):
   self.assertTrue((self.output/name).is_file())
  envelope=json.loads((self.output/"contract_envelope.json").read_text(encoding="utf-8"))
  payload,validation=verify_integrity_envelope(envelope)
  self.assertTrue(validation["passed"]);self.assertIn("uncertaintyVisualization",payload)
 def test_summary_preserves_synthetic_disclosure(self):
  summary=json.loads((self.output/"run_summary.json").read_text(encoding="utf-8"))
  self.assertTrue(summary["passed"]);self.assertIn("Synthetic",summary["syntheticDisclosure"])
 def test_bundle_rejects_path_escape(self):
  data=json.loads(BUNDLE.read_text(encoding="utf-8"));data["inputs"]["config"]="../outside.json"
  with tempfile.TemporaryDirectory(dir=ROOT/"examples") as folder:
   path=Path(folder)/"bad.json";path.write_text(json.dumps(data),encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"escapes"):load_run_bundle(path)
 def test_bundle_rejects_missing_or_extra_inputs(self):
  data=json.loads(BUNDLE.read_text(encoding="utf-8"));del data["inputs"]["meshSpec"]
  with tempfile.TemporaryDirectory(dir=ROOT/"examples") as folder:
   path=Path(folder)/"bad.json";path.write_text(json.dumps(data),encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"exactly"):load_run_bundle(path)
 def test_bundle_rejects_unsupported_target(self):
  data=json.loads(BUNDLE.read_text(encoding="utf-8"));data["targetStage"]="NativeDwg"
  with tempfile.TemporaryDirectory(dir=ROOT/"examples") as folder:
   path=Path(folder)/"bad.json";path.write_text(json.dumps(data),encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"only Stage11"):load_run_bundle(path)
 def test_rejected_rerun_removes_stale_success_artifacts(self):
  rejected={"passed":False,"decision":"Rejected","stage":"autocad_export_contract",
            "errors":[{"code":"InjectedRejection"}]}
  with tempfile.TemporaryDirectory() as folder:
   output=Path(folder);(output/"contract_envelope.json").write_text("stale",encoding="utf-8")
   (output/"neutral_contract.json").write_text("stale",encoding="utf-8")
   with patch("geologic_3d_engine.gui_backend.run_stage_eleven",return_value=rejected):
    execute_run_bundle(BUNDLE,output)
   self.assertFalse((output/"contract_envelope.json").exists())
   self.assertFalse((output/"neutral_contract.json").exists())
   summary=json.loads((output/"run_summary.json").read_text(encoding="utf-8"))
   self.assertFalse(summary["passed"])


if __name__=="__main__":unittest.main()
