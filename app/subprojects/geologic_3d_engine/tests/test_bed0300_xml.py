import tempfile
import unittest
from pathlib import Path

from geologic_3d_engine.section.bed0300_xml import parse_bed0300_xml


def xml(version="3.00", final_depth="4.0", extra=""):
    return f'''<?xml version="1.0" encoding="Shift_JIS"?>
<!DOCTYPE ボーリング情報 SYSTEM "BED0300.DTD">
<ボーリング情報 DTD_version="{version}"><標題情報><ボーリング名>BH-3</ボーリング名>
<経度緯度情報><経度_度>131</経度_度><経度_分>0</経度_分><経度_秒>33.3</経度_秒>
<緯度_度>32</緯度_度><緯度_分>52</緯度_分><緯度_秒>53.8</緯度_秒><取得方法コード>02</取得方法コード><読取精度コード>0</読取精度コード><測地系>1</測地系></経度緯度情報>
<ボーリング基本情報><孔口標高>513.83</孔口標高><総掘進長>4.0</総掘進長></ボーリング基本情報></標題情報>
<コア情報><岩石土区分><岩石土区分_下端深度>1.5</岩石土区分_下端深度><岩石土区分_岩石土名>ローム</岩石土区分_岩石土名></岩石土区分>
<岩石土区分><岩石土区分_下端深度>{final_depth}</岩石土区分_下端深度><岩石土区分_岩石土名>軽石流堆積物</岩石土区分_岩石土名></岩石土区分></コア情報>{extra}</ボーリング情報>'''


class Bed0300XmlTests(unittest.TestCase):
    def parse(self, content):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "BED.XML"
            path.write_bytes(content.encode("cp932"))
            return parse_bed0300_xml(path, horizontal_crs="EPSG:4612",
                vertical_datum="TokyoPeil", source_id="TEST-BED0300",
                source_url="https://example.invalid/bed0300")

    def test_dms_lithology_and_artifact_are_preserved(self):
        result = self.parse(xml())
        self.assertAlmostEqual(result["longitude"], 131 + 33.3/3600)
        self.assertAlmostEqual(result["latitude"], 32 + 52/60 + 53.8/3600)
        self.assertEqual([x["sourceLabel"] for x in result["intervals"]],
                         ["ローム", "軽石流堆積物"])
        self.assertAlmostEqual(result["intervals"][1]["bottomElevationM"], 509.83)
        self.assertEqual(result["formatGeodeticSystemCode"], "1")
        self.assertEqual(result["coordinateAcquisitionMethodCode"], "02")
        self.assertEqual(result["coordinateReadingPrecisionCode"], "0")
        self.assertEqual(result["exchangeFormatVersion"], "BED0300-DTD-3.00")

    def test_wrong_version_depth_entity_and_missing_crs_are_rejected(self):
        for content in (xml(version="2.10"), xml(final_depth="5.0"),
                        xml(extra='<!ENTITY attack "x">')):
            with self.subTest(content=content[:80]), self.assertRaises(ValueError):
                self.parse(content)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "BED.XML"
            path.write_bytes(xml().encode("cp932"))
            with self.assertRaises(ValueError):
                parse_bed0300_xml(path, horizontal_crs="", vertical_datum="TokyoPeil",
                                  source_id="S", source_url="U")


if __name__ == "__main__":
    unittest.main()
