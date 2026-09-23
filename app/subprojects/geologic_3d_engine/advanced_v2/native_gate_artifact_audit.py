"""Fail-closed audit of promoted Advanced V2 native-DWG gate artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class NativeGateArtifactAuditError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def audit_native_gate_artifacts(project_root: Path, output_name: str) -> dict:
    root = project_root.resolve()
    destination = root / "dwg"
    paths = {
        "dwg": destination / f"{output_name}.dwg",
        "reopenReport": destination / f"{output_name}_reopen_validation.txt",
        "runRecord": destination / f"{output_name}_run_record.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise NativeGateArtifactAuditError(
            "native gate evidence incomplete: " + ", ".join(missing)
        )
    if paths["dwg"].read_bytes()[:6] != b"AC1032":
        raise NativeGateArtifactAuditError("DWG signature is not AC1032")
    reopen_text = paths["reopenReport"].read_text(encoding="utf-8")
    if "ADVANCED_V2_REOPEN_VALIDATION=OK" not in reopen_text:
        raise NativeGateArtifactAuditError("reopen validation marker is missing")

    record = json.loads(paths["runRecord"].read_text(encoding="utf-8"))
    if record.get("decision") != "NativeDwgGatePassed":
        raise NativeGateArtifactAuditError("run record does not declare the native gate passed")
    identity = str(record.get("executionIdentity", ""))
    if not identity or identity.casefold().startswith("codexsandbox"):
        raise NativeGateArtifactAuditError("run record has an invalid execution identity")
    if record.get("profilePolicy") != "CurrentDefault_NoArgImport_NoPersistentProfileChange":
        raise NativeGateArtifactAuditError("run record profile policy is invalid")
    for key in ("dwg", "reopenReport"):
        if Path(str(record.get(key, ""))).resolve() != paths[key].resolve():
            raise NativeGateArtifactAuditError(f"run record {key} path is not the promoted artifact")

    return {
        "schemaVersion": "AdvancedV2NativeGateArtifactAudit-1.0",
        "passed": True,
        "outputName": output_name,
        "executionIdentity": identity,
        "profilePolicy": record["profilePolicy"],
        "artifacts": {
            name: {"path": str(path.resolve()), "sha256": _sha256(path), "size": path.stat().st_size}
            for name, path in paths.items()
        },
        "limitations": [
            "This automated audit does not replace visual inspection in AutoCAD",
            "Geological validity is not established by DWG persistence",
        ],
    }

