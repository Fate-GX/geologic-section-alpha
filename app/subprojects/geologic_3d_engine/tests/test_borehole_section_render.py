from pathlib import Path
import tempfile
import unittest
from PIL import Image
from geologic_3d_engine.section.borehole_section_render import render_borehole_section

class RenderTests(unittest.TestCase):
    def test_render_contains_section_and_stick_log(self):
        section={"stationsM":[0,100,200],"terrainElevationM":[100,105,100],
          "contactElevationsM":[[60,62,61],[80,82,81]],
          "units":[{"unitId":"U","normalizedLithology":"sand"}]}
        intake={"boreholes":[{"boreholeId":"B1","stationM":100,"projectionDistanceM":5,
          "projectionState":"Projected","collarElevationM":105,
          "intervals":[{"bottomElevationM":80}]}]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"section.png";render_borehole_section(section,intake,path,600,400)
            self.assertTrue(path.is_file())
            with Image.open(path) as image:self.assertEqual(image.size,(600,400))
if __name__=="__main__":unittest.main()
