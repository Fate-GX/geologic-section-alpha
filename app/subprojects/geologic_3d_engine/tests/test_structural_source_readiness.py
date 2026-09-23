import unittest

from geologic_3d_engine.section.structural_source_readiness import (
    audit_structural_source_readiness,
)


def row(**changes):
    value = {
        "recordId": "L1", "sourceId": "SOURCE-1",
        "sourceUrl": "https://example.invalid/source", "featureCount": 2,
        "orientationCount": 0, "basis": "NoOrientationSemantics",
    }
    value.update(changes)
    return value


class StructuralSourceReadinessTests(unittest.TestCase):
    def test_nonstructural_map_points_do_not_create_constraints(self):
        result = audit_structural_source_readiness([row(featureCount=69)])
        self.assertEqual(0, result["directOrientationCount"])
        self.assertFalse(result["directStructuralConstraintAvailable"])

    def test_dem_contact_fit_is_diagnostic_not_direct(self):
        result = audit_structural_source_readiness([row(
            basis="MappedContactDemPlaneFit", featureCount=6,
            orientationCount=6)])
        self.assertEqual(0, result["directOrientationCount"])
        self.assertEqual(6, result["derivedDiagnosticOrientationCount"])
        self.assertFalse(result["records"][0]["directConstraintAuthorized"])

    def test_complete_source_map_orientation_is_a_candidate(self):
        result = audit_structural_source_readiness([row(
            basis="DigitizedSourceMapOrientationSymbol", featureCount=1,
            orientationCount=1, orientations=[{
                "trueDipDegrees": 23.0, "dipDirectionDegrees": 145.0,
                "angularUncertaintyDegrees": 3.0,
            }])])
        self.assertEqual(1, result["directOrientationCount"])
        self.assertTrue(result["directStructuralConstraintAvailable"])

    def test_incomplete_or_impossible_direct_observations_fail_closed(self):
        cases = [
            row(basis="DirectFieldMeasurement", featureCount=1,
                orientationCount=1),
            row(basis="DirectFieldMeasurement", featureCount=1,
                orientationCount=1, orientations=[{
                    "trueDipDegrees": 90.0, "dipDirectionDegrees": 0.0,
                    "angularUncertaintyDegrees": 0.0}]),
            row(featureCount=0, orientationCount=1),
            row(featureCount=1, orientationCount=1),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                audit_structural_source_readiness([case])

    def test_unknown_basis_and_missing_provenance_fail_closed(self):
        for case in (row(basis="TerrainInferred"), row(sourceUrl=""), {}):
            with self.subTest(case=case), self.assertRaises(ValueError):
                audit_structural_source_readiness([case])


if __name__ == "__main__":
    unittest.main()
