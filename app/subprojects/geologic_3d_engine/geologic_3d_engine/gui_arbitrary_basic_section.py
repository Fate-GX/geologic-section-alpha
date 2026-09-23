"""Connect arbitrary-route public plan evidence to the basic section renderer."""
from pathlib import Path
import json,uuid
from .gui_plan_preview import execute_plan_preview
from .section.arbitrary_route_basic_section import build_arbitrary_route_basic_model,render_arbitrary_route_basic_section
from .export.arbitrary_route_dwg import write_arbitrary_route_dwg_handoff
from .export.native_dwg_runner import run_native_dwg

def execute_arbitrary_basic_section(project_root,output_parent,route_conditions,*,seed=20260905,contact_lines="Show"):
    root=Path(output_parent).resolve()/f"arbitrary_basic_{uuid.uuid4().hex[:12]}"
    _,evidence,_=execute_plan_preview(project_root,root,route_conditions)
    plan=json.loads(evidence.read_text(encoding="utf-8"))
    model=build_arbitrary_route_basic_model(plan,seed=seed)
    image=render_arbitrary_route_basic_section(model,root/"basic_lithology_section.png",contact_lines=contact_lines)
    model_path=image.with_name("model.json")
    contract=write_arbitrary_route_dwg_handoff(model,root/"native_dwg_contract_envelope.json")
    dwg,report=run_native_dwg(project_root,contract,f"Japan_Experimental_{seed}_{root.name[-12:]}")
    return image,model_path,evidence,contract,dwg,report
