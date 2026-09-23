"""GUI backend for mapped contact/fault linework intersections."""
import hashlib,json
from pathlib import Path
from .section.geographic_linework import (intersect_geographic_linework,
    add_terrain_elevations,load_geographic_linework_evidence)

def execute_linework_intake(source_path,plan_path,output_parent,route_conditions):
    source=Path(source_path);raw=source.read_bytes();document=json.loads(raw.decode("utf-8"))
    if document.get("schemaVersion") is not None:
        document=load_geographic_linework_evidence(source)
    features=document.get("features") if isinstance(document,dict) else None
    if not isinstance(features,list) or not features:raise ValueError("features配列を1件以上含むJSONが必要です。")
    plan=json.loads(Path(plan_path).read_text(encoding="utf-8"))
    result=add_terrain_elevations(intersect_geographic_linework(route_conditions.vertices,features),plan["terrainProfile"])
    result["sourceFile"]=source.name;result["sourceFileSha256"]=hashlib.sha256(raw).hexdigest()
    output=Path(output_parent).resolve()/"mapped_linework_intake";output.mkdir(parents=True,exist_ok=True)
    target=output/"route_linework_intersections.json";target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result,target
