import copy
import hashlib
import json
import unittest

from geologic_3d_engine.section.route_plan_comparison import (compare_route_plan_evidence,
    route_turn_angles_degrees)


def plan(route, count=2, intervals=1):
    return {"schemaVersion": "PlanEvidenceBundle-1.0", "routeLonLat": route,
        "layers": [{"evidence_kind": "DEM", "source_id": "D"},
                   {"evidence_kind": "SurfaceGeology", "source_id": "G"}],
        "terrainProfile": [{"elevationM": 10+i, "elevationSourceId": "DEM5A"}
                           for i in range(count)],
        "surfaceGeology": {"samples": count, "mappedUnitIntervals": intervals,
                           "transitions": max(0, intervals-1)}}


def proposal():
    value = {"originalRouteLonLat": [[0, 0], [1, 0]],
        "candidateRouteLonLat": [[0, 0], [.5, .1], [1, 0]],
        "insertedAfterSegmentIndex": 0,
        "applicationState": "ProposalOnly_UserMustExplicitlySelect",
        "sourceId": "H", "originalLengthM": 100.0, "candidateLengthM": 120.0,
        "additionalLengthM": 20.0, "sectionConstraintEligibleIfSelected": False}
    value["recordSha256"] = hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return value


class RoutePlanComparisonTests(unittest.TestCase):
    def test_comparison_reports_domain_change_without_adoption(self):
        value = compare_route_plan_evidence(plan([[0, 0], [1, 0]]),
            plan([[0, 0], [.5, .1], [1, 0]], 3, 2), proposal())
        self.assertEqual(value["terrainSampleIncrease"], 1)
        self.assertEqual(value["mappedSurfaceIntervalIncrease"], 1)
        self.assertAlmostEqual(value["lengthRatio"], 1.2)
        self.assertFalse(value["sectionConstraintEligibleIfSelected"])
        self.assertEqual(value["routeGeometryAudit"]["candidateRouteQuality"], "Pass")

    def test_hairpin_is_rejected_and_turn_calculation_is_generic(self):
        p = proposal()
        p["candidateRouteLonLat"] = [[0, 0], [.5, 0], [.1, .01], [1, 0]]
        unsigned = {k:v for k,v in p.items() if k != "recordSha256"}
        p["recordSha256"] = hashlib.sha256(json.dumps(unsigned, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        result = compare_route_plan_evidence(plan([[0, 0], [1, 0]]),
            plan(p["candidateRouteLonLat"], 4, 2), p, 120.0)
        self.assertEqual(result["selectionState"], "RejectedForRouteGeometry")
        self.assertGreater(result["routeGeometryAudit"]["candidateSharpTurnCount"], 0)
        self.assertAlmostEqual(route_turn_angles_degrees([[0,0],[1,0],[1,1]])[0]
                               ["directionChangeDegrees"], 90.0, places=9)

    def test_hash_route_and_incomplete_terrain_reject(self):
        p = proposal(); p["additionalLengthM"] = 21
        with self.assertRaises(ValueError): compare_route_plan_evidence(
            plan([[0, 0], [1, 0]]), plan([[0, 0], [.5, .1], [1, 0]]), p)
        p = proposal(); bad = plan([[0, 0], [.5, .1], [1, 0]])
        bad["terrainProfile"][0]["elevationM"] = None
        with self.assertRaises(ValueError): compare_route_plan_evidence(
            plan([[0, 0], [1, 0]]), bad, p)
        bad = plan([[0, 0], [1, .01]])
        with self.assertRaises(ValueError): compare_route_plan_evidence(
            bad, plan([[0, 0], [.5, .1], [1, 0]]), p)


if __name__ == "__main__": unittest.main()
