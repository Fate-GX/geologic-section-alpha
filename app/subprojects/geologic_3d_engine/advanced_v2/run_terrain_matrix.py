from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from nationwide_pipeline import run_advanced_japan_section
from route_request import AdvancedJapanSectionRequest
from synthetic_terrain_qa import multiscale_mountain_profile, audit_natural_terrain_texture


def _profile(kind, x):
    u = x / 500.0
    if kind == "plain":
        return 8.0 + 0.7*u + 0.35*math.sin(2*math.pi*u)
    if kind == "hills":
        return 55.0 + 13*math.sin(4*math.pi*u) + 5*math.sin(10*math.pi*u+0.4)
    if kind == "mountain":
        raise ValueError("mountain profile is generated as one multi-scale realization")
    if kind == "gorge":
        return 310.0 - 145*math.exp(-((u-.58)/.115)**2) + 12*u
    if kind == "piedmont":
        return 270.0 - 210/(1+math.exp(-(u-.40)*13)) + 5*math.sin(3*math.pi*u)
    if kind == "coastal":
        return 2.3 + .45*u + .22*math.sin(3*math.pi*u)
    if kind == "artificial":
        # Synthetic cut-and-fill bench. Typed evidence, rather than profile
        # shape alone, is what authorizes the artificial morphology class.
        natural = 42.0 + 9.0*math.sin(2*math.pi*u)
        return round(natural / 4.0) * 4.0
    raise ValueError(kind)


CASES = {
    "plain": ("terrace deposits", None),
    "hills": ("sandstone and mudstone", None),
    "mountain": ("andesite lava", None),
    "gorge": ("accretionary chert", None),
    "piedmont": ("granite", [{"class":"MountainFrontPiedmont",
                                "basisType":"SyntheticTestEvidence"}]),
    "coastal": ("terrace deposits", [{"class":"coastal lowland", "basisType":"SyntheticTestEvidence"}]),
    "artificial": ("mudstone", [{"class":"ArtificiallyModifiedOrUnresolved",
                                  "basisType":"SyntheticTestEvidence"}]),
}


def _case_seed(kind):
    """Keep each diagnostic realization stable in batch and single-case runs."""
    try:
        return 880100 + tuple(CASES).index(kind)
    except ValueError as exc:
        raise ValueError(f"unknown terrain-matrix case: {kind}") from exc


def _acquisition(kind, lithology, landform):
    def acquire(_root, route, _spacing, output, _method, _cache):
        stations = [float(x) for x in range(0, 501, 5 if kind == "mountain" else 10)]
        elevations = (multiscale_mountain_profile(stations) if kind == "mountain" else
                      [_profile(kind, x) for x in stations])
        rows = [{"stationM":x, "longitude":route[0][0], "latitude":route[0][1],
                 "elevationM":z} for x, z in zip(stations, elevations)]
        legend = {"symbol":f"SYN-{kind.upper()}", "title":lithology,
                  "formationAge_ja":"合成試験", "formationAge_en":"Synthetic test",
                  "lithology_ja":lithology, "lithology_en":lithology,
                  "value":"999999", "r":153, "g":153, "b":153}
        plan = {"schemaVersion":"PlanEvidenceBundle-1.0", "routeLonLat":route,
                "terrainProfile":rows,
                "layers":[{"evidence_kind":"DEM", "source_id":"SYNTHETIC-TERRAIN-MATRIX",
                           "canonical_url":"local://synthetic-test", "content_sha256":"0"*64}],
                "surfaceGeology":{"sourceId":"SYNTHETIC-DOMAIN-MATRIX",
                    "sourceEdition":"SyntheticTestOnly",
                    "samples":[{"stationM":row["stationM"], "legend":legend} for row in rows]}}
        if landform:
            plan["landformEvidence"] = landform
        if kind == "mountain":
            texture_audit = audit_natural_terrain_texture(stations, elevations)
            if not texture_audit["passed"]:
                raise ValueError("synthetic mountain texture gate failed")
            plan["syntheticTerrainTextureAudit"] = texture_audit
        Path(output, "plan_evidence_bundle.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return acquire


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--case", choices=tuple(CASES), help="run one matrix case")
    args = parser.parse_args()
    root = HERE.parents[2]
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    selected = CASES.items() if args.case is None else [(args.case, CASES[args.case])]
    for kind, (lithology, landform) in selected:
        request = AdvancedJapanSectionRequest(138.0, 36.0, 500.0, 90.0, 10.0,
                                               _case_seed(kind), "Show", True, "Standard")
        result = run_advanced_japan_section(
            root, request, args.output, acquire_plan=_acquisition(kind, lithology, landform),
            native_dwg=args.native)
        results.append({"case":kind, "passed":result.get("passed"),
                        "terrainMorphology":result.get("terrainMorphologyClassification"),
                        "manifestPath":result.get("manifestPath"),
                        "artifacts":result.get("artifacts", [])})
    summary = args.output / "terrain_matrix_summary.json"
    summary.write_text(json.dumps({"schemaVersion":"AdvancedTerrainMatrix-1.0",
        "syntheticTestOnly":True, "results":results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
