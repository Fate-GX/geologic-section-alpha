import unittest
from geologic_3d_engine.events.channel_geometry_v3 import ClearanceAwareChannelGeometry,make_clearance_aware_spec
from geologic_3d_engine.events.channel_volume_audit import audit_channel_volume_convergence


class ChannelVolumeAuditTests(unittest.TestCase):
    def test_volume_converges_and_fill_is_conserved(self):
        channel=ClearanceAwareChannelGeometry(make_clearance_aware_spec())
        result=audit_channel_volume_convergence(channel,[[0,0],[600,520]],[(40,35),(80,70),(160,140)],.03)
        self.assertTrue(result["passed"])
        self.assertLess(result["maximumVolumeConservationResidual"],1e-8)
        self.assertGreater(result["records"][-1]["incisionVolume"],0)

    def test_too_strict_tolerance_is_typed_failure(self):
        channel=ClearanceAwareChannelGeometry(make_clearance_aware_spec())
        result=audit_channel_volume_convergence(channel,[[0,0],[600,520]],[(20,18),(40,36)],1e-12)
        self.assertFalse(result["passed"])

    def test_invalid_inputs_reject(self):
        channel=ClearanceAwareChannelGeometry(make_clearance_aware_spec())
        for bounds,resolutions,tolerance in (([[0,0],[0,1]],[(2,2),(3,3)],.1),
              ([[0,0],[1,1]],[(1,2),(3,3)],.1),([[0,0],[1,1]],[(2,2)],.1),
              ([[0,0],[1,1]],[(2,2),(3,3)],True)):
            with self.assertRaises(ValueError):audit_channel_volume_convergence(channel,bounds,resolutions,tolerance)


if __name__=="__main__":unittest.main()
