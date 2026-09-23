from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geologic_3d_engine.events.channel_geometry import ChannelGeometry
from geologic_3d_engine.events.channel_geometry_v2 import (
    CurvatureAwareChannelGeometry, make_curvature_aware_spec)


class CurvatureAwareChannelTests(unittest.TestCase):
    def test_straight_channel_preserves_requested_width(self):
        spec = make_curvature_aware_spec()
        spec["centerlineXY"] = [[0., 0.], [50., 0.], [100., 0.]]
        model = CurvatureAwareChannelGeometry(spec)
        self.assertTrue(np.allclose(model.local_widths, spec["halfWidth"]))
        self.assertTrue(model.bank_audit()["passed"])

    def test_tight_bend_reduces_local_width(self):
        spec = make_curvature_aware_spec()
        spec.update(centerlineXY=[[0., 0.], [20., 0.], [25., 20.], [50., 20.]],
                    halfWidth=15.)
        model = CurvatureAwareChannelGeometry(spec)
        self.assertLess(model.local_widths.min(), 15.)
        self.assertGreaterEqual(model.local_widths.min(), 15. * spec["minimumHalfWidthFraction"])

    def test_v1_is_unchanged_and_v2_is_distinct(self):
        spec = make_curvature_aware_spec(91)
        base = {k: v for k, v in spec.items() if k not in {
            "smoothingIterations", "curvatureSafetyFactor", "minimumHalfWidthFraction"}}
        points = np.array([[300., y] for y in np.linspace(0, 800, 31)])
        v1 = ChannelGeometry(base).surfaces(points)["incision"]
        v2 = CurvatureAwareChannelGeometry(spec).surfaces(points)["incision"]
        self.assertFalse(np.array_equal(v1, v2))

    def test_bank_audit_is_deterministic(self):
        a = CurvatureAwareChannelGeometry(make_curvature_aware_spec(18)).bank_audit()
        b = CurvatureAwareChannelGeometry(make_curvature_aware_spec(18)).bank_audit()
        self.assertEqual(a, b)

    def test_invalid_policy_values_are_rejected(self):
        for key, value in [("smoothingIterations", 0), ("smoothingIterations", True),
                           ("curvatureSafetyFactor", 1), ("minimumHalfWidthFraction", 0)]:
            spec = make_curvature_aware_spec(); spec[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                CurvatureAwareChannelGeometry(spec)


if __name__ == "__main__":
    unittest.main()
