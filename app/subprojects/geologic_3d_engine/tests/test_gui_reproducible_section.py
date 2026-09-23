import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from geologic_3d_engine.gui_reproducible_section import execute_selected_section_inputs

class GuiReproducibleSectionTests(unittest.TestCase):
    @patch("geologic_3d_engine.section.reproducible_section_run.execute_reviewed_section")
    def test_selected_files_become_self_contained_hash_bundle(self,execute):
        def fake(plan,intake,review,output,*args):
            folder=Path(output)/"reviewed_borehole_section";folder.mkdir(parents=True)
            js=folder/"interpreted_section.json";png=folder/"interpreted_section.png";js.write_text("{}",encoding="utf-8");png.write_bytes(b"PNG")
            return {"validation":{"ok":True}},js,png
        execute.side_effect=fake
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);files={}
            for role in ("plan","boreholeIntake","correlationReview"):
                path=root/f"source-{role}.json";path.write_text(json.dumps({"role":role}),encoding="utf-8");files[role]=path
            manifest,run,bundle=execute_selected_section_inputs(root/"out",files)
            data=json.loads(bundle.read_text(encoding="utf-8"))
            self.assertTrue(manifest["passed"]);self.assertEqual(set(data["inputs"]),set(files))
            self.assertTrue(all((bundle.parent/v["path"]).is_file() for v in data["inputs"].values()))
            self.assertTrue((run/"run_manifest.json").is_file())
if __name__=="__main__":unittest.main()
