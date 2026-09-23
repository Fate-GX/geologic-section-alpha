"""Project Stage-9 cell uncertainty onto a declared section sampling grid."""

from __future__ import annotations

import math

DEFAULT_MAXIMUM_SECTION_SAMPLES=250000


def project_uncertainty_to_section(probability_zyx, entropy_zyx, disagreement_zyx,
                                   source_grid, section_spec,
                                   maximum_samples=DEFAULT_MAXIMUM_SECTION_SAMPLES):
    """Nearest-cell projection; representative polygons remain a separate product."""
    section_spec.validate()
    _validate_shapes(probability_zyx, entropy_zyx, disagreement_zyx, source_grid)
    u_axis,v_axis,_=section_spec.basis()
    spacing=min(source_grid.cell_size)
    u_values=_axis_values(section_spec.u_range,spacing)
    v_values=_axis_values(section_spec.v_range,spacing)
    total_samples=len(u_values)*len(v_values)
    if not isinstance(maximum_samples,int) or maximum_samples<=0:
        raise ValueError("maximum_samples must be a positive integer")
    if total_samples>maximum_samples:
        raise ValueError(f"section uncertainty sampling grid has {total_samples} samples; maximum is {maximum_samples}")
    probabilities=[];entropies=[];disagreements=[];in_domain=[]
    errors=[];sample_count=0
    for v in v_values:
        p_row=[];e_row=[];d_row=[];inside_row=[]
        for u in u_values:
            point=tuple(section_spec.origin[i]+u*u_axis[i]+v*v_axis[i] for i in range(3))
            index=_cell_index(point,source_grid)
            if index is None:
                p_row.append(None);e_row.append(None);d_row.append(None);inside_row.append(False)
                continue
            x,y,z=index;p=dict(probability_zyx[z][y][x]);e=float(entropy_zyx[z][y][x])
            d=bool(disagreement_zyx[z][y][x]);total=sum(p.values())
            if not p or any(not isinstance(value,(int,float)) or not math.isfinite(value) or
                            value<0.0 or value>1.0 for value in p.values()):
                errors.append({"code":"InvalidMaterialProbability","u":u,"v":v})
            if not math.isclose(total,1.0,rel_tol=0.0,abs_tol=1e-12):
                errors.append({"code":"ProbabilitySumMismatch","u":u,"v":v,"sum":total})
            if not math.isfinite(e) or not 0.0<=e<=1.0:
                errors.append({"code":"NormalizedEntropyOutsideRange","u":u,"v":v,"value":e})
            if d!=(sum(value>0.0 for value in p.values())>1):
                errors.append({"code":"DisagreementMaskMismatch","u":u,"v":v})
            p_row.append(p);e_row.append(e);d_row.append(d);inside_row.append(True);sample_count+=1
        probabilities.append(p_row);entropies.append(e_row)
        disagreements.append(d_row);in_domain.append(inside_row)
    coverage_status=("NoIntersection" if sample_count==0 else
                     "FullCoverage" if sample_count==total_samples else "PartialCoverage")
    if sample_count==0:errors.append({"code":"SectionDoesNotIntersectUncertaintyGrid"})
    validation={"passed":not errors,"gate":"Stage9SpatialUncertaintySectionProjection",
      "errors":errors,"inDomainSampleCount":sample_count,
      "outOfDomainSampleCount":total_samples-sample_count,
      "probabilityNormalizationTolerance":1e-12}
    return {"sectionId":section_spec.section_id,"uValues":u_values,"vValues":v_values,
      "samplingSpacing":spacing,"samplingMethod":"NearestSourceCell_NoInterpolation",
      "samplingSpacingPolicy":"MinimumSourceCellEdge_NoInventedSubcellResolution",
      "maximumSampleCount":maximum_samples,"sampleCount":total_samples,
      "coverageStatus":coverage_status,
      "materialProbabilityVU":probabilities,"normalizedEntropyVU":entropies,
      "disagreementMaskVU":disagreements,"inDomainMaskVU":in_domain,
      "sourceGrid":source_grid.to_dict(),"validation":validation,
      "representation":"SectionAlignedSpatialUncertaintyGrid"}


def _axis_values(bounds,spacing):
    count=max(1,int(math.ceil((bounds[1]-bounds[0])/spacing)))
    return [bounds[0]+(bounds[1]-bounds[0])*i/count for i in range(count+1)]


def _cell_index(point,grid):
    result=[]
    for axis,(value,low,high,size,count) in enumerate(zip(
            point,grid.minimum,grid.maximum,grid.cell_size,(grid.nx,grid.ny,grid.nz))):
        if value<low or value>high:return None
        index=int(math.floor((value-low)/size))
        if index==count and math.isclose(value,high,rel_tol=0.0,abs_tol=1e-12):index=count-1
        if not 0<=index<count:return None
        result.append(index)
    return tuple(result)


def _validate_shapes(probability,entropy,disagreement,grid):
    expected=(grid.nz,grid.ny,grid.nx)
    for name,values in (("probability",probability),("entropy",entropy),("disagreement",disagreement)):
        actual=(len(values),len(values[0]) if values else 0,
                len(values[0][0]) if values and values[0] else 0)
        if actual!=expected:raise ValueError(f"{name} grid shape {actual} does not match {expected}")
