"""GUI backend for source-linked strike/dip observations."""
import hashlib
import json
from pathlib import Path
from .section.structural_observations import project_structural_observations
from .section.route_binding import build_route_binding

def execute_structural_intake(source_path,output_parent,route_conditions,maximum_offset_m):
    source=Path(source_path);raw=source.read_bytes();document=json.loads(raw.decode("utf-8"))
    observations=document.get("observations") if isinstance(document,dict) else None
    if not isinstance(observations,list) or not observations:raise ValueError("observations配列を1件以上含むJSONが必要です。")
    projected=project_structural_observations(observations,route_conditions.vertices,maximum_offset_m)
    result={"schemaVersion":"StructuralObservationProjection-1.0","sourceFile":source.name,
      "sourceFileSha256":hashlib.sha256(raw).hexdigest(),"maximumProjectionOffsetM":float(maximum_offset_m),
      "routeBinding":build_route_binding(route_conditions.vertices),
      "observations":projected,"projectedCount":sum(v["projectionState"]=="Projected" for v in projected),
      "rejectedCount":sum(v["projectionState"]=="Rejected" for v in projected),
      "authorization":"ApparentDipCompatibilityConstraint_NotSubsurfaceTruth"}
    output=Path(output_parent).resolve()/"structural_observation_intake";output.mkdir(parents=True,exist_ok=True)
    target=output/"projected_structural_observations.json"
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result,target
