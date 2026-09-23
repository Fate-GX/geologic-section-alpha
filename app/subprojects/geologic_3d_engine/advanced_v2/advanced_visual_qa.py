"""Render an Advanced V2 DWG from a disposable copy without mutating it."""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path
from advanced_native_dwg_runner import _core_console_startup

def _sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _normalize_landscape_pdf(source_path, target_path):
    """Normalize a portrait-wrapper PDF emitted for an A3 landscape layout."""
    from pypdf import PdfReader, PdfWriter

    source=Path(source_path); target=Path(target_path)
    reader=PdfReader(source); writer=PdfWriter()
    if not reader.pages:
        raise RuntimeError("AutoCAD produced an empty layout PDF")
    for page in reader.pages:
        width=float(page.mediabox.width); height=float(page.mediabox.height)
        rotation=int(page.get("/Rotate",0))%360
        if width>height and rotation in (90,270):
            # Some AutoCAD/PDF-driver combinations already emit a landscape
            # media box but retain a stale portrait-wrapper rotation.  Keeping
            # that flag turns an A3 landscape page portrait in viewers.
            page.rotation=0
        elif height>width and rotation in (0,180):
            # AutoCAD's Degrees090 content inside the portrait-only psk:ISOA3
            # wrapper needs a counter-clockwise viewing rotation.  Keep this
            # as PDF page metadata: baking it into the content matrix shifts
            # some Microsoft Print to PDF printable-area origins and clips
            # otherwise valid layouts.
            page.rotate(-90)
        writer.add_page(page)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("wb") as stream:
        writer.write(stream)
    check=PdfReader(target)
    for page in check.pages:
        width=float(page.mediabox.width); height=float(page.mediabox.height)
        rotation=int(page.get("/Rotate",0))%360
        effective_landscape=(width>height and rotation in (0,180)) or (height>width and rotation in (90,270))
        if not effective_landscape:
            raise RuntimeError("layout PDF was not normalized to landscape viewing orientation")

def render_disposable_model_preview(dwg_path, preview_path, report_path):
    source=Path(dwg_path).resolve(); preview=Path(preview_path).resolve(); report=Path(report_path).resolve()
    if not source.is_file() or source.read_bytes()[:6] != b"AC1032":
        raise ValueError("maintained artifact is not an AC1032 DWG")
    console=Path(r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe")
    if not console.is_file(): raise RuntimeError("AutoCAD Core Console was not found")
    before=_sha256(source); preview.parent.mkdir(parents=True,exist_ok=True); report.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="adv2_visual_qa_",ignore_cleanup_errors=True) as folder:
        stage=Path(folder); copy=stage/"visual_qa_copy.dwg"; staged_png=stage/"visual_qa.png"
        shutil.copyfile(source,copy)
        script=stage/"render.scr"
        script.write_text('(setvar "FILEDIA" 0)\n_.TILEMODE\n1\n_.ZOOM\n_E\n_.PNGOUT\n'+staged_png.as_posix()+'\n_ALL\n\n_.QUIT\n_N\n',encoding="ascii")
        process=subprocess.run(_core_console_startup(console)+["/i",str(copy),"/s",str(script)],cwd=stage,env=dict(os.environ),timeout=180,capture_output=True)
        if process.returncode or not staged_png.is_file():
            output=process.stdout+process.stderr; encoding="utf-16-le" if b"\x00" in output[:200] else "utf-8"
            raise RuntimeError(output.decode(encoding,errors="replace"))
        shutil.copyfile(staged_png,preview)
    after=_sha256(source)
    result={"schemaVersion":"AdvancedV2DisposableVisualQA-1.0","maintainedArtifact":str(source),
            "maintainedSha256Before":before,"maintainedSha256After":after,
            "maintainedArtifactUnchanged":before==after,"preview":str(preview),
            "previewSha256":_sha256(preview),"renderedFromDisposableCopy":True,
            "automatedRenderingPassed":before==after,"humanVisualDecision":"Pending"}
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


def render_disposable_layout_previews(dwg_path, output_directory, report_path):
    """Render all required paper layouts from one disposable DWG copy."""
    source=Path(dwg_path).resolve(); output=Path(output_directory).resolve(); report=Path(report_path).resolve()
    if not source.is_file() or source.read_bytes()[:6] != b"AC1032":
        raise ValueError("maintained artifact is not an AC1032 DWG")
    console=Path(r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe")
    if not console.is_file(): raise RuntimeError("AutoCAD Core Console was not found")
    layouts=("GEO_JP","GEO_EN","GEO_TOPOLOGY_QA","GEO_MONOCHROME_QA")
    before=_sha256(source); output.mkdir(parents=True,exist_ok=True); report.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="adv2_layout_qa_",ignore_cleanup_errors=True) as folder:
        stage=Path(folder); copy=stage/"layout_qa_copy.dwg"; shutil.copyfile(source,copy)
        commands=['(setvar "FILEDIA" 0)','_.TILEMODE','0']
        staged=[]
        for layout in layouts:
            image=stage/f"{layout}.png"; staged.append((layout,image))
            commands.extend([f'(setvar "CTAB" "{layout}")','_.PSPACE','_.MVIEW','_ON','_ALL','','_.REGENALL','_.ZOOM','_E','_.PNGOUT',image.as_posix(),'_ALL',''])
        commands.extend(['_.QUIT','_N'])
        script=stage/"render_layouts.scr"; script.write_text('\n'.join(commands)+'\n',encoding="ascii")
        process=subprocess.run(_core_console_startup(console)+["/i",str(copy),"/s",str(script)],cwd=stage,env=dict(os.environ),timeout=180,capture_output=True)
        if process.returncode or any(not image.is_file() for _,image in staged):
            raw=process.stdout+process.stderr; encoding="utf-16-le" if b"\x00" in raw[:200] else "utf-8"
            raise RuntimeError(raw.decode(encoding,errors="replace"))
        previews=[]
        for layout,image in staged:
            target=output/f"{layout}.png"; shutil.copyfile(image,target)
            previews.append({"layout":layout,"path":str(target),"sha256":_sha256(target)})
    after=_sha256(source)
    result={"schemaVersion":"AdvancedV2DisposableLayoutQA-1.0","maintainedArtifact":str(source),
            "maintainedSha256Before":before,"maintainedSha256After":after,
            "maintainedArtifactUnchanged":before==after,"renderedFromDisposableCopy":True,
            "requiredLayouts":list(layouts),"previews":previews,
            "automatedRenderingPassed":before==after and len(previews)==len(layouts),
            "humanVisualDecision":"Pending"}
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


def plot_disposable_layout_pdfs(dwg_path, output_directory):
    """Plot required layouts through AutoCAD's native PlotEngine command."""
    source=Path(dwg_path).resolve(); output=Path(output_directory).resolve()
    if not source.is_file() or source.read_bytes()[:6] != b"AC1032":
        raise ValueError("maintained artifact is not an AC1032 DWG")
    console=Path(r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe")
    before=_sha256(source); output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="adv2_pdf_qa_",ignore_cleanup_errors=True) as folder:
        stage=Path(folder); dll=stage/"AdvancedV2GeoDwg.dll"
        shutil.copyfile(Path(__file__).resolve().parent/"native/bin/Release/net10.0-windows/AdvancedV2GeoDwg.dll",dll)
        script=stage/"plot.scr"
        script.write_text('(setvar "SECURELOAD" 0)\n_.NETLOAD\n'+dll.as_posix()+'\nPLOTADVANCEDGEOLAYOUTS\n_.QUIT\n_N\n',encoding="ascii")
        pdfs=[]
        for name in ("GEO_JP","GEO_EN","GEO_TOPOLOGY_QA","GEO_MONOCHROME_QA"):
            copy=stage/f"{name}_plot_qa_copy.dwg"; shutil.copyfile(source,copy)
            env=dict(os.environ,GEO3D_LAYOUT_PDF_DIR=str(stage/"pdf"),GEO3D_LAYOUT_NAME=name)
            (stage/"pdf").mkdir(exist_ok=True)
            process=subprocess.run(_core_console_startup(console)+["/i",str(copy),"/s",str(script)],cwd=stage,env=env,timeout=240,capture_output=True)
            staged=stage/"pdf"/f"{name}.pdf"
            if process.returncode or not staged.is_file():
                raw=process.stdout+process.stderr; encoding="utf-16-le" if b"\x00" in raw[:200] else "utf-8"
                raise RuntimeError(raw.decode(encoding,errors="replace"))
            target=output/staged.name; _normalize_landscape_pdf(staged,target); pdfs.append(target)
    if _sha256(source)!=before: raise RuntimeError("maintained DWG changed during disposable plot")
    return pdfs
