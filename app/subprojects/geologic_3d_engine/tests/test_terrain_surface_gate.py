import unittest
from geologic_3d_engine.validation.terrain_surface_gate import audit_route_terrain


def plan():
    return {"layers":[{"evidence_kind":"DEM","source_id":"DEM","canonical_url":"https://example.test/dem",
                       "content_sha256":"a"*64}]}


class TerrainSurfaceGateTests(unittest.TestCase):
    def test_valid_low_relief_surface_is_measured_not_assumed_flat(self):
        result=audit_route_terrain(plan(),[0,100,200,300,400,500],[3.1,3.2,3.15,3.4,3.3,3.25])
        self.assertTrue(result["passed"])
        self.assertEqual(result["classification"],"NearLevel")
        self.assertAlmostEqual(result["surfaceReliefM"],.3)
        self.assertTrue(result["checkedBeforeSubsurfaceGeneration"])

    def test_exactly_flat_long_profile_fails_closed(self):
        result=audit_route_terrain(plan(),[0,100,200],[4,4,4])
        self.assertFalse(result["passed"])
        self.assertIn("ExactlyFlatTerrainRequiresIndependentConfirmation",result["errors"])

    def test_missing_dem_provenance_is_rejected(self):
        result=audit_route_terrain({"layers":[]},[0,10,20],[1,2,3])
        self.assertFalse(result["passed"])
        self.assertIn("MissingDemEvidenceLayer",result["errors"])

    def test_invalid_hash_is_rejected(self):
        value=plan();value["layers"][0]["content_sha256"]="not-a-hash"
        self.assertFalse(audit_route_terrain(value,[0,10,20],[1,2,3])["passed"])


if __name__=="__main__":unittest.main()
