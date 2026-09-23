"""Explicit synthetic incision geometry; not a river evolution simulator.

Contract: docs/channel_geometry_review.md / CHANNEL-GEOMETRY-001.
No imported OSS geological solver and no regional evidence authorization.
"""
import numpy as np

from ..stratigraphy.conformable_stack import build_conformable_stack
from .stratigraphic_events import (from_conformable_stack, apply_erosion,
                                  build_deposit_on_surface)


def make_synthetic_spec(seed=3701):
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be an unsigned 32-bit integer")
    rng = np.random.default_rng(seed)
    anchors_x = np.linspace(-200,1400,9)
    anchors_y = np.array([400,220,590,230,560,250,570,280,400],dtype=float)
    anchors_y += rng.uniform(-30,30,len(anchors_y))
    gradients = np.gradient(anchors_y,anchors_x)
    path = []
    for k in range(len(anchors_x)-1):
        for t in np.linspace(0,1,20,endpoint=False):
            span = anchors_x[k+1]-anchors_x[k]
            y = ((2*t**3-3*t**2+1)*anchors_y[k]
                 +(t**3-2*t**2+t)*span*gradients[k]
                 +(-2*t**3+3*t**2)*anchors_y[k+1]
                 +(t**3-t**2)*span*gradients[k+1])
            path.append([float(anchors_x[k]+t*span),float(y)])
    path.append([float(anchors_x[-1]),float(anchors_y[-1])])
    return {"basis":"SyntheticAssumption","region":None,"realRegionAuthorized":False,
            "seed":seed,"centerlineXY":path,"halfWidth":60.,"depth":30.,
            "topElevation":80.,"hostBoundary":60.,"lowerFillFraction":.4}


class ChannelGeometry:
    def __init__(self, spec):
        keys = {"basis","region","realRegionAuthorized","seed","centerlineXY",
                "halfWidth","depth","topElevation","hostBoundary","lowerFillFraction"}
        if not isinstance(spec,dict) or set(spec)!=keys:
            raise ValueError("Missing or unknown channel specification keys")
        if spec["basis"]!="SyntheticAssumption" or spec["region"] is not None or spec["realRegionAuthorized"] is not False:
            raise ValueError("Only uncalibrated synthetic, region-free geometry is supported")
        if type(spec["seed"]) is not int or not 0<=spec["seed"]<2**32:
            raise ValueError("Invalid provenance seed")
        path = np.asarray(spec["centerlineXY"])
        if (path.ndim!=2 or path.shape[1]!=2 or not 2<=len(path)<=1000
                or path.dtype.kind not in "iuf" or not np.isfinite(path).all()
                or np.any(np.diff(path[:,0])<=0)):
            raise ValueError("Finite increasing-X polyline with 2..1000 vertices required")
        for key in ("halfWidth","depth","topElevation","hostBoundary","lowerFillFraction"):
            value = spec[key]
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or value<=0:
                raise ValueError("Invalid positive finite parameter: "+key)
        if spec["depth"]>=spec["topElevation"] or spec["hostBoundary"]>=spec["topElevation"] or spec["lowerFillFraction"]>=1:
            raise ValueError("Conflicting depth/host/fraction parameters")
        self.path = path.astype(float,copy=True)
        self.path.flags.writeable = False
        self.half_width = float(spec["halfWidth"])
        self.depth = float(spec["depth"])
        self.top = float(spec["topElevation"])
        self.host_boundary = float(spec["hostBoundary"])
        self.fraction = float(spec["lowerFillFraction"])

    def surfaces(self, xy):
        xy = np.asarray(xy,dtype=float)
        if xy.ndim!=2 or xy.shape[1]!=2 or len(xy)>1_000_000 or not np.isfinite(xy).all():
            raise ValueError("Finite N x 2 query required; N <= 1000000")
        squared = np.full(len(xy),np.inf)
        for start,end in zip(self.path[:-1],self.path[1:]):
            direction = end-start
            difference = xy-start
            t = np.clip(np.sum(difference*direction,axis=1)/np.dot(direction,direction),0,1)
            offset = difference-t[:,None]*direction
            squared = np.minimum(squared,np.sum(offset**2,axis=1))
        incision = self.depth*np.maximum(0,1-squared/self.half_width**2)
        bed = self.top-incision
        split = bed+self.fraction*incision
        return {"distance":np.sqrt(squared),"incision":incision,"bed":bed,"split":split}

    def classify(self, xyz):
        xyz = np.asarray(xyz,dtype=float)
        if xyz.ndim!=2 or xyz.shape[1]!=3 or len(xyz)>2_000_000 or not np.isfinite(xyz).all():
            raise ValueError("Finite N x 3 query required; N <= 2000000")
        xy,inverse = np.unique(xyz[:,:2],axis=0,return_inverse=True)
        s = self.surfaces(xy)
        bed,split = s["bed"][inverse],s["split"][inverse]
        z = xyz[:,2]
        occupied = (z>0)&(z<=self.top)
        result = np.where(z<=self.host_boundary,1,2).astype(np.uint8)
        fill = occupied&(z>bed)
        result[fill] = np.where(z[fill]<=split[fill],3,4)
        result[~occupied] = 0
        return result

    def build_engine_model(self, grid):
        if grid.minimum[2]!=0 or grid.maximum[2]<self.top:
            raise ValueError("Engine grid must start at zero and contain the host top")
        x = [grid.x_center(i) for i in range(grid.nx)]
        y = [grid.y_center(i) for i in range(grid.ny)]
        xx,yy = np.meshgrid(x,y)
        s = self.surfaces(np.column_stack((xx.ravel(),yy.ravel())))
        shape = (grid.ny,grid.nx)
        full = lambda v: np.full(shape,v).tolist()
        stack = build_conformable_stack(grid,full(self.top),["HOST_UPPER","HOST_LOWER"],
                  [full(self.top-self.host_boundary),full(self.host_boundary)])
        eroded = apply_erosion(from_conformable_stack(stack),s["bed"].reshape(shape).tolist(),"SYNTHETIC_INCISION")
        lower = build_deposit_on_surface(eroded,"FILL_LOWER",
                   (self.fraction*s["incision"]).reshape(shape).tolist(),"LOWER_FILL","ErosionFill")
        upper = build_deposit_on_surface(lower,"FILL_UPPER",
                   ((1-self.fraction)*s["incision"]).reshape(shape).tolist(),"UPPER_FILL","Onlap")
        return upper
