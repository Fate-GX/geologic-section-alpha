import math
import unittest

from geologic_3d_engine.section.contact_orientation_stability import audit_multiscale_contact_orientation


def diagnostic(radius, dip, direction, rmse=1.0, feature="C1"):
    dr, dd = math.radians(dip), math.radians(direction)
    normal = [math.sin(dr)*math.sin(dd), math.sin(dr)*math.cos(dd), math.cos(dr)]
    return {"featureId":feature,"radiusM":radius,"fitState":"DiagnosticFitAvailable",
            "planeFit":{"unitNormal":normal,"dipDegrees":dip,
                        "dipDirectionDegrees":direction,"orthogonalRmseM":rmse}}


class ContactOrientationStabilityTests(unittest.TestCase):
    def test_stable_case_is_eligible_but_never_authorized(self):
        result = audit_multiscale_contact_orientation([
            diagnostic(100,10,90), diagnostic(200,11,91), diagnostic(400,9,89)], 90,
            maximum_normal_separation_degrees=5,
            maximum_apparent_dip_spread_degrees=5, maximum_orthogonal_rmse_m=2)
        self.assertEqual(result["stabilityStatus"], "ScaleStableDiagnostic")
        self.assertTrue(result["eligibleForReviewedHypothesis"])
        self.assertFalse(result["subsurfaceContinuationAuthorized"])

    def test_direction_reversal_and_bad_inputs_reject(self):
        result = audit_multiscale_contact_orientation([
            diagnostic(100,20,90), diagnostic(200,2,270), diagnostic(400,15,180)], 90,
            maximum_normal_separation_degrees=10,
            maximum_apparent_dip_spread_degrees=10, maximum_orthogonal_rmse_m=3)
        self.assertEqual(result["stabilityStatus"], "RejectedScaleUnstable")
        with self.assertRaises(ValueError):
            audit_multiscale_contact_orientation([
                diagnostic(100,1,1), diagnostic(200,1,1,feature="C2"), diagnostic(400,1,1)], 0,
                maximum_normal_separation_degrees=5,
                maximum_apparent_dip_spread_degrees=5, maximum_orthogonal_rmse_m=5)
        with self.assertRaises(ValueError):
            audit_multiscale_contact_orientation([diagnostic(100,1,1)]*3, 0,
                maximum_normal_separation_degrees=5,
                maximum_apparent_dip_spread_degrees=5, maximum_orthogonal_rmse_m=5)
        mixed_station = [diagnostic(100,1,1), diagnostic(200,1,1), diagnostic(400,1,1)]
        for station, row in zip((10,10,20), mixed_station): row["stationM"] = station
        with self.assertRaises(ValueError):
            audit_multiscale_contact_orientation(mixed_station, 0,
                maximum_normal_separation_degrees=5,
                maximum_apparent_dip_spread_degrees=5, maximum_orthogonal_rmse_m=5)


if __name__ == "__main__": unittest.main()
