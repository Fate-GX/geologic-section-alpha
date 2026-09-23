import unittest

from geologic_3d_engine.section.gsj_surface_geology import (
    sample_route_legends, validate_legend)


def legend(symbol, rgb=(1,2,3)):
    return {"symbol":symbol, "r":rgb[0], "g":rgb[1], "b":rgb[2],
        "formationAge_ja":"第四紀", "formationAge_en":"Quaternary",
        "group_ja":"堆積岩", "group_en":"Sedimentary rocks",
        "lithology_ja":"礫・砂・泥", "lithology_en":"gravel, sand and mud",
        "title":"第四紀,礫・砂・泥", "value":"".join(f"{v:02x}" for v in rgb)}


class GsjSurfaceGeologyTests(unittest.TestCase):
    def setUp(self):
        self.profile = [{"stationM":i*20, "longitude":131+i/1000,
                         "latitude":32.8, "elevationM":100} for i in range(5)]

    def test_transition_is_interval_censored(self):
        records = iter([legend("A"),legend("A"),legend("B"),legend("B"),legend("C")])
        result = sample_route_legends(self.profile, lambda lat,lon:next(records), "2026-05-10")
        self.assertEqual([x["symbol"] for x in result["mappedUnitIntervals"]], ["A","B","C"])
        self.assertEqual(result["transitions"][0]["estimatedStationM"], 30)
        self.assertEqual(result["transitions"][0]["uncertaintyM"], 10)
        self.assertEqual(result["interpretationBoundary"],
                         "MappedSurfaceUnits_NotSubsurfaceContacts")

    def test_invalid_legend_and_conflicting_colour_are_rejected(self):
        with self.assertRaises(ValueError): validate_legend({"symbol":"A"})
        bad = legend("A"); bad["value"] = "ffffff"
        with self.assertRaises(ValueError): validate_legend(bad)

    def test_level4_response_may_omit_group_fields(self):
        record = legend("A")
        record.pop("group_ja"); record.pop("group_en")
        self.assertEqual(validate_legend(record)["symbol"], "A")

    def test_official_color_metadata_mismatch_can_be_preserved_as_warning(self):
        record=legend("A",(243,226,172));record["value"]="fffa82"
        checked=validate_legend(record,allow_color_metadata_mismatch=True)
        self.assertEqual(checked["sourceColorValue"],"fffa82")
        self.assertEqual(checked["value"],"f3e2ac")
        self.assertEqual(checked["colorMetadataStatus"],"SourceHexRgbMismatch_RgbUsedForDisplay")

    def test_empty_offshore_or_unmapped_response_is_preserved(self):
        records = iter([legend("A"), {}, {"symbol":""}, legend("B"), legend("B")])
        result = sample_route_legends(self.profile, lambda lat,lon:next(records), "edition")
        self.assertEqual([x["symbol"] for x in result["mappedUnitIntervals"]],
                         ["A", None, "B"])
        self.assertEqual(result["samples"][1]["sampleStatus"], "NoMappedUnit")

    def test_missing_and_duplicate_stations_are_rejected(self):
        with self.assertRaises(ValueError):
            sample_route_legends(self.profile[:1]+self.profile[:1],
                                 lambda lat,lon:legend("A"), "edition")
        with self.assertRaises(ValueError):
            sample_route_legends([{"stationM":0}], lambda a,b:legend("A"), "edition")


if __name__ == "__main__": unittest.main()
