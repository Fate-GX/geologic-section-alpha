import unittest
import numpy as np

from geologic_3d_engine.section.evidence_bounded_surface import (
    EvidenceBoundedRbfSurface, audit_surface_controls)


def control(x, y, z, contact="C", observed=True, authorized=True, support=None,
            role="DirectSubsurfaceContact"):
    return {"xM": x, "yM": y, "zM": z, "contactId": contact,
            "evidenceStatus": "Observed" if observed else "Inferred",
            "absoluteElevationConstraintAuthorized": authorized,
            "independentSupportId": support or f"BH-{x}-{y}",
            "constraintRole": role}


class EvidenceBoundedSurfaceTests(unittest.TestCase):
    def test_triangle_interpolates_inside_and_refuses_outside(self):
        controls = [control(0, 0, 10), control(10, 0, 12), control(0, 10, 7)]
        model = EvidenceBoundedRbfSurface(
            controls, .4, maximum_condition_number=1e12,
            maximum_control_residual_m=1e-9)
        result = model.evaluate([[2, 2], [0, 0], [8, 8]])
        np.testing.assert_allclose(result["elevationM"][:2], [9.8, 10], atol=1e-10)
        self.assertTrue(np.isnan(result["elevationM"][2]))
        self.assertEqual(result["insideEvidenceHull"].tolist(), [True, True, False])

    def test_one_borehole_and_collinear_controls_cannot_make_surface(self):
        one = [control(0, 0, 10)]
        self.assertIn("InsufficientControlCount",
                      [x["code"] for x in audit_surface_controls(one)["errors"]])
        line = [control(0, 0, 1), control(1, 1, 2), control(2, 2, 3)]
        self.assertIn("HorizontalControlsDoNotSpanArea",
                      [x["code"] for x in audit_surface_controls(line)["errors"]])
        with self.assertRaises(ValueError):
            EvidenceBoundedRbfSurface(
                line, .4, maximum_condition_number=1e12,
                maximum_control_residual_m=1e-9)

    def test_mixed_contact_inferred_and_unauthorized_reject(self):
        controls = [control(0, 0, 1), control(1, 0, 2, "D", False),
                    control(0, 1, 3, authorized=False)]
        codes = [item["code"] for item in audit_surface_controls(controls)["errors"]]
        self.assertIn("MixedOrMissingContactIdentity", codes)
        self.assertIn("ControlNotObserved", codes)
        self.assertIn("AbsoluteElevationUnauthorized", codes)

    def test_many_samples_from_one_surface_trace_do_not_count_as_supports(self):
        controls = [control(0, 0, 1, support="TRACE-1", role="MappedSurfaceTrace"),
                    control(1, 0, 2, support="TRACE-1", role="MappedSurfaceTrace"),
                    control(0, 1, 3, support="TRACE-1", role="MappedSurfaceTrace")]
        result = audit_surface_controls(controls)
        codes = [item["code"] for item in result["errors"]]
        self.assertEqual(result["independentSupportCount"], 1)
        self.assertIn("InsufficientIndependentSupportCount", codes)
        self.assertIn("NotDirectSubsurfaceContact", codes)

    def test_numerical_thresholds_are_explicit(self):
        controls = [control(0, 0, 10), control(10, 0, 12), control(0, 10, 7)]
        with self.assertRaises(ValueError):
            EvidenceBoundedRbfSurface(
                controls, .4, maximum_condition_number=1,
                maximum_control_residual_m=1e-9)
        with self.assertRaises(ValueError):
            EvidenceBoundedRbfSurface(
                controls, .4, maximum_condition_number=float("inf"),
                maximum_control_residual_m=1e-9)


if __name__ == "__main__":
    unittest.main()
