import copy
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from geologic_3d_engine.events.channel_geometry import ChannelGeometry,make_synthetic_spec
from geologic_3d_engine.events.stratigraphic_events import voxelize_event_model
from geologic_3d_engine.geometry.regular_grid import RegularGrid3D
from geologic_3d_engine.models import Extent3D


def straight():
    s = make_synthetic_spec()
    s.update(centerlineXY=[[-20.,10.],[40.,10.]],halfWidth=5.)
    return s


class ChannelTests(unittest.TestCase):
    def test_straight_distance_bed_and_banks(self):
        m = ChannelGeometry(straight())
        s = m.surfaces([[0,10],[0,12.5],[0,15],[0,16]])
        np.testing.assert_allclose(s["distance"],[0,2.5,5,6])
        np.testing.assert_allclose(s["bed"],[50,57.5,80,80])
        np.testing.assert_allclose(s["split"],[62,66.5,80,80])

    def test_caps_and_bend(self):
        spec = straight();spec["centerlineXY"]=[[0.,0.],[10.,0.],[20.,10.]]
        m = ChannelGeometry(spec)
        s = m.surfaces([[-3,4],[15,0],[22,12]])
        np.testing.assert_allclose(s["distance"],[5,np.sqrt(12.5),np.sqrt(8)])

    def test_boundary_ownership(self):
        m = ChannelGeometry(straight())
        xyz = [[0,10,z] for z in [-1,0,49,50,50.01,62,62.01,80,81]]
        self.assertEqual(m.classify(xyz).tolist(),[0,0,1,1,3,3,4,4,0])
        self.assertEqual(m.classify([[0,15,79],[0,16,79]]).tolist(),[2,2])

    def test_existing_engine_voxelization_matches_query(self):
        grid = RegularGrid3D.from_extent(Extent3D((0,0,0),(20,20,100),(5,5,5)))
        m = ChannelGeometry(straight());model = m.build_engine_model(grid)
        r = voxelize_event_model(model)
        self.assertTrue(r["passed"])
        lookup = {None:0,"HOST_LOWER":1,"HOST_UPPER":2,"FILL_LOWER":3,"FILL_UPPER":4}
        actual = np.array([lookup[v] for plane in r["labelsZYX"] for row in plane for v in row])
        xyz = [[grid.x_center(x),grid.y_center(y),grid.z_center(z)] for z,y,x in np.ndindex(grid.shape_zyx)]
        np.testing.assert_array_equal(actual,m.classify(xyz))
        self.assertEqual([v["eventType"] for v in model.event_log],["Erosion","ErosionFill","Onlap"])
        bodies = {b.unit_id:b for b in model.primary_bodies}
        np.testing.assert_allclose(bodies["FILL_UPPER"].bottom,bodies["FILL_LOWER"].top)

    def test_straight_volume_refinement(self):
        m = ChannelGeometry(straight());errors = []
        for n in (10,20,40):
            y = 5+(np.arange(n)+.5)*10/n
            area = m.surfaces(np.column_stack((np.zeros(n),y)))["incision"].sum()*10/n
            errors.append(abs(area-4*5*30/3))
        self.assertGreater(errors[0],errors[1]);self.assertGreater(errors[1],errors[2])
        self.assertLess(errors[-1],.1)

    def test_seed_and_sampling_independence(self):
        a = make_synthetic_spec(11);self.assertEqual(a,make_synthetic_spec(11))
        self.assertNotEqual(a["centerlineXY"],make_synthetic_spec(12)["centerlineXY"])
        m = ChannelGeometry(a)
        points = np.random.default_rng(55).uniform([0,0,0],[1200,800,100],size=(73,3))
        expected = m.classify(points)
        actual = np.concatenate([m.classify(chunk) for chunk in np.array_split(points,7)])
        np.testing.assert_array_equal(actual,expected)
        before = copy.deepcopy(a);m.classify(points);self.assertEqual(before,a)

    def test_invalid_and_out_of_scope(self):
        variants = [("halfWidth",0),("depth",81),("lowerFillFraction",1),("topElevation",float('nan')),
                    ("region","Aso"),("realRegionAuthorized",True),("basis","Observed"),
                    ("centerlineXY",[[0,0],[0,1]]),("seed",True),("hostBoundary",90)]
        for key,value in variants:
            s = straight();s[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):ChannelGeometry(s)
        s = straight();s.pop("depth")
        with self.assertRaises(ValueError):ChannelGeometry(s)
        s = straight();s["unknown"]=1
        with self.assertRaises(ValueError):ChannelGeometry(s)

    def test_query_validation(self):
        m = ChannelGeometry(straight())
        for q in ([[0,1]],[[0,np.inf,2]],[1,2,3]):
            with self.assertRaises(ValueError):m.classify(q)
        self.assertEqual(m.classify(np.empty((0,3))).size,0)


if __name__=="__main__":unittest.main()
