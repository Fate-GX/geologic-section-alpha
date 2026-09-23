from __future__ import annotations
import hashlib, json
from pathlib import Path


def verify_frozen_basic_v1(project_root):
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / "frozen_basic_v1_manifest.json").read_text(encoding="utf-8"))
    engine = Path(project_root).resolve() / "subprojects/geologic_3d_engine"
    mismatches = []
    for relative, expected in manifest["files"].items():
        path = (engine / relative).resolve()
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != expected:
            mismatches.append({"path": str(path), "expectedSha256": expected, "actualSha256": actual})
    for relative, expected in manifest.get("trees", {}).items():
        base = (engine / relative).resolve()
        digest = hashlib.sha256()
        paths = sorted(path for path in base.rglob("*") if path.is_file() and
                       path.suffix in {".py", ".json"} and "__pycache__" not in path.parts)
        for path in paths:
            digest.update(path.relative_to(base).as_posix().encode("utf-8") + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        actual = digest.hexdigest()
        if actual != expected["sha256"] or len(paths) != expected["fileCount"]:
            mismatches.append({"path":str(base), "expectedSha256":expected["sha256"],
                               "actualSha256":actual, "expectedFileCount":expected["fileCount"],
                               "actualFileCount":len(paths)})
    return {"passed": not mismatches, "schemaVersion": manifest["schemaVersion"],
            "checkedFileCount": len(manifest["files"]) + sum(v["fileCount"] for v in manifest.get("trees",{}).values()),
            "mismatches": mismatches}
