import unittest

from prefecture_catalog import PREFECTURE_NAMES, representative_point
from route_request import AdvancedJapanSectionRequest


class PrefectureCatalogTests(unittest.TestCase):
    def test_all_47_prefectures_have_valid_navigation_points(self):
        self.assertEqual(len(PREFECTURE_NAMES),47)
        self.assertEqual(len(set(PREFECTURE_NAMES)),47)
        for name in PREFECTURE_NAMES:
            longitude,latitude=representative_point(name)
            AdvancedJapanSectionRequest(longitude,latitude).validate()

    def test_yamaguchi_selection_sets_a_valid_editable_start_point(self):
        longitude,latitude=representative_point("山口県")
        self.assertAlmostEqual(longitude,131.4706)
        self.assertAlmostEqual(latitude,34.1861)

    def test_unknown_prefecture_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"unknown Japanese prefecture"):
            representative_point("存在しない県")


if __name__ == "__main__": unittest.main()
