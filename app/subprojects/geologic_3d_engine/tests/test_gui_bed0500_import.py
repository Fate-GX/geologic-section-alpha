import json
import tempfile
import unittest
from pathlib import Path

from geologic_3d_engine.gui_bed0500_import import execute_bed0500_import
from tests.test_bed0500_xml import xml


class GuiBed0500ImportTests(unittest.TestCase):
    def test_xml_is_persisted_as_unverified_normalized_collection(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/"BED0001.XML"
            source.write_bytes(xml().encode("cp932"))
            result,target=execute_bed0500_import(source,root,horizontal_crs="JGD2011",
                vertical_datum="TokyoPeil",source_id="PUBLIC-BH-1",
                source_url="https://example.invalid/public/BED0001.XML")
            persisted=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(result,persisted)
            self.assertEqual(result["recordCount"],1)
            self.assertEqual(result["boreholes"][0]["intervals"][0]["evidenceStatus"],"Unverified")
            self.assertEqual(result["interpretationBoundary"],"ObservedLogStructure_NotCorrelatedGeologicUnits")


if __name__=="__main__":unittest.main()
