"""Pure contracts for S2 root-bound dispatch issuance.

This module validates and reduces detached values only. It does not establish
authority, access the Store, invoke a signer, or grant permission to sign.
"""

from __future__ import annotations

import copy
import base64
import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from .assignment_basis import validate_handoff, validate_policy
from .contracts import ContractError, canonical_bytes
from .dispatch_instruction import (
    DISPATCH_INSTRUCTION_PURPOSE,
    dispatch_instruction_signing_bytes,
    validate_dispatch_instruction,
)

REQUEST_ID_DOMAIN = b"VST_S2_ROOT_DISPATCH_REQUEST_ID_V1\0"
OPERATION_KEY_DOMAIN = b"VST_S2_ROOT_DISPATCH_ISSUANCE_OPERATION_V1\0"
ISSUANCE_OPERATION = "VST_S2_ROOT_DISPATCH_ISSUE_V1"
HANDOFF_SCHEMA = "VST_S2_AUTHENTICATED_ASSIGNMENT_V1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_HANDOFF_FIELDS = frozenset({
    "schema", "assignment_operation_id", "policy_id", "policy_sha256", "repository",
    "sprint_id", "source_head", "manifest_sha256", "bootstrap_peer", "assignment_principal",
    "bootstrap_request", "task_id", "story_id", "project_id", "phase",
    "task_manifest_sha256", "slot", "attempt", "epoch", "lease_id", "runner_id",
    "run_id", "service_generation", "probe_sha256", "issued_at_utc", "expires_at_utc",
    "handoff_sha256",
})
_POLICY_FIELDS = frozenset({
    "schema", "policy_id", "repository", "sprint_id", "source_head", "manifest_sha256",
    "owner_principal", "allowed_assignments", "bootstrap_peer", "issuer_peer",
    "allowed_bootstrap_operations", "maximum_handoff_ttl_seconds", "valid_from_utc",
    "expires_at_utc", "revocation_id", "runner_id", "owner_ttl_seconds", "lease_ttl_seconds",
})
_POLICY_DIGEST_FIELDS = frozenset({"policy", "policy_sha256"})
_SIGNER_FIELDS = frozenset({"key_id", "key_class", "purpose", "public_key_fingerprint"})
_UNSIGNED_FIELDS = frozenset({
    "version", "algorithm", "purpose", "request_id", "task_id", "slot", "attempt",
    "epoch", "run_id", "key_id", "expires_at",
})
_INTENT_FIELDS = frozenset({
    "schema", "assignment_operation_id", "request_id", "operation_key", "operation_sha256",
    "payload_sha256", "handoff", "handoff_sha256", "policy", "policy_sha256",
    "authority_expires_at_utc", "issuer_max_ttl_seconds", "minimum_safety_slack_seconds",
    "prepared_at_utc", "manifest_sha256", "lease_id", "probe_sha256",
    "service_generation", "signer", "signing_domain", "unsigned", "unsigned_sha256",
})
_EVENT_TYPES = frozenset({
    "SUPERVISOR_DISPATCH_ISSUANCE_INTENT",
    "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED",
    "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED",
    "SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN",
})
_TERMINAL_STATES = frozenset({"ABSENT", "PENDING", "COMPLETED", "UNKNOWN", "CONFLICT"})


def _closed(value: Any, fields: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ContractError(f"{name} fields do not match the closed schema")
    return value


def _text(value: Any, name: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ContractError(f"{name} must be a non-empty canonical string")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ContractError(f"{name} has an invalid format")
    return value


def _integer(value: Any, name: str, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum or value > 2**63 - 1:
        raise ContractError(f"{name} is outside its integer bounds")
    return value


def _utc(value: Any, name: str) -> datetime:
    text = _text(value, name)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ContractError(f"{name} must be canonical UTC YYYY-MM-DDTHH:MM:SSZ") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        raise ContractError(f"{name} must be canonical UTC YYYY-MM-DDTHH:MM:SSZ")
    return parsed


def _deadline(start: datetime, seconds: int) -> datetime:
    """Add a positive bounded integer TTL without leaking datetime overflow."""
    try:
        return start + timedelta(seconds=seconds)
    except OverflowError:
        return datetime.max.replace(tzinfo=timezone.utc)


def _sha(value: Any, name: str) -> str:
    return _text(value, name, _SHA256)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("issuance JSON contains a duplicate object key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ContractError(f"issuance JSON contains a non-finite number: {value}")


def parse_canonical_json(raw: bytes) -> Any:
    """Parse UTF-8 canonical JSON; reject duplicate keys and noncanonical bytes."""
    if not isinstance(raw, bytes):
        raise ContractError("issuance JSON input must be bytes")
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("issuance JSON is not valid UTF-8 JSON") from exc
    if canonical_bytes(value) != raw:
        raise ContractError("issuance JSON bytes are not canonical")
    return value


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate_key_binding(value: Any) -> dict[str, str]:
    """Validate explicit key class; UNKNOWN is never converted to LEGACY_V1."""
    binding = _closed(value, _SIGNER_FIELDS, "dispatch signer binding")
    key_id = _text(binding["key_id"], "key_id", _ID)
    key_class = binding["key_class"]
    if not isinstance(key_class, str):
        raise ContractError("dispatch signer key_class is not recognized")
    if key_class not in {"LEGACY_V1", "DELEGATED_V1", "UNKNOWN"}:
        raise ContractError("dispatch signer key_class is not recognized")
    if key_class != "DELEGATED_V1":
        raise ContractError("root issuance requires an explicitly classified DELEGATED_V1 key")
    if binding["purpose"] != DISPATCH_INSTRUCTION_PURPOSE:
        raise ContractError("dispatch signer purpose is invalid")
    fingerprint = _sha(binding["public_key_fingerprint"], "public_key_fingerprint")
    return {"key_id": key_id, "key_class": key_class, "purpose": binding["purpose"],
            "public_key_fingerprint": fingerprint}


def validate_policy_identity(value: Any) -> dict[str, Any]:
    """Check closed policy identity and its canonical digest, not its authority."""
    identity = _closed(value, _POLICY_DIGEST_FIELDS, "policy identity")
    policy = _closed(identity["policy"], _POLICY_FIELDS, "assignment policy")
    policy_sha256 = _sha(identity["policy_sha256"], "policy_sha256")
    valid_policy, computed_sha256 = validate_policy(policy)
    if computed_sha256 != policy_sha256:
        raise ContractError("assignment policy digest is invalid")
    return {"policy": valid_policy, "policy_sha256": policy_sha256}


def validate_handoff_identity(value: Any, *, policy: Any, now: datetime) -> dict[str, Any]:
    """Validate exact handoff bindings and digest; shape validation is not authority."""
    handoff = _closed(value, _HANDOFF_FIELDS, "assignment handoff")
    policy_identity = validate_policy_identity(policy)
    root_policy = policy_identity["policy"]
    if now.tzinfo is None or now.utcoffset() != timezone.utc.utcoffset(now):
        raise ContractError("issuance clock must be timezone-aware UTC")
    if handoff["schema"] != HANDOFF_SCHEMA or handoff["policy_sha256"] != policy_identity["policy_sha256"]:
        raise ContractError("assignment handoff schema or policy digest is invalid")
    for name in ("assignment_operation_id", "policy_sha256", "manifest_sha256",
                 "task_manifest_sha256", "probe_sha256", "handoff_sha256"):
        _sha(handoff[name], f"handoff.{name}")
    validate_handoff(handoff, policy=root_policy,
                     policy_sha256=policy_identity["policy_sha256"], now=now)
    # Assignment and policy authorization must already have been established by
    # the trusted Store-bound caller; this pure validator cannot establish it.
    return copy.deepcopy(handoff)


def issuance_identity(handoff: Any, *, policy: Any, now: datetime) -> dict[str, str]:
    """Derive stable deterministic IDs from the complete validated handoff."""
    valid = validate_handoff_identity(handoff, policy=policy, now=now)
    request_id = hashlib.sha256(REQUEST_ID_DOMAIN + canonical_bytes(valid)).hexdigest()[:32]
    operation_digest = hashlib.sha256(
        OPERATION_KEY_DOMAIN + canonical_bytes({
            "assignment_operation_id": valid["assignment_operation_id"],
        })
    ).hexdigest()
    operation_key = "dispatch-issue:" + operation_digest
    return {"request_id": request_id, "operation_key": operation_key,
            "operation_sha256": operation_digest}


def freeze_issuance_intent(
    handoff: Any, *, policy: Any, signer: Any, expires_at: str,
    authority_expires_at_utc: str, issuer_max_ttl_seconds: int,
    minimum_safety_slack_seconds: int, now: datetime,
) -> dict[str, Any]:
    """Freeze exact unsigned v1 fields and all source identity before any signer call."""
    valid_handoff = validate_handoff_identity(handoff, policy=policy, now=now)
    valid_policy = validate_policy_identity(policy)
    valid_signer = validate_key_binding(signer)
    expiry = _utc(expires_at, "expires_at")
    authority_expiry = _utc(authority_expires_at_utc, "authority_expires_at_utc")
    policy_expiry = _utc(valid_policy["policy"]["expires_at_utc"], "policy.expires_at_utc")
    handoff_expiry = _utc(valid_handoff["expires_at_utc"], "handoff.expires_at_utc")
    _integer(issuer_max_ttl_seconds, "issuer_max_ttl_seconds")
    _integer(minimum_safety_slack_seconds, "minimum_safety_slack_seconds")
    prepared_at = now.replace(microsecond=0)
    expected_expiry = min(
        _deadline(prepared_at, issuer_max_ttl_seconds),
        authority_expiry, policy_expiry, handoff_expiry,
    )
    if expiry != expected_expiry or expiry <= now:
        raise ContractError("dispatch expiry does not equal the frozen minimum-validity bound")
    if (expiry - prepared_at).total_seconds() < minimum_safety_slack_seconds:
        raise ContractError("dispatch expiry is shorter than the configured safety slack")
    identity = issuance_identity(valid_handoff, policy=valid_policy, now=now)
    unsigned = {
        "version": 1, "algorithm": "Ed25519", "purpose": DISPATCH_INSTRUCTION_PURPOSE,
        "request_id": identity["request_id"], "task_id": valid_handoff["task_id"],
        "slot": valid_handoff["slot"], "attempt": valid_handoff["attempt"],
        "epoch": valid_handoff["epoch"], "run_id": valid_handoff["run_id"],
        "key_id": valid_signer["key_id"], "expires_at": expires_at,
    }
    if set(unsigned) != _UNSIGNED_FIELDS:
        raise ContractError("internal unsigned dispatch contract drift")
    frozen = {
        "schema": "VST_S2_ROOT_DISPATCH_ISSUANCE_INTENT_V1",
        "assignment_operation_id": valid_handoff["assignment_operation_id"],
        **identity,
        "payload_sha256": "",  # filled over the immutable, unsigned payload below
        "handoff": valid_handoff,
        "handoff_sha256": valid_handoff["handoff_sha256"],
        "policy": valid_policy["policy"],
        "policy_sha256": valid_policy["policy_sha256"],
        "authority_expires_at_utc": authority_expires_at_utc,
        "issuer_max_ttl_seconds": issuer_max_ttl_seconds,
        "minimum_safety_slack_seconds": minimum_safety_slack_seconds,
        "prepared_at_utc": prepared_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manifest_sha256": valid_handoff["manifest_sha256"],
        "lease_id": valid_handoff["lease_id"],
        "probe_sha256": valid_handoff["probe_sha256"],
        "service_generation": valid_handoff["service_generation"],
        "signer": valid_signer,
        "signing_domain": "VST_S2_DISPATCH_INSTRUCTION_V1",
        "unsigned": unsigned,
        "unsigned_sha256": canonical_sha256(unsigned),
    }
    frozen["payload_sha256"] = canonical_sha256({key: value for key, value in frozen.items()
                                                   if key != "payload_sha256"})
    _closed(frozen, _INTENT_FIELDS, "frozen issuance intent")
    return frozen


def validate_frozen_intent(value: Any) -> dict[str, Any]:
    """Revalidate an immutable intent read from an untrusted journal boundary."""
    intent = _closed(value, _INTENT_FIELDS, "frozen issuance intent")
    if intent["schema"] != "VST_S2_ROOT_DISPATCH_ISSUANCE_INTENT_V1":
        raise ContractError("frozen issuance intent schema is invalid")
    _text(intent["request_id"], "request_id", _REQUEST_ID)
    _text(intent["operation_key"], "operation_key")
    _sha(intent["operation_sha256"], "operation_sha256")
    _sha(intent["payload_sha256"], "payload_sha256")
    _sha(intent["unsigned_sha256"], "unsigned_sha256")
    _sha(intent["handoff_sha256"], "handoff_sha256")
    _sha(intent["policy_sha256"], "policy_sha256")
    _sha(intent["manifest_sha256"], "manifest_sha256")
    _sha(intent["probe_sha256"], "probe_sha256")
    _integer(intent["lease_id"], "lease_id")
    _text(intent["service_generation"], "service_generation", _ID)
    _text(intent["signing_domain"], "signing_domain")
    _utc(intent["authority_expires_at_utc"], "authority_expires_at_utc")
    _integer(intent["issuer_max_ttl_seconds"], "issuer_max_ttl_seconds")
    _integer(intent["minimum_safety_slack_seconds"], "minimum_safety_slack_seconds")
    prepared_at = _utc(intent["prepared_at_utc"], "prepared_at_utc")
    handoff = _closed(intent["handoff"], _HANDOFF_FIELDS, "assignment handoff")
    if handoff["schema"] != HANDOFF_SCHEMA:
        raise ContractError("frozen handoff schema is invalid")
    if canonical_sha256({key: item for key, item in handoff.items() if key != "handoff_sha256"}) != handoff["handoff_sha256"]:
        raise ContractError("frozen handoff digest is invalid")
    _closed(intent["unsigned"], _UNSIGNED_FIELDS, "unsigned dispatch instruction")
    validate_key_binding(intent["signer"])
    policy_identity = validate_policy_identity(
        {"policy": intent["policy"], "policy_sha256": intent["policy_sha256"]}
    )
    if canonical_sha256(intent["unsigned"]) != intent["unsigned_sha256"]:
        raise ContractError("frozen unsigned instruction digest is invalid")
    if intent["unsigned"]["request_id"] != intent["request_id"]:
        raise ContractError("frozen request ID differs from the unsigned instruction")
    if intent["unsigned"]["key_id"] != intent["signer"]["key_id"]:
        raise ContractError("frozen key ID differs from signer binding")
    if (intent["assignment_operation_id"] != handoff["assignment_operation_id"]
            or intent["handoff_sha256"] != handoff["handoff_sha256"]
            or intent["policy_sha256"] != handoff["policy_sha256"]):
        raise ContractError("frozen issuance identity differs from its handoff")
    if any(handoff[name] != policy_identity["policy"][name]
           for name in ("policy_id", "repository", "sprint_id", "source_head", "manifest_sha256")):
        raise ContractError("frozen handoff differs from the bound policy")
    expected_request_id = hashlib.sha256(REQUEST_ID_DOMAIN + canonical_bytes(handoff)).hexdigest()[:32]
    operation_digest = hashlib.sha256(OPERATION_KEY_DOMAIN + canonical_bytes({
        "assignment_operation_id": intent["assignment_operation_id"],
    })).hexdigest()
    if (intent["request_id"] != expected_request_id
            or intent["operation_sha256"] != operation_digest
            or intent["operation_key"] != "dispatch-issue:" + operation_digest):
        raise ContractError("frozen deterministic issuance identity is invalid")
    expected_tuple = {
        "manifest_sha256": handoff["manifest_sha256"], "lease_id": handoff["lease_id"],
        "probe_sha256": handoff["probe_sha256"], "service_generation": handoff["service_generation"],
    }
    if any(intent[key] != value for key, value in expected_tuple.items()):
        raise ContractError("frozen current-authority tuple differs from the handoff")
    unsigned_tuple = {
        "task_id": handoff["task_id"], "slot": handoff["slot"], "attempt": handoff["attempt"],
        "epoch": handoff["epoch"], "run_id": handoff["run_id"],
    }
    if any(intent["unsigned"][key] != value for key, value in unsigned_tuple.items()):
        raise ContractError("frozen unsigned instruction differs from the handoff")
    for field in ("expires_at",):
        expiry = _utc(intent["unsigned"][field], f"unsigned.{field}")
        authority_expiry = min(
            _utc(intent["authority_expires_at_utc"], "authority_expires_at_utc"),
            _utc(policy_identity["policy"]["expires_at_utc"], "policy.expires_at_utc"),
            _utc(handoff["expires_at_utc"], "handoff.expires_at_utc"),
        )
        if expiry > authority_expiry:
            raise ContractError("frozen unsigned expiry exceeds authority validity")
        expected_expiry = min(
            _deadline(prepared_at, intent["issuer_max_ttl_seconds"]), authority_expiry,
        )
        if expiry != expected_expiry or (expiry - prepared_at).total_seconds() < intent["minimum_safety_slack_seconds"]:
            raise ContractError("frozen unsigned expiry violates TTL or safety slack")
    expected_payload = canonical_sha256({key: value for key, value in intent.items()
                                         if key != "payload_sha256"})
    if expected_payload != intent["payload_sha256"]:
        raise ContractError("frozen issuance payload digest is invalid")
    return copy.deepcopy(intent)


def reduce_issuance_state(
    row: Any, events: Any, *,
    completion_verifier: Callable[[dict[str, str], bytes, bytes], bool] | None = None,
) -> dict[str, Any]:
    """Reduce normalized immutable journal records. The result never grants signing authority."""
    if row is None and events == []:
        return {"state": "ABSENT", "intent": None, "envelope": None, "may_sign": False,
                "reason": "no issuance records"}
    try:
        if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
            raise ContractError("issuance events must be an ordered list of objects")
        types = [event.get("type") for event in events]
        if any(kind not in _EVENT_TYPES for kind in types):
            raise ContractError("unknown issuance event type")
        if types.count("SUPERVISOR_DISPATCH_ISSUANCE_INTENT") != 1:
            raise ContractError("issuance requires exactly one intent event")
        if types[0] != "SUPERVISOR_DISPATCH_ISSUANCE_INTENT":
            raise ContractError("issuance intent must be the first event")
        terminal = types[1:]
        if terminal not in ([], ["SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED"],
                            ["SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED",
                             "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED"],
                            ["SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED",
                             "SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN"]):
            raise ContractError("issuance event order or multiplicity is invalid")
        intent_event = _closed(events[0], frozenset({"type", "operation_key", "operation",
                               "payload_sha256", "intent"}), "issuance intent event")
        intent = validate_frozen_intent(intent_event["intent"])
        if (intent_event["operation"] != ISSUANCE_OPERATION
                or intent_event["operation_key"] != intent["operation_key"]
                or intent_event["payload_sha256"] != intent["payload_sha256"]):
            raise ContractError("issuance event differs from its frozen intent")
        if not isinstance(row, dict) or set(row) != {"operation_key", "operation", "payload_sha256", "result"}:
            raise ContractError("issuance operation row has an invalid shape")
        if (row["operation_key"] != intent["operation_key"] or row["operation"] != ISSUANCE_OPERATION
                or row["payload_sha256"] != intent["payload_sha256"]
                or row["result"] != {"_vst_state": "PENDING"}):
            raise ContractError("issuance operation row differs from the immutable intent")
        for event in events[1:]:
            if event.get("operation_key") != intent["operation_key"]:
                raise ContractError("issuance event operation key changed")
            if event.get("intent_sha256") != canonical_sha256(intent):
                raise ContractError("issuance event intent digest changed")
            if event.get("unsigned_sha256") != intent["unsigned_sha256"]:
                raise ContractError("issuance event unsigned digest changed")
        if not terminal:
            return {"state": "PENDING", "intent": intent, "envelope": None, "may_sign": False,
                    "reason": "intent is reserved; Store must atomically claim started before signer entry"}
        if terminal[0] == "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED":
            _closed(events[1], frozenset({"type", "operation_key", "intent_sha256",
                   "unsigned_sha256"}), "issuance signing-started event")
        if terminal and terminal[-1] == "SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN":
            _closed(events[-1], frozenset({"type", "operation_key", "intent_sha256",
                   "unsigned_sha256", "error_class"}), "issuance unknown event")
            _text(events[-1]["error_class"], "error_class", _ID)
            return {"state": "UNKNOWN", "intent": intent, "envelope": None, "may_sign": False,
                    "reason": "signer outcome is ambiguous; automatic retry is forbidden"}
        if terminal[0] == "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED":
            if len(terminal) == 1:
                return {"state": "UNKNOWN", "intent": intent, "envelope": None, "may_sign": False,
                        "reason": "signer entry may have occurred; completion is not durable"}
            completed = _closed(events[-1], frozenset({"type", "operation_key", "intent_sha256",
                               "unsigned_sha256", "envelope", "envelope_sha256"}),
                                "issuance completion event")
            envelope = validate_dispatch_instruction(completed["envelope"])
            unsigned = {key: value for key, value in envelope.items() if key != "signature"}
            if unsigned != intent["unsigned"] or canonical_sha256(envelope) != completed["envelope_sha256"]:
                raise ContractError("completed envelope differs from the frozen intent")
            if completion_verifier is None or not callable(completion_verifier):
                raise ContractError("completion verifier is required to accept a signed envelope")
            if envelope["key_id"] != intent["signer"]["key_id"]:
                raise ContractError("completed envelope key ID differs from the frozen signer")
            signature = base64.urlsafe_b64decode(envelope["signature"] + "==")
            try:
                verified = completion_verifier(
                    copy.deepcopy(intent["signer"]),
                    dispatch_instruction_signing_bytes(envelope),
                    signature,
                )
            except Exception as exc:
                raise ContractError("completion signature verifier failed") from exc
            if verified is not True:
                raise ContractError("completion signature or root-pinned signer binding is invalid")
            return {"state": "COMPLETED", "intent": intent, "envelope": copy.deepcopy(envelope),
                    "may_sign": False, "reason": "exact envelope and frozen signer binding verified"}
        raise ContractError("unsupported issuance reducer state")
    except (ContractError, TypeError, ValueError, KeyError) as exc:
        return {"state": "CONFLICT", "intent": None, "envelope": None, "may_sign": False,
                "reason": str(exc)}


def effective_disposition(state: Any, *, revoked: Any, expired: Any) -> str:
    """Overlay current revocation/expiry without rewriting historical journal state."""
    if not isinstance(state, str) or state not in _TERMINAL_STATES:
        return "CONFLICT"
    if type(revoked) is not bool or type(expired) is not bool:
        return "CONFLICT"
    if state == "CONFLICT":
        return "CONFLICT"
    if revoked or expired:
        return "REVOKED_EXPIRED"
    return state
