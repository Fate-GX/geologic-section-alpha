import json,tempfile,unittest
from pathlib import Path
from geologic_3d_engine.gui_conditions import GeographicRouteConditions
from geologic_3d_engine.gui_linework_intake import execute_linework_intake

class LineworkIntakeTests(unittest.TestCase):
    def test_file_to_intersection_artifact(self):
        feature={"featureId":"F","kind":"Fault","verticesLonLat":[[131.005,32.79],[131.005,32.81]],
          "sourceId":"MAP","sourceUrl":"https://example.invalid/map","locationMethod":"MappedLine","locationalConfidence":"ScaleLimited"}
        plan={"terrainProfile":[{"stationM":0,"elevationM":100},{"stationM":1000,"elevationM":110}]}
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"line.json";source.write_text(json.dumps({"features":[feature]}),encoding="utf-8")
            terrain=Path(folder)/"plan.json";terrain.write_text(json.dumps(plan),encoding="utf-8")
            route=GeographicRouteConditions.parse("131,32.8\n131.01,32.8",25)
            result,target=execute_linework_intake(source,terrain,folder,route)
            self.assertTrue(target.is_file());self.assertEqual(len(result["events"]),1)
            self.assertIn("terrainElevationM",result["events"][0]);self.assertEqual(len(result["sourceFileSha256"]),64)
if __name__=="__main__":unittest.main()
