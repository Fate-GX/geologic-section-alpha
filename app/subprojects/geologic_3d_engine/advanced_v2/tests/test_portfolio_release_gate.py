import importlib.util,json,tempfile,unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[2]/"tools"/"portfolio_release_gate.py"
SPEC=importlib.util.spec_from_file_location("portfolio_release_gate",SCRIPT);gate=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(gate)
class PortfolioReleaseGateTests(unittest.TestCase):
    def test_demo_manifest(self):
        document=json.loads((gate.ROOT/"portfolio_demo_manifest.json").read_text(encoding="utf-8"));self.assertEqual([],gate.validate_demo_manifest(document))
    def test_missing_human_review_is_not_ready(self):
        result=gate.run_gate();self.assertFalse(result["passed"]);self.assertIn("HumanQaArtifactRequired",result["errors"])
    def test_complete_human_review(self):
        value=json.loads((gate.ROOT/"portfolio_human_qa.template.json").read_text(encoding="utf-8"));value.update(reviewer="Reviewer",reviewedAt="2026-09-14T12:00:00+09:00",decision="Passed");value["checks"]={key:True for key in value["checks"]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"qa.json";path.write_text(json.dumps(value),encoding="utf-8");self.assertEqual([],gate.validate_human_qa(path))
    def test_secret_and_path_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture_name="api"+"_"+"key";fixture_value="123456789"+"-secret"
            user_path="C:"+"\\\\Users\\\\Alice\\\\file"
            path=Path(folder)/"bad.py";path.write_text(f'{fixture_name}="{fixture_value}"\np="{user_path}"',encoding="utf-8")
            codes={row["code"] for row in gate.scan_public_source([path])};self.assertIn("GenericAssignedSecret",codes);self.assertIn("LocalAbsoluteUserPath",codes)
    def test_compound_secret_identifier_and_marker_cannot_bypass_scan(self):
        with tempfile.TemporaryDirectory() as folder:
            name="MY_"+"SECRET"+"_KEY";value="realistic"+"-credential-value"
            marker="portfolio"+"-scan: test-fixture"
            path=Path(folder)/"test_attack.py"
            path.write_text(f'{name}="{value}"  # {marker}',encoding="utf-8")
            codes={row["code"] for row in gate.scan_public_source([path])}
            self.assertIn("GenericAssignedSecret",codes)
if __name__=="__main__":unittest.main()
