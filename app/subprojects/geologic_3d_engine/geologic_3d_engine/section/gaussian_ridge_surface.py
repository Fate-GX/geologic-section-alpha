"""Affine-trend Gaussian RBF surface with explicit ridge regularization."""
from __future__ import annotations
import numpy as np


class GaussianRidgeSurface:
    def __init__(self,observations_xyz,inverse_range,regularization):
        points=np.asarray(observations_xyz,dtype=float)
        if points.ndim!=2 or points.shape[1]!=3 or len(points)<3 or not np.isfinite(points).all():
            raise ValueError("at least three finite XYZ observations required")
        for value,name,allow_zero in ((inverse_range,"inverse_range",False),(regularization,"regularization",True)):
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or value<(0 if allow_zero else np.nextafter(0,1)):
                raise ValueError(f"invalid {name}")
        if len(np.unique(points[:,:2],axis=0))!=len(points):raise ValueError("duplicate XY observations")
        xy=points[:,:2]; self.center=xy.mean(axis=0); self.scale=np.ptp(xy,axis=0)
        if np.any(self.scale==0):raise ValueError("observations must span both axes")
        nxy=(xy-self.center)/self.scale
        distance=np.linalg.norm(nxy[:,None,:]-nxy[None,:,:],axis=2)
        kernel=np.exp(-(float(inverse_range)*distance)**2)
        polynomial=np.column_stack((np.ones(len(xy)),nxy))
        system=np.block([[kernel+float(regularization)*np.eye(len(xy)),polynomial],
                         [polynomial.T,np.zeros((3,3))]])
        rhs=np.concatenate((points[:,2],np.zeros(3)))
        try: solution=np.linalg.solve(system,rhs)
        except np.linalg.LinAlgError as exc:raise ValueError("Gaussian ridge system is singular") from exc
        self.xy=xy.copy();self.xy.flags.writeable=False
        self.weights=solution[:len(xy)];self.polynomial=solution[len(xy):]
        self.inverse_range=float(inverse_range);self.regularization=float(regularization)
        self.condition_number=float(np.linalg.cond(system))

    def evaluate(self,query_xy):
        query=np.asarray(query_xy,dtype=float)
        if query.ndim!=2 or query.shape[1]!=2 or not np.isfinite(query).all():raise ValueError("finite N x 2 query required")
        nq=(query-self.center)/self.scale; controls=(self.xy-self.center)/self.scale
        distance=np.linalg.norm(nq[:,None,:]-controls[None,:,:],axis=2)
        return np.exp(-(self.inverse_range*distance)**2)@self.weights+np.column_stack((np.ones(len(query)),nq))@self.polynomial

    def gradient(self,query_xy):
        query=np.asarray(query_xy,dtype=float)
        if query.ndim!=2 or query.shape[1]!=2 or not np.isfinite(query).all():raise ValueError("finite N x 2 query required")
        nq=(query-self.center)/self.scale; controls=(self.xy-self.center)/self.scale
        delta=nq[:,None,:]-controls[None,:,:]
        kernel=np.exp(-(self.inverse_range**2)*np.sum(delta*delta,axis=2))
        derivative=np.sum((-2*self.inverse_range**2*delta)*kernel[:,:,None]*self.weights[None,:,None],axis=1)
        derivative+=self.polynomial[1:][None,:]
        return derivative/self.scale[None,:]

    def residuals(self,observed_xyz):
        observed=np.asarray(observed_xyz,dtype=float)
        return self.evaluate(observed[:,:2])-observed[:,2]
