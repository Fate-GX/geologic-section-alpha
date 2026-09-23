import unittest
from geologic_3d_engine.section.evidence_aware_route import (
    build_evidence_aware_route_candidate, propose_minimum_detour_route)


class EvidenceAwareRouteTests(unittest.TestCase):
    def test_minimum_detour_selects_expected_segment_without_changing_original(self):
        route=[[0,0],[1,0],[2,0]];original=[row[:] for row in route]
        result=propose_minimum_detour_route(route,[1.5,.1])
        self.assertEqual(result["insertedAfterSegmentIndex"],1)
        self.assertEqual(route,original)
        self.assertEqual(result["candidateRouteLonLat"][2],[1.5,.1])
        self.assertGreater(result["additionalLengthM"],0)
        self.assertEqual(result["applicationState"],"ProposalOnly_UserMustExplicitlySelect")
        self.assertEqual(result["routeTopologyStatus"],"Simple")

    def test_evidence_statuses_remain_separate_from_horizontal_collocation(self):
        borehole={"boreholeId":"B","longitude":.5,"latitude":.1,
            "horizontalCrsStatus":"Verified","verticalDatumStatus":"AuthorityInferred",
            "collarElevationAccuracyStatus":"Verified",
            "sourceId":"S","intervals":[{"evidenceStatus":"Observed"}]}
        result=build_evidence_aware_route_candidate([[0,0],[1,0]],borehole)
        self.assertTrue(result["horizontalCollocationIfSelected"])
        self.assertFalse(result["sectionConstraintEligibleIfSelected"])
        self.assertEqual(result["eligibilityBlockers"],["VerticalDatumNotVerified"])

    def test_fully_verified_observed_hole_is_eligible_but_still_only_proposed(self):
        borehole={"boreholeId":"B","longitude":.5,"latitude":.1,
            "horizontalCrsStatus":"Verified","verticalDatumStatus":"Verified",
            "collarElevationAccuracyStatus":"Verified",
            "sourceId":"S","intervals":[{"evidenceStatus":"Observed"}]}
        result=build_evidence_aware_route_candidate([[0,0],[1,0]],borehole)
        self.assertTrue(result["sectionConstraintEligibleIfSelected"])
        self.assertEqual(result["applicationState"],"ProposalOnly_UserMustExplicitlySelect")

    def test_invalid_route_and_incomplete_hole_reject(self):
        with self.assertRaises(ValueError):propose_minimum_detour_route([[0,0],[0,0]],[1,1])
        with self.assertRaises(ValueError):build_evidence_aware_route_candidate([[0,0],[1,0]],{})

    def test_candidate_self_intersection_is_reported_not_hidden(self):
        result=propose_minimum_detour_route([[0,0],[2,0],[2,2],[0,2]],[1,-1])
        # The exact minimum route is implementation-independent; if a crossing
        # occurs it must be explicit, never silently accepted as simple.
        self.assertEqual(result["routeTopologyStatus"]=="SelfIntersecting",
                         bool(result["properSelfIntersectionSegmentPairs"]))


if __name__=="__main__":unittest.main()
