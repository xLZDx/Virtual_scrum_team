"""Independent analyzer authority: signature binding for AEVE analyzer reports (S5-B, VST-039).

VST trusted code (deterministic, no model calls) signs the canonical analyzer
evidence payload with a dedicated analyzer-authority key under
ANALYZER_AUTHORITY_LABEL. The analyzer process never receives this key. The
authority key is a separate trust root and must be pairwise distinct (bytes
comparison) from every other role key (worker, supervisor, operator, event,
reviewer, runner signer, ...).

The signed payload binds analyzer identity/version/executable digest, profile,
source-tree digest, report digest, manifest digest, run id, one-shot nonce,
candidate head, epoch and the exact analysis scope.

Fail-closed API: sign and verify REQUIRE every other role key (REQUIRED_OTHER_ROLES)
and reject a missing/invalid key or a collision with the analyzer key. verify
REQUIRES verifier-owned expected values for every payload field and an atomic
consume_nonce callback invoked only after signature and binding pass.
Programmer errors (bad keys, bad binding, non-callable consume) raise
ContractError. Hostile or tampered evidence (any shape, any altered field,
wrong signer, replay) returns False and never raises.
"""

from __future__ import annotations

import hmac
from typing import Any, Callable, Mapping

from .contracts import (
    ContractError,
    _GLOB_CHARS,
    _check_keys,
    _req_hex,
    _req_int,
    _req_str,
    _validate_repo_path,
)
from .signing import ANALYZER_AUTHORITY_LABEL, MIN_KEY_BYTES, sign

ANALYZER_EVIDENCE_TYPE = "analyzer_authority_evidence_v1"
ANALYZER_PAYLOAD_FIELDS = (
    "type",
    "analyzer_id",
    "analyzer_version",
    "analyzer_sha256",
    "profile_id",
    "profile_sha256",
    "source_tree_sha256",
    "report_sha256",
    "manifest_sha256",
    "run_id",
    "nonce",
    "candidate_head",
    "epoch",
    "analysis_scope",
)
MIN_NONCE_CHARS = 16
# Roles whose keys the analyzer authority key must differ from (gate.py: key=worker,
# supervisor_key, operator_key, event_key, reviewer keys, signer_key=runner signer).
REQUIRED_OTHER_ROLES = ("worker", "supervisor", "operator", "event", "reviewer", "runner_signer")
_BINDING_FIELDS = tuple(f for f in ANALYZER_PAYLOAD_FIELDS if f != "type")
_HEX64_FIELDS = (
    "analyzer_sha256",
    "profile_sha256",
    "source_tree_sha256",
    "report_sha256",
    "manifest_sha256",
)


def build_analyzer_payload(
    *,
    analyzer_id: str,
    analyzer_version: str,
    analyzer_sha256: str,
    profile_id: str,
    profile_sha256: str,
    source_tree_sha256: str,
    report_sha256: str,
    manifest_sha256: str,
    run_id: str,
    nonce: str,
    candidate_head: str,
    epoch: int,
    analysis_scope: list[str],
) -> dict[str, Any]:
    """Pure: validate and return the canonical unsigned payload (AC-4)."""
    payload: dict[str, Any] = {
        "type": ANALYZER_EVIDENCE_TYPE,
        "analyzer_id": analyzer_id,
        "analyzer_version": analyzer_version,
        "analyzer_sha256": analyzer_sha256,
        "profile_id": profile_id,
        "profile_sha256": profile_sha256,
        "source_tree_sha256": source_tree_sha256,
        "report_sha256": report_sha256,
        "manifest_sha256": manifest_sha256,
        "run_id": run_id,
        "nonce": nonce,
        "candidate_head": candidate_head,
        "epoch": epoch,
        "analysis_scope": list(analysis_scope) if isinstance(analysis_scope, (list, tuple)) else analysis_scope,
    }
    return validate_analyzer_payload(payload)


def validate_analyzer_payload(payload: object) -> dict[str, Any]:
    """Closed-shape validation of the unsigned payload; raises ContractError."""
    _check_keys(payload, ANALYZER_PAYLOAD_FIELDS, "analyzer payload")
    assert isinstance(payload, dict)
    if payload["type"] != ANALYZER_EVIDENCE_TYPE:
        raise ContractError(f"analyzer payload.type: must be {ANALYZER_EVIDENCE_TYPE!r}")
    for name in ("analyzer_id", "analyzer_version", "profile_id", "run_id", "nonce"):
        _req_str(payload[name], f"analyzer payload.{name}")
    if len(payload["nonce"]) < MIN_NONCE_CHARS:
        raise ContractError(f"analyzer payload.nonce: must be >= {MIN_NONCE_CHARS} characters")
    for name in _HEX64_FIELDS:
        _req_hex(payload[name], f"analyzer payload.{name}", 64)
    _req_hex(payload["candidate_head"], "analyzer payload.candidate_head", 40)
    _req_int(payload["epoch"], "analyzer payload.epoch", 1)
    scope = payload["analysis_scope"]
    if not isinstance(scope, list) or not scope:
        raise ContractError("analyzer payload.analysis_scope: must be a non-empty list")
    for index, path in enumerate(scope):
        _validate_repo_path(path, f"analyzer payload.analysis_scope[{index}]")
        if any(ch in _GLOB_CHARS for ch in path):
            raise ContractError(f"analyzer payload.analysis_scope[{index}]: globs are not allowed")
    if len(set(scope)) != len(scope):
        raise ContractError("analyzer payload.analysis_scope: must not contain duplicates")
    return payload


def _key_bytes(value: object, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray)) or len(value) < MIN_KEY_BYTES:
        raise ContractError(f"{name}: must be bytes of length >= {MIN_KEY_BYTES}")
    return bytes(value)


def _check_authority_key(analyzer_key: object, other_role_keys: object) -> bytes:
    """Fail closed: every required role key must be present, valid and different."""
    raw = _key_bytes(analyzer_key, "analyzer key")
    if not isinstance(other_role_keys, Mapping):
        raise ContractError("other_role_keys: required mapping of role name to key")
    unknown = sorted(str(r) for r in other_role_keys if r not in REQUIRED_OTHER_ROLES)
    if unknown:
        raise ContractError(f"other_role_keys: unknown role(s): {', '.join(unknown)}")
    for role in REQUIRED_OTHER_ROLES:
        if role not in other_role_keys:
            raise ContractError(f"other_role_keys: missing role {role!r}")
        other = _key_bytes(other_role_keys[role], f"{role} key")
        if hmac.compare_digest(other, raw):
            raise ContractError(f"analyzer key must be distinct from the {role} key")
    return raw


def sign_analyzer_evidence(
    payload: dict[str, Any],
    analyzer_key: bytes,
    other_role_keys: Mapping[str, bytes],
) -> dict[str, Any]:
    """Return payload + signature under the analyzer-authority key and domain label only."""
    raw = _check_authority_key(analyzer_key, other_role_keys)
    if not isinstance(payload, dict):
        raise ContractError("analyzer payload: must be a dict")
    body = validate_analyzer_payload(dict(payload))
    return {**body, "signature": sign(body, raw, ANALYZER_AUTHORITY_LABEL)}


def _strict_equal(a: Any, b: Any) -> bool:
    """Equality with exact types (bool never equals int); lists compared element-wise."""
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(_strict_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, str):
        return hmac.compare_digest(a.encode("utf-8", "surrogatepass"), b.encode("utf-8", "surrogatepass"))
    return a == b


def verify_analyzer_evidence(
    evidence: object,
    analyzer_key: bytes,
    *,
    expected_binding: Mapping[str, Any],
    consume_nonce: Callable[[str], bool],
    other_role_keys: Mapping[str, bytes],
    consume: bool = True,
) -> bool:
    """True iff evidence is signed by the analyzer authority and matches the verifier's binding.

    consume=True (default, safe) consumes the one-shot nonce after signature and
    binding pass. consume=False verifies WITHOUT touching the nonce store (the
    caller must then call consume_nonce itself exactly once, e.g. the gate only
    after its final verdict); consume_nonce is not called in that mode.

    expected_binding must hold a verifier-owned value for EVERY payload field
    except signature and type (see ANALYZER_PAYLOAD_FIELDS), including run_id
    and nonce; each is compared with strict type equality. consume_nonce(nonce)
    is an atomic one-shot callback (True = first use) called only after the
    signature and binding pass; False rejects the replay.

    Raises ContractError only for programmer errors (keys, binding, callback).
    Any hostile or tampered evidence returns False.
    """
    raw = _check_authority_key(analyzer_key, other_role_keys)
    if not callable(consume_nonce):
        raise ContractError("consume_nonce: must be callable")
    if not isinstance(consume, bool):
        raise ContractError("consume: must be a bool")
    if not isinstance(expected_binding, Mapping):
        raise ContractError("expected_binding: must be a mapping")
    missing = [f for f in _BINDING_FIELDS if f not in expected_binding]
    extra = sorted(str(k) for k in expected_binding if k not in _BINDING_FIELDS)
    if missing or extra:
        raise ContractError(
            f"expected_binding: missing {missing}, unknown {extra}; must cover every payload field"
        )
    # The verifier's own expectation must itself be a valid payload.
    validate_analyzer_payload({"type": ANALYZER_EVIDENCE_TYPE, **{f: expected_binding[f] for f in _BINDING_FIELDS}})

    try:
        if not isinstance(evidence, dict):
            return False
        signature = evidence.get("signature")
        if not isinstance(signature, str) or not signature.isascii():
            return False
        body = {k: v for k, v in evidence.items() if k != "signature"}
        validate_analyzer_payload(body)  # exact keys, types, hex, scope, nonce length
        if not all(_strict_equal(body[f], expected_binding[f]) for f in _BINDING_FIELDS):
            return False
        if not hmac.compare_digest(
            sign(body, raw, ANALYZER_AUTHORITY_LABEL).encode("ascii"), signature.encode("ascii")
        ):
            return False
    except Exception:  # hostile evidence must never raise
        return False
    if not consume:
        return True
    return consume_nonce(body["nonce"]) is True
