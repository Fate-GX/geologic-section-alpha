"""Capture and normalize one official KuniJiban BED0300 candidate.

This is an evidence-intake boundary, not a geological correlation step.  The
provider's approval label and the exchange-format reference codes are retained,
but neither is promoted to independent verification.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import urllib.request

from ..section.bed_xml import parse_bed_xml
from .kunijiban_candidate_metadata import extract_candidate_metadata


RECORD_URL = "https://www.kunijiban.pwri.go.jp/viewer/refer/?data=boring&type=xml&id={record_id}"
MAXIMUM_RECORD_ID = 2_147_483_647


def angular_resolution_metres(latitude_degrees, arc_seconds):
    """Convert angular grid spacing to local GRS80 meridian/parallel spacing.

    This reports nominal coordinate resolution, not positional uncertainty or
    survey accuracy.
    """
    latitude=float(latitude_degrees);seconds=float(arc_seconds)
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("latitude for coordinate resolution is invalid")
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("angular coordinate resolution must be positive")
    semi_major=6378137.0
    inverse_flattening=298.257222101
    flattening=1.0/inverse_flattening
    eccentricity_squared=flattening*(2.0-flattening)
    phi=math.radians(latitude)
    denominator=math.sqrt(1.0-eccentricity_squared*math.sin(phi)**2)
    prime_vertical=semi_major/denominator
    meridional=semi_major*(1.0-eccentricity_squared)/(denominator**3)
    radians=math.radians(seconds/3600.0)
    return [prime_vertical*math.cos(phi)*radians,meridional*radians]


def _record_id(value):
    if isinstance(value, bool):
        raise ValueError("KuniJiban record ID must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("KuniJiban record ID must be a positive integer") from exc
    if str(parsed) != str(value).strip() or not 0 < parsed <= MAXIMUM_RECORD_ID:
        raise ValueError("KuniJiban record ID must be a positive integer")
    return parsed


def normalize_captured_record(xml_path, *, record_id, provider_approval_label=None):
    """Normalize a supported captured record using version-specific format semantics."""
    identifier = _record_id(record_id)
    url = RECORD_URL.format(record_id=identifier)
    metadata=extract_candidate_metadata(Path(xml_path).read_bytes())
    version=metadata["dtdVersion"]
    if version not in {"3.00","4.00"}:
        raise ValueError("KuniJiban selected-record intake currently supports BED 3.00 and 4.00")
    horizontal_crs=metadata["formatHorizontalCrs"]
    if horizontal_crs not in {"EPSG:4612","EPSG:6668"}:
        raise ValueError("KuniJiban record geodetic-system code is unresolved")
    result = parse_bed_xml(
        xml_path,
        horizontal_crs=horizontal_crs,
        vertical_datum="TokyoPeil",
        source_id=f"KUNIJIBAN-BORING-{identifier}",
        source_url=url,
        evidence_status="Unverified",
        horizontal_crs_status="Declared",
        vertical_datum_status="Declared",
        collar_elevation_accuracy_status="Unverified",
        horizontal_position_accuracy_status="DeclaredResolutionOnly",
    )
    result.update({
        "schemaVersion": ("KuniJibanBED0300Candidate-1.0" if version=="3.00"
                          else "KuniJibanBED0400Candidate-1.0"),
        "providerRecordId": identifier,
        "providerApprovalLabel": provider_approval_label,
        "providerApprovalInterpretation": "PreservedLabel_NotIndependentEvidenceVerification",
        "providerDataStatus": "OfficialSiteStatesCurrentlyPublishedDataAreUninspected",
        "coordinateAcquisitionInterpretation": metadata["coordinateMethodClass"],
        "coordinateResolutionInterpretation": "DeclaredAngularResolutionOnly",
        "declaredReadingResolutionArcSeconds": metadata["declaredResolutionArcSeconds"],
        "referenceSystemEvidence": {
            "sourceId": ("MLIT-BED0300-H20-12-APPENDIX" if version=="3.00"
                         else "MLIT-BED0400-H28-10"),
            "geodeticLocator": ("Appendix 5, Table 2-6: code 1 = JGD2000" if version=="3.00"
                else "Appendix 5, Table 2-7: code 01 = JGD2000 and code 02 = JGD2011"),
            "verticalLocator": ("Appendix 5, printed page 付5-17: collar elevation uses T.P. in metres"
                if version=="3.00" else "Appendix 5, printed page 付5-15: collar elevation uses T.P. in metres"),
            "interpretationBoundary": "Format semantics only; no independent coordinate or levelling accuracy for this record",
        },
        "sectionConstraintAuthorized": False,
        "authorizationBlockers": [
            *((["JGD2000ToJGD2011TransformNotApplied"] if horizontal_crs=="EPSG:4612" else [])),
            "DeclaredCoordinateResolutionIsNotIndividualSurveyAccuracy",
            "CollarElevationAccuracyUnverified",
            "LithologyTerminologyNotNormalized",
            "IndependentEvidenceReviewNotCompleted",
        ],
    })
    if result["declaredReadingResolutionArcSeconds"] is not None:
        result["nominalReadingResolutionMetresLonLat"] = angular_resolution_metres(
            result["latitude"],result["declaredReadingResolutionArcSeconds"])
    unsigned = {key: value for key, value in result.items() if key != "recordSha256"}
    result["recordSha256"] = hashlib.sha256(json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    return result


def capture_and_normalize_record(record_id, output_directory, *,
                                 provider_approval_label=None, timeout=30):
    """Download public XML, preserve its bytes, then use the strict parser."""
    identifier = _record_id(record_id)
    url = RECORD_URL.format(record_id=identifier)
    request = urllib.request.Request(url, headers={
        "User-Agent": "geologic-3d-engine-research/1.0",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        content_type = response.headers.get("Content-Type", "")
    if not raw or len(raw) > 8_000_000:
        raise ValueError("KuniJiban XML response size is invalid")
    if "xml" not in content_type.lower() and not raw.lstrip().startswith(b"<?xml"):
        raise ValueError("KuniJiban response is not XML")

    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    version=extract_candidate_metadata(raw)["dtdVersion"]
    version_slug={"3.00":"0300","4.00":"0400"}.get(version,version.replace(".",""))
    xml_path = output / f"kunijiban_{identifier}_bed{version_slug}.xml"
    xml_tmp = xml_path.with_suffix(".xml.tmp")
    xml_tmp.write_bytes(raw)
    xml_tmp.replace(xml_path)
    try:
        result = normalize_captured_record(
            xml_path, record_id=identifier,
            provider_approval_label=provider_approval_label)
    except Exception:
        # Preserve the source bytes for diagnosis, but never issue a normalized
        # candidate when strict parsing fails.
        raise
    result["httpContentType"] = content_type
    unsigned = {key: value for key, value in result.items() if key != "recordSha256"}
    result["recordSha256"] = hashlib.sha256(json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    json_path = output / f"kunijiban_{identifier}_candidate.json"
    json_tmp = json_path.with_suffix(".json.tmp")
    json_tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    json_tmp.replace(json_path)
    return result, xml_path, json_path
