"""Joint predictive, conditioning and perturbation gate for structural surfaces."""
from __future__ import annotations
import numpy as np
from .rbf_structural_surface import RbfStructuralSurface
from .gaussian_ridge_surface import GaussianRidgeSurface


def _build(points,spec):
    if not isinstance(spec,dict) or set(spec)!={"modelId","family","shape","regularization"}:
        raise ValueError("invalid structural surface candidate")
    if not spec["modelId"]:raise ValueError("modelId required")
    if spec["family"]=="MultiquadricAffine":
        return RbfStructuralSurface(points,spec["shape"],spec["regularization"])
    if spec["family"]=="GaussianAffineRidge":
        return GaussianRidgeSurface(points,spec["shape"],spec["regularization"])
    raise ValueError("unknown structural surface family")


def evaluate_surface_candidates(observations_xyz,observation_sigma,query_xy,candidates,
                                perturbation_member_count,random_seed,gates):
    points=np.asarray(observations_xyz,dtype=float); query=np.asarray(query_xy,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or len(points)<5 or not np.isfinite(points).all():
        raise ValueError("at least five finite observations required")
    if query.ndim!=2 or query.shape[1]!=2 or len(query)==0 or not np.isfinite(query).all():
        raise ValueError("finite query grid required")
    if any(isinstance(v,bool) for v in observation_sigma):raise ValueError("positive sigma required")
    sigma=np.asarray(observation_sigma,dtype=float)
    if sigma.shape!=(len(points),) or not np.isfinite(sigma).all() or np.any(sigma<=0):raise ValueError("positive sigma required")
    if isinstance(perturbation_member_count,bool) or not isinstance(perturbation_member_count,int) or perturbation_member_count<5:
        raise ValueError("at least five perturbation members required")
    if isinstance(random_seed,bool) or not isinstance(random_seed,int) or random_seed<0:raise ValueError("valid seed required")
    required={"maximumLooStandardizedResidual","maximumConditionNumber","maximumEnvelopeWidthM"}
    if not isinstance(gates,dict) or set(gates)!=required:raise ValueError("exact gate policy required")
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or v<=0 for v in gates.values()):
        raise ValueError("positive finite gates required")
    if not isinstance(candidates,list) or not candidates:raise ValueError("candidate list required")
    rng=np.random.default_rng(random_seed)
    perturbations=rng.normal(0.0,sigma,size=(perturbation_member_count,len(points)))
    results=[]
    for spec in candidates:
        model=_build(points,spec)
        residuals=[]
        for index in range(len(points)):
            withheld=points[index]
            prediction=float(_build(np.delete(points,index,axis=0),spec).evaluate(withheld[None,:2])[0])
            residuals.append(prediction-withheld[2])
        residuals=np.asarray(residuals)
        standardized=np.abs(residuals/sigma)
        samples=[]
        for delta in perturbations:
            perturbed=points.copy();perturbed[:,2]+=delta
            samples.append(_build(perturbed,spec).evaluate(query))
        samples=np.vstack(samples)
        width=np.quantile(samples,.95,axis=0)-np.quantile(samples,.05,axis=0)
        metrics={"looRmseM":float(np.sqrt(np.mean(residuals**2))),
                 "maximumLooStandardizedResidual":float(np.max(standardized)),
                 "conditionNumber":model.condition_number,
                 "maximumEnvelopeWidthM":float(np.max(width))}
        checks={"loo":metrics["maximumLooStandardizedResidual"]<=gates["maximumLooStandardizedResidual"],
                "conditioning":metrics["conditionNumber"]<=gates["maximumConditionNumber"],
                "amplification":metrics["maximumEnvelopeWidthM"]<=gates["maximumEnvelopeWidthM"]}
        results.append({"candidate":dict(spec),"metrics":metrics,"checks":checks,"passed":all(checks.values())})
    passing=[r for r in results if r["passed"]]
    selected=min(passing,key=lambda r:(r["metrics"]["looRmseM"],r["metrics"]["conditionNumber"])) if passing else None
    return {"passed":selected is not None,"selectedModelId":selected["candidate"]["modelId"] if selected else None,
            "selected":selected,"candidates":results,"gates":dict(gates),
            "perturbationMemberCount":perturbation_member_count,"randomSeed":random_seed,
            "validationLayer":"JointNumericalSelection_NotGeologicalTruth"}
