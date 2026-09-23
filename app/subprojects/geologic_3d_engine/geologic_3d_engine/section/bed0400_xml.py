"""Strict intake adapter for MLIT BED0400 (DTD 4.00) borehole XML."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .bed0500_xml import MAXIMUM_XML_BYTES, _decode_xml, _dms, _number, _required_text
from .borehole_evidence import normalize_borehole


SUPPORTED_DTD_VERSION = "4.00"
LITHOLOGY_ROW = "工学的地質区分名現場土質名"
BOTTOM_TAG = f"{LITHOLOGY_ROW}_下端深度"
LABEL_TAG = f"{LITHOLOGY_ROW}_{LITHOLOGY_ROW}"


def parse_bed0400_xml(path, *, horizontal_crs, vertical_datum,
                      source_id, source_url, evidence_status="Unverified",
                      horizontal_crs_status="Declared",
                      vertical_datum_status="Declared",
                      collar_elevation_accuracy_status=None,
                      horizontal_position_accuracy_status=None):
    """Parse BED0400 while preserving its source labels and accuracy declarations."""
    source = Path(path)
    raw = source.read_bytes()
    if not raw or len(raw) > MAXIMUM_XML_BYTES:
        raise ValueError("BED0400 XML size is invalid")
    text = _decode_xml(raw)
    if re.search(r"<!\s*(?:ENTITY|ATTLIST)\b", text, re.IGNORECASE):
        raise ValueError("BED0400 XML entities and attribute declarations are prohibited")
    text = re.sub(r"^\ufeff?<\?xml[^>]*\?>", "", text, count=1, flags=re.IGNORECASE)
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, count=1, flags=re.IGNORECASE)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError("BED0400 XML is not well formed") from exc
    if root.tag != "ボーリング情報" or root.attrib.get("DTD_version") != SUPPORTED_DTD_VERSION:
        raise ValueError("only BED0400 DTD version 4.00 is supported")

    longitude = _dms(_required_text(root, "経度_度"), _required_text(root, "経度_分"),
                     _required_text(root, "経度_秒"), False)
    latitude = _dms(_required_text(root, "緯度_度"), _required_text(root, "緯度_分"),
                    _required_text(root, "緯度_秒"), True)
    collar = _number(_required_text(root, "孔口標高"), "collar elevation")
    total = _number(_required_text(root, "総削孔長"), "total depth")
    identifier = _required_text(root, "ボーリング名")
    core = root.find("コア情報")
    if core is None:
        raise ValueError("BED0400 core information is missing")
    intervals = []
    top = 0.0
    for row in core.findall(LITHOLOGY_ROW):
        bottom = _number(_required_text(row, BOTTOM_TAG), "lithology bottom depth")
        label = _required_text(row, LABEL_TAG)
        intervals.append({
            "topDepthM": top, "bottomDepthM": bottom,
            "sourceLabel": label, "normalizedLithology": label,
            "termStatus": "Unverified", "evidenceStatus": evidence_status,
            "normalizationNote": "Source label retained; current vocabulary normalization pending",
        })
        top = bottom
    result = normalize_borehole({
        "boreholeId": identifier, "longitude": longitude, "latitude": latitude,
        "collarElevationM": collar, "totalDepthM": total,
        "horizontalCrs": horizontal_crs, "verticalDatum": vertical_datum,
        "sourceId": source_id, "sourceUrl": source_url,
        "exchangeFormatVersion": "BED0400-DTD-4.00",
        "horizontalCrsStatus": horizontal_crs_status,
        "verticalDatumStatus": vertical_datum_status,
        **({"collarElevationAccuracyStatus": collar_elevation_accuracy_status}
           if collar_elevation_accuracy_status is not None else {}),
        **({"horizontalPositionAccuracyStatus": horizontal_position_accuracy_status}
           if horizontal_position_accuracy_status is not None else {}),
        "intervals": intervals,
    })
    result.update({
        "sourceArtifactSha256": hashlib.sha256(raw).hexdigest(),
        "sourceByteLength": len(raw),
        "coordinateFormat": "DegreesMinutesSeconds",
        "formatGeodeticSystemCode": _required_text(root, "測地系"),
        "coordinateAcquisitionMethodCode": _required_text(root, "取得方法コード"),
        "coordinateReadingPrecisionCode": _required_text(root, "読取精度コード"),
        "parserBoundary": "BED0400StructureOnly_NoAutomaticDatumConversionOrTermNormalization",
    })
    return result
