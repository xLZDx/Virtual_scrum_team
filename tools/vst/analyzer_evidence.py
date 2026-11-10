"""Deterministic analyzer evidence record builder (S5-E, VST-042, AC-12/AC-13).

Pure stdlib code: no I/O, no clock, no model call, no execution. It assembles the
plan section 6 evidence record ONLY from values the caller passes in (a v3
manifest, a v3 StaticAnalysis receipt, a GateDecision and caller-supplied facts).
Nothing is invented: every field that cannot be derived from a supplied value is
labeled ``NOT_RUN`` (proof or integration absent), and every unsupported analyzer
rule is labeled ``UNSUPPORTED``; neither is ever described as success. Secret
material is never accepted: only key ids and verification outcomes.

Shapes are validated with the contract validators; every problem raises
ContractError. Coverage is re-derived from rule_statuses, head/epoch come from
the validated receipt and must agree with the decision and any supplied fact,
and ``signature_verified`` is derived only from an accepting decision that lists
this receipt among its required receipt hashes. Set-like fact lists
(excluded_paths, test_ids, skipped_xfail_ids) are emitted sorted and unique.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any, Mapping

from .contracts import (
    ContractError,
    canonical_bytes,
    manifest_sha256,
    receipt_sha256,
    validate_gate_decision,
    validate_receipt,
    validate_task_manifest,
)

EVIDENCE_RECORD_VERSION = "vst-analyzer-evidence-record-v1"
NOT_RUN = "NOT_RUN"
UNSUPPORTED = "UNSUPPORTED"
_ACCEPTING = frozenset({"APPROVE", "APPROVED_WITH_WAIVER"})

# Caller-supplied facts (all optional); anything missing is labeled NOT_RUN.
FACT_FIELDS = (
    "repository",          # repository identity string
    "head",                # exact full 40-hex git HEAD (must equal the receipt head)
    "git_status_note",     # clean / dirty note from git status
    "run_id", "epoch",     # epoch must equal the receipt epoch
    "policy_config_sha256",
    "excluded_paths",      # list of {path, reason}; sorted by path
    "acceptance_mapping_source",
    "command",             # exact adapter command / argv (order significant)
    "runtime_identity",    # platform / interpreter
    "limits",              # enforced resource / network / write boundaries
    "signer_authority", "signer_key_id",
    "signature_verified",  # may only agree with the decision-derived value
    "test_command", "test_ids", "test_counts", "test_outcome",
    "skipped_xfail_ids",
    "pinned_role_table_sha256", "pinned_aeve_head",  # gate pins; drive the *_pin_check fields
    "not_run_owners",      # {field: owner} for unavailable proofs
)
_SORTED_STR_LISTS = ("test_ids", "skipped_xfail_ids")


def _plain(value: Any, ctx: str) -> None:
    """Allow only None/bool/int/str/list/dict(str keys): no float, tuple, set, bytes."""
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _plain(item, f"{ctx}[{i}]")
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ContractError(f"{ctx}: non-string key")
            _plain(v, f"{ctx}.{k}")
        return
    raise ContractError(f"{ctx}: unsupported value type {type(value).__name__}")


def _missing(field: str, owners: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"label": NOT_RUN, "reason": f"{field} not provided"}
    owner = owners.get(field)
    if isinstance(owner, str) and owner:
        out["owner"] = owner
    return out


def _pin_check(pin: Any, receipt: Any, field: str) -> str:
    """PASS/FAIL from a strict comparison of the gate pin with the receipt value; NOT_RUN if either is absent."""
    if pin is None or receipt is None:
        return NOT_RUN
    if type(pin) is not str:
        raise ContractError(f"facts.pinned_{field}: must be a string")
    return "PASS" if receipt[field] == pin else "FAIL"


def _derive_coverage(statuses: list[dict]) -> str:
    unsupported = [s for s in statuses if s["status"] == "UNSUPPORTED"]
    if not unsupported:
        return "FULL"
    return "PARTIAL" if len(unsupported) < len(statuses) else "NOT_COVERED"


def build_evidence_record(
    *,
    manifest: Mapping[str, Any] | None = None,
    receipt: Mapping[str, Any] | None = None,
    decision: Mapping[str, Any] | None = None,
    facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the deterministic evidence record plus its canonical ``record_sha256``.

    Raises ContractError (only) for unknown/contradicting facts, invalid shapes
    or non-canonical values. Equal inputs give byte-identical canonical output.
    """
    try:
        return _build(manifest, receipt, decision, facts)
    except ContractError:
        raise
    except Exception as exc:  # never leak KeyError/TypeError/AttributeError
        raise ContractError(f"evidence record: malformed input ({type(exc).__name__})") from exc


def _build(manifest: Any, receipt: Any, decision: Any, facts_in: Any) -> dict[str, Any]:
    if facts_in is not None and not isinstance(facts_in, Mapping):
        raise ContractError("facts: must be a mapping")
    facts = {} if facts_in is None else dict(facts_in)
    unknown = sorted(str(k) for k in set(facts) - set(FACT_FIELDS))
    if unknown:
        raise ContractError(f"facts: unknown field(s): {', '.join(unknown)}")
    _plain(facts, "facts")
    owners = facts.get("not_run_owners")
    owners = owners if isinstance(owners, Mapping) else {}

    vm = validate_task_manifest(dict(manifest)) if manifest is not None else None
    if vm is not None and vm.get("contract_version") != 3:
        raise ContractError("manifest: must be a v3 manifest")
    vr = validate_receipt(dict(receipt)) if receipt is not None else None
    if vr is not None and (vr.get("contract_version") != 3 or vr["receipt_type"] != "StaticAnalysis"):
        raise ContractError("receipt: must be a v3 StaticAnalysis receipt")
    vd = validate_gate_decision(dict(decision)) if decision is not None else None
    manifest_hash = manifest_sha256(vm) if vm is not None else None
    if vr is not None and manifest_hash is not None and vr["manifest_sha256"] != manifest_hash:
        raise ContractError("receipt: manifest_sha256 does not match the manifest")
    if vr is not None and vm is not None and vr["task_id"] != vm["task_id"]:
        raise ContractError("receipt: task_id does not match the manifest")
    if vr is not None and vd is not None and (
            vd["candidate_head"] != vr["candidate_head"] or vd["epoch"] != vr["epoch"]
            or (vm is not None and vd["task_id"] != vm["task_id"])):
        raise ContractError("decision: head/epoch/task contradict the receipt")

    head = vr["candidate_head"] if vr is not None else (vd["candidate_head"] if vd is not None else None)
    epoch = vr["epoch"] if vr is not None else (vd["epoch"] if vd is not None else None)
    for name, derived in (("head", head), ("epoch", epoch)):
        if name in facts and derived is not None and facts[name] != derived:
            raise ContractError(f"facts.{name}: contradicts the validated receipt/decision")

    satisfied = (
        vd is not None and vr is not None and vd["verdict"] in _ACCEPTING
        and receipt_sha256(vr) in vd["required_receipt_hashes"]
    )
    if facts.get("signature_verified") is True and not satisfied:
        raise ContractError("facts.signature_verified: True contradicts the decision")
    if "signature_verified" in facts and not isinstance(facts["signature_verified"], bool):
        raise ContractError("facts.signature_verified: must be a bool")
    if facts.get("signature_verified") is False and satisfied:
        raise ContractError("facts.signature_verified: False contradicts the accepting decision")

    def fact(name: str) -> Any:
        if name not in facts:
            return _missing(name, owners)
        value = copy.deepcopy(facts[name])
        if name in _SORTED_STR_LISTS:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ContractError(f"facts.{name}: must be a list of strings")
            return sorted(set(value))
        if name == "excluded_paths":
            if not isinstance(value, list) or not all(
                    isinstance(v, dict) and set(v) == {"path", "reason"}
                    and isinstance(v["path"], str) and isinstance(v["reason"], str) for v in value):
                raise ContractError("facts.excluded_paths: must be a list of {path, reason}")
            return sorted(value, key=lambda v: (v["path"], v["reason"]))
        return value

    def rcpt(name: str) -> Any:
        return copy.deepcopy(vr[name]) if vr is not None else _missing(name, owners)

    if vr is not None:
        statuses = vr["rule_statuses"]
        checked: Any = sorted(s["rule_id"] for s in statuses if s["status"] == "SUPPORTED_AND_CHECKED")
        unsupported: Any = [
            {"rule_id": s["rule_id"], "label": UNSUPPORTED}
            for s in sorted(statuses, key=lambda s: s["rule_id"]) if s["status"] == "UNSUPPORTED"
        ]
        coverage: Any = _derive_coverage(statuses)
    else:
        checked = _missing("checked_rules", owners)
        unsupported = _missing("unsupported_rules", owners)
        coverage = _missing("coverage", owners)

    record: dict[str, Any] = {
        "record_version": EVIDENCE_RECORD_VERSION,
        "repository": fact("repository"),
        "head": head if head is not None else _missing("head", owners),
        "git_status_note": fact("git_status_note"),
        "manifest_sha256": manifest_hash if manifest_hash is not None else _missing("manifest_sha256", owners),
        "task_id": vm["task_id"] if vm is not None else _missing("task_id", owners),
        "run_id": fact("run_id"),
        "epoch": epoch if epoch is not None else _missing("epoch", owners),
        "analyzer_id": rcpt("analyzer_id"),
        "analyzer_version": rcpt("analyzer_version"),
        "analyzer_sha256": rcpt("analyzer_sha256"),
        "profile_id": rcpt("profile_id"),
        "profile_sha256": rcpt("profile_sha256"),
        "policy_config_sha256": fact("policy_config_sha256"),
        "analysis_scope": rcpt("analysis_scope"),
        "source_tree_sha256": rcpt("source_tree_sha256"),
        "excluded_paths": fact("excluded_paths"),
        "required_rules": list(vm["required_rule_ids"]) if vm is not None else _missing("required_rule_ids", owners),
        "checked_rules": checked,
        "unsupported_rules": unsupported,
        "coverage": coverage,
        "covered_acceptance": rcpt("covered_acceptance"),
        "acceptance_mapping_source": fact("acceptance_mapping_source"),
        "findings": rcpt("findings"),
        "command": fact("command"),
        "runtime_identity": fact("runtime_identity"),
        "limits": fact("limits"),
        "report_sha256": rcpt("report_sha256"),
        # Signed receipt values. The pin check is PASS/FAIL only when the caller supplies the gate pin
        # (strict str equality with the receipt value); without a pin or a receipt it stays NOT_RUN.
        "role_table_sha256": rcpt("role_table_sha256"),
        "role_table_sha256_pin_check": _pin_check(facts.get("pinned_role_table_sha256"), vr, "role_table_sha256"),
        "aeve_head": rcpt("aeve_head"),
        "aeve_head_pin_check": _pin_check(facts.get("pinned_aeve_head"), vr, "aeve_head"),
        "model_residual": rcpt("model_residual"),
        "reviewed_paths_sha256": rcpt("reviewed_paths_sha256"),
        "findings_count": rcpt("findings_count"),
        "highest_severity": rcpt("highest_severity"),
        "signer_authority": fact("signer_authority"),
        "signer_key_id": fact("signer_key_id"),
        "signature_verified": True if satisfied else _missing("signature_verified", owners),
        "gate_verdict": vd["verdict"] if vd is not None else _missing("gate_verdict", owners),
        "gate_reasons": list(vd["reasons"]) if vd is not None else _missing("gate_reasons", owners),
        "test_command": fact("test_command"),
        "test_ids": fact("test_ids"),
        "test_counts": fact("test_counts"),
        "test_outcome": fact("test_outcome"),
        "skipped_xfail_ids": fact("skipped_xfail_ids"),
    }
    _plain(record, "record")
    digest = hashlib.sha256(canonical_bytes(record)).hexdigest()
    return {**record, "record_sha256": digest}


def verify_evidence_record(
    record: object, *, expected_head: str, expected_manifest_sha256: str
) -> bool:
    """True iff the digest matches the canonical bytes AND the record is for the
    expected exact head and manifest (changed bytes or a stale head are rejected)."""
    try:
        if not isinstance(record, dict) or record.get("record_version") != EVIDENCE_RECORD_VERSION:
            return False
        if record.get("head") != expected_head or record.get("manifest_sha256") != expected_manifest_sha256:
            return False
        body = {k: v for k, v in record.items() if k != "record_sha256"}
        return record.get("record_sha256") == hashlib.sha256(canonical_bytes(body)).hexdigest()
    except Exception:
        return False
