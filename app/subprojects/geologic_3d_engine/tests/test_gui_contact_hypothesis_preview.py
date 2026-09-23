import hashlib,json,tempfile,unittest
from pathlib import Path

from geologic_3d_engine.gui_contact_hypothesis_preview import execute_contact_hypothesis_preview
from geologic_3d_engine.section.contact_orientation_hypothesis import build_contact_orientation_hypothesis_template
from geologic_3d_engine.gui_contact_orientation_editor import update_hypothesis_row
from tests.test_contact_orientation_hypothesis import intersections


class ContactHypothesisPreviewTests(unittest.TestCase):
    def test_bound_preview_and_empty_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);plan=root/"plan.json";ints=root/"ints.json";template=root/"template.json"
            doc=intersections();doc["planEvidenceSha256"]="pending"
            for event in doc["events"]:event["routeSegmentIndex"]=0
            plan_data={"routeLonLat":[[131,32.8],[131.01,32.8]],
                "terrainProfile":[{"stationM":0,"elevationM":500},{"stationM":1000,"elevationM":490}]}
            plan.write_text(json.dumps(plan_data),encoding="utf-8")
            doc["planEvidenceSha256"]=hashlib.sha256(plan.read_bytes()).hexdigest()
            unsigned={k:v for k,v in doc.items() if k!="recordSha256"}
            doc["recordSha256"]=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
            ints.write_text(json.dumps(doc),encoding="utf-8")
            base=build_contact_orientation_hypothesis_template(doc)
            template.write_text(json.dumps(base),encoding="utf-8")
            report,image,*_=execute_contact_hypothesis_preview(plan,ints,template,root)
            self.assertEqual(report["evaluatedContactCount"],0);self.assertTrue(image.exists())
            edited=update_hypothesis_row(base,0,{"orientationBasis":"SyntheticAssumption",
                "trueDipDegrees":"20","dipDirectionDegrees":"90",
                "angularUncertaintyDegrees":"2","lateralSupportM":"50",
                "basisSourceIds":"","interpretationNote":"test"})
            template.write_text(json.dumps(edited),encoding="utf-8")
            report,image,*_=execute_contact_hypothesis_preview(plan,ints,template,root)
            self.assertEqual(report["evaluatedContactCount"],1)
            self.assertEqual(report["drawnLithologyPolygonCount"],0)
            self.assertFalse(report["realRegionAuthorized"])

            declaration={"schemaVersion":"HypothesisLithologyUnitDeclarations-1.0",
                "orientationTemplateSha256":edited["recordSha256"],"declarations":[{
                    "unitId":"U1","sourceLabel":"synthetic","normalizedLabel":"synthetic unit",
                    "evidenceStatus":"SyntheticAssumption","topBoundary":{"type":"Terrain"},
                    "bottomBoundary":{"type":"Contact","hypothesisId":edited["hypotheses"][0]["hypothesisId"]}}]}
            declaration["recordSha256"]=hashlib.sha256(json.dumps(declaration,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
            declaration_path=root/"declarations.json";declaration_path.write_text(json.dumps(declaration),encoding="utf-8")
            report,*_=execute_contact_hypothesis_preview(plan,ints,template,root,declaration_path)
            self.assertEqual(report["diagnosticLithologyUnitCount"],1)
            self.assertGreater(report["drawnLithologyPolygonCount"],0)

    def test_rejects_unbound_plan(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);plan=root/"plan.json";ints=root/"ints.json";template=root/"template.json"
            plan.write_text('{}',encoding='utf-8');doc=intersections();ints.write_text(json.dumps(doc),encoding='utf-8')
            template.write_text(json.dumps(build_contact_orientation_hypothesis_template(doc)),encoding='utf-8')
            with self.assertRaises(ValueError):execute_contact_hypothesis_preview(plan,ints,template,root)
