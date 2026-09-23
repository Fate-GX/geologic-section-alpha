import unittest

from geologic_3d_engine.section.mapped_contact_position_uncertainty import (
    build_mapped_contact_position_uncertainty,
)


def inputs(method="SourceDeclaredGroundZone", width=2):
    crossings={"crossings":[{"featureId":"L1","stationM":10,
        "sideClassificationStatus":"MappedUnitTransition"}]}
    support={"routeLengthM":20,"intervals":[{"supportId":"S0"},{"supportId":"S1"}]}
    profile={"boundaries":[{"transitionId":"MAPPED-TRANSITION-0000","method":method,
        "halfWidthM":width,"sourceId":"SRC","locator":"p.1"}]}
    return crossings,support,profile


class ContactPositionUncertaintyTests(unittest.TestCase):
    def test_source_declared_zone_builds_certain_cores(self):
        r=build_mapped_contact_position_uncertainty(*inputs())
        self.assertEqual((r["boundaries"][0]["lowerStationM"],r["boundaries"][0]["upperStationM"]),(8,12))
        self.assertEqual([x["lengthM"] for x in r["certainCores"]],[8,8])

    def test_scale_alone_never_becomes_metres(self):
        a,b,p=inputs("MapScaleOnly",None); p["boundaries"][0]["scaleDenominator"]=50000
        r=build_mapped_contact_position_uncertainty(a,b,p)
        self.assertIsNone(r["boundaries"][0]["lowerStationM"])
        self.assertFalse(r["numericPositionUncertaintyAuthorized"])
        self.assertTrue(all(x["status"]=="UnresolvedBoundaryUncertainty" for x in r["certainCores"]))

    def test_scale_with_invented_width_is_rejected(self):
        a,b,p=inputs("MapScaleOnly",25); p["boundaries"][0]["scaleDenominator"]=50000
        with self.assertRaises(ValueError): build_mapped_contact_position_uncertainty(a,b,p)

    def test_display_assumption_is_not_evidence(self):
        r=build_mapped_contact_position_uncertainty(*inputs("ProjectDisplayAssumption",3))
        self.assertFalse(r["boundaries"][0]["evidenceEligibleNumericZone"])
        self.assertFalse(r["numericPositionUncertaintyAuthorized"])

    def test_missing_duplicate_and_unknown_records_rejected(self):
        a,b,p=inputs()
        for records in ([],p["boundaries"]*2,[dict(p["boundaries"][0],transitionId="BAD")]):
            with self.subTest(records=records):
                with self.assertRaises(ValueError):
                    build_mapped_contact_position_uncertainty(a,b,{"boundaries":records})

