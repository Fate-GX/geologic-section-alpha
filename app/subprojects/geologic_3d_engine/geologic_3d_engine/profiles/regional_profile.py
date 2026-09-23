"""Strict regional-profile boundary; no regional conclusion enters universal code."""

from __future__ import annotations

import json,math
from dataclasses import dataclass
from pathlib import Path

STATUSES={"SyntheticTest","EvidenceBoundRegionalCandidate","AcceptedForSyntheticGeneration"}
CONTEXT_TYPES={"Province","Basin","Terrane","VolcanicField","EngineeringSite"}
ROLES={"Observed","Interpreted","SyntheticTest"}


@dataclass(frozen=True)
class RegionalProfile:
 data:dict
 def validate_against(self,config):
  d=self.data;errors=[]
  def required(name):
   if not isinstance(d.get(name),str) or not d[name].strip():errors.append({"code":"MissingField","field":name})
  for name in ("profileId","profileVersion","country","ageAuthority","ageVersion","syntheticDisclosure"):required(name)
  if d.get("profileId")!=config.regional_profile_id:errors.append({"code":"RegionalProfileIdMismatch"})
  if d.get("status") not in STATUSES:errors.append({"code":"InvalidProfileStatus"})
  context=d.get("geologicalContext",{})
  if context.get("type") not in CONTEXT_TYPES or not str(context.get("name","")).strip():
   errors.append({"code":"MissingGeologicalContext"})
  environments=d.get("environments")
  if not isinstance(environments,list) or not environments or any(not str(x).strip() for x in environments):
   errors.append({"code":"MissingEnvironment"})
  spatial=d.get("spatialApplicability",{});bbox=spatial.get("bbox")
  if spatial.get("horizontalCRS")!=config.coordinate_reference.horizontal_crs:
   errors.append({"code":"RegionalProfileCrsMismatch"})
  if not _bbox_valid(bbox):errors.append({"code":"InvalidRegionalBbox"})
  elif not _contains(bbox,config.extent.minimum,config.extent.maximum):errors.append({"code":"ModelExtentOutsideRegionalProfile"})
  age=d.get("ageRangeMa")
  if not isinstance(age,list) or len(age)!=2 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in age) or age[0]<0 or age[1]<age[0]:
   errors.append({"code":"InvalidAgeRangeMa"})
  source_ids={x.source_id for x in config.sources};declared=set(d.get("sourceIds",[]))
  if not declared:errors.append({"code":"NoRegionalSources"})
  for source in declared-source_ids:errors.append({"code":"UnknownRegionalSource","sourceId":source})
  errors.extend(_evidence_errors(d.get("unitEvidence"),{x.unit_id for x in config.units},declared,"unitId"))
  errors.extend(_evidence_errors(d.get("eventEvidence"),{x.event_id for x in config.events},declared,"eventId"))
  if not isinstance(d.get("exclusions"),list) or not d["exclusions"]:errors.append({"code":"MissingExclusions"})
  if not isinstance(d.get("unresolved"),list):errors.append({"code":"MissingUnresolvedList"})
  if "synthetic" not in str(d.get("syntheticDisclosure","")).lower() and "疑似" not in str(d.get("syntheticDisclosure","")):
   errors.append({"code":"MissingSyntheticDisclosure"})
  return {"passed":not errors,"gate":"RegionalApplicabilityAndEvidenceSufficiency","errors":errors,
          "profileId":d.get("profileId"),"scope":"Region"}


def load_regional_profile(path):
 data=json.loads(Path(path).read_text(encoding="utf-8"))
 if not isinstance(data,dict):raise ValueError("regional profile root must be an object")
 return RegionalProfile(data)


def _evidence_errors(records,expected,declared,id_key):
 errors=[]
 if not isinstance(records,list):return [{"code":"MissingEvidenceRecords","kind":id_key}]
 ids=[x.get(id_key) for x in records if isinstance(x,dict)]
 if set(ids)!=expected or len(ids)!=len(set(ids)):errors.append({"code":"EvidenceCoverageMismatch","kind":id_key})
 for item in records:
  if not isinstance(item,dict):continue
  refs=set(item.get("sourceIds",[]))
  if not refs or not refs<=declared:errors.append({"code":"InvalidEvidenceSourceBinding","id":item.get(id_key)})
  if item.get("evidenceRole") not in ROLES:errors.append({"code":"InvalidEvidenceRole","id":item.get(id_key)})
 return errors


def _bbox_valid(bbox):
 return (isinstance(bbox,list) and len(bbox)==6 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in bbox)
         and bbox[3]>bbox[0] and bbox[4]>bbox[1] and bbox[5]>bbox[2])
def _contains(bbox,minimum,maximum):
 return all(bbox[i]<=minimum[i] and maximum[i]<=bbox[i+3] for i in range(3))
