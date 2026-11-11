"""U5-6 support: an in-process synthetic story harness. This module is NOT a test file.

It wires the REAL pieces of U1-U5 together without AEVE, a model, a network or git:

  role_table -> worker_gate -> rule_coverage -> review_loop (router.normalize inside) -> gate -> final_package

Only the outer world is simulated: `FakeAeve` returns canned AEVE-shaped JSON (checked by the real
`adapter.check_response`), the worker isolation uses a fake `lstat` (as tests/vst/test_u5_worker_gate.py), the
store is a real SQLite file in a temp directory, and signatures are real HMACs (`tools/vst/signing.py`).

Model invocation counting: every model-capable seam of the harness calls `ModelGuard.invoke`, which counts the
call and raises AssertionError('model invoked'). The repository has no model-fallback switch (grep of tools/uc and
tools/vst found none); the harness expresses "model fallback" as `StorySpec.model_fallback`, which only the
harness seams read (FakeAeve fallback, model-residual resolver, model-writing fixer). Default False.

Nothing here knows the expected result of a scenario: expected values are written by hand in the test file.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping

from tools.uc import role_table as uc_role_table
from tools.uc import router
from tools.vst import contracts as vst_contracts
from tools.vst import final_package as fp
from tools.vst import gate
from tools.vst import review_loop as rl
from tools.vst import rule_coverage as rc
from tools.vst import signing
from tools.vst import worker_gate as wg
from tools.vst.analyzer_adapter import AnalysisReport
from tools.vst.pipeline_migration import migrate_pipeline
from tools.vst.pipeline_state import PipelineState

from .e1e4_helpers import (
    EPOCH, HEAD, HEAD2, KEY, MANIFEST_SHA, OPERATOR_KEY, STORY, SUPERVISOR_KEY, WRONG_KEY, FakeClock,
    happy_receipts, manifest, new_env, receipt,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = "1" * 40
NOW = "2026-11-11T10:00:00Z"
PATHS = ("src/app.py",)
SNAP = "a1" * 32
EVIDENCE = "c" * 64
EVID_T1 = "d" * 64
EVID_T2 = "e" * 64
T1 = "tests/vst/test_story.py::test_alpha"
T2 = "tests/vst/test_story.py::test_beta"
REPORT_LABEL = b"vst-u5-e2e-report-v1\0"

CLEAN_ROLES = ("repo-recon", "git-worktree-ops")     # class LOCAL, COVERED_PARTIAL in catalog/role_table.json
MODEL_ROLE = ("python-reviewer",)                    # class LOCAL_PLUS_MODEL, COVERED_PARTIAL
TABLE_ROLE_NAMES = ("git-worktree-ops", "python-reviewer", "repo-recon")
CATALOG_REQUIRED = ("PY-BARE-EXCEPT", "PY-IDENTITY-LITERAL-COMPARISON")  # first two rows of docs/qa/aeve_required_rules.json
UNKNOWN_RULE = "PY-NOT-IN-CATALOG"
SECRET_TEXT = "api" + "_key=" + "abcd1234wxyz"        # built at runtime; matches tools/uc/secret_patterns


# ----------------------------------------------------------------------------- model guard
class ModelGuard:
    """The single place every model-capable seam must go through. It never succeeds."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    @property
    def count(self) -> int:
        return len(self.calls)

    def invoke(self, seam: str = "unspecified", *args: Any, **kwargs: Any) -> Any:
        self.calls.append(seam)
        raise AssertionError("model invoked")

    def fixer(self, context: Any) -> Any:
        """A model-writing fixer (OD-8: the model writes code only where no patch proposal exists)."""
        return self.invoke("fixer")


def resolve_model_residual(report: Mapping[str, Any], guard: ModelGuard, *, enabled: bool) -> list[str]:
    """The model half of a LOCAL_PLUS_MODEL role. Disabled: nothing runs and the roles stay open."""
    open_roles = [role["role"] for role in report["roles"] if role["model_residual"]]
    if open_roles and enabled:
        guard.invoke("model-residual")
    return open_roles


class FakeAeve:
    """Canned AEVE `review` answer in the shape `adapter.check_response` requires; no process, no model."""

    def __init__(self, guard: ModelGuard, *, model_fallback: bool, executor_status: Mapping[str, str],
                 raw_findings: tuple[tuple[str, str], ...]) -> None:
        self.guard = guard
        self.model_fallback = model_fallback
        self.executor_status = dict(executor_status)
        self.raw_findings = raw_findings
        self.calls = 0

    def run(self, aeve_request: Mapping[str, Any]) -> tuple[dict, int]:
        if self.model_fallback:
            self.guard.invoke("aeve-model-fallback")
        self.calls += 1
        executors = list(aeve_request["executor_ids"])
        results = [{"executor_id": e, "status": self.executor_status.get(e, "COMPLETE")} for e in executors]
        findings = [
            {"executor_id": executor, "rule_id": rule, "severity": "MAJOR", "file": PATHS[0], "line": 3, "column": 1,
             "evidence": {"line_sha256": EVIDENCE}}
            for executor, rule in self.raw_findings]
        if findings:
            status = "FINDINGS"
        elif any(r["status"] != "COMPLETE" for r in results):
            status = "PARTIAL"
        else:
            status = "COMPLETE"
        response = {
            "status": status, "request_id": aeve_request["request_id"], "head": aeve_request["base_revision"],
            "snapshot_sha256": SNAP, "iteration_id": f"it-{self.calls}", "executor_ids": executors,
            "results": results, "findings": findings, "uncovered": [], "llm_calls": self.guard.count,
            "executed_project_code": False, "source_modified": False, "dirty": False,
        }
        return response, 0 if status == "COMPLETE" else 3


# ----------------------------------------------------------------------------- role table fixtures
def real_table() -> tuple[dict, str]:
    return router.load_table_with_digest(REPO_ROOT / "catalog" / "role_table.json")


def counts_of(entries: list[dict]) -> dict:
    by_class: dict[str, int] = {}
    by_state: dict[str, int] = {}
    for entry in entries:
        by_class[entry["class"]] = by_class.get(entry["class"], 0) + 1
        by_state[entry["coverage_state"]] = by_state.get(entry["coverage_state"], 0) + 1
    return {"total": len(entries), "by_class": dict(sorted(by_class.items())),
            "by_coverage_state": dict(sorted(by_state.items()))}


def mini_table(*, matrix_executor_drift: bool = False, probe_head: str | None = None,
               probe_matrix_digest: str | None = None) -> dict:
    """A table of three REAL entries (copied from catalog/role_table.json) plus a matching inventory, matrix, probe."""
    full, _ = real_table()
    entries = [copy.deepcopy(next(e for e in full["entries"] if e["name"] == name)) for name in TABLE_ROLE_NAMES]
    entries.sort(key=lambda e: (e["kind"], e["name"]))
    pin = full["aeve_pin"]
    table = {"version": 1, "aeve_pin": dict(pin), "counts": counts_of(entries), "entries": entries}
    rows = [{"id": e["canonical_role"], "deterministic_executors": list(e["executors"])} for e in entries]
    if matrix_executor_drift:
        for row in rows:
            if row["id"] == "python-reviewer":
                row["deterministic_executors"].append("g2.extra-rule")
    return {
        "table": table,
        "inventory": {"entries": [{"kind": e["kind"], "name": e["name"]} for e in entries]},
        "matrix": {"rows": rows},
        "probe": {"aeve_head": probe_head or pin["head"],
                  "matrix": {"digest_sha256": probe_matrix_digest or pin["matrix_digest_sha256"]}},
        "sha256": hashlib.sha256(json.dumps(table, sort_keys=True).encode("utf-8")).hexdigest(),
    }


def executors_of(table: Mapping[str, Any], roles: tuple[str, ...]) -> list[str]:
    found = set()
    for role in roles:
        found.update(next(e for e in table["entries"] if e["name"] == role)["executors"])
    return sorted(found)


# ----------------------------------------------------------------------------- worker and package fixtures
def diff_for(*paths: str) -> bytes:
    return "".join(
        f"diff --git a/{p} b/{p}\nindex 1111111..2222222 100644\n--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-a\n+b\n"
        for p in paths).encode("utf-8")


def make_isolation(tmp_path: Path) -> wg.IsolationContext:
    worktree = str(tmp_path / "worktree")
    main = str(tmp_path / "main")
    roots = {os.path.normcase(worktree), os.path.normcase(main)}

    def lstat(path: str) -> Any:
        info = SimpleNamespace(st_mode=(stat.S_IFDIR if os.path.normcase(path) in roots else stat.S_IFREG) | 0o755)
        info.st_file_attributes = 0
        return info

    return wg.IsolationContext(worktree, main, False, BASE, HEAD, lstat=lstat)


def static_report(*, with_unknown_rule: bool) -> AnalysisReport:
    rules = list(CATALOG_REQUIRED) + ([UNKNOWN_RULE] if with_unknown_rule else [])
    return AnalysisReport(body={
        "analyzer_id": "aeve", "analyzer_version": "1", "analyzer_sha256": "1" * 64, "profile_id": "g2.python-rules",
        "profile_sha256": "2" * 64, "source_tree_sha256": "3" * 64, "analysis_scope": list(PATHS),
        "coverage": "FULL", "covered_rules": sorted(rules), "unsupported_rules": [],
        "rule_statuses": [{"rule_id": r, "status": "SUPPORTED_AND_CHECKED"} for r in sorted(rules)],
        "findings": []})


def static_catalog(*, admit_unknown: bool) -> rc.RuleCatalog:
    required = tuple(sorted(list(CATALOG_REQUIRED) + ([UNKNOWN_RULE] if admit_unknown else [])))
    return rc.RuleCatalog(body={}, required_rule_ids=required, optional_rule_ids=(),
                          fixture_by_rule={}, sha256="0" * 64)


def lenient_coverage_judge(real_judge: Callable[..., Any]) -> Callable[..., Any]:
    """Negative control only: the real judge with its coverage checks removed by hand.

    Drops COVERAGE_PARTIAL, DECLARED_EXECUTOR_MISSING and EXIT_NOT_ZERO and treats every declared executor as
    covered. It is installed with monkeypatch inside one test and never touches production code.
    """
    drop = {rl.COVERAGE_PARTIAL, rl.DECLARED_EXECUTOR_MISSING, rl.EXIT_NOT_ZERO}

    def judge(*args: Any, **kwargs: Any) -> Any:
        judged = real_judge(*args, **kwargs)
        reasons = tuple(r for r in judged.reasons if r not in drop)
        verdict = judged.verdict
        if not reasons and not judged.findings:
            verdict = "CLEAN"
        covered = tuple(sorted(set(judged.covered) | set(kwargs["declared"])))
        return dataclasses.replace(judged, verdict=verdict, reasons=reasons, covered=covered, missing=())

    return judge


# ----------------------------------------------------------------------------- the story
@dataclass(frozen=True)
class StorySpec:
    """Knobs of one scenario. The defaults are the clean control story."""

    roles: tuple[str, ...] = CLEAN_ROLES
    cap: int = 1
    model_fallback: bool = False
    model_fixer: bool = False
    force_package: bool = False
    # role table drift
    matrix_executor_drift: bool = False
    probe_head: str | None = None
    probe_matrix_digest: str | None = None
    # AEVE answer
    executor_status: Mapping[str, str] = field(default_factory=dict)
    raw_findings: tuple[tuple[str, str], ...] = ()
    # report integrity
    forge_report: bool = False
    verify_report: Callable[[Any], Any] | None = None
    # static rule coverage
    unknown_rule: bool = False
    catalog_admits_unknown: bool = False
    # receipts and gate
    forge_receipt: bool = False
    gate_head: str = HEAD
    # tests evidence
    t2_status: str = "PASS"
    t2_head: str | None = HEAD
    allow_not_run: Mapping[str, str] = field(default_factory=dict)
    secret_reason: str | None = None


@dataclass
class Outcome:
    guard: ModelGuard
    config: Any
    stopped_at: str = ""
    final: str = ""
    notes: dict[str, str] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)
    reports: list[dict] = field(default_factory=list)
    loop_result: Any = None
    gate_decision: Any = None
    package_result: Any = None
    worker_verdict: Any = None

    def note(self, stage: str, text: str) -> None:
        if stage not in self.trace:
            self.trace.append(stage)
        self.notes[stage] = f"{self.notes[stage]} | {text}" if stage in self.notes else text

    def stop(self, stage: str, final: str) -> "Outcome":
        self.stopped_at, self.final = stage, final
        return self


def _blocked_envelope(request_id: str, reason: str, detail: str) -> dict:
    return {"schema_version": router.contracts.BLOCKED_SCHEMA, "request_id": request_id, "status": "BLOCKED",
            "reason": reason, "detail": str(detail)[:200]}


def run_story(tmp_path: Path, spec: StorySpec | None = None, *, guard: ModelGuard | None = None) -> Outcome:
    """Run one story through the real stages and stop at the first stage that does not pass."""
    spec = spec or StorySpec()
    guard = guard or ModelGuard()
    out = Outcome(guard=guard, config=SimpleNamespace(model_fallback=spec.model_fallback, fixer_is_model=spec.model_fixer))
    root = str(tmp_path)
    changed = list(PATHS)

    # stage 1: role table against the probed AEVE checkout (tools/uc/role_table.py)
    fixture = mini_table(matrix_executor_drift=spec.matrix_executor_drift, probe_head=spec.probe_head,
                         probe_matrix_digest=spec.probe_matrix_digest)
    table = fixture["table"]
    router.check_table(table)
    problems = uc_role_table.validate_role_table(table, fixture["inventory"], fixture["matrix"], fixture["probe"])
    out.note("role_table", "; ".join(problems) if problems else "table matches the probed AEVE checkout")
    if problems:
        return out.stop("role_table", "BLOCKED")

    # stage 2: worker output through the diff gate (tools/vst/worker_gate.py)
    diff = diff_for(*PATHS)
    worker = wg.gate_worker_change(
        manifest_sha256=MANIFEST_SHA, base_head=BASE, candidate_head=HEAD, changed_paths=changed,
        allowed_paths=changed, protected_paths=(), diff_bytes=diff, isolation=make_isolation(tmp_path))
    out.worker_verdict = worker
    out.note("worker_gate", f"{worker.verdict}: " + "; ".join(f"{c} {d}" for c, d in worker.reasons))
    if worker.verdict != wg.ACCEPTED:
        return out.stop("worker_gate", worker.verdict)

    # stage 3: static rule coverage against the required-rule catalog (tools/vst/rule_coverage.py)
    report = static_report(with_unknown_rule=spec.unknown_rule)
    try:
        coverage = rc.build_static_coverage(report, static_catalog(admit_unknown=spec.catalog_admits_unknown))
        out.note("rule_coverage", f"profile={report.body['profile_id']} coverage={coverage['fields']['coverage']} "
                                  f"clean={coverage['clean']}")
    except rc.CoverageError as exc:
        out.note("rule_coverage", f"profile={report.body['profile_id']} {exc}")
        return out.stop("rule_coverage", "BLOCKED")

    # stage 4: review loop; every submit is AEVE (fake) -> adapter.check_response -> router.normalize -> signature
    aeve = FakeAeve(guard, model_fallback=spec.model_fallback, executor_status=spec.executor_status,
                    raw_findings=spec.raw_findings)
    executor_ids = executors_of(table, spec.roles)
    signatures: dict[str, str] = {}
    sign_key = WRONG_KEY if spec.forge_report else KEY

    def submit(request: rl.ReviewRequest) -> dict:
        role_request = {"schema_version": "uc.role-request.v1", "request_id": request.request_id, "root": root,
                        "base_revision": request.head, "changed_paths": list(changed), "roles": list(spec.roles),
                        "purpose": "receipt"}
        if request.iteration_of:
            role_request["iteration_of"] = request.iteration_of
        doc = router.contracts.validate_request(role_request, [root])
        aeve_request = router.adapter.build_aeve_request(
            request_id=request.request_id, root=root, base_revision=request.head, changed_paths=changed,
            executor_ids=executor_ids, iteration_of=request.iteration_of)
        response, exit_code = aeve.run(aeve_request)
        try:
            response = router.adapter.check_response(response, aeve_request, exit_code)
            result = router.normalize(doc, table, response, None, role_table_sha256=fixture["sha256"],
                                      aeve_head=table["aeve_pin"]["head"])
            router.contracts.validate_result(result)
        except router.adapter.AdapterBlocked as exc:
            out.note("aeve_adapter", f"{exc.reason}: {exc.detail}")
            return _blocked_envelope(request.request_id, exc.reason, exc.detail)
        still_open = resolve_model_residual(result, guard, enabled=spec.model_fallback)
        out.reports.append(result)
        out.note("router_normalize", " ; ".join(
            f"{r['role']} {r['status']} executors={[e['id'] for e in r['executors']]} "
            f"rules={[f['rule_id'] for f in r['findings']]}" for r in result["roles"])
            + f" model_part_disabled_for={still_open}")
        signatures[result["iteration_id"]] = signing.sign(result, sign_key, REPORT_LABEL)
        return result

    def verify_signature(doc: dict) -> bool:
        return signing.verify({**doc, "signature": signatures.get(doc["iteration_id"], "")}, KEY, REPORT_LABEL)

    path = str(tmp_path / "story.db")
    store, _, epoch = new_env(path)
    try:
        migrate_pipeline(path)
        state = PipelineState(store)
        state.start_worker_attempt(STORY, epoch=epoch, step_id="s-start-1", base_head=BASE)
        loop = rl.run_review_loop(
            state, STORY, epoch=epoch, attempt_no=1, initial_head=HEAD, declared_coverage=list(executor_ids),
            iteration_cap=spec.cap, changed_paths_sha256=router.contracts.changed_paths_sha256(changed),
            submit=submit, verify_report=spec.verify_report or verify_signature, clock=FakeClock(),
            fixer=guard.fixer if spec.model_fixer else None, manifest_sha256=MANIFEST_SHA,
            allowed_paths=changed, protected_paths=())
    finally:
        store.close()
    out.loop_result = loop
    out.note("review_loop", f"{loop.verdict} " + " ".join(f"{c}:{d}" for c, d in loop.reasons) + " " + " ".join(
        f"[{i.verdict} reasons={list(i.reasons)} coverage={list(i.coverage)} missing={list(i.missing_coverage)} "
        f"head={i.head}]" for i in loop.iterations))
    if loop.verdict != rl.CLEAN and not spec.force_package:
        return out.stop("review_loop", loop.verdict)

    # stage 5: gate evaluation over signed receipts (tools/vst/gate.py)
    receipts = happy_receipts()
    if spec.forge_receipt:
        receipts[0] = receipt("TestRun", key=WRONG_KEY)
    decision = gate.evaluate(manifest(), receipts, spec.gate_head, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
                             operator_key=OPERATOR_KEY)
    out.gate_decision = decision
    out.note("gate", decision["verdict"] + " | " + " | ".join(decision["reasons"]))
    if decision["verdict"] != "APPROVE" and not spec.force_package:
        return out.stop("gate", decision["verdict"])

    # stage 6: test evidence and final package (tools/vst/final_package.py)
    t1 = {"test_id": T1, "status": "PASS", "evidence_sha256": EVID_T1, "head": HEAD}
    if spec.secret_reason is not None:
        t1["reason"] = spec.secret_reason
    ran = spec.t2_status in ("PASS", "FAIL")
    t2 = {"test_id": T2, "status": spec.t2_status, "evidence_sha256": EVID_T2 if ran else None,
          "head": spec.t2_head if ran else None}
    package = fp.build_final_package(
        story_id=STORY, base_head=BASE, head=HEAD, diff_bytes=diff, diff_sha256=hashlib.sha256(diff).hexdigest(),
        changed_paths=changed, test_evidence=[t1, t2], required_test_ids=[T1, T2], review_results=loop.to_dict(),
        receipts=[{"receipt_id": r["receipt_id"], "head": r["candidate_head"],
                   "receipt_sha256": vst_contracts.receipt_sha256(r), "receipt_type": r["receipt_type"],
                   "result": r["result"]} for r in receipts],
        isolation_proof=worker.isolation_proof, patch_origin_share=None, now=NOW,
        allow_not_run=dict(spec.allow_not_run) or None,
        declared_limits=["synthetic story: no AEVE, no model, no network, no git"])
    out.package_result = package
    out.note("final_package", package.verdict + (": " + "; ".join(f"{c} {d}" for c, d in package.reasons)
                                                  if package.reasons else ""))
    return out.stop("final_package", package.verdict)
