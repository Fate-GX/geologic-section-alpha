import math
import unittest
import numpy as np

from geologic_3d_engine.section.map_template import MeasuredRoute2D, intersect_route_with_contacts
from geologic_3d_engine.section.orientation_geometry import (
    plane_from_three_points, plane_from_points_orthogonal_least_squares,
    planar_contact_on_vertical_section)


class MapOrientationGeometryTests(unittest.TestCase):
    def test_overdetermined_orthogonal_plane_fit_reports_true_residuals(self):
        points=[]
        for x,y,error in ((0,0,0.1),(10,0,-0.1),(0,20,0.05),(10,20,-0.05),(4,7,0.0)):
            points.append([x,y,100-0.5*x+0.25*y+error])
        result=plane_from_points_orthogonal_least_squares(points)
        self.assertEqual(result["pointCount"],5)
        self.assertEqual(result["fitMethod"],"OrthogonalLeastSquares_SVD")
        self.assertGreater(result["horizontalSpanM"],22)
        self.assertLess(result["orthogonalRmseM"],0.1)
        self.assertAlmostEqual(result["dipDegrees"],
                               math.degrees(math.atan(math.hypot(.5,.25))),delta=1.0)
        self.assertEqual(result["interpretationBoundary"],
                         "LocalPlanarComparator_NotAutomaticSubsurfaceTruth")

    def test_overdetermined_plane_fit_rejects_collinear_and_nonfinite(self):
        with self.assertRaises(ValueError):
            plane_from_points_orthogonal_least_squares([[0,0,0],[1,1,1],[2,2,2]])
        with self.assertRaises(ValueError):
            plane_from_points_orthogonal_least_squares([[0,0,0],[1,0,1],[0,1,float("nan")]])

    def test_contact_intersections_preserve_identity_and_order(self):
        route = MeasuredRoute2D([[0,0],[10,0],[10,10]])
        contacts = [
            {"contactId":"C2","unitPair":["B","C"],"verticesXY":[[10,8],[12,8]],"sourceId":"MAP"},
            {"contactId":"C1","unitPair":["A","B"],"verticesXY":[[3,-2],[3,2]],"sourceId":"MAP"}]
        events = intersect_route_with_contacts(route, contacts)
        self.assertEqual([e["contactId"] for e in events], ["C1","C2"])
        np.testing.assert_allclose([e["station"] for e in events], [3,18])
        self.assertEqual(events[0]["unitPair"], ["A","B"])

    def test_three_point_plane_and_section_trace(self):
        # z = 100 - 0.5*x + 0.25*y
        result = plane_from_three_points([[0,0,100],[10,0,95],[0,20,105]])
        self.assertLess(result["maximumResidual"], 1e-12)
        trace = planar_contact_on_vertical_section(result["unitNormal"], result["offset"],
                                                    [0,0], 90, [0,5,10])
        np.testing.assert_allclose(np.asarray(trace["xyz"])[:,2], [100,97.5,95])

    def test_horizontal_plane_has_no_strike(self):
        result = plane_from_three_points([[0,0,7],[2,0,7],[0,3,7]])
        self.assertEqual(result["orientationState"], "Horizontal")
        self.assertIsNone(result["strikeAzimuthDegrees"])

    def test_degenerate_and_vertical_single_value_cases_reject(self):
        with self.assertRaises(ValueError):
            plane_from_three_points([[0,0,0],[1,1,1],[2,2,2]])
        with self.assertRaises(ValueError):
            planar_contact_on_vertical_section([1,0,0],0,[0,0],90,[0,1])


if __name__ == "__main__": unittest.main()
