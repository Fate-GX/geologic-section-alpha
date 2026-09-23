import tempfile
import unittest
from pathlib import Path

from geologic_3d_engine.section.bed0400_xml import parse_bed0400_xml
from geologic_3d_engine.section.bed_xml import parse_bed_xml


def xml(version="4.00", total="3.0", extra=""):
    return f'''<?xml version="1.0" encoding="Shift_JIS"?>
<!DOCTYPE ボーリング情報 SYSTEM "BED0400.DTD">
<ボーリング情報 DTD_version="{version}"><標題情報><ボーリング名>BH-H28</ボーリング名>
<経度緯度情報><経度_度>131</経度_度><経度_分>1</経度_分><経度_秒>45.92</経度_秒>
<緯度_度>32</緯度_度><緯度_分>51</緯度_分><緯度_秒>22.61</緯度_秒><取得方法コード>01</取得方法コード><読取精度コード>2</読取精度コード><測地系>01</測地系></経度緯度情報>
<ボーリング基本情報><孔口標高>548.16</孔口標高><総削孔長>{total}</総削孔長></ボーリング基本情報></標題情報>
<コア情報><工学的地質区分名現場土質名><工学的地質区分名現場土質名_下端深度>1.2</工学的地質区分名現場土質名_下端深度>
<工学的地質区分名現場土質名_工学的地質区分名現場土質名>火山灰質土</工学的地質区分名現場土質名_工学的地質区分名現場土質名></工学的地質区分名現場土質名>
<工学的地質区分名現場土質名><工学的地質区分名現場土質名_下端深度>3.0</工学的地質区分名現場土質名_下端深度>
<工学的地質区分名現場土質名_工学的地質区分名現場土質名>安山岩</工学的地質区分名現場土質名_工学的地質区分名現場土質名></工学的地質区分名現場土質名></コア情報>{extra}</ボーリング情報>'''


class Bed0400XmlTests(unittest.TestCase):
    def parse(self, content, dispatcher=False):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"BED.XML";path.write_bytes(content.encode("cp932"))
            parser=parse_bed_xml if dispatcher else parse_bed0400_xml
            return parser(path,horizontal_crs="EPSG:6668",vertical_datum="TokyoPeil",
                source_id="TEST-BED0400",source_url="https://example.invalid/bed0400",
                horizontal_position_accuracy_status="DeclaredResolutionOnly")

    def test_dtd4_fields_dispatch_and_accuracy_boundary(self):
        result=self.parse(xml(),dispatcher=True)
        self.assertAlmostEqual(result["longitude"],131+1/60+45.92/3600)
        self.assertEqual(result["exchangeFormatVersion"],"BED0400-DTD-4.00")
        self.assertEqual(result["coordinateAcquisitionMethodCode"],"01")
        self.assertEqual(result["coordinateReadingPrecisionCode"],"2")
        self.assertEqual([x["sourceLabel"] for x in result["intervals"]],["火山灰質土","安山岩"])
        self.assertFalse(result["elevationConstraintAuthorized"])

    def test_wrong_version_depth_and_entity_are_rejected(self):
        for content in (xml(version="5.00"),xml(total="2.0"),xml(extra='<!ENTITY attack "x">')):
            with self.subTest(content=content[:80]),self.assertRaises(ValueError):
                self.parse(content)


if __name__=="__main__":unittest.main()
