"""Project structural observations to a bent route and audit apparent dip."""
import math
from typing import Mapping,Sequence

import numpy as np

from .map_template import MeasuredRoute2D,apparent_dip_degrees


def _local_route(route):
    if not isinstance(route,Sequence) or len(route)<2:raise ValueError("route requires at least two vertices")
    lat0=sum(float(p[1]) for p in route)/len(route)
    sx=6378137*math.cos(math.radians(lat0))*math.pi/180;sy=6378137*math.pi/180
    xy=[[float(p[0])*sx,float(p[1])*sy] for p in route]
    return MeasuredRoute2D(xy),sx,sy


def _azimuth(a,b):
    east=b[0]-a[0];north=b[1]-a[1]
    return math.degrees(math.atan2(east,north))%360


def project_structural_observations(observations,route,maximum_offset_m):
    if isinstance(maximum_offset_m,bool) or not isinstance(maximum_offset_m,(int,float)) or not math.isfinite(maximum_offset_m) or maximum_offset_m<0:
        raise ValueError("maximum offset must be a finite non-negative number")
    measured,sx,sy=_local_route(route);output=[]
    required={"observationId","longitude","latitude","trueDipDegrees","dipDirectionDegrees",
              "sourceId","sourceUrl","locationMethod","scientificConfidence","locationalConfidence"}
    for item in observations:
        if not isinstance(item,Mapping) or not required.issubset(item):raise ValueError("structural observation is incomplete")
        numeric=[item[k] for k in ("longitude","latitude","trueDipDegrees","dipDirectionDegrees")]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in numeric):raise ValueError("orientation values must be finite numbers")
        if not -180<=item["longitude"]<=180 or not -90<=item["latitude"]<=90:raise ValueError("observation longitude/latitude are invalid")
        if not 0<=item["trueDipDegrees"]<=90:raise ValueError("true dip must be in [0,90]")
        text_fields=("observationId","sourceId","sourceUrl","locationMethod",
                     "scientificConfidence","locationalConfidence")
        if not all(isinstance(item[k],str) and item[k].strip() for k in text_fields):
            raise ValueError("structural observation identity and provenance are required")
        point=[item["longitude"]*sx,item["latitude"]*sy];projected=measured.project([point]);segment=int(projected["routeSegmentIndex"][0])
        section_azimuth=_azimuth(measured.vertices[segment],measured.vertices[segment+1])
        distance=float(projected["projectionDistance"][0])
        row={"observationId":item["observationId"],"sourceId":item["sourceId"],"sourceUrl":item["sourceUrl"],
          "sourceLonLat":[float(item["longitude"]),float(item["latitude"])],"locationMethod":item["locationMethod"],
          "scientificConfidence":item["scientificConfidence"],"locationalConfidence":item["locationalConfidence"],
          "stationM":float(projected["station"][0]),"projectionDistanceM":distance,"routeSegmentIndex":segment,
          "sectionAzimuthDegrees":section_azimuth,"trueDipDegrees":float(item["trueDipDegrees"]),
          "dipDirectionDegrees":float(item["dipDirectionDegrees"]),
          "apparentDipDegrees":apparent_dip_degrees(item["trueDipDegrees"],item["dipDirectionDegrees"],section_azimuth),
          "projectionState":"Projected" if distance<=maximum_offset_m else "Rejected"}
        for optional in ("appliesToFeatureIds","unitPair","angularUncertaintyDegrees",
                         "lateralSupportM","measurementMethod","observationDate"):
            if optional in item:row[optional]=item[optional]
        output.append(row)
    return output


def audit_section_apparent_dips(section,projected_observations,contact_index=0,maximum_residual_degrees=15):
    if isinstance(contact_index,bool) or not isinstance(contact_index,int):raise ValueError("contact index must be an integer")
    stations=np.asarray(section["stationsM"],float);contacts=section["contactElevationsM"]
    if contact_index<0 or contact_index>=len(contacts):raise ValueError("contact index is invalid")
    if len(stations)<3:raise ValueError("at least three section samples are required")
    surface=np.asarray(contacts[contact_index],float);slope=np.gradient(surface,stations)
    rows=[]
    for item in projected_observations:
        if item.get("projectionState")!="Projected":continue
        index=int(np.argmin(np.abs(stations-item["stationM"])))
        modeled=math.degrees(math.atan(float(slope[index])))
        residual=((modeled-item["apparentDipDegrees"]+180)%360)-180
        rows.append({"observationId":item["observationId"],"stationM":item["stationM"],
          "sampleStationM":float(stations[index]),"observedApparentDipDegrees":item["apparentDipDegrees"],
          "modeledDipDegrees":modeled,"signedResidualDegrees":residual,
          "passed":abs(residual)<=maximum_residual_degrees,"sourceId":item["sourceId"]})
    return {"contactIndex":contact_index,"maximumResidualDegrees":maximum_residual_degrees,
      "observationCount":len(rows),"passed":bool(rows) and all(v["passed"] for v in rows),"residuals":rows,
      "validationBoundary":"CompatibilityAudit_NotOrientationConstrainedInterpolation"}
