import copy
import hashlib
import json
import unittest

from geologic_3d_engine.section.collar_elevation_audit import audit_collar_against_dem


def observation(elevation=100.4, vertical="TokyoPeil"):
    value = {"schemaVersion": "PointDemObservation-1.0", "sourceId": "GSI-DEM5A",
        "sourceUrl": "https://example.invalid/tile.png", "sourceCrs": "EPSG:6668",
        "verticalReference": vertical, "longitude": 130.0, "latitude": 32.0,
        "elevationM": elevation, "samplingMethod": "NearestPixelCentre",
        "rasterArtifactSha256": "a" * 64}
    value["recordSha256"] = hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    return value


class CollarElevationAuditTests(unittest.TestCase):
    def setUp(self):
        self.hole = {"sourceId": "H", "longitude": 130.0, "latitude": 32.0,
                     "collarElevationM": 100.0, "horizontalCrs": "EPSG:6668",
                     "verticalDatum": "TokyoPeil"}

    def test_difference_and_boundary_never_authorize(self):
        result = audit_collar_against_dem(self.hole, observation(), 0.4)
        self.assertAlmostEqual(result["signedDifferenceM"], 0.4)
        self.assertEqual(result["comparisonClass"], "ConsistentWithinDiagnosticThreshold")
        self.assertEqual(result["collarElevationAccuracyStatus"], "Unverified")
        self.assertFalse(result["sectionConstraintAuthorized"])
        above = audit_collar_against_dem(self.hole, observation(100.401), 0.4)
        self.assertEqual(above["comparisonClass"], "DifferenceExceedsDiagnosticThreshold")

    def test_vertical_reference_mismatch_is_typed(self):
        result = audit_collar_against_dem(self.hole, observation(vertical="Unknown"), 1.0)
        self.assertEqual(result["comparisonClass"], "VerticalReferenceUnresolved")
        self.assertFalse(result["verticalReferenceCompatible"])

    def test_hash_coordinate_crs_and_threshold_tampering_reject(self):
        bad = observation(); bad["elevationM"] += 1
        with self.assertRaises(ValueError): audit_collar_against_dem(self.hole, bad, 1.0)
        for key, value in (("longitude", 130.1), ("horizontalCrs", "EPSG:4612")):
            hole = copy.deepcopy(self.hole); hole[key] = value
            with self.assertRaises(ValueError): audit_collar_against_dem(hole, observation(), 1.0)
        with self.assertRaises(ValueError): audit_collar_against_dem(self.hole, observation(), float("nan"))


if __name__ == "__main__": unittest.main()
