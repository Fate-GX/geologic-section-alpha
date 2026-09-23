import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from geologic_3d_engine.section.mapped_contact_review import (canonical_sha256,
  build_mapped_contact_review_template,validate_mapped_contact_review)

def adjacency():
    row={"featureId":"C1","stationM":50.0,"terrainElevationM":100.0,
      "kind":"Contact","sideClassificationStatus":"MappedUnitTransition",
      "unitPair":[{"sourcePolygonFeatureId":10,"legends":[]},{"sourcePolygonFeatureId":20,"legends":[]}]}
    value={"schemaVersion":"GsjRouteCrossingSideClassification-1.0","crossingCount":1,
      "crossings":[row],"authorizationBoundary":"MappedSurfaceAdjacencyOnly_NoSubsurfaceContinuation"}
    value["recordSha256"]=canonical_sha256(value);return value
def correlation():return {"unitsBottomUp":[{"unitId":"OLD"},{"unitId":"YOUNG"}]}
class MappedContactReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/"adj.json"
        self.a=adjacency();self.c=correlation();self.path.write_text(json.dumps(self.a),encoding="utf-8")
        self.r=build_mapped_contact_review_template(self.path,self.c)
        self.r.update(reviewer="R",reviewedAt="2026-09-05T00:00:00Z",reviewStatus="GeologistInterpreted")
    def tearDown(self):self.temp.cleanup()
    def use(self):return {"featureId":"C1","sourcePolygonFeatureIds":[10,20],
      "decision":"UseAsSectionContact","contactIndex":1,"modelUnitPair":["OLD","YOUNG"]}
    def test_used_contact_is_bound_and_emitted(self):
        self.r["decisions"]=[self.use()];result=validate_mapped_contact_review(self.a,self.c,self.r)
        self.assertEqual(result["events"][0]["contactIndex"],1);self.assertEqual(result["review"]["usedCount"],1)
    def test_explicit_exclusion(self):
        self.r["decisions"]=[{"featureId":"C1","sourcePolygonFeatureIds":[10,20],"decision":"Exclude","reason":"unit absent"}]
        self.assertEqual(validate_mapped_contact_review(self.a,self.c,self.r)["events"],[])
    def test_wrong_direction_contact_or_binding_is_rejected(self):
        cases=[]
        x=self.use();x["sourcePolygonFeatureIds"]=[20,10];cases.append(x)
        x=self.use();x["contactIndex"]=0;cases.append(x)
        x=self.use();x["modelUnitPair"]=["OLD","OTHER"];cases.append(x)
        for decision in cases:
            review=copy.deepcopy(self.r);review["decisions"]=[decision]
            with self.assertRaises(ValueError):validate_mapped_contact_review(self.a,self.c,review)
        review=copy.deepcopy(self.r);review["adjacencyRecordSha256"]="0"*64;review["decisions"]=[self.use()]
        with self.assertRaises(ValueError):validate_mapped_contact_review(self.a,self.c,review)
    def test_missing_decision_and_changed_candidates_are_rejected(self):
        with self.assertRaises(ValueError):validate_mapped_contact_review(self.a,self.c,self.r)
        self.r["candidates"][0]["stationM"]+=1;self.r["decisions"]=[self.use()]
        with self.assertRaises(ValueError):validate_mapped_contact_review(self.a,self.c,self.r)
if __name__=="__main__":unittest.main()
