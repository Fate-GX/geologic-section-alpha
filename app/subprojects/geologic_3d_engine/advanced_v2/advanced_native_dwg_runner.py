"""Advanced-V2-only AutoCAD writer; the frozen Basic V1 runner is untouched."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def _core_console_startup(console):
    """Return explicit, portable product/language arguments for Core Console."""
    install = console.parent
    requested_product = os.environ.get("GEO3D_AUTOCAD_PRODUCT", "").strip().upper()
    # AutoCAD installations commonly contain C3D/ACA resource directories even
    # when the user's configured product is plain AutoCAD. Directory presence
    # is therefore not a safe product selector. Advanced V2 defaults to ACAD;
    # a vertical must be explicitly requested through the environment override.
    product = requested_product or "ACAD"
    requested_language = os.environ.get("GEO3D_AUTOCAD_LANGUAGE", "").strip()
    if requested_language:
        language = requested_language
    else:
        language_roots = [install / product, install]
        language = next(
            (name for name in ("ja-JP", "en-US")
             if any((root / name).is_dir() for root in language_roots)),
            "en-US",
        )
    startup = [str(console), "/product", product, "/l", language]
    if os.environ.get("GEO3D_AUTOCAD_USE_CURRENT_DEFAULT", "").strip() == "1":
        # Core Console may use the already-selected AutoCAD default profile
        # without importing, switching or persisting a Codex-owned profile.
        return startup
    profile_arg = os.environ.get("GEO3D_AUTOCAD_PROFILE_ARG", "").strip()
    if profile_arg:
        profile_path = Path(profile_arg).expanduser().resolve()
        if profile_path.suffix.lower() != ".arg" or not profile_path.is_file():
            raise RuntimeError("GEO3D_AUTOCAD_PROFILE_ARG must identify an existing .arg file")
        return startup + ["/p", str(profile_path)]
    isolated_data = Path(tempfile.gettempdir()) / "geo3d_accore_isolate_2027"
    isolated_data.mkdir(parents=True, exist_ok=True)
    return startup + ["/isolate", "Geo3DAdvancedV2", str(isolated_data)]


def run_advanced_native_dwg(project_root, contract_envelope, output_name):
    root=Path(project_root).resolve(); contract=Path(contract_envelope).resolve()
    if not contract.is_file(): raise ValueError("DWG contract envelope was not found")
    if not output_name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in output_name):
        raise ValueError("DWG output name must be ASCII-safe")
    console=Path(r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe")
    dll_source=Path(__file__).resolve().parent/"native/bin/Release/net10.0-windows/AdvancedV2GeoDwg.dll"
    seed_source=root/"tools/AuthoritativeGeoDwg/seed.dxf"
    if not console.is_file() or not dll_source.is_file(): raise RuntimeError("advanced native writer prerequisites are missing")
    destination=root/"dwg";destination.mkdir(parents=True,exist_ok=True)
    final_dwg=destination/f"{output_name}.dwg";final_report=destination/f"{output_name}_reopen_validation.txt"
    def console_text(value):
        if not value: return ""
        encoding="utf-16-le" if b"\x00" in value[:200] else "utf-8"
        return value.decode(encoding,errors="replace")
    with tempfile.TemporaryDirectory(prefix="geo3d_adv2_",ignore_cleanup_errors=True) as folder:
        stage=Path(folder);dll=stage/"AdvancedV2GeoDwg.dll";staged_contract=stage/"contract.json";staged_dwg=stage/f"{output_name}.dwg";report=stage/"report.txt"
        shutil.copyfile(dll_source,dll);shutil.copyfile(seed_source,stage/"seed.dxf");shutil.copyfile(contract,staged_contract)
        (stage/"create.scr").write_text(f'(setvar "SECURELOAD" 0)\n_.NETLOAD\n{dll.as_posix()}\nCREATEADVANCEDGEOSECTION\n_.QUIT\n_Y\n',encoding="ascii")
        (stage/"verify.scr").write_text(f'(setvar "SECURELOAD" 0)\n_.NETLOAD\n{dll.as_posix()}\nVALIDATEADVANCEDGEOSECTION\n_.QUIT\n_N\n',encoding="ascii")
        env=dict(os.environ,GEO3D_EXPORT_CONTRACT=str(staged_contract),GEO3D_DWG_OUTPUT=str(staged_dwg))
        # Resolve the installed vertical/language explicitly. Environment
        # overrides keep the GitHub version portable across AutoCAD variants.
        startup=_core_console_startup(console)
        created=subprocess.run(startup+["/i",str(stage/"seed.dxf"),"/s",str(stage/"create.scr")],cwd=stage,env=env,timeout=180,capture_output=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if created.returncode or not staged_dwg.is_file(): raise RuntimeError(console_text(created.stdout+created.stderr))
        env["GEO3D_VERIFY_REPORT"]=str(report)
        reopened=subprocess.run(startup+["/i",str(staged_dwg),"/s",str(stage/"verify.scr")],cwd=stage,env=env,timeout=180,capture_output=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if reopened.returncode or not report.is_file(): raise RuntimeError(console_text(reopened.stdout+reopened.stderr))
        audit=report.read_text(encoding="utf-8")
        if "ADVANCED_V2_REOPEN_VALIDATION=OK" not in audit: raise RuntimeError(audit)
        if "GRID_STROKES_OK=true" not in audit:raise RuntimeError("GridStrokeAuditMissingOrFailed")
        if staged_dwg.read_bytes()[:6]!=b"AC1032":raise RuntimeError("saved artifact is not AC1032")
        shutil.copyfile(staged_dwg,final_dwg);shutil.copyfile(report,final_report)
    return final_dwg,final_report
