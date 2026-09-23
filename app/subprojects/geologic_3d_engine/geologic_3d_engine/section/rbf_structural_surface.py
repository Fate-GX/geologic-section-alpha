"""Regularized RBF structural surface for non-overturned synthetic benchmarks.

One reference surface is fitted from XYZ contact observations. Conformable
contacts must be derived as offsets/thickness fields from this shared surface;
independent horizon fits are intentionally outside this contract.
"""
from __future__ import annotations

import numpy as np


class RbfStructuralSurface:
    def __init__(self, observations_xyz, shape_parameter, regularization=0.0):
        points = np.asarray(observations_xyz, dtype=float)
        if (points.ndim != 2 or points.shape[1] != 3 or len(points) < 3
                or not np.isfinite(points).all()):
            raise ValueError("at least three finite XYZ observations are required")
        if (isinstance(shape_parameter, bool) or not isinstance(shape_parameter, (int,float))
                or not np.isfinite(shape_parameter) or shape_parameter <= 0):
            raise ValueError("shape_parameter must be positive")
        if (isinstance(regularization, bool) or not isinstance(regularization, (int,float))
                or not np.isfinite(regularization) or regularization < 0):
            raise ValueError("regularization must be non-negative")
        if len(np.unique(points[:,:2], axis=0)) != len(points):
            raise ValueError("duplicate XY observations are ambiguous")
        xy, z = points[:,:2], points[:,2]
        scale = np.ptp(xy, axis=0)
        if np.any(scale == 0):
            raise ValueError("observations must span both horizontal axes")
        center = np.mean(xy, axis=0)
        normalized = (xy-center)/scale
        distance = np.linalg.norm(normalized[:,None,:]-normalized[None,:,:], axis=2)
        kernel = np.sqrt(distance*distance + shape_parameter*shape_parameter)
        kernel += regularization*np.eye(len(points))
        polynomial = np.column_stack((np.ones(len(points)), normalized))
        system = np.block([[kernel, polynomial], [polynomial.T, np.zeros((3,3))]])
        rhs = np.concatenate((z, np.zeros(3)))
        try:
            solution = np.linalg.solve(system, rhs)
        except np.linalg.LinAlgError as exc:
            raise ValueError("RBF structural system is singular") from exc
        self.xy = xy.copy(); self.xy.flags.writeable=False
        self.center=center; self.scale=scale
        self.shape_parameter=float(shape_parameter)
        self.weights=solution[:len(points)]
        self.polynomial=solution[len(points):]
        self.condition_number=float(np.linalg.cond(system))
        self.regularization=float(regularization)

    def evaluate(self, query_xy):
        query=np.asarray(query_xy,dtype=float)
        if query.ndim!=2 or query.shape[1]!=2 or not np.isfinite(query).all():
            raise ValueError("query must be finite N x 2")
        normalized=(query-self.center)/self.scale
        controls=(self.xy-self.center)/self.scale
        distance=np.linalg.norm(normalized[:,None,:]-controls[None,:,:],axis=2)
        kernel=np.sqrt(distance*distance+self.shape_parameter*self.shape_parameter)
        polynomial=np.column_stack((np.ones(len(query)),normalized))
        return kernel@self.weights+polynomial@self.polynomial

    def gradient(self, query_xy):
        """Return dz/dx,dz/dy of the fitted graph surface."""
        query=np.asarray(query_xy,dtype=float)
        if query.ndim!=2 or query.shape[1]!=2 or not np.isfinite(query).all():
            raise ValueError("query must be finite N x 2")
        normalized=(query-self.center)/self.scale
        controls=(self.xy-self.center)/self.scale
        delta=normalized[:,None,:]-controls[None,:,:]
        radius=np.sqrt(np.sum(delta*delta,axis=2)+self.shape_parameter**2)
        derivative=np.sum((delta/radius[:,:,None])*self.weights[None,:,None],axis=1)
        derivative+=self.polynomial[1:][None,:]
        return derivative/self.scale[None,:]

    def residuals(self, observed_xyz):
        observed=np.asarray(observed_xyz,dtype=float)
        if observed.ndim!=2 or observed.shape[1]!=3:
            raise ValueError("observed_xyz must be N x 3")
        return self.evaluate(observed[:,:2])-observed[:,2]

    def audit(self, observed_xyz, maximum_residual):
        residuals=self.residuals(observed_xyz)
        maximum=float(np.max(np.abs(residuals))) if len(residuals) else 0.0
        return {"maximumAbsoluteResidual":maximum,
                "rootMeanSquareResidual":float(np.sqrt(np.mean(residuals*residuals))),
                "conditionNumber":self.condition_number,
                "passed":maximum<=maximum_residual and np.isfinite(self.condition_number),
                "representation":"SharedReferenceSurface_NonOverturnedOnly"}
