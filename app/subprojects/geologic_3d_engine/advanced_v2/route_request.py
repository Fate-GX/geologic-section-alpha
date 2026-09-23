"""Nationwide request contract isolated from the basic-version GUI/schema."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math

EARTH_RADIUS_M = 6378137.0  # identical to the basic route stationing contract
JAPAN_BOUNDS = (122.0, 20.0, 154.0, 46.0)
MIN_SECTION_LENGTH_M = 10.0
# Conservative operational ceiling: the maintained terrain/DWG fixtures are
# 500 m sections. This is not a guarantee of evidence availability at every site.
MAX_SECTION_LENGTH_M = 500.0
SECTION_LENGTH_LABEL = f"{MIN_SECTION_LENGTH_M:g} m～{MAX_SECTION_LENGTH_M:g} m"
SECTION_LENGTH_TOLERANCE_M = 1e-6  # floating-point round-trip at either limit only


def validate_endpoint(point):
    west, south, east, north = JAPAN_BOUNDS
    if not isinstance(point, (tuple, list)) or len(point) != 2:
        raise ValueError("始点A・終点Bの経度と緯度を指定してください")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point):
        raise ValueError("二点の座標は有限の数値で指定してください")
    if not west <= point[0] <= east or not south <= point[1] <= north:
        raise ValueError("二点は日本の対応範囲内で指定してください")


def checked_section_length(length):
    for limit in (MIN_SECTION_LENGTH_M, MAX_SECTION_LENGTH_M):
        if math.isclose(length, limit, rel_tol=0, abs_tol=SECTION_LENGTH_TOLERANCE_M):
            return limit
    if not MIN_SECTION_LENGTH_M <= length <= MAX_SECTION_LENGTH_M:
        raise ValueError(f"始点A・終点Bは{SECTION_LENGTH_LABEL}離して指定してください")
    return length


def endpoint_geometry(start, end):
    """Same spherical stationing convention as existing routes; not survey accuracy."""
    for point in (start, end):validate_endpoint(point)
    lon1, lat1, lon2, lat2 = map(math.radians, (*start, *end))
    dl = lon2 - lon1
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dl/2)**2
    length = checked_section_length(2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h))))
    bearing = math.degrees(math.atan2(math.sin(dl)*math.cos(lat2),
        math.cos(lat1)*math.sin(lat2)-math.sin(lat1)*math.cos(lat2)*math.cos(dl))) % 360
    center = destination(*start, bearing, length/2)
    return center, length, bearing


def destination(longitude, latitude, bearing_degrees, distance_m):
    lon1, lat1 = math.radians(longitude), math.radians(latitude)
    bearing = math.radians(bearing_degrees)
    angular = distance_m / EARTH_RADIUS_M
    lat2 = math.asin(math.sin(lat1) * math.cos(angular) +
                     math.cos(lat1) * math.sin(angular) * math.cos(bearing))
    lon2 = lon1 + math.atan2(math.sin(bearing) * math.sin(angular) * math.cos(lat1),
                             math.cos(angular) - math.sin(lat1) * math.sin(lat2))
    return [math.degrees(lon2), math.degrees(lat2)]


@dataclass(frozen=True)
class AdvancedJapanSectionRequest:
    center_longitude: float
    center_latitude: float
    length_m: float = 500.0
    azimuth_degrees: float = 90.0
    sample_spacing_m: float = 10.0
    seed: int = 1
    contact_lines: str = "Show"
    png_preview: bool = True
    drafting_density: str = "Standard"
    route_endpoints: tuple | None = None

    @classmethod
    def from_endpoints(cls, start, end, **options):
        center, length, bearing = endpoint_geometry(start, end)
        return cls(*center, length_m=length, azimuth_degrees=bearing,
                   route_endpoints=(tuple(start), tuple(end)), **options).validate()

    def validate(self):
        numeric = (self.center_longitude, self.center_latitude, self.length_m,
                   self.azimuth_degrees, self.sample_spacing_m)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in numeric):
            raise ValueError("route request values must be finite numbers")
        west, south, east, north = JAPAN_BOUNDS
        if not west <= self.center_longitude <= east or not south <= self.center_latitude <= north:
            raise ValueError("centre coordinate is outside the Japan extension boundary")
        checked_section_length(self.length_m)
        if not 0 <= self.azimuth_degrees < 360:
            raise ValueError("azimuth must be in [0,360) degrees clockwise from north")
        if not 1 <= self.sample_spacing_m <= min(1000, self.length_m):
            raise ValueError("sample spacing is outside the supported range")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("seed must be a uint32")
        if self.contact_lines not in {"Show", "Hide"}:
            raise ValueError("contact_lines must be Show or Hide")
        if self.drafting_density not in {"Compact", "Standard", "Detailed"}:
            raise ValueError("drafting_density must be Compact, Standard or Detailed")
        if self.route_endpoints is not None:
            if not isinstance(self.route_endpoints, tuple) or len(self.route_endpoints) != 2:
                raise ValueError("two ordered endpoints are required")
            center, length, bearing = endpoint_geometry(*self.route_endpoints)
            if (not math.isclose(length, self.length_m, rel_tol=0, abs_tol=1e-6)
                    or abs(bearing-self.azimuth_degrees) > 1e-9
                    or abs(center[0]-self.center_longitude) > 1e-9
                    or abs(center[1]-self.center_latitude) > 1e-9):
                raise ValueError("endpoint geometry conflicts with route metadata")
        return self

    def route(self):
        self.validate()
        if self.route_endpoints is not None:
            return [list(point) for point in self.route_endpoints]
        half = self.length_m / 2.0
        return [destination(self.center_longitude, self.center_latitude,
                            (self.azimuth_degrees + 180.0) % 360.0, half),
                destination(self.center_longitude, self.center_latitude,
                            self.azimuth_degrees, half)]

    def to_dict(self):
        values = asdict(self); values.pop("route_endpoints")
        result = {**values, "routeLonLat": self.route(),
                  "schemaVersion": "AdvancedJapanSectionRequest-2.0"}
        if self.route_endpoints is not None:
            result.update(schemaVersion="AdvancedJapanSectionRequest-2.1", routeDefinition="OrderedEndpointsAB")
        return result
