import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from geologic_3d_engine.gui_evidence_route import execute_evidence_route_candidate


class GuiEvidenceRouteTests(unittest.TestCase):
    def test_backend_preserves_proposal_and_eligibility_boundary(self):
        document={"schemaVersion":"PublicBoreholeEvidence-1.0","boreholes":[{
          "boreholeId":"B1","longitude":.5,"latitude":.1,
          "horizontalCrsStatus":"Verified","verticalDatumStatus":"AuthorityInferred",
          "collarElevationAccuracyStatus":"Verified",
          "sourceId":"S","intervals":[{"evidenceStatus":"Observed"}]}]}
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"hole.json";source.write_text(json.dumps(document),encoding="utf-8")
            result,target=execute_evidence_route_candidate(
                SimpleNamespace(vertices=[[0,0],[1,0]]),source,folder)
            self.assertTrue(target.is_file())
            self.assertFalse(result["sectionConstraintEligibleIfSelected"])
            self.assertEqual(result["applicationState"],"ProposalOnly_UserMustExplicitlySelect")

    def test_multiple_holes_are_not_silently_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"hole.json";source.write_text(json.dumps({
                "schemaVersion":"PublicBoreholeEvidence-1.0","boreholes":[{},{}]}),encoding="utf-8")
            with self.assertRaises(ValueError):execute_evidence_route_candidate(
                SimpleNamespace(vertices=[[0,0],[1,0]]),source,folder)


if __name__=="__main__":unittest.main()
