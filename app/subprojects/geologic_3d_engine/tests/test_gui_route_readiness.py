import json
from pathlib import Path
import tempfile
import unittest

from geologic_3d_engine.gui_route_readiness import (execute_route_readiness,
    execute_route_evidence_workspace)
from geologic_3d_engine.section.route_binding import build_route_binding
from geologic_3d_engine.section.borehole_correlation import canonical_sha256


class GuiRouteReadinessTests(unittest.TestCase):
    def test_plan_surface_transitions_and_rejected_borehole_are_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            plan=root/"plan.json";intake=root/"holes.json"
            plan.write_text(json.dumps({"schemaVersion":"PlanEvidenceBundle-1.0",
                "routeLonLat":[[130,32],[131,32]],
                "terrainProfile":[{"elevationM":10.0},{"elevationM":9.0}],
                "surfaceGeology":{"transitions":[{"lowerStationM":1,"upperStationM":2}]}}),encoding="utf-8")
            intake.write_text(json.dumps({"schemaVersion":"BoreholeSectionIntake-1.0",
                "boreholes":[{"projectionState":"Rejected","elevationConstraintAuthorized":False}]}),encoding="utf-8")
            result,target=execute_route_readiness(plan,root/"out",intake)
            self.assertEqual(result["mappedTransitionCount"],1)
            self.assertEqual(result["mappedTransitionBasis"],
                             "PointSampledIntervalCensoredSurfaceTransition")
            self.assertEqual(result["rejectedBoreholeCount"],1)
            self.assertFalse(result["sectionGeometryAuthorized"])
            self.assertTrue(target.is_file())

    def test_wrong_borehole_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);plan=root/"p.json";holes=root/"h.json"
            plan.write_text(json.dumps({"schemaVersion":"PlanEvidenceBundle-1.0",
                "routeLonLat":[[0,0],[1,0]],"terrainProfile":[{"elevationM":0}]}),encoding="utf-8")
            holes.write_text(json.dumps({"schemaVersion":"Other"}),encoding="utf-8")
            with self.assertRaises(ValueError):execute_route_readiness(plan,root/"out",holes)

    def test_route_bound_workspace_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);plan=root/"p.json";holes=root/"h.json"
            route=[[131,32],[131.01,32.01]]
            plan.write_text(json.dumps({"schemaVersion":"PlanEvidenceBundle-1.0",
              "routeLonLat":route,"terrainProfile":[{"stationM":0,"elevationM":10},
              {"stationM":1000,"elevationM":20}]}),encoding="utf-8")
            holes.write_text(json.dumps({"schemaVersion":"BoreholeSectionIntake-1.0",
              "routeBinding":build_route_binding(route),"boreholes":[]}),encoding="utf-8")
            result,target=execute_route_evidence_workspace(plan,root/"out",holes)
            self.assertTrue(target.is_file())
            self.assertTrue((target.parent/"route_evidence_section.png").is_file())
            self.assertTrue((target.parent/"route_evidence_section_render.json").is_file())
            self.assertEqual(result["authorizationState"],
              "EvidenceOverlayOnly_NoAutomaticSubsurfaceGeometry")

    def test_structural_and_exact_crossing_files_are_used(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);plan=root/"p.json";structure=root/"s.json";cross=root/"c.json"
            plan.write_text(json.dumps({"schemaVersion":"PlanEvidenceBundle-1.0",
                "routeLonLat":[[0,0],[1,0]],"terrainProfile":[{"elevationM":0.0}]}),encoding="utf-8")
            structure.write_text(json.dumps({"schemaVersion":"StructuralObservationProjection-1.0",
                "observations":[{"projectionState":"Projected","sourceId":"OBS"}]}),encoding="utf-8")
            cross.write_text(json.dumps({"schemaVersion":"GsjRouteCrossingSideClassification-1.0",
                "crossings":[{"sideClassificationStatus":"MappedUnitTransition"}]}),encoding="utf-8")
            result,_=execute_route_readiness(plan,root/"out",
                structural_observations_path=structure,mapped_crossings_path=cross)
            self.assertEqual(result["directOrientationConstraintCount"],1)
            self.assertEqual(result["mappedTransitionBasis"],"ExactVectorCrossingSideClassification")
            self.assertFalse(result["sectionGeometryAuthorized"])

    def test_hash_bound_three_hole_review_reaches_authorized_branch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);plan=root/"p.json";holes_path=root/"h.json";review_path=root/"r.json"
            plan.write_text(json.dumps({"schemaVersion":"PlanEvidenceBundle-1.0",
                "routeLonLat":[[0,0],[1,0]],"terrainProfile":[{"elevationM":10.0}],
                "surfaceGeology":{"transitions":[{"lowerStationM":1,"upperStationM":2}]}}),encoding="utf-8")
            holes=[]
            for index in range(3):
                holes.append({"boreholeId":f"B{index}","sourceId":f"S{index}",
                    "sourceLonLat":[130+index*.01,32],"projectionState":"Projected",
                    "elevationConstraintAuthorized":True,"stationM":float(index),
                    "projectionDistanceM":0.0,"collarElevationM":100.0,
                    "verticalDatum":"TP","intervals":[{"intervalIndex":0,
                    "sourceLabel":"sand","normalizedLithology":"sand",
                    "topElevationM":100.0,"bottomElevationM":90.0}]})
            intake={"schemaVersion":"BoreholeSectionIntake-1.0","boreholes":holes}
            holes_path.write_text(json.dumps(intake),encoding="utf-8")
            review={"schemaVersion":"BoreholeCorrelationReview-1.0","correlationId":"C",
                "reviewer":"Geologist","reviewedAt":"2026-09-05T00:00:00Z",
                "intakeSha256":canonical_sha256(intake),"reviewStatus":"GeologistInterpreted",
                "unitsBottomUp":[{"unitId":"U","normalizedLithology":"sand",
                    "members":[{"boreholeId":f"B{i}","intervalIndex":0} for i in range(3)]}]}
            review_path.write_text(json.dumps(review),encoding="utf-8")
            result,_=execute_route_readiness(plan,root/"out",holes_path,
                                              correlation_review_path=review_path)
            self.assertTrue(result["sectionGeometryAuthorized"])
            self.assertEqual(result["acceptedReviewedGeometryCount"],1)
            self.assertIn("correlationReview",result["inputArtifactSha256"])


if __name__=="__main__":unittest.main()
