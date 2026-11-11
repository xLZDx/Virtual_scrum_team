"""U5-6: synthetic end-to-end story, model-forbidden.

Acceptance text: "Run with the model fallback disabled and every model invocation stubbed to raise; the
model-call count is 0; a clean control story that uses only fully covered local roles with no model-residual
obligation returns CLEAN; a separate fixture with a LOCAL_PLUS_MODEL role whose local checks pass but whose model
part is disabled returns PARTIAL or another non-approving status, never CLEAN; each seeded defect names its
expected stage, executor, rule and status; defect classes: moved head, forged signature, skipped test, partial
coverage, unsupported rule, role-table drift, secret in a finding; a negative control with the responsible check
disabled by hand shows the defect is then not caught."

The harness is tests/vst/u5_e2e_support.py (real U1-U5 code, canned AEVE answers, no model, no network, no git).
Every expected value below is written by hand from the vocabularies in the real modules and from
docs/sdlc/u5/E2E_STORY.md; none is read from the code under test. Every scenario ends with the same two
assertions (see `story`): the model-fallback flag is False and the model-call count is 0.

Negative controls: the ONE responsible check is replaced inside the test's own `monkeypatch` scope (or the one
relaxed input is passed); production code is never edited. The control is "this is not a mutation run".
Tests are written, NOT_RUN (operator ban on running tests for this sprint).
"""

from __future__ import annotations

import json

import pytest

from tools.uc import role_table as uc_role_table
from tools.uc import router
from tools.vst import final_package as fp
from tools.vst import gate
from tools.vst import review_loop as rl

from .u5_e2e_support import (
    HEAD, HEAD2, SECRET_TEXT, T1, T2, UNKNOWN_RULE, CLEAN_ROLES, MODEL_ROLE, ModelGuard, FakeAeve, StorySpec,
    lenient_coverage_judge, real_table, resolve_model_residual, run_story,
)

CLEAN_DECLARED = ["g1.repository-snapshot", "g4.worktree-facts", "g5.layering-shapes"]
FULL_TRACE = ["role_table", "worker_gate", "rule_coverage", "router_normalize", "review_loop", "gate", "final_package"]
PARTIAL_EXECUTOR = {"g5.layering-shapes": "PARTIAL"}
SECRET_FINDING = (("g5.layering-shapes", SECRET_TEXT),)
LEAKED_TOKEN = "api_key-abcd1234wxyz"   # what to_token makes of SECRET_TEXT when has_secret is switched off


def story(tmp_path, **knobs):
    """Run one scenario and check, for every scenario including the failing ones, that no model was reached."""
    spec = StorySpec(**knobs)
    assert spec.model_fallback is False or knobs.get("model_fallback") is True
    outcome = run_story(tmp_path, spec)
    expect_calls = 1 if (knobs.get("model_fallback") or knobs.get("model_fixer")) else 0
    assert outcome.guard.count == expect_calls
    assert outcome.config.model_fallback is bool(knobs.get("model_fallback", False))
    return outcome


def finding_rules(outcome):
    return [f["rule_id"] for report in outcome.reports for role in report["roles"] for f in role["findings"]]


# ------------------------------------------------------------------ fixture honesty
def test_fixture_roles_are_the_real_catalog_entries():
    table, _ = real_table()
    by_name = {e["name"]: e for e in table["entries"]}
    expected = {
        "repo-recon": ("LOCAL", "COVERED_PARTIAL", ["g1.repository-snapshot", "g5.layering-shapes"]),
        "git-worktree-ops": ("LOCAL", "COVERED_PARTIAL", ["g4.worktree-facts"]),
        "python-reviewer": ("LOCAL_PLUS_MODEL", "COVERED_PARTIAL", ["g2.python-rules"]),
    }
    for name, (klass, state, executors) in expected.items():
        assert (by_name[name]["class"], by_name[name]["coverage_state"], by_name[name]["executors"]) == (
            klass, state, executors)
    assert CLEAN_ROLES == ("repo-recon", "git-worktree-ops") and MODEL_ROLE == ("python-reviewer",)


# ------------------------------------------------------------------ model guard
def test_guard_counts_and_raises():
    guard = ModelGuard()
    with pytest.raises(AssertionError, match="model invoked"):
        guard.invoke("anything")
    assert guard.count == 1 and guard.calls == ["anything"]


def test_every_model_capable_seam_goes_through_the_guard():
    guard = ModelGuard()
    aeve = FakeAeve(guard, model_fallback=True, executor_status={}, raw_findings=())
    request = {"executor_ids": ["g1.repository-snapshot"], "request_id": "r-1", "base_revision": HEAD}
    with pytest.raises(AssertionError, match="model invoked"):
        aeve.run(request)
    report = {"roles": [{"role": "python-reviewer", "model_residual": ["model-judgment"]}]}
    with pytest.raises(AssertionError, match="model invoked"):
        resolve_model_residual(report, guard, enabled=True)
    with pytest.raises(AssertionError, match="model invoked"):
        guard.fixer(None)
    assert guard.calls == ["aeve-model-fallback", "model-residual", "fixer"] and guard.count == 3
    # disabled: the same seams do not touch the guard
    quiet = ModelGuard()
    assert FakeAeve(quiet, model_fallback=False, executor_status={}, raw_findings=()).run(request)[1] == 0
    assert resolve_model_residual(report, quiet, enabled=False) == ["python-reviewer"]
    assert quiet.count == 0


def test_a_story_that_reaches_the_model_fallback_is_blocked_and_counted(tmp_path):
    outcome = story(tmp_path, model_fallback=True)
    assert outcome.stopped_at == "review_loop" and outcome.final == "BLOCKED"
    assert "SUBMIT_FAILED" in outcome.loop_result.reason_codes
    assert outcome.guard.calls == ["aeve-model-fallback"]


def test_a_story_that_reaches_the_model_fixer_is_blocked_and_counted(tmp_path):
    outcome = story(tmp_path, model_fixer=True, cap=2, raw_findings=(("g5.layering-shapes", "py-bare-except"),))
    assert outcome.stopped_at == "review_loop" and outcome.final == "BLOCKED"
    assert "FIXER_FAILED" in outcome.loop_result.reason_codes
    assert outcome.guard.calls == ["fixer"]


# ------------------------------------------------------------------ scenario 1: clean control
def test_clean_control_story_is_clean_end_to_end(tmp_path):
    outcome = story(tmp_path)
    assert outcome.trace == FULL_TRACE
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")
    assert outcome.worker_verdict.verdict == "ACCEPTED"
    report = outcome.reports[0]
    assert [(r["role"], r["class"], r["status"], r["model_residual"], r["uncovered"]) for r in report["roles"]] == [
        ("repo-recon", "LOCAL", "CLEAN", [], []), ("git-worktree-ops", "LOCAL", "CLEAN", [], [])]
    assert report["exit_code"] == 0
    loop = outcome.loop_result
    assert loop.verdict == "CLEAN" and loop.reasons == () and loop.declared_coverage == tuple(CLEAN_DECLARED)
    assert [i.verdict for i in loop.iterations] == ["CLEAN"] and loop.iterations[0].coverage == tuple(CLEAN_DECLARED)
    assert outcome.gate_decision["verdict"] == "APPROVE"
    package = outcome.package_result.package
    assert package["review"]["verdict"] == "CLEAN" and package["valid_for_head"] == HEAD
    assert package["tests"]["passed"] == sorted([T1, T2]) and package["not_run"] == []


# ------------------------------------------------------------------ scenario 2: LOCAL_PLUS_MODEL, model part disabled
def test_local_plus_model_role_with_the_model_part_disabled_is_partial_never_clean(tmp_path):
    outcome = story(tmp_path, roles=MODEL_ROLE)
    role = outcome.reports[0]["roles"][0]
    assert (role["role"], role["class"], role["status"], role["model_residual"]) == (
        "python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", ["model-judgment"])
    assert [e["status"] for e in role["executors"]] == ["COMPLETE"]       # the local part passed
    loop = outcome.loop_result
    assert [i.verdict for i in loop.iterations] == ["PARTIAL"]
    assert list(loop.iterations[0].reasons) == ["MODEL_RESIDUAL_OPEN", "COVERAGE_PARTIAL", "EXIT_NOT_ZERO"]
    assert loop.verdict == "BLOCKED" and loop.verdict != "CLEAN"
    assert (outcome.stopped_at, outcome.final) == ("review_loop", "BLOCKED")
    assert "model_part_disabled_for=['python-reviewer']" in outcome.notes["router_normalize"]
    assert outcome.package_result is None and "final_package" not in outcome.trace


def test_local_plus_model_fixture_is_never_ready_even_when_the_package_is_forced(tmp_path):
    outcome = story(tmp_path, roles=MODEL_ROLE, force_package=True)
    assert outcome.package_result.verdict == "REFUSED" and outcome.final == "REFUSED"
    assert "REVIEW_NOT_CLEAN" in outcome.notes["final_package"]


# ------------------------------------------------------------------ scenario 3: seeded defects
# (id, knobs, catching stage, executor named, rule named, stage where the story stops, final status)
DEFECTS = [
    pytest.param({"t2_head": HEAD2}, "final_package", T2, "STALE_EVIDENCE", "final_package", "REFUSED",
                 id="moved-head-package"),
    pytest.param({"gate_head": HEAD2}, "gate", "tests", "stale head", "gate", "NO_GO", id="moved-head-gate"),
    pytest.param({"forge_receipt": True}, "gate", "tests", "invalid signature", "gate", "MODIFY",
                 id="forged-signature-receipt"),
    pytest.param({"forge_report": True}, "review_loop", "g5.layering-shapes", "SIGNATURE_UNVERIFIED", "review_loop",
                 "BLOCKED", id="forged-signature-report"),
    pytest.param({"t2_status": "NOT_RUN"}, "final_package", T2, "NOT_RUN_UNACKNOWLEDGED", "final_package",
                 "REFUSED", id="skipped-test"),
    pytest.param({"executor_status": PARTIAL_EXECUTOR}, "review_loop", "g5.layering-shapes",
                 "DECLARED_EXECUTOR_MISSING", "review_loop", "BLOCKED", id="partial-coverage"),
    pytest.param({"unknown_rule": True}, "rule_coverage", "g2.python-rules", "STATUS_UNKNOWN_RULE", "rule_coverage",
                 "BLOCKED", id="unsupported-rule"),
    pytest.param({"probe_head": "f" * 40}, "role_table", None, "pin: AEVE head differs from the probed checkout",
                 "role_table", "BLOCKED", id="role-table-drift-head"),
    pytest.param({"probe_matrix_digest": "f" * 64}, "role_table", None,
                 "pin: AEVE matrix digest differs from the probed matrix", "role_table", "BLOCKED",
                 id="role-table-drift-matrix-digest"),
    pytest.param({"matrix_executor_drift": True}, "role_table", "python-reviewer",
                 "executors differ from the matrix", "role_table", "BLOCKED", id="role-table-drift-executors"),
    pytest.param({"raw_findings": SECRET_FINDING}, "router_normalize", "g5.layering-shapes", "redacted",
                 "review_loop", "BLOCKED", id="secret-in-finding"),
    pytest.param({"secret_reason": SECRET_TEXT}, "final_package", "test_evidence", "SECRET_IN_EVIDENCE",
                 "final_package", "REFUSED", id="secret-in-evidence-text"),
]


@pytest.mark.parametrize("knobs, stage, executor, rule, stopped_at, final", DEFECTS)
def test_seeded_defect_names_stage_executor_rule_and_status(tmp_path, knobs, stage, executor, rule, stopped_at, final):
    outcome = story(tmp_path, **knobs)
    assert stage in outcome.notes
    note = outcome.notes[stage]
    assert rule in note
    if executor is not None:
        assert executor in note
    assert (outcome.stopped_at, outcome.final) == (stopped_at, final)
    assert outcome.final not in ("CLEAN", "READY", "APPROVE")
    assert SECRET_TEXT not in json.dumps(outcome.reports) + "".join(outcome.notes.values())


def test_secret_finding_is_redacted_in_the_result_and_the_story_still_stops(tmp_path):
    outcome = story(tmp_path, raw_findings=SECRET_FINDING)
    assert finding_rules(outcome) == ["redacted"]
    assert outcome.loop_result.verdict == "BLOCKED"
    assert [i.verdict for i in outcome.loop_result.iterations] == ["FINDINGS"]
    assert "ITERATION_CAP" in outcome.loop_result.reason_codes


def test_unsupported_rule_names_the_rule_id(tmp_path):
    outcome = story(tmp_path, unknown_rule=True)
    assert UNKNOWN_RULE in outcome.notes["rule_coverage"]


def test_partial_coverage_report_is_partial_and_names_the_missing_executor(tmp_path):
    outcome = story(tmp_path, executor_status=PARTIAL_EXECUTOR)
    iteration = outcome.loop_result.iterations[0]
    assert iteration.verdict == "PARTIAL" and iteration.missing_coverage == ("g5.layering-shapes",)
    assert list(iteration.reasons) == ["COVERAGE_PARTIAL", "DECLARED_EXECUTOR_MISSING", "EXIT_NOT_ZERO"]


# ------------------------------------------------------------------ scenario 4: negative controls
def test_control_moved_head_not_caught_when_the_stale_check_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(fp, "_stale", lambda *args, **kwargs: None)       # the one check: stale-evidence reason
    outcome = story(tmp_path, t2_head=HEAD2)
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")
    assert "STALE_EVIDENCE" not in outcome.notes["final_package"]


def test_control_forged_receipt_not_caught_when_the_signature_check_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "verify", lambda *args, **kwargs: True)     # the one check: HMAC verification
    outcome = story(tmp_path, forge_receipt=True)
    assert outcome.gate_decision["verdict"] == "APPROVE"
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")


def test_control_forged_report_not_caught_when_the_verifier_accepts_everything(tmp_path):
    outcome = story(tmp_path, forge_report=True, verify_report=lambda doc: True)   # the one check: verify_report
    assert outcome.loop_result.verdict == "CLEAN"
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")


def test_control_skipped_test_not_caught_when_the_acknowledgement_is_given(tmp_path):
    outcome = story(tmp_path, t2_status="NOT_RUN", allow_not_run={T2: "control: the check is relaxed by hand"})
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")
    assert "NOT_RUN_UNACKNOWLEDGED" not in outcome.notes["final_package"]
    assert [item["test_id"] for item in outcome.package_result.package["not_run"]] == [T2]   # still listed, not PASS


def test_control_partial_coverage_not_caught_when_the_coverage_judgement_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(rl, "judge_report", lenient_coverage_judge(rl.judge_report))   # the one check: coverage reasons
    outcome = story(tmp_path, executor_status=PARTIAL_EXECUTOR)
    assert outcome.reports[0]["roles"][0]["status"] == "PARTIAL"      # the evidence still shows the gap
    assert outcome.loop_result.verdict == "CLEAN"
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")


def test_control_unsupported_rule_not_caught_when_the_catalog_admits_it(tmp_path):
    outcome = story(tmp_path, unknown_rule=True, catalog_admits_unknown=True)   # the one input: required-rule catalog
    assert "coverage=FULL clean=True" in outcome.notes["rule_coverage"]
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")


@pytest.mark.parametrize("knobs", [
    pytest.param({"probe_head": "f" * 40}, id="head"),
    pytest.param({"probe_matrix_digest": "f" * 64}, id="matrix-digest"),
    pytest.param({"matrix_executor_drift": True}, id="executors"),
])
def test_control_role_table_drift_not_caught_when_validation_is_off(tmp_path, monkeypatch, knobs):
    monkeypatch.setattr(uc_role_table, "validate_role_table", lambda *args, **kwargs: [])   # the one check
    outcome = story(tmp_path, **knobs)
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")
    assert outcome.notes["role_table"] == "table matches the probed AEVE checkout"


def test_control_secret_in_finding_leaks_when_the_redaction_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(router, "has_secret", lambda text: False)         # the one check: secret-shape detection
    outcome = story(tmp_path, raw_findings=SECRET_FINDING)
    assert finding_rules(outcome) == [LEAKED_TOKEN]
    assert "abcd1234wxyz" in json.dumps(outcome.reports)


def test_control_secret_in_evidence_text_leaks_when_the_scan_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(fp, "_refuse_secrets", lambda *args, **kwargs: None)   # the one check: free-text scan
    outcome = story(tmp_path, secret_reason=SECRET_TEXT)
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")
    assert SECRET_TEXT in json.dumps(outcome.package_result.package)
