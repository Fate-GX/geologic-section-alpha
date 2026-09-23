import unittest
import numpy as np
from geologic_3d_engine.section.erosion_fill_uncertainty import propagate_erosion_fill_ensemble,surface_quantiles


class ErosionFillUncertaintyTests(unittest.TestCase):
    def fixture(self):
        uncon=np.array([[10,10,10],[11,11,11]],float)
        old=[uncon-6,uncon-3,uncon-1]
        return old,uncon,np.array([0,1,.5]),np.array([4,6]),uncon+2,uncon+5

    def test_order_conservation_and_zero_outside(self):
        result=propagate_erosion_fill_ensemble(*self.fixture()[:4],.4,*self.fixture()[4:])
        self.assertEqual(result["negativeOrderedIntervalCount"],0)
        self.assertLess(result["maximumFillConservationResidual"],1e-12)
        self.assertEqual(result["outsideChannelFillMaximum"],0)
        self.assertEqual(result["surfaceSamples"].shape,(2,8,3))

    def test_quantiles_are_ordered(self):
        result=propagate_erosion_fill_ensemble(*self.fixture()[:4],.4,*self.fixture()[4:])
        values=surface_quantiles(result)["values"]
        self.assertTrue(np.all(np.diff(values,axis=0)>=0))

    def test_invalid_shape_and_depth_reject(self):
        old,uncon,shape,depth,cover,terrain=self.fixture()
        for bad_shape,bad_depth in (([0,1,1.1],depth),(shape,[4,0])):
            with self.assertRaises(ValueError):propagate_erosion_fill_ensemble(old,uncon,bad_shape,bad_depth,.4,cover,terrain)


if __name__=="__main__":unittest.main()
