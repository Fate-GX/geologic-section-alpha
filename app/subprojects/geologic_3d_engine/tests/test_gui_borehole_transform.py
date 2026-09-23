import hashlib,json,tempfile,unittest
from pathlib import Path
from geologic_3d_engine.gui_borehole_transform import execute_borehole_geographic_transform
from tests.test_borehole_coordinate_transform import hole,transform


class GuiBoreholeTransformTests(unittest.TestCase):
 def test_transform_collection_preserves_accuracy_block(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/"source.json";operation=root/"operation.json"
   record=hole()|{"horizontalCrsStatus":"Declared","verticalDatumStatus":"Declared",
                  "collarElevationAccuracyStatus":"Unverified"}
   source.write_text(json.dumps({"boreholes":[record]}),encoding="utf-8")
   operation.write_text(json.dumps(transform()),encoding="utf-8")
   result,target=execute_borehole_geographic_transform(source,operation,root/"out")
   self.assertTrue(target.is_file());self.assertEqual(result["boreholes"][0]["horizontalCrs"],"EPSG:6668")
   self.assertFalse(result["sectionConstraintAuthorized"])
   self.assertEqual(result["boreholes"][0]["collarElevationAccuracyStatus"],"Unverified")

 def test_multi_record_and_tampered_transform_reject(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/"source.json";operation=root/"operation.json"
   source.write_text(json.dumps({"boreholes":[hole(),hole()]}),encoding="utf-8")
   operation.write_text(json.dumps(transform()),encoding="utf-8")
   with self.assertRaises(ValueError):execute_borehole_geographic_transform(source,operation,root)
   source.write_text(json.dumps({"boreholes":[hole()]}),encoding="utf-8")
   bad=transform();bad["targetLonLat"][0]+=0.1;operation.write_text(json.dumps(bad))
   with self.assertRaises(ValueError):execute_borehole_geographic_transform(source,operation,root)


if __name__=="__main__":unittest.main()
