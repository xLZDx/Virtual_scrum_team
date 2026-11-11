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
docs/sdlc/u5/E2E_STORY.md; none is read from the code under test.

Non-vacuous model count: `story` installs `install_escape_guards` (subprocess.Popen/run, socket connect,
adapter.run_review, router._call, aeve_probe.probe, and anthropic/openai constructors when importable) so any real
escape raises AssertionError('model invoked') and is counted. `test_escape_seams_raise_and_count` proves each patched
seam fires. The expected call count and the expected model_fallback flag are literals given by each test.

Structured assertions: gate decision verdict/reasons, CoverageError.code, PackageResult.reasons pairs,
ReviewLoopResult.reasons and IterationSummary fields, router result roles. "Executor" for gate and package rows is
the evidence producer (slot, test id, section); AEVE executor ids appear only where the code under test produced
them (router result, review loop coverage).

Negative controls: the ONE responsible check is replaced inside the test's own `monkeypatch` scope (or the one
relaxed input is passed); production code is never edited. This is not a mutation run.
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
    HEAD, HEAD2, SECRET_TEXT, T1, T2, UNKNOWN_RULE, UNSUPPORTED_RULE, CLEAN_ROLES, MODEL_ROLE, FakeAeve, ModelGuard,
    StorySpec, install_escape_guards, lenient_coverage_judge, real_table, resolve_model_residual, run_story,
)

CLEAN_DECLARED = ["g1.repository-snapshot", "g4.worktree-facts", "g5.layering-shapes"]
FULL_TRACE = ["role_table", "worker_gate", "rule_coverage", "router_normalize", "review_loop", "gate", "final_package"]
PARTIAL_EXECUTOR = {"g5.layering-shapes": "PARTIAL"}
SECRET_FINDING = (("g5.layering-shapes", SECRET_TEXT),)
LEAKED_TOKEN = "api_key-abcd1234wxyz"   # what to_token makes of SECRET_TEXT when has_secret is switched off
SECRET_EVIDENCE_REASON = ("SECRET_IN_EVIDENCE", "test_evidence contains a value that looks like a secret")


def story(tmp_path, monkeypatch, *, model_calls=0, fallback=False, submit_error=False, **knobs):
    """Run one scenario with the escape points guarded.

    `model_calls`, `fallback` and `submit_error` are literals written by each test: the expected guard count, the
    expected model_fallback flag and whether submit is expected to have failed. They are never derived from `knobs`.
    """
    guard = ModelGuard()
    install_escape_guards(monkeypatch, guard)
    outcome = run_story(tmp_path, StorySpec(**knobs), guard=guard)
    assert outcome.config.model_fallback is fallback
    assert guard.count == model_calls
    assert ("submit_error" in outcome.notes) is submit_error
    return outcome


def finding_rules(outcome):
    return [f["rule_id"] for report in outcome.reports for role in report["roles"] for f in role["findings"]]


def package_reasons(outcome):
    return list(outcome.package_result.reasons)


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


# ------------------------------------------------------------------ model guard (non-vacuous)
def test_guard_counts_and_raises():
    guard = ModelGuard()
    with pytest.raises(AssertionError, match="model invoked"):
        guard.invoke("anything")
    assert guard.count == 1 and guard.calls == ["anything"]


def test_escape_seams_raise_and_count(monkeypatch):
    guard = ModelGuard()
    installed = install_escape_guards(monkeypatch, guard)
    names = [name for name, _, _ in installed]
    assert {"subprocess.Popen", "subprocess.run", "socket.socket.connect", "adapter.run_review", "router._call",
            "aeve_probe.probe"} <= set(names)
    for position, (name, owner, attribute) in enumerate(installed, 1):
        with pytest.raises(AssertionError, match="model invoked"):
            getattr(owner, attribute)()
        assert guard.count == position and guard.calls[-1] == name


def test_every_harness_model_seam_goes_through_the_guard():
    guard = ModelGuard()
    aeve = FakeAeve(guard, aeve_model_fallback=True, executor_status={}, raw_findings=())
    request = {"executor_ids": ["g1.repository-snapshot"], "request_id": "r-1", "base_revision": HEAD}
    with pytest.raises(AssertionError, match="model invoked"):
        aeve.run(request)
    report = {"roles": [{"role": "python-reviewer", "model_residual": ["model-judgment"]}]}
    with pytest.raises(AssertionError, match="model invoked"):
        resolve_model_residual(report, guard, enabled=True)
    with pytest.raises(AssertionError, match="model invoked"):
        guard.fixer(None)
    assert guard.calls == ["aeve-model-fallback", "model-residual", "fixer"] and guard.count == 3
    quiet = ModelGuard()
    response, exit_code = FakeAeve(quiet, aeve_model_fallback=False, executor_status={}, raw_findings=()).run(request)
    assert exit_code == 0 and response["llm_calls"] == 0
    assert resolve_model_residual(report, quiet, enabled=False) == ["python-reviewer"]
    assert quiet.count == 0


def test_aeve_model_fallback_is_blocked_and_counted(tmp_path, monkeypatch):
    outcome = story(tmp_path, monkeypatch, model_calls=1, submit_error=True, aeve_model_fallback=True)
    assert (outcome.stopped_at, outcome.final) == ("review_loop", "BLOCKED")
    assert "SUBMIT_FAILED" in outcome.loop_result.reason_codes
    assert outcome.guard.calls == ["aeve-model-fallback"]


def test_model_residual_fallback_is_blocked_and_counted(tmp_path, monkeypatch):
    outcome = story(tmp_path, monkeypatch, model_calls=1, fallback=True, submit_error=True,
                    roles=MODEL_ROLE, model_fallback=True)
    assert (outcome.stopped_at, outcome.final) == ("review_loop", "BLOCKED")
    assert "SUBMIT_FAILED" in outcome.loop_result.reason_codes
    assert outcome.guard.calls == ["model-residual"]


def test_model_writing_fixer_is_blocked_and_counted(tmp_path, monkeypatch):
    outcome = story(tmp_path, monkeypatch, model_calls=1, model_fixer=True, cap=2,
                    raw_findings=(("g5.layering-shapes", "py-bare-except"),))
    assert (outcome.stopped_at, outcome.final) == ("review_loop", "BLOCKED")
    assert "FIXER_FAILED" in outcome.loop_result.reason_codes
    assert outcome.guard.calls == ["fixer"]


# ------------------------------------------------------------------ scenario 1: clean control
def test_clean_control_story_is_clean_end_to_end(tmp_path, monkeypatch):
    outcome = story(tmp_path, monkeypatch)
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
    assert outcome.gate_decision["verdict"] == "APPROVE" and outcome.gate_decision["reasons"] == []
    assert outcome.package_result.reasons == ()
    package = outcome.package_result.package
    assert package["review"]["verdict"] == "CLEAN" and package["valid_for_head"] == HEAD
    assert package["tests"]["passed"] == sorted([T1, T2]) and package["not_run"] == []


# ------------------------------------------------------------------ scenario 2: LOCAL_PLUS_MODEL, model part disabled
def test_local_plus_model_role_with_the_model_part_disabled_is_partial_never_clean(tmp_path, monkeypatch):
    outcome = story(tmp_path, monkeypatch, roles=MODEL_ROLE)
    role = outcome.reports[0]["roles"][0]
    assert (role["role"], role["class"], role["status"], role["model_residual"]) == (
        "python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", ["model-judgment"])
    assert [(e["id"], e["status"]) for e in role["executors"]] == [("g2.python-rules", "COMPLETE")]   # local part passed
    loop = outcome.loop_result
    assert [i.verdict for i in loop.iterations] == ["PARTIAL"]
    assert list(loop.iterations[0].reasons) == ["MODEL_RESIDUAL_OPEN", "COVERAGE_PARTIAL", "EXIT_NOT_ZERO"]
    assert loop.verdict == "BLOCKED" and loop.reason_codes == ("ITERATION_CAP",)
    assert (outcome.stopped_at, outcome.final) == ("review_loop", "BLOCKED")
    assert "model_part_disabled_for=['python-reviewer']" in outcome.notes["router_normalize"]
    assert outcome.package_result is None and "final_package" not in outcome.trace


def test_local_plus_model_fixture_is_never_ready_even_when_the_package_is_forced(tmp_path, monkeypatch):
    outcome = story(tmp_path, monkeypatch, roles=MODEL_ROLE, force_package=True)
    assert outcome.final == "REFUSED" and outcome.package_result.verdict == "REFUSED"
    assert "REVIEW_NOT_CLEAN" in [code for code, _ in package_reasons(outcome)]
    assert outcome.package_result.package is None


# ------------------------------------------------------------------ scenario 3: seeded defects (structured)
def test_moved_head_in_test_evidence_is_refused_by_the_package(tmp_path, monkeypatch):
    # stage final_package; executor = evidence producer = the test id; rule STALE_EVIDENCE; status REFUSED
    outcome = story(tmp_path, monkeypatch, t2_head=HEAD2)
    assert (outcome.stopped_at, outcome.final) == ("final_package", "REFUSED")
    assert package_reasons(outcome) == [
        ("STALE_EVIDENCE", f"test:{T2}: evidence names head {HEAD2}, the package head is {HEAD}")]


def test_moved_head_at_the_gate_is_no_go(tmp_path, monkeypatch):
    # stage gate; executor = evidence producer = slot "tests" (receipt r-tests-1); rule "stale head"; status NO_GO
    outcome = story(tmp_path, monkeypatch, gate_head=HEAD2)
    decision = outcome.gate_decision
    assert (outcome.stopped_at, outcome.final) == ("gate", "NO_GO") and decision["verdict"] == "NO_GO"
    assert ("receipt r-tests-1 stale head: candidate_head != current head (slot 'tests' attempt 1)"
            in decision["reasons"])
    assert "all deciding receipts for this task are stale (head mismatch or future epoch)" in decision["reasons"]


def test_forged_receipt_signature_is_modify_and_the_slot_is_missing(tmp_path, monkeypatch):
    # stage gate; executor = slot "tests" (receipt[0] = r-tests-1, signed with the wrong key); rule "invalid signature"
    outcome = story(tmp_path, monkeypatch, forge_receipt=True)
    decision = outcome.gate_decision
    assert (outcome.stopped_at, outcome.final) == ("gate", "MODIFY") and decision["verdict"] == "MODIFY"
    assert "receipt[0] (r-tests-1) invalid signature" in decision["reasons"]
    assert "missing receipt for slot 'tests'" in decision["reasons"]
    assert decision["acceptance_unmet"] == ["AC-1"]


def test_forged_report_signature_blocks_the_review_loop(tmp_path, monkeypatch):
    # stage review_loop; rule SIGNATURE_UNVERIFIED; the executors are those the loop saw COMPLETE
    outcome = story(tmp_path, monkeypatch, forge_report=True)
    loop = outcome.loop_result
    assert (outcome.stopped_at, outcome.final) == ("review_loop", "BLOCKED")
    assert loop.reason_codes == ("ITERATION_CAP",)
    assert loop.iterations[0].verdict == "BLOCKED" and loop.iterations[0].reasons == ("SIGNATURE_UNVERIFIED",)
    assert loop.iterations[0].coverage == tuple(CLEAN_DECLARED)


def test_skipped_required_test_is_refused_by_the_package(tmp_path, monkeypatch):
    # stage final_package; executor = test id T2; rule NOT_RUN_UNACKNOWLEDGED; status REFUSED
    outcome = story(tmp_path, monkeypatch, t2_status="NOT_RUN")
    assert (outcome.stopped_at, outcome.final) == ("final_package", "REFUSED")
    assert package_reasons(outcome) == [
        ("NOT_RUN_UNACKNOWLEDGED", f"required tests not run and not acknowledged: {T2}")]


def test_partial_coverage_names_the_missing_executor(tmp_path, monkeypatch):
    # stage review_loop; executor g5.layering-shapes (produced by router + loop); rule DECLARED_EXECUTOR_MISSING
    outcome = story(tmp_path, monkeypatch, executor_status=PARTIAL_EXECUTOR)
    loop = outcome.loop_result
    iteration = loop.iterations[0]
    assert (outcome.stopped_at, outcome.final) == ("review_loop", "BLOCKED") and loop.reason_codes == ("ITERATION_CAP",)
    assert iteration.verdict == "PARTIAL" and iteration.missing_coverage == ("g5.layering-shapes",)
    assert iteration.reasons == ("COVERAGE_PARTIAL", "DECLARED_EXECUTOR_MISSING", "EXIT_NOT_ZERO")
    assert iteration.coverage == ("g1.repository-snapshot", "g4.worktree-facts")


def test_rule_outside_the_required_catalog_is_unknown_rule(tmp_path, monkeypatch):
    # stage rule_coverage; rule STATUS_UNKNOWN_RULE naming the rule id; status BLOCKED (harness mapping of the raise)
    outcome = story(tmp_path, monkeypatch, unknown_rule=True)
    assert (outcome.stopped_at, outcome.final) == ("rule_coverage", "BLOCKED")
    assert outcome.coverage_error.code == "STATUS_UNKNOWN_RULE" and UNKNOWN_RULE in str(outcome.coverage_error)
    assert outcome.coverage_result is None


def test_required_rule_marked_unsupported_makes_coverage_partial_and_not_clean(tmp_path, monkeypatch):
    # stage rule_coverage; rule = the unsupported required rule id; coverage PARTIAL, clean False; status BLOCKED
    outcome = story(tmp_path, monkeypatch, unsupported_rule=True)
    assert (outcome.stopped_at, outcome.final) == ("rule_coverage", "BLOCKED")
    fields = outcome.coverage_result["fields"]
    assert outcome.coverage_result["clean"] is False and outcome.coverage_error is None
    assert fields["coverage"] == "PARTIAL"
    assert fields["unsupported_rules"] == [UNSUPPORTED_RULE] and fields["covered_rules"] == ["PY-BARE-EXCEPT"]
    assert fields["rule_statuses"] == [{"rule_id": "PY-BARE-EXCEPT", "status": "SUPPORTED_AND_CHECKED"},
                                       {"rule_id": UNSUPPORTED_RULE, "status": "UNSUPPORTED"}]


@pytest.mark.parametrize("knobs, problem", [
    pytest.param({"probe_head": "f" * 40}, "pin: AEVE head differs from the probed checkout", id="head"),
    pytest.param({"probe_matrix_digest": "f" * 64}, "pin: AEVE matrix digest differs from the probed matrix",
                 id="matrix-digest"),
    pytest.param({"matrix_executor_drift": True},
                 "agent python-reviewer: executors differ from the matrix for 'python-reviewer'", id="executors"),
])
def test_role_table_drift_is_blocked_with_the_exact_problem(tmp_path, monkeypatch, knobs, problem):
    # stage role_table; pin rows name no executor (table-wide); the executor row names the role; status BLOCKED
    outcome = story(tmp_path, monkeypatch, **knobs)
    assert (outcome.stopped_at, outcome.final) == ("role_table", "BLOCKED")
    assert outcome.role_problems == [problem]
    assert outcome.trace == ["role_table"]


def test_secret_in_a_finding_is_redacted_by_the_router(tmp_path, monkeypatch):
    # stage router_normalize; executor g5.layering-shapes (router result executors); rule id becomes "redacted"
    outcome = story(tmp_path, monkeypatch, raw_findings=SECRET_FINDING)
    recon = outcome.reports[0]["roles"][0]
    assert recon["role"] == "repo-recon" and recon["status"] == "FINDINGS"
    assert [e["id"] for e in recon["executors"]] == ["g1.repository-snapshot", "g5.layering-shapes"]
    assert finding_rules(outcome) == ["redacted"]
    assert SECRET_TEXT not in json.dumps(outcome.reports) + "".join(outcome.notes.values())
    loop = outcome.loop_result
    assert (outcome.stopped_at, outcome.final) == ("review_loop", "BLOCKED")
    assert [i.verdict for i in loop.iterations] == ["FINDINGS"] and loop.reason_codes == ("ITERATION_CAP",)


def test_secret_in_evidence_text_is_refused_by_the_package(tmp_path, monkeypatch):
    # stage final_package; executor = evidence section "test_evidence"; rule SECRET_IN_EVIDENCE; status REFUSED
    outcome = story(tmp_path, monkeypatch, secret_reason=SECRET_TEXT)
    assert (outcome.stopped_at, outcome.final) == ("final_package", "REFUSED")
    assert package_reasons(outcome) == [SECRET_EVIDENCE_REASON]
    assert SECRET_TEXT not in "".join(outcome.notes.values())


# ------------------------------------------------------------------ scenario 4: negative controls
def test_control_moved_head_not_caught_when_the_stale_check_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(fp, "_stale", lambda *args, **kwargs: None)       # the one check: stale-evidence reason
    outcome = story(tmp_path, monkeypatch, t2_head=HEAD2)
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")
    assert package_reasons(outcome) == []


def test_control_forged_receipt_not_caught_when_the_signature_check_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "verify", lambda *args, **kwargs: True)     # the one check: HMAC verification
    outcome = story(tmp_path, monkeypatch, forge_receipt=True)
    assert outcome.gate_decision["verdict"] == "APPROVE" and outcome.gate_decision["reasons"] == []
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")


def test_control_forged_report_not_caught_when_the_verifier_accepts_everything(tmp_path, monkeypatch):
    outcome = story(tmp_path, monkeypatch, forge_report=True, verify_report=lambda doc: True)   # the one check
    assert outcome.loop_result.verdict == "CLEAN" and outcome.loop_result.reasons == ()
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")


def test_control_skipped_test_not_caught_when_the_acknowledgement_is_given(tmp_path, monkeypatch):
    outcome = story(tmp_path, monkeypatch, t2_status="NOT_RUN",
                    allow_not_run={T2: "control: the check is relaxed by hand"})
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")
    assert package_reasons(outcome) == []
    assert [item["test_id"] for item in outcome.package_result.package["not_run"]] == [T2]   # still listed, not PASS


def test_control_partial_coverage_not_caught_when_the_coverage_judgement_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(rl, "judge_report", lenient_coverage_judge(rl.judge_report))   # the one check: coverage reasons
    outcome = story(tmp_path, monkeypatch, executor_status=PARTIAL_EXECUTOR)
    assert outcome.reports[0]["roles"][0]["status"] == "PARTIAL"      # the evidence still shows the gap
    assert outcome.loop_result.verdict == "CLEAN" and outcome.loop_result.reasons == ()   # not BLOCKED by an exception
    assert "submit_error" not in outcome.notes
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")


def test_control_unknown_rule_not_caught_when_the_catalog_admits_it(tmp_path, monkeypatch):
    outcome = story(tmp_path, monkeypatch, unknown_rule=True, catalog_admits_unknown=True)   # the one input: catalog
    assert outcome.coverage_error is None and outcome.coverage_result["clean"] is True
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")


def test_control_unsupported_rule_not_caught_when_the_clean_check_is_relaxed(tmp_path, monkeypatch):
    outcome = story(tmp_path, monkeypatch, unsupported_rule=True, require_clean_coverage=False)   # harness check off
    assert outcome.coverage_result["clean"] is False                  # the evidence still says not clean
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")


@pytest.mark.parametrize("knobs", [
    pytest.param({"probe_head": "f" * 40}, id="head"),
    pytest.param({"probe_matrix_digest": "f" * 64}, id="matrix-digest"),
    pytest.param({"matrix_executor_drift": True}, id="executors"),
])
def test_control_role_table_drift_not_caught_when_validation_is_off(tmp_path, monkeypatch, knobs):
    monkeypatch.setattr(uc_role_table, "validate_role_table", lambda *args, **kwargs: [])   # the one check
    outcome = story(tmp_path, monkeypatch, **knobs)
    assert outcome.role_problems == []
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")


def test_control_secret_in_finding_leaks_when_the_redaction_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(router, "has_secret", lambda text: False)         # the one check: secret-shape detection
    outcome = story(tmp_path, monkeypatch, raw_findings=SECRET_FINDING)
    assert finding_rules(outcome) == [LEAKED_TOKEN]
    assert "abcd1234wxyz" in json.dumps(outcome.reports)


def test_control_secret_in_evidence_text_leaks_when_the_scan_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(fp, "_refuse_secrets", lambda *args, **kwargs: None)   # the one check: free-text scan
    outcome = story(tmp_path, monkeypatch, secret_reason=SECRET_TEXT)
    assert (outcome.stopped_at, outcome.final) == ("final_package", "READY")
    assert SECRET_TEXT in json.dumps(outcome.package_result.package)
