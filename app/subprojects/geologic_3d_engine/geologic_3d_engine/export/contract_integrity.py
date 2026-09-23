"""Cross-language integrity envelope for the AutoCAD handoff contract."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import unicodedata
from typing import Any

ENVELOPE_VERSION = "1.0"
CANONICALIZATION_VERSION = "GEO3D-JCS-LIKE-1.0"


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite number is prohibited")
        return 0.0 if value == 0.0 else value
    if isinstance(value, dict):
        return {_normalize(str(key)): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if value is None or isinstance(value, (bool, int)):
        return value
    raise ValueError(f"unsupported contract value type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(_normalize(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_integrity_envelope(payload: dict, validation: dict,
                             validator_version: str) -> dict:
    payload_bytes = canonical_json_bytes(payload)
    payload_digest = sha256_hex(payload_bytes)
    bound_validation = dict(validation)
    bound_validation.update({"payloadSha256": payload_digest,
                             "validatorVersion": validator_version})
    validation_bytes = canonical_json_bytes(bound_validation)
    return {"envelopeVersion": ENVELOPE_VERSION,
            "canonicalizationVersion": CANONICALIZATION_VERSION,
            "payloadEncoding": "base64-utf8-json",
            "payloadSha256": payload_digest,
            "payloadBase64": base64.b64encode(payload_bytes).decode("ascii"),
            "validationSha256": sha256_hex(validation_bytes),
            "validationBase64": base64.b64encode(validation_bytes).decode("ascii")}


def verify_integrity_envelope(envelope: dict) -> tuple[dict, dict]:
    if envelope.get("envelopeVersion") != ENVELOPE_VERSION:
        raise ValueError("unsupported envelopeVersion")
    if envelope.get("canonicalizationVersion") != CANONICALIZATION_VERSION:
        raise ValueError("unsupported canonicalizationVersion")
    if envelope.get("payloadEncoding") != "base64-utf8-json":
        raise ValueError("unsupported payloadEncoding")
    try:
        payload_bytes = base64.b64decode(envelope["payloadBase64"], validate=True)
        validation_bytes = base64.b64decode(envelope["validationBase64"], validate=True)
    except Exception as error:
        raise ValueError("invalid envelope base64") from error
    if sha256_hex(payload_bytes) != envelope.get("payloadSha256"):
        raise ValueError("payload digest mismatch")
    if sha256_hex(validation_bytes) != envelope.get("validationSha256"):
        raise ValueError("validation digest mismatch")
    payload = json.loads(payload_bytes.decode("utf-8"))
    validation = json.loads(validation_bytes.decode("utf-8"))
    if validation.get("payloadSha256") != envelope["payloadSha256"]:
        raise ValueError("validation is not bound to payload")
    if not validation.get("passed", False):
        raise ValueError("validation did not pass")
    if canonical_json_bytes(payload) != payload_bytes:
        raise ValueError("payload violates canonicalization contract")
    if canonical_json_bytes(validation) != validation_bytes:
        raise ValueError("validation violates canonicalization contract")
    return payload, validation
