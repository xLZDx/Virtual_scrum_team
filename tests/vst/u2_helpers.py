"""Shared builders for the U2-6 negative-case tests (test_u2_bridge.py, test_u2_gate.py).

Everything here is synthetic: a throwaway git repository in a temp dir, hand-built uc.role-result.v1 documents,
hand-built analyzer reports, local HMAC keys. No AEVE, no model, no network. Helpers never weaken a product check;
they only construct inputs and call the unchanged product functions.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import os
import pathlib
import subprocess
from dataclasses import dataclass
from typing import Any

from tools.vst import analyzer_authority, contracts, gate, signing
from tools.vst.analyzer_adapter import AdapterResult, AnalysisReport, Outcome, source_tree_digest
from tools.vst.contracts import RECEIPT_V3_LABEL, canonical_bytes
from tools.vst.receipt_builder import build_static_receipt
from tools.vst.rule_coverage import FROZEN_CATALOG_SHA256, load_catalog

from tests.vst.e1e4_helpers import (
    EPOCH, EVENT_KEY, KEY, OPERATOR_KEY, ROLE as ROLE_SHA, SUPERVISOR_KEY, TASK, manifest, mhash, unsigned_receipt,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

ANALYZER_KEY = b"u2-analyzer-authority-key-0123456789-abc"
SIGNER_KEY = b"u2-test-isolated-signer-key-0123456789"
REVIEWER_KEY = b"u2-reviewer-authority-key-0123456789"
OTHER_ROLE_KEYS = {
    "worker": KEY, "supervisor": SUPERVISOR_KEY, "operator": OPERATOR_KEY, "event": EVENT_KEY,
    "reviewer": REVIEWER_KEY, "runner_signer": SIGNER_KEY,
}

ROLE = "opensource-sanitizer"  # class LOCAL in catalog/role_table.json
PATHS = ["docs/b.md", "src/a.py"]
TABLE_SHA = "a1" * 32
AEVE_HEAD = "d4" * 20
SNAPSHOT = "b3" * 32
FAKE_SECRET = "sk_live_FAKE0123456789SECRET"
BRIDGE_FIELDS = contracts.BRIDGE_FACT_FIELDS


# ----------------------------------------------------------------------------------------------- git
def git(repo: pathlib.Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "u2-test", "GIT_AUTHOR_EMAIL": "u2-test@example.invalid",
        "GIT_COMMITTER_NAME": "u2-test", "GIT_COMMITTER_EMAIL": "u2-test@example.invalid",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
    }
    done = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)
    return done.stdout.strip()


def make_repo(parent: pathlib.Path, name: str = "repo") -> tuple[pathlib.Path, str]:
    """A clean one-commit repository tracking docs/b.md and src/a.py. Returns (path, 40-hex HEAD)."""
    repo = parent / name
    (repo / "src").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "src" / "a.py").write_bytes(b"x = 1\n")
    (repo / "docs" / "b.md").write_bytes(b"# b\n")
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init")
    return repo, git(repo, "rev-parse", "HEAD")


# ------------------------------------------------------------------------------------------ role result
def uc_finding(severity: str = "MAJOR", path: str = "src/a.py", line: int = 3, rule: str = "py-silent-except-swallow") -> dict:
    return {"rule_id": rule, "severity": severity, "path": path, "line": line, "column": 1, "evidence_hash": "c3" * 32}


def paths_sha(paths) -> str:
    return hashlib.sha256(canonical_bytes(sorted(paths))).hexdigest()


def role_result(head: str, paths=PATHS, *, role: str = ROLE, klass: str = "LOCAL", status: str = "CLEAN",
                findings=(), residual=(), uncovered=(), purpose: str = "receipt", table_sha: str = TABLE_SHA,
                aeve_head: str = AEVE_HEAD, changed_sha: str | None = None, extra_entries=(), **over) -> dict:
    entry = {
        "role": role, "canonical_role": role, "class": klass, "status": status,
        "executors": [{"id": "g2.python-rules", "status": "COMPLETE", "snapshot_hash": SNAPSHOT}],
        "findings": list(findings), "uncovered": list(uncovered), "model_residual": list(residual),
    }
    entries = [entry, *extra_entries]
    doc = {
        "schema_version": "uc.role-result.v1", "request_id": "req-1", "base_revision": head, "snapshot_hash": SNAPSHOT,
        "iteration_id": "it-1", "exit_code": 0 if all(e["status"] == "CLEAN" for e in entries) else 3,
        "roles": entries, "role_table_sha256": table_sha, "aeve_head": aeve_head, "purpose": purpose,
        "changed_paths_sha256": changed_sha or paths_sha(paths),
    }
    doc.update(over)
    return doc


# --------------------------------------------------------------------------------------- analyzer report
def report_finding(rule: str = "R1", severity: str = "LOW", path: str = "src/a.py", line: int = 1,
                   ref: str = "reports/analysis.json") -> dict:
    return {"rule_id": rule, "severity": severity, "evidence_ref": ref, "evidence_sha256": "e5" * 32, "path": path,
            "line": line}


def adapter_result(repo, head: str, paths=PATHS, *, rules=("R1",), unsupported=(), findings=(), body_over=None,
                   outcome: Outcome = Outcome.OK, blocking_unknown=(), candidate_head: str | None = "same",
                   source_tree_sha256: str | None = "same", with_report: bool = True) -> AdapterResult:
    tree = source_tree_digest(str(repo), sorted(paths), head).sha256
    checked = sorted(set(rules) - set(unsupported))
    coverage = "FULL" if not unsupported else ("PARTIAL" if checked else "NOT_COVERED")
    body = {
        "analyzer_id": "aeve", "analyzer_version": "1.0.0", "analyzer_sha256": "1f" * 32, "profile_id": "profile-1",
        "profile_sha256": "2e" * 32, "source_tree_sha256": tree, "analysis_scope": sorted(paths), "coverage": coverage,
        "covered_rules": checked, "unsupported_rules": sorted(unsupported),
        "rule_statuses": [{"rule_id": r, "status": "UNSUPPORTED" if r in unsupported else "SUPPORTED_AND_CHECKED"}
                          for r in sorted(rules)],
        "findings": [dict(f) for f in findings],
    }
    body.update(copy.deepcopy(body_over or {}))
    return AdapterResult(
        outcome=outcome, detail="", run=None, report=AnalysisReport(body=body) if with_report else None,
        source_tree_sha256=tree if source_tree_sha256 == "same" else source_tree_sha256,
        analyzer_sha256=body["analyzer_sha256"] if "analyzer_sha256" in body else None,
        profile_sha256=body.get("profile_sha256"), analyzer_version=body.get("analyzer_version"),
        candidate_head=head if candidate_head == "same" else candidate_head,
        blocking_unknown=tuple(blocking_unknown),
    )


def builder_kwargs(repo, head: str, paths=PATHS, **over) -> dict[str, Any]:
    kw: dict[str, Any] = dict(
        role_result=role_result(head, paths), role=ROLE, candidate_head=head, reviewed_paths=list(paths),
        required_paths=list(paths), snapshot_root=str(repo), adapter_result=adapter_result(repo, head, paths),
        manifest_sha256="e7" * 32, epoch=EPOCH, run_id="run-1", nonce="nonce-0123456789abcdef",
        receipt_id="r-static-1", task_id=TASK, slot="static", attempt=1, prev_receipt_sha256=None,
        runner_id="runner-1", role_sha256=ROLE_SHA, resolved_model="sonnet-5.5", invocation_id="inv-1",
        created_at="2026-11-10T00:00:00Z", covered_acceptance=["AC-2"],
    )
    kw.update(over)
    return kw


def build(repo, head: str, paths=PATHS, **over):
    return build_static_receipt(**builder_kwargs(repo, head, paths, **over))


# ------------------------------------------------------------------------------------ gate-level world
@dataclass
class World:
    repo: pathlib.Path
    head: str
    catalog: Any
    manifest: dict
    registry: dict
    tests: dict
    review: dict

    @property
    def manifest_sha(self) -> str:
        return mhash(self.manifest)


def load_real_catalog():
    return load_catalog(REPO_ROOT, expected_sha256=FROZEN_CATALOG_SHA256)


def v3_manifest(catalog, paths=PATHS) -> tuple[dict, dict]:
    m = manifest(scope=list(paths))
    registry_body = {"version": "registry-1", "entries": [{"principal": "reviewer-x", "key_id": "reviewer-key-1"}]}
    registry = {**registry_body, "signature": signing.sign(registry_body, OPERATOR_KEY, signing.REVIEWER_REGISTRY_LABEL)}
    parser_id, parser_version, parser_sha = next(iter(contracts.TRUSTED_PARSER_CATALOG))
    m.update({
        "contract_version": 3,
        "reviewer_registry": {"version": "registry-1", "sha256": hashlib.sha256(canonical_bytes(registry_body)).hexdigest()},
        "mandatory_commands": [{"slot": "tests", "argv": ["pytest", "-q"], "parser_id": parser_id,
                                "parser_version": parser_version, "parser_sha256": parser_sha}],
        "change_scope": {"allowed_paths": list(paths)},
        "required_rule_ids": list(catalog.required_rule_ids),
        "static_acceptance_ids": ["AC-2"],
    })
    contracts.validate_task_manifest(m)  # a malformed fixture must fail here, not inside the gate
    return m, registry


def _testrun_receipt(m: dict, head: str) -> dict:
    msha = mhash(m)
    item = unsigned_receipt("TestRun", contract_version=3, task_id=TASK, manifest_sha256=msha, slot="tests",
                            candidate_head=head, epoch=EPOCH)
    parser_id, parser_version, parser_sha = next(iter(contracts.TRUSTED_PARSER_CATALOG))
    argv = ["pytest", "-q"]
    parser_results = [{"argv": argv, "parser_id": parser_id, "parser_version": parser_version, "parser_sha256": parser_sha,
                       "parser_result": {"executed_test_ids": ["t1", "t2"], "skipped_test_ids": [], "xfail_test_ids": []}}]
    request = {"request_id": "u2-request", "task_id": TASK, "slot": "tests", "attempt": 1, "epoch": EPOCH,
               "manifest_sha256": msha, "candidate_head": head, "commands": [{"argv": argv, "exit_code": 0}],
               "parser_results": parser_results, "artifact_digests": {}}
    request_signature = signing.sign(request, SIGNER_KEY, signing.SIGNING_REQUEST_LABEL)
    diff_body = {"manifest_sha256": msha, "candidate_head": head, "diff_sha256": "d6" * 32, "changed_paths": [],
                 "verdict": "PASS", "reason": "PASS"}
    item.update({
        "parser_results": parser_results,
        "diff_gate": {**diff_body, "signature": signing.sign(diff_body, SIGNER_KEY, signing.DIFF_GATE_LABEL)},
        "runner_attestation": {"request": request, "signature": request_signature},
        "signature": request_signature,
    })
    return item


def _review_receipt(m: dict, head: str) -> dict:
    item = unsigned_receipt("IndependentReview", contract_version=3, task_id=TASK, manifest_sha256=mhash(m),
                            slot="review", candidate_head=head, epoch=EPOCH)
    item["reviewer_key_id"] = "reviewer-key-1"
    item["signature"] = signing.sign(item, REVIEWER_KEY, signing.REVIEWER_LABEL)
    return item


def make_world(parent: pathlib.Path) -> World:
    repo, head = make_repo(parent)
    catalog = load_real_catalog()
    m, registry = v3_manifest(catalog)
    return World(repo, head, catalog, m, registry, _testrun_receipt(m, head), _review_receipt(m, head))


def static_run(world: World, *, role_res: dict | None = None, rules=None, unsupported=(), findings=(), edit=None,
               receipt_edit=None, nonce: str = "nonce-0123456789abcdef", receipt_id: str = "r-static-1", **builder_over):
    """Build (signed_receipt, unsigned_payload) with the real receipt builder.

    ``edit(d)`` is applied to BOTH the receipt body and the payload (a hand-forged bridge fact the analyzer authority
    signs); ``receipt_edit(body)`` only to the receipt body.
    """
    rules = list(world.catalog.required_rule_ids) if rules is None else list(rules)
    kw = builder_kwargs(
        world.repo, world.head, PATHS,
        role_result=role_res if role_res is not None else role_result(world.head),
        adapter_result=adapter_result(world.repo, world.head, PATHS, rules=rules, unsupported=unsupported,
                                      findings=findings),
        manifest_sha256=world.manifest_sha, role_sha256=world.manifest["role_sha256"], nonce=nonce,
        receipt_id=receipt_id,
    )
    kw.update(builder_over)
    body, payload = build_static_receipt(**kw)
    if edit:
        edit(body)
        edit(payload)
    if receipt_edit:
        receipt_edit(body)
    return {**body, "signature": signing.sign(body, ANALYZER_KEY, RECEIPT_V3_LABEL)}, payload


class Nonces:
    """Atomic one-shot nonce store for analyzer_trust['consume_nonce']."""

    def __init__(self) -> None:
        self.used: list[str] = []

    def __call__(self, nonce: str) -> bool:
        if nonce in self.used:
            return False
        self.used.append(nonce)
        return True


def pins_of(payload: dict) -> dict:
    out = {k: payload[k] for k in ("analyzer_id", "analyzer_version", "analyzer_sha256", "profile_id", "profile_sha256")}
    out["role_table_sha256"] = payload["role_table_sha256"]
    out["aeve_head"] = payload["aeve_head"]
    return out


def expected_of(payload: dict) -> dict:
    return {k: copy.deepcopy(payload[k]) for k in gate._V3_RUN_FIELDS}


def make_trust(world: World, receipt: dict, payload: dict, *, nonces: Nonces | None = None, pinned_edit=None,
               evidence: dict | None = None, expected: dict | None = None) -> dict:
    evidence = evidence if evidence is not None else analyzer_authority.sign_analyzer_evidence(
        payload, ANALYZER_KEY, OTHER_ROLE_KEYS)
    pinned = pins_of(payload)
    if pinned_edit is not None:
        pinned = pinned_edit(pinned)
    return {
        "analyzer_key": ANALYZER_KEY, "other_role_keys": dict(OTHER_ROLE_KEYS),
        "consume_nonce": nonces if nonces is not None else Nonces(), "catalog": world.catalog,
        "runs": {receipt["receipt_id"]: {"evidence": evidence,
                                         "expected": expected if expected is not None else expected_of(payload)}},
        "pinned": pinned,
    }


def evaluate(world: World, static_receipt: dict, trust: Any, *, waiver: dict | None = None, head: str | None = None,
             receipts: list | None = None) -> dict:
    return gate.evaluate(
        world.manifest, receipts if receipts is not None else [world.tests, static_receipt, world.review],
        head or world.head, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY, waiver=waiver,
        reviewer_registry=world.registry, reviewer_keys={"reviewer-key-1": REVIEWER_KEY}, signer_key=SIGNER_KEY,
        event_key=EVENT_KEY, analyzer_trust=trust,
    )


def signed_waiver(world: World, *, slots=("static",), results=("INCONCLUSIVE",), acceptance=()) -> dict:
    body = {"record_id": "W-U2", "operator": "operator-ivan", "task_id": TASK, "epoch": EPOCH, "head": world.head,
            "manifest_sha256": world.manifest_sha, "waived_slots": list(slots), "waived_acceptance": list(acceptance),
            "expires_epoch": EPOCH, "waived_results": list(results)}
    return {**body, "signature": signing.sign(body, OPERATOR_KEY, signing.WAIVER_LABEL)}


def reasons_text(decision: dict) -> str:
    return " | ".join(decision["reasons"])


def refusal_code(call, *args, **kw) -> str:
    """Run a builder call that must raise ContractError; return the RB_* code at the start of its message."""
    try:
        call(*args, **kw)
    except contracts.ContractError as exc:
        return str(exc).split(":", 1)[0]
    raise AssertionError("the call did not raise ContractError")


replace = dataclasses.replace
