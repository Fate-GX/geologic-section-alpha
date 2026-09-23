import io
import unittest
from unittest.mock import patch
from PIL import Image

from map_location_selector import (global_pixel_to_lonlat,lonlat_to_global_pixel,
                                   query_gsi_elevation)


class _Response:
    def __init__(self,payload):self.payload=payload
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self):return self.payload


def _dem_png(encoded):
    image=Image.new("RGB",(256,256),(encoded//65536,(encoded//256)%256,encoded%256))
    data=io.BytesIO();image.save(data,format="PNG");return data.getvalue()


class MapLocationSelectorTests(unittest.TestCase):
    def test_web_mercator_round_trip_for_yamaguchi(self):
        for zoom in (5,10,16):
            pixel=lonlat_to_global_pixel(131.4706,34.1861,zoom)
            longitude,latitude=global_pixel_to_lonlat(*pixel,zoom)
            self.assertAlmostEqual(longitude,131.4706,places=10)
            self.assertAlmostEqual(latitude,34.1861,places=10)

    def test_invalid_mercator_coordinate_is_rejected(self):
        with self.assertRaises(ValueError):lonlat_to_global_pixel(131,90,10)

    @patch("map_location_selector.urllib.request.urlopen")
    def test_finite_land_elevation_is_accepted(self,open_url):
        open_url.return_value=_Response(_dem_png(2540))
        self.assertAlmostEqual(query_gsi_elevation(131.4706,34.1861),25.4)

    @patch("map_location_selector.urllib.request.urlopen")
    def test_missing_ocean_elevation_fails_closed(self,open_url):
        open_url.return_value=_Response(_dem_png(2**23))
        with self.assertRaisesRegex(ValueError,"DEM"):
            query_gsi_elevation(135.0,20.0)


if __name__=="__main__":unittest.main()
