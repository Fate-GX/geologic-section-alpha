"""Curvature-aware synthetic channel geometry comparator.

This module is an independent project implementation. It does not claim river
process simulation or real-region validity. The v1 polyline-distance geometry
remains available as the regression baseline.
"""
import numpy as np

from .channel_geometry import ChannelGeometry


def _corner_cut(points, iterations):
    result = np.asarray(points, dtype=float)
    for _ in range(iterations):
        q = 0.75 * result[:-1] + 0.25 * result[1:]
        r = 0.25 * result[:-1] + 0.75 * result[1:]
        merged = np.empty((2 * len(result), 2), dtype=float)
        merged[0], merged[-1] = result[0], result[-1]
        merged[1:-1:2], merged[2:-1:2] = q, r
        result = merged
    return result


def _curvature_radii(points):
    radii = np.full(len(points), np.inf, dtype=float)
    for i in range(1, len(points) - 1):
        a = np.linalg.norm(points[i] - points[i - 1])
        b = np.linalg.norm(points[i + 1] - points[i])
        c = np.linalg.norm(points[i + 1] - points[i - 1])
        u = points[i] - points[i - 1]
        v = points[i + 1] - points[i - 1]
        twice_area = abs(u[0] * v[1] - u[1] * v[0])
        if twice_area > np.finfo(float).eps * max(a * b, 1.0):
            radii[i] = a * b * c / (2.0 * twice_area)
    return radii


def _segment_intersections(polyline):
    def orientation(a, b, c):
        u, v = b - a, c - a
        return u[0] * v[1] - u[1] * v[0]

    hits = []
    for i in range(len(polyline) - 1):
        a, b = polyline[i], polyline[i + 1]
        for j in range(i + 2, len(polyline) - 1):
            if i == 0 and j == len(polyline) - 2:
                continue
            c, d = polyline[j], polyline[j + 1]
            if (max(a[0], b[0]) <= min(c[0], d[0]) or max(c[0], d[0]) <= min(a[0], b[0])
                    or max(a[1], b[1]) <= min(c[1], d[1]) or max(c[1], d[1]) <= min(a[1], b[1])):
                continue
            o1, o2 = orientation(a, b, c), orientation(a, b, d)
            o3, o4 = orientation(c, d, a), orientation(c, d, b)
            if o1 * o2 < 0 and o3 * o4 < 0:
                hits.append([i, j])
    return hits


class CurvatureAwareChannelGeometry(ChannelGeometry):
    """Smooth-centerline comparator with an explicit local-width safety gate."""

    def __init__(self, spec):
        extra = {"smoothingIterations", "curvatureSafetyFactor", "minimumHalfWidthFraction"}
        if not isinstance(spec, dict) or not extra.issubset(spec):
            raise ValueError("Curvature-aware specification keys are required")
        base = {key: value for key, value in spec.items() if key not in extra}
        super().__init__(base)
        iterations = spec["smoothingIterations"]
        safety = spec["curvatureSafetyFactor"]
        minimum = spec["minimumHalfWidthFraction"]
        if type(iterations) is not int or not 1 <= iterations <= 8:
            raise ValueError("smoothingIterations must be an integer in 1..8")
        if (isinstance(safety, bool) or not isinstance(safety, (int, float))
                or not np.isfinite(safety) or not 0 < safety < 1):
            raise ValueError("curvatureSafetyFactor must be in (0,1)")
        if (isinstance(minimum, bool) or not isinstance(minimum, (int, float))
                or not np.isfinite(minimum) or not 0 < minimum <= 1):
            raise ValueError("minimumHalfWidthFraction must be in (0,1]")
        smooth = _corner_cut(self.path, iterations)
        radii = _curvature_radii(smooth)
        widths = np.minimum(self.half_width, safety * radii)
        widths = np.maximum(widths, minimum * self.half_width)
        self.path = smooth
        self.path.flags.writeable = False
        self.local_widths = widths
        self.local_widths.flags.writeable = False
        self.curvature_safety_factor = float(safety)
        self.minimum_half_width_fraction = float(minimum)

    def surfaces(self, xy):
        xy = np.asarray(xy, dtype=float)
        if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) > 1_000_000 or not np.isfinite(xy).all():
            raise ValueError("Finite N x 2 query required; N <= 1000000")
        squared = np.full(len(xy), np.inf)
        nearest_width = np.full(len(xy), self.half_width)
        for i, (start, end) in enumerate(zip(self.path[:-1], self.path[1:])):
            direction = end - start
            difference = xy - start
            denominator = np.dot(direction, direction)
            if denominator == 0:
                continue
            t = np.clip(np.sum(difference * direction, axis=1) / denominator, 0, 1)
            candidate = np.sum((difference - t[:, None] * direction) ** 2, axis=1)
            select = candidate < squared
            squared[select] = candidate[select]
            segment_width = self.local_widths[i] + t * (self.local_widths[i + 1] - self.local_widths[i])
            nearest_width[select] = segment_width[select]
        incision = self.depth * np.maximum(0, 1 - squared / nearest_width ** 2)
        bed = self.top - incision
        return {"distance": np.sqrt(squared), "effectiveHalfWidth": nearest_width,
                "incision": incision, "bed": bed,
                "split": bed + self.fraction * incision}

    def bank_audit(self):
        tangent = np.gradient(self.path, axis=0)
        length = np.linalg.norm(tangent, axis=1)
        if np.any(length == 0):
            raise ValueError("Smoothed centerline contains a stationary point")
        normals = np.column_stack((-tangent[:, 1] / length, tangent[:, 0] / length))
        left = self.path + normals * self.local_widths[:, None]
        right = self.path - normals * self.local_widths[:, None]
        return {"leftBankXY": left.tolist(), "rightBankXY": right.tolist(),
                "leftSelfIntersections": _segment_intersections(left),
                "rightSelfIntersections": _segment_intersections(right),
                "minimumEffectiveHalfWidth": float(self.local_widths.min()),
                "maximumEffectiveHalfWidth": float(self.local_widths.max()),
                "passed": not _segment_intersections(left) and not _segment_intersections(right)}


def make_curvature_aware_spec(seed=3701):
    from .channel_geometry import make_synthetic_spec
    spec = make_synthetic_spec(seed)
    spec.update(smoothingIterations=2, curvatureSafetyFactor=0.65,
                minimumHalfWidthFraction=0.35)
    return spec
