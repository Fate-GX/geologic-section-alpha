import unittest
import numpy as np

from geologic_3d_engine.section.plan_evidence import (
    PlanEvidenceLayer, PriorityXyzElevationSampler, XyzRasterSampler, build_plan_evidence,
    classify_orthophoto_metadata_point, global_pixel_to_lonlat,
    lonlat_to_global_pixel, sample_geographic_route,
    sample_geographic_route_at_stations)


DIGEST = "1" * 64


class PlanEvidenceTests(unittest.TestCase):
    def test_xyz_round_trip_and_tile_edge(self):
        for lon, lat, zoom in [(131.04, 32.88, 15), (-73.5, 40.7, 9), (0, 0, 0)]:
            x, y = lonlat_to_global_pixel(lon, lat, zoom)
            actual = global_pixel_to_lonlat(x, y, zoom)
            self.assertAlmostEqual(actual[0], lon, places=11)
            self.assertAlmostEqual(actual[1], lat, places=11)
        x, _ = lonlat_to_global_pixel(180, 0, 2)
        self.assertLess(x, 256 * 4)

    def test_arbitrary_bent_route_and_nodata(self):
        tile = np.full((256, 256), 123.5, dtype=float)
        sampler = XyzRasterSampler(10, "Elevation", lambda z, x, y: tile)
        result = sample_geographic_route([[131.0, 32.8], [131.001, 32.8],
                                          [131.001, 32.801]], 25, sampler)
        self.assertGreater(len(result), 7)
        self.assertEqual({row["routeSegmentIndex"] for row in result}, {0, 1})
        self.assertTrue(all(row["elevationM"] == 123.5 for row in result))
        missing = XyzRasterSampler(10, "Elevation", lambda z, x, y: None)
        self.assertTrue(all(row["elevationM"] is None for row in
                            sample_geographic_route([[131,32.8],[131.001,32.8]], 50, missing)))

    def test_direct_exact_station_sampling_uses_same_route_metric(self):
        tile = np.full((256, 256), 77.25, dtype=float)
        sampler = XyzRasterSampler(12, "Elevation", lambda z, x, y: tile)
        route = [[131.0, 32.8], [131.001, 32.8], [131.001, 32.801]]
        regular = sample_geographic_route(route, 40, sampler)
        targets = [regular[0]["stationM"], regular[2]["stationM"],
                   regular[-1]["stationM"]]
        direct = sample_geographic_route_at_stations(route, targets, sampler)
        self.assertEqual([row["stationM"] for row in direct], targets)
        self.assertEqual([row["routeSegmentIndex"] for row in direct],
                         [regular[0]["routeSegmentIndex"],
                          regular[2]["routeSegmentIndex"],
                          regular[-1]["routeSegmentIndex"]])
        self.assertTrue(all(row["elevationM"] == 77.25 for row in direct))
        with self.assertRaises(ValueError):
            sample_geographic_route_at_stations(route, [0, 0], sampler)
        with self.assertRaises(ValueError):
            sample_geographic_route_at_stations(route, [0, 1e9], sampler)

    def test_bilinear_elevation_uses_pixel_centres_and_crosses_tile_edge(self):
        zoom = 1
        def tile(_z, tx, ty):
            yy, xx = np.mgrid[0:256, 0:256]
            return ((tx * 256 + xx) + 2 * (ty * 256 + yy)).astype(float)
        sampler = XyzRasterSampler(zoom, "Elevation", tile)
        # Convert a global position straddling x tile 0/1 and away from Y edges.
        lon, lat = global_pixel_to_lonlat(255.75, 100.25, zoom)
        # Centre-shifted coordinates are (255.25,99.75); the global linear
        # field therefore evaluates exactly to x + 2*y.
        self.assertAlmostEqual(sampler.sample_bilinear_elevation(lon, lat),
                               255.25 + 2 * 99.75, places=10)
        bad = XyzRasterSampler(zoom, "Elevation", lambda z, x, y: None)
        self.assertIsNone(bad.sample_bilinear_elevation(lon, lat))
        rgb = XyzRasterSampler(zoom, "RGB", lambda z, x, y:
                               np.zeros((256, 256, 3), dtype=np.uint8))
        with self.assertRaises(ValueError):
            rgb.sample_bilinear_elevation(lon, lat)

    def test_priority_sampler_never_blends_incomplete_dem_sources(self):
        zoom = 2
        lon, lat = global_pixel_to_lonlat(300.2, 300.2, zoom)
        incomplete = XyzRasterSampler(
            zoom, "Elevation", lambda z, x, y:
            np.full((256, 256), np.nan) if (x, y) == (1, 1)
            else np.full((256, 256), 10.0))
        complete = XyzRasterSampler(
            zoom, "Elevation", lambda z, x, y: np.full((256, 256), 20.0))
        priority = PriorityXyzElevationSampler(
            [("HIGH-RES", incomplete), ("FALLBACK", complete)])
        value, source = priority.sample_with_source(
            lon, lat, "BilinearPixelCentres")
        self.assertEqual(value, 20.0)
        self.assertEqual(source, "FALLBACK")
        route = sample_geographic_route_at_stations(
            [[lon, lat], [lon + .001, lat]], [0, 10], priority,
            sampling_method="BilinearPixelCentres")
        self.assertTrue(all(row["elevationSourceId"] == "FALLBACK" for row in route))

    def layer(self, kind, role, name=None, crs="JGD2011/WebMercator"):
        return PlanEvidenceLayer(name or kind, kind, "OFFICIAL-"+kind,
            "https://example.invalid/official", crs, "2026-01-01", DIGEST, role)

    def test_orthophoto_and_dem_do_not_authorize_lithology(self):
        layers = [self.layer("Orthophoto", "VisibleSurfaceContext"),
                  self.layer("DEM", "TerrainElevation")]
        result = build_plan_evidence(layers, [[131,32],[131.1,32]],
                                     [{"stationM":0,"elevationM":100}])
        self.assertEqual(result["authorizationState"],
                         "TerrainPlanOnly_NoSubsurfaceLithologyAuthorization")

    def test_geology_plus_subsurface_observation_unlocks_inputs_only(self):
        layers = [self.layer("DEM", "TerrainElevation"),
                  self.layer("SurfaceGeology", "MappedSurfaceUnit"),
                  self.layer("Borehole", "SubsurfaceObservation")]
        result = build_plan_evidence(layers, [[0,0],[1,0]],
                                     [{"stationM":0,"elevationM":10}])
        self.assertEqual(result["authorizationState"],
                         "SubsurfaceInterpretationInputsPresent")

    def test_conflicting_crs_and_role_escalation_are_rejected(self):
        with self.assertRaises(ValueError):
            self.layer("Orthophoto", "SubsurfaceObservation").validate()
        with self.assertRaises(ValueError):
            build_plan_evidence([self.layer("DEM", "TerrainElevation"),
                self.layer("Orthophoto", "VisibleSurfaceContext", crs="EPSG:6670")],
                [[0,0],[1,0]], [{"elevationM":1}])
        with self.assertRaises(ValueError):
            self.layer("DEM", "TerrainElevation", name="bad").__class__(
                "bad", "DEM", "S", "u", "c", "d", "ABC", "TerrainElevation").validate()

    def test_orthophoto_metadata_polygon_and_hole(self):
        geojson = {"type":"FeatureCollection", "features":[{"type":"Feature",
            "properties":{"データソース":"official-photo", "撮影年月":"2024年4月"},
            "geometry":{"type":"Polygon", "coordinates":[
                [[0,0],[4,0],[4,4],[0,4],[0,0]],
                [[1,1],[2,1],[2,2],[1,2],[1,1]]]}}]}
        matched = classify_orthophoto_metadata_point(geojson, 3, 3)
        self.assertEqual(matched["status"], "ExactPolygonMatch")
        self.assertEqual(matched["interpretationRole"], "VisibleSurfaceContext")
        self.assertEqual(classify_orthophoto_metadata_point(geojson, 1.5, 1.5)["status"],
                         "UnresolvedMetadata")

    def test_orthophoto_metadata_overlap_and_missing_fields_fail_closed(self):
        feature = lambda source: {"type":"Feature", "properties":{
            "データソース":source, "撮影年月":"2020"}, "geometry":{"type":"Polygon",
            "coordinates":[[[0,0],[2,0],[2,2],[0,2],[0,0]]]}}
        overlap = {"type":"FeatureCollection", "features":[feature("A"), feature("B")]}
        self.assertEqual(classify_orthophoto_metadata_point(overlap, 1, 1)["status"],
                         "AmbiguousOverlappingMetadata")
        missing = feature(None)
        self.assertEqual(classify_orthophoto_metadata_point(
            {"type":"FeatureCollection", "features":[missing]}, 1, 1)["status"],
            "UnresolvedMetadata")


if __name__ == "__main__":
    unittest.main()
