"""Evidence-gated vertical-throw fault operation for section contacts."""
import copy,math
from typing import Mapping
import numpy as np

def apply_vertical_throw(section: Mapping,fault_event: Mapping,fault_evidence: Mapping):
    required={"faultId","verticalThrowM","downthrownRouteSide","affectedContactIndices",
              "sourceId","evidenceStatus","uncertaintyM"}
    if not isinstance(fault_evidence,Mapping) or set(fault_evidence)!=required:raise ValueError("vertical-throw evidence is incomplete")
    if fault_event.get("kind")!="Fault" or fault_event.get("featureId")!=fault_evidence["faultId"]:raise ValueError("fault event and evidence identity mismatch")
    if fault_evidence["sourceId"]!=fault_event.get("sourceId"):raise ValueError("fault event and displacement source mismatch")
    if fault_evidence["evidenceStatus"] not in {"Observed","Literature"}:raise ValueError("fault displacement requires observed or literature evidence")
    throw=fault_evidence["verticalThrowM"];uncertainty=fault_evidence["uncertaintyM"]
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (throw,uncertainty)) or throw<=0 or uncertainty<0:raise ValueError("throw must be positive and uncertainty non-negative")
    side=fault_evidence["downthrownRouteSide"]
    if side not in {"BeforeIntersection","AfterIntersection"}:raise ValueError("invalid downthrown route side")
    contacts=[np.asarray(v,float).copy() for v in section["contactElevationsM"]];indices=fault_evidence["affectedContactIndices"]
    if not isinstance(indices,list) or not indices or len(set(indices))!=len(indices) or any(isinstance(i,bool) or not isinstance(i,int) or i<0 or i>=len(contacts) for i in indices):raise ValueError("affected contact indices are invalid")
    stations=np.asarray(section["stationsM"],float);crossing=float(fault_event["stationM"])
    selected=stations<crossing if side=="BeforeIntersection" else stations>crossing
    for index in indices:contacts[index][selected]-=throw
    if any(np.any(upper<lower-1e-9) for lower,upper in zip(contacts[:-1],contacts[1:])):raise ValueError("fault operation reverses stratigraphic order")
    result=copy.deepcopy(section);result["contactElevationsM"]=[v.tolist() for v in contacts]
    result["activeMasks"]=[(contacts[i+1]>contacts[i]+1e-9).tolist() for i in range(len(contacts)-1)]
    result.setdefault("faultOperations",[]).append({"faultId":fault_evidence["faultId"],"stationM":crossing,
      "verticalThrowM":float(throw),"uncertaintyM":float(uncertainty),"downthrownRouteSide":side,
      "affectedContactIndices":indices,"sourceId":fault_evidence["sourceId"],
      "kinematicScope":"VerticalThrowComparator_NotGeneralSlipOrBalancedRestoration"})
    result["realRegionAuthorized"]=False
    return result
