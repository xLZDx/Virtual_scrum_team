"""Signed provenance contract for S2 task dispatch instructions."""

from __future__ import annotations

import base64
import datetime as dt
import re
from collections.abc import Mapping
from typing import Any

from .contracts import ContractError, canonical_bytes

DISPATCH_INSTRUCTION_DOMAIN = b"VST_S2_DISPATCH_INSTRUCTION_V1\0"
DISPATCH_INSTRUCTION_PURPOSE = "VST_S2_DISPATCH_INSTRUCTION_V1"
DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH = "/etc/vst-runner/dispatch-instruction-trust.json"
_FIELDS = frozenset({
    "version", "algorithm", "purpose", "request_id", "task_id", "slot",
    "attempt", "epoch", "run_id", "key_id", "expires_at", "signature",
})
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{86}$")


def validate_dispatch_instruction(value: object) -> dict[str, Any]:
    """Validate exact v1 shape and canonical values; does not trust signature."""
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ContractError("dispatch instruction fields do not match v1 contract")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ContractError("dispatch instruction version is unsupported")
    if value["algorithm"] != "Ed25519" or value["purpose"] != DISPATCH_INSTRUCTION_PURPOSE:
        raise ContractError("dispatch instruction algorithm or purpose is invalid")
    for field in ("task_id", "slot", "run_id", "key_id"):
        if not isinstance(value[field], str) or not _ID.fullmatch(value[field]):
            raise ContractError(f"dispatch instruction {field} is invalid")
    if not isinstance(value["request_id"], str) or not _REQUEST_ID.fullmatch(value["request_id"]):
        raise ContractError("dispatch instruction request_id must be 32 lowercase hex characters")
    for field in ("attempt", "epoch"):
        if type(value[field]) is not int or not 1 <= value[field] <= 2**63 - 1:
            raise ContractError(f"dispatch instruction {field} is invalid")
    expires_at = value["expires_at"]
    if not isinstance(expires_at, str):
        raise ContractError("dispatch instruction expiry must be canonical UTC")
    try:
        parsed = dt.datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise ContractError("dispatch instruction expiry must be canonical UTC YYYY-MM-DDTHH:MM:SSZ") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != expires_at:
        raise ContractError("dispatch instruction expiry is not canonical")
    if not isinstance(value["signature"], str) or not _SIGNATURE.fullmatch(value["signature"]):
        raise ContractError("dispatch instruction signature is malformed")
    try:
        raw = base64.urlsafe_b64decode(value["signature"] + "==")
    except (ValueError, base64.binascii.Error) as exc:
        raise ContractError("dispatch instruction signature is malformed") from exc
    if len(raw) != 64 or base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != value["signature"]:
        raise ContractError("dispatch instruction signature is malformed")
    return value


def dispatch_instruction_signing_bytes(value: object) -> bytes:
    instruction = validate_dispatch_instruction(value)
    unsigned = {key: instruction[key] for key in _FIELDS if key != "signature"}
    return DISPATCH_INSTRUCTION_DOMAIN + canonical_bytes(unsigned)


def verify_dispatch_instruction(
    value: object, trust_registry: Mapping[str, Mapping[str, str]], *,
    expected_principal: str, openssl_path: str, now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Verify an exact envelope against root-configured key identity and expiry."""
    instruction = validate_dispatch_instruction(value)
    entry = trust_registry.get(instruction["key_id"])
    if (not isinstance(entry, Mapping)
            or set(entry) != {"principal", "purpose", "public_key_path"}
            or entry.get("principal") != expected_principal
            or entry.get("purpose") != DISPATCH_INSTRUCTION_PURPOSE
            or not isinstance(entry.get("public_key_path"), str)):
        raise ContractError("dispatch instruction key is not trusted for this principal and purpose")
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() != dt.timedelta(0):
        raise ContractError("dispatch instruction verifier clock must be UTC")
    expiry = dt.datetime.strptime(instruction["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    if expiry <= current:
        raise ContractError("dispatch instruction has expired")
    from .execution_grant import _openssl_signature

    signature = base64.urlsafe_b64decode(instruction["signature"] + "==")
    valid = _openssl_signature(
        openssl_path, key_path=entry["public_key_path"],
        payload=dispatch_instruction_signing_bytes(instruction), signature=signature,
        private=False,
    )
    if valid is not True:
        raise ContractError("dispatch instruction Ed25519 signature is invalid")
    return {"principal": expected_principal, "key_id": instruction["key_id"],
            "instruction": instruction}
