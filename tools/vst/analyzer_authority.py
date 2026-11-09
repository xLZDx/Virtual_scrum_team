"""Independent analyzer authority: signature binding for AEVE analyzer reports (S5-B, VST-039).

VST trusted code (deterministic, no model calls) signs the canonical analyzer
evidence payload with a dedicated analyzer-authority key under
ANALYZER_AUTHORITY_LABEL. The analyzer process never receives this key. The
authority key is a separate trust root and must be pairwise distinct (bytes
comparison) from every other role key (worker, supervisor, operator, event,
reviewer, runner signer, ...).

The signed payload binds analyzer identity/version/executable digest, profile,
source-tree digest, report digest, manifest digest, run id, one-shot nonce,
candidate head, epoch and the exact analysis scope. verify_analyzer_evidence()
returns False (never raises) for any altered field, wrong role key, or replayed
request; it raises ContractError only for an invalid key or a key collision.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .contracts import (
    ContractError,
    _GLOB_CHARS,
    _check_keys,
    _req_hex,
    _req_int,
    _req_str,
    _validate_repo_path,
)
from .signing import ANALYZER_AUTHORITY_LABEL, MIN_KEY_BYTES, sign, verify

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


def _check_authority_key(analyzer_key: object, other_role_keys: Mapping[str, object] | None) -> bytes:
    if not isinstance(analyzer_key, (bytes, bytearray)) or len(analyzer_key) < MIN_KEY_BYTES:
        raise ContractError(f"analyzer key: must be bytes of length >= {MIN_KEY_BYTES}")
    raw = bytes(analyzer_key)
    for role, other in (other_role_keys or {}).items():
        if other is None:
            continue
        if not isinstance(other, (bytes, bytearray)):
            raise ContractError(f"{role} key: must be bytes")
        if bytes(other) == raw:
            raise ContractError(f"analyzer key must be distinct from the {role} key")
    return raw


def sign_analyzer_evidence(
    payload: dict[str, Any],
    analyzer_key: bytes,
    other_role_keys: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    """Return payload + signature under the analyzer-authority key and domain label only."""
    raw = _check_authority_key(analyzer_key, other_role_keys)
    body = validate_analyzer_payload(dict(payload))
    return {**body, "signature": sign(body, raw, ANALYZER_AUTHORITY_LABEL)}


def verify_analyzer_evidence(
    evidence: object,
    analyzer_key: bytes,
    *,
    expected_run_id: str,
    expected_nonce: str,
    expected_binding: Mapping[str, Any] | None = None,
    consumed_nonces: Iterable[str] = (),
    other_role_keys: Mapping[str, bytes] | None = None,
) -> bool:
    """True iff evidence is a well-formed analyzer payload signed by the analyzer authority.

    Replay protection: run_id and nonce must equal the caller's expected values
    and the nonce must not be in consumed_nonces. expected_binding optionally
    pins other payload fields (manifest_sha256, candidate_head, epoch,
    source_tree_sha256, ...) that the verifier computed itself; any mismatch is False.
    """
    raw = _check_authority_key(analyzer_key, other_role_keys)
    if not isinstance(evidence, dict) or not isinstance(evidence.get("signature"), str):
        return False
    body = {k: v for k, v in evidence.items() if k != "signature"}
    try:
        validate_analyzer_payload(body)
    except ContractError:
        return False
    if body["run_id"] != expected_run_id or body["nonce"] != expected_nonce:
        return False
    if expected_nonce in set(consumed_nonces):
        return False
    for name, value in (expected_binding or {}).items():
        if name not in body or body[name] != value:
            return False
    return verify(evidence, raw, ANALYZER_AUTHORITY_LABEL)
