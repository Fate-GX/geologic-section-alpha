import hashlib,json,tempfile,unittest
from pathlib import Path
from geologic_3d_engine.section.mapped_polygon_adjacency import (load_mapped_polygon_adjacency,
  select_geologic_contact_intersections)

def signed(row):
    value={"schemaVersion":"GsjRouteCrossingSideClassification-1.0","crossingCount":1,
      "crossings":[row],"authorizationBoundary":"MappedSurfaceAdjacencyOnly_NoSubsurfaceContinuation"}
    value["recordSha256"]=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
      ensure_ascii=False).encode()).hexdigest();return value
class MappedPolygonAdjacencyTests(unittest.TestCase):
    def check(self,value,accepted):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"x.json";path.write_text(json.dumps(value),encoding="utf-8")
            if accepted:self.assertEqual(load_mapped_polygon_adjacency(path)["crossingCount"],1)
            else:
                with self.assertRaises(ValueError):load_mapped_polygon_adjacency(path)
    def test_valid_transition(self):
        self.check(signed({"sideClassificationStatus":"MappedUnitTransition","unitPair":[
          {"sourcePolygonFeatureId":1},{"sourcePolygonFeatureId":2}]}),True)
    def test_unresolved_cannot_claim_pair(self):
        self.check(signed({"sideClassificationStatus":"AmbiguousPolygonCoverage","unitPair":[
          {"sourcePolygonFeatureId":1},{"sourcePolygonFeatureId":2}]}),False)
        self.check(signed({"sideClassificationStatus":"NonGeologicSurfaceBoundary","unitPair":None}),True)
    def test_same_unit_and_tamper_are_rejected(self):
        value=signed({"sideClassificationStatus":"MappedUnitTransition","unitPair":[
          {"sourcePolygonFeatureId":1},{"sourcePolygonFeatureId":1}]});self.check(value,False)
        value=signed({"sideClassificationStatus":"MappedUnitTransition","unitPair":[
          {"sourcePolygonFeatureId":1},{"sourcePolygonFeatureId":2}]})
        value["crossingCount"]=2;self.check(value,False)
    def test_geologic_selector_excludes_water_boundary_and_requires_match(self):
        events={"events":[{"featureId":"C1","kind":"Contact","stationM":10.0},
                          {"featureId":"W1","kind":"Contact","stationM":20.0}]}
        adjacency={"crossings":[
          {"featureId":"C1","stationM":10.01,"sideClassificationStatus":"MappedUnitTransition",
           "unitPair":[{"sourcePolygonFeatureId":1},{"sourcePolygonFeatureId":2}]},
          {"featureId":"W1","stationM":20.0,"sideClassificationStatus":"NonGeologicSurfaceBoundary",
           "unitPair":None}]}
        result=select_geologic_contact_intersections(events,adjacency)
        self.assertEqual([v["featureId"] for v in result],["C1"])
        self.assertEqual(result[0]["surfaceClassification"],"MappedUnitTransition")
        with self.assertRaises(ValueError):
            select_geologic_contact_intersections(events,{"crossings":adjacency["crossings"][:1]})
if __name__=="__main__":unittest.main()
