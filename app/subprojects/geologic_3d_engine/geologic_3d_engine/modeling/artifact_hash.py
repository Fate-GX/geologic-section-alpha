import hashlib,json

def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
        ensure_ascii=False,allow_nan=False).encode("utf-8")).hexdigest()

def signed_artifact(value):
    result=dict(value);result["artifactSha256"]=canonical_sha256(result);return result

def verify_artifact(value,schema):
    if not isinstance(value,dict) or value.get("schemaVersion")!=schema:raise ValueError(f"{schema} is required")
    claimed=value.get("artifactSha256");unsigned={k:v for k,v in value.items() if k!="artifactSha256"}
    if claimed!=canonical_sha256(unsigned):raise ValueError("artifact hash mismatch")
    return value
