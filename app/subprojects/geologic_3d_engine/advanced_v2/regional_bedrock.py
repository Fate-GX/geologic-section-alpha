"""Retain mapped bedrock beneath a sediment-cover prior, independent of location.

Rock identity is map-supported; buried contact depths remain synthetic. Neither
a prefecture name nor topographic relief selects a rock. Conflicting bedrock
families are retained as unresolved candidates, not invented stacked strata.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np

from regional_major_lithology import MAJOR_LITHOLOGIES, SPECIFICITY_ORDER
from regional_lithology_data import load_vocabulary, matching_keys, regional_dataset_for_plan

POLICY_ID = "ADV2-REGIONAL-BEDROCK-UNDER-COVER-1.0"
SOURCE_ID = "GSJ-SEAMLESS-V2-API"
API_URL = "https://gbank.gsj.jp/seamless/v2/api/1.3.1/legend.json?point={lat:.8f},{lon:.8f}&type=level4"
BEDROCK_KEYS = {key for key, row in MAJOR_LITHOLOGIES.items()
                if "UnconsolidatedSedimentTerrain" not in row["domains"]}
BEDROCK_KEYS.discard("volcanic_ash_soil")


def _rock(legend):
    if not isinstance(legend, dict):
        return None
    vocabulary = load_vocabulary()
    by_key = {r["key"]:r for r in vocabulary["lithologies"]}
    matches = [key for key in matching_keys(legend, vocabulary)
               if "UnconsolidatedSedimentTerrain" not in by_key[key]["domains"]]
    for group in vocabulary.get("sourceGroups", []):
        if set(matches) == set(group["members"]):
            return {"key":group["key"], "ja":group["ja"], "en":group["en"], "memberKeys":matches}
    if len(matches) > 1:
        return {"key":"unresolved_mixed_bedrock", "ja":"岩種未解決",
                "en":"unresolved mixed bedrock", "memberKeys":matches}
    if not matches:
        return None
    key = matches[0]
    return {"key":key, "ja":by_key[key]["ja"], "en":by_key[key]["en"], "memberKeys":[key]}


def resolve_regional_bedrock(plan):
    """Resolve among bedrock samples, NOT among all sediment/bedrock samples."""
    data = regional_dataset_for_plan(plan)
    route = [r["sourceSample"] for r in data["records"] if r["origin"] == "OnRoute"]
    nearby = [r["sourceSample"] for r in data["records"] if r["origin"] == "Nearby"]
    candidates = {}
    origin = "OnRouteMappedBedrock"
    for samples, kind in ((route, origin), (nearby, "NearbyMappedBedrock")):
        for sample in samples:
            rock = _rock(sample.get("legend", {}))
            if not rock:
                continue
            record = candidates.setdefault(rock["key"], {**rock, "evidence":[]})
            record["evidence"].append(copy.deepcopy(sample))
        if candidates:
            origin = kind
            break
    ranked = sorted(candidates.values(), key=lambda r: (-len(r["evidence"]), r["key"]))
    # No fabrication of a contact separating multiple incompatible rock parents.
    selected = ranked[0] if len(ranked) == 1 and ranked[0]["key"] != "unresolved_mixed_bedrock" else None
    if selected and origin == "NearbyMappedBedrock" and len(selected["evidence"]) < 2:
        selected = None
    stations = [float(r["stationM"]) for r in plan.get("terrainProfile", [])]
    too_long = bool(stations and max(stations) - min(stations) > 5000.0)
    if too_long:
        selected = None
    return {"policyId":POLICY_ID, "sourceIds":[SOURCE_ID], "origin":origin,
            "status":("RouteTooLongForSingleBedrockPrior" if too_long else
                      "RegionalBedrockPrior" if selected else
                      "ConflictingBedrockCandidates" if len(ranked) > 1 else
                      "InsufficientRegionalBedrockEvidence"),
            "selected":selected, "candidates":ranked,
            "mandatoryWhenSelected":True, "basisType":"SyntheticAssumption",
            "identityBasis":"MappedSurfaceGeology", "contactDepthBasis":"UncalibratedSyntheticPrior",
            "subsurfaceContactObserved":False,
            "mappedSourceId":plan.get("surfaceGeology", {}).get("sourceId"),
            "sourceEdition":plan.get("surfaceGeology", {}).get("sourceEdition"),
            "sourceLayers":copy.deepcopy([r for r in plan.get("layers", [])
                                          if r.get("evidence_kind") == "SurfaceGeology"])}


def acquire_bedrock_neighborhood(plan, *, fetch=None):
    """At most eight point queries, four workers; retain failures as missing data.

    Search radius is an explicit local-context policy, not a geological law.
    Off-route observations NEVER constrain a contact at a route station.
    """
    if fetch is None:
        from route_location import fetch_bytes
        fetch = fetch_bytes
    route = plan.get("routeLonLat", [])
    if len(route) < 2:
        return {"status":"MissingRoute", "samples":[], "queries":[]}
    stations = [float(r["stationM"]) for r in plan.get("terrainProfile", [])]
    if stations and max(stations) - min(stations) > 5000.0:
        return {"status":"RequiresSegmentedRegionalContext", "samples":[], "queries":[]}
    lon = sum(float(p[0]) for p in route) / len(route)
    lat = sum(float(p[1]) for p in route) / len(route)
    if not (122 <= lon <= 154 and 20 <= lat <= 46):
        return {"status":"OutsideJapanContextSearch", "samples":[], "queries":[]}
    def query(item):
        radius, bearing = item
        angle = math.radians(bearing)
        y = lat + radius * math.cos(angle) / 111195.0
        x = lon + radius * math.sin(angle) / (111195.0 * math.cos(math.radians(lat)))
        url = API_URL.format(lat=y, lon=x)
        record = {"longitude":x, "latitude":y, "radiusM":radius,
                  "url":url, "sourceId":SOURCE_ID, "basisType":"MappedSurfaceUnit"}
        try:
            raw = fetch(url)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("NoUnambiguousPointLegend")
            from geologic_3d_engine.section.gsj_surface_geology import validate_legend
            legend = validate_legend(data, allow_color_metadata_mismatch=True)
            record.update(legend=legend, sha256=hashlib.sha256(raw).hexdigest(), status="Available")
        except Exception as exc:
            record.update(status="Unavailable", errorType=type(exc).__name__)
        return record
    points = [(r, b) for r in (1000.0, 2000.0) for b in (0, 90, 180, 270)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(query, points))
    return {"status":"BoundedLocalSearch", "radiusLimitM":2000.0,
            "acquiredUtc":datetime.now(timezone.utc).isoformat(),
            "queries":records, "samples":[r for r in records if r["status"] == "Available"],
            "absenceProvesNoBedrock":False}


def has_ash_evidence(plan):
    # Only local/nearby source labels, never a globally available lithology name.
    return any(c["key"] == "volcanic_ash_soil"
               for c in regional_dataset_for_plan(plan)["candidates"])


def apply_regional_bedrock_geometry(model):
    """Truncate the existing shared cover stack against one inferred substrate.

    Far from an on-route mapped bedrock point the old *synthetic* base is kept.
    Towards that point cover thins smoothly to the protected surface cover.
    Nearby-only evidence selects identity, not on-route exposure or depth.
    """
    evidence = model.get("regionalBedrockEvidence", {})
    selected = evidence.get("selected")
    if not selected:
        return model
    if model.get("lithologySelection", {}).get("domain") != "UnconsolidatedSedimentTerrain":
        raise ValueError("Regional bedrock under cover is out of scope")
    layers = model["composition"]["layersTopDown"]
    bodies = model["syntheticEventArchitecture"]["renderBodies"]
    expected_id = "ADV2-REGIONAL-" + selected["key"].upper()
    if layers[-1]["unitId"] != expected_id or len(bodies) != len(layers):
        raise ValueError("Required regional bedrock is not bound to the substrate")
    x = np.asarray(model["stationsM"], float)
    original = np.asarray(layers[-1]["topElevationM"], float)
    cover_base = np.asarray(layers[0]["bottomElevationM"], float)
    support = max(float(np.ptp(x)) * 0.5, 1.0)
    influence = np.zeros_like(x)
    anchors = []
    if evidence.get("origin") == "OnRouteMappedBedrock":
        for record in selected["evidence"]:
            station = float(record["stationM"])
            if not math.isfinite(station) or not x[0] <= station <= x[-1]:
                raise ValueError("Mapped bedrock station outside section")
            anchors.append(station)
            t = np.clip(np.abs(x - station) / support, 0, 1)
            influence = np.maximum(influence, 1 - (6*t**5 - 15*t**4 + 10*t**3))
    contact = np.minimum(cover_base, original + influence * (cover_base - original))
    previous = np.asarray(model["terrainElevationM"], float)
    for index, (layer, body) in enumerate(zip(layers, bodies)):
        old_bottom = np.asarray(layer["bottomElevationM"], float)
        bottom = old_bottom if index == len(layers)-1 else np.minimum(previous, np.maximum(old_bottom, contact))
        thickness = previous - bottom
        common = {"topElevationM":previous.tolist(), "bottomElevationM":bottom.tolist(),
                  "thicknessM":thickness.tolist(), "activeMask":(thickness > 1e-9).tolist(),
                  "allowPinchout":index != 0,
                  "regionalBedrockTruncationMask":(bottom == contact).tolist(),
                  "regionalBedrockTruncationContactClass":"InferredCoverBedrockContact"}
        if index == len(layers)-2:
            common["bottomContactClass"] = "InferredCoverBedrockContact"
        layer.update(common); body.update(common)
        previous = bottom
    model["regionalBedrockGeometry"] = {
        "policyId":POLICY_ID, "basisType":"SyntheticAssumption", "unitId":expected_id,
        "contactElevationM":contact.tolist(), "onRouteAnchorStationsM":anchors,
        "influenceSupportM":support, "mapBoundaryPositionMeasured":False,
        "contactConstruction":"SharedStackTruncatedAgainstRegionalSubstratePrior",
        "surfaceMapProjectedVertically":False, "regionalRockRequiredAndRendered":True,
        "depthCalibrated":False,
        "limitations":["Map scale does not locate a surveyed outcrop/contact",
                       "Underlying rock identity and all buried depths are hypotheses"]}
    return model


def audit_regional_bedrock(model):
    evidence = model.get("regionalBedrockEvidence", {})
    if not evidence.get("selected"):
        return {"applicable":False, "passed":True, "errors":[]}
    expected_id = "ADV2-REGIONAL-" + evidence["selected"]["key"].upper()
    layers = model.get("composition", {}).get("layersTopDown", [])
    bodies = model.get("syntheticEventArchitecture", {}).get("renderBodies", [])
    geometry = model.get("regionalBedrockGeometry", {})
    errors = []
    if not layers or layers[-1].get("unitId") != expected_id or not any(
            b.get("unitId") == expected_id and any(b.get("activeMask", [])) for b in bodies):
        errors.append("RequiredRegionalBedrockMissing")
    if not geometry or geometry.get("contactElevationM") != layers[-1].get("topElevationM"):
        errors.append("RegionalBedrockGeometryBindingMismatch")
    if evidence.get("subsurfaceContactObserved") is not False or evidence.get("basisType") != "SyntheticAssumption":
        errors.append("RegionalInferencePromotedToObservation")
    return {"applicable":True, "passed":not errors, "errors":errors,
            "requiredUnitId":expected_id, "basisType":"SyntheticAssumption"}
