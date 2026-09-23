"""GUI backend for applying one reviewed geographic transform record."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from .section.borehole_evidence import apply_geographic_transform_record


def execute_borehole_geographic_transform(collection_path, transform_path,
                                           output_parent):
    collection_source=Path(collection_path).resolve()
    transform_source=Path(transform_path).resolve()
    collection=json.loads(collection_source.read_text(encoding="utf-8"))
    transform=json.loads(transform_source.read_text(encoding="utf-8"))
    records=collection.get("boreholes") if isinstance(collection,dict) else None
    if not isinstance(records,list) or len(records)!=1:
        raise ValueError("現在の変換画面は1孔だけのboreholes配列を要求します。")
    transformed=apply_geographic_transform_record(records[0],transform)
    result={
        "schemaVersion":"NormalizedBoreholeEvidenceCollection-1.0",
        "source":"EvidenceBoundGeographicTransformation",
        "inputCollectionSha256":hashlib.sha256(collection_source.read_bytes()).hexdigest(),
        "transformArtifactSha256":hashlib.sha256(transform_source.read_bytes()).hexdigest(),
        "boreholes":[transformed],
        "correlationState":"NotCorrelated",
        "sectionConstraintAuthorized":bool(transformed["elevationConstraintAuthorized"]),
        "authorizationBoundary":"CoordinateTransformOnly_NoCorrelationAuthorization",
    }
    output=Path(output_parent).resolve()/"borehole_coordinate_transform"
    output.mkdir(parents=True,exist_ok=True)
    target=output/"transformed_boreholes.json"
    temporary=target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temporary.replace(target)
    return result,target
