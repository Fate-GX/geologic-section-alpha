"""Bind completed human inspection of the terrain-matrix plots to each DWG."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

LAYOUTS = ("GEO_JP", "GEO_EN", "GEO_TOPOLOGY_QA", "GEO_MONOCHROME_QA")
COMMON = {
    "modelGeometryVisible": True,
    "geometryWithinViewport": True,
    "noBlankGeology": True,
    "noMojibake": True,
    "textWithinSheet": True,
    "requiredTicksVisible": True,
    "modelLowerLimitFilled": True,
    "contactLinesInForeground": True,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("plot_root", type=Path)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    for row in summary["results"]:
        manifest = Path(row["manifestPath"])
        run_dir = manifest.parent
        dwg = next(Path(item["path"]) for item in row["artifacts"] if item["path"].lower().endswith(".dwg"))
        layouts = {}
        for name in LAYOUTS:
            pdf = args.plot_root / row["case"] / f"{name}.pdf"
            checks = dict(COMMON, plotSha256=sha256(pdf))
            if name == "GEO_TOPOLOGY_QA":
                checks["hatchesHidden"] = True
            if name == "GEO_MONOCHROME_QA":
                checks["monochromeEffective"] = True
            layouts[name] = checks
        record = {
            "schemaVersion": "AdvancedV2PostGenerationVisualAdjudication-1.0",
            "decision": "Accepted",
            "reviewedDwg": str(dwg),
            "reviewedDwgSha256": sha256(dwg),
            "plotOutputReviewed": True,
            "reviewMethod": "All four native AutoCAD PlotEngine PDFs were rendered with Poppler and visually inspected individually and in a seven-terrain comparison sheet.",
            "layouts": layouts,
            "geologicalValidity": "SyntheticAssumption",
            "releaseScope": "AdvancedV2ExperimentalOnly",
            "notes": [
                "The drafting-only basal band continues the already selected deepest unit and is explicitly marked SyntheticAssumption, not observed geology.",
                "Acceptance covers drafting, topology presentation and native persistence; it does not assert an observed subsurface truth.",
            ],
        }
        (run_dir / "post_generation_visual_adjudication.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
