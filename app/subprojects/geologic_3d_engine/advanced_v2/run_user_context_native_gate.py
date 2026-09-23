"""Run the Advanced V2 native-DWG gate from the interactive Windows user.

This entry point never imports an ARG profile and never changes AutoCAD's
persistent profile.  It is intentionally rejected under the Codex sandbox
identity because that identity has a different HKCU hive from the user who is
running AutoCAD.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path

from advanced_native_dwg_runner import run_advanced_native_dwg


class NativeGateInteractiveUserRequired(RuntimeError):
    pass


def windows_process_identity() -> str:
    """Return the authenticated Windows process identity, not an env alias."""
    size = ctypes.c_ulong(256)
    buffer = ctypes.create_unicode_buffer(size.value)
    if not ctypes.windll.advapi32.GetUserNameW(buffer, ctypes.byref(size)):
        raise OSError("GetUserNameW failed")
    return buffer.value


def ensure_interactive_user(identity: str) -> str:
    normalized = identity.strip()
    if not normalized or normalized.casefold().startswith("codexsandbox"):
        raise NativeGateInteractiveUserRequired(
            "native DWG gate must run from the interactive AutoCAD user context"
        )
    return normalized


def current_default_environment(source: dict[str, str]) -> dict[str, str]:
    result = dict(source)
    result["GEO3D_AUTOCAD_USE_CURRENT_DEFAULT"] = "1"
    result["GEO3D_AUTOCAD_PRODUCT"] = result.get("GEO3D_AUTOCAD_PRODUCT", "ACAD") or "ACAD"
    result["GEO3D_AUTOCAD_LANGUAGE"] = result.get("GEO3D_AUTOCAD_LANGUAGE", "ja-JP") or "ja-JP"
    result.pop("GEO3D_AUTOCAD_PROFILE_ARG", None)
    return result


def run_gate(project_root: Path, contract: Path, output_name: str, identity: str) -> dict:
    user = ensure_interactive_user(identity)
    root = project_root.resolve()
    destination = root / "dwg"
    dwg = destination / f"{output_name}.dwg"
    report = destination / f"{output_name}_reopen_validation.txt"
    record = destination / f"{output_name}_run_record.json"
    existing = [str(path) for path in (dwg, report, record) if path.exists()]
    if existing:
        raise FileExistsError("native gate refuses to overwrite: " + ", ".join(existing))

    previous = dict(os.environ)
    os.environ.clear()
    os.environ.update(current_default_environment(previous))
    try:
        written_dwg, written_report = run_advanced_native_dwg(root, contract, output_name)
    finally:
        os.environ.clear()
        os.environ.update(previous)

    if written_dwg.read_bytes()[:6] != b"AC1032":
        raise RuntimeError("promoted DWG is not AC1032")
    audit = written_report.read_text(encoding="utf-8")
    if "ADVANCED_V2_REOPEN_VALIDATION=OK" not in audit:
        raise RuntimeError("promoted reopen report does not contain the success marker")

    payload = {
        "schemaVersion": "AdvancedV2NativeGateRun-1.0",
        "decision": "NativeDwgGatePassed",
        "executionIdentity": user,
        "profilePolicy": "CurrentDefault_NoArgImport_NoPersistentProfileChange",
        "contractEnvelope": str(contract.resolve()),
        "dwg": str(written_dwg.resolve()),
        "reopenReport": str(written_report.resolve()),
        "dwgSignature": "AC1032",
        "reopenValidation": "OK",
    }
    record.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--contract-envelope", required=True, type=Path)
    parser.add_argument("--output-name", required=True)
    args = parser.parse_args()
    print(json.dumps(run_gate(
        args.project_root,
        args.contract_envelope,
        args.output_name,
        windows_process_identity(),
    ), ensure_ascii=False, indent=2))
