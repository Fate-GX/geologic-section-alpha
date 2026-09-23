import json,tempfile,unittest
from pathlib import Path
from geologic_3d_engine.gui_contact_structural_binding import execute_contact_structural_binding
from geologic_3d_engine.section.contact_orientation_hypothesis import build_contact_orientation_hypothesis_template
from geologic_3d_engine.section.route_binding import build_route_binding
from tests.test_contact_orientation_hypothesis import intersections


class GuiContactStructuralBindingTests(unittest.TestCase):
    def test_file_backend_writes_proposals_and_accepted_candidate_template(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);route=[[131,32.8],[131.01,32.8]];inter=intersections()
            template=build_contact_orientation_hypothesis_template(inter)
            projected={"routeBinding":build_route_binding(route),"observations":[{
                "observationId":"O","sourceId":"FIELD","stationM":100,"projectionState":"Projected",
                "appliesToFeatureIds":["C1"],"trueDipDegrees":20,"dipDirectionDegrees":90,
                "angularUncertaintyDegrees":3,"lateralSupportM":150}]}
            files=[]
            for name,value in (("plan.json",{"routeLonLat":route}),("inter.json",inter),
                               ("template.json",template),("projected.json",projected)):
                path=root/name;path.write_text(json.dumps(value),encoding="utf-8");files.append(path)
            proposals,proposal_path,accepted_path=execute_contact_structural_binding(*files,root,200,True)
            self.assertEqual(proposals["uniqueCandidateCount"],1);self.assertTrue(proposal_path.exists())
            accepted=json.loads(accepted_path.read_text(encoding="utf-8"))
            self.assertEqual(accepted["hypotheses"][0]["orientationBasis"],"EvidenceCandidate")
