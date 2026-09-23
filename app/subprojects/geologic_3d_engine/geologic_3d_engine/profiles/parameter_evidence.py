"""Typed evidence bindings for geometry-affecting numeric parameters."""

from __future__ import annotations

import math

BASIS_TYPES={"Observed","Literature","ProjectNumerical","SyntheticAssumption"}
VALUE_KINDS={"Scalar","Range","Distribution","NumericField"}
SCOPES={"Global","Domain","Environment","Region","DatasetSpecific"}


def validate_parameter_evidence(requirements,bindings,declared_source_ids,profile_id):
 errors=[]
 required={}
 for item in requirements:
  parameter_id=item.get("parameterId")
  if not parameter_id or parameter_id in required:
   errors.append({"code":"InvalidOrDuplicateParameterRequirement","parameterId":parameter_id});continue
  if not item.get("implementationPath") or not item.get("unit") or not item.get("dimension"):
   errors.append({"code":"IncompleteParameterRequirement","parameterId":parameter_id})
  if item.get("geometryAffecting") is True:required[parameter_id]=item
 by_id={}
 for item in bindings:
  by_id.setdefault(item.get("parameterId"),[]).append(item)
 for parameter_id,requirement in required.items():
  found=by_id.get(parameter_id,[])
  if len(found)!=1:
   errors.append({"code":"ParameterEvidenceCoverageMismatch","parameterId":parameter_id,"count":len(found)});continue
  item=found[0]
  if item.get("implementationPath")!=requirement.get("implementationPath"):
   errors.append({"code":"ParameterImplementationPathMismatch","parameterId":parameter_id})
  if item.get("unit")!=requirement.get("unit") or item.get("dimension")!=requirement.get("dimension"):
   errors.append({"code":"ParameterUnitOrDimensionMismatch","parameterId":parameter_id})
  if item.get("profileId")!=profile_id:errors.append({"code":"ParameterProfileMismatch","parameterId":parameter_id})
  if item.get("basisType") not in BASIS_TYPES:errors.append({"code":"InvalidParameterBasisType","parameterId":parameter_id})
  if item.get("valueKind") not in VALUE_KINDS:errors.append({"code":"InvalidParameterValueKind","parameterId":parameter_id})
  if item.get("scope") not in SCOPES:errors.append({"code":"InvalidParameterScope","parameterId":parameter_id})
  refs=set(item.get("sourceIds",[]))
  if not refs or not refs<=set(declared_source_ids):errors.append({"code":"InvalidParameterSourceBinding","parameterId":parameter_id})
  if not _value_contract_valid(item):errors.append({"code":"InvalidParameterValueContract","parameterId":parameter_id})
  if not isinstance(item.get("uncertainty"),dict) or not item["uncertainty"].get("semantics"):
   errors.append({"code":"MissingParameterUncertainty","parameterId":parameter_id})
  if not isinstance(item.get("applicability"),dict) or not item["applicability"].get("statement"):
   errors.append({"code":"MissingParameterApplicability","parameterId":parameter_id})
  if not isinstance(item.get("exclusions"),list) or not item["exclusions"]:
   errors.append({"code":"MissingParameterExclusions","parameterId":parameter_id})
 for parameter_id in set(by_id)-set(required):
  errors.append({"code":"UnexpectedParameterEvidence","parameterId":parameter_id,
                 "recordCount":len(by_id[parameter_id])})
 return {"passed":not errors,"gate":"GeometryParameterEvidenceBinding","errors":errors,
   "requiredParameterCount":len(required),"boundParameterCount":sum(len(by_id.get(x,[]))==1 for x in required)}


def _value_contract_valid(item):
 kind=item.get("valueKind")
 if kind=="Scalar":return _finite(item.get("value"))
 if kind=="Range":
  value=item.get("range");return isinstance(value,list) and len(value)==2 and all(_finite(x) for x in value) and value[1]>=value[0]
 if kind=="Distribution":return isinstance(item.get("distribution"),dict) and bool(item["distribution"].get("family"))
 if kind=="NumericField":return isinstance(item.get("fieldReference"),str) and bool(item["fieldReference"])
 return False
def _finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
