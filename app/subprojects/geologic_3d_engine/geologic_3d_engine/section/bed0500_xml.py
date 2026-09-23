"""Strict intake adapter for MLIT BED0500 (DTD 5.00) borehole XML."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .borehole_evidence import normalize_borehole


MAXIMUM_XML_BYTES = 20_000_000
SUPPORTED_DTD_VERSION = "5.00"
LITHOLOGY_ROW = "工学的地質区分名現場土質名"
BOTTOM_TAG = f"{LITHOLOGY_ROW}_下端深度"
LABEL_TAG = f"{LITHOLOGY_ROW}_{LITHOLOGY_ROW}"


def _required_text(parent, tag):
    values = [(node.text or "").strip() for node in parent.findall(f".//{tag}")]
    if len(values) != 1 or not values[0]:
        raise ValueError(f"BED0500 requires exactly one non-empty {tag}")
    return values[0]


def _number(text, name):
    try:
        value = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"BED0500 {name} must be numeric") from exc
    if not math.isfinite(value):
        raise ValueError(f"BED0500 {name} must be finite")
    return value


def _dms(degrees, minutes, seconds, latitude):
    deg = _number(degrees, "degrees")
    minute = _number(minutes, "minutes")
    second = _number(seconds, "seconds")
    if deg < 0 or not 0 <= minute < 60 or not 0 <= second < 60:
        raise ValueError("BED0500 DMS coordinate is invalid")
    result = deg + minute/60.0 + second/3600.0
    limit = 90 if latitude else 180
    if result > limit:
        raise ValueError("BED0500 coordinate exceeds geographic range")
    return result


def _decode_xml(raw):
    head = raw[:200].decode("ascii", errors="ignore")
    match = re.search(r'encoding=["\']([^"\']+)', head, re.IGNORECASE)
    encoding = (match.group(1) if match else "utf-8").lower().replace("-", "_")
    if encoding not in {"shift_jis", "shiftjis", "sjis", "cp932", "utf_8", "utf8"}:
        raise ValueError("unsupported BED0500 XML encoding")
    codec = "cp932" if encoding in {"shift_jis", "shiftjis", "sjis", "cp932"} else "utf-8"
    try:
        return raw.decode(codec)
    except UnicodeDecodeError as exc:
        raise ValueError("BED0500 XML byte encoding is invalid") from exc


def parse_bed0500_xml(path, *, horizontal_crs, vertical_datum,
                      source_id, source_url, evidence_status="Unverified"):
    """Parse one BED0500 log and pass it through the shared evidence gate.

    CRS and vertical datum are caller-declared because a format code alone is
    not silently treated as a coordinate transformation or height datum.
    """
    source = Path(path)
    raw = source.read_bytes()
    if not raw or len(raw) > MAXIMUM_XML_BYTES:
        raise ValueError("BED0500 XML size is invalid")
    text = _decode_xml(raw)
    if re.search(r"<!\s*(?:ENTITY|ATTLIST)\b", text, re.IGNORECASE):
        raise ValueError("BED0500 XML entities and attribute declarations are prohibited")
    text = re.sub(r"^\ufeff?<\?xml[^>]*\?>", "", text, count=1, flags=re.IGNORECASE)
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, count=1, flags=re.IGNORECASE)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError("BED0500 XML is not well formed") from exc
    if root.tag != "ボーリング情報" or root.attrib.get("DTD_version") != SUPPORTED_DTD_VERSION:
        raise ValueError("only BED0500 DTD version 5.00 is supported")

    longitude = _dms(_required_text(root,"経度_度"), _required_text(root,"経度_分"),
                     _required_text(root,"経度_秒"), False)
    latitude = _dms(_required_text(root,"緯度_度"), _required_text(root,"緯度_分"),
                    _required_text(root,"緯度_秒"), True)
    collar = _number(_required_text(root,"孔口標高"), "collar elevation")
    total = _number(_required_text(root,"総削孔長"), "total depth")
    name_nodes = [(node.text or "").strip() for node in root.findall(".//ボーリング名")]
    serial_nodes = [(node.text or "").strip() for node in root.findall(".//ボーリング連番")]
    if len(name_nodes) != 1 or len(serial_nodes) != 1 or not (name_nodes[0] or serial_nodes[0]):
        raise ValueError("BED0500 borehole identity is missing or duplicated")
    identifier = name_nodes[0] or f"BED-{serial_nodes[0]}"
    core = root.find("コア情報")
    if core is None:
        raise ValueError("BED0500 core information is missing")
    intervals = []
    top = 0.0
    for row in core.findall(LITHOLOGY_ROW):
        bottom = _number(_required_text(row, BOTTOM_TAG), "lithology bottom depth")
        label = _required_text(row, LABEL_TAG)
        intervals.append({"topDepthM": top, "bottomDepthM": bottom,
            "sourceLabel": label, "normalizedLithology": label,
            "termStatus": "Unverified", "evidenceStatus": evidence_status,
            "normalizationNote": "Source label retained; current vocabulary normalization pending"})
        top = bottom
    record = {"boreholeId": identifier, "longitude": longitude, "latitude": latitude,
        "collarElevationM": collar, "totalDepthM": total,
        "horizontalCrs": horizontal_crs, "verticalDatum": vertical_datum,
        "sourceId": source_id, "sourceUrl": source_url,
        "exchangeFormatVersion": "BED0500-DTD-5.00", "intervals": intervals}
    result = normalize_borehole(record)
    result.update({"sourceArtifactSha256": hashlib.sha256(raw).hexdigest(),
                   "sourceByteLength": len(raw),
                   "coordinateFormat": "DegreesMinutesSeconds",
                   "formatGeodeticSystemCode": _required_text(root,"測地系"),
                   "parserBoundary": "BED0500StructureOnly_NoAutomaticDatumConversionOrTermNormalization"})
    return result
