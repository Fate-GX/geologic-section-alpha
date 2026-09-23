import json
from pathlib import Path
import tempfile
import unittest
from geologic_3d_engine.gui_conditions import GeographicRouteConditions
from geologic_3d_engine.gui_structural_intake import execute_structural_intake

class StructuralIntakeTests(unittest.TestCase):
    def test_source_hash_and_projection_are_persisted(self):
        observation={"observationId":"O","longitude":131.005,"latitude":32.8001,"trueDipDegrees":25,
          "dipDirectionDegrees":90,"sourceId":"FIELD","sourceUrl":"https://example.invalid/field","locationMethod":"GNSS",
          "scientificConfidence":"Measured","locationalConfidence":"Surveyed"}
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"source.json";source.write_text(json.dumps({"observations":[observation]}),encoding="utf-8")
            route=GeographicRouteConditions.parse("131,32.8\n131.01,32.8",25)
            result,target=execute_structural_intake(source,folder,route,100)
            self.assertTrue(target.is_file());self.assertEqual(result["projectedCount"],1)
            self.assertEqual(len(result["sourceFileSha256"]),64)
            self.assertAlmostEqual(result["observations"][0]["apparentDipDegrees"],25)
if __name__=="__main__":unittest.main()
