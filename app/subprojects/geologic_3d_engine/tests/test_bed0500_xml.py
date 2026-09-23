import tempfile
import unittest
from pathlib import Path

from geologic_3d_engine.section.bed0500_xml import parse_bed0500_xml


def xml(version="5.00", second="30", total="3.0", extra=""):
    return f'''<?xml version="1.0" encoding="Shift_JIS"?>
<!DOCTYPE ボーリング情報 SYSTEM "BED0500.DTD">
<ボーリング情報 DTD_version="{version}"><標題情報><ボーリング名>BH-R8</ボーリング名><ボーリング連番>1</ボーリング連番>
<経度緯度情報><経度_度>131</経度_度><経度_分>30</経度_分><経度_秒>{second}</経度_秒>
<緯度_度>32</緯度_度><緯度_分>15</緯度_分><緯度_秒>0</緯度_秒><測地系>02</測地系></経度緯度情報>
<ボーリング基本情報><孔口標高>500.5</孔口標高><総削孔長>{total}</総削孔長></ボーリング基本情報></標題情報>
<コア情報><工学的地質区分名現場土質名><工学的地質区分名現場土質名_下端深度>1.2</工学的地質区分名現場土質名_下端深度>
<工学的地質区分名現場土質名_工学的地質区分名現場土質名>火山灰質土</工学的地質区分名現場土質名_工学的地質区分名現場土質名></工学的地質区分名現場土質名>
<工学的地質区分名現場土質名><工学的地質区分名現場土質名_下端深度>3.0</工学的地質区分名現場土質名_下端深度>
<工学的地質区分名現場土質名_工学的地質区分名現場土質名>安山岩</工学的地質区分名現場土質名_工学的地質区分名現場土質名></工学的地質区分名現場土質名></コア情報>{extra}</ボーリング情報>'''


class Bed0500XmlTests(unittest.TestCase):
    def parse(self,content):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"BED0001.XML";path.write_bytes(content.encode("cp932"))
            return parse_bed0500_xml(path,horizontal_crs="JGD2011",vertical_datum="TokyoPeil",
                source_id="TEST-BED",source_url="https://example.invalid/bed",evidence_status="Observed")

    def test_r82_dms_depths_labels_and_hash_are_preserved(self):
        result=self.parse(xml())
        self.assertAlmostEqual(result["longitude"],131+30/60+30/3600)
        self.assertEqual(result["intervals"][1]["topElevationM"],499.3)
        self.assertEqual(result["intervals"][1]["bottomElevationM"],497.5)
        self.assertEqual(result["intervals"][0]["sourceLabel"],"火山灰質土")
        self.assertEqual(result["intervals"][0]["termStatus"],"Unverified")
        self.assertEqual(len(result["sourceArtifactSha256"]),64)
        self.assertEqual(result["formatGeodeticSystemCode"],"02")

    def test_unsupported_version_invalid_coordinate_and_depth_are_rejected(self):
        for content in (xml(version="4.00"),xml(second="60"),xml(total="2.0")):
            with self.subTest(content=content[:80]),self.assertRaises(ValueError):self.parse(content)

    def test_entity_declaration_and_missing_explicit_datum_are_rejected(self):
        with self.assertRaises(ValueError):self.parse(xml(extra='<!ENTITY attack "x">'))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"BED.XML";path.write_bytes(xml().encode("cp932"))
            with self.assertRaises(ValueError):
                parse_bed0500_xml(path,horizontal_crs="",vertical_datum="TokyoPeil",
                    source_id="S",source_url="U")


if __name__=="__main__":unittest.main()
