import unittest

from geologic_3d_engine.section.evidence_bounded_surface import EvidenceBoundedRbfSurface
from geologic_3d_engine.section.exact_route_hull_intersection import intersect_route_with_evidence_hull


def control(x, y, z):
    return {"xM": x, "yM": y, "zM": z, "contactId": "C",
            "evidenceStatus": "Observed", "absoluteElevationConstraintAuthorized": True,
            "independentSupportId": f"BH-{x}-{y}",
            "constraintRole": "DirectSubsurfaceContact"}


class ExactRouteHullIntersectionTests(unittest.TestCase):
    def setUp(self):
        self.surface = EvidenceBoundedRbfSurface(
            [control(0, 0, 10), control(10, 0, 12), control(0, 10, 7)], .4,
            maximum_condition_number=1e12, maximum_control_residual_m=1e-9)

    def test_oblique_crossing_has_exact_stations_and_elevations(self):
        route = [{"stationM": 0, "xM": -2, "yM": 2},
                 {"stationM": 120, "xM": 10, "yM": 2}]
        result = intersect_route_with_evidence_hull(self.surface, route)
        interval = result["supportedIntervals"][0]
        self.assertAlmostEqual(interval["start"]["stationM"], 20, places=9)
        self.assertAlmostEqual(interval["end"]["stationM"], 100, places=9)
        self.assertAlmostEqual(interval["start"]["contactElevationM"], 9.4, places=9)
        self.assertAlmostEqual(interval["end"]["contactElevationM"], 11.0, places=9)
        self.assertFalse(result["sampleSpacingDependency"])

    def test_bent_route_can_exit_and_reenter(self):
        route = [{"stationM": 0, "xM": -1, "yM": 1},
                 {"stationM": 2, "xM": 1, "yM": 1},
                 {"stationM": 4, "xM": -1, "yM": 2},
                 {"stationM": 6, "xM": 1, "yM": 2}]
        result = intersect_route_with_evidence_hull(self.surface, route)
        self.assertEqual(result["supportedIntervalCount"], 2)

    def test_outside_and_tangent_do_not_create_area_support(self):
        outside = [{"stationM": 0, "xM": -2, "yM": -2},
                   {"stationM": 1, "xM": -1, "yM": -1}]
        self.assertEqual(intersect_route_with_evidence_hull(
            self.surface, outside)["supportedIntervalCount"], 0)
        tangent = [{"stationM": 0, "xM": -1, "yM": 1},
                   {"stationM": 1, "xM": 1, "yM": -1}]
        self.assertEqual(intersect_route_with_evidence_hull(
            self.surface, tangent)["supportedIntervalCount"], 0)

    def test_invalid_station_order_rejects(self):
        with self.assertRaises(ValueError):
            intersect_route_with_evidence_hull(self.surface, [
                {"stationM": 1, "xM": 0, "yM": 0},
                {"stationM": 1, "xM": 1, "yM": 1}])


if __name__ == "__main__":
    unittest.main()
