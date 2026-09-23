import unittest
import numpy as np

from geologic_3d_engine.section.adaptive_section_station_plan import (
    attach_direct_terrain_evidence, build_adaptive_section_station_plan,
    sample_adaptive_plan_from_xyz_dem)
from geologic_3d_engine.section.plan_evidence import XyzRasterSampler


def coverage(start_station, start_x, end_station, end_x):
    return {"schemaVersion": "ExactRouteEvidenceHullIntersection-1.0",
            "supportedIntervals": [{"start": {"stationM": start_station,
                                                "xM": start_x, "yM": 0},
                                    "end": {"stationM": end_station,
                                              "xM": end_x, "yM": 0}}]}


class AdaptiveSectionStationPlanTests(unittest.TestCase):
    def setUp(self):
        self.route = [{"stationM": 0, "xM": 0, "yM": 0},
                      {"stationM": 100, "xM": 100, "yM": 0}]

    def test_exact_boundaries_are_inserted_and_z_remains_missing(self):
        result = build_adaptive_section_station_plan(
            self.route, [coverage(20, 20, 80, 80), coverage(20, 20, 60, 60)],
            merge_tolerance_m=1e-9)
        self.assertEqual([x["stationM"] for x in result["stations"]],
                         [0, 20, 60, 80, 100])
        self.assertEqual(result["insertedExactBoundaryCount"], 3)
        self.assertTrue(all(x["terrainElevationM"] is None for x in result["stations"]))
        self.assertFalse(result["terrainLinearInterpolationAuthorized"])
        self.assertEqual(len(result["stations"][1]["reasons"]), 2)

    def test_direct_dem_completion_requires_hash_and_exact_station(self):
        plan = build_adaptive_section_station_plan(
            self.route, [coverage(20, 20, 80, 80)], merge_tolerance_m=1e-9)
        observations = [{"stationM": row["stationM"], "elevationM": 100 + i,
                         "sourceId": "DEM", "sourceArtifactSha256": "a" * 64}
                        for i, row in enumerate(plan["stations"])]
        completed = attach_direct_terrain_evidence(plan, observations)
        self.assertEqual(completed["terrainCompletionStatus"],
                         "CompleteDirectDemSampling")
        bad = [dict(item) for item in observations]; bad[1]["stationM"] += .1
        with self.assertRaises(ValueError):
            attach_direct_terrain_evidence(plan, bad)

    def test_off_route_endpoint_and_bad_hash_reject(self):
        with self.assertRaises(ValueError):
            build_adaptive_section_station_plan(
                self.route, [coverage(20, 21, 80, 80)], merge_tolerance_m=1e-9)
        plan = build_adaptive_section_station_plan(
            self.route, [], merge_tolerance_m=1e-9)
        observations = [{"stationM": row["stationM"], "elevationM": 100,
                         "sourceId": "DEM", "sourceArtifactSha256": "X" * 64}
                        for row in plan["stations"]]
        with self.assertRaises(ValueError):
            attach_direct_terrain_evidence(plan, observations)

    def test_adaptive_stations_are_directly_sampled_from_xyz_dem(self):
        plan = build_adaptive_section_station_plan(
            self.route, [coverage(20, 20, 80, 80)], merge_tolerance_m=1e-9)
        sampler = XyzRasterSampler(
            10, "Elevation", lambda z, x, y: np.full((256, 256), 123.45))
        # Route station values in the plan are defined by this approximately
        # 100 m geographic segment for the test.
        from geologic_3d_engine.section.plan_evidence import _haversine_m
        geographic = [[131.0, 32.8], [131.0 + 100 /
                       (6378137 * np.cos(np.radians(32.8))) * 180 / np.pi, 32.8]]
        total = _haversine_m(geographic[0], geographic[1])
        scaled_plan = {**plan, "stations": [
            {**row, "stationM": row["stationM"] * total / 100}
            for row in plan["stations"]]}
        completed = sample_adaptive_plan_from_xyz_dem(
            scaled_plan, geographic, sampler, source_id="GSI-DEM",
            dem_artifact_sha256="a" * 64,
            sampling_method="BilinearPixelCentres")
        self.assertEqual(completed["terrainCompletionStatus"],
                         "CompleteDirectDemSampling")
        self.assertTrue(all(abs(row["terrainElevationM"] - 123.45) < 1e-12
                            for row in completed["stations"]))
        self.assertTrue(all("longitude" in row for row in completed["stations"]))
        self.assertEqual(completed["terrainSamplingMethod"], "BilinearPixelCentres")


if __name__ == "__main__":
    unittest.main()
