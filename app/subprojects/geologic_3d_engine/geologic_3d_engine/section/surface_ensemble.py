"""Deterministic observation-uncertainty ensemble for one shared RBF surface."""
from __future__ import annotations
import numpy as np
from .rbf_structural_surface import RbfStructuralSurface


class RbfSurfaceEnsemble:
    """Perturb observed Z within declared sigma and refit a shared surface.

    This is a parametric sensitivity ensemble, not a Bayesian posterior. Derived
    conformable contacts must reuse each member's shared reference surface.
    """
    def __init__(self,observations_xyz,observation_sigma,shape_parameter,
                 member_count,random_seed,regularization=0.0):
        points=np.asarray(observations_xyz,dtype=float)
        if points.ndim!=2 or points.shape[1]!=3 or len(points)<5 or not np.isfinite(points).all():
            raise ValueError("at least five finite XYZ observations are required")
        if any(isinstance(v,bool) for v in observation_sigma):
            raise ValueError("positive observation sigma required")
        sigma=np.asarray(observation_sigma,dtype=float)
        if sigma.shape!=(len(points),) or not np.isfinite(sigma).all() or np.any(sigma<=0):
            raise ValueError("positive observation sigma required")
        if isinstance(member_count,bool) or not isinstance(member_count,int) or member_count<3:
            raise ValueError("at least three ensemble members required")
        if isinstance(random_seed,bool) or not isinstance(random_seed,int) or random_seed<0:
            raise ValueError("non-negative integer seed required")
        rng=np.random.default_rng(random_seed)
        perturbations=rng.normal(0.0,sigma,size=(member_count,len(points)))
        self.members=[]
        for delta in perturbations:
            member_points=points.copy(); member_points[:,2]+=delta
            self.members.append(RbfStructuralSurface(member_points,shape_parameter,regularization))
        self.observations=points.copy(); self.observations.flags.writeable=False
        self.sigma=sigma.copy(); self.sigma.flags.writeable=False
        self.perturbations=perturbations.copy(); self.perturbations.flags.writeable=False
        self.random_seed=random_seed

    def evaluate(self,query_xy,quantiles=(0.05,0.5,0.95)):
        if any(isinstance(q,bool) for q in quantiles): raise ValueError("valid quantiles required")
        q=np.asarray(quantiles,dtype=float)
        if q.ndim!=1 or len(q)==0 or not np.isfinite(q).all() or np.any(q<0) or np.any(q>1) or np.any(np.diff(q)<0):
            raise ValueError("valid ordered quantiles required")
        samples=np.vstack([member.evaluate(query_xy) for member in self.members])
        values=np.quantile(samples,q,axis=0)
        return {"quantiles":q.tolist(),"values":values,"samples":samples,
                "memberCount":len(self.members),
                "uncertaintyMeaning":"ObservationZPerturbationSensitivity_NotPosterior"}

    def audit(self):
        empirical=np.std(self.perturbations,axis=0,ddof=1)
        return {"memberCount":len(self.members),"randomSeed":self.random_seed,
                "declaredSigma":self.sigma.tolist(),"empiricalPerturbationSigma":empirical.tolist(),
                "sharedSurfacePerMember":True,
                "validationLayer":"ParametricSensitivity_NotGeologicalTruth"}
