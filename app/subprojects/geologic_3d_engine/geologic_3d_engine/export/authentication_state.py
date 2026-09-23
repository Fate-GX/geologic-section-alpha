"""Persistent replay defense and key-rotation policy for local HMAC validation."""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path
from typing import Mapping

from .authenticated_validation import verify_authenticated_validation
from .contract_integrity import canonical_json_bytes, verify_integrity_envelope

ALLOWED_KEY_STATUSES = {"Active", "VerifyOnly", "Revoked"}


def _utc(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("policy timestamp must be UTC and end in Z")
    return dt.datetime.fromisoformat(value[:-1] + "+00:00")


class SqliteNonceStore:
    """Atomic nonce consumption using a database uniqueness constraint."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS consumed_nonce ("
                "key_id TEXT NOT NULL, nonce TEXT NOT NULL, expires_at_utc TEXT NOT NULL, "
                "consumed_at_utc TEXT NOT NULL, PRIMARY KEY (key_id, nonce))")
            connection.commit()
        finally:
            connection.close()

    def consume(self, key_id: str, nonce: str, expires_at_utc: str, now_utc: str) -> bool:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level="IMMEDIATE")
        try:
            connection.execute(
                "INSERT INTO consumed_nonce(key_id,nonce,expires_at_utc,consumed_at_utc) "
                "VALUES(?,?,?,?)", (key_id, nonce, expires_at_utc, now_utc))
            connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            connection.close()

    def prune_expired(self, now_utc: str) -> int:
        _utc(now_utc)
        connection = sqlite3.connect(self.path, timeout=30, isolation_level="IMMEDIATE")
        try:
            cursor = connection.execute(
                "DELETE FROM consumed_nonce WHERE expires_at_utc <= ?", (now_utc,))
            count = int(cursor.rowcount)
            connection.commit()
            return count
        finally:
            connection.close()


def validate_key_policies(policies: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for policy in policies:
        allowed = {"keyId", "status", "notBeforeUtc", "notAfterUtc", "purposes"}
        if set(policy) != allowed:
            raise ValueError("key policy fields are incomplete or unsupported")
        key_id, status = policy["keyId"], policy["status"]
        if not key_id or key_id in result:
            raise ValueError("keyId must be non-empty and unique")
        if status not in ALLOWED_KEY_STATUSES:
            raise ValueError("unsupported key status")
        if _utc(policy["notAfterUtc"]) <= _utc(policy["notBeforeUtc"]):
            raise ValueError("key policy validity interval is empty")
        if not isinstance(policy["purposes"], list) or not policy["purposes"]:
            raise ValueError("key policy purposes are required")
        result[key_id] = dict(policy)
    return result


def verification_key(
    *, key_id: str, purpose: str, now_utc: str, secrets: Mapping[str, bytes],
    policies: Mapping[str, dict]
) -> bytes:
    if key_id not in policies or key_id not in secrets:
        raise ValueError("keyId is not present in both policy and protected secret store")
    policy = policies[key_id]
    if policy["status"] == "Revoked":
        raise ValueError("keyId is revoked")
    now = _utc(now_utc)
    if not (_utc(policy["notBeforeUtc"]) <= now < _utc(policy["notAfterUtc"])):
        raise ValueError("keyId is outside its verification validity interval")
    if purpose not in policy["purposes"]:
        raise ValueError("keyId is not authorized for this purpose")
    return secrets[key_id]


def signing_key(
    *, key_id: str, purpose: str, now_utc: str, secrets: Mapping[str, bytes],
    policies: Mapping[str, dict]
) -> bytes:
    secret = verification_key(key_id=key_id, purpose=purpose, now_utc=now_utc,
                              secrets=secrets, policies=policies)
    if policies[key_id]["status"] != "Active":
        raise ValueError("only an Active key may sign new artifacts")
    return secret


def verify_with_rotation_policy(
    authenticated: dict, *, secrets: Mapping[str, bytes], policies: Mapping[str, dict],
    expected_purpose: str, now_utc: str, nonce_store: SqliteNonceStore,
    expected_payload: dict | None = None,
    expected_validation: Mapping[str, object] | None = None,
) -> tuple[dict, dict]:
    key_id = authenticated.get("keyId", "")
    secret = verification_key(key_id=key_id, purpose=expected_purpose, now_utc=now_utc,
                              secrets=secrets, policies=policies)
    # Use an ephemeral replay set first. Persistent nonce consumption is the
    # final step, after the nested integrity envelope and request binding pass.
    integrity = verify_authenticated_validation(
        authenticated, trusted_keys={key_id: secret}, expected_purpose=expected_purpose,
        now_utc=now_utc, used_nonces=set())
    payload, validation = verify_integrity_envelope(integrity)
    if expected_payload is not None and (
            canonical_json_bytes(payload) != canonical_json_bytes(expected_payload)):
        raise ValueError("authenticated validation is bound to a different request")
    for name, expected in (expected_validation or {}).items():
        if validation.get(name) != expected:
            raise ValueError(f"authenticated validation {name} mismatch")
    if not nonce_store.consume(key_id, authenticated["nonce"],
                               authenticated["expiresAtUtc"], now_utc):
        raise ValueError("authentication nonce replay detected")
    return payload, validation
