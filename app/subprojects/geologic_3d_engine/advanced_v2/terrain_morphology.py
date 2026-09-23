from __future__ import annotations

import math
from statistics import median


POLICY_ID = "TerrainMorphologyHypothesis-1.0"

# These tokens are evidence labels, not elevation-shape heuristics.  In
# particular, anthropogenic and coastal classes must never be inferred from a
# smooth or low profile alone.
_ARTIFICIAL_TOKENS = (
    "artificial", "reclaimed", "reclamation", "embankment", "cut and fill",
    "盛土", "埋立", "干拓", "切土",
)
_COASTAL_TOKENS = (
    "coastal lowland", "coastal plain", "tidal flat", "delta", "浜堤",
    "海岸低地", "三角州", "干潟",
)


def _quantile(values, probability):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position)); upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _evidence_text(landform_evidence):
    if not landform_evidence:
        return ""
    parts = []
    for row in landform_evidence:
        if isinstance(row, str):
            parts.append(row)
        elif isinstance(row, dict):
            parts.extend(str(row.get(key, "")) for key in
                         ("class", "label", "title", "description"))
    return " ".join(parts).casefold()


_DIRECT_EVIDENCE_CLASSES = {"BroadLowland", "RollingHills", "MountainousRelief",
    "NarrowValleyOrGorge", "MountainFrontPiedmont", "CoastalLowland",
    "ArtificiallyModifiedOrUnresolved"}


def classify_terrain_morphology(stations_m, elevations_m, *, landform_evidence=None):
    """Return ranked terrain-shape hypotheses without inferring subsurface geology.

    The profile metrics are dimensionless where practical, so the same logic can
    be used for short diagnostic sections and longer regional transects.  Typed
    landform evidence may override shape-only ambiguity for artificial/coastal
    settings, but it does not authorize any geological event or contact.
    """
    stations = [float(value) for value in stations_m]
    elevations = [float(value) for value in elevations_m]
    if len(stations) != len(elevations) or len(stations) < 3:
        raise ValueError("terrain profile requires at least three paired samples")
    if not all(math.isfinite(value) for value in stations + elevations):
        raise ValueError("terrain profile values must be finite")
    if any(right <= left for left, right in zip(stations, stations[1:])):
        raise ValueError("stations must be strictly increasing")

    span = stations[-1] - stations[0]
    relief = max(elevations) - min(elevations)
    slopes = [(right_y-left_y)/(right_x-left_x) for left_x, right_x, left_y, right_y
              in zip(stations, stations[1:], elevations, elevations[1:])]
    abs_slopes = [abs(value) for value in slopes]
    q90_slope = _quantile(abs_slopes, 0.90)
    low_gradient_fraction = sum(value <= 0.03 for value in abs_slopes) / len(abs_slopes)
    slope_turns = sum(1 for left, right in zip(slopes, slopes[1:])
                      if left * right < 0.0)
    turning_density = slope_turns / max(1, len(slopes)-1)
    roughness = median(abs(right-left) for left, right in zip(slopes, slopes[1:])) \
        if len(slopes) > 1 else 0.0
    relief_ratio = relief / span

    minimum_index = min(range(len(elevations)), key=elevations.__getitem__)
    minimum_fraction = (stations[minimum_index] - stations[0]) / span
    edge_reference = 0.5 * (elevations[0] + elevations[-1])
    valley_depth_ratio = max(0.0, edge_reference - elevations[minimum_index]) / span
    valley_asymmetry = abs(minimum_fraction - 0.5) * 2.0

    scores = {
        "BroadLowland": 0.0,
        "RollingHills": 0.0,
        "MountainousRelief": 0.0,
        "NarrowValleyOrGorge": 0.0,
        "MountainFrontPiedmont": 0.0,
        "CoastalLowland": 0.0,
        "ArtificiallyModifiedOrUnresolved": 0.0,
    }
    scores["BroadLowland"] = max(0.0, 1.0-relief_ratio/0.035) * low_gradient_fraction
    scores["RollingHills"] = min(1.0, relief_ratio/0.06) * min(1.0, turning_density/0.18)
    scores["MountainousRelief"] = min(1.0, relief_ratio/0.18) * min(1.0, q90_slope/0.35)
    interior_minimum = 0.08 < minimum_fraction < 0.92
    scores["NarrowValleyOrGorge"] = (1.10 if interior_minimum else 0.55) * \
        min(1.0, valley_depth_ratio/0.12) * min(1.0, q90_slope/0.30)
    # A mountain-front profile combines substantial relief with a sizeable flat
    # fraction; unlike a valley it need not have a central minimum.
    scores["MountainFrontPiedmont"] = min(1.0, relief_ratio/0.12) * \
        min(1.0, low_gradient_fraction/0.45)

    evidence_text = _evidence_text(landform_evidence)
    evidence_classes = []
    direct_rows = [row for row in landform_evidence or [] if isinstance(row, dict)
                   and row.get("class") in _DIRECT_EVIDENCE_CLASSES]
    station_groups = {}
    for index, row in enumerate(direct_rows):
        station_groups.setdefault(row.get("stationM", f"unlocated-{index}"), []).append(row)
    station_classes = []
    for rows in station_groups.values():
        artificial = next((row["class"] for row in rows
                           if row["class"] == "ArtificiallyModifiedOrUnresolved"), None)
        station_classes.append(artificial or rows[0]["class"])
    if station_classes:
        for evidence_class in set(station_classes):
            fraction = station_classes.count(evidence_class) / len(station_classes)
            scores[evidence_class] = max(scores[evidence_class], 0.40 + 0.90*fraction)
            if fraction >= 0.55:
                evidence_classes.append(evidence_class)
    if not direct_rows and any(token in evidence_text for token in _ARTIFICIAL_TOKENS):
        scores["ArtificiallyModifiedOrUnresolved"] = 1.25
        evidence_classes.append("ArtificiallyModifiedOrUnresolved")
    if not direct_rows and any(token in evidence_text for token in _COASTAL_TOKENS):
        scores["CoastalLowland"] = 1.20
        evidence_classes.append("CoastalLowland")

    ranked = sorted(scores.items(), key=lambda row: (-row[1], row[0]))
    confidence_gap = ranked[0][1] - ranked[1][1]
    primary = ranked[0][0] if ranked[0][1] >= 0.20 else "Unresolved"
    confidence = "EvidenceSupported" if primary in evidence_classes else (
        "ShapeSupported" if confidence_gap >= 0.15 else "Ambiguous")
    return {
        "policyId": POLICY_ID,
        "primaryClass": primary,
        "confidenceClass": confidence,
        "rankedHypotheses": [{"class": name, "score": score} for name, score in ranked],
        "metrics": {
            "sampleCount": len(stations), "spanM": span, "reliefM": relief,
            "reliefToSpan": relief_ratio, "absoluteSlopeP90": q90_slope,
            "lowGradientFraction": low_gradient_fraction,
            "slopeTurningDensity": turning_density, "slopeRoughness": roughness,
            "profileMinimumFraction": minimum_fraction,
            "valleyDepthToSpan": valley_depth_ratio,
            "valleyAsymmetry": valley_asymmetry,
        },
        "evidenceClasses": evidence_classes,
        "terrainDeterminesSubsurface": False,
        "localizedEventAuthorization": [],
        "limitations": [
            "Profile morphology is route- and scale-dependent",
            "Shape alone does not identify geological cause",
            "Artificial and coastal classes require typed landform evidence",
        ],
    }
