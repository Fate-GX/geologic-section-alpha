"""Terrain-independent lithology section contract and basic generator."""
import math
import numpy as np
from ..fields.separable_gaussian import sample_separable_gaussian,machine_eigen_tolerance
from .artifact_hash import signed_artifact,verify_artifact

SCHEMA="LithologySectionModel-1.0"

def generate_basic_relative_depth_lithology(stations_m,layers,*,seed,range_m=500,log_std=.18):
    """Generate correlated positive thickness without accepting terrain elevations."""
    stations=np.asarray(stations_m,dtype=float)
    if stations.ndim!=1 or len(stations)<2 or not np.isfinite(stations).all() or stations[0]!=0 or np.any(np.diff(stations)<=0):
        raise ValueError("ordered stations beginning at zero are required")
    spacing=np.diff(stations)
    if not np.allclose(spacing,spacing[0],rtol=0,atol=1e-8):raise ValueError("basic provider requires regular stations")
    if not isinstance(seed,int) or isinstance(seed,bool):raise ValueError("integer seed required")
    if range_m<=0 or log_std<0:raise ValueError("range and log standard deviation are invalid")
    if not layers:raise ValueError("at least one lithology layer is required")
    rng=np.random.default_rng(seed);outputs=[]
    for layer in layers:
        layer_range=float(layer.get("rangeM",range_m))
        layer_log_std=float(layer.get("logStd",log_std))
        if layer_range<=0 or layer_log_std<0:
            raise ValueError("layer range and log standard deviation are invalid")
        if "meanThicknessProfileM" in layer:
            mean=np.asarray(layer["meanThicknessProfileM"],dtype=float)
            if mean.shape!=stations.shape or not np.isfinite(mean).all() or np.any(mean<=0):
                raise ValueError("positive mean thickness profile matching stations is required")
        else:
            mean=float(layer["meanThicknessM"])
            if not math.isfinite(mean) or mean<=0:raise ValueError("positive mean thickness is required")
        latent=sample_separable_gaussian(nx=len(stations),ny=1,spacing_x=float(spacing[0]),spacing_y=1,
          range_x=layer_range,range_y=1,variance=1,standard_normal=rng.standard_normal((1,len(stations))),
          negative_eigen_tolerances=(machine_eigen_tolerance(len(stations)),machine_eigen_tolerance(1)))[0]
        thickness=mean*np.exp(layer_log_std*latent-.5*layer_log_std**2)
        outputs.append({"unitId":layer["unitId"],"normalizedLithology":layer["normalizedLithology"],
          "color":layer.get("color"),"thicknessM":thickness.tolist(),
          "generationParameters":{"rangeM":layer_range,"logStd":layer_log_std}})
    return signed_artifact({"schemaVersion":SCHEMA,"providerId":"BasicCorrelatedRelativeDepth-1.0",
      "representation":"RelativeDepthStack","coordinateFrame":"RouteStation_DepthBelowTerrainM",
      "stationsM":stations.tolist(),"layersTopDown":outputs,"seed":seed,
      "parameters":{"rangeM":float(range_m),"logStd":float(log_std)},
      "terrainInputAccepted":False,"geologicalValidity":"SyntheticAssumption",
      "realRegionAuthorized":False})

def verify_lithology_section_model(value):
    verify_artifact(value,SCHEMA)
    if value.get("representation") not in {"RelativeDepthStack","AbsoluteElevationSurfaces"}:raise ValueError("unsupported lithology representation")
    return value
