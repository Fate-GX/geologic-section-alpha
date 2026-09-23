"""The map's projected ring and click gate share the route contract limits."""
import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from route_request import (destination, endpoint_geometry, EARTH_RADIUS_M,
                           MIN_SECTION_LENGTH_M, MAX_SECTION_LENGTH_M, AdvancedJapanSectionRequest)
from map_location_selector import (distance_ring_pixels, global_pixel_to_lonlat, lonlat_to_global_pixel,
                                   selection_candidate, GsiRouteSelector)


class DistanceLimitTests(unittest.TestCase):
    def test_point_selection_preserves_zoom_and_center(self):
        class Variable:
            def __init__(self,value):self.value=value
            def get(self):return self.value
            def set(self,value):self.value=value
        for initial_zoom in (10,16):
            selector=SimpleNamespace(_drag=(384,280,[138,36],False,384,280),
                _accepting=False,_render_id=None,center=[138,36],zoom=initial_zoom,
                WIDTH=768,HEIGHT=560,points=[],target=Variable('A'),status=Variable(''),
                _draw_points=Mock(),_update_status=Mock(),_fit_range=Mock())
            GsiRouteSelector._release(selector,SimpleNamespace(x=384,y=280))
            self.assertEqual(len(selector.points),1)
            self.assertEqual(selector.target.get(),'B')
            selector._fit_range.assert_not_called()
            gx,gy=lonlat_to_global_pixel(138,36,initial_zoom)
            bx,by=lonlat_to_global_pixel(*destination(138,36,90,250),initial_zoom)
            selector._drag=(384,280,[138,36],False,384,280)
            GsiRouteSelector._release(selector,SimpleNamespace(x=384+bx-gx,y=280+by-gy))
            self.assertEqual(len(selector.points),2)
            selector._fit_range.assert_not_called()
            self.assertEqual(selector.zoom,initial_zoom)
            self.assertEqual(selector.center,[138,36])

    def test_target_switch_does_not_refit_existing_range(self):
        selector=SimpleNamespace(points=[(138,36)],_draw_points=Mock(),_fit_range=Mock())
        GsiRouteSelector._target_changed(selector)
        selector._fit_range.assert_not_called()

    def test_generation_uses_same_conservative_limit(self):
        self.assertEqual(MAX_SECTION_LENGTH_M,500.0)
        AdvancedJapanSectionRequest(138,36,length_m=500).validate()
        for length in (500.01,6682.78,100000):
            with self.assertRaises(ValueError):
                AdvancedJapanSectionRequest(138,36,length_m=length).validate()

    def test_both_boundaries_are_accepted_in_all_directions(self):
        for anchor in ((131,25),(138,35),(143,44)):
            for distance in (MIN_SECTION_LENGTH_M,MAX_SECTION_LENGTH_M):
                for bearing in range(0,360,15):
                    point=destination(*anchor,bearing,distance)
                    selected=selection_candidate([anchor],'B',point)
                    self.assertEqual(selected,[anchor,point])
                    self.assertAlmostEqual(endpoint_geometry(*selected)[1],distance,places=6)

    def test_just_outside_limits_rejected_without_mutating_selection(self):
        anchor=(138,36);existing=destination(*anchor,70,500)
        for distance in (0,9.99,500.01,6682.78,100000):
            points=[anchor,existing];before=list(points)
            with self.subTest(distance=distance),self.assertRaises(ValueError):
                selection_candidate(points,'B',destination(*anchor,20,distance))
            self.assertEqual(points,before)

    def test_one_point_invalid_second_is_not_added(self):
        points=[(138,36)]
        with self.assertRaises(ValueError):selection_candidate(points,'B',points[0])
        self.assertEqual(len(points),1)

    def test_replacing_a_checks_distance_from_existing_b(self):
        a=(138,36);b=destination(*a,90,500);points=[a,b]
        with self.assertRaises(ValueError):selection_candidate(points,'A',destination(*b,0,110000))
        replacement=destination(*b,0,250)
        self.assertEqual(selection_candidate(points,'A',replacement),[replacement,b])
        self.assertEqual(points,[a,b])

    def test_first_point_still_requires_japan_finite_coordinates(self):
        for point in ((0,0),(138,float('nan')),(True,36),None):
            with self.subTest(point=point),self.assertRaises(ValueError):selection_candidate([],'A',point)

    def test_projected_rings_are_ground_distance_not_fixed_pixel_radius(self):
        for anchor in ((131,25),(138,35),(143,44)):
            lon1,lat1=map(math.radians,anchor)
            for radius in (MIN_SECTION_LENGTH_M,MAX_SECTION_LENGTH_M):
                for zoom in (5,10,16):
                    ring=distance_ring_pixels(anchor,radius,zoom)
                    self.assertEqual(len(ring),181)
                    self.assertAlmostEqual(ring[0][0],ring[-1][0],places=7)
                    for x,y in ring:
                        point=global_pixel_to_lonlat(x,y,zoom)
                        lon2,lat2=map(math.radians,point)
                        h=(math.sin((lat2-lat1)/2)**2
                           +math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2)
                        distance=2*EARTH_RADIUS_M*math.atan2(math.sqrt(h),math.sqrt(1-h))
                        self.assertAlmostEqual(distance,radius,places=6)
                        selection_candidate([anchor],'B',point)


if __name__=='__main__':unittest.main()
