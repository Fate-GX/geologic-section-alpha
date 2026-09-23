import unittest

from geologic_3d_engine.section.route_evidence_readiness import (
    assess_route_evidence_readiness, audit_constraint_station_distribution)


def plan(missing=False):
    return {"schemaVersion":"PlanEvidenceBundle-1.0",
            "routeLonLat":[[130,32],[131,32]],
            "terrainProfile":[{"stationM":0.0,"elevationM":100.0},
                              {"stationM":1000.0,"elevationM":None if missing else 90.0}]}


def crossings():
    return {"schemaVersion":"GsjRouteCrossingSideClassification-1.0",
            "crossings":[{"sideClassificationStatus":"MappedUnitTransition"},
                         {"sideClassificationStatus":"NonGeologicBoundary"}]}


class RouteEvidenceReadinessTests(unittest.TestCase):
    def test_surface_context_does_not_authorize_subsurface_geometry(self):
        result=assess_route_evidence_readiness(plan(),mapped_crossings=crossings())
        self.assertFalse(result["sectionGeometryAuthorized"])
        self.assertEqual(result["mappedTransitionCount"],1)
        self.assertIn("NoDirectSubsurfaceConstraintCandidates",result["blockingReasons"])

    def test_rejected_borehole_and_dem_plane_remain_context_only(self):
        result=assess_route_evidence_readiness(
            plan(), mapped_crossings=crossings(),
            boreholes=[{"projectionState":"Rejected","elevationConstraintAuthorized":False}],
            contact_plane_diagnostics={"schemaVersion":"MappedContactDemPlaneDiagnostics-1.0",
                "diagnostics":[{"subsurfaceContinuationAuthorized":False}]})
        self.assertEqual(result["rejectedBoreholeCount"],1)
        self.assertEqual(result["authorizedContactPlaneCount"],0)
        self.assertFalse(result["sectionGeometryAuthorized"])

    def test_only_explicit_artifact_bound_review_authorizes_geometry(self):
        result=assess_route_evidence_readiness(
            plan(),mapped_crossings=crossings(),
            boreholes=[{"projectionState":"Projected","elevationConstraintAuthorized":True}],
            reviewed_geometry=[{"reviewStatus":"Accepted","artifactBound":True}])
        self.assertTrue(result["sectionGeometryAuthorized"])
        self.assertEqual(result["authorizationState"],
                         "ReviewedEvidenceConstrainedSectionAuthorized")

    def test_projected_source_linked_orientation_is_a_constraint_candidate(self):
        result=assess_route_evidence_readiness(
            plan(),mapped_crossings=crossings(),
            structural_observations=[{"projectionState":"Projected","sourceId":"OBS"}])
        self.assertEqual(result["directOrientationConstraintCount"],1)
        self.assertNotIn("NoDirectSubsurfaceConstraintCandidates",result["blockingReasons"])
        self.assertFalse(result["sectionGeometryAuthorized"])

    def test_missing_terrain_and_unbound_review_fail_closed(self):
        result=assess_route_evidence_readiness(
            plan(True),mapped_crossings=crossings(),
            reviewed_geometry=[{"reviewStatus":"Accepted","artifactBound":False}])
        self.assertFalse(result["terrainComplete"])
        self.assertFalse(result["sectionGeometryAuthorized"])
        self.assertIn("TerrainProfileIncomplete",result["blockingReasons"])

    def test_bad_schema_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_route_evidence_readiness({"schemaVersion":"Other"})

    def test_constraint_station_distribution_has_no_implicit_support_radius(self):
        result = audit_constraint_station_distribution(1000, [
            {"stationM":200}, {"stationM":650}])
        self.assertEqual(result["constraintStationsM"], [200.0, 650.0])
        self.assertEqual(result["maximumUnbracketedGapM"], 450.0)
        self.assertEqual(result["startEndpointGapM"], 200.0)
        self.assertEqual(result["endEndpointGapM"], 350.0)
        self.assertEqual(result["coverageInterpretation"],
                         "SpacingDiagnosticOnly_NoInterpolationRadiusAuthorized")

    def test_no_constraints_reports_entire_route_as_unbracketed(self):
        result = audit_constraint_station_distribution(1234.5, [])
        self.assertEqual(result["maximumUnbracketedGapM"], 1234.5)
        self.assertEqual(result["coverageInterpretation"], "NoDirectConstraintStations")

    def test_constraint_outside_route_is_rejected(self):
        with self.assertRaises(ValueError):
            audit_constraint_station_distribution(100, [{"stationM":101}])


if __name__=="__main__": unittest.main()
