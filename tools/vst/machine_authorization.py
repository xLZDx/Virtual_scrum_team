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
import math
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
POLICY_SCHEMA_V2 = "VST_S2_MACHINE_DELEGATION_POLICY_V2"
POLICY_PURPOSE_V2 = "VST_S2_MACHINE_DELEGATION_POLICY_V2"
ASSIGNMENT_SCHEMA_V2 = "VST_S2_ASSIGNMENT_AUTHORIZATION_V2"
ASSIGNMENT_PURPOSE_V2 = "VST_S2_ASSIGNMENT_AUTHORIZATION_V2"
TRUST_SCHEMA_V2 = "VST_S2_MACHINE_DELEGATION_TRUST_CONFIG_V2"
ISSUER_PURPOSE_V2 = "VST_S2_DELEGATED_DISPATCH_ISSUER_V2"
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
POLICY_V2_FIELDS = frozenset({
    "schema", "operator_key_id", "policy_id", "project", "repository", "sprint_id", "role",
    "machine_principal", "machine_key_id", "key_purpose", "source_head",
    "manifest_sha256", "allowed_authorization_type", "not_before", "expires_at",
    "revocation_id", "signature",
})
ASSIGNMENT_V2_FIELDS = frozenset({
    "schema", "authorization_id", "assignment_operation_id", "project", "repository",
    "sprint_id", "source_head", "manifest_sha256", "project_id", "phase",
    "task_manifest_sha256", "task_id", "story_id", "principal", "slot", "attempt",
    "epoch", "lease_id", "runner_id", "run_id", "service_generation", "probe_sha256",
    "request_id", "assignment_policy_id", "assignment_policy_sha256", "delegation_policy_id",
    "delegation_policy_sha256", "authorization_key_id", "issuer_key_id",
    "issuer_key_purpose", "issued_at", "expires_at", "revocation_id", "signature",
})
TRUST_V2_FIELDS = frozenset({"schema", "operator_authorities", "machine_principals", "revocations"})


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


def validate_delegation_policy_v2(value: object, *, now: dt.datetime | None = None) -> dict[str, Any]:
    """Validate the closed V2 issuer policy without treating its shape as authority."""
    policy = _exact_object(value, POLICY_V2_FIELDS, "delegation policy V2")
    if policy["schema"] != POLICY_SCHEMA_V2:
        raise ContractError("delegation policy V2: unsupported schema")
    for field in ("operator_key_id", "policy_id", "project", "sprint_id", "role",
                  "machine_principal", "machine_key_id", "key_purpose", "revocation_id"):
        _identifier(policy[field], f"delegation policy V2 {field}")
    if policy["project"] != "Virtual_scrum_team" or policy["repository"] != "Virtual_scrum_team":
        raise ContractError("delegation policy V2 project and repository must match the root Store identity")
    if (policy["role"] != "dispatch-issuer"
            or policy["allowed_authorization_type"] != ASSIGNMENT_SCHEMA_V2
            or policy["key_purpose"] != ISSUER_PURPOSE_V2):
        raise ContractError("delegation policy V2 role, authorization type or key purpose is invalid")
    if not isinstance(policy["source_head"], str) or not _HEX40.fullmatch(policy["source_head"]):
        raise ContractError("delegation policy V2 source_head: expected full lowercase Git SHA")
    _digest(policy["manifest_sha256"], "delegation policy V2 manifest_sha256")
    not_before = _utc(policy["not_before"], "delegation policy V2 not_before")
    expires_at = _utc(policy["expires_at"], "delegation policy V2 expires_at")
    if expires_at <= not_before:
        raise ContractError("delegation policy V2 expiry must follow not_before")
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() != dt.timedelta(0):
        raise ContractError("delegation policy V2 verifier clock must be UTC")
    if current < not_before or current >= expires_at:
        raise ContractError("delegation policy V2 is outside its validity window")
    _signature_bytes(policy["signature"], "delegation policy V2 signature")
    return value


def validate_trust_config_v2(value: object, *, now: dt.datetime | None = None) -> dict[str, Any]:
    """Validate only V2 purposes; V1 trust entries cannot authorize this contract."""
    config = _exact_object(value, TRUST_V2_FIELDS, "machine delegation trust config V2")
    if config["schema"] != TRUST_SCHEMA_V2:
        raise ContractError("machine delegation trust config V2: unsupported schema")
    if not all(isinstance(config[field], list)
               for field in ("operator_authorities", "machine_principals", "revocations")):
        raise ContractError("machine delegation trust config V2 registries must be arrays")
    operator_ids: set[str] = set()
    operator_purposes: set[str] = set()
    for entry in config["operator_authorities"]:
        _exact_object(entry, AUTHORITY_FIELDS, "V2 operator authority")
        key_id = _identifier(entry["key_id"], "V2 operator authority key_id")
        purpose = entry["purpose"]
        if purpose not in {POLICY_PURPOSE_V2, ASSIGNMENT_PURPOSE_V2}:
            raise ContractError("V2 operator authority has a non-V2 purpose")
        _identifier(entry["revocation_id"], "V2 operator authority revocation_id")
        if (not isinstance(entry["public_key_path"], str)
                or not os.path.isabs(entry["public_key_path"])):
            raise ContractError("V2 operator authority public key path must be absolute")
        if key_id in operator_ids or purpose in operator_purposes:
            raise ContractError("V2 operator authorities must have unique IDs and purposes")
        operator_ids.add(key_id)
        operator_purposes.add(purpose)
    machine_ids: set[str] = set()
    machine_principals: set[str] = set()
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() != dt.timedelta(0):
        raise ContractError("machine trust V2 verifier clock must be UTC")
    for entry in config["machine_principals"]:
        _exact_object(entry, MACHINE_FIELDS, "V2 machine principal")
        key_id = _identifier(entry["key_id"], "V2 machine principal key_id")
        principal = _identifier(entry["principal"], "V2 machine principal principal")
        if (key_id in machine_ids or principal in machine_principals
                or key_id in operator_ids or entry["purpose"] != ISSUER_PURPOSE_V2):
            raise ContractError("V2 machine principal has a duplicate key or non-V2 purpose")
        if (not isinstance(entry["public_key_path"], str)
                or not os.path.isabs(entry["public_key_path"])):
            raise ContractError("V2 machine principal public key path must be absolute")
        _digest(entry["policy_sha256"], "V2 machine principal policy_sha256")
        start = _utc(entry["not_before"], "V2 machine not_before")
        end = _utc(entry["expires_at"], "V2 machine expires_at")
        if end <= start:
            raise ContractError("V2 machine principal validity window is empty")
        _identifier(entry["revocation_id"], "V2 machine principal revocation_id")
        machine_ids.add(key_id)
        machine_principals.add(principal)
    revoked: set[str] = set()
    for entry in config["revocations"]:
        _exact_object(entry, REVOCATION_FIELDS, "V2 revocation")
        identifier = _identifier(entry["revocation_id"], "V2 revocation_id")
        _utc(entry["revoked_at"], "V2 revoked_at")
        _identifier(entry["reason_code"], "V2 revocation reason_code")
        if identifier in revoked:
            raise ContractError("V2 trust config has a duplicate revocation")
        revoked.add(identifier)
    return value


def _trusted_key_v2(config: Mapping[str, Any], *, key_id: str, purpose: str,
                    now: dt.datetime) -> str:
    revoked = {entry["revocation_id"] for entry in config["revocations"]}
    if purpose in {POLICY_PURPOSE_V2, ASSIGNMENT_PURPOSE_V2}:
        matches = [item for item in config["operator_authorities"]
                   if item["key_id"] == key_id and item["purpose"] == purpose]
    elif purpose == ISSUER_PURPOSE_V2:
        matches = [item for item in config["machine_principals"]
                   if item["key_id"] == key_id and item["purpose"] == purpose
                   and _utc(item["not_before"], "V2 machine not_before") <= now
                   < _utc(item["expires_at"], "V2 machine expires_at")]
    else:
        raise ContractError("machine authorization V2: unsupported signature purpose")
    if len(matches) != 1:
        raise ContractError("machine authorization V2: key is not uniquely trusted for purpose")
    entry = matches[0]
    if entry["revocation_id"] in revoked:
        raise ContractError("machine authorization V2: signing key is revoked")
    path = entry["public_key_path"]
    _trusted_root_file(path, private=False)
    return path


def verify_policy_v2(policy: object, trust_config: Mapping[str, Any], *,
                     openssl_path: str, now: dt.datetime | None = None) -> dict[str, Any]:
    """Verify the V2 policy under a distinct V2 trust registry and signature purpose."""
    current = now or dt.datetime.now(dt.timezone.utc)
    checked = validate_delegation_policy_v2(policy, now=current)
    config = validate_trust_config_v2(trust_config, now=current)
    key_path = _trusted_key_v2(config, key_id=checked["operator_key_id"],
                               purpose=POLICY_PURPOSE_V2, now=current)
    _verify_ed25519(checked, key_path=key_path, purpose=POLICY_PURPOSE_V2,
                    openssl_path=openssl_path)
    digest = hashlib.sha256(canonical_bytes(checked)).hexdigest()
    machine = [item for item in config["machine_principals"]
               if item["key_id"] == checked["machine_key_id"]
               and item["principal"] == checked["machine_principal"]
               and item["purpose"] == ISSUER_PURPOSE_V2
               and item["policy_sha256"] == digest]
    revoked = {entry["revocation_id"] for entry in config["revocations"]}
    if (len(machine) != 1 or checked["revocation_id"] in revoked
            or machine[0]["revocation_id"] in revoked):
        raise ContractError("V2 delegation policy does not match one live trusted machine principal")
    if not (_utc(machine[0]["not_before"], "V2 machine not_before") <= current
            < _utc(machine[0]["expires_at"], "V2 machine expires_at")):
        raise ContractError("V2 machine principal is outside its validity window")
    return {"policy": dict(checked), "policy_sha256": digest,
            "machine_principal": dict(machine[0])}


def validate_assignment_authorization_v2(value: object, *,
                                         now: dt.datetime | None = None) -> dict[str, Any]:
    """Validate the immutable V2 assignment tuple and its signed operation identity."""
    record = _exact_object(value, ASSIGNMENT_V2_FIELDS, "assignment authorization V2")
    if record["schema"] != ASSIGNMENT_SCHEMA_V2:
        raise ContractError("assignment authorization V2: unsupported schema")
    for field in ("authorization_id", "project", "sprint_id", "project_id", "task_id", "story_id",
                  "principal", "slot", "runner_id", "run_id", "service_generation",
                  "assignment_policy_id", "delegation_policy_id", "authorization_key_id",
                  "issuer_key_id", "issuer_key_purpose", "revocation_id"):
        _identifier(record[field], f"assignment authorization V2 {field}")
    if record["project"] != "Virtual_scrum_team" or record["repository"] != "Virtual_scrum_team":
        raise ContractError("assignment authorization V2 project and repository must match the root Store identity")
    if record["principal"] != "Codex" or record["issuer_key_purpose"] != ISSUER_PURPOSE_V2:
        raise ContractError("assignment authorization V2 principal or issuer purpose is invalid")
    for field in ("assignment_operation_id", "manifest_sha256", "task_manifest_sha256",
                  "assignment_policy_sha256", "delegation_policy_sha256", "probe_sha256"):
        _digest(record[field], f"assignment authorization V2 {field}")
    if not isinstance(record["source_head"], str) or not _HEX40.fullmatch(record["source_head"]):
        raise ContractError("assignment authorization V2 source_head must be a full Git SHA")
    for field in ("phase", "attempt", "epoch", "lease_id"):
        if (type(record[field]) is not int or not 1 <= record[field] <= 2**63 - 1
                or (field == "phase" and record[field] > 10)):
            raise ContractError(f"assignment authorization V2 {field} must be a positive integer")
    if not isinstance(record["request_id"], str) or not _NONCE.fullmatch(record["request_id"]):
        raise ContractError("assignment authorization V2 request_id must be 32 lowercase hex characters")
    issued = _utc(record["issued_at"], "assignment authorization V2 issued_at")
    expires = _utc(record["expires_at"], "assignment authorization V2 expires_at")
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() != dt.timedelta(0):
        raise ContractError("assignment authorization V2 verifier clock must be UTC")
    if issued > current or expires <= current or expires <= issued:
        raise ContractError("assignment authorization V2 is not currently valid")
    _signature_bytes(record["signature"], "assignment authorization V2 signature")
    return value


def validate_authorization_id_v2(value: object) -> str:
    """Validate the sole request selector before a trusted provider is consulted."""
    return _identifier(value, "assignment authorization V2 authorization_id")


def verify_assignment_authorization_v2(
    authorization: object, policy: object, trust_config: Mapping[str, Any], *,
    openssl_path: str, now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Verify V2 authorization signature and all explicit policy/version bindings."""
    current = now or dt.datetime.now(dt.timezone.utc)
    record = validate_assignment_authorization_v2(authorization, now=current)
    config = validate_trust_config_v2(trust_config, now=current)
    verified_policy = verify_policy_v2(policy, config, openssl_path=openssl_path, now=current)
    policy_record = verified_policy["policy"]
    policy_not_before = _utc(policy_record["not_before"], "delegation policy V2 not_before")
    policy_expires = _utc(policy_record["expires_at"], "delegation policy V2 expires_at")
    authorization_issued = _utc(record["issued_at"], "assignment authorization V2 issued_at")
    authorization_expires = _utc(record["expires_at"], "assignment authorization V2 expires_at")
    if (record["delegation_policy_id"] != policy_record["policy_id"]
            or record["delegation_policy_sha256"] != verified_policy["policy_sha256"]
            or record["project"] != policy_record["project"]
            or record["repository"] != policy_record["repository"]
            or record["sprint_id"] != policy_record["sprint_id"]
            or record["source_head"] != policy_record["source_head"]
            or record["manifest_sha256"] != policy_record["manifest_sha256"]
            or record["issuer_key_id"] != policy_record["machine_key_id"]
            or record["issuer_key_purpose"] != policy_record["key_purpose"]
            or authorization_issued < policy_not_before
            or authorization_expires > policy_expires):
        raise ContractError("assignment authorization V2 differs from its signed delegation policy")
    key_path = _trusted_key_v2(config, key_id=record["authorization_key_id"],
                               purpose=ASSIGNMENT_PURPOSE_V2, now=current)
    _verify_ed25519(record, key_path=key_path, purpose=ASSIGNMENT_PURPOSE_V2,
                    openssl_path=openssl_path)
    machine = verified_policy["machine_principal"]
    revoked = {entry["revocation_id"] for entry in config["revocations"]}
    if (record["authorization_key_id"] not in {entry["key_id"]
                                               for entry in config["operator_authorities"]
                                               if entry["purpose"] == ASSIGNMENT_PURPOSE_V2}
            or record["revocation_id"] in revoked
            or machine["revocation_id"] in revoked):
        raise ContractError("assignment authorization V2 is revoked or has an untrusted key")
    return {"authorization": dict(record),
            "authorization_sha256": hashlib.sha256(canonical_bytes(record)).hexdigest(),
            "policy": dict(policy_record), "policy_sha256": verified_policy["policy_sha256"]}


def compare_assignment_authorization_v2_to_store(
    verified: Mapping[str, Any], store_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare a verified V2 record with one snapshot obtained by root Supervisor Store I/O.

    This pure comparator performs no Store I/O and is not itself an authorization boundary.
    Production callers must obtain `store_snapshot` inside the root Supervisor method.
    """
    if (not isinstance(verified, Mapping)
            or set(verified) != {"authorization", "authorization_sha256", "policy", "policy_sha256"}
            or not isinstance(store_snapshot, Mapping)
            or set(store_snapshot) != {"handoff", "basis", "authority_expires_at"}):
        raise ContractError("V2 authorization or Store snapshot has an invalid verified shape")
    record = validate_assignment_authorization_v2(verified["authorization"])
    if hashlib.sha256(canonical_bytes(record)).hexdigest() != verified["authorization_sha256"]:
        raise ContractError("V2 assignment authorization digest changed after verification")
    policy = validate_delegation_policy_v2(verified["policy"])
    if hashlib.sha256(canonical_bytes(policy)).hexdigest() != verified["policy_sha256"]:
        raise ContractError("V2 delegation policy digest changed after verification")
    handoff = store_snapshot["handoff"]
    if not isinstance(handoff, Mapping):
        raise ContractError("authenticated Store handoff is unavailable")
    bootstrap = handoff.get("bootstrap_request")
    if not isinstance(bootstrap, Mapping):
        raise ContractError("authenticated Store bootstrap request is unavailable")
    expected = {
        "assignment_operation_id": handoff.get("assignment_operation_id"),
        "project": handoff.get("repository"),
        "repository": handoff.get("repository"),
        "sprint_id": handoff.get("sprint_id"),
        "source_head": handoff.get("source_head"),
        "manifest_sha256": handoff.get("manifest_sha256"),
        "project_id": handoff.get("project_id"),
        "phase": handoff.get("phase"),
        "task_manifest_sha256": handoff.get("task_manifest_sha256"),
        "task_id": handoff.get("task_id"),
        "story_id": handoff.get("story_id"),
        "principal": handoff.get("assignment_principal"),
        "slot": handoff.get("slot"),
        "attempt": handoff.get("attempt"),
        "epoch": handoff.get("epoch"),
        "lease_id": handoff.get("lease_id"),
        "runner_id": handoff.get("runner_id"),
        "run_id": handoff.get("run_id"),
        "service_generation": handoff.get("service_generation"),
        "probe_sha256": handoff.get("probe_sha256"),
        "request_id": bootstrap.get("request_id"),
        "assignment_policy_id": handoff.get("policy_id"),
        "assignment_policy_sha256": handoff.get("policy_sha256"),
        "delegation_policy_id": policy.get("policy_id"),
        "delegation_policy_sha256": verified["policy_sha256"],
    }
    for name, expected_value in expected.items():
        if record[name] != expected_value:
            raise ContractError(f"V2 assignment authorization differs from current Store {name}")
    if (record["principal"] != "Codex"
            or record["project"] != policy["project"]
            or record["repository"] != policy["repository"]
            or record["sprint_id"] != policy["sprint_id"]
            or record["source_head"] != policy["source_head"]
            or record["manifest_sha256"] != policy["manifest_sha256"]
            or record["issuer_key_id"] != policy["machine_key_id"]
            or record["issuer_key_purpose"] != policy["key_purpose"]):
        raise ContractError("V2 assignment authorization differs from its delegation scope")
    authority_expiry = store_snapshot["authority_expires_at"]
    if (isinstance(authority_expiry, bool) or not isinstance(authority_expiry, (float, int))
            or not math.isfinite(authority_expiry)
            or record["expires_at"] > dt.datetime.fromtimestamp(
                authority_expiry, dt.timezone.utc,
            ).strftime("%Y-%m-%dT%H:%M:%SZ")):
        raise ContractError("V2 assignment authorization exceeds current Store authority expiry")
    return {"authorization_id": record["authorization_id"],
            "authorization_sha256": verified["authorization_sha256"],
            "assignment_operation_id": record["assignment_operation_id"],
            "handoff_sha256": handoff["handoff_sha256"],
            "policy_sha256": verified["policy_sha256"],
            "assignment_policy_sha256": record["assignment_policy_sha256"],
            "service_generation": record["service_generation"], "run_id": record["run_id"]}


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
