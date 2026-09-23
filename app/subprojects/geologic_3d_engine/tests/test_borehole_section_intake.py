import json
from pathlib import Path
import tempfile
import unittest

from geologic_3d_engine.section.borehole_section_intake import (
    load_and_project_borehole_file,validate_projection_offset)


def record(identifier,lat):
    return {"boreholeId":identifier,"longitude":131.001,"latitude":lat,
      "collarElevationM":100.0,"totalDepthM":10.0,"horizontalCrs":"JGD2011",
      "verticalDatum":"TokyoPeil","sourceId":"PUBLIC-LOG","sourceUrl":"https://example.invalid/log",
      "exchangeFormatVersion":"BED0500-TEST","intervals":[
       {"topDepthM":0.0,"bottomDepthM":10.0,"sourceLabel":"砂","normalizedLithology":"sand",
        "termStatus":"Current","evidenceStatus":"Observed"}]}


class BoreholeSectionIntakeTests(unittest.TestCase):
    def test_file_hash_projection_and_no_correlation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"holes.json"
            path.write_text(json.dumps({"boreholes":[record("N",32.8001),record("F",32.82)]}),encoding="utf-8")
            result=load_and_project_borehole_file(path,[(131,32.8),(131.01,32.8)],100)
        self.assertEqual(result["projectedCount"],1)
        self.assertEqual(result["rejectedByOffsetCount"],1)
        self.assertEqual(result["correlationState"],"NotCorrelated")
        self.assertFalse(result["subsurfaceSurfaceAuthorization"])
        self.assertEqual(result["verticalDatumCompatibility"],"Compatible")
        self.assertEqual(len(result["sourceFileSha256"]),64)

    def test_bad_document_and_offset_are_rejected(self):
        for value in (-1,10001,float("nan"),"x",True):
            with self.subTest(value=value),self.assertRaises(ValueError):validate_projection_offset(value)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"bad.json";path.write_text("{}",encoding="utf-8")
            with self.assertRaises(ValueError):
                load_and_project_borehole_file(path,[(131,32),(132,32)],100)

if __name__=="__main__":unittest.main()
