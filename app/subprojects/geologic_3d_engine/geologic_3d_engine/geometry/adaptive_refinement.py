"""Risk-driven subcell resampling and topology-safe material partition audit."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

from ..events.intrusion_3d import point_inside_intrusion
from ..geometry.regular_grid import RegularGrid3D
from ..physics.structural_3d import transform_point
from .voxel_brep import build_closed_breps
from .voxel_topology_audit import audit_label_grid


@dataclass(frozen=True)
class AdaptivePartitionModel:
    leaves: tuple[dict, ...]
    fine_labels_zyx: list
    fine_grid: RegularGrid3D
    refined_brep: object
    validation: dict

    def to_dict(self):
        return {"leaves":list(self.leaves),"fineLabelsZYX":self.fine_labels_zyx,
                "fineGrid":self.fine_grid.to_dict(),
                "refinedBrep":None if self.refined_brep is None else self.refined_brep.to_dict(),
                "validation":self.validation,"representation":"AdaptiveLeavesWithConformingAuditGrid"}


def refine_partition(intrusion_model, factor=2, maximum_refined_fraction=1.0,
                     volume_relative_tolerance=0.25, require_topology_stability=False,
                     convergence_levels=2):
    if factor != 2:
        raise ValueError("Stage 8 currently supports refinementFactor 2 only")
    if convergence_levels != 2:
        raise ValueError("Stage 8 currently requires exactly two convergence levels")
    grid=intrusion_model.source_model.source_model.grid; coarse=intrusion_model.labels_zyx
    risk=_risk_cells(coarse,grid)
    fraction=len(risk)/(grid.nx*grid.ny*grid.nz)
    if fraction>maximum_refined_fraction:
        raise ValueError("refined-cell fraction exceeds declared maximum")
    previous_grid,previous,_=_resample(risk,intrusion_model,factor)
    final_factor=factor**convergence_levels
    fine_grid,fine,leaves=_resample(risk,intrusion_model,final_factor)
    units=sorted({v for layer in fine for row in layer for v in row if v is not None})
    topology_preflight=audit_label_grid(fine,units)
    coarse_counts=_counts(coarse); previous_counts=_counts(previous); fine_counts=_counts(fine)
    coarse_vol={k:v*grid.cell_volume for k,v in coarse_counts.items()}
    fine_vol={k:v*fine_grid.cell_volume for k,v in fine_counts.items()}
    previous_vol={k:v*previous_grid.cell_volume for k,v in previous_counts.items()}
    coarse_changes={k:abs(fine_vol.get(k,0)-coarse_vol.get(k,0))/max(coarse_vol.get(k,0),fine_grid.cell_volume)
                    for k in set(coarse_vol)|set(fine_vol)}
    changes={k:abs(fine_vol.get(k,0)-previous_vol.get(k,0))/max(previous_vol.get(k,0),fine_grid.cell_volume)
             for k in set(previous_vol)|set(fine_vol)}
    coarse_sig=_topology_signature(coarse); previous_sig=_topology_signature(previous); fine_sig=_topology_signature(fine)
    coverage=sum((fine_grid.cell_volume if leaf["level"]==1 else grid.cell_volume)
                 for leaf in leaves)
    expected=grid.nx*grid.ny*grid.nz*grid.cell_volume
    common={"refinedCoarseCellCount":len(risk),"refinedFraction":fraction,
      "leafCount":len(leaves),"fineAuditCellCount":fine_grid.nx*fine_grid.ny*fine_grid.nz,
      "partitionOverlapCount":0,"leafCoverageVolume":coverage,"domainVolume":expected,
      "coarseUnitVolumes":coarse_vol,"previousLevelUnitVolumes":previous_vol,
      "refinedUnitVolumes":fine_vol,"coarseToFinalRelativeChanges":coarse_changes,
      "unitVolumeRelativeChanges":changes,"volumeRelativeTolerance":volume_relative_tolerance,
      "coarseTopologySignature":coarse_sig,"previousLevelTopologySignature":previous_sig,
      "refinedTopologySignature":fine_sig,"topologyStable":previous_sig==fine_sig,
      "topologyStabilityRequired":require_topology_stability,
      "convergenceLevels":convergence_levels,"finalRefinementFactor":final_factor,
      "voxelTopologyPreflight":topology_preflight}
    if not topology_preflight["passed"]:
        error={"code":"PreBrepTopologyRejected","preflightGate":topology_preflight["gate"],
          "touchEdgeCount":topology_preflight["touchEdgeCount"],
          "touchPointCount":topology_preflight["touchPointCount"],
          "unitAudits":topology_preflight["unitAudits"]}
        validation={"passed":False,"gate":"AdaptiveRefinementAndBooleanPartition",
          "errors":[error],"refinedBrepPassed":False,"refinedBrepSkipped":True,
          "refinedBrepValidation":None,**common}
        return AdaptivePartitionModel(tuple(leaves),fine,fine_grid,None,validation)
    brep=build_closed_breps(fine,fine_grid,units)
    errors=[]
    if any(value>volume_relative_tolerance for value in changes.values()):
        errors.append({"code":"VolumeConvergenceExceeded","relativeChanges":changes})
    if require_topology_stability and previous_sig!=fine_sig:
        errors.append({"code":"TopologySignatureChanged","previous":previous_sig,"refined":fine_sig})
    if not math.isclose(coverage,expected,rel_tol=1e-12,abs_tol=1e-9):
        errors.append({"code":"AdaptiveLeafCoverageMismatch"})
    if not brep.validation["passed"]:
        errors.append({"code":"RefinedBrepFailed","brepGate":brep.validation["gate"],
          "brepErrors":brep.validation["errors"],
          "unitDiagnostics":brep.validation["unitDiagnostics"]})
        errors.append({"code":"PreflightBrepDisagreement",
          "message":"Pre-B-rep voxel topology passed but the constructed B-rep failed validation"})
    validation={"passed":not errors,"gate":"AdaptiveRefinementAndBooleanPartition",
      "errors":errors,"refinedBrepPassed":brep.validation["passed"],
      "refinedBrepSkipped":False,"refinedBrepValidation":brep.validation,**common}
    return AdaptivePartitionModel(tuple(leaves),fine,fine_grid,brep,validation)


def _resample(risk,intrusion_model,factor):
    grid=intrusion_model.source_model.source_model.grid; coarse=intrusion_model.labels_zyx
    fine_grid=RegularGrid3D(grid.minimum,grid.maximum,tuple(v/factor for v in grid.cell_size),
                            (grid.nz*factor,grid.ny*factor,grid.nx*factor))
    fine=[[[None for _ in range(fine_grid.nx)] for _ in range(fine_grid.ny)]
          for _ in range(fine_grid.nz)]; leaves=[]
    for z in range(grid.nz):
     for y in range(grid.ny):
      for x in range(grid.nx):
       if (x,y,z) in risk:
        for sz in range(factor):
         for sy in range(factor):
          for sx in range(factor):
           fx,fy,fz=x*factor+sx,y*factor+sy,z*factor+sz
           point=(fine_grid.x_center(fx),fine_grid.y_center(fy),fine_grid.z_center(fz))
           label=_classify(point,intrusion_model); fine[fz][fy][fx]=label
           leaves.append(_leaf(fx,fy,fz,1,label,fine_grid))
       else:
        label=coarse[z][y][x]
        for sz in range(factor):
         for sy in range(factor):
          for sx in range(factor): fine[z*factor+sz][y*factor+sy][x*factor+sx]=label
        leaves.append(_leaf(x*factor,y*factor,z*factor,factor,label,fine_grid))
    return fine_grid,fine,leaves


def _risk_cells(labels,grid):
    risk=set()
    for z in range(grid.nz):
     for y in range(grid.ny):
      for x in range(grid.nx):
       label=labels[z][y][x]
       for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
        xx,yy,zz=x+dx,y+dy,z+dz
        other=labels[zz][yy][xx] if 0<=xx<grid.nx and 0<=yy<grid.ny and 0<=zz<grid.nz else None
        if other!=label:
            risk.add((x,y,z)); break
    return risk


def _classify(point,intrusion_model):
    structural=intrusion_model.source_model; model=structural.source_model
    x,y,z=point; label=None
    for body in model.primary_bodies:
        top=_field_at(x,y,body.top,model.grid); bottom=_field_at(x,y,body.bottom,model.grid)
        if bottom<z<=top: label=body.unit_id; break
    for body in model.replacement_bodies:
        top=_field_at(x,y,body.top,model.grid); bottom=_field_at(x,y,body.bottom,model.grid)
        if bottom<z<=top: label=body.unit_id
    if label is None: return None
    for operation in intrusion_model.operations:
        if label in operation.host_unit_ids and point_inside_intrusion(
                transform_point(point,label,structural),operation): label=operation.unit_id
    return label


def _field_at(x,y,values,grid):
    gx=(x-grid.minimum[0])/grid.cell_size[0]-.5; gy=(y-grid.minimum[1])/grid.cell_size[1]-.5
    x0=max(0,min(grid.nx-1,math.floor(gx))); x1=max(0,min(grid.nx-1,x0+1))
    y0=max(0,min(grid.ny-1,math.floor(gy))); y1=max(0,min(grid.ny-1,y0+1))
    tx=max(0,min(1,gx-x0)); ty=max(0,min(1,gy-y0))
    return ((values[y0][x0]*(1-tx)+values[y0][x1]*tx)*(1-ty)+
            (values[y1][x0]*(1-tx)+values[y1][x1]*tx)*ty)


def _leaf(x,y,z,size_factor,label,fine_grid):
    size=tuple(v*size_factor for v in fine_grid.cell_size)
    minimum=(fine_grid.minimum[0]+x*fine_grid.cell_size[0],
             fine_grid.minimum[1]+y*fine_grid.cell_size[1],
             fine_grid.minimum[2]+z*fine_grid.cell_size[2])
    return {"level":1 if size_factor==1 else 0,"minimum":list(minimum),
            "size":list(size),"label":label}


def _counts(labels):
    result={}
    for layer in labels:
     for row in layer:
      for value in row:
       if value is not None: result[value]=result.get(value,0)+1
    return result


def _topology_signature(labels):
    nz,ny,nx=len(labels),len(labels[0]),len(labels[0][0]); signatures=[]
    for unit in sorted({v for layer in labels for row in layer for v in row if v is not None}):
        cells={(x,y,z) for z in range(nz) for y in range(ny) for x in range(nx) if labels[z][y][x]==unit}
        components=0
        while cells:
            components+=1; q=deque([cells.pop()])
            while q:
                x,y,z=q.popleft()
                for d in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                    n=(x+d[0],y+d[1],z+d[2])
                    if n in cells: cells.remove(n); q.append(n)
        signatures.append(f"{unit}:{components}")
    return signatures
