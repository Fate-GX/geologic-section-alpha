import tempfile
import unittest
from pathlib import Path

from geologic_3d_engine.section.bed_xml import detect_bed_dtd_version, parse_bed_xml
from tests.test_bed0210_xml import xml as xml210
from tests.test_bed0300_xml import xml as xml300
from tests.test_bed0500_xml import xml as xml500


class BedXmlDispatchTests(unittest.TestCase):
    def write(self, content):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/"BED.XML";path.write_bytes(content.encode("cp932"));return path

    def test_supported_versions_dispatch_to_exact_adapter(self):
        for version,content in (("2.10",xml210()),("3.00",xml300()),("5.00",xml500())):
            with self.subTest(version=version):
                path=self.write(content)
                self.assertEqual(detect_bed_dtd_version(path),version)
                result=parse_bed_xml(path,horizontal_crs="EPSG:6668",vertical_datum="Unverified",
                    source_id="S",source_url="U")
                expected={"2.10":"BED0210-DTD-2.10","3.00":"BED0300-DTD-3.00",
                          "5.00":"BED0500-DTD-5.00"}[version]
                self.assertEqual(result["exchangeFormatVersion"],expected)

    def test_unknown_or_missing_version_is_rejected(self):
        for content in (xml300(version="4.00"),"<ボーリング情報></ボーリング情報>"):
            with self.assertRaises(ValueError):
                parse_bed_xml(self.write(content),horizontal_crs="EPSG:6668",
                    vertical_datum="Unverified",source_id="S",source_url="U")


if __name__=="__main__":unittest.main()
