"""GUI-safe official KuniJiban route-candidate discovery."""
from __future__ import annotations
import hashlib,json,urllib.request
from pathlib import Path
from .evidence.kunijiban_candidate_index import MARKER_URL,build_candidate_index,route_marker_tiles

def execute_kunijiban_candidate_search(plan_path,output_parent):
 source=Path(plan_path);plan=json.loads(source.read_text(encoding="utf-8"))
 if plan.get("schemaVersion")!="PlanEvidenceBundle-1.0":raise ValueError("PlanEvidenceBundle-1.0が必要です。")
 route=plan.get("routeLonLat");responses=[]
 for x,y,z in route_marker_tiles(route):
  request=urllib.request.Request(MARKER_URL.format(x=x,y=y,z=z),
    headers={"User-Agent":"geologic-3d-engine-research/1.0"})
  with urllib.request.urlopen(request,timeout=30) as response:raw=response.read()
  responses.append(((x,y,z),json.loads(raw.decode("utf-8")),hashlib.sha256(raw).hexdigest()))
 result=build_candidate_index(route,responses)
 result["planEvidenceSha256"]=hashlib.sha256(source.read_bytes()).hexdigest()
 # Re-sign after binding the selected plan artifact.
 unsigned={k:v for k,v in result.items() if k!="recordSha256"}
 result["recordSha256"]=hashlib.sha256(json.dumps(unsigned,sort_keys=True,
   separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
 output=Path(output_parent).resolve()/"kunijiban_candidates";output.mkdir(parents=True,exist_ok=True)
 target=output/"route_borehole_candidates.json";temporary=target.with_suffix(".json.tmp")
 temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");temporary.replace(target)
 return result,target
