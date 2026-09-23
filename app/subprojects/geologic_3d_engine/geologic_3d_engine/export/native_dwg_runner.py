"""Execute the reviewed AutoCAD .NET writer in an isolated ASCII staging path."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def run_native_dwg(project_root, contract_envelope, output_name):
    root = Path(project_root).resolve()
    contract = Path(contract_envelope).resolve()
    if not contract.is_file():
        raise ValueError("DWG contract envelope was not found")
    if not output_name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in output_name):
        raise ValueError("DWG output name must be ASCII letters, digits, underscore or hyphen")
    console = Path(r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe")
    dll_source = root / "tools/AuthoritativeGeoDwg/bin/Release/net10.0-windows/AuthoritativeGeoDwg.dll"
    seed_source = root / "tools/AuthoritativeGeoDwg/seed.dxf"
    if not console.is_file():
        raise RuntimeError("AutoCAD Core Console 2027 is not installed")
    if not dll_source.is_file():
        raise RuntimeError("native DWG writer must be built before execution")
    destination = root / "dwg"
    destination.mkdir(parents=True, exist_ok=True)
    final_dwg = destination / f"{output_name}.dwg"
    final_report = destination / f"{output_name}_reopen_validation.txt"
    with tempfile.TemporaryDirectory(prefix="geo3d_") as folder:
        stage = Path(folder)
        dll = stage / "AuthoritativeGeoDwg.dll"
        staged_contract = stage / "contract.json"
        staged_dwg = stage / f"{output_name}.dwg"
        report = stage / "reopen_report.txt"
        shutil.copyfile(dll_source, dll)
        shutil.copyfile(seed_source, stage / "seed.dxf")
        shutil.copyfile(contract, staged_contract)
        netload = dll.as_posix()
        (stage / "create.scr").write_text(
            f'(setvar "SECURELOAD" 0)\n_.NETLOAD\n{netload}\nCREATEGEO3DSECTION\n_.QUIT\n_Y\n', encoding="ascii")
        (stage / "verify.scr").write_text(
            f'(setvar "SECURELOAD" 0)\n_.NETLOAD\n{netload}\nVALIDATEGEO3DSECTION\n_.QUIT\n_N\n', encoding="ascii")
        environment = dict(os.environ, GEO3D_EXPORT_CONTRACT=str(staged_contract), GEO3D_DWG_OUTPUT=str(staged_dwg))
        created = subprocess.run([str(console), "/i", str(stage / "seed.dxf"), "/s", str(stage / "create.scr"), "/l", "en-US"],
                                 cwd=stage, env=environment, timeout=180, capture_output=True)
        if created.returncode or not staged_dwg.is_file():
            raise RuntimeError("AutoCAD did not create the DWG")
        environment["GEO3D_VERIFY_REPORT"] = str(report)
        reopened = subprocess.run([str(console), "/i", str(staged_dwg), "/s", str(stage / "verify.scr"), "/l", "en-US"],
                                  cwd=stage, env=environment, timeout=180, capture_output=True)
        if reopened.returncode or not report.is_file():
            raise RuntimeError("AutoCAD did not produce a reopen report")
        audit = report.read_text(encoding="utf-8")
        if "GEO3D_REOPEN_VALIDATION=OK" not in audit:
            raise RuntimeError(audit)
        if staged_dwg.read_bytes()[:6] != b"AC1032":
            raise RuntimeError("saved artifact is not an AutoCAD 2018 DWG")
        shutil.copyfile(staged_dwg, final_dwg)
        shutil.copyfile(report, final_report)
    return final_dwg, final_report
