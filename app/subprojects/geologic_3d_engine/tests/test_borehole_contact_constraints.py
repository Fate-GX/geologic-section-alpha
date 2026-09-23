import unittest

from geologic_3d_engine.section.borehole_contact_constraints import build_borehole_contact_constraints


def hole():
    return {"boreholeId": "B", "sourceId": "S", "intervals": [
        {"topDepthM": 0, "bottomDepthM": 4, "evidenceStatus": "Observed"},
        {"topDepthM": 4, "bottomDepthM": 10, "evidenceStatus": "Observed"},
        {"topDepthM": 10, "bottomDepthM": 20, "evidenceStatus": "Observed"}]}


class BoreholeContactConstraintTests(unittest.TestCase):
    def test_relative_contacts_are_point_local(self):
        result = build_borehole_contact_constraints(
            hole(), station_m=25, projection_distance_m=0)
        self.assertEqual([x["depthM"] for x in result["contacts"]], [4, 10])
        self.assertTrue(all(x["relativeDepthConstraintAuthorized"] for x in result["contacts"]))
        self.assertTrue(all(not x["lateralContinuationAuthorized"] for x in result["contacts"]))
        self.assertFalse(result["absoluteElevationConstraintAuthorized"])

    def test_reporting_precision_does_not_authorize_absolute_z(self):
        evidence = {"sectionConstraintAuthorized": False,
                    "roundingIntersectionM": [99.95, 100.05]}
        result = build_borehole_contact_constraints(
            hole(), station_m=0, projection_distance_m=0,
            collar_elevation_evidence=evidence)
        self.assertIsNone(result["contacts"][0]["elevationAccuracyEnvelopeM"])

    def test_verified_accuracy_envelope_translates_z_up(self):
        evidence = {"sectionConstraintAuthorized": True,
                    "accuracyEnvelopeM": [99.8, 100.2]}
        result = build_borehole_contact_constraints(
            hole(), station_m=0, projection_distance_m=2,
            collar_elevation_evidence=evidence)
        self.assertEqual(result["contacts"][0]["elevationAccuracyEnvelopeM"],
                         [95.8, 96.2])
        self.assertTrue(result["absoluteElevationConstraintAuthorized"])

    def test_gap_and_inferred_interval_reject(self):
        broken = hole(); broken["intervals"][1]["topDepthM"] = 5
        with self.assertRaises(ValueError):
            build_borehole_contact_constraints(broken, station_m=0,
                                                projection_distance_m=0)
        inferred = hole(); inferred["intervals"][0]["evidenceStatus"] = "Inferred"
        with self.assertRaises(ValueError):
            build_borehole_contact_constraints(inferred, station_m=0,
                                                projection_distance_m=0)


if __name__ == "__main__":
    unittest.main()
