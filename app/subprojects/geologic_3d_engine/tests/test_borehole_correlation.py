import copy
import unittest
from geologic_3d_engine.section.borehole_correlation import canonical_sha256,build_correlation_review_template,build_reviewed_borehole_section,create_correlation_review,validate_correlation_review

def intake():
    holes=[]
    for i,(lon,lat) in enumerate(((131,32.8),(131.01,32.8),(131,32.81))):
        holes.append({"boreholeId":f"B{i}","sourceId":f"S{i}","sourceLonLat":[lon,lat],"projectionState":"Projected",
          "intervals":[{"normalizedLithology":"sand","topElevationM":100,"bottomElevationM":90},
                       {"normalizedLithology":"mud","topElevationM":90,"bottomElevationM":75}]})
    return {"schemaVersion":"BoreholeSectionIntake-1.0","boreholes":holes}

def review(data):
    members=lambda n:[{"boreholeId":f"B{i}","intervalIndex":n} for i in range(3)]
    return {"schemaVersion":"BoreholeCorrelationReview-1.0","correlationId":"C1","reviewer":"Test geologist",
      "reviewedAt":"2026-09-04T12:00:00+09:00","intakeSha256":canonical_sha256(data),"reviewStatus":"GeologistInterpreted",
      "unitsBottomUp":[{"unitId":"MUD","normalizedLithology":"mud","members":members(1)},
                       {"unitId":"SAND","normalizedLithology":"sand","members":members(0)}]}

def plan():
    return {"schemaVersion":"PlanEvidenceBundle-1.0","authorizationState":"TerrainPlanOnly_NoSubsurfaceLithologyAuthorization",
      "terrainProfile":[{"stationM":i*100,"longitude":131+.0025*i,"latitude":32.8,"elevationM":105} for i in range(5)]}

class CorrelationTests(unittest.TestCase):
    def test_template_is_bound_but_does_not_claim_review(self):
        data=intake()
        for i,hole in enumerate(data["boreholes"]):
            hole.update(stationM=i*10,projectionDistanceM=2)
            for n,item in enumerate(hole["intervals"]):item.update(intervalIndex=n,sourceLabel=item["normalizedLithology"])
        template=build_correlation_review_template(data)
        self.assertEqual(template["intakeSha256"],canonical_sha256(data))
        self.assertEqual(template["reviewStatus"],"Draft_NotReviewed")
        self.assertEqual(template["unitsBottomUp"],[])
        self.assertEqual(len(template["candidateIntervals"]),3)
    def test_explicit_review_builds_non_authorized_hypothesis(self):
        data=intake();result=build_reviewed_borehole_section(plan(),data,review(data))
        self.assertTrue(all(result["validation"].values()));self.assertFalse(result["realRegionAuthorized"])
        self.assertEqual(result["correlation"]["correlationId"],"C1")
        made=create_correlation_review(data,"C2","Independent reviewer",review(data)["unitsBottomUp"],"2026-09-04T00:00:00Z")
        self.assertEqual(made["intakeSha256"],canonical_sha256(data))
        self.assertEqual(made["reviewStatus"],"GeologistInterpreted")
    def test_tampering_and_missing_review_are_rejected(self):
        data=intake();binding=review(data);changed=copy.deepcopy(data)
        changed["boreholes"][0]["intervals"][0]["bottomElevationM"]=89
        with self.assertRaises(ValueError):validate_correlation_review(changed,binding)
        with self.assertRaises(ValueError):validate_correlation_review(data,{"unitsBottomUp":binding["unitsBottomUp"]})
    def test_wrong_order_duplicate_hole_and_lithology_are_rejected(self):
        data=intake();bad=review(data);bad["unitsBottomUp"].reverse()
        with self.assertRaises(ValueError):validate_correlation_review(data,bad)
        bad=review(data);bad["unitsBottomUp"][0]["members"][1]["boreholeId"]="B0"
        with self.assertRaises(ValueError):validate_correlation_review(data,bad)
        bad=review(data);bad["unitsBottomUp"][0]["normalizedLithology"]="clay"
        with self.assertRaises(ValueError):validate_correlation_review(data,bad)
if __name__=="__main__":unittest.main()
