"""Strict intake adapter for legacy MLIT BED0210 (DTD 2.10) borehole XML.

This adapter preserves the source coordinate and vocabulary.  It does not
interpret the legacy geodetic-system code, transform datums, or normalize
lithology names.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .bed0500_xml import MAXIMUM_XML_BYTES, _decode_xml, _dms, _number, _required_text
from .borehole_evidence import normalize_borehole


SUPPORTED_DTD_VERSION = "2.10"
LITHOLOGY_ROW = "土質岩種区分"
BOTTOM_TAG = f"{LITHOLOGY_ROW}_下端深度"
LABEL_TAG = f"{LITHOLOGY_ROW}_土質岩種区分1"


def parse_bed0210_xml(path, *, horizontal_crs, vertical_datum,
                      source_id, source_url, evidence_status="Unverified"):
    """Parse one BED0210 log through the shared borehole evidence gate.

    ``horizontal_crs`` and ``vertical_datum`` are mandatory declarations by
    the caller.  The legacy ``測地系`` code is retained only as source evidence;
    it is not silently promoted to a modern CRS.
    """
    source = Path(path)
    raw = source.read_bytes()
    if not raw or len(raw) > MAXIMUM_XML_BYTES:
        raise ValueError("BED0210 XML size is invalid")
    text = _decode_xml(raw)
    if re.search(r"<!\s*(?:ENTITY|ATTLIST)\b", text, re.IGNORECASE):
        raise ValueError("BED0210 XML entities and attribute declarations are prohibited")
    text = re.sub(r"^\ufeff?<\?xml[^>]*\?>", "", text, count=1, flags=re.IGNORECASE)
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, count=1, flags=re.IGNORECASE)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError("BED0210 XML is not well formed") from exc
    if root.tag != "ボーリング情報" or root.attrib.get("DTD_version") != SUPPORTED_DTD_VERSION:
        raise ValueError("only BED0210 DTD version 2.10 is supported")

    longitude = _dms(_required_text(root, "経度_度"), _required_text(root, "経度_分"),
                     _required_text(root, "経度_秒"), False)
    latitude = _dms(_required_text(root, "緯度_度"), _required_text(root, "緯度_分"),
                    _required_text(root, "緯度_秒"), True)
    collar = _number(_required_text(root, "孔口標高"), "collar elevation")
    total = _number(_required_text(root, "総掘進長"), "total depth")
    identifier = _required_text(root, "ボーリング名")
    core = root.find("コア情報")
    if core is None:
        raise ValueError("BED0210 core information is missing")
    intervals = []
    top = 0.0
    for row in core.findall(LITHOLOGY_ROW):
        bottom = _number(_required_text(row, BOTTOM_TAG), "lithology bottom depth")
        label = _required_text(row, LABEL_TAG)
        intervals.append({
            "topDepthM": top,
            "bottomDepthM": bottom,
            "sourceLabel": label,
            "normalizedLithology": label,
            "termStatus": "Unverified",
            "evidenceStatus": evidence_status,
            "normalizationNote": "Legacy source label retained; current vocabulary normalization pending",
        })
        top = bottom
    record = {
        "boreholeId": identifier,
        "longitude": longitude,
        "latitude": latitude,
        "collarElevationM": collar,
        "totalDepthM": total,
        "horizontalCrs": horizontal_crs,
        "verticalDatum": vertical_datum,
        "sourceId": source_id,
        "sourceUrl": source_url,
        "exchangeFormatVersion": "BED0210-DTD-2.10",
        "intervals": intervals,
    }
    result = normalize_borehole(record)
    result.update({
        "sourceArtifactSha256": hashlib.sha256(raw).hexdigest(),
        "sourceByteLength": len(raw),
        "coordinateFormat": "DegreesMinutesSeconds",
        "formatGeodeticSystemCode": _required_text(root, "測地系"),
        "parserBoundary": "BED0210StructureOnly_NoAutomaticDatumConversionOrTermNormalization",
    })
    return result
