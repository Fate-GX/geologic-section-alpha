"""GUI backend for a non-correlating regional borehole context preview."""
import hashlib
import json
from pathlib import Path

from PIL import Image

from .section.regional_borehole_context_render import render_regional_borehole_context


def execute_regional_borehole_context(plan_path, role_path, borehole_path, output_parent):
    load = lambda p: json.loads(Path(p).resolve().read_text(encoding="utf-8"))
    output = Path(output_parent).resolve()/"regional_borehole_context"
    output.mkdir(parents=True, exist_ok=True)
    target = output/"regional_borehole_context.png"
    plan = load(plan_path); roles = load(role_path); holes = load(borehole_path)
    result = render_regional_borehole_context(plan, roles, holes, target)
    plan_image = Path(plan_path).resolve().with_name(
        "current_aerial_and_arbitrary_terrain_profile.png")
    combined = None
    if plan_image.is_file():
        base = Image.open(plan_image).convert("RGB")
        context = Image.open(target).convert("RGB")
        if context.width != base.width:
            scaled_height = round(context.height*base.width/context.width)
            context = context.resize((base.width, scaled_height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (base.width, base.height+context.height), "white")
        canvas.paste(base, (0, 0)); canvas.paste(context, (0, base.height))
        combined = output/"plan_terrain_and_regional_borehole_context.png"
        canvas.save(combined)
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    integrated = dict(plan)
    integrated["regionalBoreholeContext"] = {
        **result,
        "roleArtifactSha256":digest(role_path),
        "boreholeArtifactSha256":digest(borehole_path),
        "standaloneImageSha256":digest(target),
        "combinedImageSha256":digest(combined) if combined else None,
        "combinedImageState":"Generated" if combined else "PlanImageUnavailable",
        "authorizationBoundary":"DisplayOnly_NoSubsurfaceCorrelation"
    }
    evidence = output/"integrated_plan_evidence_bundle.json"
    evidence.write_text(json.dumps(integrated, ensure_ascii=False, indent=2)+"\n",
                        encoding="utf-8")
    return result, target, target.with_suffix(".json"), combined, evidence
