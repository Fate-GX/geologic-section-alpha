import unittest
from geologic_3d_engine.section.geographic_linework import intersect_geographic_linework,add_terrain_elevations,audit_mapped_contacts

def feature(**changes):
    value={"featureId":"C1","kind":"Contact","verticesLonLat":[[131.005,32.79],[131.005,32.81]],
      "sourceId":"MAP","sourceUrl":"https://example.invalid/map","locationMethod":"MappedLine",
      "locationalConfidence":"ScaleLimited","unitPair":["A","B"],"contactIndex":1}
    value.update(changes);return value

class GeographicLineworkTests(unittest.TestCase):
    def test_crossing_bent_route_preserves_source_and_station(self):
        result=intersect_geographic_linework([[131,32.8],[131.01,32.8],[131.01,32.81]],[feature()])
        self.assertEqual(len(result["events"]),1);event=result["events"][0]
        self.assertEqual(event["sourceId"],"MAP");self.assertAlmostEqual(event["intersectionLonLat"][0],131.005)
        self.assertEqual(event["contactIndex"],1)
        self.assertEqual(event["unitPair"],["A","B"])

    def test_collinear_overlap_is_ambiguous_not_fake_point(self):
        result=intersect_geographic_linework([[131,32.8],[131.01,32.8]],
          [feature(verticesLonLat=[[131.002,32.8],[131.008,32.8]])])
        self.assertEqual(result["events"],[]);self.assertEqual(result["ambiguities"][0]["classification"],"CollinearOverlap_NotPointEvent")

    def test_terrain_and_contact_residual_gate(self):
        crossings=intersect_geographic_linework([[131,32.8],[131.01,32.8]],[feature()])
        profile=[{"stationM":0,"elevationM":100},{"stationM":1000,"elevationM":110}]
        crossings=add_terrain_elevations(crossings,profile);station=crossings["events"][0]["stationM"]
        terrain=crossings["events"][0]["terrainElevationM"]
        section={"stationsM":[0,station,1000],"contactElevationsM":[[0,0,0],[terrain,terrain,terrain]]}
        self.assertTrue(audit_mapped_contacts(section,crossings,1)["passed"])
        section["contactElevationsM"][1]=[0,0,0]
        self.assertFalse(audit_mapped_contacts(section,crossings,1)["passed"])

    def test_fault_metadata_and_invalid_feature(self):
        result=intersect_geographic_linework([[131,32.8],[131.01,32.8]],
          [feature(kind="Fault",faultType="Normal",dipDegrees=60,dipDirectionDegrees=90)])
        self.assertEqual(result["events"][0]["faultType"],"Normal")
        audit=audit_mapped_contacts({"stationsM":[0,1],"contactElevationsM":[[0,0]]},result)
        self.assertEqual(audit["applicability"],"NotApplicable_NoMappedContacts")
        with self.assertRaises(ValueError):intersect_geographic_linework([[131,32.8],[131.01,32.8]],[feature(sourceId="")])

    def test_morphology_kind_requires_explicit_separate_intake(self):
        morphology=feature(kind="CraterRim")
        with self.assertRaises(ValueError):
            intersect_geographic_linework([[131,32.8],[131.01,32.8]],[morphology])
        result=intersect_geographic_linework([[131,32.8],[131.01,32.8]],[morphology],
            allowed_kinds={"CraterRim","Dike","ConcealedLavaFront"},
            interpretation_state="SurfaceMorphologyEvidence_NoLithologyBoundaryPromotion")
        self.assertEqual(result["events"][0]["kind"],"CraterRim")
        self.assertEqual(result["interpretationState"],
                         "SurfaceMorphologyEvidence_NoLithologyBoundaryPromotion")
if __name__=="__main__":unittest.main()
