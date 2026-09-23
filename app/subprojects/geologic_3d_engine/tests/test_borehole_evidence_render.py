from pathlib import Path
import tempfile
import unittest

from PIL import Image

from geologic_3d_engine.section.borehole_evidence_render import render_borehole_evidence_section


class BoreholeEvidenceRenderTests(unittest.TestCase):
    def fixtures(self):
        plan = {"schemaVersion":"PlanEvidenceBundle-1.0", "terrainProfile":[
            {"stationM":0,"elevationM":100}, {"stationM":100,"elevationM":110}]}
        hole = {"boreholeId":"BH-X","longitude":131,"latitude":32.8,
            "collarElevationM":105,"totalDepthM":20,"horizontalCrs":"JGD2011",
            "verticalDatum":"TP","sourceId":"SRC","sourceUrl":"https://example.invalid/src",
            "exchangeFormatVersion":"TEST","intervals":[
              {"topDepthM":0,"bottomDepthM":5,"sourceLabel":"A","normalizedLithology":"sand",
               "termStatus":"Current","evidenceStatus":"Observed"},
              {"topDepthM":5,"bottomDepthM":20,"sourceLabel":"B","normalizedLithology":"mud",
               "termStatus":"Current","evidenceStatus":"Observed"}]}
        return plan, hole

    def test_observed_column_is_separate_from_unknown_subsurface(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"column.png"
            result = render_borehole_evidence_section(*self.fixtures(), 40, path,
                                                       width=900, height=500)
            self.assertEqual(result["observedIntervalCount"], 2)
            self.assertEqual(result["lateralInterpolation"], "None")
            self.assertFalse(result["sectionGeometryAuthorized"])
            with Image.open(path) as image:
                self.assertEqual(image.size, (900,500))

    def test_outside_station_and_authorization_promotion_reject(self):
        plan, hole = self.fixtures()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                render_borehole_evidence_section(plan,hole,101,Path(folder)/"x.png")
            with self.assertRaises(ValueError):
                render_borehole_evidence_section(plan,hole,50,Path(folder)/"x.png",
                                                   absolute_elevation_authorized=True)


if __name__ == "__main__": unittest.main()
