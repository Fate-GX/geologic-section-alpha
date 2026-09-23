import math
import unittest
import numpy as np

from geologic_3d_engine.section.map_template import (
    MeasuredRoute2D, RegularDem2D, apparent_dip_degrees, build_section_template)


class MapSectionTemplateTests(unittest.TestCase):
    def setUp(self):
        self.route = MeasuredRoute2D([[0, 0], [10, 0], [10, 10]])
        yy, xx = np.mgrid[0:3, 0:3]
        self.dem = RegularDem2D((0, 0), (5, 5), 100 + 2*xx + 3*yy,
                                "EPSG:6670", "SyntheticDatum")

    def test_measured_route_and_signed_projection(self):
        result = self.route.project([[4, 3], [8, -2], [12, 7]])
        np.testing.assert_allclose(result["station"], [4, 8, 17])
        np.testing.assert_allclose(result["projectionDistance"], [3, 2, 2])
        np.testing.assert_allclose(result["signedOffset"], [3, -2, -2])

    def test_bilinear_dem_is_exact_for_plane(self):
        actual = self.dem.sample(np.array([[2.5, 2.5], [7.5, 7.5], [10, 10]]))
        np.testing.assert_allclose(actual, [102.5, 107.5, 110])

    def test_apparent_dip_boundaries(self):
        self.assertAlmostEqual(apparent_dip_degrees(40, 90, 90), 40)
        self.assertAlmostEqual(apparent_dip_degrees(40, 90, 0), 0)
        self.assertAlmostEqual(apparent_dip_degrees(40, 270, 90), -40)
        expected = math.degrees(math.atan(math.tan(math.radians(40))/math.sqrt(2)))
        self.assertAlmostEqual(apparent_dip_degrees(40, 90, 45), expected)

    def test_template_preserves_evidence_and_rejection(self):
        observations = [
            {"observationId":"ON", "xy":[5,0], "kind":"StrikeDip", "sourceId":"S1"},
            {"observationId":"NEAR", "xy":[5,2], "kind":"Borehole", "sourceId":"S2"},
            {"observationId":"FAR", "xy":[0,9], "kind":"Borehole", "sourceId":"S3"}]
        result = build_section_template(self.route, self.dem, 5, observations, 3)
        self.assertEqual([v["projectionState"] for v in result["observations"]],
                         ["OnSection", "Projected", "Rejected"])
        self.assertEqual(result["interpretationState"], "EvidenceTemplate_NoSubsurfaceInference")
        self.assertEqual(result["observations"][1]["sourceXY"], [5.0, 2.0])

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError): MeasuredRoute2D([[0,0],[0,0]])
        with self.assertRaises(ValueError): self.dem.sample(np.array([[20,20]]))
        with self.assertRaises(ValueError): apparent_dip_degrees(91,0,0)
        with self.assertRaises(ValueError): build_section_template(self.route,self.dem,0)


if __name__ == "__main__": unittest.main()
