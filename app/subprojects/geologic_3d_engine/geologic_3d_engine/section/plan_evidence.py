"""Source-aware XYZ plan evidence and arbitrary-route terrain profiles.

Raster appearance is evidence about the visible surface only.  In particular,
an orthophoto is never promoted to a subsurface lithology observation here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Callable, Mapping, Sequence

import numpy as np


TILE_SIZE = 256
MAX_MERCATOR_LATITUDE = 85.0511287798066


def _point_in_ring(longitude, latitude, ring):
    """Return True for points inside or on a GeoJSON linear ring."""
    inside = False
    for first, second in zip(ring, ring[1:]):
        x1, y1 = map(float, first[:2])
        x2, y2 = map(float, second[:2])
        cross = (longitude-x1)*(y2-y1) - (latitude-y1)*(x2-x1)
        if abs(cross) <= 1e-12 and min(x1, x2)-1e-12 <= longitude <= max(x1, x2)+1e-12 \
                and min(y1, y2)-1e-12 <= latitude <= max(y1, y2)+1e-12:
            return True
        if ((y1 > latitude) != (y2 > latitude)):
            crossing_x = x1 + (latitude-y1)*(x2-x1)/(y2-y1)
            if longitude < crossing_x:
                inside = not inside
    return inside


def classify_orthophoto_metadata_point(feature_collection, longitude, latitude):
    """Classify one location using GSI seamlessphoto_spec GeoJSON.

    The result records acquisition/source metadata only.  It never upgrades an
    orthophoto from visible-surface context to subsurface evidence.
    """
    if not isinstance(feature_collection, Mapping) or feature_collection.get("type") != "FeatureCollection":
        raise ValueError("orthophoto metadata must be a GeoJSON FeatureCollection")
    matches = []
    for feature in feature_collection.get("features", []):
        geometry = feature.get("geometry", {})
        polygons = ([geometry.get("coordinates", [])] if geometry.get("type") == "Polygon"
                    else geometry.get("coordinates", []) if geometry.get("type") == "MultiPolygon"
                    else [])
        for polygon in polygons:
            if polygon and _point_in_ring(longitude, latitude, polygon[0]) and not any(
                    _point_in_ring(longitude, latitude, hole) for hole in polygon[1:]):
                properties = feature.get("properties", {})
                matches.append({"dataSource": properties.get("データソース"),
                                "acquisitionDateOrRange": properties.get("撮影年月")})
                break
    unique = [dict(items) for items in {tuple(sorted(item.items())) for item in matches}]
    if len(unique) > 1:
        return {"status": "AmbiguousOverlappingMetadata", "matches": unique,
                "interpretationRole": "VisibleSurfaceContext"}
    if not unique or not all(isinstance(v, str) and v.strip() for v in unique[0].values()):
        return {"status": "UnresolvedMetadata", "matches": unique,
                "interpretationRole": "VisibleSurfaceContext"}
    return {"status": "ExactPolygonMatch", **unique[0],
            "interpretationRole": "VisibleSurfaceContext"}


def lonlat_to_global_pixel(longitude, latitude, zoom):
    """Convert JGD2011/WGS84-compatible longitude/latitude to XYZ pixels."""
    values = (longitude, latitude, zoom)
    if any(isinstance(v, bool) for v in values):
        raise ValueError("longitude, latitude and zoom must be numeric")
    if not all(isinstance(v, (int, float)) and math.isfinite(v)
               for v in (longitude, latitude)):
        raise ValueError("longitude and latitude must be finite")
    if not isinstance(zoom, int) or zoom < 0:
        raise ValueError("zoom must be a non-negative integer")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("longitude must lie in [-180, 180]")
    if not -MAX_MERCATOR_LATITUDE <= latitude <= MAX_MERCATOR_LATITUDE:
        raise ValueError("latitude is outside the XYZ Mercator domain")
    scale = TILE_SIZE * (2 ** zoom)
    x = (longitude + 180.0) / 360.0 * scale
    sin_latitude = math.sin(math.radians(latitude))
    y = (0.5 - math.log((1.0 + sin_latitude) /
                        (1.0 - sin_latitude)) / (4.0 * math.pi)) * scale
    # Longitude 180 and the southern Mercator limit lie on the open outer edge.
    upper = math.nextafter(float(scale), 0.0)
    return min(max(x, 0.0), upper), min(max(y, 0.0), upper)


def global_pixel_to_lonlat(x, y, zoom):
    if not isinstance(zoom, int) or zoom < 0:
        raise ValueError("zoom must be a non-negative integer")
    scale = TILE_SIZE * (2 ** zoom)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v < scale
               for v in (x, y)):
        raise ValueError("global pixel must lie inside the tile matrix")
    longitude = x / scale * 360.0 - 180.0
    latitude = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0*y/scale))))
    return longitude, latitude


def _validate_tile(array, kind):
    tile = np.asarray(array)
    expected = (TILE_SIZE, TILE_SIZE, 3) if kind == "RGB" else (TILE_SIZE, TILE_SIZE)
    if tile.shape != expected:
        raise ValueError(f"{kind} tile must have shape {expected}")
    if kind == "RGB" and tile.dtype != np.uint8:
        raise ValueError("RGB tile must use uint8 samples")
    if kind == "Elevation" and not np.issubdtype(tile.dtype, np.floating):
        raise ValueError("elevation tile must use floating samples")
    return tile


class XyzRasterSampler:
    """Sample immutable XYZ tiles supplied by a cache, file reader, or client."""

    def __init__(self, zoom: int, kind: str,
                 fetch_tile: Callable[[int, int, int], np.ndarray | None]):
        if not isinstance(zoom, int) or zoom < 0 or kind not in {"RGB", "Elevation"}:
            raise ValueError("invalid XYZ raster declaration")
        if not callable(fetch_tile):
            raise ValueError("fetch_tile must be callable")
        self.zoom, self.kind, self.fetch_tile = zoom, kind, fetch_tile

    def sample_nearest(self, longitude, latitude):
        gx, gy = lonlat_to_global_pixel(longitude, latitude, self.zoom)
        px, py = int(math.floor(gx)), int(math.floor(gy))
        tx, ty = px // TILE_SIZE, py // TILE_SIZE
        tile = self.fetch_tile(self.zoom, tx, ty)
        if tile is None:
            return None
        tile = _validate_tile(tile, self.kind)
        value = tile[py % TILE_SIZE, px % TILE_SIZE]
        if self.kind == "Elevation" and not math.isfinite(float(value)):
            return None
        return value.copy() if self.kind == "RGB" else float(value)

    def sample_bilinear_elevation(self, longitude, latitude):
        """Bilinearly resample four elevation pixel centres, including tile edges."""
        if self.kind != "Elevation":
            raise ValueError("bilinear sampling is available only for elevation")
        gx, gy = lonlat_to_global_pixel(longitude, latitude, self.zoom)
        # XYZ pixels cover cells [i,i+1); their representative samples are at
        # i+0.5, hence interpolation coordinates are shifted by half a pixel.
        ux, uy = gx - 0.5, gy - 0.5
        x0, y0 = math.floor(ux), math.floor(uy)
        fx, fy = ux - x0, uy - y0
        scale = TILE_SIZE * (2 ** self.zoom)
        if x0 < 0 or y0 < 0 or x0 + 1 >= scale or y0 + 1 >= scale:
            return None
        values = []
        for py in (y0, y0 + 1):
            row = []
            for px in (x0, x0 + 1):
                tile = self.fetch_tile(self.zoom, px // TILE_SIZE, py // TILE_SIZE)
                if tile is None:
                    return None
                tile = _validate_tile(tile, "Elevation")
                value = float(tile[py % TILE_SIZE, px % TILE_SIZE])
                if not math.isfinite(value):
                    return None
                row.append(value)
            values.append(row)
        return float((1-fx)*(1-fy)*values[0][0] + fx*(1-fy)*values[0][1]
                     + (1-fx)*fy*values[1][0] + fx*fy*values[1][1])


class PriorityXyzElevationSampler:
    """Choose the first complete DEM source; never blend sources in one sample."""
    kind = "Elevation"

    def __init__(self, sources):
        if (not isinstance(sources, Sequence) or isinstance(sources, (str, bytes))
                or not sources):
            raise ValueError("one or more priority DEM sources are required")
        checked = []
        for item in sources:
            if (not isinstance(item, Sequence) or len(item) != 2
                    or not isinstance(item[0], str) or not item[0].strip()
                    or not isinstance(item[1], XyzRasterSampler)
                    or item[1].kind != "Elevation"):
                raise ValueError("each source must pair an ID and elevation sampler")
            checked.append((item[0], item[1]))
        if len({item[0] for item in checked}) != len(checked):
            raise ValueError("priority DEM source IDs must be unique")
        self.sources = tuple(checked)

    def sample_with_source(self, longitude, latitude, sampling_method):
        if sampling_method not in {"NearestPixel", "BilinearPixelCentres"}:
            raise ValueError("unsupported elevation sampling method")
        for source_id, sampler in self.sources:
            value = (sampler.sample_nearest(longitude, latitude)
                     if sampling_method == "NearestPixel" else
                     sampler.sample_bilinear_elevation(longitude, latitude))
            if value is not None:
                return value, source_id
        return None, None


def _haversine_m(a, b):
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon, dlat = lon2-lon1, lat2-lat1
    value = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6378137.0 * 2.0 * math.asin(min(1.0, math.sqrt(value)))


def sample_geographic_route(vertices_lonlat, spacing_m, elevation_sampler, *,
                            sampling_method="NearestPixel"):
    """Sample a multi-segment route by cumulative great-circle chord distance."""
    vertices = np.asarray(vertices_lonlat, dtype=float)
    if (vertices.ndim != 2 or vertices.shape[1] != 2 or len(vertices) < 2 or
            not np.isfinite(vertices).all() or not isinstance(
                elevation_sampler, (XyzRasterSampler, PriorityXyzElevationSampler))
            or elevation_sampler.kind != "Elevation"):
        raise ValueError("finite route and an elevation sampler are required")
    if isinstance(spacing_m, bool) or not isinstance(spacing_m, (int, float)) or spacing_m <= 0:
        raise ValueError("spacing_m must be positive")
    lengths = np.array([_haversine_m(a, b) for a, b in zip(vertices[:-1], vertices[1:])])
    if np.any(lengths == 0):
        raise ValueError("route contains a zero-length segment")
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    stations = np.linspace(0.0, cumulative[-1], int(math.ceil(cumulative[-1]/spacing_m))+1)
    return sample_geographic_route_at_stations(
        vertices_lonlat, stations.tolist(), elevation_sampler,
        sampling_method=sampling_method)


def sample_geographic_route_at_stations(vertices_lonlat, stations_m, elevation_sampler,
                                        *, sampling_method="NearestPixel"):
    """Directly sample a geographic route at caller-declared cumulative stations."""
    vertices = np.asarray(vertices_lonlat, dtype=float)
    if (vertices.ndim != 2 or vertices.shape[1] != 2 or len(vertices) < 2 or
            not np.isfinite(vertices).all() or not isinstance(
                elevation_sampler, (XyzRasterSampler, PriorityXyzElevationSampler))
            or elevation_sampler.kind != "Elevation"):
        raise ValueError("finite route and an elevation sampler are required")
    lengths = np.array([_haversine_m(a, b) for a, b in zip(vertices[:-1], vertices[1:])])
    if np.any(lengths == 0):
        raise ValueError("route contains a zero-length segment")
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    if (not isinstance(stations_m, Sequence) or isinstance(stations_m, (str, bytes))
            or not stations_m):
        raise ValueError("one or more target stations are required")
    stations = []
    for value in stations_m:
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)):
            raise ValueError("target stations must be finite numbers")
        stations.append(float(value))
    station_tolerance = math.ulp(max(float(cumulative[-1]), 1.0)) * 8
    if (any(value < -station_tolerance or value > cumulative[-1] + station_tolerance
            for value in stations)
            or any(right <= left for left, right in zip(stations, stations[1:]))):
        raise ValueError("target stations must strictly increase within the route")
    result = []
    if sampling_method not in {"NearestPixel", "BilinearPixelCentres"}:
        raise ValueError("unsupported elevation sampling method")
    for station in stations:
        station = min(max(station, 0.0), float(cumulative[-1]))
        index = min(np.searchsorted(cumulative, station, side="right")-1, len(lengths)-1)
        fraction = (station-cumulative[index])/lengths[index]
        point = vertices[index] + fraction*(vertices[index+1]-vertices[index])
        if isinstance(elevation_sampler, PriorityXyzElevationSampler):
            elevation, elevation_source = elevation_sampler.sample_with_source(
                point[0], point[1], sampling_method)
        else:
            elevation = (elevation_sampler.sample_nearest(point[0], point[1])
                         if sampling_method == "NearestPixel" else
                         elevation_sampler.sample_bilinear_elevation(point[0], point[1]))
            elevation_source = None
        result.append({"stationM": float(station), "longitude": float(point[0]),
                       "latitude": float(point[1]), "elevationM": elevation,
                       "routeSegmentIndex": int(index),
                       "elevationSamplingMethod": sampling_method,
                       "elevationSourceId": elevation_source})
    return result


@dataclass(frozen=True)
class PlanEvidenceLayer:
    layer_id: str
    evidence_kind: str
    source_id: str
    canonical_url: str
    crs: str
    acquisition_date_or_range: str
    content_sha256: str
    interpretation_role: str

    def validate(self):
        allowed = {
            "Orthophoto": {"VisibleSurfaceContext"},
            "DEM": {"TerrainElevation"},
            "SurfaceGeology": {"MappedSurfaceUnit"},
            "Borehole": {"SubsurfaceObservation"},
            "StructureObservation": {"OrientationConstraint"},
        }
        if self.evidence_kind not in allowed or self.interpretation_role not in allowed[self.evidence_kind]:
            raise ValueError("evidence kind cannot authorize the declared role")
        required = (self.layer_id, self.source_id, self.canonical_url, self.crs,
                    self.acquisition_date_or_range)
        if not all(isinstance(value, str) and value.strip() for value in required):
            raise ValueError("layer identity, source, URL, CRS and date are required")
        digest = self.content_sha256
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("content_sha256 must be lowercase SHA-256")
        return self


def build_plan_evidence(layers: Sequence[PlanEvidenceLayer], route_lonlat,
                        terrain_profile: Sequence[Mapping]):
    if not layers:
        raise ValueError("at least one evidence layer is required")
    checked = [layer.validate() for layer in layers]
    ids = [layer.layer_id for layer in checked]
    if len(ids) != len(set(ids)):
        raise ValueError("layer IDs must be unique")
    crs_values = {layer.crs for layer in checked}
    if len(crs_values) != 1:
        raise ValueError("all plan layers must be explicitly transformed to one CRS")
    if not any(layer.evidence_kind == "DEM" for layer in checked):
        raise ValueError("a DEM layer is required for a terrain section")
    if not terrain_profile or any("elevationM" not in row for row in terrain_profile):
        raise ValueError("a sampled terrain profile is required")
    subsurface = any(layer.evidence_kind in {"Borehole", "StructureObservation"}
                     for layer in checked)
    mapped_geology = any(layer.evidence_kind == "SurfaceGeology" for layer in checked)
    state = ("SubsurfaceInterpretationInputsPresent" if subsurface and mapped_geology else
             "TerrainPlanOnly_NoSubsurfaceLithologyAuthorization")
    payload = {
        "schemaVersion": "PlanEvidenceBundle-1.0",
        "layers": [layer.__dict__ for layer in checked],
        "routeLonLat": np.asarray(route_lonlat, dtype=float).tolist(),
        "terrainProfile": [dict(row) for row in terrain_profile],
        "authorizationState": state,
        "orthophotoInferenceBoundary": "VisibleSurfaceCandidatesOnly",
    }
    canonical = __import__("json").dumps(payload, sort_keys=True, separators=(",", ":"),
                                          ensure_ascii=False).encode("utf-8")
    payload["bundleSha256"] = hashlib.sha256(canonical).hexdigest()
    return payload
