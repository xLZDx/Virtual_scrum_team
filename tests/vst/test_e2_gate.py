"""E2 gate: default-deny verdict function, every rule of the gate docstring.

Remediation A: manifest-bound receipts, three separated keys, epoch history,
supervisor slot, manifest-derived acceptance, default-deny artifacts and an
operator-signed waiver.
"""

from __future__ import annotations

import copy
import random

import pytest

from tools.vst import contracts as c
from tools.vst import gate, signing

from .e1e4_helpers import (
    EPOCH,
    HEAD,
    HEAD2,
    KEY,
    MANIFEST_SHA,
    OPERATOR_KEY,
    SUPERVISOR_KEY,
    TASK,
    WRONG_KEY,
    bound,
    doc_manifest,
    happy_receipts,
    manifest,
    mhash,
    receipt,
    resign,
    signed_waiver,
    supervisor_receipt,
    unsigned_receipt,
)

M = manifest()
ART = "a" * 64
ALL_SLOTS = ["tests", "static", "review"]
ALL_ACCEPTANCE = ["AC-1", "AC-2"]


def ev(
    receipts,
    *,
    m=None,
    head=HEAD,
    epoch=EPOCH,
    key=KEY,
    supervisor_key=SUPERVISOR_KEY,
    operator_key=OPERATOR_KEY,
    waiver=None,
    resolver=None,
):
    return gate.evaluate(
        M if m is None else m,
        receipts,
        head,
        epoch,
        key,
        supervisor_key=supervisor_key,
        operator_key=operator_key,
        waiver=waiver,
        artifact_resolver=resolver,
    )


def reasons_text(d):
    return " | ".join(d["reasons"])


def hash_of(r):
    return c.receipt_sha256(r)


def valid_waiver(**kw):
    """Operator-signed waiver for slot 'tests' / AC-1 bound to M, HEAD, EPOCH."""
    return signed_waiver(**kw)


def broad_waiver(**kw):
    base = {"waived_slots": list(ALL_SLOTS), "waived_acceptance": list(ALL_ACCEPTANCE)}
    base.update(kw)
    return signed_waiver(**base)


def not_run_tests():
    """tests slot NOT_RUN: unmet slot 'tests' and unmet acceptance AC-1."""
    return [receipt("TestRun", result="NOT_RUN"), receipt("StaticAnalysis"), receipt("IndependentReview")]


def rest_receipts():
    return [receipt("StaticAnalysis"), receipt("IndependentReview")]


def bound_happy(m):
    return [bound(m, "TestRun"), bound(m, "StaticAnalysis"), bound(m, "IndependentReview")]


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


def test_gate_signature_requires_keyword_supervisor_key():
    with pytest.raises(TypeError):
        gate.evaluate(M, happy_receipts(), HEAD, EPOCH, KEY)
    with pytest.raises(TypeError):  # operator_key / waiver / resolver are keyword-only
        gate.evaluate(M, happy_receipts(), HEAD, EPOCH, KEY, SUPERVISOR_KEY)


def test_testrun_claiming_acceptance_outside_the_manifest_is_a_hard_reason():
    rs = [
        receipt("TestRun", covered_acceptance=["AC-1", "AC-UNKNOWN"]),
        receipt("StaticAnalysis"),
        receipt("IndependentReview"),
    ]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert "covered_acceptance contains ids outside the manifest" in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-1"]  # the offending slot is unmet
    assert ev(rs, waiver=broad_waiver())["verdict"] == "MODIFY"  # hard: not waivable


def test_unknown_acceptance_ids_from_static_and_review_are_ignored_not_blocking():
    rs = [
        receipt("TestRun"),
        receipt("StaticAnalysis", covered_acceptance=["AC-UNKNOWN"]),
        receipt("IndependentReview", covered_acceptance=["AC-2", "AC-UNKNOWN"]),
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
    for slot in ALL_SLOTS:
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


def test_receipt_without_manifest_sha256_field_is_invalid():
    bad = receipt("TestRun")
    del bad["manifest_sha256"]
    d = ev([bad, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "manifest_sha256" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_non_dict_receipt_item_does_not_raise():
    d = ev(happy_receipts() + [None, "x", 3])
    assert d["verdict"] == "MODIFY"
    assert reasons_text(d).count("invalid") == 3


# ------------------------------------------- manifest / role binding (swap)


def test_receipts_bound_to_another_manifest_of_the_same_task_are_rejected():
    # Same task id, but the manifest was changed (extra acceptance id): the old
    # receipts must not carry over, even though they are validly signed.
    m2 = manifest(acceptance=["AC-1", "AC-2", "AC-3"])
    assert m2["task_id"] == M["task_id"] and mhash(m2) != MANIFEST_SHA
    d = ev(happy_receipts(), m=m2)
    assert d["verdict"] == "MODIFY"  # own receipts, not all stale-by-head: not NO_GO
    assert reasons_text(d).count("manifest_sha256 does not match the manifest") == 3
    assert d["required_receipt_hashes"] == []
    assert d["acceptance_unmet"] == ["AC-1", "AC-2", "AC-3"]


def test_weakened_manifest_swap_cannot_reuse_receipts_of_the_strict_manifest():
    weak = manifest(
        required_receipts=[
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "review", "receipt_type": "IndependentReview"},
        ],
        required_rules=[],
    )
    d = ev(happy_receipts(), m=weak)
    assert d["verdict"] != "APPROVE"
    assert "manifest_sha256 does not match the manifest" in reasons_text(d)


def test_receipt_with_swapped_manifest_hash_but_old_signature_is_invalid():
    swapped = receipt("TestRun")
    swapped["manifest_sha256"] = mhash(manifest(model_policy="other"))
    d = ev([swapped, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "manifest_sha256 does not match the manifest" in reasons_text(d)


def test_receipts_resigned_for_the_new_manifest_are_accepted():
    m2 = manifest(acceptance=["AC-1", "AC-2", "AC-3"])
    rs = bound_happy(m2)
    d = ev(rs, m=m2)
    assert d["verdict"] == "MODIFY"  # AC-3 has no covering test/review
    assert "manifest_sha256 does not match" not in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-3"]


def test_receipt_role_sha256_must_equal_manifest_role():
    r = receipt("TestRun", role_sha256="e" * 64)
    d = ev([r, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "role_sha256 does not match the manifest" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_replay_against_another_task_manifest_is_not_approval():
    d = ev(happy_receipts(), m=manifest(task_id="OTHER"))
    assert d["verdict"] == "MODIFY"
    assert reasons_text(d).count("belongs to another task") == 3


# --------------------------------------------------------------- staleness


def test_stale_head_one_receipt_is_a_hard_reason_and_the_slot_is_unmet():
    stale = receipt("TestRun", candidate_head=HEAD2)
    rs = [stale, receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"  # 1 of 3 deciding receipts stale: not NO_GO
    assert f"receipt {stale['receipt_id']} stale head" in reasons_text(d)
    # the stale receipt is in the chain (not "missing"), but it cannot decide the slot
    assert "missing receipt for slot 'tests'" not in d["reasons"]
    assert any(r.startswith("slot 'tests' needs an attempt at the current head") for r in d["reasons"])
    assert d["acceptance_unmet"] == ["AC-1"]
    assert hash_of(stale) not in d["required_receipt_hashes"]
    assert len(d["required_receipt_hashes"]) == 2


def test_replay_of_valid_set_against_other_head_is_no_go():
    d = ev(happy_receipts(), head=HEAD2)
    assert d["verdict"] == "NO_GO"
    assert "stale head" in reasons_text(d)
    assert "all deciding receipts for this task are stale" in reasons_text(d)
    assert d["candidate_head"] == HEAD2


def test_stale_plus_wrong_signature_is_not_a_deciding_receipt_so_not_no_go():
    # The signature check runs before the head check: a forged receipt is dropped,
    # so it is neither deciding nor stale. Only 'invalid signature' is reported.
    stale_unsigned = receipt("TestRun", candidate_head=HEAD2)
    stale_unsigned["signature"] = "0" * 64
    d = ev([stale_unsigned])
    assert d["verdict"] == "MODIFY"
    assert "invalid signature" in reasons_text(d)
    assert "stale head" not in reasons_text(d)
    assert "all deciding receipts" not in reasons_text(d)


# ------------------------------------------------------ epochs are history


def test_older_epoch_receipt_is_history_not_a_hard_reason_and_slot_needs_current_attempt():
    old = receipt("TestRun", epoch=EPOCH - 1)
    d = ev([old, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "stale epoch" not in reasons_text(d) and "future epoch" not in reasons_text(d)
    assert "slot 'tests' needs a current-epoch attempt" in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-1"]  # an old PASS gives no current coverage


def test_all_receipts_from_older_epoch_are_not_no_go_but_everything_is_unmet():
    rs = [
        receipt("TestRun", epoch=EPOCH - 1),
        receipt("StaticAnalysis", epoch=EPOCH - 1),
        receipt("IndependentReview", epoch=EPOCH - 1),
    ]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert reasons_text(d).count("needs a current-epoch attempt") == 3
    assert d["acceptance_unmet"] == ["AC-1", "AC-2"]


def test_replay_of_valid_set_against_newer_epoch_needs_fresh_attempts_not_no_go():
    d = ev(happy_receipts(), epoch=EPOCH + 1)
    assert d["verdict"] == "MODIFY"
    assert reasons_text(d).count("needs a current-epoch attempt") == 3
    assert d["acceptance_unmet"] == ["AC-1", "AC-2"]
    assert d["epoch"] == EPOCH + 1


def test_future_epoch_receipt_is_a_hard_reason_and_excluded():
    future = receipt("TestRun", epoch=EPOCH + 1)
    d = ev([future, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "future epoch" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_replay_against_older_gate_epoch_is_no_go_with_future_epoch_reason():
    d = ev(happy_receipts(), epoch=EPOCH - 1)
    assert d["verdict"] == "NO_GO"
    assert "future epoch" in reasons_text(d)
    assert "all deciding receipts for this task are stale" in reasons_text(d)


def test_failure_in_older_epoch_is_retained_when_current_epoch_retries_and_passes():
    first = receipt("TestRun", attempt=1, epoch=EPOCH - 1, skipped_test_ids=["t3"])
    assert first["result"] == "FAIL"
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first))
    d = ev([second, first, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "APPROVE"
    assert d["unresolved_findings"] == ["earlier failure retained: tests attempt 1 FAIL"]
    assert hash_of(second) in d["required_receipt_hashes"]


def test_cross_epoch_chain_with_wrong_prev_hash_is_broken():
    first = receipt("TestRun", attempt=1, epoch=EPOCH - 1, skipped_test_ids=["t3"])
    second = receipt("TestRun", attempt=2, prev_receipt_sha256="e" * 64)
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "attempt chain broken for slot 'tests'" in reasons_text(d)


@pytest.mark.parametrize("fresh_first", [False, True])
def test_new_epoch_cannot_discard_history_by_restarting_the_chain(fresh_first):
    # An old-epoch FAIL as attempt 1 and a "fresh" current-epoch attempt 1: a
    # takeover trying to hide the failure. Duplicate attempt numbers = hard.
    old_fail = receipt("TestRun", attempt=1, epoch=EPOCH - 1, skipped_test_ids=["t3"])
    fresh = receipt("TestRun", attempt=1, epoch=EPOCH, receipt_id="r-fresh")
    pair = [fresh, old_fail] if fresh_first else [old_fail, fresh]
    d = ev(pair + rest_receipts())
    assert d["verdict"] == "MODIFY"
    assert "attempt chain broken for slot 'tests'" in reasons_text(d)
    assert ev(pair + rest_receipts(), waiver=broad_waiver())["verdict"] == "MODIFY"


def test_latest_attempt_from_older_epoch_cannot_approve_even_after_current_epoch_failure_was_dropped():
    old_pass = receipt("TestRun", attempt=1, epoch=EPOCH - 1)
    d = ev([old_pass, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] != "APPROVE"
    assert d["acceptance_unmet"] == ["AC-1"]


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
    rs = [receipt("TestRun", key=WRONG_KEY), receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] != "APPROVE"
    assert "invalid signature" in reasons_text(d)


@pytest.mark.parametrize("other_key", [SUPERVISOR_KEY, OPERATOR_KEY])
def test_worker_slot_receipt_signed_with_supervisor_or_operator_key_rejected(other_key):
    rs = [receipt("TestRun", key=other_key), receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert "invalid signature" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_receipt_signed_under_the_waiver_label_is_rejected():
    r = unsigned_receipt("TestRun")
    r["signature"] = signing.sign(r, KEY, signing.WAIVER_LABEL)
    d = ev([r, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "invalid signature" in reasons_text(d)


def test_receipt_signed_without_any_label_domain_is_rejected():
    # Raw HMAC over canonical bytes (the pre-remediation scheme) must not verify.
    import hashlib
    import hmac

    r = unsigned_receipt("TestRun")
    r["signature"] = hmac.new(KEY, c.canonical_bytes(r), hashlib.sha256).hexdigest()
    d = ev([r, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "invalid signature" in reasons_text(d)


@pytest.mark.parametrize(
    "field,value",
    [
        ("runner_id", "attacker"),
        ("covered_acceptance", ["AC-1", "AC-2"]),
        ("created_at", "2030-01-01"),
        ("commands", [{"argv": ["pytest", "-q", "--forged"], "exit_code": 0}]),
        ("manifest_sha256", "f" * 64),
    ],
)
def test_post_signing_tamper_rejected(field, value):
    r = receipt("TestRun")
    assert r[field] != value
    r[field] = value
    d = ev([r, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "missing receipt for slot 'tests'" in d["reasons"]


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
        {"commands": [{"argv": ["pytest", "-q"], "exit_code": 1}]},
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
    assert d["unresolved_findings"] == ["earlier failure retained: tests attempt 1 FAIL"]
    assert hash_of(second) in d["required_receipt_hashes"]
    assert hash_of(first) not in d["required_receipt_hashes"]


@pytest.mark.parametrize("first_result", ["FAIL", "NOT_RUN", "BLOCKED", "INCONCLUSIVE"])
def test_every_non_pass_earlier_attempt_is_retained(first_result):
    extra = {"skipped_test_ids": ["t3"]} if first_result == "FAIL" else {}
    first = receipt("TestRun", attempt=1, result=first_result, **extra)
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first))
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "APPROVE"
    assert d["unresolved_findings"] == [f"earlier failure retained: tests attempt 1 {first_result}"]


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
    assert any("tests attempt 1 FAIL" in f for f in d["unresolved_findings"])


# ------------------------------------------------------ acceptance coverage


def test_acceptance_not_covered_by_review_blocks_approval():
    rs = [receipt("TestRun"), receipt("StaticAnalysis"), receipt("IndependentReview", covered_acceptance=[])]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert d["acceptance_unmet"] == ["AC-2"]
    assert "acceptance not covered: 'AC-2'" in d["reasons"]


def test_testrun_acceptance_comes_from_the_manifest_not_from_the_receipt_claim():
    # The worker claims nothing, yet the manifest says t1/t2 prove AC-1.
    rs = [receipt("TestRun", covered_acceptance=[]), receipt("StaticAnalysis"), receipt("IndependentReview")]
    assert ev(rs)["verdict"] == "APPROVE"


def test_worker_claimed_acceptance_beyond_the_manifest_mapping_creates_no_coverage():
    # The worker claims AC-2 too (a valid manifest id), but required_tests map
    # only AC-1 to this slot; AC-2 must still come from review/static.
    rs = [
        receipt("TestRun", covered_acceptance=["AC-1", "AC-2"]),
        receipt("StaticAnalysis"),
        receipt("IndependentReview", covered_acceptance=[]),
    ]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert d["acceptance_unmet"] == ["AC-2"]


def test_testrun_acceptance_follows_per_test_mapping_of_the_manifest():
    m2 = manifest(
        required_tests=[
            {"slot": "tests", "test_id": "t1", "acceptance": ["AC-1"]},
            {"slot": "tests", "test_id": "t2", "acceptance": ["AC-2"]},
        ]
    )
    rs = [
        bound(m2, "TestRun"),
        bound(m2, "StaticAnalysis"),
        bound(m2, "IndependentReview", covered_acceptance=[]),
    ]
    d = ev(rs, m=m2)
    assert d["verdict"] == "APPROVE"  # AC-2 proven by test t2, not by the review


def test_acceptance_union_across_slots_counts():
    rs = [
        receipt("TestRun"),
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


def test_documentation_receipt_never_contributes_acceptance():
    dm = doc_manifest()
    rs = [
        bound(dm, "TestRun"),
        bound(dm, "Documentation", covered_acceptance=["AC-2"]),
        bound(dm, "IndependentReview", covered_acceptance=[]),
    ]
    d = ev(rs, m=dm)
    assert d["verdict"] == "MODIFY"
    assert d["acceptance_unmet"] == ["AC-2"]


# ------------------------------------------- TestRun: commands, expected ids


@pytest.mark.parametrize(
    "argv",
    [
        ["pytest", "-q", "--forged"],
        ["pytest"],
        ["PYTEST", "-q"],
        ["rm", "-rf", "/"],
        ["true"],
    ],
)
def test_command_outside_allowed_commands_is_hard_even_when_signed_and_passing(argv):
    r = receipt("TestRun", commands=[{"argv": argv, "exit_code": 0}])
    assert r["result"] == "PASS"
    d = ev([r, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "is not in allowed_commands" in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-1"]
    assert ev([r, *rest_receipts()], waiver=broad_waiver())["verdict"] == "MODIFY"


def test_one_disallowed_command_among_allowed_ones_is_hard():
    r = receipt(
        "TestRun",
        commands=[{"argv": ["pytest", "-q"], "exit_code": 0}, {"argv": ["curl", "evil"], "exit_code": 0}],
    )
    d = ev([r, *rest_receipts()])
    assert d["verdict"] == "MODIFY"
    assert "['curl', 'evil'] is not in allowed_commands" in reasons_text(d)


def test_multiple_allowed_commands_of_the_slot_are_all_accepted():
    m2 = manifest(
        allowed_commands=[
            {"slot": "tests", "argv": ["pytest", "-q"]},
            {"slot": "tests", "argv": ["ruff", "check"]},
        ]
    )
    r = bound(
        m2,
        "TestRun",
        commands=[{"argv": ["pytest", "-q"], "exit_code": 0}, {"argv": ["ruff", "check"], "exit_code": 0}],
    )
    d = ev([r, bound(m2, "StaticAnalysis"), bound(m2, "IndependentReview")], m=m2)
    assert d["verdict"] == "APPROVE"


def test_command_allowed_only_for_a_different_slot_is_not_accepted():
    m2 = manifest(
        required_receipts=[
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "tests2", "receipt_type": "TestRun"},
            {"slot": "review", "receipt_type": "IndependentReview"},
        ],
        required_tests=[
            {"slot": "tests", "test_id": "t1", "acceptance": ["AC-1"]},
            {"slot": "tests2", "test_id": "u1", "acceptance": ["AC-2"]},
        ],
        allowed_commands=[
            {"slot": "tests", "argv": ["pytest", "-q"]},
            {"slot": "tests2", "argv": ["other-runner"]},
        ],
        required_rules=[],
    )
    ok1 = bound(m2, "TestRun", expected_test_ids=["t1"], executed_test_ids=["t1"])
    # tests2 uses the command that is only allowed for 'tests'
    bad2 = bound(
        m2, "TestRun", slot="tests2", expected_test_ids=["u1"], executed_test_ids=["u1"],
        commands=[{"argv": ["pytest", "-q"], "exit_code": 0}],
    )
    d = ev([ok1, bad2, bound(m2, "IndependentReview", covered_acceptance=[])], m=m2)
    assert d["verdict"] == "MODIFY"
    assert "slot 'tests2': command ['pytest', '-q'] is not in allowed_commands" in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-2"]


@pytest.mark.parametrize(
    "ids",
    [["t1"], ["t1", "t2", "t3"], ["t1", "other"], ["t3"]],
)
def test_expected_test_ids_must_equal_the_manifest_required_tests(ids):
    # The worker redefines the suite; its own derivation says PASS, the gate disagrees.
    r = receipt("TestRun", expected_test_ids=ids, executed_test_ids=ids)
    assert r["result"] == "PASS"
    d = ev([r, *rest_receipts()])
    assert d["verdict"] == "MODIFY"
    assert "expected_test_ids differ from the manifest required tests" in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-1"]
    assert ev([r, *rest_receipts()], waiver=broad_waiver())["verdict"] == "MODIFY"


def test_expected_test_id_order_does_not_matter():
    r = receipt("TestRun", expected_test_ids=["t2", "t1"], executed_test_ids=["t1", "t2"])
    assert ev([r, *rest_receipts()])["verdict"] == "APPROVE"


def test_check_is_made_on_the_latest_attempt_only():
    bad_first = receipt(
        "TestRun", attempt=1, commands=[{"argv": ["curl", "x"], "exit_code": 1}]
    )
    good_second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(bad_first))
    d = ev([bad_first, good_second, *rest_receipts()])
    assert d["verdict"] == "APPROVE"
    assert "allowed_commands" not in reasons_text(d)


# ----------------------------------------------------- StaticAnalysis rules


def test_static_full_coverage_without_covered_rules_cannot_pass():
    lying = receipt("StaticAnalysis", result="PASS", covered_rules=[])
    d = ev([receipt("TestRun"), lying, receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "does not match derived result INCONCLUSIVE" in reasons_text(d)


def test_static_honest_vacuous_receipt_is_an_unmet_slot():
    honest = receipt("StaticAnalysis", covered_rules=[])
    assert honest["result"] == "INCONCLUSIVE"
    d = ev([receipt("TestRun"), honest, receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "slot 'static' latest attempt 1 result INCONCLUSIVE" in d["reasons"]


def _rules_manifest():
    return manifest(
        required_rules=[
            {"slot": "static", "rule_id": "R1"},
            {"slot": "static", "rule_id": "R2"},
        ]
    )


def test_static_missing_a_required_rule_is_an_unmet_slot_and_waivable():
    m2 = _rules_manifest()
    rs = [bound(m2, "TestRun"), bound(m2, "StaticAnalysis", covered_rules=["R1"]), bound(m2, "IndependentReview")]
    d = ev(rs, m=m2)
    assert d["verdict"] == "MODIFY"
    assert "slot 'static': required rules not covered: R2" in reasons_text(d)
    assert d["acceptance_unmet"] == []
    w = signed_waiver(manifest_sha256=mhash(m2), waived_slots=["static"], waived_acceptance=[])
    dw = ev(rs, m=m2, waiver=w)
    assert dw["verdict"] == "APPROVED_WITH_WAIVER"
    assert dw["waiver_record"] == "W-1"


def test_static_covering_all_required_rules_plus_extra_is_accepted():
    m2 = _rules_manifest()
    rs = [
        bound(m2, "TestRun"),
        bound(m2, "StaticAnalysis", covered_rules=["R3", "R2", "R1"]),
        bound(m2, "IndependentReview"),
    ]
    assert ev(rs, m=m2)["verdict"] == "APPROVE"


def test_static_covering_only_unrelated_rules_is_unmet():
    rs = [receipt("TestRun"), receipt("StaticAnalysis", covered_rules=["R9"]), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert "required rules not covered: R1" in reasons_text(d)


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


def test_documentation_slot_blocked_receipt_is_unmet_not_a_terminal_marker():
    dm = doc_manifest()
    rs = [
        bound(dm, "TestRun"),
        bound(dm, "Documentation", result="BLOCKED", check_description="RETRY_EXHAUSTED"),
        bound(dm, "IndependentReview"),
    ]
    d = ev(rs, m=dm)
    assert d["verdict"] == "MODIFY"
    assert "slot 'doc' latest attempt 1 result BLOCKED" in d["reasons"]
    assert "terminal marker" not in reasons_text(d)  # only the supervisor slot carries markers
    assert d["acceptance_unmet"] == []


def test_documentation_slot_pass_is_required_but_adds_no_coverage():
    dm = doc_manifest()
    rs = [bound(dm, "TestRun"), bound(dm, "Documentation"), bound(dm, "IndependentReview")]
    assert ev(rs, m=dm)["verdict"] == "APPROVE"


# --------------------------------------------- reviewer / author principals


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


def test_review_author_must_match_the_manifest_author():
    r = receipt("IndependentReview", author_principal="mallory")
    assert r["result"] == "PASS"  # distinct from the reviewer, so self-derivation passes
    d = ev([receipt("TestRun"), receipt("StaticAnalysis"), r])
    assert d["verdict"] == "MODIFY"
    assert "review author_principal does not match the manifest" in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-2"]
    assert ev([receipt("TestRun"), receipt("StaticAnalysis"), r], waiver=broad_waiver())["verdict"] == "MODIFY"


def test_author_cannot_review_own_work_by_lying_about_author_name():
    # The real author (manifest: 'author-y') reviews under a spelling variant
    # and the receipt names somebody else as the author.
    r = receipt("IndependentReview", reviewer_principal="Author-Y ", author_principal="someone-else")
    assert r["result"] == "PASS"
    d = ev([receipt("TestRun"), receipt("StaticAnalysis"), r])
    assert d["verdict"] == "MODIFY"
    assert "review author_principal does not match the manifest" in reasons_text(d)


def test_normalized_principal_spoof_reviewer_variant_of_author_claiming_pass_is_rejected():
    r = receipt("IndependentReview", result="PASS", reviewer_principal="Author-Y ", author_principal="author-y")
    d = ev([receipt("TestRun"), receipt("StaticAnalysis"), r])
    assert d["verdict"] == "MODIFY"
    assert "does not match derived result FAIL" in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-2"]


@pytest.mark.parametrize("variant", ["Author-Y ", " AUTHOR-Y", "ＡＵＴＨＯＲ－Ｙ", "author-y　"])
def test_normalized_principal_spoof_honest_fail_is_hard_and_unmet(variant):
    r = receipt("IndependentReview", reviewer_principal=variant, author_principal="author-y")
    assert r["result"] == "FAIL"
    d = ev([receipt("TestRun"), receipt("StaticAnalysis"), r])
    assert d["verdict"] == "MODIFY"
    assert "reviewer_principal equals author_principal" in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-2"]
    assert ev([receipt("TestRun"), receipt("StaticAnalysis"), r], waiver=broad_waiver())["verdict"] == "MODIFY"


@pytest.mark.parametrize(
    "variant",
    ["author-y️", "author-y͏", "author-yㅤ", "author឴-y", "author-y͸"],
)
def test_invisible_char_reviewer_variant_of_author_never_approves(variant):
    # An invisible/filler suffix must not make the reviewer look distinct from
    # the author: the review receipt is not accepted as an approval.
    r = receipt("IndependentReview", result="PASS", reviewer_principal=variant, author_principal="author-y")
    try:
        d = ev([receipt("TestRun"), receipt("StaticAnalysis"), r])
    except c.ContractError:
        return
    assert d["verdict"] != "APPROVE"


def test_review_author_spelling_variant_of_manifest_author_is_accepted_after_normalization():
    r = receipt("IndependentReview", author_principal="  AUTHOR-Y ")
    assert ev([receipt("TestRun"), receipt("StaticAnalysis"), r])["verdict"] == "APPROVE"


def test_manifest_author_with_case_and_whitespace_is_normalized_too():
    m2 = manifest(author_principal="  Author-Y ")
    assert ev(bound_happy(m2), m=m2)["verdict"] == "APPROVE"


def test_review_findings_are_listed_as_unresolved_findings():
    r = receipt("IndependentReview", findings=["rename x", "add docstring"])
    d = ev([receipt("TestRun"), receipt("StaticAnalysis"), r])
    assert d["unresolved_findings"] == ["review finding: rename x", "review finding: add docstring"]
    assert d["verdict"] == "APPROVE"  # findings are informational, not reasons


# ---------------------------------------------------------- supervisor slot


@pytest.mark.parametrize("marker", ["BUDGET_EXCEEDED", "RETRY_EXHAUSTED"])
def test_terminal_marker_is_hard_and_blocks_otherwise_complete_set(marker):
    d = ev(happy_receipts() + [supervisor_receipt(marker)])
    assert d["verdict"] == "MODIFY"
    assert f"terminal marker {marker} (supervisor attempt 1)" in d["reasons"]
    assert d["acceptance_unmet"] == []  # the work itself is fine; the marker alone blocks


@pytest.mark.parametrize("marker", ["BUDGET_EXCEEDED", "RETRY_EXHAUSTED"])
def test_terminal_marker_is_not_waivable(marker):
    rs = not_run_tests() + [supervisor_receipt(marker)]
    d = ev(rs, waiver=broad_waiver())
    assert d["verdict"] == "MODIFY"
    assert d["waiver_record"] is None and d["human_approvals"] == []
    # Control: the same set without the marker is waivable.
    assert ev(not_run_tests(), waiver=broad_waiver())["verdict"] == "APPROVED_WITH_WAIVER"


def test_terminal_marker_from_an_older_epoch_still_blocks():
    old = supervisor_receipt("RETRY_EXHAUSTED", epoch=EPOCH - 1)
    d = ev(happy_receipts() + [old])
    assert d["verdict"] == "MODIFY"
    assert "terminal marker RETRY_EXHAUSTED" in reasons_text(d)


def test_worker_lost_marker_is_informational_and_does_not_block_approval():
    d = ev(happy_receipts() + [supervisor_receipt("WORKER_LOST")])
    assert d["verdict"] == "APPROVE"
    assert d["reasons"] == []
    assert d["unresolved_findings"] == ["worker lost: attempt 1"]


def test_supervisor_chain_of_worker_lost_markers_lists_each_loss():
    m1 = supervisor_receipt("WORKER_LOST")
    m2 = supervisor_receipt("WORKER_LOST", attempt=2, prev=hash_of(m1))
    d = ev(happy_receipts() + [m2, m1])
    assert d["verdict"] == "APPROVE"
    assert d["unresolved_findings"] == ["worker lost: attempt 1", "worker lost: attempt 2"]


def test_supervisor_chain_may_span_epochs():
    m1 = supervisor_receipt("WORKER_LOST", epoch=EPOCH - 1)
    m2 = supervisor_receipt("WORKER_LOST", attempt=2, prev=hash_of(m1))
    d = ev(happy_receipts() + [m1, m2])
    assert d["verdict"] == "APPROVE"
    assert len(d["unresolved_findings"]) == 2


def test_worker_lost_followed_by_retry_exhausted_blocks_and_keeps_the_loss_visible():
    m1 = supervisor_receipt("WORKER_LOST")
    m2 = supervisor_receipt("RETRY_EXHAUSTED", attempt=2, prev=hash_of(m1))
    d = ev(happy_receipts() + [m1, m2])
    assert d["verdict"] == "MODIFY"
    assert "terminal marker RETRY_EXHAUSTED (supervisor attempt 2)" in d["reasons"]
    assert "worker lost: attempt 1" in d["unresolved_findings"]


def test_supervisor_chain_with_wrong_prev_hash_is_hard():
    m1 = supervisor_receipt("WORKER_LOST")
    m2 = supervisor_receipt("WORKER_LOST", attempt=2, prev="e" * 64)
    d = ev(happy_receipts() + [m1, m2])
    assert d["verdict"] == "MODIFY"
    assert "attempt chain broken for slot '__supervisor__'" in reasons_text(d)


def test_supervisor_chain_not_starting_at_one_is_hard():
    m2 = supervisor_receipt("WORKER_LOST", attempt=2, prev="e" * 64)
    d = ev(happy_receipts() + [m2])
    assert d["verdict"] == "MODIFY"
    assert "attempt chain broken for slot '__supervisor__'" in reasons_text(d)


def test_unknown_supervisor_marker_text_is_hard():
    d = ev(happy_receipts() + [supervisor_receipt("ALL_GOOD", result="PASS")])
    assert d["verdict"] == "MODIFY"
    assert "unknown supervisor marker 'ALL_GOOD'" in reasons_text(d)


def test_supervisor_marker_signed_with_worker_key_is_rejected():
    forged = supervisor_receipt("WORKER_LOST", key=KEY)
    d = ev(happy_receipts() + [forged])
    assert d["verdict"] == "MODIFY"
    assert "invalid signature" in reasons_text(d)
    assert d["unresolved_findings"] == []  # a forged marker is not even recorded


def test_supervisor_marker_signed_with_operator_key_is_rejected():
    d = ev(happy_receipts() + [supervisor_receipt("WORKER_LOST", key=OPERATOR_KEY)])
    assert d["verdict"] == "MODIFY"
    assert "invalid signature" in reasons_text(d)


def test_worker_slot_receipt_signed_with_supervisor_key_is_rejected():
    r = receipt("TestRun", key=SUPERVISOR_KEY)
    d = ev([r, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "invalid signature" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_gate_with_swapped_key_arguments_rejects_everything():
    d = ev(happy_receipts() + [supervisor_receipt("WORKER_LOST")], key=SUPERVISOR_KEY, supervisor_key=KEY)
    assert d["verdict"] != "APPROVE"
    assert reasons_text(d).count("invalid signature") == 4


def test_supervisor_marker_never_counts_toward_acceptance():
    marker = supervisor_receipt("WORKER_LOST", covered_acceptance=["AC-1"])
    rs = [marker, receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert d["acceptance_unmet"] == ["AC-1"]
    assert "missing receipt for slot 'tests'" in d["reasons"]


def test_supervisor_marker_bound_to_another_manifest_is_rejected():
    stray = supervisor_receipt("WORKER_LOST", manifest_sha256="f" * 64)
    d = ev(happy_receipts() + [stray])
    assert d["verdict"] == "MODIFY"
    assert "manifest_sha256 does not match the manifest" in reasons_text(d)


def test_supervisor_marker_with_future_epoch_is_hard():
    d = ev(happy_receipts() + [supervisor_receipt("WORKER_LOST", epoch=EPOCH + 1)])
    assert d["verdict"] == "MODIFY"
    assert "future epoch" in reasons_text(d)


def test_non_documentation_receipt_in_supervisor_slot_is_invalid():
    bad = receipt("TestRun", slot="__supervisor__", key=SUPERVISOR_KEY)
    d = ev(happy_receipts() + [bad])
    assert d["verdict"] == "MODIFY"
    assert "reserved" in reasons_text(d)


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


def test_waiver_expiry_boundary_current_epoch_equal_to_expires_epoch_is_valid():
    assert ev(not_run_tests(), waiver=valid_waiver(expires_epoch=EPOCH))["verdict"] == "APPROVED_WITH_WAIVER"
    assert ev(not_run_tests(), waiver=valid_waiver(expires_epoch=EPOCH + 10))["verdict"] == "APPROVED_WITH_WAIVER"


@pytest.mark.parametrize(
    "kw,fragment",
    [
        ({"task_id": "OTHER"}, "waiver task_id != manifest task_id"),
        ({"epoch": EPOCH - 1}, "waiver epoch != current epoch"),
        ({"epoch": EPOCH + 1, "expires_epoch": EPOCH + 5}, "waiver epoch != current epoch"),
        ({"head": HEAD2}, "waiver head != current head"),
        ({"manifest_sha256": "e" * 64}, "waiver manifest_sha256 != manifest"),
        ({"expires_epoch": EPOCH - 1}, "expired"),
        ({"waived_slots": []}, "slot 'tests' is not waived"),
        ({"waived_slots": ["static"]}, "slot 'tests' is not waived"),
        ({"waived_acceptance": []}, "acceptance 'AC-1' is not waived"),
        ({"waived_acceptance": ["AC-2"]}, "acceptance 'AC-1' is not waived"),
    ],
)
def test_signed_waiver_with_failing_binding_leaves_modify(kw, fragment):
    w = valid_waiver(**kw)
    assert signing.verify(w, OPERATOR_KEY, signing.WAIVER_LABEL)  # the signature itself is genuine
    d = ev(not_run_tests(), waiver=w)
    assert d["verdict"] == "MODIFY"
    assert d["waiver_record"] is None
    assert d["human_approvals"] == []
    assert fragment in reasons_text(d)


def test_waiver_signed_for_one_manifest_cannot_be_replayed_on_a_changed_manifest():
    m2 = manifest(model_policy="other-policy")
    rs = [
        bound(m2, "TestRun", result="NOT_RUN"),
        bound(m2, "StaticAnalysis"),
        bound(m2, "IndependentReview"),
    ]
    assert ev(rs, m=m2, waiver=valid_waiver(manifest_sha256=mhash(m2)))["verdict"] == "APPROVED_WITH_WAIVER"
    d = ev(rs, m=m2, waiver=valid_waiver())  # signed for manifest M
    assert d["verdict"] == "MODIFY"
    assert "waiver manifest_sha256 != manifest" in reasons_text(d)


@pytest.mark.parametrize(
    "kw,fragment",
    [
        ({"operator": ""}, "operator must be a non-empty string"),
        ({"operator": "  "}, "operator must be a non-empty string"),
        ({"operator": None}, "operator must be a non-empty string"),
        ({"record_id": ""}, "record_id must be a non-empty string"),
        ({"task_id": ""}, "task_id must be a non-empty string"),
        ({"head": ""}, "head must be a non-empty string"),
        ({"manifest_sha256": ""}, "manifest_sha256 must be a non-empty string"),
        ({"epoch": "2"}, "epoch must be an integer"),
        ({"epoch": True}, "epoch must be an integer"),
        ({"expires_epoch": "5"}, "expires_epoch must be an integer"),
        ({"expires_epoch": True}, "expires_epoch must be an integer"),
        ({"expires_epoch": 2.0}, "expires_epoch must be an integer"),
        ({"waived_slots": "tests"}, "waived_slots must be a list of strings"),
        ({"waived_acceptance": [1]}, "waived_acceptance must be a list of strings"),
    ],
)
def test_malformed_waiver_field_leaves_modify(kw, fragment):
    d = ev(not_run_tests(), waiver=valid_waiver(**kw))
    assert d["verdict"] == "MODIFY"
    assert d["waiver_record"] is None
    assert d["human_approvals"] == []
    assert fragment in reasons_text(d)


@pytest.mark.parametrize("sig", ["Z" * 64, "A" * 64, "a" * 63, "", None, 5])
def test_waiver_signature_must_be_64_lowercase_hex(sig):
    w = valid_waiver()
    w["signature"] = sig
    d = ev(not_run_tests(), waiver=w)
    assert d["verdict"] == "MODIFY"
    assert "signature must be 64 lowercase hex characters" in reasons_text(d)


@pytest.mark.parametrize(
    "field",
    [
        "record_id", "operator", "task_id", "epoch", "head", "manifest_sha256",
        "waived_slots", "waived_acceptance", "expires_epoch", "signature",
    ],
)
def test_waiver_missing_field_rejected(field):
    w = valid_waiver()
    del w[field]
    d = ev(not_run_tests(), waiver=w)
    assert d["verdict"] == "MODIFY"
    assert f"missing field(s): {field}" in reasons_text(d)


def test_waiver_unknown_field_rejected_even_when_signed():
    d = ev(not_run_tests(), waiver=valid_waiver(note="x"))
    assert d["verdict"] == "MODIFY"
    assert "unknown field(s): note" in reasons_text(d)


def test_legacy_unsigned_waiver_format_is_rejected():
    legacy = {
        "record_id": "W-1",
        "operator": "operator-ivan",
        "waived_slots": ["tests"],
        "waived_acceptance": ["AC-1"],
        "head": HEAD,
        "expires_epoch_or_date": "2026-12-31",
    }
    d = ev(not_run_tests(), waiver=legacy)
    assert d["verdict"] == "MODIFY"
    assert d["waiver_record"] is None and d["human_approvals"] == []
    assert "unknown field(s): expires_epoch_or_date" in reasons_text(d)
    assert "missing field(s)" in reasons_text(d)


@pytest.mark.parametrize("bad", ["W-1", ["x"], 5, True])
def test_non_dict_waiver_rejected(bad):
    d = ev(not_run_tests(), waiver=bad)
    assert d["verdict"] == "MODIFY"
    assert "waiver rejected" in reasons_text(d)


def test_waiver_with_forged_signature_is_rejected():
    w = valid_waiver()
    w["signature"] = "0" * 64
    d = ev(not_run_tests(), waiver=w)
    assert d["verdict"] == "MODIFY"
    assert "waiver rejected: invalid signature" in reasons_text(d)


def test_waiver_tampered_after_signing_is_rejected():
    w = valid_waiver()
    w["waived_acceptance"] = ["AC-1", "AC-2"]  # widened after the operator signed
    d = ev(not_run_tests(), waiver=w)
    assert d["verdict"] == "MODIFY"
    assert "waiver rejected: invalid signature" in reasons_text(d)


def test_waiver_signed_with_the_receipt_label_is_rejected():
    # Label separation: an operator-key signature in the receipt domain is not a waiver.
    w = signed_waiver(label=signing.RECEIPT_LABEL)
    assert signing.verify(w, OPERATOR_KEY, signing.RECEIPT_LABEL)
    d = ev(not_run_tests(), waiver=w)
    assert d["verdict"] == "MODIFY"
    assert "waiver rejected: invalid signature" in reasons_text(d)
    assert d["waiver_record"] is None and d["human_approvals"] == []


@pytest.mark.parametrize("wrong", [KEY, SUPERVISOR_KEY, WRONG_KEY])
def test_waiver_signed_with_a_non_operator_key_is_rejected(wrong):
    d = ev(not_run_tests(), waiver=signed_waiver(key=wrong))
    assert d["verdict"] == "MODIFY"
    assert "waiver rejected: invalid signature" in reasons_text(d)


def test_waiver_by_worker_key_in_waiver_label_is_rejected_even_if_worker_holds_it():
    # A compromised worker that knows its own key still cannot waive.
    d = ev(not_run_tests(), waiver=signed_waiver(key=KEY, label=signing.WAIVER_LABEL))
    assert d["verdict"] == "MODIFY"


@pytest.mark.parametrize("op_key", [None, b"", b"o" * 31, "text-key"])
def test_waiver_without_a_valid_operator_key_is_unusable(op_key):
    d = ev(not_run_tests(), operator_key=op_key, waiver=valid_waiver())
    assert d["verdict"] == "MODIFY"
    assert "waiver rejected: no valid operator_key" in reasons_text(d)
    assert d["waiver_record"] is None


def test_operator_key_without_a_waiver_changes_nothing():
    assert ev(happy_receipts(), operator_key=None)["verdict"] == "APPROVE"
    assert ev(not_run_tests(), operator_key=OPERATOR_KEY)["verdict"] == "MODIFY"


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


def test_waiver_can_cover_a_slot_that_only_has_an_older_epoch_attempt():
    rs = [receipt("TestRun", epoch=EPOCH - 1), receipt("StaticAnalysis"), receipt("IndependentReview")]
    assert ev(rs)["verdict"] == "MODIFY"
    assert ev(rs, waiver=valid_waiver())["verdict"] == "APPROVED_WITH_WAIVER"


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
    d = gate.evaluate(bad, happy_receipts(), HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY)
    assert d["verdict"] == "NO_GO"
    assert d["task_id"] == ""


def test_manifest_with_zero_required_receipts_is_no_go():
    d = ev(happy_receipts(), m=manifest(required_receipts=[]))
    assert d["verdict"] == "NO_GO"


@pytest.mark.parametrize(
    "overrides",
    [
        {"author_principal": ""},
        {"required_tests": []},
        {"allowed_commands": []},
        {"required_rules": []},
        {"required_receipts": [{"slot": "__supervisor__", "receipt_type": "Documentation"}]},
        {"required_receipts": [{"slot": "tests", "receipt_type": "TestRun"}]},  # no review slot
    ],
)
def test_manifest_violating_the_new_contract_is_no_go(overrides):
    d = ev(happy_receipts(), m=manifest(**overrides))
    assert d["verdict"] == "NO_GO"
    assert "manifest invalid" in reasons_text(d)
    assert d["required_receipt_hashes"] == []


def test_manifest_missing_a_new_field_is_no_go():
    m = manifest()
    del m["required_tests"]
    d = ev(happy_receipts(), m=m)
    assert d["verdict"] == "NO_GO"
    assert "required_tests" in reasons_text(d)


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
        ({"key": b"k" * 31}, "key"),
        ({"key": "text-key" * 8}, "key"),
        ({"key": None}, "key"),
        ({"supervisor_key": None}, "supervisor_key"),
        ({"supervisor_key": b"s" * 31}, "supervisor_key"),
        ({"supervisor_key": "s" * 40}, "supervisor_key"),
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


def test_bytearray_keys_accepted():
    d = ev(happy_receipts(), key=bytearray(KEY), supervisor_key=bytearray(SUPERVISOR_KEY))
    assert d["verdict"] == "APPROVE"


def test_exactly_32_byte_keys_are_accepted():
    k, s = b"w" * 32, b"s" * 32
    rs = [receipt("TestRun", key=k), receipt("StaticAnalysis", key=k), receipt("IndependentReview", key=k)]
    assert ev(rs, key=k, supervisor_key=s)["verdict"] == "APPROVE"


# --------------------------------------------------------------- invariants


def _bad_scenarios():
    first, second = _retry_pair("FAIL")
    forged = receipt("TestRun")
    forged["signature"] = "0" * 64
    gap = receipt("TestRun", attempt=3, prev_receipt_sha256=hash_of(first))
    rest = rest_receipts()
    old_fail = receipt("TestRun", attempt=1, epoch=EPOCH - 1, skipped_test_ids=["t3"])
    fresh_one = receipt("TestRun", attempt=1, epoch=EPOCH, receipt_id="r-fresh")
    return {
        "missing": [r for r in happy_receipts() if r["slot"] != "review"],
        "empty": [],
        "unlisted": happy_receipts() + [receipt("TestRun", slot="zz")],
        "stale_head": [receipt("TestRun", candidate_head=HEAD2)] + rest,
        "stale_epoch": [receipt("TestRun", epoch=EPOCH + 5)] + rest,
        "old_epoch_attempt": [receipt("TestRun", epoch=EPOCH - 1)] + rest,
        "epoch_takeover": [old_fail, fresh_one] + rest,
        "forged": [forged] + rest,
        "lying": [receipt("TestRun", result="PASS", skipped_test_ids=["q"])] + rest,
        "gap": [first, gap] + rest,
        "not_run": [receipt("TestRun", result="NOT_RUN")] + rest,
        "inconclusive": [receipt("TestRun", result="INCONCLUSIVE")] + rest,
        "blocked": [receipt("TestRun", result="BLOCKED")] + rest,
        "self_review": [receipt("TestRun"), receipt("StaticAnalysis"),
                        receipt("IndependentReview", reviewer_principal="s", author_principal="s")],
        "uncovered": [receipt("TestRun"), receipt("StaticAnalysis"),
                      receipt("IndependentReview", covered_acceptance=[])],
        "other_task": happy_receipts() + [receipt("TestRun", task_id="X")],
        "type_mismatch": [receipt("Documentation", slot="tests")] + rest,
        "wrong_manifest_hash": [receipt("TestRun", manifest_sha256="e" * 64)] + rest,
        "wrong_role": [receipt("TestRun", role_sha256="e" * 64)] + rest,
        "author_mismatch": [receipt("TestRun"), receipt("StaticAnalysis"),
                            receipt("IndependentReview", author_principal="mallory")],
        "bad_command": [receipt("TestRun", commands=[{"argv": ["rm", "-rf"], "exit_code": 0}])] + rest,
        "wrong_expected_ids": [receipt("TestRun", expected_test_ids=["t1"], executed_test_ids=["t1"])] + rest,
        "claimed_unknown_acceptance": [receipt("TestRun", covered_acceptance=["AC-X"])] + rest,
        "artifact_no_resolver": [receipt("TestRun", artifact_digests={"p": ART})] + rest,
        "terminal_marker": happy_receipts() + [supervisor_receipt("BUDGET_EXCEEDED")],
        "unknown_marker": happy_receipts() + [supervisor_receipt("ALL_GOOD", result="PASS")],
        "forged_marker": happy_receipts() + [supervisor_receipt("WORKER_LOST", key=KEY)],
        "supervisor_key_on_worker_slot": [receipt("TestRun", key=SUPERVISOR_KEY)] + rest,
    }


@pytest.mark.parametrize("name", sorted(_bad_scenarios()))
def test_never_approve_when_any_hard_or_soft_reason_exists(name):
    rs = _bad_scenarios()[name]
    for waiver in (None, broad_waiver()):
        d = ev(rs, waiver=waiver)
        assert d["verdict"] != "APPROVE", name
        assert d["reasons"], name
        if d["verdict"] == "APPROVED_WITH_WAIVER":
            assert d["waiver_record"] == "W-1"
        else:
            assert d["waiver_record"] is None and d["human_approvals"] == []
        c.validate_gate_decision(d)


HARD_SCENARIOS = [
    "unlisted", "stale_head", "stale_epoch", "epoch_takeover", "forged", "lying", "gap",
    "self_review", "other_task", "type_mismatch", "wrong_manifest_hash", "wrong_role", "author_mismatch",
    "bad_command", "wrong_expected_ids", "claimed_unknown_acceptance", "artifact_no_resolver",
    "terminal_marker", "unknown_marker", "forged_marker", "supervisor_key_on_worker_slot",
]


@pytest.mark.parametrize("name", HARD_SCENARIOS)
def test_hard_reason_scenarios_are_never_waivable(name):
    rs = _bad_scenarios()[name]
    d = ev(rs, waiver=broad_waiver())
    assert d["verdict"] in {"MODIFY", "NO_GO"}
    assert d["waiver_record"] is None and d["human_approvals"] == []


@pytest.mark.parametrize("name", ["missing", "empty", "old_epoch_attempt", "not_run", "inconclusive",
                                  "blocked", "uncovered"])
def test_soft_only_scenarios_are_waivable_with_a_broad_signed_waiver(name):
    # Control for the previous test: the broad waiver itself is valid, so the
    # HARD_SCENARIOS result above is due to the hard reasons, not a bad waiver.
    rs = _bad_scenarios()[name]
    d = ev(rs, waiver=broad_waiver())
    assert d["verdict"] == "APPROVED_WITH_WAIVER", (name, d["reasons"])
    assert d["waiver_record"] == "W-1" and d["human_approvals"] == ["operator-ivan"]


def test_inputs_are_not_mutated_in_any_scenario():
    w = broad_waiver()
    snapshot_w = copy.deepcopy(w)
    m = manifest()
    snapshot_m = copy.deepcopy(m)
    for name, rs in _bad_scenarios().items():
        snap = copy.deepcopy(rs)
        gate.evaluate(m, rs, HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
                      operator_key=OPERATOR_KEY, waiver=w, artifact_resolver=lambda p: ART)
        assert rs == snap, name
    rs = happy_receipts()
    snap = copy.deepcopy(rs)
    gate.evaluate(m, rs, HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
                  operator_key=OPERATOR_KEY, waiver=w)
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


def _with_artifact(**kw):
    return [
        receipt("TestRun", artifact_digests={"out/report.txt": ART}, **kw),
        receipt("StaticAnalysis"),
        receipt("IndependentReview"),
    ]


def test_resolver_matching_digest_keeps_approve_and_receives_the_path():
    seen = []

    def resolver(path):
        seen.append(path)
        return ART

    d = ev(_with_artifact(), resolver=resolver)
    assert d["verdict"] == "APPROVE"
    assert seen == ["out/report.txt"]


def test_resolver_mismatching_digest_is_hard_reason_and_receipt_invalid():
    d = ev(_with_artifact(), resolver=lambda p: "b" * 64)
    assert d["verdict"] == "MODIFY"
    assert "digest mismatch" in reasons_text(d) and "out/report.txt" in reasons_text(d)
    assert "r-tests-1" in reasons_text(d)
    assert "slot 'tests' latest attempt 1 rejected: artifact check failed" in d["reasons"]
    assert d["acceptance_unmet"] == ["AC-1"]


def test_resolver_returning_none_is_rejected():
    d = ev(_with_artifact(), resolver=lambda p: None)
    assert d["verdict"] == "MODIFY"
    assert "digest mismatch" in reasons_text(d)
    assert "slot 'tests' latest attempt 1 rejected: artifact check failed" in d["reasons"]


def test_raising_resolver_is_default_deny_not_an_exception():
    def boom(path):
        raise OSError("disk gone")

    d = ev(_with_artifact(), resolver=boom)
    assert d["verdict"] == "MODIFY"
    assert "cannot be resolved" in reasons_text(d) and "OSError" in reasons_text(d)
    assert "slot 'tests' latest attempt 1 rejected: artifact check failed" in d["reasons"]


def test_artifact_digests_without_a_resolver_are_denied_by_default():
    d = ev(_with_artifact())
    assert d["verdict"] == "MODIFY"
    assert "artifact digests present but no artifact_resolver" in d["reasons"]
    assert "slot 'tests' latest attempt 1 rejected: artifact check failed" in d["reasons"]
    assert d["acceptance_unmet"] == ["AC-1"]
    assert d["required_receipt_hashes"] != []  # the other slots are still recorded
    # explicit None is the same as omitting the resolver
    assert ev(_with_artifact(), resolver=None)["verdict"] == "MODIFY"


def test_missing_resolver_denial_is_not_waivable():
    d = ev(_with_artifact(), waiver=broad_waiver())
    assert d["verdict"] == "MODIFY"
    assert d["waiver_record"] is None


def test_receipts_without_artifacts_need_no_resolver():
    assert ev(happy_receipts())["verdict"] == "APPROVE"


def test_resolver_not_called_for_receipts_without_artifacts_or_other_types():
    calls = []
    d = ev(happy_receipts(), resolver=lambda p: calls.append(p) or "x")
    assert d["verdict"] == "APPROVE" and calls == []


def test_resolver_checks_every_artifact_of_the_receipt():
    rs = [
        receipt("TestRun", artifact_digests={"a": ART, "b": "c" * 64}),
        receipt("StaticAnalysis"),
        receipt("IndependentReview"),
    ]
    d = ev(rs, resolver=lambda p: {"a": ART, "b": "d" * 64}[p])
    assert d["verdict"] == "MODIFY" and "'b'" in reasons_text(d)


def test_resolver_mismatch_is_not_waivable():
    d = ev(_with_artifact(), waiver=broad_waiver(), resolver=lambda p: "b" * 64)
    assert d["verdict"] == "MODIFY"


def test_resolver_not_consulted_for_receipt_already_invalid():
    calls = []
    bad = receipt("TestRun", artifact_digests={"a": ART})
    bad["signature"] = "0" * 64
    d = ev([bad, receipt("StaticAnalysis"), receipt("IndependentReview")],
           resolver=lambda p: calls.append(p) or ART)
    assert "invalid signature" in reasons_text(d) and calls == []


def test_zero_digest_receipt_claiming_pass_is_rejected_as_derived_mismatch():
    lying = receipt("TestRun", result="PASS", artifact_digests={"gone": "0" * 64})
    d = ev([lying, receipt("StaticAnalysis"), receipt("IndependentReview")], resolver=lambda p: "0" * 64)
    assert d["verdict"] == "MODIFY"
    assert "does not match derived result FAIL" in reasons_text(d)


# ====================================================================
# S1 second remediation (package C1): deciding receipt, history, markers,
# key distinctness, artifact keys
# ====================================================================


def at_head(head):
    """Complete valid receipt set whose candidate_head is `head`."""
    return [
        receipt("TestRun", candidate_head=head),
        receipt("StaticAnalysis", candidate_head=head),
        receipt("IndependentReview", candidate_head=head),
    ]


def history_text(d):
    return [f for f in d["unresolved_findings"] if f.startswith("history attempt at other head")]


# ---- retry across a head change: older attempts are history, not blockers


def test_retry_after_head_change_reaches_approve_with_history_finding():
    first = receipt("TestRun", attempt=1, candidate_head=HEAD2, skipped_test_ids=["t3"])
    assert first["result"] == "FAIL"
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first))
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "APPROVE"
    assert d["reasons"] == []
    assert d["unresolved_findings"] == [
        "earlier failure retained: tests attempt 1 FAIL",
        "history attempt at other head: tests attempt 1",
    ]
    assert hash_of(second) in d["required_receipt_hashes"]
    assert hash_of(first) not in d["required_receipt_hashes"]
    assert d["acceptance_unmet"] == []


def test_earlier_pass_at_other_head_is_only_a_history_finding():
    first = receipt("TestRun", attempt=1, candidate_head=HEAD2)
    assert first["result"] == "PASS"
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first))
    d = ev([second, first, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "APPROVE"
    assert d["reasons"] == []
    assert d["unresolved_findings"] == ["history attempt at other head: tests attempt 1"]


def test_history_at_other_head_and_older_epoch_both_do_not_block():
    first = receipt("TestRun", attempt=1, epoch=EPOCH - 1, candidate_head=HEAD2, skipped_test_ids=["t3"])
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first))
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "APPROVE"
    assert d["reasons"] == []
    assert history_text(d) == ["history attempt at other head: tests attempt 1"]


def test_three_attempt_chain_over_two_heads_lists_each_other_head_attempt():
    a1 = receipt("TestRun", attempt=1, candidate_head=HEAD2, result="BLOCKED")
    a2 = receipt("TestRun", attempt=2, candidate_head=HEAD2, prev_receipt_sha256=hash_of(a1), result="INCONCLUSIVE")
    a3 = receipt("TestRun", attempt=3, prev_receipt_sha256=hash_of(a2))
    d = ev([a3, a2, a1, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "APPROVE"
    assert d["reasons"] == []
    assert history_text(d) == [
        "history attempt at other head: tests attempt 1",
        "history attempt at other head: tests attempt 2",
    ]


def test_older_attempt_at_the_current_head_gets_no_history_finding():
    first = receipt("TestRun", attempt=1, skipped_test_ids=["t3"])
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first))
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "APPROVE"
    assert history_text(d) == []


def test_older_attempt_with_wrong_head_and_broken_chain_is_still_a_hard_chain_error():
    # History is tolerated only inside an intact chain.
    first = receipt("TestRun", attempt=1, candidate_head=HEAD2, skipped_test_ids=["t3"])
    second = receipt("TestRun", attempt=2, prev_receipt_sha256="e" * 64)
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert "attempt chain broken for slot 'tests'" in reasons_text(d)
    assert hash_of(second) not in d["required_receipt_hashes"]


# ---- deciding receipt at another head: hard + unmet


def test_latest_attempt_at_other_head_is_stale_even_if_an_earlier_one_is_current():
    first = receipt("TestRun", attempt=1)
    second = receipt("TestRun", attempt=2, candidate_head=HEAD2, prev_receipt_sha256=hash_of(first))
    d = ev([first, second, receipt("StaticAnalysis"), receipt("IndependentReview")])
    assert d["verdict"] == "MODIFY"
    assert f"receipt {second['receipt_id']} stale head" in reasons_text(d)
    assert any(r.startswith("slot 'tests' needs an attempt at the current head") for r in d["reasons"])
    assert d["acceptance_unmet"] == ["AC-1"]  # the earlier current-head PASS gives no coverage
    assert hash_of(first) not in d["required_receipt_hashes"]
    assert hash_of(second) not in d["required_receipt_hashes"]
    assert history_text(d) == []  # attempt 1 is at the current head; attempt 2 is deciding, not history


def test_deciding_stale_receipt_is_a_hard_reason_so_a_waiver_cannot_cover_it():
    stale = receipt("TestRun", candidate_head=HEAD2)
    rs = [stale, receipt("StaticAnalysis"), receipt("IndependentReview")]
    d = ev(rs, waiver=broad_waiver())
    assert d["verdict"] == "MODIFY"
    assert d["waiver_record"] is None and d["human_approvals"] == []
    # control: the same slot merely NOT_RUN at the current head is waivable
    assert ev(not_run_tests(), waiver=broad_waiver())["verdict"] == "APPROVED_WITH_WAIVER"


@pytest.mark.parametrize(
    "rtype,slot,unmet",
    [("TestRun", "tests", ["AC-1"]), ("StaticAnalysis", "static", []), ("IndependentReview", "review", ["AC-2"])],
)
def test_stale_deciding_receipt_of_any_slot_type_is_hard_and_unmet(rtype, slot, unmet):
    stale = receipt(rtype, candidate_head=HEAD2)
    rs = [stale] + [r for r in happy_receipts() if r["slot"] != slot]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert f"receipt {stale['receipt_id']} stale head" in reasons_text(d)
    assert any(r.startswith(f"slot '{slot}' needs an attempt at the current head") for r in d["reasons"])
    assert d["acceptance_unmet"] == unmet
    assert hash_of(stale) not in d["required_receipt_hashes"]
    assert len(d["required_receipt_hashes"]) == 2


def test_two_of_three_deciding_stale_is_modify_not_no_go():
    rs = [
        receipt("TestRun", candidate_head=HEAD2),
        receipt("StaticAnalysis", candidate_head=HEAD2),
        receipt("IndependentReview"),
    ]
    d = ev(rs)
    assert d["verdict"] == "MODIFY"
    assert "all deciding receipts" not in reasons_text(d)
    assert reasons_text(d).count("stale head") == 2


# ---- all deciding receipts stale -> NO_GO (markers / history do not count)


def test_all_deciding_stale_is_no_go_even_with_a_current_head_history_attempt():
    first = receipt("TestRun", attempt=1, skipped_test_ids=["t3"])  # current head, but history
    second = receipt("TestRun", attempt=2, candidate_head=HEAD2, prev_receipt_sha256=hash_of(first))
    rs = [first, second, receipt("StaticAnalysis", candidate_head=HEAD2), receipt("IndependentReview", candidate_head=HEAD2)]
    d = ev(rs)
    assert d["verdict"] == "NO_GO"
    assert "all deciding receipts for this task are stale" in reasons_text(d)


def test_all_deciding_stale_is_no_go_even_with_a_current_head_worker_lost_marker():
    d = ev(at_head(HEAD2) + [supervisor_receipt("WORKER_LOST")])  # marker at the CURRENT head
    assert d["verdict"] == "NO_GO"
    assert "all deciding receipts for this task are stale" in reasons_text(d)
    assert d["unresolved_findings"] == ["worker lost: attempt 1"]  # still reported


def test_all_deciding_stale_is_no_go_with_marker_at_the_stale_head_too():
    d = ev(at_head(HEAD2) + [supervisor_receipt("WORKER_LOST", candidate_head=HEAD2)])
    assert d["verdict"] == "NO_GO"


def test_all_deciding_stale_is_no_go_with_history_at_another_head():
    first = receipt("TestRun", attempt=1, candidate_head=HEAD2, skipped_test_ids=["t3"])
    second = receipt("TestRun", attempt=2, candidate_head=HEAD2, prev_receipt_sha256=hash_of(first))
    d = ev([first, second, receipt("StaticAnalysis", candidate_head=HEAD2), receipt("IndependentReview", candidate_head=HEAD2)])
    assert d["verdict"] == "NO_GO"
    assert history_text(d) == ["history attempt at other head: tests attempt 1"]


def test_single_stale_deciding_receipt_plus_marker_is_no_go():
    d = ev([receipt("TestRun", candidate_head=HEAD2), supervisor_receipt("WORKER_LOST")])
    assert d["verdict"] == "NO_GO"


def test_supervisor_marker_alone_does_not_make_the_set_stale():
    # A marker is not a deciding receipt: with nothing else there is nothing stale.
    d = ev([supervisor_receipt("WORKER_LOST", candidate_head=HEAD2)])
    assert d["verdict"] == "MODIFY"
    assert "all deciding receipts" not in reasons_text(d)
    assert d["acceptance_unmet"] == ["AC-1", "AC-2"]


def test_future_epoch_worker_receipts_and_stale_head_receipts_together_are_no_go():
    rs = [
        receipt("TestRun", epoch=EPOCH + 1),
        receipt("StaticAnalysis", candidate_head=HEAD2),
        receipt("IndependentReview", candidate_head=HEAD2),
    ]
    d = ev(rs)
    assert d["verdict"] == "NO_GO"
    assert "future epoch" in reasons_text(d) and "stale head" in reasons_text(d)


def test_future_epoch_supervisor_marker_does_not_count_toward_the_stale_set():
    d = ev(at_head(HEAD2) + [supervisor_receipt("WORKER_LOST", epoch=EPOCH + 1)])
    assert d["verdict"] == "NO_GO"  # all three deciding receipts are stale
    d2 = ev([supervisor_receipt("WORKER_LOST", epoch=EPOCH + 1)])
    assert d2["verdict"] == "MODIFY"  # a marker alone is not a stale deciding receipt
    assert "future epoch" in reasons_text(d2)


def test_waiver_cannot_rescue_all_deciding_stale_with_history():
    first = receipt("TestRun", attempt=1, result="NOT_RUN")
    second = receipt("TestRun", attempt=2, candidate_head=HEAD2, prev_receipt_sha256=hash_of(first), result="NOT_RUN")
    rs = [first, second, receipt("StaticAnalysis", candidate_head=HEAD2), receipt("IndependentReview", candidate_head=HEAD2)]
    d = ev(rs, waiver=broad_waiver())
    assert d["verdict"] == "NO_GO"
    assert d["waiver_record"] is None and d["human_approvals"] == []


# ---- supervisor markers vs. the head


def test_worker_lost_marker_at_another_head_is_not_a_hard_reason():
    d = ev(happy_receipts() + [supervisor_receipt("WORKER_LOST", candidate_head=HEAD2)])
    assert d["verdict"] == "APPROVE"
    assert d["reasons"] == []
    assert d["unresolved_findings"] == ["worker lost: attempt 1"]
    assert d["acceptance_unmet"] == []


def test_worker_lost_marker_at_base_head_while_gate_head_moved_is_not_a_hard_reason():
    assert M["base_head"] == HEAD and HEAD2 != HEAD
    marker = supervisor_receipt("WORKER_LOST", candidate_head=M["base_head"])
    d = ev(at_head(HEAD2) + [marker], head=HEAD2)
    assert d["verdict"] == "APPROVE"
    assert d["reasons"] == []
    assert d["candidate_head"] == HEAD2
    assert d["unresolved_findings"] == ["worker lost: attempt 1"]


def test_worker_lost_chain_across_heads_lists_each_loss_and_approves():
    m1 = supervisor_receipt("WORKER_LOST", candidate_head=HEAD2)
    m2 = supervisor_receipt("WORKER_LOST", attempt=2, prev=hash_of(m1))
    d = ev(happy_receipts() + [m2, m1])
    assert d["verdict"] == "APPROVE"
    assert d["unresolved_findings"] == ["worker lost: attempt 1", "worker lost: attempt 2"]


@pytest.mark.parametrize("marker", ["BUDGET_EXCEEDED", "RETRY_EXHAUSTED"])
def test_terminal_marker_at_another_head_is_still_hard(marker):
    d = ev(happy_receipts() + [supervisor_receipt(marker, candidate_head=HEAD2)])
    assert d["verdict"] == "MODIFY"
    assert f"terminal marker {marker} (supervisor attempt 1)" in d["reasons"]
    assert "stale head" not in reasons_text(d)  # hard because it is terminal, not because of the head
    assert d["acceptance_unmet"] == []


@pytest.mark.parametrize("marker", ["BUDGET_EXCEEDED", "RETRY_EXHAUSTED"])
def test_terminal_marker_at_another_head_is_not_waivable(marker):
    rs = not_run_tests() + [supervisor_receipt(marker, candidate_head=HEAD2)]
    d = ev(rs, waiver=broad_waiver())
    assert d["verdict"] == "MODIFY"
    assert d["waiver_record"] is None and d["human_approvals"] == []


def test_unknown_marker_at_another_head_is_hard_for_its_text_not_its_head():
    d = ev(happy_receipts() + [supervisor_receipt("ALL_GOOD", result="PASS", candidate_head=HEAD2)])
    assert d["verdict"] == "MODIFY"
    assert "unknown supervisor marker 'ALL_GOOD'" in reasons_text(d)
    assert "stale head" not in reasons_text(d)


def test_marker_chain_worker_lost_then_terminal_at_other_heads_keeps_loss_and_blocks():
    m1 = supervisor_receipt("WORKER_LOST", candidate_head=HEAD2)
    m2 = supervisor_receipt("RETRY_EXHAUSTED", attempt=2, prev=hash_of(m1), candidate_head=HEAD2)
    d = ev(happy_receipts() + [m1, m2])
    assert d["verdict"] == "MODIFY"
    assert "terminal marker RETRY_EXHAUSTED (supervisor attempt 2)" in d["reasons"]
    assert "worker lost: attempt 1" in d["unresolved_findings"]


# ---- terminal markers are dropped only for bad signature / binding


def test_future_epoch_worker_lost_marker_is_kept_and_hard():
    d = ev(happy_receipts() + [supervisor_receipt("WORKER_LOST", epoch=EPOCH + 1)])
    assert d["verdict"] == "MODIFY"
    assert f"future epoch: {EPOCH + 1} > {EPOCH}" in reasons_text(d)
    assert d["unresolved_findings"] == ["worker lost: attempt 1"]  # kept, not dropped
    assert d["acceptance_unmet"] == []


@pytest.mark.parametrize("marker", ["BUDGET_EXCEEDED", "RETRY_EXHAUSTED"])
def test_future_epoch_terminal_marker_is_kept_both_reasons_are_hard(marker):
    d = ev(happy_receipts() + [supervisor_receipt(marker, epoch=EPOCH + 1)])
    assert d["verdict"] == "MODIFY"
    assert "future epoch" in reasons_text(d)
    assert f"terminal marker {marker} (supervisor attempt 1)" in d["reasons"]
    assert ev(not_run_tests() + [supervisor_receipt(marker, epoch=EPOCH + 1)], waiver=broad_waiver())["verdict"] == "MODIFY"


def test_future_epoch_marker_chain_is_intact_after_a_kept_marker():
    m1 = supervisor_receipt("WORKER_LOST", epoch=EPOCH + 1)
    m2 = supervisor_receipt("WORKER_LOST", attempt=2, prev=hash_of(m1))
    d = ev(happy_receipts() + [m1, m2])
    assert "attempt chain broken" not in reasons_text(d)  # m1 was kept, so m2 links to it
    assert d["unresolved_findings"] == ["worker lost: attempt 1", "worker lost: attempt 2"]


def test_forged_future_epoch_terminal_marker_is_dropped():
    d = ev(happy_receipts() + [supervisor_receipt("BUDGET_EXCEEDED", epoch=EPOCH + 1, key=KEY)])
    assert d["verdict"] == "MODIFY"
    assert "invalid signature" in reasons_text(d) and "future epoch" in reasons_text(d)
    assert "terminal marker" not in reasons_text(d)
    assert d["unresolved_findings"] == []


def test_terminal_marker_bound_to_another_manifest_is_dropped_not_recorded():
    d = ev(happy_receipts() + [supervisor_receipt("RETRY_EXHAUSTED", manifest_sha256="f" * 64)])
    assert d["verdict"] == "MODIFY"
    assert "manifest_sha256 does not match the manifest" in reasons_text(d)
    assert "terminal marker" not in reasons_text(d)


def test_terminal_marker_with_wrong_role_is_dropped_not_recorded():
    d = ev(happy_receipts() + [supervisor_receipt("RETRY_EXHAUSTED", role_sha256="e" * 64)])
    assert d["verdict"] == "MODIFY"
    assert "role_sha256 does not match the manifest" in reasons_text(d)
    assert "terminal marker" not in reasons_text(d)


# ---- artifact checks only on the deciding attempt


def _retry_with_artifact(first_artifacts, second_artifacts):
    first = receipt("TestRun", attempt=1, skipped_test_ids=["t3"], artifact_digests=first_artifacts)
    second = receipt("TestRun", attempt=2, prev_receipt_sha256=hash_of(first), artifact_digests=second_artifacts)
    return first, second, [first, second, receipt("StaticAnalysis"), receipt("IndependentReview")]


@pytest.mark.parametrize("resolver", [lambda p: "b" * 64, lambda p: None])
def test_artifact_mismatch_on_an_older_attempt_gives_no_hard_reason(resolver):
    _, second, rs = _retry_with_artifact({"out/report.txt": ART}, {})
    d = ev(rs, resolver=resolver)
    assert d["verdict"] == "APPROVE"
    assert d["reasons"] == []
    assert hash_of(second) in d["required_receipt_hashes"]


def test_older_attempt_with_artifacts_needs_no_resolver():
    _, _, rs = _retry_with_artifact({"out/report.txt": ART}, {})
    d = ev(rs)  # no resolver at all
    assert d["verdict"] == "APPROVE"
    assert "no artifact_resolver" not in reasons_text(d)


def test_resolver_is_not_consulted_for_older_attempts():
    calls = []
    _, _, rs = _retry_with_artifact({"out/old.txt": ART}, {})
    d = ev(rs, resolver=lambda p: calls.append(p) or "b" * 64)
    assert d["verdict"] == "APPROVE" and calls == []


def test_artifact_mismatch_on_the_deciding_attempt_is_hard_and_slot_unmet():
    _, second, rs = _retry_with_artifact({}, {"out/report.txt": ART})
    d = ev(rs, resolver=lambda p: "b" * 64)
    assert d["verdict"] == "MODIFY"
    assert f"receipt {second['receipt_id']} artifact 'out/report.txt' digest mismatch" in reasons_text(d)
    assert "slot 'tests' latest attempt 2 rejected: artifact check failed" in d["reasons"]
    assert d["acceptance_unmet"] == ["AC-1"]
    assert hash_of(second) not in d["required_receipt_hashes"]
    assert ev(rs, resolver=lambda p: "b" * 64, waiver=broad_waiver())["verdict"] == "MODIFY"


def test_artifact_on_the_deciding_attempt_without_resolver_is_denied_but_matching_resolver_approves():
    _, second, rs = _retry_with_artifact({}, {"out/report.txt": ART})
    assert "artifact digests present but no artifact_resolver" in ev(rs)["reasons"]
    d = ev(rs, resolver=lambda p: ART)
    assert d["verdict"] == "APPROVE"
    assert hash_of(second) in d["required_receipt_hashes"]


def test_stale_deciding_receipt_is_not_artifact_checked():
    calls = []
    stale = receipt("TestRun", candidate_head=HEAD2, artifact_digests={"out/report.txt": ART})
    d = ev([stale, receipt("StaticAnalysis"), receipt("IndependentReview")],
           resolver=lambda p: calls.append(p) or "b" * 64)
    assert d["verdict"] == "MODIFY"
    assert "stale head" in reasons_text(d)
    assert "digest mismatch" not in reasons_text(d) and calls == []


# ---- artifact keys through the gate


@pytest.mark.parametrize("key", ["../x", "a/../b", "/abs/x", "C:/x", "C:\\x", "a//b"])
def test_receipt_with_non_repo_relative_artifact_key_is_invalid_in_the_gate(key):
    calls = []
    bad = receipt("TestRun", artifact_digests={key: ART})
    d = ev([bad, receipt("StaticAnalysis"), receipt("IndependentReview")],
           resolver=lambda p: calls.append(p) or ART)
    assert d["verdict"] == "MODIFY"
    assert "receipt[0] invalid" in reasons_text(d) and "artifact_digests" in reasons_text(d)
    assert "missing receipt for slot 'tests'" in d["reasons"]
    assert calls == []  # the resolver never sees an escaping path


# ---- keys must be pairwise distinct


def _no_go_for_keys(d, *messages):
    assert d["verdict"] == "NO_GO"
    for message in messages:
        assert message in d["reasons"]
    assert d["required_receipt_hashes"] == []
    assert d["acceptance_unmet"] == ["AC-1", "AC-2"]
    assert d["waiver_record"] is None and d["human_approvals"] == []
    c.validate_gate_decision(d)


def test_key_equal_to_supervisor_key_is_no_go_even_with_otherwise_valid_receipts():
    rs = [receipt("TestRun", key=KEY), receipt("StaticAnalysis", key=KEY), receipt("IndependentReview", key=KEY)]
    d = ev(rs, key=KEY, supervisor_key=KEY)
    _no_go_for_keys(d, "keys must be pairwise distinct: key equals supervisor_key")


def test_key_equal_to_operator_key_is_no_go():
    d = ev(happy_receipts(), key=OPERATOR_KEY, operator_key=OPERATOR_KEY)
    _no_go_for_keys(d, "keys must be pairwise distinct: key equals operator_key")


def test_supervisor_key_equal_to_operator_key_is_no_go():
    d = ev(happy_receipts(), supervisor_key=OPERATOR_KEY, operator_key=OPERATOR_KEY)
    _no_go_for_keys(d, "keys must be pairwise distinct: supervisor_key equals operator_key")


def test_all_three_keys_equal_reports_every_colliding_pair():
    d = ev(happy_receipts(), key=KEY, supervisor_key=KEY, operator_key=KEY)
    _no_go_for_keys(
        d,
        "keys must be pairwise distinct: key equals supervisor_key",
        "keys must be pairwise distinct: key equals operator_key",
        "keys must be pairwise distinct: supervisor_key equals operator_key",
    )


def test_bytearray_key_equal_to_bytes_key_is_a_collision():
    d = ev(happy_receipts(), key=bytearray(SUPERVISOR_KEY), supervisor_key=SUPERVISOR_KEY)
    _no_go_for_keys(d, "keys must be pairwise distinct: key equals supervisor_key")
    d2 = ev(happy_receipts(), supervisor_key=bytearray(OPERATOR_KEY), operator_key=OPERATOR_KEY)
    _no_go_for_keys(d2, "keys must be pairwise distinct: supervisor_key equals operator_key")


def test_equal_keys_cannot_be_rescued_by_a_waiver():
    d = ev(not_run_tests(), key=OPERATOR_KEY, operator_key=OPERATOR_KEY, waiver=broad_waiver())
    assert d["verdict"] == "NO_GO"
    assert d["waiver_record"] is None and d["human_approvals"] == []


def test_operator_key_none_is_allowed_when_worker_and_supervisor_keys_differ():
    d = ev(happy_receipts(), operator_key=None)
    assert d["verdict"] == "APPROVE"
    assert not any("pairwise distinct" in r for r in d["reasons"])


def test_operator_key_none_does_not_hide_a_worker_supervisor_collision():
    d = ev(happy_receipts(), key=SUPERVISOR_KEY, operator_key=None)
    assert d["verdict"] == "NO_GO"
    assert "keys must be pairwise distinct: key equals supervisor_key" in d["reasons"]
    assert not any("operator_key" in r and "pairwise" in r for r in d["reasons"])


def test_keys_differing_in_one_byte_are_distinct():
    near = KEY[:-1] + bytes([KEY[-1] ^ 1])
    assert near != KEY and len(near) == len(KEY)
    d = ev(happy_receipts(), supervisor_key=near)
    assert d["verdict"] == "APPROVE"
    assert not any("pairwise distinct" in r for r in d["reasons"])


def test_invalid_manifest_still_reports_no_go_when_keys_collide():
    d = ev(happy_receipts(), m=manifest(extra=1), key=KEY, supervisor_key=KEY)
    assert d["verdict"] == "NO_GO"
    assert "manifest invalid" in reasons_text(d)
