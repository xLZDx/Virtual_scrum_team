"""Deterministic analyzer evidence record builder (S5-E, VST-042, AC-12/AC-13).

Pure stdlib code: no I/O, no clock, no model call, no execution. It assembles the
plan section 6 evidence record ONLY from values the caller passes in (a v3
manifest, a v3 StaticAnalysis receipt, a GateDecision and caller-supplied facts).
Nothing is invented: every field that cannot be derived from a supplied value is
labeled ``NOT_RUN`` (proof or integration absent), and every unsupported analyzer
rule is labeled ``UNSUPPORTED``; neither is ever described as success. Secret
material is never accepted: only key ids and verification outcomes.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any, Mapping

from .contracts import ContractError, canonical_bytes, manifest_sha256

EVIDENCE_RECORD_VERSION = "vst-analyzer-evidence-record-v1"
NOT_RUN = "NOT_RUN"
UNSUPPORTED = "UNSUPPORTED"

# Caller-supplied facts (all optional); anything missing is labeled NOT_RUN.
FACT_FIELDS = (
    "repository",          # repository identity string
    "head",                # exact full 40-hex git HEAD
    "git_status_note",     # clean / dirty note from git status
    "run_id", "epoch",
    "policy_config_sha256",
    "excluded_paths",      # list of {path, reason}
    "acceptance_mapping_source",
    "command",             # exact adapter command / argv
    "runtime_identity",    # platform / interpreter
    "limits",              # enforced resource / network / write boundaries
    "signer_authority", "signer_key_id",
    "signature_verified",  # bool outcome of the gate-side verification
    "test_command", "test_ids", "test_counts", "test_outcome",
    "skipped_xfail_ids",
    "not_run_owners",      # {field: owner} for unavailable proofs
)
_RECEIPT_FIELDS = (
    "analyzer_id", "analyzer_version", "analyzer_sha256", "profile_id", "profile_sha256",
    "source_tree_sha256", "report_sha256", "analysis_scope", "coverage",
    "covered_acceptance", "findings",
)


def _missing(field: str, owners: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"label": NOT_RUN, "reason": f"{field} not provided"}
    owner = owners.get(field)
    if isinstance(owner, str) and owner:
        out["owner"] = owner
    return out


def build_evidence_record(
    *,
    manifest: Mapping[str, Any] | None = None,
    receipt: Mapping[str, Any] | None = None,
    decision: Mapping[str, Any] | None = None,
    facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the deterministic evidence record plus its canonical ``record_sha256``.

    Unknown ``facts`` keys raise ContractError (closed shape). Equal inputs always
    produce byte-identical canonical output.
    """
    facts = {} if facts is None else dict(facts)
    unknown = sorted(set(facts) - set(FACT_FIELDS))
    if unknown:
        raise ContractError(f"facts: unknown field(s): {', '.join(unknown)}")
    owners = facts.get("not_run_owners")
    owners = owners if isinstance(owners, Mapping) else {}

    def fact(name: str) -> Any:
        return copy.deepcopy(facts[name]) if name in facts else _missing(name, owners)

    def rcpt(name: str) -> Any:
        if isinstance(receipt, Mapping) and name in receipt:
            return copy.deepcopy(receipt[name])
        return _missing(name, owners)

    manifest_ok = isinstance(manifest, Mapping)
    required = (
        list(manifest["required_rule_ids"])
        if manifest_ok and isinstance(manifest.get("required_rule_ids"), list)
        else _missing("required_rule_ids", owners)
    )
    statuses = receipt.get("rule_statuses") if isinstance(receipt, Mapping) else None
    if isinstance(statuses, list):
        checked = sorted(s["rule_id"] for s in statuses if s.get("status") == "SUPPORTED_AND_CHECKED")
        unsupported: Any = [
            {"rule_id": s["rule_id"], "label": UNSUPPORTED}
            for s in sorted(statuses, key=lambda s: s["rule_id"]) if s.get("status") == "UNSUPPORTED"
        ]
    else:
        checked = _missing("checked_rules", owners)
        unsupported = _missing("unsupported_rules", owners)

    record: dict[str, Any] = {
        "record_version": EVIDENCE_RECORD_VERSION,
        "repository": fact("repository"),
        "head": fact("head"),
        "git_status_note": fact("git_status_note"),
        "manifest_sha256": (
            manifest_sha256(dict(manifest)) if manifest_ok else _missing("manifest_sha256", owners)
        ),
        "task_id": manifest["task_id"] if manifest_ok and "task_id" in manifest else _missing("task_id", owners),
        "run_id": fact("run_id"),
        "epoch": fact("epoch"),
        "analyzer_id": rcpt("analyzer_id"),
        "analyzer_version": rcpt("analyzer_version"),
        "analyzer_sha256": rcpt("analyzer_sha256"),
        "profile_id": rcpt("profile_id"),
        "profile_sha256": rcpt("profile_sha256"),
        "policy_config_sha256": fact("policy_config_sha256"),
        "analysis_scope": rcpt("analysis_scope"),
        "source_tree_sha256": rcpt("source_tree_sha256"),
        "excluded_paths": fact("excluded_paths"),
        "required_rules": required,
        "checked_rules": checked,
        "unsupported_rules": unsupported,
        "coverage": rcpt("coverage"),
        "covered_acceptance": rcpt("covered_acceptance"),
        "acceptance_mapping_source": fact("acceptance_mapping_source"),
        "findings": rcpt("findings"),
        "command": fact("command"),
        "runtime_identity": fact("runtime_identity"),
        "limits": fact("limits"),
        "report_sha256": rcpt("report_sha256"),
        "signer_authority": fact("signer_authority"),
        "signer_key_id": fact("signer_key_id"),
        "signature_verified": (
            facts["signature_verified"] if isinstance(facts.get("signature_verified"), bool)
            else _missing("signature_verified", owners)
        ),
        "gate_verdict": decision["verdict"] if isinstance(decision, Mapping) and "verdict" in decision
        else _missing("gate_verdict", owners),
        "gate_reasons": list(decision["reasons"]) if isinstance(decision, Mapping) and "reasons" in decision
        else _missing("gate_reasons", owners),
        "test_command": fact("test_command"),
        "test_ids": fact("test_ids"),
        "test_counts": fact("test_counts"),
        "test_outcome": fact("test_outcome"),
        "skipped_xfail_ids": fact("skipped_xfail_ids"),
    }
    digest = hashlib.sha256(canonical_bytes(record)).hexdigest()
    return {**record, "record_sha256": digest}


def verify_evidence_record(record: object) -> bool:
    """True iff ``record_sha256`` matches the canonical bytes of the rest (changed bytes rejected)."""
    try:
        if not isinstance(record, dict) or record.get("record_version") != EVIDENCE_RECORD_VERSION:
            return False
        body = {k: v for k, v in record.items() if k != "record_sha256"}
        return record.get("record_sha256") == hashlib.sha256(canonical_bytes(body)).hexdigest()
    except Exception:
        return False
