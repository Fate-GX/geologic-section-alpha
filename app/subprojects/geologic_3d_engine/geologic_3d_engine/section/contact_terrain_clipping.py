"""Clip diagnostic contact hypotheses against a piecewise-linear DEM profile."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def _terrain_nodes(profile):
    if not isinstance(profile, Sequence) or isinstance(profile, (str, bytes)) or len(profile)<2:
        raise ValueError("at least two terrain samples are required")
    nodes=[]
    for row in profile:
        if not isinstance(row,Mapping):raise ValueError("terrain sample must be an object")
        s,z=row.get("stationM"),row.get("elevationM")
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)
               for v in (s,z)):
            raise ValueError("terrain station/elevation must be finite")
        nodes.append((float(s),float(z)))
    if any(b[0]<=a[0] for a,b in zip(nodes,nodes[1:])):
        raise ValueError("terrain stations must be strictly increasing")
    return nodes


def _interpolate(nodes, station):
    if station<nodes[0][0] or station>nodes[-1][0]:
        raise ValueError("contact support lies outside terrain coverage")
    if station==nodes[-1][0]:return nodes[-1][1]
    for a,b in zip(nodes,nodes[1:]):
        if a[0]<=station<=b[0]:
            t=(station-a[0])/(b[0]-a[0])
            return a[1]+t*(b[1]-a[1])
    raise AssertionError("covered station was not interpolated")


def _merge_segments(segments,tolerance):
    merged=[]
    for segment in segments:
        if merged and abs(merged[-1][-1][0]-segment[0][0])<=tolerance:
            merged[-1].extend(segment[1:])
        else:merged.append(list(segment))
    return merged


def clip_contact_hypotheses_below_terrain(evaluation: Mapping, terrain_profile,
                                           *, elevation_tolerance_m=1e-8):
    if evaluation.get("schemaVersion")!="ContactOrientationHypothesisEvaluation-1.0":
        raise ValueError("contact-orientation evaluation is required")
    if (isinstance(elevation_tolerance_m,bool) or
            not isinstance(elevation_tolerance_m,(int,float)) or
            not math.isfinite(elevation_tolerance_m) or elevation_tolerance_m<0):
        raise ValueError("elevation tolerance must be finite and non-negative")
    terrain=_terrain_nodes(terrain_profile);outputs=[]
    for row in evaluation.get("hypotheses",[]):
        support=row.get("supportIntervalM");endpoints=row.get("candidateEndpointsStationElevation")
        slopes=row.get("elevationSlopeRangePerStation")
        if (not isinstance(support,list) or len(support)!=2 or
                not isinstance(endpoints,list) or len(endpoints)!=2 or
                not isinstance(slopes,list) or len(slopes)!=2):
            raise ValueError("evaluated contact is incomplete")
        left,right=map(float,support)
        if not left<right:raise ValueError("contact support interval is invalid")
        anchor=(left+right)/2
        nominal_slope=float(row["elevationSlopePerStation"])
        anchor_z=float(endpoints[0][1])+nominal_slope*(anchor-float(endpoints[0][0]))
        stations=[left]+[s for s,_ in terrain if left<s<right]+[right]
        samples=[]
        for station in stations:
            terrain_z=_interpolate(terrain,station)
            dz=station-anchor
            nominal=anchor_z+nominal_slope*dz
            envelope=sorted((anchor_z+float(slopes[0])*dz,
                             anchor_z+float(slopes[1])*dz))
            if envelope[1]<=terrain_z+elevation_tolerance_m:
                certainty="DefinitelyBelowOrOnTerrain"
            elif envelope[0]<=terrain_z+elevation_tolerance_m:
                certainty="PossiblyBelowTerrain"
            else:certainty="DefinitelyAboveTerrain"
            samples.append({"stationM":station,"terrainElevationM":terrain_z,
                "nominalContactElevationM":nominal,
                "minimumContactElevationM":envelope[0],
                "maximumContactElevationM":envelope[1],"certainty":certainty})
        nominal_segments=[]
        for a,b in zip(samples,samples[1:]):
            da=a["nominalContactElevationM"]-a["terrainElevationM"]
            db=b["nominalContactElevationM"]-b["terrainElevationM"]
            if abs(da)<=elevation_tolerance_m:da=0.0
            if abs(db)<=elevation_tolerance_m:db=0.0
            a_below=da<=0;b_below=db<=0
            if a_below and b_below:
                nominal_segments.append([[a["stationM"],a["nominalContactElevationM"]],
                                         [b["stationM"],b["nominalContactElevationM"]]])
            elif a_below!=b_below:
                # Both terrain and contact are affine inside this interval, so
                # their difference has an exact linear root.
                fraction=-da/(db-da)
                fraction=max(0.0,min(1.0,fraction))
                station=a["stationM"]+fraction*(b["stationM"]-a["stationM"])
                contact=a["nominalContactElevationM"]+fraction*(
                    b["nominalContactElevationM"]-a["nominalContactElevationM"])
                root=[station,contact]
                nominal_segments.append(([[a["stationM"],a["nominalContactElevationM"]],root]
                                         if a_below else [root,[b["stationM"],b["nominalContactElevationM"]]]))
        merged=_merge_segments(nominal_segments,1e-9)
        outputs.append({"hypothesisId":row.get("hypothesisId"),
            "supportIntervalM":[left,right],"samples":samples,
            "nominalSubsurfaceSegments":merged,
            "nominalSubsurfaceSegmentCount":len(merged),
            "aboveTerrainGeometryDiscarded":True,
            "subsurfaceContinuationAuthorized":False})
    return {"schemaVersion":"ContactTerrainClipping-1.0","contactCount":len(outputs),
        "contacts":outputs,"elevationToleranceM":float(elevation_tolerance_m),
        "realRegionAuthorized":False,
        "authorizationBoundary":"TerrainClippingOfDiagnosticCandidates_NotSectionAuthorization"}
