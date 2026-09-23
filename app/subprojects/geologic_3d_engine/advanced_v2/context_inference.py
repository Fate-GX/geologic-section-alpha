"""Conservative surrounding-geology inference for artificial surface routes."""
from __future__ import annotations
from collections import defaultdict

EXCLUDED_SURFACE_DOMAINS = {"ArtificiallyModifiedTerrain", "Unresolved", None}


def context_evidence_from_plan(plan: dict, legend_classifier) -> dict:
    """Classify mapped samples without requiring complete DEM elevations."""
    terrain = plan.get("terrainProfile", [])
    samples = sorted(plan.get("surfaceGeology", {}).get("samples", []),
                     key=lambda row: float(row["stationM"]))
    if len(terrain) < 2 or not samples:
        raise ValueError("context plan needs route stations and surface geology")
    total = float(terrain[-1]["stationM"])
    if total <= 0:
        raise ValueError("context route length must be positive")
    evidence = []
    stations = [float(row["stationM"]) for row in samples]
    for index, (row, station) in enumerate(zip(samples, stations)):
        left = 0.0 if index == 0 else (stations[index-1] + station) / 2.0
        right = total if index == len(stations)-1 else (station + stations[index+1]) / 2.0
        legend = row.get("legend")
        domain = "Unresolved" if not isinstance(legend, dict) else legend_classifier(legend)
        evidence.append({"stationM":station, "weightM":max(0.0, right-left),
                         "classifiedDomain":domain,
                         "symbol":None if not legend else legend.get("symbol")})
    return {"sampleEvidence":evidence, "routeLengthM":total,
            "terrainElevationUsedForInference":False}


def infer_natural_domain(classification: dict, *, minimum_natural_weight_fraction=0.35,
                         minimum_natural_dominance=0.65) -> dict:
    samples = classification.get("sampleEvidence", [])
    totals = defaultdict(float)
    total_weight = 0.0
    natural_weight = 0.0
    for row in samples:
        weight = float(row.get("weightM", 0.0))
        domain = row.get("classifiedDomain")
        if weight < 0:
            raise ValueError("context sample weight cannot be negative")
        total_weight += weight
        if domain not in EXCLUDED_SURFACE_DOMAINS:
            totals[domain] += weight
            natural_weight += weight
    natural_fraction = natural_weight / total_weight if total_weight else 0.0
    if not totals:
        return {"passed":False, "reason":"NoNaturalContextEvidence",
                "naturalWeightFraction":natural_fraction, "domainFractions":{}}
    winner, winner_weight = max(totals.items(), key=lambda pair: (pair[1], pair[0]))
    dominance = winner_weight / natural_weight
    passed = natural_fraction >= minimum_natural_weight_fraction and dominance >= minimum_natural_dominance
    return {"passed":passed,
            "reason":None if passed else "InsufficientNaturalContextDominance",
            "inferredNaturalDomain":winner, "naturalWeightFraction":natural_fraction,
            "naturalDominance":dominance,
            "domainFractions":{key:value/natural_weight for key,value in sorted(totals.items())},
            "method":"RouteLengthWeightedNaturalSamples_ArtificialExcluded",
            "subsurfaceMeaning":"SurroundingMappedGeologyPrior_NotLocalObservation",
            "realRegionAuthorized":False}
