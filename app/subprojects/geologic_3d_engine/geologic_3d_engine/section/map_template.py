"""Evidence-preserving map-to-section template primitives.

The module projects observed map features to a measured route.  It does not
infer unobserved subsurface contacts and does not authorize regional geology.
"""
from __future__ import annotations

import math
import numpy as np


def _finite_xy(value, name):
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or array.shape[1] != 2 or len(array) < 2 or not np.isfinite(array).all():
        raise ValueError(f"{name} must be a finite N x 2 array with N >= 2")
    if np.any(np.linalg.norm(np.diff(array, axis=0), axis=1) == 0):
        raise ValueError(f"{name} contains a zero-length segment")
    return array


class MeasuredRoute2D:
    def __init__(self, vertices_xy):
        self.vertices = _finite_xy(vertices_xy, "route")
        self.segment_vectors = np.diff(self.vertices, axis=0)
        self.segment_lengths = np.linalg.norm(self.segment_vectors, axis=1)
        self.stations = np.concatenate(([0.0], np.cumsum(self.segment_lengths)))

    @property
    def length(self):
        return float(self.stations[-1])

    def project(self, points_xy):
        points = np.asarray(points_xy, dtype=float)
        if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
            raise ValueError("points must be a finite N x 2 array")
        best = np.full(len(points), np.inf)
        station = np.zeros(len(points))
        signed_offset = np.zeros(len(points))
        projected = np.zeros_like(points)
        segment_index = np.zeros(len(points), dtype=int)
        for index, (start, vector, length) in enumerate(zip(
                self.vertices[:-1], self.segment_vectors, self.segment_lengths)):
            delta = points - start
            t = np.clip(np.sum(delta * vector, axis=1) / (length * length), 0.0, 1.0)
            candidate = start + t[:, None] * vector
            residual = points - candidate
            distance2 = np.sum(residual * residual, axis=1)
            choose = distance2 < best
            cross = vector[0] * residual[:, 1] - vector[1] * residual[:, 0]
            best[choose] = distance2[choose]
            station[choose] = self.stations[index] + t[choose] * length
            signed_offset[choose] = np.sign(cross[choose]) * np.sqrt(distance2[choose])
            projected[choose] = candidate[choose]
            segment_index[choose] = index
        return {"station": station, "signedOffset": signed_offset,
                "projectionDistance": np.sqrt(best), "projectedXY": projected,
                "routeSegmentIndex": segment_index}

    def point_at(self, stations):
        values = np.asarray(stations, dtype=float)
        if not np.isfinite(values).all() or np.any(values < 0) or np.any(values > self.length):
            raise ValueError("stations must lie within the route")
        indices = np.searchsorted(self.stations, values, side="right") - 1
        indices = np.clip(indices, 0, len(self.segment_lengths) - 1)
        t = (values - self.stations[indices]) / self.segment_lengths[indices]
        return self.vertices[indices] + t[..., None] * self.segment_vectors[indices]


class RegularDem2D:
    def __init__(self, origin_xy, spacing_xy, elevations_yx, crs, vertical_datum):
        self.origin = np.asarray(origin_xy, dtype=float)
        self.spacing = np.asarray(spacing_xy, dtype=float)
        self.values = np.asarray(elevations_yx, dtype=float)
        if (self.origin.shape != (2,) or self.spacing.shape != (2,) or
                not np.isfinite(self.origin).all() or not np.isfinite(self.spacing).all() or
                np.any(self.spacing <= 0) or self.values.ndim != 2 or
                min(self.values.shape) < 2 or not np.isfinite(self.values).all()):
            raise ValueError("invalid regular DEM")
        if not crs or not vertical_datum:
            raise ValueError("CRS and vertical datum are required")
        self.crs, self.vertical_datum = str(crs), str(vertical_datum)

    def sample(self, points_xy):
        points = np.asarray(points_xy, dtype=float)
        fractional = (points - self.origin) / self.spacing
        x, y = fractional[:, 0], fractional[:, 1]
        if (np.any(x < 0) or np.any(y < 0) or np.any(x > self.values.shape[1] - 1)
                or np.any(y > self.values.shape[0] - 1)):
            raise ValueError("DEM query outside extent")
        ix = np.minimum(np.floor(x).astype(int), self.values.shape[1] - 2)
        iy = np.minimum(np.floor(y).astype(int), self.values.shape[0] - 2)
        tx, ty = x - ix, y - iy
        return ((1-tx)*(1-ty)*self.values[iy, ix] + tx*(1-ty)*self.values[iy, ix+1]
                + (1-tx)*ty*self.values[iy+1, ix] + tx*ty*self.values[iy+1, ix+1])


def apparent_dip_degrees(true_dip_degrees, dip_direction_degrees, section_azimuth_degrees):
    values = (true_dip_degrees, dip_direction_degrees, section_azimuth_degrees)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError("orientation values must be finite numbers")
    if not 0 <= true_dip_degrees <= 90:
        raise ValueError("true dip must be in [0,90] degrees")
    difference = math.radians((dip_direction_degrees - section_azimuth_degrees + 180) % 360 - 180)
    if true_dip_degrees == 90:
        if abs(math.cos(difference)) < 1e-15:
            return 0.0
        return math.copysign(90.0, math.cos(difference))
    return math.degrees(math.atan(math.tan(math.radians(true_dip_degrees)) * math.cos(difference)))


def build_section_template(route, dem, spacing, observations=(), maximum_projection_distance=0.0):
    if not isinstance(route, MeasuredRoute2D) or not isinstance(dem, RegularDem2D):
        raise ValueError("typed route and DEM are required")
    if isinstance(spacing, bool) or not isinstance(spacing, (int, float)) or spacing <= 0:
        raise ValueError("spacing must be positive")
    if maximum_projection_distance < 0:
        raise ValueError("maximum projection distance must be non-negative")
    stations = np.linspace(0.0, route.length, int(math.ceil(route.length / spacing)) + 1)
    xy = route.point_at(stations)
    z = dem.sample(xy)
    projected = []
    for observation in observations:
        required = {"observationId", "xy", "kind", "sourceId"}
        if not isinstance(observation, dict) or not required.issubset(observation):
            raise ValueError("observation identity, XY, kind and source are required")
        result = route.project([observation["xy"]])
        distance = float(result["projectionDistance"][0])
        projected.append({"observationId": observation["observationId"],
            "kind": observation["kind"], "sourceId": observation["sourceId"],
            "sourceXY": list(map(float, observation["xy"])),
            "projectedXY": result["projectedXY"][0].tolist(),
            "station": float(result["station"][0]),
            "signedOffset": float(result["signedOffset"][0]),
            "projectionDistance": distance,
            "projectionState": "OnSection" if distance == 0 else
                ("Projected" if distance <= maximum_projection_distance else "Rejected")})
    return {"routeLength": route.length, "stations": stations.tolist(),
            "terrainXY": xy.tolist(), "terrainElevation": z.tolist(),
            "crs": dem.crs, "verticalDatum": dem.vertical_datum,
            "projectionBuffer": float(maximum_projection_distance),
            "observations": projected,
            "interpretationState": "EvidenceTemplate_NoSubsurfaceInference"}


def intersect_route_with_contacts(route, contacts, tolerance=1e-9):
    """Return exact 2D route/contact crossings with both source identities."""
    if not isinstance(route, MeasuredRoute2D) or tolerance <= 0:
        raise ValueError("typed route and positive tolerance are required")
    events = []
    for contact in contacts:
        if not isinstance(contact, dict) or set(contact) != {"contactId", "unitPair", "verticesXY", "sourceId"}:
            raise ValueError("invalid contact record")
        vertices = _finite_xy(contact["verticesXY"], "contact")
        for route_index, (a, rv, route_length) in enumerate(zip(
                route.vertices[:-1], route.segment_vectors, route.segment_lengths)):
            for contact_index, (c, dv) in enumerate(zip(vertices[:-1], np.diff(vertices, axis=0))):
                denominator = rv[0] * dv[1] - rv[1] * dv[0]
                delta = c - a
                if abs(denominator) <= tolerance:
                    continue
                route_t = (delta[0] * dv[1] - delta[1] * dv[0]) / denominator
                contact_t = (delta[0] * rv[1] - delta[1] * rv[0]) / denominator
                if -tolerance <= route_t <= 1+tolerance and -tolerance <= contact_t <= 1+tolerance:
                    point = a + np.clip(route_t, 0, 1) * rv
                    station = route.stations[route_index] + np.clip(route_t, 0, 1) * route_length
                    if not any(abs(event["station"] - station) <= tolerance and
                               event["contactId"] == contact["contactId"] for event in events):
                        events.append({"contactId": contact["contactId"],
                            "unitPair": list(contact["unitPair"]), "sourceId": contact["sourceId"],
                            "routeSegmentIndex": route_index, "contactSegmentIndex": contact_index,
                            "station": float(station), "intersectionXY": point.tolist()})
    return sorted(events, key=lambda item: (item["station"], item["contactId"]))
