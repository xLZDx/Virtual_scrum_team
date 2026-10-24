"""E2 gate: default-deny verdict function, every rule of the gate docstring."""

from __future__ import annotations

import copy
import random

import pytest

from tools.vst import contracts as c
from tools.vst import gate

from .e1e4_helpers import (
    EPOCH,
    HEAD,
    HEAD2,
    KEY,
    TASK,
    happy_receipts,
    manifest,
    receipt,
    resign,
)

M = manifest()


def ev(receipts, *, m=None, head=HEAD, epoch=EPOCH, key=KEY, waiver=None):
    return gate.evaluate(M if m is None else m, receipts, head, epoch, key, waiver)


def reasons_text(d):
    return " | ".join(d["reasons"])


def hash_of(r):
    return c.receipt_sha256(r)


def valid_waiver(**kw):
    w = {
        "record_id": "W-1",
        "operator": "operator-ivan",
        "waived_slots": ["tests"],
        "waived_acceptance": ["AC-1"],
        "head": HEAD,
        "expires_epoch_or_date": "2026-12-31",
    }
    w.update(kw)
    return w


def not_run_tests():
    """tests slot NOT_RUN: unmet slot 'tests' and unmet acceptance AC-1."""
    return [receipt("TestRun", result="NOT_RUN"), receipt("StaticAnalysis"), receipt("IndependentReview")]


# ------------------------------------------------------------------ approve


def test_approve_only_when_fully_satisfied():
    rs = happy_receipts()
    d = ev(rs)
    assert d["verdict"] == "APPROVE"
    assert d["reasons"] == []
    assert d["acceptance_unmet"] == []
    assert d["unresolved_findings"] == []
    assert d["human_approvals"] == []
    assert d["waiver_record"] is None
    assert d["task_id"] == TASK and d["candidate_head"] == HEAD and d["epoch"] == EPOCH
    assert d["required_receipt_hashes"] == [hash_of(r) for r in rs]  # manifest slot order


def test_approve_independent_of_receipt_order():
    rs = happy_receipts()
    expected = ev(rs)
    for seed in range(5):
        shuffled = rs[:]
        random.Random(seed).shuffle(shuffled)
        assert ev(shuffled) == expected


def test_decision_is_deterministic_and_does_not_alias_inputs():
    rs = happy_receipts()
    first, second = ev(rs), ev(rs)
    assert first == second
    first["reasons"].append("mutated")
    first["required_receipt_hashes"].clear()
    assert ev(rs)["required_receipt_hashes"] != []


def test_extra_acceptance_ids_covered_by_receipts_do_not_block():
    rs = [
        receipt("TestRun", covered_acceptance=["AC-1", "AC-UNKNOWN"]),
        receipt("StaticAnalysis"),
        receipt("IndependentReview"),
    ]
    assert ev(rs)["verdict"] == "APPROVE"


# ------------------------------------------------- missing / unlisted receipts


@pytest.mark.parametrize(
    "slot,unmet",
    [("tests", ["AC-1"]), ("static", []), ("review", ["AC-2"])],
)
def test_missing_required_receipt_is_not_approval(slot, unmet):
    rs = [r for r in happy_receipts() if r["slot"] != slot]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert f"missing receipt for slot '{slot}'" in d["reasons"]
    assert d["acceptance_unmet"] == unmet
    assert len(d["required_receipt_hashes"]) == 2


def test_no_receipts_gives_modify_with_everything_unmet():
    d = ev([])
    assert d["verdict"] == "MODIFY"
    assert d["required_receipt_hashes"] == []
    assert d["acceptance_unmet"] == ["AC-1", "AC-2"]
    for slot in ("tests", "static", "review"):
        assert f"missing receipt for slot '{slot}'" in d["reasons"]


def test_unlisted_failing_receipt_blocks_approval_even_if_all_required_pass():
    extra = receipt("TestRun", slot="extra-slot", result="FAIL", skipped_test_ids=["x"])
    d = ev(happy_receipts() + [extra])
    assert d["verdict"] == "MODIFY"
    assert "unlisted receipt" in reasons_text(d)
    assert d["acceptance_unmet"] == []  # everything required is satisfied


def test_unlisted_passing_receipt_also_blocks_approval():
    d = ev(happy_receipts() + [receipt("TestRun", slot="extra-slot")])
    assert d["verdict"] == "MODIFY"
    assert "unlisted receipt" in reasons_text(d)


def test_receipt_type_mismatch_is_hard_and_slot_stays_unsatisfied():
    wrong = receipt("Documentation", slot="tests")
    rs = [wrong] + [r for r in happy_receipts() if r["slot"] != "tests"]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert "receipt type mismatch" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]
    assert d["acceptance_unmet"] == ["AC-1"]


def test_receipt_of_another_task_is_rejected_not_counted():
    other = receipt("TestRun", task_id="OTHER")
    rs = [other] + [r for r in happy_receipts() if r["slot"] != "tests"]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"  # not NO_GO: it is not one of this task's receipts
    assert "belongs to another task" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_receipt_of_another_task_added_to_complete_set_blocks_approval():
    d = ev(happy_receipts() + [receipt("TestRun", task_id="OTHER")])
    assert d["verdict"] == "MODIFY"
    assert "belongs to another task" in reasons_text(d)


def test_malformed_receipt_gives_hard_reason_and_is_excluded():
    bad = receipt("TestRun")
    bad["surprise"] = 1
    rs = [bad, receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert "invalid" in reasons_text(d) and "surprise" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_non_dict_receipt_item_does_not_raise():
    d = ev(happy_receipts() + [None, "x", 3])
    assert d["verdict"] == "MODIFY"
    assert reasons_text(d).count("invalid") == 3


# --------------------------------------------------------------- staleness


def test_stale_head_one_receipt_is_excluded_and_blocks():
    stale = receipt("TestRun", candidate_head=HEAD2)
    rs = [stale, receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert "stale head" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_stale_epoch_one_receipt_is_excluded_and_blocks():
    stale = receipt("TestRun", epoch=EPOCH - 1)
    rs = [stale, receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert "stale epoch" in reasons_text(d)


def test_replay_of_valid_set_against_other_head_is_no_go():
    d = ev(happy_receipts(), head=HEAD2)
    assert d["verdict"] == "NO_GO"
    assert "stale head" in reasons_text(d)
    assert "all receipts for this task are stale" in reasons_text(d)
    assert d["candidate_head"] == HEAD2


def test_replay_of_valid_set_against_newer_epoch_is_no_go():
    d = ev(happy_receipts(), epoch=EPOCH + 1)
    assert d["verdict"] == "NO_GO"
    assert "stale epoch" in reasons_text(d)


def test_replay_against_another_task_manifest_is_not_approval():
    d = ev(happy_receipts(), m=manifest(task_id="OTHER"))
    assert d["verdict"] == "MODIFY"
    assert reasons_text(d).count("belongs to another task") == 3


def test_stale_plus_wrong_signature_all_own_receipts_still_no_go():
    stale_unsigned = receipt("TestRun", candidate_head=HEAD2)
    stale_unsigned["signature"] = "0" * 64
    d = ev([stale_unsigned])
    assert d["verdict"] == "NO_GO"


# ------------------------------------------------------ signature / derived


def test_forged_unsigned_receipt_rejected():
    forged = receipt("TestRun")
    forged["signature"] = "0" * 64
    rs = [forged, receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert "invalid signature" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_signature_by_wrong_key_rejected():
    rs = [receipt("TestRun", key=b"another-key"), receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] != "APPROVE"
    assert "invalid signature" in reasons_text(d)


@pytest.mark.parametrize(
    "field,value",
    [
        ("runner_id", "attacker"),
        ("covered_acceptance", ["AC-1", "AC-2"]),
        ("created_at", "2030-01-01"),
        ("commands", [{"argv": ["pytest", "-q", "--forged"], "exit_code": 0}]),
    ],
)
def test_post_signing_tamper_rejected(field, value):
    r = receipt("TestRun")
    assert r[field] != value
    r[field] = value
    d = ev([r, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "invalid signature" in reasons_text(d)


def test_result_not_matching_derived_rejected_even_with_valid_signature():
    # Signed PASS although a skipped test exists: derive says FAIL.
    lying = receipt("TestRun", result="PASS", skipped_test_ids=["t3"])
    d = ev([lying, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "does not match derived result FAIL" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"executed_test_ids": ["t1"]},
        {"commands": [{"argv": ["x"], "exit_code": 1}]},
        {"xfail_test_ids": ["t2"]},
    ],
)
def test_testrun_claiming_pass_without_evidence_rejected(overrides):
    lying = receipt("TestRun", result="PASS", **overrides)
    d = ev([lying, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "does not match derived result" in reasons_text(d)


def test_static_partial_coverage_claiming_pass_rejected():
    lying = receipt("StaticAnalysis", result="PASS", coverage="PARTIAL")
    rs = [receipt("TestRun"), lying, receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert "does not match derived result INCONCLUSIVE" in reasons_text(d)


def test_static_partial_honest_inconclusive_is_unmet_slot():
    honest = receipt("StaticAnalysis", coverage="PARTIAL")
    assert honest["result"] == "INCONCLUSIVE"
    d = ev([receipt("TestRun"), honest, receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "slot 'static' latest attempt 1 result INCONCLUSIVE" in d["reasons"]


# ------------------------------------------------------------- attempt chain


def _retry_pair(first_result="FAIL"):
    first = receipt("TestRun", attempt=1, result=first_result, skipped_test_ids=["t3"] if first_result == "FAIL" else [])
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first))
    return first, second


def test_retry_after_fail_is_approved_but_failure_is_retained():
    first, second = _retry_pair("FAIL")
    assert first["result"] == "FAIL"
    rs = [first, second, receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "APPROVE"
    assert d["unresolved_findings"] == ["earlier failure retained: slot 'tests' attempt 1 result FAIL"]
    assert hash_of(second) in d["required_receipt_hashes"]
    assert hash_of(first) not in d["required_receipt_hashes"]


@pytest.mark.parametrize("first_result", ["FAIL", "NOT_RUN", "BLOCKED", "INCONCLUSIVE"])
def test_every_non_pass_earlier_attempt_is_retained(first_result):
    extra = {"skipped_test_ids": ["t3"]} if first_result == "FAIL" else {}
    first = receipt("TestRun", attempt=1, result=first_result, **extra)
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first))
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "APPROVE"
    assert d["unresolved_findings"] == [
        f"earlier failure retained: slot 'tests' attempt 1 result {first_result}"
    ]


def test_earlier_pass_is_not_listed_as_finding():
    first = receipt("TestRun", attempt=1)
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first))
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "APPROVE"
    assert d["unresolved_findings"] == []


def test_later_failure_overrides_earlier_pass():
    first = receipt("TestRun", attempt=1)
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first), skipped_test_ids=["t3"])
    assert second["result"] == "FAIL"
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "slot 'tests' latest attempt 2 result FAIL" in d["reasons"]
    assert d["acceptance_unmet"] == ["AC-1"]  # earlier PASS coverage must not count


def test_three_attempt_chain_valid():
    a1 = receipt("TestRun", attempt=1, result="BLOCKED")
    a2 = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(a1), result="INCONCLUSIVE")
    a3 = receipt("TestRun", attempt=3, prev_receipt_sha256=hash_of(a2))
    d = ev([a3, a1, a2, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "APPROVE"
    assert len(d["unresolved_findings"]) == 2


def test_attempt_chain_wrong_prev_hash_is_hard_reason():
    first, _ = _retry_pair("FAIL")
    second = receipt("TestRun", attempt=2, prev_receipt_sha256="e" * 64)
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "attempt chain broken for slot 'tests'" in reasons_text(d)
    assert hash_of(second) not in d["required_receipt_hashes"]


def test_attempt_gap_is_hard_reason():
    a1 = receipt("TestRun", attempt=1, result="FAIL", skipped_test_ids=["t3"])
    a3 = receipt("TestRun", attempt=3, prev_receipt_sha256=hash_of(a1))
    d = ev([a1, a3, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "attempt chain broken for slot 'tests'" in reasons_text(d)


def test_chain_not_starting_at_one_is_hard_reason():
    a2 = receipt("TestRun", attempt=2, prev_receipt_sha256="e" * 64)
    d = ev([a2, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "attempt chain broken" in reasons_text(d)


def test_duplicate_attempt_number_is_hard_reason():
    a = receipt("TestRun", attempt=1)
    b = receipt("TestRun", attempt=1, receipt_id="r-other")
    d = ev([a, b, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "attempt chain broken" in reasons_text(d)


def test_replayed_identical_receipt_twice_is_hard_reason():
    a = receipt("TestRun")
    d = ev([a, copy.deepcopy(a), receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "attempt chain broken" in reasons_text(d)


def test_broken_chain_still_retains_earlier_failure():
    a1 = receipt("TestRun", attempt=1, result="FAIL", skipped_test_ids=["t3"])
    a3 = receipt("TestRun", attempt=3, prev_receipt_sha256=hash_of(a1))
    d = ev([a1, a3, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert any("attempt 1 result FAIL" in f for f in d["unresolved_findings"])


# ------------------------------------------------------ acceptance coverage


def test_acceptance_not_covered_blocks_approval():
    rs = [receipt("TestRun", covered_acceptance=[]), receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert d["acceptance_unmet"] == ["AC-1"]
    assert "acceptance not covered: 'AC-1'" in d["reasons"]


def test_acceptance_union_across_slots_counts():
    rs = [
        receipt("TestRun", covered_acceptance=["AC-1"]),
        receipt("StaticAnalysis", covered_acceptance=["AC-2"]),
        receipt("IndependentReview", covered_acceptance=[]),
    ]
    assert ev(rs)["verdict"] == "APPROVE"


def test_acceptance_from_non_pass_slot_does_not_count():
    rs = [
        receipt("TestRun", result="NOT_RUN", covered_acceptance=["AC-1", "AC-2"]),
        receipt("StaticAnalysis"),
        receipt("IndependentReview", covered_acceptance=[]),
    ]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert d["acceptance_unmet"] == ["AC-1", "AC-2"]


# ---------------------------------------------------- non-approving results


@pytest.mark.parametrize("result", ["NOT_RUN", "INCONCLUSIVE", "BLOCKED"])
def test_non_approving_slot_result_is_unmet_and_not_approve(result):
    rs = [receipt("TestRun", result=result), receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert f"slot 'tests' latest attempt 1 result {result}" in d["reasons"]
    assert d["acceptance_unmet"] == ["AC-1"]


@pytest.mark.parametrize("result", ["NOT_RUN", "INCONCLUSIVE", "BLOCKED"])
def test_non_approving_review_slot_is_not_approve(result):
    rs = [receipt("TestRun"), receipt("StaticAnalysis"), receipt("IndependentReview", result=result)]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert d["acceptance_unmet"] == ["AC-2"]


def test_supervisor_style_documentation_blocked_receipt_is_unmet():
    m = manifest(
        required_receipts=[{"slot": "doc", "receipt_type": "Documentation"}],
        acceptance=["AC-1"],
    )
    r = receipt("Documentation", result="BLOCKED", check_description="RETRY_EXHAUSTED")
    d = ev([r], m=m)
    assert d["verdict"] == "MODIFY"
    assert "slot 'doc' latest attempt 1 result BLOCKED" in d["reasons"]


# --------------------------------------------------------- reviewer == author


def test_reviewer_equal_author_claiming_pass_is_rejected():
    r = receipt("IndependentReview", result="PASS", reviewer_principal="same", author_principal="same")
    d = ev([receipt("TestRun"), receipt("StaticAnalysis"), r])
    assert d["verdict"] == "MODIFY"
    assert "does not match derived result FAIL" in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-2"]


def test_reviewer_equal_author_honest_fail_is_unmet():
    r = receipt("IndependentReview", reviewer_principal="same", author_principal="same")
    assert r["result"] == "FAIL"
    d = ev([receipt("TestRun"), receipt("StaticAnalysis"), r])
    assert d["verdict"] == "MODIFY"
    assert "slot 'review' latest attempt 1 result FAIL" in d["reasons"]


def test_review_signed_modify_is_not_approval():
    r = receipt("IndependentReview", signed_verdict="MODIFY")
    d = ev([receipt("TestRun"), receipt("StaticAnalysis"), r])
    assert d["verdict"] == "MODIFY"
    assert d["acceptance_unmet"] == ["AC-2"]


# ----------------------------------------------------------------- waivers


def test_valid_waiver_for_not_run_slot_gives_approved_with_waiver():
    d = ev(not_run_tests(), waiver=valid_waiver())
    assert d["verdict"] == "APPROVED_WITH_WAIVER"
    assert d["waiver_record"] == "W-1"
    assert d["human_approvals"] == ["operator-ivan"]
    assert d["acceptance_unmet"] == ["AC-1"]
    assert "slot 'tests' latest attempt 1 result NOT_RUN" in d["reasons"]


def test_not_run_without_waiver_is_never_approve():
    d = ev(not_run_tests())
    assert d["verdict"] == "MODIFY"
    assert d["waiver_record"] is None and d["human_approvals"] == []


def test_waiver_may_cover_more_than_needed():
    w = valid_waiver(waived_slots=["tests", "static"], waived_acceptance=["AC-1", "AC-2"])
    assert ev(not_run_tests(), waiver=w)["verdict"] == "APPROVED_WITH_WAIVER"


def test_waiver_for_missing_slot_receipt():
    rs = [r for r in happy_receipts() if r["slot"] != "tests"]
    d = ev(rs, waiver=valid_waiver())
    assert d["verdict"] == "APPROVED_WITH_WAIVER"


@pytest.mark.parametrize(
    "kw,fragment",
    [
        ({"head": HEAD2}, "waiver head != current head"),
        ({"waived_slots": []}, "slot 'tests' is not waived"),
        ({"waived_slots": ["static"]}, "slot 'tests' is not waived"),
        ({"waived_acceptance": []}, "acceptance 'AC-1' is not waived"),
        ({"waived_acceptance": ["AC-2"]}, "acceptance 'AC-1' is not waived"),
        ({"operator": ""}, "operator must be a non-empty string"),
        ({"operator": "  "}, "operator must be a non-empty string"),
        ({"record_id": ""}, "record_id must be a non-empty string"),
        ({"expires_epoch_or_date": ""}, "expires_epoch_or_date must be a non-empty string"),
        ({"waived_slots": "tests"}, "waived_slots must be a list of strings"),
        ({"waived_acceptance": [1]}, "waived_acceptance must be a list of strings"),
        ({"operator": None}, "operator must be a non-empty string"),
    ],
)
def test_invalid_waiver_leaves_modify(kw, fragment):
    d = ev(not_run_tests(), waiver=valid_waiver(**kw))
    assert d["verdict"] == "MODIFY"
    assert d["waiver_record"] is None
    assert d["human_approvals"] == []
    assert fragment in reasons_text(d)


@pytest.mark.parametrize("field", ["record_id", "operator", "waived_slots", "waived_acceptance", "head", "expires_epoch_or_date"])
def test_waiver_missing_field_rejected(field):
    w = valid_waiver()
    del w[field]
    d = ev(not_run_tests(), waiver=w)
    assert d["verdict"] == "MODIFY"
    assert f"missing field(s): {field}" in reasons_text(d)


def test_waiver_unknown_field_rejected():
    d = ev(not_run_tests(), waiver=valid_waiver(note="x"))
    assert d["verdict"] == "MODIFY"
    assert "unknown field(s): note" in reasons_text(d)


@pytest.mark.parametrize("bad", ["W-1", ["x"], 5, True])
def test_non_dict_waiver_rejected(bad):
    d = ev(not_run_tests(), waiver=bad)
    assert d["verdict"] == "MODIFY"
    assert "waiver rejected" in reasons_text(d)


def test_waiver_ignored_when_nothing_is_unmet():
    d = ev(happy_receipts(), waiver=valid_waiver())
    assert d["verdict"] == "APPROVE"
    assert d["waiver_record"] is None
    assert d["human_approvals"] == []


def test_waiver_cannot_cover_hard_reason():
    rs = not_run_tests() + [receipt("TestRun", slot="extra-slot")]  # unlisted -> hard
    d = ev(rs, waiver=valid_waiver())
    assert d["verdict"] == "MODIFY"
    assert d["waiver_record"] is None


def test_waiver_cannot_cover_forged_signature():
    forged = receipt("TestRun", result="NOT_RUN")
    forged["signature"] = "1" * 64
    d = ev([forged, receipt("StaticAnalysis"), receipt("IndependentReview")], waiver=valid_waiver())
    assert d["verdict"] == "MODIFY"


def test_waiver_cannot_cover_broken_chain():
    a1 = receipt("TestRun", attempt=1, result="NOT_RUN")
    a3 = receipt("TestRun", attempt=3, prev_receipt_sha256=hash_of(a1), result="NOT_RUN")
    d = ev([a1, a3, receipt("StaticAnalysis"), receipt("IndependentReview")], waiver=valid_waiver())
    assert d["verdict"] == "MODIFY"


def test_waiver_cannot_rescue_all_stale_no_go():
    d = ev(not_run_tests(), head=HEAD2, waiver=valid_waiver(head=HEAD2))
    assert d["verdict"] == "NO_GO"
    assert d["waiver_record"] is None


def test_waiver_for_other_head_does_not_approve_current_head():
    d = ev(not_run_tests(), waiver=valid_waiver(head=HEAD2))
    assert d["verdict"] != "APPROVED_WITH_WAIVER"


# --------------------------------------------------------------- NO_GO inputs


def test_invalid_manifest_is_no_go_with_echoed_task_id():
    bad = manifest(extra=1)
    d = ev(happy_receipts(), m=bad)
    assert d["verdict"] == "NO_GO"
    assert d["task_id"] == TASK
    assert "manifest invalid" in reasons_text(d)
    assert d["required_receipt_hashes"] == []


@pytest.mark.parametrize("bad", [None, "x", [], 5])
def test_non_dict_manifest_is_no_go_not_exception(bad):
    d = gate.evaluate(bad, happy_receipts(), HEAD, EPOCH, KEY)
    assert d["verdict"] == "NO_GO"
    assert d["task_id"] == ""


def test_manifest_with_zero_required_receipts_is_no_go():
    d = ev(happy_receipts(), m=manifest(required_receipts=[]))
    assert d["verdict"] == "NO_GO"


@pytest.mark.parametrize(
    "kwargs,fragment",
    [
        ({"head": "A" * 40}, "current_head"),
        ({"head": "a" * 39}, "current_head"),
        ({"head": None}, "current_head"),
        ({"epoch": 0}, "current_epoch"),
        ({"epoch": True}, "current_epoch"),
        ({"epoch": "2"}, "current_epoch"),
        ({"epoch": 2.0}, "current_epoch"),
        ({"key": b""}, "key"),
        ({"key": "text-key"}, "key"),
        ({"key": None}, "key"),
    ],
)
def test_bad_gate_inputs_are_no_go(kwargs, fragment):
    d = ev(happy_receipts(), **kwargs)
    assert d["verdict"] == "NO_GO"
    assert fragment in reasons_text(d)
    c.validate_gate_decision(d)


@pytest.mark.parametrize("bad", [None, (), "x", {}])
def test_receipts_not_a_list_is_no_go(bad):
    d = ev(bad)
    assert d["verdict"] == "NO_GO"
    assert "receipts: must be a list" in reasons_text(d)


def test_bytearray_key_accepted():
    assert ev(happy_receipts(), key=bytearray(KEY))["verdict"] == "APPROVE"


# --------------------------------------------------------------- invariants


def _bad_scenarios():
    first, second = _retry_pair("FAIL")
    forged = receipt("TestRun")
    forged["signature"] = "0" * 64
    gap = receipt("TestRun", attempt=3, prev_receipt_sha256=hash_of(first))
    rest = [receipt("StaticAnalysis"), receipt("IndependentReview")]
    return {
        "missing": [r for r in happy_receipts() if r["slot"] != "review"],
        "empty": [],
        "unlisted": happy_receipts() + [receipt("TestRun", slot="zz")],
        "stale_head": [receipt("TestRun", candidate_head=HEAD2)] + rest,
        "stale_epoch": [receipt("TestRun", epoch=EPOCH + 5)] + rest,
        "forged": [forged] + rest,
        "lying": [receipt("TestRun", result="PASS", skipped_test_ids=["q"])] + rest,
        "gap": [first, gap] + rest,
        "not_run": [receipt("TestRun", result="NOT_RUN")] + rest,
        "inconclusive": [receipt("TestRun", result="INCONCLUSIVE")] + rest,
        "blocked": [receipt("TestRun", result="BLOCKED")] + rest,
        "self_review": [receipt("TestRun"), receipt("StaticAnalysis"),
                        receipt("IndependentReview", reviewer_principal="s", author_principal="s")],
        "uncovered": [receipt("TestRun", covered_acceptance=[])] + rest,
        "other_task": happy_receipts() + [receipt("TestRun", task_id="X")],
        "type_mismatch": [receipt("Documentation", slot="tests")] + rest,
    }


@pytest.mark.parametrize("name", sorted(_bad_scenarios()))
def test_never_approve_when_any_hard_or_soft_reason_exists(name):
    rs = _bad_scenarios()[name]
    for waiver in (None, valid_waiver(waived_slots=["tests", "static", "review"],
                                      waived_acceptance=["AC-1", "AC-2"])):
        d = ev(rs, waiver=waiver)
        assert d["verdict"] != "APPROVE", name
        assert d["reasons"], name
        if d["verdict"] == "APPROVED_WITH_WAIVER":
            assert d["waiver_record"] == "W-1"
        else:
            assert d["waiver_record"] is None and d["human_approvals"] == []
        c.validate_gate_decision(d)


@pytest.mark.parametrize("name", ["unlisted", "stale_head", "stale_epoch", "forged", "lying",
                                  "gap", "other_task", "type_mismatch"])
def test_hard_reason_scenarios_are_never_waivable(name):
    w = valid_waiver(waived_slots=["tests", "static", "review"], waived_acceptance=["AC-1", "AC-2"])
    rs = _bad_scenarios()[name]
    assert ev(rs, waiver=w)["verdict"] in {"MODIFY", "NO_GO"}


def test_inputs_are_not_mutated_in_any_scenario():
    w = valid_waiver()
    snapshot_w = copy.deepcopy(w)
    m = manifest()
    snapshot_m = copy.deepcopy(m)
    for name, rs in _bad_scenarios().items():
        snap = copy.deepcopy(rs)
        gate.evaluate(m, rs, HEAD, EPOCH, KEY, w)
        assert rs == snap, name
    rs = happy_receipts()
    snap = copy.deepcopy(rs)
    gate.evaluate(m, rs, HEAD, EPOCH, KEY, w)
    assert rs == snap and m == snapshot_m and w == snapshot_w


def test_resigned_tamper_with_stolen_key_would_pass_only_with_valid_derived_result():
    # A receipt re-signed with the right key but a lying result is still rejected.
    r = receipt("TestRun", skipped_test_ids=["t9"])
    r["result"] = "PASS"
    r = resign(r)
    d = ev([r, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "does not match derived result" in reasons_text(d)


# ------------------------------------------------------ artifact_resolver


ART = "a" * 64


def _with_artifact(**kw):
    return [
        receipt("TestRun", artifact_digests={"out/report.txt": ART}, **kw),
        receipt("StaticAnalysis"),
        receipt("IndependentReview"),
    ]


def _ev_res(rs, resolver):
    return gate.evaluate(M, rs, HEAD, EPOCH, KEY, None, artifact_resolver=resolver)


def test_resolver_matching_digest_keeps_approve_and_receives_the_path():
    seen = []

    def resolver(path):
        seen.append(path)
        return ART

    d = _ev_res(_with_artifact(), resolver)
    assert d["verdict"] == "APPROVE"
    assert seen == ["out/report.txt"]


def test_resolver_mismatching_digest_is_hard_reason_and_receipt_invalid():
    d = _ev_res(_with_artifact(), lambda p: "b" * 64)
    assert d["verdict"] == "MODIFY"
    assert "digest mismatch" in reasons_text(d) and "out/report.txt" in reasons_text(d)
    assert "r-tests-1" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]
    assert d["acceptance_unmet"] == ["AC-1"]


def test_resolver_returning_none_is_rejected():
    d = _ev_res(_with_artifact(), lambda p: None)
    assert d["verdict"] == "MODIFY"
    assert "digest mismatch" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_raising_resolver_is_default_deny_not_an_exception():
    def boom(path):
        raise OSError("disk gone")

    d = _ev_res(_with_artifact(), boom)
    assert d["verdict"] == "MODIFY"
    assert "cannot be resolved" in reasons_text(d) and "OSError" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_no_resolver_means_artifacts_are_not_rechecked():
    d = gate.evaluate(M, _with_artifact(), HEAD, EPOCH, KEY)
    assert d["verdict"] == "APPROVE"
    assert _ev_res(_with_artifact(), None)["verdict"] == "APPROVE"


def test_resolver_not_called_for_receipts_without_artifacts_or_other_types():
    calls = []
    d = _ev_res(happy_receipts(), lambda p: calls.append(p) or "x")
    assert d["verdict"] == "APPROVE" and calls == []


def test_resolver_checks_every_artifact_of_the_receipt():
    rs = [
        receipt("TestRun", artifact_digests={"a": ART, "b": "c" * 64}),
        receipt("StaticAnalysis"),
        receipt("IndependentReview"),
    ]
    d = _ev_res(rs, lambda p: {"a": ART, "b": "d" * 64}[p])
    assert d["verdict"] == "MODIFY" and "'b'" in reasons_text(d)


def test_resolver_mismatch_is_not_waivable():
    d = gate.evaluate(M, _with_artifact(), HEAD, EPOCH, KEY, valid_waiver(), artifact_resolver=lambda p: "b" * 64)
    assert d["verdict"] == "MODIFY"


def test_resolver_not_consulted_for_receipt_already_invalid():
    calls = []
    bad = receipt("TestRun", artifact_digests={"a": ART})
    bad["signature"] = "0" * 64
    d = _ev_res([bad, receipt("StaticAnalysis"), receipt("IndependentReview")], lambda p: calls.append(p) or ART)
    assert "invalid signature" in reasons_text(d) and calls == []


def test_zero_digest_receipt_claiming_pass_is_rejected_as_derived_mismatch():
    lying = receipt("TestRun", result="PASS", artifact_digests={"gone": "0" * 64})
    d = ev([lying, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "does not match derived result FAIL" in reasons_text(d)
