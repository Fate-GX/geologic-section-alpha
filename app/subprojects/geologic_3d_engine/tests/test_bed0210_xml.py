import tempfile
import unittest
from pathlib import Path

from geologic_3d_engine.section.bed0210_xml import parse_bed0210_xml


def xml(version="2.10", final_depth="3.0", extra=""):
    return f'''<?xml version="1.0" encoding="Shift_JIS"?>
<!DOCTYPE ボーリング情報 SYSTEM "BED0210.DTD">
<ボーリング情報 DTD_version="{version}"><標題情報><ボーリング名>LEGACY-1</ボーリング名>
<経度緯度情報><経度_度>131</経度_度><経度_分>1</経度_分><経度_秒>19.992</経度_秒>
<緯度_度>32</緯度_度><緯度_分>56</緯度_分><緯度_秒>53.016</緯度_秒><測地系>0</測地系></経度緯度情報>
<ボーリング基本情報><孔口標高>475</孔口標高><総掘進長>3.0</総掘進長></ボーリング基本情報></標題情報>
<コア情報><土質岩種区分><土質岩種区分_下端深度>1.0</土質岩種区分_下端深度><土質岩種区分_土質岩種区分1>表土</土質岩種区分_土質岩種区分1></土質岩種区分>
<土質岩種区分><土質岩種区分_下端深度>{final_depth}</土質岩種区分_下端深度><土質岩種区分_土質岩種区分1>砂質シルト</土質岩種区分_土質岩種区分1></土質岩種区分></コア情報>{extra}</ボーリング情報>'''


class Bed0210XmlTests(unittest.TestCase):
    def parse(self, content):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "BED.XML"
            path.write_bytes(content.encode("cp932"))
            return parse_bed0210_xml(
                path,
                horizontal_crs="EPSG:4301",
                vertical_datum="TokyoPeil",
                source_id="TEST-BED0210",
                source_url="https://example.invalid/legacy",
            )

    def test_dms_legacy_labels_depths_and_provenance_are_preserved(self):
        result = self.parse(xml())
        self.assertAlmostEqual(result["longitude"], 131 + 1/60 + 19.992/3600)
        self.assertAlmostEqual(result["latitude"], 32 + 56/60 + 53.016/3600)
        self.assertEqual(result["intervals"][1]["sourceLabel"], "砂質シルト")
        self.assertEqual(result["intervals"][1]["bottomElevationM"], 472.0)
        self.assertEqual(result["formatGeodeticSystemCode"], "0")
        self.assertEqual(result["exchangeFormatVersion"], "BED0210-DTD-2.10")

    def test_wrong_version_depth_entity_and_missing_datum_are_rejected(self):
        for content in (xml(version="5.00"), xml(final_depth="4.0"),
                        xml(extra='<!ENTITY attack "x">')):
            with self.subTest(content=content[:80]), self.assertRaises(ValueError):
                self.parse(content)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "BED.XML"
            path.write_bytes(xml().encode("cp932"))
            with self.assertRaises(ValueError):
                parse_bed0210_xml(path, horizontal_crs="", vertical_datum="TokyoPeil",
                                  source_id="S", source_url="U")


if __name__ == "__main__":
    unittest.main()
