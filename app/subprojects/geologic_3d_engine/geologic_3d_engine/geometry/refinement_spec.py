"""Stage-8 adaptive refinement and convergence contract."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RefinementSpec:
    refinement_factor:int=2
    maximum_refined_fraction:float=1.0
    volume_relative_tolerance:float=.25
    require_topology_stability:bool=False
    convergence_levels:int=2

    @classmethod
    def from_dict(cls,data):
        return cls(int(data.get("refinementFactor",2)),float(data.get("maximumRefinedFraction",1)),
                   float(data.get("volumeRelativeTolerance",.25)),
                   bool(data.get("requireTopologyStability",False)),
                   int(data.get("convergenceLevels",2)))

    def validate(self):
        if self.refinement_factor!=2: raise ValueError("refinementFactor must currently equal 2")
        if not 0<self.maximum_refined_fraction<=1: raise ValueError("maximumRefinedFraction must be in (0,1]")
        if self.volume_relative_tolerance<0: raise ValueError("volumeRelativeTolerance must be non-negative")
        if self.convergence_levels!=2: raise ValueError("convergenceLevels must currently equal 2")
        return self


def load_refinement_spec(path:str|Path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,dict): raise ValueError("refinement specification root must be an object")
    return RefinementSpec.from_dict(data)
