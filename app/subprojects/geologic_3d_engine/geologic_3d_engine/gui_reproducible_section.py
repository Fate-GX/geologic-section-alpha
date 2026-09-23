"""Package selected GUI inputs and execute only through the hash-bound runner."""
import json,shutil,uuid
from pathlib import Path
from .section.reproducible_section_run import build_bundle_document,execute_reproducible_section_bundle

def execute_selected_section_inputs(output_parent,artifacts):
    output=Path(output_parent).resolve();package=output/("section_bundle_"+uuid.uuid4().hex[:12]);package.mkdir(parents=True,exist_ok=False)
    copied={}
    for role,path in artifacts.items():
        if path:
            target=package/(role+".json");shutil.copyfile(Path(path),target);copied[role]=target
    run_id="ARBITRARY-SECTION-"+uuid.uuid4().hex
    bundle=build_bundle_document(run_id,copied,package);bundle_path=package/"bundle.json"
    bundle_path.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding="utf-8")
    manifest,run=execute_reproducible_section_bundle(bundle_path,output)
    return manifest,run,bundle_path
