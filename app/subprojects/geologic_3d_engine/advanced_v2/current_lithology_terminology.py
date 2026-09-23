"""Current, source-preserving terminology gate for Advanced V2 output.

The synthetic catalogue uses broad display labels, not laboratory soil
classifications or invented formal stratigraphic units.  Original wording is
retained as evidence while publication labels must pass this fail-closed gate.
"""
from __future__ import annotations


POLICY_ID = "ADV2-CURRENT-GEOLOGICAL-TERMINOLOGY-1.0"
REQUIRED_FIELDS = (
    "SourceLabel", "SourceYear", "SourceAuthority", "SourceUnitCode",
    "NormalizedLabelJa", "NormalizedLabelEn", "NormalizationAuthority",
    "VocabularyVersion", "TermStatus", "NormalizationNote",
)
PUBLICATION_STATUSES = {"Current", "DerivedDisplayLabel", "LocalRelativeUnit"}
FORBIDDEN_PUBLICATION_FRAGMENTS = (
    "旧期", "更新世以前", "礫混じり", "砂礫質", "泥炭・有機質泥", "礫質谷底",
)

MODEL_ADDED_NORMALIZATIONS = {
    "SYN-VALLEY-BASAL": ("れき質谷底堆積物（合成）", "Gravelly basal valley deposit (synthetic)"),
    "SYN-VALLEY-MIXED": ("砂泥質谷埋め堆積物（合成）", "Mixed sand-mud valley fill (synthetic)"),
    "SYN-VALLEY-FINE": ("細粒谷埋め堆積物（合成）", "Fine-grained valley fill (synthetic)"),
}


def terminology_record(unit_id: str, source_label: str, normalized_ja: str,
                       normalized_en: str) -> dict:
    """Build a traceable record without pretending a synthetic label is official."""
    return {
        "SourceLabel": str(source_label),
        "SourceYear": 2026,
        "SourceAuthority": "Advanced V2 synthetic catalogue",
        "SourceUnitCode": str(unit_id),
        "NormalizedLabelJa": str(normalized_ja),
        "NormalizedLabelEn": str(normalized_en),
        "NormalizationAuthority": (
            "JGS JGS 0051 current geomaterial terminology; GSJ Seamless V2/ZFK; "
            "ICS International Chronostratigraphic Chart; CGI/GeoSciML concepts"
        ),
        "VocabularyVersion": "JGS0051-current_checked-2026-09-17;GSJ-V2/ZFK-2025-12-17;ICS-2026/06",
        "TermStatus": "DerivedDisplayLabel",
        "NormalizationNote": (
            "Synthetic broad-prior display label. It is not a laboratory classification, "
            "formal formation name, or observed local unit. The original catalogue label "
            "is preserved separately in SourceLabel."
        ),
    }


def audit_publication_terminology(rows: list[dict]) -> dict:
    errors: list[str] = []
    for index, row in enumerate(rows):
        unit_id = str(row.get("unitId", f"index-{index}"))
        record = row.get("terminology")
        if not isinstance(record, dict):
            errors.append(f"MissingTerminologyRecord:{unit_id}")
            continue
        missing = [field for field in REQUIRED_FIELDS if field not in record]
        if missing:
            errors.append(f"MissingTerminologyFields:{unit_id}:{','.join(missing)}")
        status = record.get("TermStatus")
        if status not in PUBLICATION_STATUSES:
            errors.append(f"NonCurrentTermStatus:{unit_id}:{status}")
        label = str(record.get("NormalizedLabelJa", ""))
        for fragment in FORBIDDEN_PUBLICATION_FRAGMENTS:
            if fragment in label:
                errors.append(f"ForbiddenLegacyFragment:{unit_id}:{fragment}")
        if "更新世" in label and "更新統" not in label:
            errors.append(f"GeochronologyUsedForRockBody:{unit_id}:更新世")
    return {
        "policyId": POLICY_ID,
        "passed": not errors,
        "checkedUnitCount": len(rows),
        "allowedPublicationStatuses": sorted(PUBLICATION_STATUSES),
        "errors": errors,
    }


def require_current_publication_terminology(model: dict) -> dict:
    audit = audit_publication_terminology(model.get("faciesMetadata", []))
    metadata = {row.get("unitId"): row.get("terminology", {})
                for row in model.get("faciesMetadata", [])}
    for style in model.get("renderingLithologies", []):
        unit_id = style.get("unitId")
        record = metadata.get(unit_id)
        if not record:
            audit["errors"].append(f"RenderedUnitMissingTerminology:{unit_id}")
            continue
        if style.get("label") != record.get("NormalizedLabelJa"):
            audit["errors"].append(f"RenderedLabelNotNormalized:{unit_id}")
    audit["renderedUnitCount"] = len(model.get("renderingLithologies", []))
    audit["passed"] = not audit["errors"]
    model["terminologyCurrencyAudit"] = audit
    if not audit["passed"]:
        raise ValueError("current geological terminology gate rejected: " + ";".join(audit["errors"]))
    return audit


def normalize_model_added_lithologies(model: dict) -> dict:
    """Normalize units introduced after catalogue selection, before rendering."""
    metadata = model.setdefault("faciesMetadata", [])
    by_id = {row.get("unitId"): row for row in metadata}
    english = model.setdefault("advancedEnglishUnitLabels", {})
    for style in model.get("renderingLithologies", []):
        unit_id = style.get("unitId")
        if unit_id not in MODEL_ADDED_NORMALIZATIONS:
            continue
        normalized_ja, normalized_en = MODEL_ADDED_NORMALIZATIONS[unit_id]
        source_label = str(style.get("label", normalized_ja))
        style["label"] = normalized_ja
        english[unit_id] = normalized_en
        record = terminology_record(unit_id, source_label, normalized_ja, normalized_en)
        if unit_id in by_id:
            by_id[unit_id]["terminology"] = record
        else:
            row = {
                "unitId": unit_id,
                "materialRole": "SyntheticEventFill",
                "basisType": "SyntheticAssumption",
                "sourceIds": ["JGS-0051-CURRENT", "GSJ-SEAMLESS-V2-LEGEND"],
                "portrayalRole": "GeometricBody",
                "formationNameInvented": False,
                "localObservationClaim": False,
                "terminology": record,
            }
            metadata.append(row)
            by_id[unit_id] = row
    return model
