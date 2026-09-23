import unittest

from geologic_3d_engine.section.mapped_surface_support import (
    build_mapped_surface_support_intervals,
)


def morphology():
    return {"units": [
        {"unitId": "A", "sourcePolygonFeatureId": 1, "symbol": "a",
         "morphologyClass": "SurficialFallDepositDrape", "finiteBodyRequired": False},
        {"unitId": "B", "sourcePolygonFeatureId": 2, "symbol": "b",
         "morphologyClass": "ScoriaConeAndLavaFlowApron", "finiteBodyRequired": True},
    ]}


def crossing(station, before, after, status="MappedUnitTransition"):
    return {"stationM": station, "sideClassificationStatus": status,
            "unitPair": [{"sourcePolygonFeatureId": before},
                         {"sourcePolygonFeatureId": after}] if before is not None else None}


class MappedSurfaceSupportTests(unittest.TestCase):
    def test_repeated_finite_unit_components_are_not_bridged(self):
        record = {"crossings": [crossing(20, 1, 2), crossing(40, 2, 1),
                                crossing(70, 1, 2)]}
        result = build_mapped_surface_support_intervals(record, 100, morphology())
        self.assertEqual(4, result["supportIntervalCount"])
        finite = [row for row in result["intervals"] if row["unitId"] == "B"]
        self.assertEqual([[20.0, 40.0], [70.0, 100.0]],
                         [[row["startStationM"], row["endStationM"]] for row in finite])
        self.assertEqual([0, 1], [row["componentIndexForUnit"] for row in finite])
        self.assertTrue(all(not row["lateralGapBridgingAuthorized"] for row in finite))
        self.assertFalse(result["subsurfaceGeometryAuthorized"])

    def test_non_geologic_crossings_are_ignored_without_splitting_support(self):
        record = {"crossings": [crossing(20, 1, 2),
            crossing(30, None, None, "NonGeologicSurfaceBoundary"),
            crossing(60, 2, 1)]}
        result = build_mapped_surface_support_intervals(record, 80, morphology())
        self.assertEqual(1, result["ignoredNonTransitionCrossingCount"])
        self.assertEqual([20.0, 60.0], [result["intervals"][1]["startStationM"],
                                        result["intervals"][1]["endStationM"]])

    def test_discontinuous_chain_fails_closed(self):
        record = {"crossings": [crossing(20, 1, 2), crossing(40, 1, 2)]}
        with self.assertRaises(ValueError):
            build_mapped_surface_support_intervals(record, 100, morphology())

    def test_unknown_unit_bad_station_and_bad_pair_fail_closed(self):
        cases = [
            ({"crossings": [crossing(20, 1, 3)]}, 100),
            ({"crossings": [crossing(100, 1, 2)]}, 100),
            ({"crossings": [{"stationM": 20,
                              "sideClassificationStatus": "MappedUnitTransition",
                              "unitPair": [{"sourcePolygonFeatureId": 1}]}]}, 100),
            ({"crossings": []}, 100),
        ]
        for record, length in cases:
            with self.subTest(record=record), self.assertRaises(ValueError):
                build_mapped_surface_support_intervals(record, length, morphology())

    def test_duplicate_morphology_identity_and_bad_route_fail_closed(self):
        duplicate = morphology()
        duplicate["units"][1]["sourcePolygonFeatureId"] = 1
        for data, length in ((duplicate, 100), (morphology(), 0)):
            with self.subTest(length=length), self.assertRaises(ValueError):
                build_mapped_surface_support_intervals(
                    {"crossings": [crossing(20, 1, 2)]}, length, data)


if __name__ == "__main__":
    unittest.main()
