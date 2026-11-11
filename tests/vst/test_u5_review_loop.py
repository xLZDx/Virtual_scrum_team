"""U5-4: review-loop driver.

Acceptance text: "The loop resubmits with iteration_of until local checks are clean for the declared
coverage or an iteration cap is reached; the cap result is BLOCKED, never a pass."

Every test drives the public API against a real SQLite store with the pipeline schema. Raw sqlite3
connections only OBSERVE state. Nothing here starts AEVE, a model or a process: `submit`, `fixer`,
`gate`, `verify_report` and the clock are injected fakes. Reports are real `uc.role-result.v1`
documents (they pass tools/uc/contracts.validate_result). Expected values are hand-computed from the
data written in this file and from the rules in docs/sdlc/u5/REVIEW_LOOP.md; the request id and the
finding-set digest are restated with an independent formula. Time is a FakeClock; nothing sleeps.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import math
import os
import pathlib
import sqlite3
import stat
from types import SimpleNamespace

import pytest

from tools.vst import review_loop as rl
from tools.vst import worker_gate as wg
from tools.vst.pipeline_migration import migrate_pipeline
from tools.vst.pipeline_state import PipelineState
from tools.vst.review_loop import Candidate, IterationSummary, ReviewLoopResult
from tools.vst.worker_gate import WorkerGateVerdict

from .e1e4_helpers import OWNER_TTL, STORY, FakeClock, new_env


def h(n: int) -> str:
    return f"{n:040x}"


BASE = h(1)          # base head of the worker attempt
CAND = h(2)          # first candidate head that is reviewed
MANIFEST = "9" * 64
SNAP = "a1" * 32
EXEC = "g2.python-rules"
EXTRA = "g9.extra-rule"
EVIDENCE = "c" * 64
PATHS = "e" * 64     # changed_paths_sha256 every report must carry


class Crash(BaseException):
    """Stands for a process death: not an Exception, so nothing may swallow it."""


# --------------------------------------------------------------------- database observers
def rows(path, sql, args=()):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def count(path, table):
    return rows(path, f"SELECT COUNT(*) FROM {table}")[0][0]


def review_rows(path):
    return [(r["iteration_index"], r["iteration_of"], r["findings_count"], r["verdict"], r["step_id"])
            for r in rows(path, "SELECT * FROM pl_review_iterations ORDER BY iteration_index")]


# --------------------------------------------------------------------- report builders
def finding(line, rule="py-bare-except"):
    return {"rule_id": rule, "severity": "MAJOR", "path": "src/a.py", "line": line, "column": 1,
            "evidence_hash": EVIDENCE}


def role_entry(name="python-reviewer", klass="LOCAL", status="CLEAN", executors=((EXEC, "COMPLETE"),),
               findings=(), uncovered=(), residual=()):
    return {
        "role": name, "canonical_role": name, "class": klass, "status": status,
        "executors": [{"id": i, "status": s, "snapshot_hash": SNAP} for i, s in executors],
        "findings": [dict(f) for f in findings], "uncovered": list(uncovered), "model_residual": list(residual),
    }


def make_report(request, iteration_id, roles=None, *, head=None, request_id=None, purpose="receipt", paths=None):
    roles = roles if roles is not None else [role_entry()]
    all_clean = all(r["status"] == "CLEAN" for r in roles)
    return {
        "schema_version": "uc.role-result.v1", "request_id": request_id or request.request_id,
        "base_revision": head or request.head, "snapshot_hash": SNAP, "iteration_id": iteration_id,
        "exit_code": 0 if all_clean else 3, "roles": roles, "role_table_sha256": "c" * 64,
        "aeve_head": "d" * 40, "purpose": purpose, "changed_paths_sha256": paths or PATHS,
    }


def clean_report(request, n=None):
    return make_report(request, f"it-{n or request.local_index}")


def findings_report(request, lines=None, n=None):
    lines = lines if lines is not None else [request.local_index + 2]
    return make_report(request, f"it-{n or request.local_index}",
                       [role_entry(status="FINDINGS", findings=[finding(x) for x in lines])])


# --------------------------------------------------------------------- injected fakes
class Submit:
    """submit callable: `plan(request)` returns the report; every request is kept."""

    def __init__(self, plan):
        self.plan = plan
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.plan(request)


class Fixer:
    def __init__(self, head=None, fail=None):
        self.contexts = []
        self.fixed_head = head
        self.fail = fail

    def __call__(self, context):
        self.contexts.append(context)
        if self.fail is not None:
            raise self.fail
        return Candidate(head=self.fixed_head or h(len(self.contexts) + 2), changed_paths=("src/a.py",),
                         diff_bytes=b"diff", isolation=None)


def honest_proof():
    props = []
    for name in wg.REQUIRED_PROPERTIES:
        status = "CALLER_ASSERTED" if name in wg.CALLER_ONLY_PROPERTIES else "VERIFIED"
        props.append({"property": name, "status": status, "detail": "d"})
    for name in wg.NOT_VERIFIED_PROPERTIES:
        props.append({"property": name, "status": "NOT_VERIFIED", "detail": "d"})
    return {"schema": "vst-worker-isolation-proof-v1", "isolation_mode": "windows-local-no-wsl", "properties": props}


class Gate:
    def __init__(self, verdict="ACCEPTED"):
        self.verdict = verdict
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.verdict == "ACCEPTED":
            return WorkerGateVerdict("ACCEPTED", (("DIFFGATE_PASS", "all checks passed"),), {"paths": ["src/a.py"]},
                                     honest_proof())
        return WorkerGateVerdict(self.verdict, (("OUT_OF_SCOPE_PATH", "'x'"),), None, None)


def always_true(doc):
    return True


@pytest.fixture
def env(tmp_path):
    path = str(tmp_path / "loop.db")
    store, clock, epoch = new_env(path)
    migrate_pipeline(path)
    ps = PipelineState(store)
    ps.start_worker_attempt(STORY, epoch=epoch, step_id="s-start-1", base_head=BASE)
    yield ps, store, clock, path, epoch
    store.close()


def run(env, submit, *, cap=3, fixer=None, gate=None, verify=always_true, declared=(EXEC,), clock=None,
        real_gate=False, **over):
    ps, _, _, _, epoch = env
    args = dict(
        state=ps, story_id=STORY, epoch=epoch, attempt_no=1, initial_head=CAND, declared_coverage=list(declared),
        iteration_cap=cap, changed_paths_sha256=PATHS, submit=submit, verify_report=verify, clock=clock or FakeClock(), fixer=fixer,
        manifest_sha256=MANIFEST, allowed_paths=["src/a.py"], protected_paths=[],
    )
    if not real_gate:
        args["gate"] = gate or Gate()
    args.update(over)
    state = args.pop("state")
    story = args.pop("story_id")
    return rl.run_review_loop(state, story, **args)


def codes(result):
    return result.reason_codes


# --------------------------------------------------------------------- CLEAN paths
def test_clean_on_the_first_iteration(env):
    ps, _, _, path, epoch = env
    submit = Submit(clean_report)
    result = run(env, submit, cap=3)
    assert result.verdict == "CLEAN" and result.clean and result.reasons == ()
    assert result.iteration_count == 1 and (result.submit_calls, result.fixer_calls) == (1, 0)
    expected_request_id = "rl-" + hashlib.sha256(b"story-1\x001").hexdigest()[:40]
    request = submit.requests[0]
    assert request.request_id == expected_request_id == rl.request_id_for(STORY, 1)
    assert (request.iteration_of, request.head, request.local_index, request.iteration_index) == (None, CAND, 1, 1)
    assert request.declared_coverage == (EXEC,)
    summary = result.iterations[0]
    assert (summary.verdict, summary.findings_count, summary.reasons, summary.coverage) == ("CLEAN", 0, (), (EXEC,))
    assert (summary.iteration_id, summary.iteration_of, summary.head, summary.replayed) == ("it-1", None, CAND, False)
    assert review_rows(path) == [(1, None, 0, "CLEAN", "rl-a1-i1")]
    stored = ps.list_review_iterations(STORY)[0]
    assert stored["coverage_declared"] == [EXEC] and stored["attempt_no"] == 1


def test_clean_at_the_cap_is_still_clean(env):
    result = run(env, Submit(clean_report), cap=1)
    assert result.verdict == "CLEAN" and result.cap_effective == 1


def test_findings_then_clean_resubmits_with_the_exact_iteration_of_chain(env):
    ps, _, _, path, epoch = env

    def plan(request):
        if request.local_index < 3:
            return findings_report(request, lines=[3, 4] if request.local_index == 1 else [7])
        return clean_report(request)

    submit, fixer, gate = Submit(plan), Fixer(), Gate()
    result = run(env, submit, cap=5, fixer=fixer, gate=gate)
    assert result.verdict == "CLEAN" and result.iteration_count == 3
    assert [r.iteration_of for r in submit.requests] == [None, "it-1", "it-2"]
    assert [r.head for r in submit.requests] == [CAND, h(3), h(4)]
    assert [r.iteration_index for r in submit.requests] == [1, 2, 3]
    assert [s.iteration_id for s in result.iterations] == ["it-1", "it-2", "it-3"]
    assert [s.iteration_of for s in result.iterations] == [None, "it-1", "it-2"]
    assert [(s.verdict, s.findings_count) for s in result.iterations] == [("FINDINGS", 2), ("FINDINGS", 1), ("CLEAN", 0)]
    assert result.iterations[0].reasons == ("FINDINGS_OPEN", "EXIT_NOT_ZERO")
    assert (result.submit_calls, result.fixer_calls, result.final_head) == (3, 2, h(4))
    # the fixer got the trusted findings and the head they belong to
    first = fixer.contexts[0]
    assert (first.head, first.iteration_id, first.local_index) == (CAND, "it-1", 1)
    assert [f["line"] for f in first.findings] == [3, 4] and first.findings[0]["role"] == "python-reviewer"
    # the gate saw base head, candidate head and the declared inputs
    assert [(c["base_head"], c["candidate_head"]) for c in gate.calls] == [(CAND, h(3)), (h(3), h(4))]
    assert gate.calls[0]["manifest_sha256"] == MANIFEST and gate.calls[0]["allowed_paths"] == ["src/a.py"]
    assert gate.calls[0]["diff_bytes"] == b"diff" and gate.calls[0]["changed_paths"] == ("src/a.py",)
    # recorded rows: iteration_of is the previous story-level index
    assert review_rows(path) == [
        (1, None, 2, "FINDINGS", "rl-a1-i1"), (2, 1, 1, "FINDINGS", "rl-a1-i2"), (3, 2, 0, "CLEAN", "rl-a1-i3")]
    gates = ps.list_diff_gates(STORY)
    assert [(g["gate_id"], g["verdict"], g["step_id"]) for g in gates] == [
        ("rl-a1-g1", "ACCEPTED", "rl-a1-i1-gate"), ("rl-a1-g2", "ACCEPTED", "rl-a1-i2-gate")]
    assert [g["gate_id"] for g in result.gates] == ["rl-a1-g1", "rl-a1-g2"]


def test_a_second_attempt_continues_the_story_level_index(env):
    ps, _, _, path, epoch = env
    run(env, Submit(clean_report), cap=2)
    ps.finish_worker_attempt(STORY, epoch=epoch, step_id="f1", attempt_no=1, state="FAILED")
    ps.start_worker_attempt(STORY, epoch=epoch, step_id="s-start-2", base_head=CAND)
    submit = Submit(clean_report)
    result = run(env, submit, cap=2, attempt_no=2)
    assert result.verdict == "CLEAN"
    request = submit.requests[0]
    # first review of the new attempt: no AEVE iteration_of, story-level index 2, a different request id
    assert (request.iteration_of, request.local_index, request.iteration_index) == (None, 1, 2)
    assert request.request_id == "rl-" + hashlib.sha256(b"story-1\x002").hexdigest()[:40]
    assert review_rows(path)[-1] == (2, 1, 0, "CLEAN", "rl-a2-i2")


# --------------------------------------------------------------------- cap
def test_cap_reached_with_findings_is_blocked_and_calls_equal_the_cap(env):
    ps, _, _, path, epoch = env
    submit, fixer = Submit(findings_report), Fixer()
    result = run(env, submit, cap=3, fixer=fixer)
    assert result.verdict == "BLOCKED" and not result.clean
    assert codes(result) == ("ITERATION_CAP",)
    assert (len(submit.requests), result.submit_calls, result.iteration_count) == (3, 3, 3)
    assert (len(fixer.contexts), result.fixer_calls) == (2, 2)   # no fix after the last iteration
    assert [(s.verdict, s.findings_count) for s in result.iterations] == [("FINDINGS", 1)] * 3
    assert [r[3] for r in review_rows(path)] == ["FINDINGS"] * 3
    assert count(path, "pl_diff_gates") == 2
    assert result.cap_requested == 3 and result.cap_effective == 3 and result.cap_clamped is False


def test_cap_of_one_with_findings_blocks_without_calling_the_fixer(env):
    fixer = Fixer()
    result = run(env, Submit(findings_report), cap=1, fixer=fixer)
    assert codes(result) == ("ITERATION_CAP",) and result.submit_calls == 1 and fixer.contexts == []


@pytest.mark.parametrize("bad", [False, None, 1, "yes", "raise"])
def test_cap_reached_with_an_unverifiable_but_clean_looking_last_report_is_blocked(env, bad):
    path = env[3]

    def plan(request):
        return findings_report(request) if request.local_index == 1 else clean_report(request)

    def verify(doc):
        if doc["iteration_id"] == "it-1":
            return True
        if bad == "raise":
            raise RuntimeError("no key available")
        return bad          # only the exact value True counts

    result = run(env, Submit(plan), cap=2, fixer=Fixer(), verify=verify)
    assert result.verdict == "BLOCKED" and codes(result) == ("ITERATION_CAP",)
    last = result.iterations[-1]
    assert (last.verdict, last.reasons, last.findings_count) == ("BLOCKED", ("SIGNATURE_UNVERIFIED",), 0)
    assert [r[3] for r in review_rows(path)] == ["FINDINGS", "BLOCKED"]
    assert count(path, "pl_review_iterations") == 2 and result.submit_calls == 2


def test_an_unverifiable_report_repeated_without_a_fix_is_no_progress(env):
    submit = Submit(clean_report)
    result = run(env, submit, cap=6, verify=lambda doc: False)
    assert codes(result) == ("NO_PROGRESS",) and result.submit_calls == 2
    assert [s.verdict for s in result.iterations] == ["BLOCKED", "BLOCKED"]
    assert [r.head for r in submit.requests] == [CAND, CAND] and submit.requests[1].iteration_of == "it-1"


def test_caps_above_the_hard_maximum_are_clamped(env):
    path = env[3]
    assert rl.MAX_ITERATIONS == 10
    submit, fixer = Submit(findings_report), Fixer()
    result = run(env, submit, cap=11, fixer=fixer)
    assert codes(result) == ("ITERATION_CAP",)
    assert (result.submit_calls, result.iteration_count) == (10, 10)
    assert (result.cap_requested, result.cap_effective, result.cap_clamped) == (11, 10, True)
    assert count(path, "pl_review_iterations") == 10 and result.fixer_calls == 9


def test_a_huge_cap_is_clamped_and_a_cap_equal_to_the_maximum_is_not_marked_clamped(tmp_path):
    for requested, clamped in ((10 ** 9, True), (10, False)):
        path = str(tmp_path / f"c{requested}.db")
        store, clock, epoch = new_env(path)
        migrate_pipeline(path)
        ps = PipelineState(store)
        ps.start_worker_attempt(STORY, epoch=epoch, step_id="s-start-1", base_head=BASE)
        result = run((ps, store, clock, path, epoch), Submit(findings_report), cap=requested, fixer=Fixer())
        assert (result.submit_calls, result.cap_effective, result.cap_clamped) == (10, 10, clamped)
        assert codes(result) == ("ITERATION_CAP",)
        store.close()


@pytest.mark.parametrize("cap", [0, -1, True, False, "3", None, 2.0, 1.5, [3]])
def test_an_invalid_cap_is_refused_and_nothing_runs(env, cap):
    path = env[3]
    submit = Submit(clean_report)
    result = run(env, submit, cap=cap)
    assert result.verdict == "BLOCKED" and codes(result) == ("CAP_INVALID",)
    assert submit.requests == [] and result.submit_calls == 0 and result.iterations == ()
    assert result.cap_effective is None and result.cap_requested == (cap if type(cap) is int else None)
    assert count(path, "pl_review_iterations") == 0


# --------------------------------------------------------------------- coverage
PARTIAL_CASES = {
    "model residual open": (
        [role_entry(klass="LOCAL_PLUS_MODEL", status="PARTIAL", residual=["model-judgment"])],
        {"MODEL_RESIDUAL_OPEN", "COVERAGE_PARTIAL", "EXIT_NOT_ZERO"}),
    "unsupported role beside a clean one": (
        [role_entry(), role_entry(name="mystery-role", klass="UNKNOWN", status="NOT_COVERED", executors=(),
                                  uncovered=["unknown-role"])],
        {"COVERAGE_PARTIAL", "EXIT_NOT_ZERO"}),
    "partial executor": (
        [role_entry(status="PARTIAL", executors=((EXEC, "PARTIAL"),), uncovered=["aeve-partial"])],
        {"COVERAGE_PARTIAL", "DECLARED_EXECUTOR_MISSING", "EXIT_NOT_ZERO"}),
    "executor not run": (
        [role_entry(status="NOT_RUN", executors=((EXEC, "NOT_RUN"),))],
        {"COVERAGE_PARTIAL", "DECLARED_EXECUTOR_MISSING", "EXIT_NOT_ZERO"}),
    "executor partial in a second role": (
        [role_entry(), role_entry(name="second-role", status="PARTIAL", executors=((EXEC, "PARTIAL"),),
                                  uncovered=["x-gap"])],
        {"COVERAGE_PARTIAL", "DECLARED_EXECUTOR_MISSING", "EXIT_NOT_ZERO"}),
}


@pytest.mark.parametrize("label", sorted(PARTIAL_CASES))
def test_partial_or_unsupported_coverage_is_never_clean(env, label):
    path = env[3]
    roles, expected = PARTIAL_CASES[label]
    submit = Submit(lambda r: make_report(r, f"it-{r.local_index}", roles))
    result = run(env, submit, cap=5)
    assert result.verdict == "BLOCKED" and codes(result) == ("NO_PROGRESS",) and result.submit_calls == 2
    first = result.iterations[0]
    assert first.verdict == "PARTIAL" and first.findings_count == 0 and set(first.reasons) == expected
    assert [r[3] for r in review_rows(path)] == ["PARTIAL", "PARTIAL"]
    assert not any(s.verdict == "CLEAN" for s in result.iterations)


def test_a_missing_declared_executor_is_not_clean_and_is_named(env):
    submit = Submit(clean_report)
    result = run(env, submit, cap=5, declared=(EXEC, EXTRA))
    first = result.iterations[0]
    assert result.verdict == "BLOCKED" and codes(result) == ("NO_PROGRESS",)
    assert (first.verdict, first.reasons, first.missing_coverage, first.coverage) == (
        "PARTIAL", ("DECLARED_EXECUTOR_MISSING",), (EXTRA,), (EXEC,))


def test_reported_coverage_that_exceeds_the_declaration_is_clean(env):
    both = ((EXEC, "COMPLETE"), (EXTRA, "COMPLETE"))
    submit = Submit(lambda r: make_report(r, "it-1", [role_entry(executors=both)]))
    result = run(env, submit, cap=2, declared=(EXEC,))
    assert result.verdict == "CLEAN" and result.iterations[0].coverage == (EXEC, EXTRA)


# --------------------------------------------------------------------- stale and foreign reports
@pytest.mark.parametrize("label,override,reason", [
    ("old head", {"head": CAND}, "HEAD_MISMATCH"),
    ("repeated iteration id", {"iteration_id": "it-1"}, "REPORT_STALE"),
])
def test_a_stale_or_foreign_report_for_the_second_iteration_is_not_clean(env, label, override, reason):
    path = env[3]

    def plan(request):
        if request.local_index == 1:
            return findings_report(request)
        return make_report(request, override.get("iteration_id", "it-2"), head=override.get("head"))

    result = run(env, Submit(plan), cap=2, fixer=Fixer())
    assert result.verdict == "BLOCKED" and codes(result) == ("ITERATION_CAP",)
    last = result.iterations[1]
    assert (last.verdict, last.reasons) == ("BLOCKED", (reason,))
    assert [r[3] for r in review_rows(path)] == ["FINDINGS", "BLOCKED"]


@pytest.mark.parametrize("kwargs,reason", [
    ({"head": h(77)}, "HEAD_MISMATCH"),
    ({"request_id": "someone-elses-request"}, "REQUEST_MISMATCH"),
])
def test_a_report_for_another_head_or_request_is_never_clean_and_repeats_are_no_progress(env, kwargs, reason):
    submit = Submit(lambda r: make_report(r, f"x-{r.local_index}", **kwargs))
    result = run(env, submit, cap=8)
    assert result.verdict == "BLOCKED" and codes(result) == ("NO_PROGRESS",) and result.submit_calls == 2
    assert [s.reasons for s in result.iterations] == [(reason,), (reason,)]
    assert all(s.verdict == "BLOCKED" for s in result.iterations)


# --------------------------------------------------------------------- progress
def test_same_head_and_same_findings_twice_is_no_progress(env):
    path = env[3]
    fixer = Fixer()
    # unverifiable findings are not trusted: the fixer is not called and the same head is reviewed again
    submit = Submit(lambda r: findings_report(r, lines=[3]))
    result = run(env, submit, cap=6, fixer=fixer, verify=lambda doc: False)
    assert codes(result) == ("NO_PROGRESS",) and result.submit_calls == 2 and fixer.contexts == []
    first = result.iterations[0]
    assert first.verdict == "BLOCKED" and first.findings_count == 1
    assert first.reasons == ("SIGNATURE_UNVERIFIED", "FINDINGS_OPEN", "EXIT_NOT_ZERO")
    assert result.iterations[0].finding_set_sha256 == result.iterations[1].finding_set_sha256
    assert [(r[2], r[3]) for r in review_rows(path)] == [(1, "BLOCKED"), (1, "BLOCKED")]


def test_a_different_finding_set_at_the_same_head_is_progress(env):
    submit = Submit(lambda r: findings_report(r, lines=[r.local_index + 2]))
    result = run(env, submit, cap=3, fixer=Fixer(), verify=lambda doc: False)
    assert codes(result) == ("ITERATION_CAP",) and result.submit_calls == 3
    assert [s.head for s in result.iterations] == [CAND, CAND, CAND]


def test_a_fixer_that_returns_the_same_head_is_no_progress_and_the_gate_is_not_called(env):
    gate, fixer = Gate(), Fixer(head=CAND)
    result = run(env, Submit(findings_report), cap=5, fixer=fixer, gate=gate)
    assert codes(result) == ("NO_PROGRESS",) and gate.calls == [] and result.fixer_calls == 1
    assert result.submit_calls == 1


def test_the_same_findings_at_a_new_head_are_not_no_progress_and_end_at_the_cap(env):
    submit = Submit(lambda r: findings_report(r, lines=[3]))   # identical finding set every time
    result = run(env, submit, cap=3, fixer=Fixer())
    assert codes(result) == ("ITERATION_CAP",) and result.submit_calls == 3
    assert len({s.finding_set_sha256 for s in result.iterations}) == 1
    assert [s.head for s in result.iterations] == [CAND, h(3), h(4)]


def test_cap_and_no_progress_together_list_both_reasons_cap_first(env):
    result = run(env, Submit(clean_report), cap=2, verify=lambda doc: False)
    assert codes(result) == ("ITERATION_CAP", "NO_PROGRESS")


def test_findings_without_a_fixer_end_the_loop_blocked(env):
    result = run(env, Submit(findings_report), cap=5)
    assert codes(result) == ("NO_FIXER",) and result.submit_calls == 1 and result.verdict == "BLOCKED"


# --------------------------------------------------------------------- stop path and epoch
def test_a_stopped_story_is_blocked_and_nothing_is_submitted(env):
    ps, _, _, path, epoch = env
    ps.stop_story(STORY, epoch=epoch, step_id="stop-1", reason="operator stop")
    submit = Submit(clean_report)
    result = run(env, submit)
    assert result.verdict == "BLOCKED" and codes(result) == ("STOPPED",)
    assert submit.requests == [] and count(path, "pl_review_iterations") == 0


def test_a_stop_during_the_loop_ends_it_with_no_further_submit(env):
    ps, _, _, path, epoch = env
    submit, gate = Submit(findings_report), Gate()

    def stopping_fixer(context):
        ps.stop_story(STORY, epoch=epoch, step_id="stop-1", reason="operator stop")
        return Candidate(head=h(3), changed_paths=("src/a.py",), diff_bytes=b"diff", isolation=None)

    result = run(env, submit, cap=5, fixer=stopping_fixer, gate=gate)
    assert codes(result) == ("STOPPED",) and result.submit_calls == 1 and len(submit.requests) == 1
    assert count(path, "pl_diff_gates") == 0 and count(path, "pl_review_iterations") == 1


def test_a_stop_while_a_review_runs_is_never_a_pass(env):
    ps, _, _, path, epoch = env

    def plan(request):
        ps.stop_story(STORY, epoch=epoch, step_id="stop-1", reason="operator stop")
        return clean_report(request)        # a perfectly clean report arrives after the stop

    result = run(env, Submit(plan), cap=3)
    assert result.verdict == "BLOCKED" and codes(result) == ("STOPPED",) and not result.clean
    assert count(path, "pl_review_iterations") == 0


def test_a_stale_epoch_is_refused_before_anything_runs(env):
    path, epoch = env[3], env[4]
    submit = Submit(clean_report)
    result = run(env, submit, epoch=epoch + 1)
    assert codes(result) == ("EPOCH_STALE",) and submit.requests == [] and count(path, "pl_review_iterations") == 0


def bump_epoch(env):
    ps, store, clock, path, epoch = env
    clock.advance(OWNER_TTL + 1)
    assert store.acquire_epoch(STORY, "owner-b", OWNER_TTL) == epoch + 1


def test_an_epoch_that_changes_during_a_review_refuses_the_record(env):
    path = env[3]

    def plan(request):
        bump_epoch(env)
        return clean_report(request)

    submit = Submit(plan)
    result = run(env, submit)
    assert codes(result) == ("EPOCH_STALE",) and not result.clean
    assert count(path, "pl_review_iterations") == 0 and len(submit.requests) == 1


def test_an_epoch_that_changes_during_a_fix_stops_before_the_next_submit(env):
    path = env[3]
    submit = Submit(findings_report)

    def fixer(context):
        bump_epoch(env)
        return Candidate(head=h(3), changed_paths=("src/a.py",), diff_bytes=b"diff", isolation=None)

    result = run(env, submit, cap=4, fixer=fixer)
    assert codes(result) == ("EPOCH_STALE",) and len(submit.requests) == 1
    assert count(path, "pl_diff_gates") == 0


def test_unknown_story_and_unknown_attempt_are_blocked(env):
    submit = Submit(clean_report)
    assert codes(run(env, submit, story_id="no-such-story")) == ("STORE_ERROR",)
    assert codes(run(env, submit, attempt_no=7)) == ("STORE_ERROR",)
    assert submit.requests == []


# --------------------------------------------------------------------- failures never become CLEAN
def test_a_submit_that_raises_is_blocked_with_an_ascii_escaped_reason(env):
    path = env[3]

    def boom(request):
        raise RuntimeError("bad \u00e9 line\nsecond\x00 \U0001f600")

    result = run(env, boom)
    assert result.verdict == "BLOCKED" and codes(result) == ("SUBMIT_FAILED",)
    detail = result.reasons[0][1]
    assert all(32 <= ord(c) < 127 for c in detail) and len(detail) <= 300
    assert detail.startswith("RuntimeError: bad ") and "\\xe9" in detail and "\\x0a" in detail
    assert "\\x00" in detail and "\\U0001f600" in detail
    assert count(path, "pl_review_iterations") == 0 and result.iterations == ()


def test_a_very_long_failure_text_is_truncated(env):
    def boom(request):
        raise RuntimeError("x" * 5000)

    assert len(run(env, boom).reasons[0][1]) == 300


@pytest.mark.parametrize("label,payload,code", [
    ("none", None, "BAD_REPORT"),
    ("string", "clean", "BAD_REPORT"),
    ("empty object", {}, "BAD_REPORT"),
    ("blocked envelope", {"schema_version": "uc.blocked.v1", "request_id": "r", "status": "BLOCKED",
                          "reason": "AEVE_PIN_MISMATCH", "detail": "x"}, "SUBMIT_BLOCKED"),
])
def test_an_unusable_report_is_blocked_and_not_recorded(env, label, payload, code):
    path = env[3]
    submit = Submit(lambda r: payload)
    result = run(env, submit)
    assert result.verdict == "BLOCKED" and codes(result) == (code,) and len(submit.requests) == 1
    assert count(path, "pl_review_iterations") == 0
    if code == "SUBMIT_BLOCKED":
        assert "reason=AEVE_PIN_MISMATCH" in result.reasons[0][1]


def test_a_report_with_an_unknown_field_or_inconsistent_exit_code_is_bad(env):
    def with_extra(request):
        doc = clean_report(request)
        doc["extra"] = 1
        return doc

    def wrong_exit(request):
        doc = clean_report(request)
        doc["exit_code"] = 3          # claims open items although every role is CLEAN
        return doc

    assert codes(run(env, Submit(with_extra))) == ("BAD_REPORT",)
    assert codes(run(env, Submit(wrong_exit))) == ("BAD_REPORT",)


def test_a_process_death_is_not_swallowed(env):
    def die(request):
        raise Crash()

    with pytest.raises(Crash):
        run(env, die)


def _gate_down(**kwargs):
    raise RuntimeError("gate down")


def _text_fixer():
    return lambda ctx: "not a candidate"


def _bad_head_fixer():
    return lambda ctx: Candidate(head="XYZ", changed_paths=("a",), diff_bytes=b"d", isolation=None)


FAILURES = {   # label -> (fixer factory, gate or None, code); factories give every test a fresh fixer
    "fixer raises": (lambda: Fixer(fail=ValueError("no fix")), None, "FIXER_FAILED"),
    "fixer returns text": (_text_fixer, None, "FIXER_FAILED"),
    "fixer returns a bad head": (_bad_head_fixer, None, "FIXER_FAILED"),
    "gate raises": (Fixer, _gate_down, "GATE_FAILED"),
    "gate returns a dict": (Fixer, lambda **kw: {"verdict": "ACCEPTED"}, "GATE_FAILED"),
}


@pytest.mark.parametrize("label", sorted(FAILURES))
def test_fixer_and_gate_failures_end_the_loop_blocked(env, label):
    path = env[3]
    make_fixer, gate, code = FAILURES[label]
    result = run(env, Submit(findings_report), cap=5, fixer=make_fixer(), gate=gate or Gate())
    assert result.verdict == "BLOCKED" and codes(result) == (code,) and result.submit_calls == 1
    assert count(path, "pl_diff_gates") == 0 and result.final_head == CAND


@pytest.mark.parametrize("label", ["failed entry", "missing property"])
def test_an_accepted_gate_with_a_dishonest_proof_is_a_store_error_and_not_adopted(env, label):
    path = env[3]
    proof = honest_proof()
    if label == "failed entry":
        proof["properties"][0]["status"] = "FAILED"
    else:
        proof["properties"] = proof["properties"][1:]

    def gate(**kwargs):
        return WorkerGateVerdict("ACCEPTED", (("DIFFGATE_PASS", "all checks passed"),), {"paths": ["src/a.py"]}, proof)

    submit = Submit(findings_report)
    result = run(env, submit, cap=5, fixer=Fixer(), gate=gate)
    assert result.verdict == "BLOCKED" and codes(result) == ("STORE_ERROR",)
    assert result.final_head == CAND and result.submit_calls == 1 and len(submit.requests) == 1
    assert count(path, "pl_diff_gates") == 0


def make_isolation(tmp_path, pinned, head):
    worktree, main = str(tmp_path / "worktree"), str(tmp_path / "main")
    roots = {os.path.normcase(worktree), os.path.normcase(main)}

    def lstat(path):
        norm = os.path.normcase(path)
        info = SimpleNamespace(st_mode=(stat.S_IFDIR if norm in roots else stat.S_IFREG) | 0o755)
        info.st_file_attributes = 0
        return info

    return wg.IsolationContext(worktree, main, False, pinned, head, lstat=lstat)


def diff_for(path):
    return (f"diff --git a/{path} b/{path}\nindex 1111111..2222222 100644\n--- a/{path}\n+++ b/{path}\n"
            "@@ -1 +1 @@\n-a\n+b\n").encode("utf-8")


def test_the_real_worker_gate_accepts_a_valid_candidate_and_the_loop_goes_on(env, tmp_path):
    ps = env[0]

    def plan(request):
        return findings_report(request) if request.local_index == 1 else clean_report(request)

    def fixer(context):
        return Candidate(head=h(3), changed_paths=("src/a.py",), diff_bytes=diff_for("src/a.py"),
                         isolation=make_isolation(tmp_path, context.head, h(3)))

    submit = Submit(plan)
    result = run(env, submit, cap=3, fixer=fixer, real_gate=True)
    assert result.verdict == "CLEAN" and len(submit.requests) == 2 and submit.requests[1].head == h(3)
    stored = ps.list_diff_gates(STORY)
    assert [(g["gate_id"], g["verdict"]) for g in stored] == [("rl-a1-g1", "ACCEPTED")]
    assert stored[0]["proof_statuses"]["base_commit_pinned"] == "CALLER_ASSERTED"
    assert stored[0]["proof_statuses"]["os_sandbox"] == "NOT_VERIFIED"
    assert result.gates[0]["verdict"] == "ACCEPTED" and result.gates[0]["replayed"] is False


@pytest.mark.parametrize("verdict,code", [("REFUSED", "GATE_REFUSED"), ("BLOCKED", "GATE_BLOCKED")])
def test_a_candidate_the_gate_does_not_accept_ends_the_loop_and_is_recorded(env, verdict, code):
    ps, _, _, path, _ = env
    submit = Submit(findings_report)
    result = run(env, submit, cap=5, fixer=Fixer(), gate=Gate(verdict))
    assert codes(result) == (code,) and len(submit.requests) == 1
    assert result.reasons[0][1] == "OUT_OF_SCOPE_PATH"
    stored = ps.list_diff_gates(STORY)
    assert [(g["gate_id"], g["verdict"]) for g in stored] == [("rl-a1-g1", verdict)]
    assert result.final_head == CAND       # the refused candidate is never adopted


def test_the_default_gate_is_the_u5_1_worker_gate_and_blocks_a_candidate_without_a_diff(env):
    assert inspect.signature(rl.run_review_loop).parameters["gate"].default is wg.gate_worker_change
    ps = env[0]
    fixer = lambda ctx: Candidate(head=h(3), changed_paths=("src/a.py",), diff_bytes=b"", isolation=None)
    result = run(env, Submit(findings_report), cap=4, fixer=fixer, real_gate=True)
    assert result.verdict == "BLOCKED" and codes(result) == ("GATE_BLOCKED",)
    assert ps.list_diff_gates(STORY)[0]["verdict"] == "BLOCKED"


def test_a_failing_callback_ends_the_loop_blocked(env):
    def callback(summary):
        raise OSError("disk full")

    result = run(env, Submit(clean_report), on_iteration=callback)
    assert codes(result) == ("CALLBACK_FAILED",) and not result.clean


# --------------------------------------------------------------------- clock and deadline
def test_the_total_deadline_stops_the_loop_before_the_next_submit(env):
    clock = FakeClock(1000.0)

    def plan(request):
        clock.advance(100)
        return findings_report(request)

    submit = Submit(plan)
    result = run(env, submit, cap=5, fixer=Fixer(), clock=clock, max_total_seconds=150)
    assert codes(result) == ("DEADLINE",) and result.submit_calls == 2
    assert [(s.started_at, s.finished_at) for s in result.iterations] == [(1000.0, 1100.0), (1100.0, 1200.0)]


@pytest.mark.parametrize("label", ["raises", "nan", "string", "backwards"])
def test_a_broken_clock_is_blocked(env, label):
    ticks = iter([1000.0, 999.0, 998.0])

    def clock():
        if label == "raises":
            raise RuntimeError("no clock")
        if label == "nan":
            return math.nan
        if label == "string":
            return "now"
        return next(ticks)

    submit = Submit(clean_report)
    result = run(env, submit, clock=clock)
    assert result.verdict == "BLOCKED" and codes(result) == ("CLOCK_FAILED",) and submit.requests == []


# --------------------------------------------------------------------- bad input
@pytest.mark.parametrize("label,over", [
    ("empty declared", {"declared": ()}),
    ("declared is a string", {"declared": EXEC}),
    ("declared not a token", {"declared": ("G2 Rules",)}),
    ("declared duplicate", {"declared": (EXEC, EXEC)}),
    ("bad head", {"initial_head": "xyz"}),
    ("upper case head", {"initial_head": "A" * 40}),
    ("epoch zero", {"epoch": 0}),
    ("attempt is a bool", {"attempt_no": True}),
    ("no verifier", {"verify": None}),
    ("submit not callable", {"submit": "x"}),
    ("negative deadline", {"max_total_seconds": -1}),
    ("resume is a string", {"resume": "x"}),
    ("fixer not callable", {"fixer": 5}),
    ("state is not a PipelineState", {"state": object()}),
    ("paths digest malformed", {"changed_paths_sha256": "xyz"}),
])
def test_bad_input_is_blocked_before_anything_runs(env, label, over):
    path = env[3]
    submit = Submit(clean_report)
    over = dict(over)
    if "submit" not in over:
        over["submit"] = submit
    if "verify" in over:
        over["verify_report"] = over.pop("verify")
    ps = env[0]
    args = dict(
        state=ps, epoch=env[4], attempt_no=1, initial_head=CAND, declared_coverage=[EXEC], iteration_cap=3,
        changed_paths_sha256=PATHS, clock=FakeClock(), verify_report=always_true)
    if "declared" in over:
        args["declared_coverage"] = over.pop("declared")
    args.update(over)
    state = args.pop("state")
    result = rl.run_review_loop(state, STORY, **args)
    assert result.verdict == "BLOCKED" and codes(result) == ("BAD_INPUT",), label
    assert submit.requests == [] and count(path, "pl_review_iterations") == 0


# --------------------------------------------------------------------- replay after a crash
def collect_run(env, plan, **kw):
    seen = []
    result = run(env, Submit(plan), on_iteration=seen.append, **kw)
    return result, seen


def find_then_clean(request):
    return findings_report(request) if request.local_index == 1 else clean_report(request)


def test_a_complete_replay_submits_nothing_and_records_nothing_new(env):
    ps, _, _, path, _ = env
    first, seen = collect_run(env, find_then_clean, cap=4, fixer=Fixer())
    assert first.verdict == "CLEAN" and len(seen) == 2
    before = ps.get_status(STORY)["counts"]
    submit, fixer, gate = Submit(find_then_clean), Fixer(), Gate()
    second = run(env, submit, cap=4, fixer=fixer, gate=gate, resume=[s.to_dict() for s in seen])
    assert second.verdict == "CLEAN" and submit.requests == [] and fixer.contexts == [] and gate.calls == []
    assert (second.submit_calls, second.fixer_calls) == (0, 0)
    assert [s.replayed for s in second.iterations] == [True, True]
    assert [s.iteration_id for s in second.iterations] == ["it-1", "it-2"]
    assert ps.get_status(STORY)["counts"] == before
    assert [r[4] for r in review_rows(path)] == ["rl-a1-i1", "rl-a1-i2"]
    # an IterationSummary object is accepted as well as its dict form
    third = run(env, Submit(find_then_clean), cap=4, resume=list(seen))
    assert third.verdict == "CLEAN" and third.submit_calls == 0


def test_a_replay_without_any_summaries_rebuilds_everything_from_the_store(env):
    path = env[3]
    first, seen = collect_run(env, find_then_clean, cap=4, fixer=Fixer())
    submit, fixer = Submit(find_then_clean), Fixer()
    result = run(env, submit, cap=4, fixer=fixer)          # no resume at all
    assert result.verdict == "CLEAN" and result.replayed is True
    assert submit.requests == [] and fixer.contexts == [] and (result.submit_calls, result.fixer_calls) == (0, 0)
    assert [s.iteration_id for s in result.iterations] == ["it-1", "it-2"]
    assert [s.iteration_of for s in result.iterations] == [None, "it-1"]
    assert [s.head for s in result.iterations] == [CAND, h(3)] and result.final_head == h(3)
    assert [s.verdict for s in result.iterations] == ["FINDINGS", "CLEAN"]
    assert result.iterations[0].findings_count == 1 and result.iterations[0].coverage == (EXEC,)
    one = [{"role": "python-reviewer", **finding(3)}]
    assert result.iterations[0].finding_set_sha256 == rl.finding_set_sha256(one)
    assert result.iterations[0].findings == tuple(one)
    assert first.replayed is False
    assert [r[4] for r in review_rows(path)] == ["rl-a1-i1", "rl-a1-i2"]


def test_a_crash_between_the_row_and_the_callback_resumes_from_the_store_alone(env):
    path = env[3]

    def dying(summary):
        raise Crash()

    first_submit = Submit(find_then_clean)
    with pytest.raises(Crash):
        run(env, first_submit, cap=4, fixer=Fixer(), on_iteration=dying)
    assert review_rows(path) == [(1, None, 1, "FINDINGS", "rl-a1-i1")]
    second_submit = Submit(find_then_clean)
    result = run(env, second_submit, cap=4, fixer=Fixer())     # the summary never left the process: no resume
    assert result.verdict == "CLEAN" and len(second_submit.requests) == 1
    request = second_submit.requests[0]
    assert (request.local_index, request.iteration_of, request.head) == (2, "it-1", h(3))
    assert result.iterations[0].replayed is True and result.iterations[1].replayed is False
    assert result.replayed is False


def test_a_crash_in_the_fixer_replays_without_resubmitting_the_recorded_iteration(env):
    path = env[3]
    seen = []
    first_submit = Submit(find_then_clean)
    with pytest.raises(Crash):
        run(env, first_submit, cap=4, fixer=Fixer(fail=Crash()), on_iteration=seen.append)
    assert len(first_submit.requests) == 1 and [s.iteration_id for s in seen] == ["it-1"]
    assert review_rows(path) == [(1, None, 1, "FINDINGS", "rl-a1-i1")] and count(path, "pl_diff_gates") == 0
    second_submit = Submit(find_then_clean)
    result = run(env, second_submit, cap=4, fixer=Fixer(), resume=[s.to_dict() for s in seen])   # optional cross-check
    assert result.verdict == "CLEAN"
    assert len(first_submit.requests) + len(second_submit.requests) == 2       # iteration 1 was never re-run
    request = second_submit.requests[0]
    assert (request.local_index, request.iteration_index, request.iteration_of, request.head) == (2, 2, "it-1", h(3))
    assert [r[4] for r in review_rows(path)] == ["rl-a1-i1", "rl-a1-i2"]
    assert [s.replayed for s in result.iterations] == [True, False]


def test_a_crash_after_the_gate_record_adopts_the_stored_candidate_and_skips_the_fixer(env):
    ps, _, _, path, _ = env

    def crashing(request):
        if request.local_index == 1:
            return findings_report(request)
        raise Crash()

    with pytest.raises(Crash):
        run(env, Submit(crashing), cap=4, fixer=Fixer())
    assert count(path, "pl_diff_gates") == 1 and count(path, "pl_review_iterations") == 1
    steps_before = count(path, "pl_steps")            # attempt start, review 1, gate 1
    assert steps_before == 3
    submit, fixer, gate = Submit(clean_report), Fixer(head=h(77)), Gate()   # a new fixer would answer h(77)
    result = run(env, submit, cap=4, fixer=fixer, gate=gate)               # no resume
    assert result.verdict == "CLEAN" and fixer.contexts == [] and gate.calls == []
    assert len(submit.requests) == 1 and submit.requests[0].iteration_of == "it-1"
    assert submit.requests[0].head == h(3)             # the stored candidate head, not the new fixer's
    assert result.gates[0]["gate_id"] == "rl-a1-g1" and result.gates[0]["replayed"] is True
    assert result.gates[0]["candidate_head"] == h(3) and result.fixer_calls == 0
    assert count(path, "pl_diff_gates") == 1 and count(path, "pl_steps") == steps_before + 1


@pytest.mark.parametrize("verdict,code", [("REFUSED", "GATE_REFUSED"), ("BLOCKED", "GATE_BLOCKED")])
def test_a_recorded_gate_refusal_is_reported_again_without_calling_the_fixer(env, verdict, code):
    first = run(env, Submit(findings_report), cap=5, fixer=Fixer(), gate=Gate(verdict))
    assert codes(first) == (code,)
    submit, fixer, gate = Submit(findings_report), Fixer(), Gate()
    again = run(env, submit, cap=5, fixer=fixer, gate=gate)
    assert codes(again) == (code,) and fixer.contexts == [] and gate.calls == [] and submit.requests == []
    assert again.reasons[0][1] == "OUT_OF_SCOPE_PATH" and again.final_head == CAND
    assert again.gates[0]["replayed"] is True


def test_a_second_loop_for_the_same_attempt_inside_submit_is_blocked(env):
    path = env[3]
    inner_results = []

    def outer_plan(request):
        inner_results.append(run(env, Submit(lambda r: make_report(r, "it-1")), cap=2))   # same story and attempt
        return make_report(request, "it-1")

    outer = run(env, Submit(outer_plan), cap=2)
    assert inner_results[0].verdict == "CLEAN"
    assert outer.verdict == "BLOCKED" and codes(outer) == ("RESUME_MISMATCH",) and not outer.clean
    assert count(path, "pl_review_iterations") == 1


def test_a_second_loop_that_recorded_other_facts_is_blocked_too(env):
    path = env[3]
    inner_results = []

    def outer_plan(request):
        inner_results.append(run(env, Submit(lambda r: make_report(r, "inner-1")), cap=2))
        return make_report(request, "outer-1")

    outer = run(env, Submit(outer_plan), cap=2)
    assert inner_results[0].verdict == "CLEAN"
    assert outer.verdict == "BLOCKED" and codes(outer) == ("RESUME_MISMATCH",)
    assert count(path, "pl_review_iterations") == 1


def test_a_replayed_cap_result_does_not_submit_or_fix(env):
    first, seen = collect_run(env, findings_report, cap=2, fixer=Fixer())
    assert codes(first) == ("ITERATION_CAP",)
    submit, fixer = Submit(findings_report), Fixer()
    again = run(env, submit, cap=2, fixer=fixer, resume=[s.to_dict() for s in seen])
    assert codes(again) == ("ITERATION_CAP",) and submit.requests == [] and fixer.contexts == []


def mutated(summaries, index, **changes):
    docs = [s.to_dict() for s in summaries]
    docs[index].update(changes)
    return docs


@pytest.mark.parametrize("label,make", [
    ("verdict differs", lambda s: mutated(s, 0, verdict="PARTIAL")),
    ("finding count differs", lambda s: mutated(s, 0, findings_count=5)),
    ("claims CLEAN with a reason", lambda s: mutated(s, 1, reasons=["COVERAGE_PARTIAL"])),
    ("iteration_of chain broken", lambda s: mutated(s, 1, iteration_of="it-9")),
    ("wrong step id", lambda s: mutated(s, 1, step_id="rl-a1-i9")),
    ("wrong local index", lambda s: mutated(s, 1, local_index=5)),
    ("first head changed", lambda s: mutated(s, 0, head=h(55))),
    ("repeated iteration id", lambda s: mutated(s, 1, iteration_id="it-1", iteration_of="it-1")),
    ("unknown verdict", lambda s: mutated(s, 0, verdict="MAYBE")),
    ("forged head at index 1", lambda s: mutated(s, 0, head=h(55))),
    ("forged coverage", lambda s: mutated(s, 1, coverage=[EXEC, EXTRA])),
    ("forged digest", lambda s: mutated(s, 0, finding_set_sha256="1" * 64)),
    ("forged id", lambda s: mutated(s, 0, iteration_id="it-forged")),
    ("too few summaries", lambda s: [s[0].to_dict()]),
    ("extra key", lambda s: [dict(d, extra=1) for d in map(lambda x: x.to_dict(), s)]),
    ("extra summary", lambda s: [x.to_dict() for x in s] + [s[0].to_dict()]),
])
def test_resume_summaries_that_disagree_with_the_recorded_rows_are_refused(env, label, make):
    first, seen = collect_run(env, find_then_clean, cap=4, fixer=Fixer())
    submit = Submit(find_then_clean)
    result = run(env, submit, cap=4, fixer=Fixer(), resume=make(seen))
    assert result.verdict == "BLOCKED" and codes(result) == ("RESUME_MISMATCH",), label
    assert submit.requests == []


def test_resume_without_any_recorded_iteration_is_refused(env):
    first, seen = collect_run(env, find_then_clean, cap=4, fixer=Fixer())
    # a second attempt has no recorded iteration yet but is handed the first attempt's summaries
    ps, _, _, path, epoch = env
    ps.finish_worker_attempt(STORY, epoch=epoch, step_id="f1", attempt_no=1, state="FAILED")
    ps.start_worker_attempt(STORY, epoch=epoch, step_id="s-start-2", base_head=CAND)
    submit = Submit(clean_report)
    result = run(env, submit, cap=3, attempt_no=2, resume=[s.to_dict() for s in seen])
    assert codes(result) == ("RESUME_MISMATCH",) and submit.requests == []


def test_a_changed_declaration_or_a_smaller_cap_blocks_the_replay(env):
    first, seen = collect_run(env, find_then_clean, cap=4, fixer=Fixer())
    resume = [s.to_dict() for s in seen]
    submit = Submit(find_then_clean)
    changed = run(env, submit, cap=4, declared=(EXEC, EXTRA), resume=resume)
    assert codes(changed) == ("RESUME_MISMATCH",)
    smaller = run(env, submit, cap=1, resume=resume)
    assert codes(smaller) == ("ITERATION_CAP",) and not smaller.clean
    assert submit.requests == []


def test_a_new_owner_may_replay_but_the_old_epoch_is_refused(env):
    ps, _, _, path, epoch = env
    first, seen = collect_run(env, clean_report, cap=2)
    assert first.verdict == "CLEAN"
    bump_epoch(env)
    resume = [s.to_dict() for s in seen]
    stale = run(env, Submit(clean_report), cap=2, resume=resume)                   # old epoch
    assert codes(stale) == ("EPOCH_STALE",)
    fresh = run(env, Submit(clean_report), cap=2, resume=resume, epoch=epoch + 1)  # new owner
    assert fresh.verdict == "CLEAN" and fresh.submit_calls == 0 and fresh.iterations[0].replayed is True


# --------------------------------------------------------------------- result and report contracts
def summary_example(**over):
    base = dict(
        local_index=1, iteration_index=1, step_id="rl-a1-i1", iteration_id="it-1", iteration_of=None, head=CAND,
        findings_count=0, findings=(), finding_set_sha256="0" * 64, coverage=(EXEC,), missing_coverage=(),
        verdict="CLEAN", reasons=())
    base.update(over)
    return IterationSummary(**base)


def result_example(verdict, iterations, reasons=(), declared=(EXEC,), paths=PATHS):
    return ReviewLoopResult(
        verdict=verdict, reasons=tuple(reasons), iterations=tuple(iterations), story_id=STORY, attempt_no=1,
        declared_coverage=tuple(declared), cap_requested=3, cap_effective=3, cap_clamped=False, final_head=CAND,
        submit_calls=1, fixer_calls=0, gates=(), changed_paths_sha256=paths)


def test_a_clean_result_cannot_be_built_without_a_clean_covering_last_iteration():
    result_example("CLEAN", [summary_example()])        # control: the legitimate shape builds
    bad = {
        "no iteration": dict(iterations=[]),
        "last not clean": dict(iterations=[summary_example(verdict="PARTIAL", reasons=("COVERAGE_PARTIAL",))]),
        "findings present": dict(iterations=[summary_example(findings_count=1)]),
        "findings listed with count zero": dict(iterations=[summary_example(findings=({"rule_id": "x"},))]),
        "clean iteration with a reason": dict(iterations=[summary_example(reasons=("COVERAGE_PARTIAL",))]),
        "declared not covered": dict(iterations=[summary_example()], declared=(EXEC, EXTRA)),
        "missing coverage listed": dict(iterations=[summary_example(missing_coverage=(EXTRA,))]),
        "reasons present": dict(iterations=[summary_example()], reasons=[("ITERATION_CAP", "x")]),
        "empty declaration": dict(iterations=[summary_example()], declared=()),
    }
    for label, kw in bad.items():
        with pytest.raises(ValueError):
            result_example("CLEAN", **kw)
    with pytest.raises(ValueError):
        result_example("BLOCKED", [])                    # BLOCKED needs a reason
    # a CLEAN result must carry the 64-hex paths digest the reports were checked against
    for bad_digest in (None, "", "xyz", "E" * 64, "e" * 63, "e" * 65, 5):
        with pytest.raises(ValueError):
            result_example("CLEAN", [summary_example()], paths=bad_digest)
    assert result_example("CLEAN", [summary_example()], paths="a" * 64).changed_paths_sha256 == "a" * 64
    # BLOCKED may lack it (no valid input), but a present value must be well formed
    assert result_example("BLOCKED", [], reasons=[("BAD_INPUT", "x")], paths=None).changed_paths_sha256 is None
    with pytest.raises(ValueError):
        result_example("BLOCKED", [], reasons=[("BAD_INPUT", "x")], paths="xyz")
    with pytest.raises(ValueError):
        result_example("PASS", [summary_example()])      # nothing but CLEAN or BLOCKED


def test_the_result_is_json_serialisable_with_the_documented_fields(env):
    result = run(env, Submit(findings_report), cap=2, fixer=Fixer())
    doc = json.loads(json.dumps(result.to_dict()))
    assert doc["verdict"] == "BLOCKED" and doc["iteration_count"] == 2
    assert doc["reasons"][0]["code"] == "ITERATION_CAP"
    assert set(doc["iterations"][0]) == {
        "local_index", "iteration_index", "step_id", "iteration_id", "iteration_of", "head", "findings_count",
        "findings", "finding_set_sha256", "coverage", "missing_coverage", "verdict", "reasons", "truncated",
        "replayed", "started_at", "finished_at"}
    assert [i["findings_count"] for i in doc["iterations"]] == [1, 1]
    assert (doc["cap_requested"], doc["cap_effective"], doc["submit_calls"], doc["fixer_calls"]) == (2, 2, 2, 1)
    assert IterationSummary.from_dict(doc["iterations"][0]) == result.iterations[0]
    assert doc["changed_paths_sha256"] == PATHS == "e" * 64      # the loop input, exposed for the final package


def test_a_clean_result_exposes_the_paths_digest_in_to_dict(env):
    clean = run(env, Submit(clean_report), cap=2)
    assert clean.verdict == "CLEAN" and clean.changed_paths_sha256 == PATHS
    assert clean.to_dict()["changed_paths_sha256"] == PATHS


def test_a_blocked_result_carries_the_loop_input_digest_not_the_report_digest(env):
    submit = Submit(lambda r: make_report(r, f"it-{r.local_index}", paths="f" * 64))   # reports for other paths
    blocked = run(env, submit, cap=1)
    assert blocked.verdict == "BLOCKED" and codes(blocked) == ("ITERATION_CAP",)
    assert blocked.changed_paths_sha256 == PATHS and blocked.to_dict()["changed_paths_sha256"] == PATHS


def test_a_loop_with_malformed_paths_digest_input_reports_none(env):
    result = run(env, Submit(clean_report), changed_paths_sha256="xyz")
    assert codes(result) == ("BAD_INPUT",) and result.changed_paths_sha256 is None
    assert result.to_dict()["changed_paths_sha256"] is None


def test_a_replayed_result_takes_the_digest_from_the_stored_facts_and_a_different_input_is_refused(env):
    ps = env[0]
    first, seen = collect_run(env, clean_report, cap=2)
    assert first.verdict == "CLEAN" and first.changed_paths_sha256 == PATHS
    stored = ps.get_step(STORY, "rl-a1-i1")["result"]["facts"]["changed_paths_sha256"]
    again = run(env, Submit(clean_report), cap=2)
    assert again.replayed is True and again.verdict == "CLEAN"
    assert again.changed_paths_sha256 == stored == PATHS
    other = run(env, Submit(clean_report), cap=2, changed_paths_sha256="f" * 64)
    assert codes(other) == ("RESUME_MISMATCH",) and not other.clean
    assert other.changed_paths_sha256 == "f" * 64


def test_the_finding_set_digest_matches_an_independent_formula():
    one = [{"role": "python-reviewer", **finding(3)}]
    expected = hashlib.sha256(
        b'[["python-reviewer","py-bare-except","MAJOR","src/a.py",3,1,"' + EVIDENCE.encode() + b'"]]').hexdigest()
    assert rl.finding_set_sha256(one) == expected
    two = [{"role": "python-reviewer", **finding(4)}, *one]
    assert rl.finding_set_sha256(two) == rl.finding_set_sha256(list(reversed(two)))   # order does not matter
    assert rl.finding_set_sha256([]) == hashlib.sha256(b"[]").hexdigest()


def test_judge_report_names_every_reason_for_a_report_that_is_wrong_in_many_ways():
    request = rl.ReviewRequest(STORY, 1, 2, 2, "req-x", CAND, "it-1", (EXEC, EXTRA))
    roles = [role_entry(status="FINDINGS", findings=[finding(3)], executors=((EXEC, "COMPLETE"),),
                        uncovered=["gap"], residual=["model-judgment"])]
    doc = make_report(request, "it-1", roles, head=h(9), request_id="req-other", purpose="advisory", paths="f" * 64)
    judged = rl.judge_report(doc, request_id="req-x", head=CAND, declared=(EXEC, EXTRA), seen_ids=["it-1"],
                             verify_report=lambda d: False, changed_paths_sha256=PATHS)
    assert judged.reasons == (
        "REQUEST_MISMATCH", "HEAD_MISMATCH", "PURPOSE_NOT_RECEIPT", "PATHS_MISMATCH", "REPORT_STALE",
        "SIGNATURE_UNVERIFIED", "FINDINGS_OPEN", "MODEL_RESIDUAL_OPEN", "COVERAGE_PARTIAL",
        "DECLARED_EXECUTOR_MISSING", "EXIT_NOT_ZERO")
    assert judged.verdict == "BLOCKED" and judged.missing == (EXTRA,) and judged.covered == (EXEC,)
    assert judged.exit_code == 3 and len(judged.findings) == 1
    with pytest.raises(rl.ReportUnusable):
        rl.judge_report({"x": 1}, request_id="r", head=CAND, declared=(EXEC,), seen_ids=[], verify_report=always_true,
                        changed_paths_sha256=PATHS)


def test_an_advisory_report_is_never_clean(env):
    submit = Submit(lambda r: make_report(r, f"it-{r.local_index}", purpose="advisory"))
    result = run(env, submit, cap=5)
    assert result.verdict == "BLOCKED" and codes(result) == ("NO_PROGRESS",)
    assert [(s.verdict, s.reasons) for s in result.iterations] == [("BLOCKED", ("PURPOSE_NOT_RECEIPT",))] * 2


def test_a_report_for_other_paths_is_never_clean(env):
    submit = Submit(lambda r: make_report(r, f"it-{r.local_index}", paths="f" * 64))
    result = run(env, submit, cap=5)
    assert result.verdict == "BLOCKED" and codes(result) == ("NO_PROGRESS",)
    assert [(s.verdict, s.reasons) for s in result.iterations] == [("BLOCKED", ("PATHS_MISMATCH",))] * 2


def test_the_request_carries_the_expected_paths_digest_and_purpose(env):
    submit = Submit(clean_report)
    run(env, submit)
    assert (submit.requests[0].changed_paths_sha256, submit.requests[0].purpose) == (PATHS, "receipt")


def test_a_manifest_digest_is_required_when_a_fixer_is_given(env):
    for manifest in (None, "xyz", "A" * 64):
        submit = Submit(findings_report)
        result = run(env, submit, cap=3, fixer=Fixer(), manifest_sha256=manifest)
        assert codes(result) == ("BAD_INPUT",) and submit.requests == []
    assert run(env, Submit(clean_report), cap=2, manifest_sha256=None).verdict == "CLEAN"   # no fixer: not needed


def test_a_verifier_gets_a_copy_and_cannot_change_what_is_judged(env):
    def meddling(doc):
        doc["roles"][0]["status"] = "PARTIAL"
        doc["roles"][0]["executors"][0]["status"] = "PARTIAL"
        doc["iteration_id"] = "tampered"
        return True

    result = run(env, Submit(clean_report), cap=2, verify=meddling)
    assert result.verdict == "CLEAN" and result.iterations[0].iteration_id == "it-1"
    assert result.iterations[0].coverage == (EXEC,)


def test_a_long_finding_list_is_flagged_truncated_but_its_digest_covers_all_findings(env):
    lines = list(range(1, 202))     # 201 findings, the loop keeps 200

    def plan(request):
        return findings_report(request, lines=lines) if request.local_index == 1 else clean_report(request)

    fixer = Fixer()
    first = run(env, Submit(plan), cap=3, fixer=fixer)
    assert first.verdict == "CLEAN"
    summary = first.iterations[0]
    assert summary.truncated is True and summary.findings_count == 201 and len(summary.findings) == 200
    assert fixer.contexts[0].truncated is True and len(fixer.contexts[0].findings) == 200
    full = [{"role": "python-reviewer", **finding(x)} for x in lines]
    assert summary.finding_set_sha256 == rl.finding_set_sha256(full)
    again = run(env, Submit(plan), cap=3, fixer=Fixer())          # the flag and the digest come back from the store
    assert again.replayed is True and again.iterations[0].truncated is True
    assert again.iterations[0].finding_set_sha256 == summary.finding_set_sha256
    assert again.iterations[1].truncated is False


def test_the_driver_imports_only_the_expected_modules():
    """A guard on the import list (it is not a proof of no side effects): no os, subprocess, shutil or sqlite3,
    and the only relative imports are the contract, the pipeline state, the store and the worker gate."""
    source = pathlib.Path(rl.__file__).read_text(encoding="utf-8")
    absolute, relative = set(), set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            absolute |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                absolute.add((node.module or "").split(".")[0])
            else:
                relative.add((node.level, node.module or "", tuple(sorted(a.name for a in node.names if node.module is None))))
    assert absolute == {"__future__", "copy", "hashlib", "json", "math", "re", "dataclasses", "typing"}
    assert relative == {(2, "uc", ()), (1, "pipeline_state", ()), (1, "store", ()), (1, "worker_gate", ())}
