import unittest

from geologic_3d_engine.section.contact_terrain_clipping import (
    clip_contact_hypotheses_below_terrain)


def evaluation(slope=-1.0,slope_range=(-1.1,-.9)):
    return {"schemaVersion":"ContactOrientationHypothesisEvaluation-1.0",
        "hypotheses":[{"hypothesisId":"H","supportIntervalM":[0.0,100.0],
            "candidateEndpointsStationElevation":[[0.0,100.0-slope*50.0],
                                                  [100.0,100.0+slope*50.0]],
            "elevationSlopePerStation":slope,
            "elevationSlopeRangePerStation":list(slope_range)}]}


class ContactTerrainClippingTests(unittest.TestCase):
    def test_exact_piecewise_linear_crossing_discards_above_ground(self):
        terrain=[{"stationM":0.0,"elevationM":100.0},
                 {"stationM":50.0,"elevationM":100.0},
                 {"stationM":100.0,"elevationM":100.0}]
        result=clip_contact_hypotheses_below_terrain(evaluation(),terrain,
                                                     elevation_tolerance_m=0)
        contact=result["contacts"][0]
        self.assertEqual(contact["nominalSubsurfaceSegmentCount"],1)
        self.assertEqual(contact["nominalSubsurfaceSegments"][0][0],[50.0,100.0])
        self.assertEqual(contact["nominalSubsurfaceSegments"][0][-1],[100.0,50.0])
        self.assertTrue(all(z<=100 for _,z in contact["nominalSubsurfaceSegments"][0]))
        self.assertFalse(result["realRegionAuthorized"])

    def test_terrain_relief_can_create_multiple_disjoint_subsurface_segments(self):
        terrain=[{"stationM":0.0,"elevationM":140.0},
                 {"stationM":25.0,"elevationM":100.0},
                 {"stationM":50.0,"elevationM":120.0},
                 {"stationM":75.0,"elevationM":50.0},
                 {"stationM":100.0,"elevationM":60.0}]
        result=clip_contact_hypotheses_below_terrain(evaluation(0.0,(-.01,.01)),terrain,
                                                     elevation_tolerance_m=0)
        self.assertGreaterEqual(result["contacts"][0]["nominalSubsurfaceSegmentCount"],1)
        self.assertIn("PossiblyBelowTerrain",
                      {x["certainty"] for x in result["contacts"][0]["samples"]})

    def test_invalid_terrain_and_outside_support_reject(self):
        with self.assertRaises(ValueError):
            clip_contact_hypotheses_below_terrain(evaluation(),[
                {"stationM":0,"elevationM":1},{"stationM":0,"elevationM":2}])
        with self.assertRaises(ValueError):
            clip_contact_hypotheses_below_terrain(evaluation(),[
                {"stationM":1,"elevationM":1},{"stationM":100,"elevationM":2}])


if __name__=="__main__":unittest.main()
