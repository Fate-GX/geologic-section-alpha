import json,tempfile,unittest
from pathlib import Path
from geologic_3d_engine.gui_basic_section import load_basic_section_regions,execute_basic_section_preview

class BasicSectionGuiBackendTests(unittest.TestCase):
 def test_catalog_and_backend_generate_separated_artifacts(self):
  regions=load_basic_section_regions();self.assertIn("阿蘇",next(iter(regions)))
  with tempfile.TemporaryDirectory() as folder:
   image,model=execute_basic_section_preview(folder,next(iter(regions.values())),seed=93,distance_end=2200,
     elevation_bottom=650,elevation_top=1400,horizontal_tick=500,vertical_tick=100,contact_lines="Show")
   self.assertEqual(image.read_bytes()[:8],b"\x89PNG\r\n\x1a\n")
   data=json.loads(model.read_text(encoding="utf-8"))
   self.assertEqual(data["moduleSeparation"],"TerrainIndependentLithology_ExplicitComposition")
   self.assertFalse(data["lithologyModel"]["terrainInputAccepted"])
 def test_catalog_rejects_missing_profile(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/"regions.json";path.write_text(json.dumps({"schemaVersion":"BasicSectionRegionCatalog-1.0",
     "regions":[{"label":"X","profile":"missing.json","defaults":{}}]}),encoding="utf-8")
   with self.assertRaises(ValueError):load_basic_section_regions(path)
