import json
from pathlib import Path
import tempfile
import unittest
from geologic_3d_engine.image_preview import generate_model, export_image
from geologic_3d_engine.section.shape_preserving import interpolate
import numpy as np


class ImagePreviewTests(unittest.TestCase):
    def test_monotone_interpolation(self):
        x=np.array([0.,1.,3.,4.]);y=np.array([0.,2.,1.,1.])
        np.testing.assert_allclose(interpolate(x,y,x),y)
        for i in range(3):
            v=interpolate(x,y,np.linspace(x[i],x[i+1],201))
            self.assertTrue(np.all(v>=min(y[i:i+2])-1e-12))
            self.assertTrue(np.all(v<=max(y[i:i+2])+1e-12))
        for knot in x[1:-1]:
            eps=1e-6
            v=interpolate(x,y,[knot-eps,knot,knot+eps])
            self.assertAlmostEqual((v[1]-v[0])/eps,(v[2]-v[1])/eps,places=4)
        with self.assertRaises(ValueError):interpolate(x,y,[-1])

    def test_terrain_samples_and_terminology(self):
        model=generate_model(71)
        for x,z in model["terrainSamples"]:
            self.assertAlmostEqual(model["terrain"][model["x"].index(x)],z)
        for term in model["profile"]["layers"]+[model["profile"]["basement"]]:
            for key in ("SourceLabel","NormalizedLabel","SourceAuthority","SourceYear","NormalizationAuthority","VocabularyVersion","TermStatus","NormalizationNote"):
                self.assertIn(key,term)

    def test_line_toggle_preserves_geometry(self):
        with tempfile.TemporaryDirectory() as temp:
            a=export_image(temp,71,contact_lines="Show");b=export_image(temp,71,contact_lines="Hide")
            self.assertNotEqual(a.read_bytes(),b.read_bytes())
            ma=json.loads(a.with_name("model.json").read_text(encoding="utf-8"))
            mb=json.loads(b.with_name("model.json").read_text(encoding="utf-8"))
            self.assertEqual(ma["layers"],mb["layers"])
            self.assertEqual(mb["drawingSettings"]["contactLines"],"Hide")
            with self.assertRaises(ValueError):export_image(temp,71,contact_lines="unknown")
    def test_replay_and_shared_contacts(self):
        a=generate_model(71);b=generate_model(71);c=generate_model(72)
        self.assertEqual(a,b);self.assertNotEqual(a["layers"],c["layers"])
        self.assertEqual(a["terrain"],c["terrain"])
        self.assertFalse(a["realRegionAuthorized"])
        for previous,current in zip(a["layers"],a["layers"][1:]):
            self.assertEqual(previous["bottom"],current["top"])
        self.assertTrue(a["audit"]["passed"])

    def test_invalid_seeds(self):
        for seed in (-1,2**32,True,1.1,"7"):
            with self.assertRaises(ValueError):generate_model(seed)

    def test_output_and_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            image=export_image(temp,71)
            self.assertEqual(image.read_bytes()[:8],b"\x89PNG\r\n\x1a\n")
            model=json.loads(image.with_name("model.json").read_text(encoding="utf-8"))
            self.assertEqual(model["seed"],71)
            other=export_image(temp,72);self.assertNotEqual(image.parent,other.parent)

    def test_invalid_frames(self):
        with tempfile.TemporaryDirectory() as temp:
            for settings in ({"horizontal_tick":0},{"distance_end":float("nan")},
                             {"vertical_tick":.01},{"distance_end":100},{"elevation_bottom":1300}):
                with self.assertRaises(ValueError):export_image(temp,1,**settings)
            self.assertEqual(list(Path(temp).iterdir()),[])
