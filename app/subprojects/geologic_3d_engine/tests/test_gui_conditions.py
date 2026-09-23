from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from geologic_3d_engine.gui_conditions import DrawingConditions,GeographicRouteConditions,bundle_details,execute_conditions

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/"examples/stage11_gui_run_bundle.json"

class GuiConditionsTests(unittest.TestCase):
    def setUp(self):self.config,self.default=bundle_details(BUNDLE)
    def test_defaults(self):
        self.assertEqual(self.default,DrawingConditions())
        self.default.validate(self.config)
    def test_invalid_numbers(self):
        for value in (float("nan"),float("inf"),True):
            with self.subTest(value=value),self.assertRaises(ValueError):
                replace(self.default,x_end=value).validate(self.config)
    def test_limits(self):
        for change in ({"horizontal_tick":0},{"vertical_tick":-1},{"x_end":50},
                       {"elevation_bottom":-20},{"section_y":100},{"horizontal_tick":0.1}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                replace(self.default,**change).validate(self.config)
    def test_larger_frame_does_not_change_model(self):
        c=replace(self.default,x_end=500,horizontal_tick=100)
        c.validate(self.config)
        self.assertEqual(self.config["extent"]["maximum"][0],100)
        self.assertEqual(c.ticks()["horizontalMeters"],[0,100,200,300,400,500])
    def test_tick_boundary(self):
        replace(self.default,horizontal_tick=1).validate(self.config)
        self.assertEqual(len(replace(self.default,horizontal_tick=1).ticks()["horizontalMeters"]),101)
    def test_actual_run_persists_settings_without_editing_source(self):
        original=BUNDLE.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            result,run=execute_conditions(BUNDLE,folder,self.default)
            self.assertTrue(result["passed"])
            settings=json.loads((run/"drawing_settings.json").read_text(encoding="utf-8"))
            self.assertFalse(settings["realRegionAuthorized"])
            self.assertIn("NativeDwgNotImplemented",settings["tickStatus"])
            section=json.loads((run/"inputs/sectionSpec.json").read_text())
            self.assertEqual(section["vRange"],[-50,50])
            self.assertTrue((run/"outputs/neutral_contract.json").is_file())
        self.assertEqual(BUNDLE.read_bytes(),original)

    def test_geographic_route_conditions(self):
        route=GeographicRouteConditions.parse("131.0,32.0\n131.1,32.2\n",25)
        self.assertEqual(route.vertices,((131.0,32.0),(131.1,32.2)))
        self.assertEqual(route.sample_spacing_m,25.0)
        self.assertEqual(route.terrain_sampling_method,"BilinearPixelCentres")
        nearest=GeographicRouteConditions.parse("131.0,32.0\n131.1,32.2",25,"NearestPixel")
        self.assertEqual(nearest.terrain_sampling_method,"NearestPixel")

    def test_geographic_route_rejects_bad_input(self):
        cases=(("131,32",0),("131,32",25),("181,32\n131,33",25),
               ("131,32\n131,32",25),("131;32\n132,33",25))
        for text,spacing in cases:
            with self.subTest(text=text,spacing=spacing),self.assertRaises(ValueError):
                GeographicRouteConditions.parse(text,spacing)
        with self.assertRaises(ValueError):
            GeographicRouteConditions.parse("131,32\n132,33",25,"Cubic")

if __name__=="__main__":unittest.main()
