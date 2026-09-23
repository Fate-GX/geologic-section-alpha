"""Assemble bounded contact projections into non-crossing lithology intervals."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def assemble_evidence_bounded_section(
        terrain_samples: Sequence[Mapping], contact_projections_bottom_up: Sequence[Mapping],
        units_bottom_up: Sequence[Mapping], *, ordering_tolerance_m: float) -> dict:
    """Create unit intervals only where their required boundaries are supported.

    Each declared unit uses its basal contact and either the next contact or the
    terrain as its top. Missing support remains unknown; crossing contacts are
    rejected rather than clipped or reordered.
    """
    if (isinstance(ordering_tolerance_m, bool)
            or not isinstance(ordering_tolerance_m, (int, float))
            or not math.isfinite(ordering_tolerance_m) or ordering_tolerance_m < 0):
        raise ValueError("ordering_tolerance_m must be finite and non-negative")
    if (not isinstance(terrain_samples, Sequence)
            or isinstance(terrain_samples, (str, bytes)) or not terrain_samples):
        raise ValueError("terrain samples are required")
    stations = []
    terrain = []
    for row in terrain_samples:
        try:
            station = float(row["stationM"]); elevation = float(row["elevationM"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("terrain sample requires stationM and elevationM") from exc
        if not math.isfinite(station) or not math.isfinite(elevation):
            raise ValueError("terrain samples must be finite")
        stations.append(station); terrain.append(elevation)
    if any(b <= a for a, b in zip(stations, stations[1:])):
        raise ValueError("terrain stations must be strictly increasing")
    if (not isinstance(contact_projections_bottom_up, Sequence)
            or isinstance(contact_projections_bottom_up, (str, bytes))
            or not contact_projections_bottom_up):
        raise ValueError("one or more basal contact projections are required")
    if (not isinstance(units_bottom_up, Sequence)
            or isinstance(units_bottom_up, (str, bytes))
            or len(units_bottom_up) != len(contact_projections_bottom_up)):
        raise ValueError("one unit is required for every basal contact")
    contact_ids = []
    contact_values = []
    for projection in contact_projections_bottom_up:
        contact_id = projection.get("contactId")
        route = projection.get("routeProjection", projection)
        samples = route.get("samples") if isinstance(route, Mapping) else None
        if not isinstance(contact_id, str) or not contact_id or not isinstance(samples, Sequence):
            raise ValueError("invalid contact projection")
        if len(samples) != len(stations):
            raise ValueError("contact and terrain sample counts differ")
        if [float(row["stationM"]) for row in samples] != stations:
            raise ValueError("contact and terrain stations differ")
        values = []
        for row in samples:
            value = row.get("contactElevationM")
            if value is None:
                values.append(None)
            else:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError("supported contact elevation must be finite")
                values.append(number)
        contact_ids.append(contact_id); contact_values.append(values)
    if len(set(contact_ids)) != len(contact_ids):
        raise ValueError("contact IDs must be unique")

    errors = []
    unit_samples = []
    for unit_index, unit in enumerate(units_bottom_up):
        if not isinstance(unit, Mapping) or not unit.get("unitId"):
            raise ValueError("every unit requires a unitId")
        if unit.get("basalContactId") != contact_ids[unit_index]:
            raise ValueError("unit basalContactId does not match contact order")
        expected_top = (contact_ids[unit_index + 1]
                        if unit_index + 1 < len(contact_ids) else "Terrain")
        if unit.get("topBoundary") != expected_top:
            raise ValueError("unit topBoundary must explicitly match the next contact or Terrain")
        lower_values = contact_values[unit_index]
        upper_values = (contact_values[unit_index + 1]
                        if unit_index + 1 < len(contact_values) else terrain)
        rows = []
        for sample_index, (lower, upper) in enumerate(zip(lower_values, upper_values)):
            supported = lower is not None and upper is not None
            if supported and upper + ordering_tolerance_m < lower:
                errors.append({"code": "ContactOrderViolation",
                               "unitId": unit["unitId"], "sampleIndex": sample_index,
                               "stationM": stations[sample_index],
                               "lowerElevationM": lower, "upperElevationM": upper})
            if supported and upper > terrain[sample_index] + ordering_tolerance_m:
                errors.append({"code": "ContactAboveTerrain",
                               "unitId": unit["unitId"], "sampleIndex": sample_index,
                               "stationM": stations[sample_index],
                               "contactElevationM": upper,
                               "terrainElevationM": terrain[sample_index]})
            rows.append({"stationM": stations[sample_index],
                         "bottomElevationM": lower if supported else None,
                         "topElevationM": upper if supported else None,
                         "thicknessM": max(0.0, upper - lower) if supported else None,
                         "coverageStatus": "BoundedByEvidence" if supported
                                           else "UnknownMissingBoundary"})
        unit_samples.append({"unitId": unit["unitId"],
                             "normalizedLithology": unit.get("normalizedLithology"),
                             "basalContactId": unit["basalContactId"],
                             "topBoundary": unit["topBoundary"],
                             "samples": rows})
    if errors:
        raise ValueError({"message": "section contact topology failed", "errors": errors})
    return {"schemaVersion": "EvidenceBoundedLithologySection-1.0",
            "stationsM": stations, "terrainElevationM": terrain,
            "contactIdsBottomUp": contact_ids, "unitsBottomUp": unit_samples,
            "unknownPreserved": True, "contactClippingUsed": False,
            "orderingToleranceM": float(ordering_tolerance_m),
            "realRegionAuthorization": "RequiresExternalReleaseGate"}
