import unittest

from geologic_3d_engine.section.evidence_bounded_surface import EvidenceBoundedRbfSurface
from geologic_3d_engine.section.route_surface_projection import project_surface_to_route_samples


def control(x, y, z):
    return {"xM": x, "yM": y, "zM": z, "contactId": "C",
            "evidenceStatus": "Observed", "absoluteElevationConstraintAuthorized": True,
            "independentSupportId": f"BH-{x}-{y}",
            "constraintRole": "DirectSubsurfaceContact"}


class RouteSurfaceProjectionTests(unittest.TestCase):
    def setUp(self):
        self.surface = EvidenceBoundedRbfSurface(
            [control(0, 0, 10), control(10, 0, 12), control(0, 10, 7)], .4,
            maximum_condition_number=1e12, maximum_control_residual_m=1e-9)

    def test_route_preserves_unknown_and_sample_brackets(self):
        route = [{"stationM": i * 10, "xM": x, "yM": 2}
                 for i, x in enumerate((-2, 0, 2, 4, 6, 8, 10))]
        result = project_surface_to_route_samples(self.surface, route)
        self.assertEqual(result["supportedSampleCount"], 5)
        self.assertIsNone(result["samples"][0]["contactElevationM"])
        self.assertEqual(result["supportedRuns"][0]["firstSampleIndex"], 1)
        self.assertEqual(result["supportedRuns"][0]["lastSampleIndex"], 5)
        self.assertEqual(len(result["coverageTransitionBrackets"]), 2)
        self.assertFalse(result["extrapolationAuthorized"])

    def test_bent_route_can_have_multiple_supported_runs(self):
        xy = [(-1, 1), (1, 1), (-1, 2), (1, 2)]
        route = [{"stationM": i, "xM": x, "yM": y} for i, (x, y) in enumerate(xy)]
        result = project_surface_to_route_samples(self.surface, route)
        self.assertEqual(len(result["supportedRuns"]), 2)

    def test_bad_station_order_rejects(self):
        with self.assertRaises(ValueError):
            project_surface_to_route_samples(self.surface, [
                {"stationM": 1, "xM": 0, "yM": 0},
                {"stationM": 1, "xM": 1, "yM": 1}])


if __name__ == "__main__":
    unittest.main()
