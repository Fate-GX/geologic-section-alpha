"""Read-only readiness evidence for the Advanced V2 native-DWG gate.

HKCU always belongs to the process identity.  A sandboxed verifier must not
interpret an absent key in its own hive as evidence that the interactive
AutoCAD user's profile is uninitialized.
"""
from __future__ import annotations

import getpass
from pathlib import Path
import winreg


AUTOCAD_USER_ROOT = r"Software\Autodesk\AutoCAD\R26.0"


def user_product_roots() -> list[str]:
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOCAD_USER_ROOT)
    except FileNotFoundError:
        return []
    result: list[str] = []
    with root:
        index = 0
        while True:
            try:
                name = winreg.EnumKey(root, index)
            except OSError:
                break
            if name.upper().startswith("ACAD-"):
                result.append(name)
            index += 1
    return sorted(result)


def classify_readiness(*, prerequisites: dict[str, bool], product_roots: list[str],
                       inspection_identity: str) -> dict:
    missing = [name for name, present in prerequisites.items() if not present]
    if missing:
        status = "BlockedBeforeNativeGate"
        reasons = missing
    elif product_roots:
        status = "ReadyInInspectionUserContext"
        reasons = []
    else:
        status = "IndeterminateAcrossUserBoundary"
        reasons = ["InspectionUserHKCUHasNoProductRoot_InteractiveUserNotInferred"]
    return {
        "schemaVersion": "AdvancedV2NativeReadiness-1.1",
        "mode": "ReadOnly",
        "inspectionIdentity": inspection_identity,
        "hkcuScope": "CurrentProcessIdentityOnly",
        "prerequisites": prerequisites,
        "hkcuProductRoots": list(product_roots),
        "profileImportAttempted": False,
        "registryWriteAttempted": False,
        "status": status,
        "blockingReasons": reasons,
        "interactiveAutoCadProfileState": (
            "NotInferredFromDifferentProcessIdentity" if not product_roots else
            "SameInspectionIdentityHasProductRoot"
        ),
    }


def probe(project_root: Path) -> dict:
    prerequisites = {
        "coreConsole": Path(r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe").is_file(),
        "writerDll": (project_root / "subprojects/geologic_3d_engine/advanced_v2/native/bin/Release/net10.0-windows/AdvancedV2GeoDwg.dll").is_file(),
        "seedDxf": (project_root / "tools/AuthoritativeGeoDwg/seed.dxf").is_file(),
    }
    return classify_readiness(
        prerequisites=prerequisites,
        product_roots=user_product_roots(),
        inspection_identity=getpass.getuser(),
    )
