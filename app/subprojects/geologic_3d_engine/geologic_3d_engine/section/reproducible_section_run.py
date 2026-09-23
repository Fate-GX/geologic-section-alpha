"""Hash-bound reproducible execution bundle for arbitrary-route sections."""
import hashlib,json,shutil,uuid
from pathlib import Path
from ..gui_reviewed_section import execute_reviewed_section

REQUIRED=("plan","boreholeIntake","correlationReview")
OPTIONAL=("structuralObservations","mappedLinework","faultEvidence","erosionFill",
          "qualitativeStratigraphy")

def sha256_file(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _resolve(root,value,key):
    if not isinstance(value,dict) or set(value)!={"path","sha256"}:raise ValueError(f"invalid {key} artifact binding")
    if not isinstance(value["path"],str) or not isinstance(value["sha256"],str):raise ValueError(f"invalid {key} path or hash")
    path=(root/value["path"]).resolve()
    try:path.relative_to(root)
    except ValueError:raise ValueError(f"{key} path escapes bundle directory")
    if not path.is_file():raise ValueError(f"{key} artifact is missing")
    actual=sha256_file(path)
    if actual!=value["sha256"]:raise ValueError(f"{key} artifact hash mismatch")
    return path,actual

def execute_reproducible_section_bundle(bundle_path,output_parent):
    bundle_file=Path(bundle_path).resolve();root=bundle_file.parent
    bundle=json.loads(bundle_file.read_text(encoding="utf-8"))
    allowed={"schemaVersion","runId","inputs"}
    if not isinstance(bundle,dict) or set(bundle)!=allowed or bundle["schemaVersion"]!="ArbitrarySectionRunBundle-1.0":raise ValueError("unsupported section run bundle")
    if not isinstance(bundle["runId"],str) or not bundle["runId"].strip():raise ValueError("runId is required")
    inputs=bundle["inputs"]
    if not isinstance(inputs,dict) or not set(REQUIRED)<=set(inputs) or not set(inputs)<=set(REQUIRED+OPTIONAL):raise ValueError("section run inputs are incomplete or unknown")
    resolved={};hashes={}
    for key,value in inputs.items():resolved[key],hashes[key]=_resolve(root,value,key)
    run=Path(output_parent).resolve()/("section_run_"+uuid.uuid4().hex[:12]);copied=run/"inputs";copied.mkdir(parents=True,exist_ok=False)
    local={}
    for key,path in resolved.items():
        target=copied/(key+path.suffix.lower());shutil.copyfile(path,target);local[key]=target
        if sha256_file(target)!=hashes[key]:raise RuntimeError("copied input hash mismatch")
    try:
        section,json_path,image_path=execute_reviewed_section(local["plan"],local["boreholeIntake"],local["correlationReview"],run,
          local.get("structuralObservations"),local.get("mappedLinework"),local.get("faultEvidence"),local.get("erosionFill"),
          local.get("qualitativeStratigraphy"))
        outputs={"sectionJson":{"path":str(json_path.relative_to(run)),"sha256":sha256_file(json_path)},
                 "sectionPng":{"path":str(image_path.relative_to(run)),"sha256":sha256_file(image_path)}}
        passed=all(section.get("validation",{}).values())
        manifest={"schemaVersion":"ArbitrarySectionRunManifest-1.0","runId":bundle["runId"],"passed":passed,
          "decision":"Experimental" if passed else "Rejected","inputSha256":hashes,"outputs":outputs,
          "realRegionAuthorized":False,"scope":"EvidenceLinkedInterpretedSection_NotNativeDwg"}
    except Exception as error:
        manifest={"schemaVersion":"ArbitrarySectionRunManifest-1.0","runId":bundle["runId"],"passed":False,
          "decision":"Rejected","inputSha256":hashes,"outputs":{},"realRegionAuthorized":False,
          "scope":"EvidenceLinkedInterpretedSection_NotNativeDwg","error":str(error)}
    manifest_path=run/"run_manifest.json";manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest,run

def build_bundle_document(run_id,artifacts,bundle_directory):
    root=Path(bundle_directory).resolve();inputs={}
    for key,path in artifacts.items():
        if key not in REQUIRED+OPTIONAL:raise ValueError("unknown input role")
        resolved=Path(path).resolve()
        try:relative=resolved.relative_to(root)
        except ValueError:raise ValueError("all bundle inputs must be inside the bundle directory")
        inputs[key]={"path":relative.as_posix(),"sha256":sha256_file(resolved)}
    return {"schemaVersion":"ArbitrarySectionRunBundle-1.0","runId":run_id,"inputs":inputs}
