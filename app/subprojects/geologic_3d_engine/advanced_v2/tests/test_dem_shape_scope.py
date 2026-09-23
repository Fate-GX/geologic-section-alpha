"""DEM evidence must not be rejected for failing synthetic mountain aesthetics."""
import unittest
from synthetic_terrain_qa import audit_natural_terrain_texture


class DemShapeScopeTests(unittest.TestCase):
    def test_low_relief_monotonic_dem_is_not_a_resolution_failure(self):
        x=[437.03318808845404*i/44 for i in range(45)]
        z=[75+63.796098610421964*i/44 for i in range(45)]
        before=(list(x),list(z))
        result=audit_natural_terrain_texture(x,z,synthetic_test_only=False)
        self.assertTrue(result['passed'])
        self.assertFalse(result['shapeGateApplicable'])
        self.assertFalse(result['demResolutionVerifiedByThisAudit'])
        self.assertIn('InsufficientMountainRelief',result['shapeDiagnostics'])
        self.assertEqual((x,z),before)
        self.assertFalse(audit_natural_terrain_texture(x,z)['passed'])

    def test_short_flat_dem_remains_valid_evidence(self):
        self.assertTrue(audit_natural_terrain_texture([0,10],[80,80],synthetic_test_only=False)['passed'])

    def test_invalid_evidence_is_still_rejected(self):
        for x,z in (([0,0],[1,2]),([10,0],[1,2]),([0,10],[1,float('nan')]),
                    ([0,float('inf')],[1,2]),([0,10],[1]),([],[])):
            with self.subTest(x=x,z=z),self.assertRaises(ValueError):
                audit_natural_terrain_texture(x,z,synthetic_test_only=False)


if __name__=='__main__':unittest.main()
