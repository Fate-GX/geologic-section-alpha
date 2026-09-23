"""GUI backend for strict BED0500 XML to normalized borehole JSON intake."""
import json
from pathlib import Path

from .section.bed0500_xml import parse_bed0500_xml


def execute_bed0500_import(xml_path, output_parent, *, horizontal_crs,
                           vertical_datum, source_id, source_url):
    record = parse_bed0500_xml(xml_path, horizontal_crs=horizontal_crs,
        vertical_datum=vertical_datum, source_id=source_id,
        source_url=source_url, evidence_status="Unverified")
    result = {"schemaVersion":"NormalizedPublicBoreholeCollection-1.0",
        "boreholes":[record], "recordCount":1,
        "evidenceState":"Unverified_RequiresArtifactAndDatumReview",
        "interpretationBoundary":"ObservedLogStructure_NotCorrelatedGeologicUnits"}
    output = Path(output_parent).resolve()/"bed0500_import"
    output.mkdir(parents=True, exist_ok=True)
    target = output/"normalized_boreholes.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result, target
