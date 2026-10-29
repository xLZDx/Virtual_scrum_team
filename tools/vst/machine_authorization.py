"""Candidate S2 machine-delegation contracts.

This module verifies candidate external records against a separately supplied trusted
configuration. It cannot create authority, issue instructions, or modify a Store.
The authority purpose and trust configuration are not currently provisioned.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from typing import Any

from .contracts import ContractError, canonical_bytes
from .execution_grant import _openssl_signature, _trusted_root_file

TRUST_CONFIG_PATH = "/etc/vst-runner/machine-delegation-trust.json"
POLICY_SCHEMA = "VST_S2_MACHINE_DELEGATION_POLICY_V1"
POLICY_PURPOSE = "VST_S2_MACHINE_DELEGATION_POLICY_V1"
ASSIGNMENT_SCHEMA = "VST_S2_ASSIGNMENT_AUTHORIZATION_V1"
ASSIGNMENT_PURPOSE = "VST_S2_ASSIGNMENT_AUTHORIZATION_V1"
TRUST_SCHEMA = "VST_S2_MACHINE_DELEGATION_TRUST_CONFIG_V1"
ISSUER_PURPOSE = "VST_S2_DELEGATED_DISPATCH_ISSUER_V1"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_NONCE = re.compile(r"^[0-9a-f]{32}$")
_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{86}$")

POLICY_FIELDS = frozenset({
    "schema", "operator_key_id", "policy_id", "project", "repository", "sprint_id", "role",
    "machine_principal", "machine_key_id", "key_purpose", "source_head",
    "manifest_sha256", "allowed_authorization_type", "not_before", "expires_at",
    "revocation_id", "signature",
})
ASSIGNMENT_FIELDS = frozenset({
    "schema", "authorization_id", "project", "repository", "sprint_id",
    "manifest_sha256", "task_id", "story_id", "principal", "slot", "attempt",
    "epoch", "lease_id", "run_id", "request_id", "policy_id", "policy_sha256",
    "authorization_key_id", "issuer_key_id", "issuer_key_purpose", "issued_at", "expires_at",
    "revocation_id", "signature",
})
TRUST_FIELDS = frozenset({"schema", "operator_authorities", "machine_principals", "revocations"})
AUTHORITY_FIELDS = frozenset({"key_id", "purpose", "public_key_path", "revocation_id"})
MACHINE_FIELDS = frozenset({
    "principal", "key_id", "purpose", "public_key_path", "policy_sha256",
    "not_before", "expires_at", "revocation_id",
})
REVOCATION_FIELDS = frozenset({"revocation_id", "revoked_at", "reason_code"})


def _exact_object(value: object, fields: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ContractError(f"{name}: fields do not match the closed contract")
    return value


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ContractError(f"{name}: invalid identifier")
    return value


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise ContractError(f"{name}: expected lowercase SHA-256")
    return value


def _utc(value: object, name: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ContractError(f"{name}: expected canonical UTC timestamp")
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise ContractError(f"{name}: expected canonical YYYY-MM-DDTHH:MM:SSZ") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ContractError(f"{name}: timestamp is not canonical")
    return parsed


def parse_json_object(raw: bytes, *, name: str, maximum_bytes: int = 1024 * 1024) -> dict[str, Any]:
    """Parse bounded UTF-8 JSON, rejecting duplicate keys and non-object roots."""
    if not isinstance(raw, bytes) or len(raw) > maximum_bytes:
        raise ContractError(f"{name}: input is not bytes or exceeds the size limit")

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ContractError(f"{name}: duplicate JSON field")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=unique_pairs,
                           parse_constant=lambda _value: (_ for _ in ()).throw(
                               ContractError(f"{name}: non-finite JSON number")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"{name}: invalid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{name}: JSON root must be an object")
    return value


def validate_delegation_policy(value: object, *, now: dt.datetime | None = None) -> dict[str, Any]:
    policy = _exact_object(value, POLICY_FIELDS, "delegation policy")
    if policy["schema"] != POLICY_SCHEMA:
        raise ContractError("delegation policy: unsupported schema")
    for field in ("operator_key_id", "policy_id", "project", "sprint_id", "role", "machine_principal",
                  "machine_key_id", "key_purpose", "revocation_id"):
        _identifier(policy[field], f"delegation policy {field}")
    if not isinstance(policy["repository"], str) or not policy["repository"].startswith("https://"):
        raise ContractError("delegation policy repository: expected an HTTPS repository identity")
    if policy["allowed_authorization_type"] != ASSIGNMENT_SCHEMA:
        raise ContractError("delegation policy: unsupported authorization type")
    if (policy["role"] != "dispatch-issuer"
            or policy["key_purpose"] != ISSUER_PURPOSE):
        raise ContractError("delegation policy: role and machine key purpose do not match")
    if not isinstance(policy["source_head"], str) or not _HEX40.fullmatch(policy["source_head"]):
        raise ContractError("delegation policy source_head: expected full lowercase Git SHA")
    _digest(policy["manifest_sha256"], "delegation policy manifest_sha256")
    not_before = _utc(policy["not_before"], "delegation policy not_before")
    expires_at = _utc(policy["expires_at"], "delegation policy expires_at")
    if expires_at <= not_before:
        raise ContractError("delegation policy: expiry must follow not_before")
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() != dt.timedelta(0):
        raise ContractError("delegation policy verifier clock must be UTC")
    if current < not_before or current >= expires_at:
        raise ContractError("delegation policy: outside its validity window")
    _signature_bytes(policy["signature"], "delegation policy signature")
    return value


def validate_assignment_authorization(value: object, *, now: dt.datetime | None = None) -> dict[str, Any]:
    authorization = _exact_object(value, ASSIGNMENT_FIELDS, "assignment authorization")
    if authorization["schema"] != ASSIGNMENT_SCHEMA:
        raise ContractError("assignment authorization: unsupported schema")
    for field in ("authorization_id", "project", "sprint_id", "task_id", "story_id",
                  "principal", "slot", "lease_id", "run_id", "policy_id",
                  "authorization_key_id", "issuer_key_id", "issuer_key_purpose", "revocation_id"):
        _identifier(authorization[field], f"assignment authorization {field}")
    if not isinstance(authorization["repository"], str) or not authorization["repository"].startswith("https://"):
        raise ContractError("assignment authorization repository: expected HTTPS identity")
    if authorization["principal"] != "Codex":
        raise ContractError("assignment authorization principal is not Codex")
    if authorization["issuer_key_purpose"] != ISSUER_PURPOSE:
        raise ContractError("assignment authorization issuer purpose is invalid")
    for field in ("manifest_sha256", "policy_sha256"):
        _digest(authorization[field], f"assignment authorization {field}")
    for field in ("attempt", "epoch"):
        if type(authorization[field]) is not int or not 1 <= authorization[field] <= 2**63 - 1:
            raise ContractError(f"assignment authorization {field}: invalid positive integer")
    if not isinstance(authorization["request_id"], str) or not _NONCE.fullmatch(authorization["request_id"]):
        raise ContractError("assignment authorization request_id: expected 32 lowercase hex characters")
    issued = _utc(authorization["issued_at"], "assignment authorization issued_at")
    expires = _utc(authorization["expires_at"], "assignment authorization expires_at")
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() != dt.timedelta(0):
        raise ContractError("assignment authorization verifier clock must be UTC")
    if issued > current or expires <= current or expires <= issued:
        raise ContractError("assignment authorization is not currently valid")
    _signature_bytes(authorization["signature"], "assignment authorization signature")
    return value


def _signature_bytes(value: object, name: str) -> bytes:
    if not isinstance(value, str) or not _SIGNATURE.fullmatch(value):
        raise ContractError(f"{name}: malformed Ed25519 signature")
    try:
        decoded = base64.urlsafe_b64decode(value + "==")
    except (ValueError, base64.binascii.Error) as exc:
        raise ContractError(f"{name}: malformed Ed25519 signature") from exc
    if len(decoded) != 64 or base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != value:
        raise ContractError(f"{name}: malformed Ed25519 signature")
    return decoded


def signing_bytes(value: Mapping[str, Any], *, domain: str, signature_field: str = "signature") -> bytes:
    if not isinstance(value, Mapping) or signature_field not in value:
        raise ContractError("signed object: missing signature")
    unsigned = dict(value)
    del unsigned[signature_field]
    return domain.encode("ascii") + b"\0" + canonical_bytes(unsigned)


def validate_trust_config(value: object, *, now: dt.datetime | None = None) -> dict[str, Any]:
    config = _exact_object(value, TRUST_FIELDS, "machine delegation trust config")
    if config["schema"] != TRUST_SCHEMA:
        raise ContractError("machine delegation trust config: unsupported schema")
    if not all(isinstance(config[field], list) for field in ("operator_authorities", "machine_principals", "revocations")):
        raise ContractError("machine delegation trust config: registries must be arrays")
    operator_ids: set[str] = set()
    operator_purposes: set[str] = set()
    for entry in config["operator_authorities"]:
        _exact_object(entry, AUTHORITY_FIELDS, "operator authority")
        key_id = _identifier(entry["key_id"], "operator authority key_id")
        if (not isinstance(entry["purpose"], str)
                or entry["purpose"] not in {POLICY_PURPOSE, ASSIGNMENT_PURPOSE}):
            raise ContractError("operator authority: purpose is not allowed")
        _identifier(entry["revocation_id"], "operator authority revocation_id")
        if not isinstance(entry["public_key_path"], str) or not os.path.isabs(entry["public_key_path"]):
            raise ContractError("operator authority: public key path must be absolute")
        if key_id in operator_ids or entry["purpose"] in operator_purposes:
            raise ContractError("operator authority: key IDs and signing purposes must be unique")
        operator_ids.add(key_id)
        operator_purposes.add(entry["purpose"])
    machine_ids: set[str] = set()
    for entry in config["machine_principals"]:
        _exact_object(entry, MACHINE_FIELDS, "machine principal")
        key_id = _identifier(entry["key_id"], "machine principal key_id")
        if key_id in machine_ids or entry["purpose"] != ISSUER_PURPOSE:
            raise ContractError("machine principal: duplicate key or unsupported purpose")
        if not isinstance(entry["principal"], str) or not _ID.fullmatch(entry["principal"]):
            raise ContractError("machine principal: invalid principal")
        if not isinstance(entry["public_key_path"], str) or not os.path.isabs(entry["public_key_path"]):
            raise ContractError("machine principal: public key path must be absolute")
        _digest(entry["policy_sha256"], "machine principal policy_sha256")
        start = _utc(entry["not_before"], "machine principal not_before")
        end = _utc(entry["expires_at"], "machine principal expires_at")
        if end <= start:
            raise ContractError("machine principal validity window is empty")
        _identifier(entry["revocation_id"], "machine principal revocation_id")
        machine_ids.add(key_id)
    revocations: set[str] = set()
    for entry in config["revocations"]:
        _exact_object(entry, REVOCATION_FIELDS, "revocation")
        revocation_id = _identifier(entry["revocation_id"], "revocation_id")
        _utc(entry["revoked_at"], "revoked_at")
        _identifier(entry["reason_code"], "revocation reason_code")
        if revocation_id in revocations:
            raise ContractError("machine delegation trust config: duplicate revocation")
        revocations.add(revocation_id)
    return value


def load_trust_config(path: str = TRUST_CONFIG_PATH) -> dict[str, Any]:
    """Load the proposed trust config only from a root-controlled no-follow file."""
    _trusted_root_file(path, private=False)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if stat.S_IMODE(info.st_mode) & 0o022:
            raise ContractError("machine delegation trust config is group/world writable")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(1024 * 1024 + 1)
    finally:
        os.close(fd)
    config = parse_json_object(raw, name="machine delegation trust config")
    validate_trust_config(config)
    return config


def _trusted_key(config: Mapping[str, Any], *, key_id: str, purpose: str,
                 now: dt.datetime) -> str:
    revoked = {entry["revocation_id"] for entry in config["revocations"]}
    if purpose in {POLICY_PURPOSE, ASSIGNMENT_PURPOSE}:
        matches = [item for item in config["operator_authorities"]
                   if item["key_id"] == key_id and item["purpose"] == purpose]
    elif purpose == ISSUER_PURPOSE:
        matches = [item for item in config["machine_principals"]
                   if item["key_id"] == key_id and item["purpose"] == purpose
                   and _utc(item["not_before"], "machine not_before") <= now < _utc(item["expires_at"], "machine expires_at")]
    else:
        raise ContractError("machine authorization: unsupported signature purpose")
    if len(matches) != 1:
        raise ContractError("machine authorization: key is not uniquely trusted for purpose")
    entry = matches[0]
    if entry.get("revocation_id") in revoked:
        raise ContractError("machine authorization: signing key is revoked")
    path = entry["public_key_path"]
    _trusted_root_file(path, private=False)
    return path


def _verify_ed25519(value: Mapping[str, Any], *, key_path: str, purpose: str,
                    openssl_path: str) -> None:
    signature = _signature_bytes(value["signature"], f"{purpose} signature")
    valid = _openssl_signature(openssl_path, key_path=key_path,
                               payload=signing_bytes(value, domain=purpose),
                               signature=signature, private=False)
    if valid is not True:
        raise ContractError(f"{purpose}: signature verification failed")


def verify_policy(policy: object, trust_config: Mapping[str, Any], *,
                  openssl_path: str, now: dt.datetime | None = None) -> dict[str, Any]:
    current = now or dt.datetime.now(dt.timezone.utc)
    checked = validate_delegation_policy(policy, now=current)
    config = validate_trust_config(trust_config, now=current)
    key_path = _trusted_key(config, key_id=checked["operator_key_id"],
                            purpose=POLICY_PURPOSE, now=current)
    _verify_ed25519(checked, key_path=key_path, purpose=POLICY_PURPOSE,
                    openssl_path=openssl_path)
    policy_digest = hashlib.sha256(canonical_bytes(checked)).hexdigest()
    machine = [item for item in config["machine_principals"]
               if item["key_id"] == checked["machine_key_id"]
               and item["principal"] == checked["machine_principal"]
               and item["purpose"] == checked["key_purpose"]
               and item["policy_sha256"] == policy_digest]
    if len(machine) != 1:
        raise ContractError("delegation policy does not match one configured machine principal")
    if not (_utc(machine[0]["not_before"], "machine not_before") <= current
            < _utc(machine[0]["expires_at"], "machine expires_at")):
        raise ContractError("delegation policy machine principal is outside its validity window")
    if (checked["revocation_id"] in {entry["revocation_id"] for entry in config["revocations"]}
            or machine[0]["revocation_id"] in {entry["revocation_id"] for entry in config["revocations"]}):
        raise ContractError("delegation policy machine key is revoked")
    return {"policy": dict(checked), "policy_sha256": policy_digest,
            "machine_principal": dict(machine[0])}


def verify_assignment_authorization(
    authorization: object, policy: object, trust_config: Mapping[str, Any],
    store_snapshot: Mapping[str, Any], *,
    openssl_path: str, expected_project: str, expected_repository: str,
    expected_sprint_id: str, expected_manifest_sha256: str, expected_source_head: str,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Verify a new external assignment record and compare it with one read-only Store snapshot.

    `store_snapshot` is a caller-provided authenticated read result. This function performs no
    Store I/O, mutation, task enumeration, signing, or dispatch.
    """
    current = now or dt.datetime.now(dt.timezone.utc)
    record = validate_assignment_authorization(authorization, now=current)
    config = validate_trust_config(trust_config, now=current)
    verified_policy = verify_policy(policy, config, openssl_path=openssl_path, now=current)
    policy_record = verified_policy["policy"]
    for field in ("policy_id", "project", "repository", "sprint_id", "manifest_sha256",
                  "machine_key_id", "key_purpose"):
        assignment_field = "issuer_key_id" if field == "machine_key_id" else (
            "issuer_key_purpose" if field == "key_purpose" else field)
        if record[assignment_field] != policy_record[field]:
            raise ContractError("assignment authorization does not match its signed delegation policy")
    if (policy_record["source_head"] != expected_source_head
            or verified_policy["policy_sha256"] != record["policy_sha256"]):
        raise ContractError("assignment authorization source or policy digest is stale")
    revoked = {entry["revocation_id"] for entry in config["revocations"]}
    if record["revocation_id"] in revoked:
        raise ContractError("assignment authorization is revoked")
    key_path = _trusted_key(config, key_id=record["authorization_key_id"],
                            purpose=ASSIGNMENT_PURPOSE, now=current)
    _verify_ed25519(record, key_path=key_path, purpose=ASSIGNMENT_PURPOSE,
                    openssl_path=openssl_path)
    machine = [item for item in config["machine_principals"]
               if item["key_id"] == record["issuer_key_id"]
               and item["purpose"] == record["issuer_key_purpose"]
               and item["policy_sha256"] == record["policy_sha256"]]
    if len(machine) != 1:
        raise ContractError("assignment authorization does not bind one trusted issuer policy")
    if machine[0]["revocation_id"] in revoked:
        raise ContractError("assignment authorization issuer policy is revoked")
    if not isinstance(store_snapshot, Mapping):
        raise ContractError("Store assignment snapshot must be an authenticated mapping")
    expected = {
        "project": expected_project, "repository": expected_repository,
        "sprint_id": expected_sprint_id, "manifest_sha256": expected_manifest_sha256,
        "source_head": expected_source_head,
    }
    expected.update({key: record[key] for key in (
        "task_id", "story_id", "principal", "slot", "attempt", "epoch", "lease_id", "run_id",
    )})
    if any(record[key] != value for key, value in expected.items() if key in record):
        raise ContractError("assignment authorization does not match the expected project scope")
    snapshot_fields = {
        "task_id": "task_id", "story_id": "story_id", "principal": "owner_principal",
        "slot": "slot", "attempt": "attempt", "epoch": "owner_epoch", "lease_id": "lease_id",
        "run_id": "run_id", "manifest_sha256": "manifest_sha256",
    }
    for record_field, snapshot_field in snapshot_fields.items():
        if store_snapshot.get(snapshot_field) != record[record_field]:
            raise ContractError("assignment authorization does not match current Store snapshot")
    if store_snapshot.get("assignment_state") != "ASSIGNED" or store_snapshot.get("lease_state") != "LIVE":
        raise ContractError("Store snapshot does not show one assigned task with a live lease")
    return {"authorization": dict(record),
            "authorization_sha256": hashlib.sha256(canonical_bytes(record)).hexdigest(),
            "snapshot_match": True}
