import unittest
import numpy as np
from geologic_3d_engine.events.channel_geometry_v3 import ClearanceAwareChannelGeometry,make_clearance_aware_spec


class ClearanceAwareChannelTests(unittest.TestCase):
    def test_straight_path_passes_without_false_nonlocal_rejection(self):
        spec=make_clearance_aware_spec();spec.update(centerlineXY=[[0,0],[50,0],[100,0],[150,0]],halfWidth=5,
          nonlocalArcSeparationM=200)
        model=ClearanceAwareChannelGeometry(spec)
        self.assertTrue(model.clearance_audit()["passed"])

    def test_close_return_is_rejected_when_minimum_width_impossible(self):
        spec=make_clearance_aware_spec();spec.update(centerlineXY=[[0,0],[10,30],[20,0],[30,30],[40,0],[50,30]],
          halfWidth=15,smoothingIterations=1,nonlocalIndexSeparation=3,minimumHalfWidthFraction=.7)
        spec["nonlocalArcSeparationM"]=35
        spec.pop("nonlocalIndexSeparation",None)
        with self.assertRaisesRegex(ValueError,"ChannelClearanceBelowMinimum"):
            ClearanceAwareChannelGeometry(spec)

    def test_close_return_can_be_narrowed_with_explicit_policy(self):
        spec=make_clearance_aware_spec();spec.update(centerlineXY=[[0,0],[20,35],[40,0],[60,35],[80,0],[100,35]],
          halfWidth=15,smoothingIterations=2,nonlocalIndexSeparation=5,minimumHalfWidthFraction=.1)
        spec["nonlocalArcSeparationM"]=45
        spec.pop("nonlocalIndexSeparation",None)
        model=ClearanceAwareChannelGeometry(spec)
        self.assertTrue(model.clearance_audit()["passed"])
        self.assertLessEqual(model.local_widths.max(),15)

    def test_invalid_policy_rejects(self):
        for key,value in (("nonlocalArcSeparationM",True),("nonlocalArcSeparationM",0),("nonlocalSafetyFactor",.5),("nonlocalSafetyFactor",True)):
            spec=make_clearance_aware_spec();spec[key]=value
            with self.assertRaises(ValueError):ClearanceAwareChannelGeometry(spec)


if __name__=="__main__":unittest.main()
