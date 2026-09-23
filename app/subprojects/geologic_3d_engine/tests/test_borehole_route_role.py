import copy
import unittest

from geologic_3d_engine.section.borehole_route_role import classify_borehole_route_roles


def hole(lat=.001, authorized=True):
    return {"boreholeId": "H", "longitude": .5, "latitude": lat,
        "collarElevationM": 10.0, "totalDepthM": 2.0,
        "horizontalCrs": "EPSG:6668", "verticalDatum": "TokyoPeil",
        "sourceId": "S", "sourceUrl": "https://example.invalid", "exchangeFormatVersion": "X",
        "horizontalCrsStatus": "Verified", "verticalDatumStatus": "Verified",
        "collarElevationAccuracyStatus": "Verified",
        "horizontalPositionAccuracyStatus": "Verified",
        "intervals": [{"topDepthM": 0.0, "bottomDepthM": 2.0,
            "sourceLabel": "x", "normalizedLithology": "x", "termStatus": "Current",
            "evidenceStatus": "Observed"}], "elevationConstraintAuthorized": authorized}


class BoreholeRouteRoleTests(unittest.TestCase):
    def test_three_roles_and_quality_override(self):
        route = [[0, 0], [1, 0]]
        direct = classify_borehole_route_roles([hole(.0001)], route, 20, 500)
        self.assertEqual(direct["boreholes"][0]["role"], "DirectSectionConstraintCandidate")
        context = classify_borehole_route_roles([hole(.001)], route, 20, 500)
        self.assertEqual(context["boreholes"][0]["role"], "RegionalContextOnly")
        self.assertFalse(context["boreholes"][0]["sectionGeometryAuthorized"])
        outside = classify_borehole_route_roles([hole(.01)], route, 20, 500)
        self.assertEqual(outside["boreholes"][0]["role"], "OutsideDeclaredContextRange")
        weak = hole(.0001); weak["collarElevationAccuracyStatus"] = "Unverified"
        result = classify_borehole_route_roles([weak], route, 20, 500)
        self.assertEqual(result["boreholes"][0]["role"], "RegionalContextOnly")

    def test_invalid_threshold_crs_and_interval_status_reject_or_demote(self):
        with self.assertRaises(ValueError): classify_borehole_route_roles([hole()], [[0,0],[1,0]], 100, 99)
        bad = hole(); bad["horizontalCrs"] = "EPSG:4612"
        with self.assertRaises(ValueError): classify_borehole_route_roles([bad], [[0,0],[1,0]], 100, 500)
        weak = hole(.0001); weak["intervals"][0]["evidenceStatus"] = "Unverified"
        result = classify_borehole_route_roles([weak], [[0,0],[1,0]], 20, 500)
        self.assertEqual(result["boreholes"][0]["role"], "RegionalContextOnly")
        self.assertIn("IntervalsNotEvidenceQualified", result["boreholes"][0]["qualityBlockers"])


if __name__ == "__main__": unittest.main()
