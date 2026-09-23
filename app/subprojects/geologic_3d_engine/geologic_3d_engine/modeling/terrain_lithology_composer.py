"""Compose independently generated terrain and lithology artifacts."""
import numpy as np
from .artifact_hash import signed_artifact
from .terrain_surface_model import verify_terrain_surface_model
from .lithology_section_model import verify_lithology_section_model

def compose_terrain_and_lithology(terrain,lithology):
    verify_terrain_surface_model(terrain);verify_lithology_section_model(lithology)
    ts=np.asarray([x["stationM"] for x in terrain["samples"]],float)
    tz=np.asarray([x["elevationM"] for x in terrain["samples"]],float)
    ls=np.asarray(lithology["stationsM"],float)
    if ls[0]<ts[0] or ls[-1]>ts[-1]:raise ValueError("lithology stations exceed terrain coverage")
    top=np.interp(ls,ts,tz);layers=[]
    if lithology["representation"]=="RelativeDepthStack":
        for layer in lithology["layersTopDown"]:
            thickness=np.asarray(layer["thicknessM"],float)
            if thickness.shape!=ls.shape or not np.isfinite(thickness).all() or np.any(thickness<=0):raise ValueError("layer thickness must be finite and positive")
            bottom=top-thickness
            layers.append({**{k:v for k,v in layer.items() if k!="thicknessM"},
              "topElevationM":top.tolist(),"bottomElevationM":bottom.tolist(),"thicknessM":thickness.tolist()})
            top=bottom
    else:
        raise ValueError("absolute-elevation provider composition is reserved for a later adapter")
    return signed_artifact({"schemaVersion":"TerrainLithologyComposition-1.0",
      "terrainArtifactSha256":terrain["artifactSha256"],"lithologyArtifactSha256":lithology["artifactSha256"],
      "stationsM":ls.tolist(),"terrainElevationM":np.interp(ls,ts,tz).tolist(),"layersTopDown":layers,
      "compositionMethod":"AnchorRelativeDepthStackBelowIndependentTerrain",
      "terrainModifiedByLithology":False,"lithologyGeneratorReceivedTerrain":False,
      "realRegionAuthorized":False})
