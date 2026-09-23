"""Observation-level cross-validation diagnostics for structural surfaces."""
from __future__ import annotations
import numpy as np
from .rbf_structural_surface import RbfStructuralSurface


def leave_one_out_rbf(observations_xyz,shape_parameter,regularization=0.0,
                      observation_sigma=None,maximum_standardized_residual=3.0):
    points=np.asarray(observations_xyz,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or len(points)<5 or not np.isfinite(points).all():
        raise ValueError("at least five finite XYZ observations are required")
    if (isinstance(maximum_standardized_residual,bool)
            or not isinstance(maximum_standardized_residual,(int,float))
            or not np.isfinite(maximum_standardized_residual)
            or maximum_standardized_residual<=0):
        raise ValueError("positive standardized residual limit required")
    if observation_sigma is None:
        sigma=np.ones(len(points),dtype=float); sigma_declared=False
    else:
        if any(isinstance(value,bool) for value in observation_sigma):
            raise ValueError("one positive uncertainty value per observation required")
        sigma=np.asarray(observation_sigma,dtype=float)
        if sigma.shape!=(len(points),) or not np.isfinite(sigma).all() or np.any(sigma<=0):
            raise ValueError("one positive uncertainty value per observation required")
        sigma_declared=True
    records=[]
    for i in range(len(points)):
        prediction=float(RbfStructuralSurface(np.delete(points,i,axis=0),shape_parameter,regularization)
                         .evaluate(points[i:i+1,:2])[0])
        residual=prediction-float(points[i,2])
        records.append({"observationIndex":i,"xy":points[i,:2].tolist(),
                        "observedElevation":float(points[i,2]),"predictedElevation":prediction,
                        "residual":residual,"absoluteResidual":abs(residual),
                        "declaredSigma":float(sigma[i]),"standardizedResidual":residual/float(sigma[i])})
    absolute=np.array([r["absoluteResidual"] for r in records])
    standardized=np.abs([r["standardizedResidual"] for r in records])
    return {"passed":bool(np.max(standardized)<=maximum_standardized_residual),
            "records":records,"observationCount":len(records),
            "rootMeanSquareResidual":float(np.sqrt(np.mean(absolute**2))),
            "maximumAbsoluteResidual":float(np.max(absolute)),
            "maximumAbsoluteStandardizedResidual":float(np.max(standardized)),
            "uncertaintyMode":"DeclaredObservationSigma" if sigma_declared else "UnitSigmaDiagnosticOnly",
            "validationLayer":"LeaveOneOutPredictiveDiagnostic_NotGeologicalTruth"}
