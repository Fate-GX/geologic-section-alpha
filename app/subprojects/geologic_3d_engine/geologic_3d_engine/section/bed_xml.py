"""Version-dispatching, fail-closed MLIT borehole XML intake."""
from __future__ import annotations

from pathlib import Path
import re

from .bed0210_xml import parse_bed0210_xml
from .bed0300_xml import parse_bed0300_xml
from .bed0400_xml import parse_bed0400_xml
from .bed0500_xml import MAXIMUM_XML_BYTES, _decode_xml, parse_bed0500_xml


PARSERS = {
    "2.10": parse_bed0210_xml,
    "3.00": parse_bed0300_xml,
    "4.00": parse_bed0400_xml,
    "5.00": parse_bed0500_xml,
}


def detect_bed_dtd_version(path):
    raw = Path(path).read_bytes()
    if not raw or len(raw) > MAXIMUM_XML_BYTES:
        raise ValueError("BED XML size is invalid")
    text = _decode_xml(raw)
    match = re.search(r'<ボーリング情報\b[^>]*\bDTD_version=["\']([^"\']+)["\']', text)
    if not match:
        raise ValueError("BED XML DTD version is missing")
    return match.group(1)


def parse_bed_xml(path, **kwargs):
    version = detect_bed_dtd_version(path)
    parser = PARSERS.get(version)
    if parser is None:
        raise ValueError(f"unsupported BED XML DTD version: {version}")
    return parser(path, **kwargs)
