from __future__ import annotations

import copy


POLICY_ID = "TerrainConditionedBroadPrior-1.0"

# These controls only vary the spatial texture of an already-selected domain
# prior.  They never add/remove units or authorize valleys, faults, fans,
# landslides, terraces, reclamation, or other localized events.
_TEXTURE = {
    "BroadLowland": {"rangeFraction": 0.34, "logStd": 0.18},
    "CoastalLowland": {"rangeFraction": 0.40, "logStd": 0.15},
    "RollingHills": {"rangeFraction": 0.23, "logStd": 0.30},
    "MountainousRelief": {"rangeFraction": 0.17, "logStd": 0.52},
    "NarrowValleyOrGorge": {"rangeFraction": 0.20, "logStd": 0.42},
    "MountainFrontPiedmont": {"rangeFraction": 0.27, "logStd": 0.36},
    "ArtificiallyModifiedOrUnresolved": {"rangeFraction": 0.30, "logStd": 0.18},
    "Unresolved": {"rangeFraction": 0.30, "logStd": 0.20},
}


def condition_profile_for_terrain(profile, terrain_classification, route_length_m):
    if profile is None:
        return None
    length = float(route_length_m)
    if length <= 0.0:
        raise ValueError("route length must be positive")
    terrain_class = terrain_classification.get("primaryClass", "Unresolved")
    control = _TEXTURE.get(terrain_class, _TEXTURE["Unresolved"])
    result = copy.deepcopy(profile)
    background = result.setdefault("backgroundArchitecture", {})
    background["defaultCorrelationRangeM"] = max(25.0, length * control["rangeFraction"])
    background["defaultLogStd"] = control["logStd"]
    result["terrainConditioning"] = {
        "policyId": POLICY_ID,
        "terrainClass": terrain_class,
        "classificationConfidence": terrain_classification.get("confidenceClass"),
        "effect": "BackgroundThicknessTextureOnly",
        "localizedEventAuthorization": [],
        "terrainDeterminesUnitSequence": False,
        "terrainDeterminesContactGeometry": False,
        "basisType": "SyntheticAssumption",
    }
    return result
