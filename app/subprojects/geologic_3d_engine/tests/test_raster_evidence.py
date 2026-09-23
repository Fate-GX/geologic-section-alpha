import unittest
from geologic_3d_engine.section.raster_evidence import assess_numeric_raster_evidence


class RasterEvidenceTests(unittest.TestCase):
    def test_rendered_rgb_geotiff_without_georeference_is_not_numeric(self):
        result=assess_numeric_raster_evidence({"width":4810,"height":3352,
          "bands":[{"dataType":"Byte","colorInterpretation":"Red"},
                   {"dataType":"Byte","colorInterpretation":"Green"},
                   {"dataType":"Byte","colorInterpretation":"Blue"}],
          "crs":"","geotransform":None,"quantity":"","unit":""})
        self.assertFalse(result["numericSamplingAuthorized"])
        self.assertIn("RenderedColorImage_NotNumericQuantity",result["blockingReasons"])
        self.assertIn("MissingCoordinateReferenceSystem",result["blockingReasons"])

    def test_single_band_georeferenced_float_thickness_is_usable(self):
        result=assess_numeric_raster_evidence({"width":20,"height":10,
          "bands":[{"dataType":"Float32","colorInterpretation":"Gray"}],
          "crs":"EPSG:6670","geotransform":[0,5,0,100,0,-5],
          "quantity":"deposit thickness","unit":"m"})
        self.assertTrue(result["numericSamplingAuthorized"])

    def test_georeferenced_rgb_is_still_not_a_numeric_thickness_field(self):
        result=assess_numeric_raster_evidence({"width":2,"height":2,
          "bands":[{"dataType":"Byte","colorInterpretation":"Palette"}],
          "crs":"EPSG:6670","geotransform":[0,1,0,2,0,-1],
          "quantity":"thickness class colors","unit":"class"})
        self.assertFalse(result["numericSamplingAuthorized"])
        self.assertIn("RenderedColorImage_NotNumericQuantity",result["blockingReasons"])

    def test_incomplete_metadata_is_rejected(self):
        with self.assertRaises(ValueError):assess_numeric_raster_evidence({"width":1})

if __name__=="__main__":unittest.main()
