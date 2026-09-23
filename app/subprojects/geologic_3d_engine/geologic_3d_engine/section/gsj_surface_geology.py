"""Typed GSJ Seamless V2 point-legend samples for section routes."""
from __future__ import annotations

import math
from typing import Callable, Mapping, Sequence


GSJ_API_VERSION = "1.3.1"
GSJ_LEGEND_URL = "https://gbank.gsj.jp/seamless/v2/api/1.3.1/legend.json"
REQUIRED_FIELDS = {
    "symbol", "formationAge_ja", "formationAge_en", "lithology_ja",
    "lithology_en", "title", "value", "r", "g", "b"}


def validate_legend(record: Mapping, *, allow_color_metadata_mismatch=False):
    if not isinstance(record, Mapping) or not REQUIRED_FIELDS.issubset(record):
        raise ValueError("GSJ legend response is incomplete")
    if not isinstance(record["symbol"], str) or not record["symbol"].strip():
        raise ValueError("GSJ legend symbol is required")
    if (not isinstance(record["value"], str) or len(record["value"]) != 6 or
            any(c.lower() not in "0123456789abcdef" for c in record["value"])):
        raise ValueError("GSJ legend colour must be six hexadecimal digits")
    if any(isinstance(record[key], bool) or not isinstance(record[key], int) or
           not 0 <= record[key] <= 255 for key in ("r", "g", "b")):
        raise ValueError("GSJ RGB values must be integers in [0,255]")
    expected="".join(f"{record[k]:02x}" for k in ("r", "g", "b"))
    if record["value"].lower() != expected:
        if not allow_color_metadata_mismatch:
            raise ValueError("GSJ hexadecimal and RGB colours disagree")
        result=dict(record);result["sourceColorValue"]=record["value"]
        result["value"]=expected;result["colorMetadataStatus"]="SourceHexRgbMismatch_RgbUsedForDisplay"
        return result
    result=dict(record);result["colorMetadataStatus"]="SourceHexRgbConsistent"
    return result


def sample_route_legends(terrain_profile: Sequence[Mapping],
                         query_point: Callable[[float, float], Mapping],
                         source_edition: str, *, allow_color_metadata_mismatch=False):
    """Attach official point legends and bracket map-unit transitions.

    Transition locations are interval-censored between adjacent point samples;
    no raster-colour inversion or fictitious exact contact is produced.
    """
    if not terrain_profile or not callable(query_point) or not source_edition:
        raise ValueError("profile, query function and source edition are required")
    samples = []
    previous_station = -math.inf
    for row in terrain_profile:
        required = {"stationM", "longitude", "latitude"}
        if not isinstance(row, Mapping) or not required.issubset(row):
            raise ValueError("terrain sample lacks station or coordinates")
        station = float(row["stationM"])
        if not math.isfinite(station) or station <= previous_station:
            raise ValueError("stations must be finite and strictly increasing")
        raw = query_point(float(row["latitude"]), float(row["longitude"]))
        legend = (None if isinstance(raw, Mapping) and not raw.get("symbol")
                  else validate_legend(raw,allow_color_metadata_mismatch=allow_color_metadata_mismatch))
        samples.append({"stationM": station, "longitude": float(row["longitude"]),
                        "latitude": float(row["latitude"]), "legend": legend,
                        "sampleStatus": "Mapped" if legend else "NoMappedUnit"})
        previous_station = station
    intervals = []
    start = 0
    for index in range(1, len(samples)+1):
        current_symbol = None if index == len(samples) or samples[index]["legend"] is None else samples[index]["legend"]["symbol"]
        start_symbol = None if samples[start]["legend"] is None else samples[start]["legend"]["symbol"]
        if index == len(samples) or current_symbol != start_symbol:
            intervals.append({
                "symbol": start_symbol,
                "lithologyJa": None if samples[start]["legend"] is None else samples[start]["legend"]["lithology_ja"],
                "formationAgeJa": None if samples[start]["legend"] is None else samples[start]["legend"]["formationAge_ja"],
                "startStationM": samples[start]["stationM"],
                "endStationM": samples[index-1]["stationM"],
                "firstSampleIndex": start, "lastSampleIndex": index-1})
            start = index
    transitions = []
    for left, right in zip(samples[:-1], samples[1:]):
        left_symbol = None if left["legend"] is None else left["legend"]["symbol"]
        right_symbol = None if right["legend"] is None else right["legend"]["symbol"]
        if left_symbol != right_symbol:
            transitions.append({"leftSymbol":left_symbol,
                "rightSymbol":right_symbol,
                "lowerStationM":left["stationM"], "upperStationM":right["stationM"],
                "estimatedStationM":0.5*(left["stationM"]+right["stationM"]),
                "uncertaintyM":0.5*(right["stationM"]-left["stationM"]),
                "locatorStatus":"IntervalCensoredBetweenPointQueries"})
    return {"sourceId":"GSJ-SEAMLESS-V2-API", "apiVersion":GSJ_API_VERSION,
            "sourceEdition":source_edition, "samples":samples,
            "mappedUnitIntervals":intervals, "transitions":transitions,
            "interpretationBoundary":"MappedSurfaceUnits_NotSubsurfaceContacts"}
