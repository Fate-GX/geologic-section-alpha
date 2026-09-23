"""Fail-closed checks for reusable domain-model geological common sense.

The gate validates internal consistency and model semantics.  Passing it does
not establish that the synthetic subsurface is locally true.
"""
from __future__ import annotations
import math
import numpy as np

COMPATIBLE={
 "VolcanicTerrain":{"VolcanicPaleosurfaceStack"},
 "SedimentaryRockTerrain":{"DeformedSedimentaryStack"},
 "AccretionaryComplex":{"DeformedSedimentaryStack"},
 "MetamorphicBelt":{"DeformedSedimentaryStack"},
 "PlutonicTerrain":{"PlutonicWeatheringMass"}}

def audit_domain_model_realism(model):
    errors=[];classification=model.get("planGeologicalDomainClassification",{})
    domain=classification.get("geologicalDomain");composition=model.get("composition",{})
    architecture=composition.get("backgroundArchitecture",{});kind=architecture.get("type")
    if domain in COMPATIBLE and kind not in COMPATIBLE[domain]:
        errors.append("DomainArchitectureMismatch")
    layers=composition.get("layersTopDown",[]);x=np.asarray(model.get("stationsM",[]),float)
    if domain in COMPATIBLE and len(layers)<5:errors.append("InsufficientDomainLithologyStates")
    if x.size<2 or not np.isfinite(x).all() or np.any(np.diff(x)<=0):
        errors.append("InvalidStationsForDomainAudit")
    maximum_gradient=0.0
    if not errors and x.size>=2:
        for index,layer in enumerate(layers[:-1]):
            z=np.asarray(layer.get("bottomElevationM",[]),float)
            if z.shape!=x.shape or not np.isfinite(z).all():
                errors.append(f"InvalidContact:{index}");continue
            gradient=float(np.max(np.abs(np.diff(z)/np.diff(x))))
            maximum_gradient=max(maximum_gradient,gradient)
            if gradient>3.0:errors.append(f"NearVerticalUnexplainedContact:{index}")
    events=model.get("syntheticEventArchitecture",{}).get("eventLog",[])
    local_types={"Erosion","StratifiedErosionFill","Fault","Fold","Intrusion","Lens"}
    localized=sorted({row.get("eventType") for row in events}&local_types)
    decision=model.get("geologicalPriorDecision",{})
    if localized and not decision.get("localizedEventsAuthorized",False):
        errors.append("LocalizedEventWithoutRouteApplicableEvidence")
    if kind=="PlutonicWeatheringMass" and architecture.get("weatheringRepresentation")!=\
            "GradedParentRockState_NotStratigraphicBeds":
        errors.append("PlutonicStateFrontsMisrepresentedAsBeds")
    return {"passed":not errors,"errors":errors,"gate":"DomainModelGeologicalCommonSense",
      "classifiedDomain":domain,"architectureType":kind,"lithologyStateCount":len(layers),
      "maximumAbsoluteContactGradient":maximum_gradient,
      "localizedEventTypes":localized,"localTruthEstablished":False,
      "meaning":"Internal plausibility only; not validation of unobserved local geology"}
