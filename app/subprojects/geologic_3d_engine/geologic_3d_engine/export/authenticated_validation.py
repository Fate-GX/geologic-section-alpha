"""Authenticated wrapper for a validated integrity envelope.

HMAC-SHA-256 is intentionally limited to a trusted local boundary whose
producer and consumer can protect a shared secret. Public/distributed review
requires an asymmetric-signature contract and is outside this module.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
from typing import Any, MutableSet

from .contract_integrity import canonical_json_bytes, sha256_hex

AUTHENTICATION_VERSION = "GEO3D-HMAC-AUTH-1.0"
ALGORITHM = "HMAC-SHA-256"
MINIMUM_KEY_BYTES = 32
NONCE_PATTERN = re.compile(r"^[0-9a-f]{32,128}$")


def _utc(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be an ISO-8601 UTC value ending in Z")
    parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo != dt.timezone.utc:
        raise ValueError("timestamp must use UTC")
    return parsed


def _key(secret: bytes) -> bytes:
    if not isinstance(secret, bytes) or len(secret) < MINIMUM_KEY_BYTES:
        raise ValueError("HMAC key must contain at least 32 bytes")
    return secret


def _unsigned(envelope: dict) -> dict:
    return {key: value for key, value in envelope.items() if key != "macHex"}


def build_authenticated_validation(
    integrity_envelope: dict,
    *,
    secret: bytes,
    key_id: str,
    purpose: str,
    issued_at_utc: str,
    expires_at_utc: str,
    nonce: str,
) -> dict:
    _key(secret)
    if not key_id or not purpose:
        raise ValueError("keyId and purpose are required")
    if not NONCE_PATTERN.fullmatch(nonce):
        raise ValueError("nonce must be 32-128 lowercase hexadecimal characters")
    issued, expires = _utc(issued_at_utc), _utc(expires_at_utc)
    if expires <= issued:
        raise ValueError("expiresAtUtc must be after issuedAtUtc")
    result = {
        "authenticationVersion": AUTHENTICATION_VERSION,
        "algorithm": ALGORITHM,
        "keyId": key_id,
        "purpose": purpose,
        "issuedAtUtc": issued_at_utc,
        "expiresAtUtc": expires_at_utc,
        "nonce": nonce,
        "integrityEnvelopeSha256": sha256_hex(canonical_json_bytes(integrity_envelope)),
        "integrityEnvelope": integrity_envelope,
    }
    result["macHex"] = hmac.new(
        secret, canonical_json_bytes(result), hashlib.sha256).hexdigest()
    return result


def verify_authenticated_validation(
    authenticated: dict,
    *,
    trusted_keys: dict[str, bytes],
    expected_purpose: str,
    now_utc: str,
    used_nonces: Any,
    maximum_lifetime_seconds: int = 900,
    maximum_future_skew_seconds: int = 30,
) -> dict:
    allowed = {
        "authenticationVersion", "algorithm", "keyId", "purpose", "issuedAtUtc",
        "expiresAtUtc", "nonce", "integrityEnvelopeSha256", "integrityEnvelope", "macHex",
    }
    unknown = sorted(set(authenticated) - allowed)
    missing = sorted(allowed - set(authenticated))
    if unknown or missing:
        raise ValueError(f"invalid authentication fields; missing={missing}; unknown={unknown}")
    if authenticated["authenticationVersion"] != AUTHENTICATION_VERSION:
        raise ValueError("unsupported authenticationVersion")
    if authenticated["algorithm"] != ALGORITHM:
        raise ValueError("unsupported authentication algorithm")
    if authenticated["purpose"] != expected_purpose:
        raise ValueError("authentication purpose mismatch")
    key_id = authenticated["keyId"]
    if key_id not in trusted_keys:
        raise ValueError("unknown or revoked keyId")
    secret = _key(trusted_keys[key_id])
    nonce = authenticated["nonce"]
    if not NONCE_PATTERN.fullmatch(nonce):
        raise ValueError("invalid nonce")
    expected_mac = hmac.new(
        secret, canonical_json_bytes(_unsigned(authenticated)), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_mac, authenticated["macHex"]):
        raise ValueError("authentication MAC mismatch")
    integrity = authenticated["integrityEnvelope"]
    if sha256_hex(canonical_json_bytes(integrity)) != authenticated["integrityEnvelopeSha256"]:
        raise ValueError("authenticated integrity-envelope digest mismatch")
    issued = _utc(authenticated["issuedAtUtc"])
    expires = _utc(authenticated["expiresAtUtc"])
    now = _utc(now_utc)
    if expires <= issued:
        raise ValueError("invalid authentication lifetime")
    if (expires - issued).total_seconds() > maximum_lifetime_seconds:
        raise ValueError("authentication lifetime exceeds policy")
    if issued > now + dt.timedelta(seconds=maximum_future_skew_seconds):
        raise ValueError("authentication issued too far in the future")
    if now >= expires:
        raise ValueError("authentication expired")
    replay_key = (key_id, nonce)
    if hasattr(used_nonces, "consume"):
        if not used_nonces.consume(key_id, nonce, authenticated["expiresAtUtc"], now_utc):
            raise ValueError("authentication nonce replay detected")
    else:
        if replay_key in used_nonces:
            raise ValueError("authentication nonce replay detected")
        used_nonces.add(replay_key)
    return integrity
