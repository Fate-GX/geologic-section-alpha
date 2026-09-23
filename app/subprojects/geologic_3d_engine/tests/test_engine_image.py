import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from geologic_3d_engine import engine_image as module


class EngineImageTests(unittest.TestCase):
    def test_real_engine_and_exact_intersection(self):
        captured=[]
        original=module.extract_section
        def spy(brep,spec):
            result=original(brep,spec);captured.append(result);return result
        with tempfile.TemporaryDirectory() as temp, patch.object(module,"extract_section",side_effect=spy):
            image=module.export_image(temp,1234)
            report=json.loads(image.with_name("run.json").read_text(encoding="utf-8"))
            self.assertEqual(report["section"],captured[0])
            self.assertFalse(report["passed"])
            self.assertTrue(report["stage8Passed"])
            self.assertTrue(report["diagnosticExtraction"])
            self.assertEqual(report["decision"],"Rejected")
            self.assertEqual(image.read_bytes()[:8],b"\x89PNG\r\n\x1a\n")
            self.assertIn("PreBrepTopologyRejected",json.dumps(report["diagnostics"]))
            self.assertIn("VolumeConvergenceExceeded",json.dumps(report["diagnostics"]))
            other=module.export_image(temp,1234,contact_lines="Hide")
            second=json.loads(other.with_name("run.json").read_text(encoding="utf-8"))
            self.assertEqual(report["section"],second["section"])
            self.assertNotEqual(image.read_bytes(),other.read_bytes())
            changed=module.export_image(temp,1235)
            third=json.loads(changed.with_name("run.json").read_text(encoding="utf-8"))
            self.assertNotEqual(report["sourcePayloadSha256"],third["sourcePayloadSha256"])

    def test_no_success_geometry_on_missing_section(self):
        with tempfile.TemporaryDirectory() as temp:
            data={"passed":False,"decision":"Rejected","seed":1,"section":None,
                  "inputs":{"stage10_section_spec.json":{"origin":[0,47,0]}}}
            module.render(data,Path(temp)/"rejected.png",100,-50,50,20,10,"Show")
            self.assertTrue((Path(temp)/"rejected.png").exists())

    def test_input_rejection_precedes_engine(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(module,"run_engine") as run:
            for options in ({"section_y":0},{"distance_end":90},{"horizontal_tick":0},{"contact_lines":"x"}):
                with self.assertRaises(ValueError):module.export_image(temp,1,**options)
            run.assert_not_called()
