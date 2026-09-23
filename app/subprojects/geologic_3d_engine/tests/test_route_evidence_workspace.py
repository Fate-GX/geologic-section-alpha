import json
from pathlib import Path
import tempfile
import unittest

from geologic_3d_engine.section.route_binding import build_route_binding, route_sha256
from geologic_3d_engine.section.route_evidence_workspace import assemble_route_evidence_workspace


class RouteEvidenceWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.route=[[131.0,32.8],[131.01,32.81]]
        self.plan=self.root/"plan.json"
        self.plan.write_text(json.dumps({"schemaVersion":"PlanEvidenceBundle-1.0",
          "routeLonLat":self.route,"terrainProfile":[{"stationM":0,"elevationM":10},
          {"stationM":1000,"elevationM":20}],"surfaceGeology":{"transitions":[]}}),encoding="utf-8")
    def tearDown(self):self.temp.cleanup()
    def artifact(self,name,schema,rows_key,rows,route=None):
        path=self.root/name
        path.write_text(json.dumps({"schemaVersion":schema,
          "routeBinding":build_route_binding(route or self.route),rows_key:rows}),encoding="utf-8")
        return path
    def test_route_hash_is_canonical_and_workspace_is_evidence_only(self):
        self.assertEqual(route_sha256([(131,32.8),(131.01,32.81)]),route_sha256(self.route))
        holes=self.artifact("h.json","BoreholeSectionIntake-1.0","boreholes",
          [{"projectionState":"Projected","stationM":500}])
        structure=self.artifact("s.json","StructuralObservationProjection-1.0","observations",
          [{"projectionState":"Projected","stationM":600,"sourceId":"S"}])
        result=assemble_route_evidence_workspace(self.plan,borehole_path=holes,
                                                  structural_path=structure)
        self.assertEqual(result["authorizationState"],
          "EvidenceOverlayOnly_NoAutomaticSubsurfaceGeometry")
        self.assertEqual(len(result["inputArtifactSha256"]),3)
        self.assertEqual(len(result["recordSha256"]),64)
    def test_other_route_and_unbound_artifact_are_rejected(self):
        wrong=self.artifact("wrong.json","BoreholeSectionIntake-1.0","boreholes",[],
                            [[130,32],[130.1,32]])
        with self.assertRaisesRegex(ValueError,"route binding mismatch"):
            assemble_route_evidence_workspace(self.plan,borehole_path=wrong)
        unbound=self.root/"unbound.json"
        unbound.write_text(json.dumps({"schemaVersion":"BoreholeSectionIntake-1.0",
                                       "boreholes":[]}),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"no route binding"):
            assemble_route_evidence_workspace(self.plan,borehole_path=unbound)
    def test_out_of_route_station_is_rejected(self):
        holes=self.artifact("h.json","BoreholeSectionIntake-1.0","boreholes",
          [{"projectionState":"Projected","stationM":1000.1}])
        with self.assertRaisesRegex(ValueError,"outside"):
            assemble_route_evidence_workspace(self.plan,borehole_path=holes)


if __name__=="__main__":unittest.main()
