import unittest

from geologic_3d_engine.section.hypothesis_unit_assembly import (
    assemble_hypothesis_lithology_units)


TERRAIN=[{"stationM":0.0,"elevationM":100.0},{"stationM":50.0,"elevationM":110.0},
         {"stationM":100.0,"elevationM":100.0}]


def clipping(lower=60.0):
    return {"schemaVersion":"ContactTerrainClipping-1.0","contacts":[
        {"hypothesisId":"TOP","nominalSubsurfaceSegments":[[[10,90],[90,90]]]},
        {"hypothesisId":"BOTTOM","nominalSubsurfaceSegments":[[[20,lower],[80,lower]]]}]}


def topology(status="OrderProvenWithinDeclaredEnvelope"):
    return {"schemaVersion":"ContactHypothesisTopologyAudit-1.0","relations":[
        {"aboveHypothesisId":"TOP","belowHypothesisId":"BOTTOM","status":status}]}


class HypothesisUnitAssemblyTests(unittest.TestCase):
    def test_terrain_and_contact_create_positive_support_bounded_polygon(self):
        declarations=[{"unitId":"U1","sourceLabel":"source","normalizedLabel":"unit",
            "evidenceStatus":"SyntheticAssumption","topBoundary":{"type":"Terrain"},
            "bottomBoundary":{"type":"Contact","hypothesisId":"TOP"}}]
        result=assemble_hypothesis_lithology_units(TERRAIN,clipping(),topology(),declarations)
        component=result["units"][0]["components"][0]
        self.assertEqual(component["stationIntervalM"],[10.0,90.0])
        self.assertGreater(component["minimumThicknessM"],0)
        self.assertGreater(component["areaM2"],0)
        self.assertFalse(result["realRegionAuthorized"])

    def test_proven_contact_order_creates_lower_unit_only_on_shared_support(self):
        declarations=[{"unitId":"U2","sourceLabel":"source","normalizedLabel":"unit",
            "evidenceStatus":"EvidenceCandidate",
            "topBoundary":{"type":"Contact","hypothesisId":"TOP"},
            "bottomBoundary":{"type":"Contact","hypothesisId":"BOTTOM"}}]
        result=assemble_hypothesis_lithology_units(TERRAIN,clipping(),topology(),declarations)
        self.assertEqual(result["units"][0]["components"][0]["stationIntervalM"],[20.0,80.0])
        self.assertAlmostEqual(result["units"][0]["components"][0]["areaM2"],1800)

    def test_unproven_order_and_nonpositive_thickness_reject(self):
        declaration={"unitId":"U","sourceLabel":"x","normalizedLabel":"x",
            "evidenceStatus":"SyntheticAssumption",
            "topBoundary":{"type":"Contact","hypothesisId":"TOP"},
            "bottomBoundary":{"type":"Contact","hypothesisId":"BOTTOM"}}
        with self.assertRaises(ValueError):
            assemble_hypothesis_lithology_units(TERRAIN,clipping(),topology("UncertaintyEnvelopeOverlap"),[declaration])
        with self.assertRaises(ValueError):
            assemble_hypothesis_lithology_units(TERRAIN,clipping(95),topology(),[declaration])
        with self.assertRaises(ValueError):
            assemble_hypothesis_lithology_units(TERRAIN,clipping(),topology(),[])

    def test_terrain_contact_may_close_at_outcrop_endpoint_but_not_inside(self):
        declaration={"unitId":"OUTCROP","sourceLabel":"x","normalizedLabel":"x",
            "evidenceStatus":"SyntheticAssumption","topBoundary":{"type":"Terrain"},
            "bottomBoundary":{"type":"Contact","hypothesisId":"TOP"}}
        result=assemble_hypothesis_lithology_units(TERRAIN,{"schemaVersion":"ContactTerrainClipping-1.0",
            "contacts":[{"hypothesisId":"TOP","nominalSubsurfaceSegments":[[[0,100],[50,90]]]}]},
            topology(),[declaration])
        self.assertTrue(result["units"][0]["components"][0]["surfaceClosureAtEndpoint"])
        with self.assertRaises(ValueError):
            assemble_hypothesis_lithology_units(TERRAIN,{"schemaVersion":"ContactTerrainClipping-1.0",
                "contacts":[{"hypothesisId":"TOP","nominalSubsurfaceSegments":[[[0,90],[50,110],[100,90]]]}]},
                topology(),[declaration])


if __name__=="__main__":unittest.main()
