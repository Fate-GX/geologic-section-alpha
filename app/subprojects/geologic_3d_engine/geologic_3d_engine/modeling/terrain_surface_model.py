"""Terrain-only section model. It contains no lithology assumptions."""
import math
from .artifact_hash import signed_artifact,verify_artifact

SCHEMA="TerrainSurfaceModel-1.0"

def build_terrain_surface_model(samples,*,source_id,source_sha256,sampling_method):
    if not isinstance(samples,list) or len(samples)<2:raise ValueError("terrain needs at least two samples")
    rows=[];last=-math.inf
    for row in samples:
        station=float(row["stationM"]);elevation=float(row["elevationM"])
        if not math.isfinite(station) or not math.isfinite(elevation) or station<=last:raise ValueError("terrain samples must be finite and ordered")
        rows.append({"stationM":station,"elevationM":elevation});last=station
    if rows[0]["stationM"]!=0:raise ValueError("terrain must start at station zero")
    return signed_artifact({"schemaVersion":SCHEMA,"coordinateFrame":"RouteStation_AbsoluteElevationM",
      "samples":rows,"sourceId":source_id,"sourceArtifactSha256":source_sha256,
      "samplingMethod":sampling_method,"containsLithology":False})

def verify_terrain_surface_model(value):return verify_artifact(value,SCHEMA)
