"""E1 contracts: strict validators, derive_result, canonical form, GateDecision."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json

import pytest

from tools.vst import contracts as c
from tools.vst import signing

from .e1e4_helpers import (
    HEAD,
    KEY,
    MANIFEST_SHA,
    OPERATOR_KEY,
    SUPERVISOR_KEY,
    WRONG_KEY,
    doc_manifest,
    manifest,
    mhash,
    receipt,
    supervisor_receipt,
    unsigned_receipt,
)

ContractError = c.ContractError


# ------------------------------------------------------------------ manifest


def test_manifest_valid_returns_equal_deep_copy():
    m = manifest()
    out = c.validate_task_manifest(m)
    assert out == m
    out["scope"].append("x/y")
    out["required_receipts"][0]["slot"] = "changed"
    out["required_tests"][0]["acceptance"].append("zzz")
    out["allowed_commands"][0]["argv"].append("--zzz")
    out["required_rules"][0]["rule_id"] = "changed"
    assert m == manifest()  # input untouched, copy independent


@pytest.mark.parametrize("field", sorted(c.MANIFEST_FIELDS))
def test_manifest_missing_each_field_rejected(field):
    m = manifest()
    del m[field]
    with pytest.raises(ContractError, match=field):
        c.validate_task_manifest(m)


def test_manifest_unknown_field_rejected():
    m = manifest(extra_field=1)
    with pytest.raises(ContractError, match="extra_field"):
        c.validate_task_manifest(m)


@pytest.mark.parametrize("bad", [None, [], "x", 5])
def test_manifest_non_dict_rejected(bad):
    with pytest.raises(ContractError):
        c.validate_task_manifest(bad)


@pytest.mark.parametrize(
    "field,value",
    [
        ("phase", True),
        ("phase", 0),
        ("phase", 11),
        ("phase", "4"),
        ("phase", 4.0),
        ("timeout_sec", True),
        ("timeout_sec", 0),
        ("timeout_sec", -1),
        ("cost_cap", True),
        ("cost_cap", -1),
        ("retry_cap", False),
        ("retry_cap", -1),
        ("retry_cap", 1.5),
        ("task_id", ""),
        ("task_id", "   "),
        ("task_id", 5),
        ("project_id", ""),
        ("story_id", None),
        ("owner_role", ""),
        ("model_policy", ""),
        ("base_head", "a" * 39),
        ("base_head", "A" * 40),
        ("base_head", "g" * 40),
        ("role_sha256", "c" * 63),
        ("role_sha256", "C" * 64),
    ],
)
def test_manifest_wrong_scalar_rejected(field, value):
    with pytest.raises(ContractError, match=field):
        c.validate_task_manifest(manifest(**{field: value}))


def test_manifest_boundary_values_accepted():
    for phase in (1, 10):
        c.validate_task_manifest(manifest(phase=phase))
    c.validate_task_manifest(manifest(cost_cap=0, retry_cap=0, timeout_sec=1))
    c.validate_task_manifest(manifest(forbidden_actions=[], tools=[], skills=[]))


@pytest.mark.parametrize(
    "path",
    [
        "..",
        "../x",
        "a/../b",
        "a\\..\\b",
        "/etc/passwd",
        "\\share\\x",
        "C:/x",
        "C:\\x",
        "C:x",
        "a:b",
        "a//b",
        "src/",
        "./a",
        "a/./b",
        ".",
        "",
        " a",
        "a ",
    ],
)
def test_manifest_bad_scope_path_rejected(path):
    with pytest.raises(ContractError, match="scope"):
        c.validate_task_manifest(manifest(scope=[path]))


@pytest.mark.parametrize("path", ["src/app.py", "a-b/c.d", "file", "dir\\file.txt", "..hidden/x", "a/.b"])
def test_manifest_good_scope_path_accepted(path):
    c.validate_task_manifest(manifest(scope=[path]))


def test_manifest_scope_empty_duplicate_or_nonlist_rejected():
    for bad in ([], ["a", "a"], "a", None):
        with pytest.raises(ContractError, match="scope"):
            c.validate_task_manifest(manifest(scope=bad))


def test_manifest_lists_of_strings_enforced():
    with pytest.raises(ContractError, match="forbidden_actions"):
        c.validate_task_manifest(manifest(forbidden_actions=["a", "a"]))
    with pytest.raises(ContractError, match="tools"):
        c.validate_task_manifest(manifest(tools=[""]))
    with pytest.raises(ContractError, match="tools"):
        c.validate_task_manifest(manifest(tools=[1]))


def test_manifest_acceptance_rules():
    for bad in ([], ["AC-1", "AC-1"], [""], "AC-1"):
        with pytest.raises(ContractError, match="acceptance"):
            c.validate_task_manifest(manifest(acceptance=bad))


def test_manifest_duplicate_ids_rejected_for_slots_and_skills():
    dup_slots = [
        {"slot": "tests", "receipt_type": "TestRun"},
        {"slot": "tests", "receipt_type": "StaticAnalysis"},
    ]
    with pytest.raises(ContractError, match="duplicate slot"):
        c.validate_task_manifest(manifest(required_receipts=dup_slots))
    dup_skills = [{"id": "s", "sha256": "d" * 64}, {"id": "s", "sha256": "e" * 64}]
    with pytest.raises(ContractError, match="duplicate skill"):
        c.validate_task_manifest(manifest(skills=dup_skills))


def test_manifest_zero_required_receipts_rejected():
    with pytest.raises(ContractError, match="required_receipts"):
        c.validate_task_manifest(manifest(required_receipts=[]))
    with pytest.raises(ContractError, match="required_receipts"):
        c.validate_task_manifest(manifest(required_receipts=None))


@pytest.mark.parametrize(
    "slot",
    [
        {"slot": "x", "receipt_type": "Nope"},
        {"slot": "x", "receipt_type": "testrun"},
        {"slot": "", "receipt_type": "TestRun"},
        {"slot": "x"},
        {"slot": "x", "receipt_type": "TestRun", "extra": 1},
        "tests",
    ],
)
def test_manifest_bad_required_receipt_entry_rejected(slot):
    with pytest.raises(ContractError):
        c.validate_task_manifest(manifest(required_receipts=[slot]))


@pytest.mark.parametrize(
    "skill",
    [
        {"id": "", "sha256": "d" * 64},
        {"id": "s", "sha256": "d" * 63},
        {"id": "s"},
        {"id": "s", "sha256": "d" * 64, "x": 1},
    ],
)
def test_manifest_bad_skill_rejected(skill):
    with pytest.raises(ContractError):
        c.validate_task_manifest(manifest(skills=[skill]))


# ------------------------------------------------------------------ receipts


@pytest.mark.parametrize("rtype", sorted(c.RECEIPT_TYPES))
def test_receipt_valid_each_type_returns_deep_copy(rtype):
    r = receipt(rtype)
    out = c.validate_receipt(r)
    assert out == r
    out["covered_acceptance"].append("zzz")
    assert "zzz" not in r["covered_acceptance"]


@pytest.mark.parametrize("rtype", sorted(c.RECEIPT_TYPES))
def test_receipt_missing_each_field_rejected(rtype):
    base = receipt(rtype)
    for field in sorted(base):
        r = copy.deepcopy(base)
        del r[field]
        with pytest.raises(ContractError):
            c.validate_receipt(r)


@pytest.mark.parametrize("rtype", sorted(c.RECEIPT_TYPES))
def test_receipt_unknown_field_rejected(rtype):
    r = receipt(rtype)
    r["reason"] = "WORKER_LOST"
    with pytest.raises(ContractError, match="reason"):
        c.validate_receipt(r)


@pytest.mark.parametrize("bad", [None, "x", ["TestRun"], 5, ["a"], {}])
def test_receipt_bad_type_value_rejected(bad):
    r = receipt()
    r["receipt_type"] = bad
    with pytest.raises(ContractError, match="receipt_type"):
        c.validate_receipt(r)


def test_receipt_non_dict_rejected():
    for bad in (None, [], "x"):
        with pytest.raises(ContractError):
            c.validate_receipt(bad)


@pytest.mark.parametrize(
    "field,value",
    [
        ("result", "pass"),
        ("result", "SKIPPED"),
        ("result", True),
        ("result", None),
        ("attempt", True),
        ("attempt", 0),
        ("attempt", "1"),
        ("attempt", 1.0),
        ("epoch", True),
        ("epoch", 0),
        ("epoch", 1.5),
        ("candidate_head", "a" * 39),
        ("candidate_head", "A" * 40),
        ("role_sha256", "c" * 65),
        ("manifest_sha256", "a" * 63),
        ("manifest_sha256", "A" * 64),
        ("manifest_sha256", "g" * 64),
        ("manifest_sha256", None),
        ("manifest_sha256", ""),
        ("signature", "a" * 63),
        ("signature", "A" * 64),
        ("signature", None),
        ("receipt_id", ""),
        ("task_id", " "),
        ("slot", ""),
        ("runner_id", 3),
        ("resolved_model", ""),
        ("invocation_id", None),
        ("created_at", ""),
    ],
)
def test_receipt_wrong_common_value_rejected(field, value):
    r = receipt()
    r[field] = value
    with pytest.raises(ContractError, match=field):
        c.validate_receipt(r)


def test_receipt_prev_hash_null_iff_attempt_one():
    r = receipt(attempt=1, prev_receipt_sha256="e" * 64)
    with pytest.raises(ContractError, match="prev_receipt_sha256"):
        c.validate_receipt(r)
    r = receipt(attempt=2, prev_receipt_sha256=None)
    with pytest.raises(ContractError, match="prev_receipt_sha256"):
        c.validate_receipt(r)
    r = receipt(attempt=2, prev_receipt_sha256="E" * 64)
    with pytest.raises(ContractError, match="prev_receipt_sha256"):
        c.validate_receipt(r)
    c.validate_receipt(receipt(attempt=2, prev_receipt_sha256="e" * 64))


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_test_ids", "t1"),
        ("executed_test_ids", [""]),
        ("skipped_test_ids", [1]),
        ("xfail_test_ids", None),
        ("covered_acceptance", [None]),
        ("commands", []),
        ("commands", None),
        ("commands", [{"argv": [], "exit_code": 0}]),
        ("commands", [{"argv": ["x"], "exit_code": True}]),
        ("commands", [{"argv": ["x"], "exit_code": "0"}]),
        ("commands", [{"argv": ["x"]}]),
        ("commands", [{"argv": ["x"], "exit_code": 0, "extra": 1}]),
        ("commands", [{"argv": [""], "exit_code": 0}]),
        ("commands", ["x"]),
    ],
)
def test_testrun_bad_field_rejected(field, value):
    r = receipt("TestRun")
    r[field] = value
    with pytest.raises(ContractError, match=field):
        c.validate_receipt(r)


def test_testrun_negative_exit_code_is_a_valid_integer():
    r = receipt("TestRun", commands=[{"argv": ["x"], "exit_code": -2}])
    assert c.validate_receipt(r)["commands"][0]["exit_code"] == -2


@pytest.mark.parametrize(
    "rtype,field,value",
    [
        ("StaticAnalysis", "coverage", "full"),
        ("StaticAnalysis", "coverage", None),
        ("StaticAnalysis", "covered_rules", "R1"),
        ("StaticAnalysis", "unsupported_rules", [1]),
        ("IndependentReview", "signed_verdict", "APPROVED_WITH_WAIVER"),
        ("IndependentReview", "signed_verdict", "PASS"),
        ("IndependentReview", "reviewer_principal", ""),
        ("IndependentReview", "author_principal", None),
        ("IndependentReview", "findings", [""]),
        ("Documentation", "check_description", ""),
        ("Documentation", "check_description", None),
        ("Documentation", "covered_acceptance", "AC-1"),
    ],
)
def test_other_types_bad_field_rejected(rtype, field, value):
    r = receipt(rtype)
    r[field] = value
    with pytest.raises(ContractError, match=field):
        c.validate_receipt(r)


def test_receipt_type_specific_fields_not_interchangeable():
    r = receipt("Documentation")
    r["coverage"] = "FULL"
    with pytest.raises(ContractError, match="coverage"):
        c.validate_receipt(r)


# -------------------------------------------------------------- derive_result


def _tr(**kw):
    return unsigned_receipt("TestRun", result="FAIL", **kw)


def test_derive_testrun_pass_when_everything_matches():
    assert c.derive_result(_tr()) == "PASS"


def test_derive_testrun_zero_executed_is_inconclusive_even_with_failing_exit():
    r = _tr(executed_test_ids=[], commands=[{"argv": ["x"], "exit_code": 1}])
    assert c.derive_result(r) == "INCONCLUSIVE"
    assert c.derive_result(_tr(executed_test_ids=[], expected_test_ids=[])) == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "overrides",
    [
        {"skipped_test_ids": ["t3"]},
        {"xfail_test_ids": ["t2"]},
        {"commands": [{"argv": ["x"], "exit_code": 1}]},
        {"commands": [{"argv": ["x"], "exit_code": 0}, {"argv": ["y"], "exit_code": 5}]},
        {"commands": [{"argv": ["x"], "exit_code": -1}]},
        {"expected_test_ids": []},
        {"executed_test_ids": ["t1"]},
        {"executed_test_ids": ["t1", "t2", "t3"]},
        {"executed_test_ids": ["t1", "other"]},
    ],
)
def test_derive_testrun_fail_cases(overrides):
    assert c.derive_result(_tr(**overrides)) == "FAIL"


def test_derive_testrun_id_order_irrelevant():
    assert c.derive_result(_tr(executed_test_ids=["t2", "t1"])) == "PASS"


def test_derive_static_analysis():
    def sa(**kw):
        return unsigned_receipt("StaticAnalysis", result="FAIL", **kw)

    assert c.derive_result(sa()) == "PASS"
    assert c.derive_result(sa(coverage="PARTIAL")) == "INCONCLUSIVE"
    assert c.derive_result(sa(coverage="NOT_COVERED")) == "INCONCLUSIVE"
    assert c.derive_result(sa(unsupported_rules=["R9"])) == "INCONCLUSIVE"


def test_derive_static_analysis_full_coverage_without_covered_rules_is_not_pass():
    # FULL coverage claimed but no rule was actually covered: vacuous, never PASS.
    r = unsigned_receipt("StaticAnalysis", result="FAIL", covered_rules=[])
    assert r["coverage"] == "FULL" and r["unsupported_rules"] == []
    assert c.derive_result(r) == "INCONCLUSIVE"
    claimed = unsigned_receipt("StaticAnalysis", result="PASS", covered_rules=[])
    assert c.derive_result(claimed) == "INCONCLUSIVE" != claimed["result"]


def test_derive_independent_review():
    def rv(**kw):
        return unsigned_receipt("IndependentReview", result="PASS", **kw)

    assert c.derive_result(rv()) == "PASS"
    assert c.derive_result(rv(signed_verdict="MODIFY")) == "FAIL"
    assert c.derive_result(rv(signed_verdict="NO_GO")) == "FAIL"
    assert c.derive_result(rv(reviewer_principal="same", author_principal="same")) == "FAIL"


@pytest.mark.parametrize(
    "reviewer,author",
    [
        ("Author-Y ", "author-y"),
        ("author-y", " AUTHOR-Y"),
        ("  same  ", "same"),  # a tab here would now be rejected (Cc), see principals below
        ("SAME", "same"),
        ("ＳＡＭＥ", "same"),  # full-width forms are folded by NFKC before the comparison
        ("same　", "same"),  # ideographic space is stripped after NFKC
        ("Straße", "STRASSE"),  # casefold, not just lower
    ],
)
def test_derive_review_compares_normalized_principals(reviewer, author):
    r = unsigned_receipt(
        "IndependentReview", result="PASS", reviewer_principal=reviewer, author_principal=author
    )
    assert c.derive_result(r) == "FAIL"


def test_derive_review_distinct_principals_after_normalization_pass():
    r = unsigned_receipt(
        "IndependentReview", result="FAIL", reviewer_principal=" Reviewer-X ", author_principal="author-y"
    )
    assert c.derive_result(r) == "PASS"


def test_derive_documentation_keeps_pass_and_fail_only():
    def doc(result):
        return unsigned_receipt("Documentation", result=result)

    assert c.derive_result(doc("PASS")) == "PASS"
    assert c.derive_result(doc("FAIL")) == "FAIL"


@pytest.mark.parametrize("rtype", sorted(c.RECEIPT_TYPES))
@pytest.mark.parametrize("given", sorted(c.NON_APPROVING_RESULTS))
def test_derive_non_approving_results_accepted_as_given(rtype, given):
    # Even for evidence that would otherwise derive PASS (or FAIL).
    assert c.derive_result(unsigned_receipt(rtype, result=given)) == given


def test_derive_given_pass_or_fail_is_compared_with_computed_value():
    bad = unsigned_receipt("TestRun", result="PASS", skipped_test_ids=["t9"])
    assert c.derive_result(bad) == "FAIL" != bad["result"]
    good_but_fail = unsigned_receipt("TestRun", result="FAIL")
    assert c.derive_result(good_but_fail) == "PASS" != good_but_fail["result"]


def test_derive_unknown_type_raises():
    with pytest.raises(ContractError):
        c.derive_result({"receipt_type": "Bogus", "result": "PASS"})


def test_derive_unknown_type_with_non_approving_result_returns_given():
    # Documented rule 'applied first' for every type.
    assert c.derive_result({"receipt_type": "Bogus", "result": "NOT_RUN"}) == "NOT_RUN"


# ------------------------------------------------------------ canonical + hash


def test_canonical_bytes_exact_form():
    assert c.canonical_bytes({"b": 1, "a": [1, 2]}) == b'{"a":[1,2],"b":1}'
    assert c.canonical_bytes({"k": "\u00e9"}) == b'{"k":"\\u00e9"}'
    assert c.canonical_bytes(None) == b"null"


def test_canonical_bytes_key_order_independent():
    a = {"x": 1, "y": {"p": 1, "q": 2}}
    b = {"y": {"q": 2, "p": 1}, "x": 1}
    assert c.canonical_bytes(a) == c.canonical_bytes(b)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {1, 2}, object(), {"k": b"x"}])
def test_canonical_bytes_unserialisable_raises_contract_error(bad):
    with pytest.raises(ContractError):
        c.canonical_bytes(bad)


def test_receipt_sha256_matches_independent_computation_and_is_stable():
    r = receipt()
    expected = hashlib.sha256(
        json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    assert c.receipt_sha256(r) == expected
    assert c.receipt_sha256(r) == c.receipt_sha256(copy.deepcopy(r))
    reordered = dict(reversed(list(r.items())))
    assert c.receipt_sha256(reordered) == expected
    assert len(expected) == 64


def _mutate(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return value + "x"
    if isinstance(value, list):
        return value + ["extra"]
    if isinstance(value, dict):
        return {**value, "extra-path": "a" * 64}
    if value is None:
        return "x"
    raise AssertionError(type(value))


@pytest.mark.parametrize("rtype", sorted(c.RECEIPT_TYPES))
def test_receipt_sha256_sensitive_to_every_field(rtype):
    r = receipt(rtype, attempt=2, prev_receipt_sha256="e" * 64)
    base = c.receipt_sha256(r)
    for field in r:
        changed = copy.deepcopy(r)
        changed[field] = _mutate(changed[field])
        assert c.receipt_sha256(changed) != base, field


def test_receipt_sha256_sensitive_to_nested_command_fields():
    r = receipt()
    base = c.receipt_sha256(r)
    r2 = copy.deepcopy(r)
    r2["commands"][0]["exit_code"] = 1
    r3 = copy.deepcopy(r)
    r3["commands"][0]["argv"][0] = "other"
    assert len({base, c.receipt_sha256(r2), c.receipt_sha256(r3)}) == 3


def test_receipt_sha256_includes_signature():
    r = receipt()
    other = dict(r, signature="f" * 64)
    assert c.receipt_sha256(r) != c.receipt_sha256(other)


# -------------------------------------------------------------- GateDecision


def _decision(**kw):
    d = {
        "task_id": "T1",
        "candidate_head": HEAD,
        "epoch": 2,
        "required_receipt_hashes": ["a" * 64],
        "unresolved_findings": [],
        "human_approvals": [],
        "verdict": "MODIFY",
        "waiver_record": None,
        "acceptance_unmet": ["AC-1"],
        "reasons": ["r"],
    }
    d.update(kw)
    return d


def test_gate_decision_valid_and_deep_copy():
    d = _decision()
    out = c.validate_gate_decision(d)
    assert out == d
    out["reasons"].append("z")
    assert d["reasons"] == ["r"]


@pytest.mark.parametrize("field", sorted(c.GATE_DECISION_FIELDS))
def test_gate_decision_missing_field_rejected(field):
    d = _decision()
    del d[field]
    with pytest.raises(ContractError, match=field):
        c.validate_gate_decision(d)


def test_gate_decision_unknown_field_and_enum_rejected():
    with pytest.raises(ContractError, match="zzz"):
        c.validate_gate_decision(_decision(zzz=1))
    with pytest.raises(ContractError, match="verdict"):
        c.validate_gate_decision(_decision(verdict="GO"))


@pytest.mark.parametrize(
    "kw",
    [
        {"epoch": True},
        {"epoch": -1},
        {"task_id": 5},
        {"candidate_head": None},
        {"required_receipt_hashes": ["abc"]},
        {"required_receipt_hashes": "x"},
        {"unresolved_findings": [""]},
        {"human_approvals": [1]},
        {"acceptance_unmet": "AC-1"},
        {"reasons": [None]},
    ],
)
def test_gate_decision_bad_values_rejected(kw):
    with pytest.raises(ContractError):
        c.validate_gate_decision(_decision(**kw))


def test_gate_decision_allows_empty_echo_strings_and_epoch_zero():
    # NO_GO must be emittable for malformed gate inputs.
    out = c.validate_gate_decision(_decision(task_id="", candidate_head="zz", epoch=0, verdict="NO_GO"))
    assert out["epoch"] == 0


def test_gate_decision_waiver_record_iff_approved_with_waiver():
    ok = _decision(verdict="APPROVED_WITH_WAIVER", waiver_record="W-1")
    assert c.validate_gate_decision(ok)["waiver_record"] == "W-1"
    for bad in (None, "", "  ", 5):
        with pytest.raises(ContractError, match="waiver_record"):
            c.validate_gate_decision(_decision(verdict="APPROVED_WITH_WAIVER", waiver_record=bad))
    for verdict in ("MODIFY", "NO_GO", "APPROVE"):
        with pytest.raises(ContractError, match="waiver_record"):
            c.validate_gate_decision(
                _decision(verdict=verdict, waiver_record="W-1", reasons=[], acceptance_unmet=[])
            )


def test_gate_decision_approve_requires_no_reasons_and_no_unmet():
    c.validate_gate_decision(_decision(verdict="APPROVE", reasons=[], acceptance_unmet=[]))
    with pytest.raises(ContractError, match="APPROVE"):
        c.validate_gate_decision(_decision(verdict="APPROVE", reasons=["x"], acceptance_unmet=[]))
    with pytest.raises(ContractError, match="APPROVE"):
        c.validate_gate_decision(_decision(verdict="APPROVE", reasons=[], acceptance_unmet=["AC-1"]))
    # Waiver verdict may carry reasons (the waived gaps).
    c.validate_gate_decision(
        _decision(verdict="APPROVED_WITH_WAIVER", waiver_record="W", reasons=["gap"])
    )


def test_validate_manifest_with_documentation_slot_fixture_is_valid():
    assert c.validate_task_manifest(doc_manifest())["required_receipts"][1]["slot"] == "doc"


# ------------------------------------------------------- artifact_digests


ZERO = c.MISSING_ARTIFACT_DIGEST


def test_artifact_digests_missing_field_rejected_by_name():
    r = receipt("TestRun")
    del r["artifact_digests"]
    with pytest.raises(ContractError, match="artifact_digests"):
        c.validate_receipt(r)


def test_artifact_digests_valid_values_accepted_and_deep_copied():
    r = receipt("TestRun", artifact_digests={"out/a.bin": "a" * 64, "b.txt": "b" * 64})
    out = c.validate_receipt(r)
    assert out["artifact_digests"] == r["artifact_digests"]
    out["artifact_digests"]["new"] = "c" * 64
    assert "new" not in r["artifact_digests"]


@pytest.mark.parametrize("bad", [None, [], "x", [("a", "b" * 64)], 5])
def test_artifact_digests_non_dict_rejected(bad):
    r = receipt("TestRun")
    r["artifact_digests"] = bad
    with pytest.raises(ContractError, match="artifact_digests"):
        c.validate_receipt(r)


@pytest.mark.parametrize("key", ["", "   "])
def test_artifact_digests_empty_key_rejected(key):
    r = receipt("TestRun")
    r["artifact_digests"] = {key: "a" * 64}
    with pytest.raises(ContractError, match="artifact_digests"):
        c.validate_receipt(r)


@pytest.mark.parametrize(
    "key",
    [
        "../x",
        "..",
        "a/../b",
        "a\\..\\b",
        "out/..",
        "/abs/x.bin",
        "\\abs\\x.bin",
        "C:/x.bin",
        "C:\\x.bin",
        "c:x.bin",
        "out/a:b",
        "a//b",
        "a\\\\b",
        "out/",
        "a/./b",
        "./a",
        " out/a.bin",
        "out/a.bin ",
    ],
)
def test_artifact_digests_key_must_be_a_repo_relative_path(key):
    r = receipt("TestRun")
    r["artifact_digests"] = {key: "a" * 64}
    with pytest.raises(ContractError, match="artifact_digests"):
        c.validate_receipt(r)


def test_artifact_digests_one_bad_key_rejects_the_whole_receipt():
    r = receipt("TestRun")
    r["artifact_digests"] = {"out/ok.bin": "a" * 64, "../evil": "b" * 64}
    with pytest.raises(ContractError, match="artifact_digests"):
        c.validate_receipt(r)


@pytest.mark.parametrize("key", ["report.txt", "out/report.txt", "out/sub/dir/r.bin", "a b/c d.txt", "out\\win.bin", "v1..2/x"])
def test_artifact_digests_repo_relative_keys_are_accepted(key):
    r = receipt("TestRun", artifact_digests={key: "a" * 64})
    assert c.validate_receipt(r)["artifact_digests"] == {key: "a" * 64}


@pytest.mark.parametrize("value", ["a" * 63, "a" * 65, "A" * 64, "g" * 64, "", None, 5, ["a" * 64]])
def test_artifact_digests_non_hex_value_rejected(value):
    r = receipt("TestRun")
    r["artifact_digests"] = {"f.bin": value}
    with pytest.raises(ContractError, match="artifact_digests"):
        c.validate_receipt(r)


def test_zero_digest_is_a_valid_value_but_derives_fail():
    r = unsigned_receipt("TestRun", result="PASS", artifact_digests={"gone.bin": ZERO})
    assert ZERO == "0" * 64
    c.validate_receipt(dict(r, signature="a" * 64))
    assert c.derive_result(r) == "FAIL"


def test_zero_digest_fails_even_when_everything_else_passes_and_when_nothing_executed():
    ok = unsigned_receipt("TestRun", result="FAIL", artifact_digests={"a": "b" * 64})
    assert c.derive_result(ok) == "PASS"
    one_missing = unsigned_receipt("TestRun", result="FAIL", artifact_digests={"a": "b" * 64, "z": ZERO})
    assert c.derive_result(one_missing) == "FAIL"
    none_run = unsigned_receipt("TestRun", result="FAIL", executed_test_ids=[], artifact_digests={"z": ZERO})
    assert c.derive_result(none_run) == "FAIL"


def test_zero_digest_with_given_non_approving_result_is_accepted_as_given():
    r = unsigned_receipt("TestRun", result="NOT_RUN", artifact_digests={"z": ZERO})
    assert c.derive_result(r) == "NOT_RUN"


def test_receipt_sha256_sensitive_to_artifact_digest_value():
    a = receipt("TestRun", artifact_digests={"f": "a" * 64})
    b = receipt("TestRun", artifact_digests={"f": "b" * 64})
    assert c.receipt_sha256(a) != c.receipt_sha256(b)


# ============================================================================
# Remediation A: manifest binding fields, reserved slot, hashes, principals
# ============================================================================


@pytest.mark.parametrize(
    "field",
    ["author_principal", "required_tests", "allowed_commands", "required_rules"],
)
def test_manifest_new_required_field_missing_is_rejected_by_name(field):
    m = manifest()
    del m[field]
    with pytest.raises(ContractError, match=field):
        c.validate_task_manifest(m)


@pytest.mark.parametrize("value", ["", "   ", "\t\n", None, 5, ["a"]])
def test_manifest_author_principal_must_be_non_blank_string(value):
    with pytest.raises(ContractError, match="author_principal"):
        c.validate_task_manifest(manifest(author_principal=value))


def test_manifest_author_principal_is_stored_verbatim_not_normalized():
    out = c.validate_task_manifest(manifest(author_principal="  Author-Y "))
    assert out["author_principal"] == "  Author-Y "


@pytest.mark.parametrize("bad", [None, "x", {}, 5])
@pytest.mark.parametrize("field", ["required_tests", "allowed_commands", "required_rules"])
def test_manifest_new_list_fields_must_be_lists(field, bad):
    with pytest.raises(ContractError, match=field):
        c.validate_task_manifest(manifest(**{field: bad}))


@pytest.mark.parametrize(
    "item",
    [
        {"slot": "tests", "test_id": "t1"},  # missing acceptance
        {"slot": "tests", "acceptance": ["AC-1"]},  # missing test_id
        {"test_id": "t1", "acceptance": ["AC-1"]},  # missing slot
        {"slot": "tests", "test_id": "t1", "acceptance": ["AC-1"], "extra": 1},
        {"slot": "tests", "test_id": "", "acceptance": ["AC-1"]},
        {"slot": "tests", "test_id": "t1", "acceptance": []},  # must cover something
        {"slot": "tests", "test_id": "t1", "acceptance": ["AC-9"]},  # not in manifest acceptance
        {"slot": "tests", "test_id": "t1", "acceptance": "AC-1"},
        {"slot": "ghost", "test_id": "t1", "acceptance": ["AC-1"]},  # unknown slot
        {"slot": "static", "test_id": "t1", "acceptance": ["AC-1"]},  # not a TestRun slot
        {"slot": "review", "test_id": "t1", "acceptance": ["AC-1"]},
        "t1",
    ],
)
def test_manifest_bad_required_test_entry_rejected(item):
    good = manifest()["required_tests"]
    with pytest.raises(ContractError, match="required_tests"):
        c.validate_task_manifest(manifest(required_tests=good + [item]))


def test_manifest_duplicate_test_id_in_same_slot_rejected_but_allowed_across_slots():
    dup = [
        {"slot": "tests", "test_id": "t1", "acceptance": ["AC-1"]},
        {"slot": "tests", "test_id": "t1", "acceptance": ["AC-2"]},
    ]
    with pytest.raises(ContractError, match="duplicate test id"):
        c.validate_task_manifest(manifest(required_tests=dup))
    two_slots = [
        {"slot": "tests", "test_id": "t1", "acceptance": ["AC-1"]},
        {"slot": "tests2", "test_id": "t1", "acceptance": ["AC-2"]},
    ]
    m = manifest(
        required_receipts=[
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "tests2", "receipt_type": "TestRun"},
            {"slot": "review", "receipt_type": "IndependentReview"},
        ],
        required_tests=two_slots,
        allowed_commands=[
            {"slot": "tests", "argv": ["pytest"]},
            {"slot": "tests2", "argv": ["pytest", "-x"]},
        ],
        required_rules=[],
    )
    assert c.validate_task_manifest(m) == m


@pytest.mark.parametrize(
    "item",
    [
        {"slot": "tests"},  # missing argv
        {"argv": ["pytest"]},  # missing slot
        {"slot": "tests", "argv": []},
        {"slot": "tests", "argv": [""]},
        {"slot": "tests", "argv": [1]},
        {"slot": "tests", "argv": "pytest -q"},
        {"slot": "tests", "argv": ["pytest"], "extra": 1},
        {"slot": "ghost", "argv": ["pytest"]},
        {"slot": "static", "argv": ["pytest"]},  # not a TestRun slot
        ["pytest"],
    ],
)
def test_manifest_bad_allowed_command_rejected(item):
    good = manifest()["allowed_commands"]
    with pytest.raises(ContractError, match="allowed_commands"):
        c.validate_task_manifest(manifest(allowed_commands=good + [item]))


@pytest.mark.parametrize(
    "item",
    [
        {"slot": "static"},  # missing rule_id
        {"rule_id": "R2"},  # missing slot
        {"slot": "static", "rule_id": ""},
        {"slot": "static", "rule_id": 3},
        {"slot": "static", "rule_id": "R2", "extra": 1},
        {"slot": "ghost", "rule_id": "R2"},
        {"slot": "tests", "rule_id": "R2"},  # not a StaticAnalysis slot
        {"slot": "static", "rule_id": "R1"},  # duplicate of the default R1
        "R2",
    ],
)
def test_manifest_bad_required_rule_rejected(item):
    good = manifest()["required_rules"]
    with pytest.raises(ContractError, match="required_rules"):
        c.validate_task_manifest(manifest(required_rules=good + [item]))


def test_manifest_testrun_slot_without_tests_rejected():
    with pytest.raises(ContractError, match="TestRun slot 'tests' has no test"):
        c.validate_task_manifest(manifest(required_tests=[]))


def test_manifest_testrun_slot_without_allowed_command_rejected():
    with pytest.raises(ContractError, match="TestRun slot 'tests' has no allowed command"):
        c.validate_task_manifest(manifest(allowed_commands=[]))


def test_manifest_every_testrun_slot_needs_its_own_tests_and_commands():
    slots = [
        {"slot": "tests", "receipt_type": "TestRun"},
        {"slot": "tests2", "receipt_type": "TestRun"},
        {"slot": "review", "receipt_type": "IndependentReview"},
    ]
    only_first_tests = [{"slot": "tests", "test_id": "t1", "acceptance": ["AC-1"]}]
    cmds = [{"slot": "tests", "argv": ["pytest"]}, {"slot": "tests2", "argv": ["pytest"]}]
    with pytest.raises(ContractError, match="'tests2' has no test"):
        c.validate_task_manifest(
            manifest(required_receipts=slots, required_tests=only_first_tests,
                     allowed_commands=cmds, required_rules=[])
        )
    both_tests = only_first_tests + [{"slot": "tests2", "test_id": "t9", "acceptance": ["AC-2"]}]
    with pytest.raises(ContractError, match="'tests2' has no allowed command"):
        c.validate_task_manifest(
            manifest(required_receipts=slots, required_tests=both_tests,
                     allowed_commands=cmds[:1], required_rules=[])
        )


def test_manifest_static_slot_without_rules_rejected():
    with pytest.raises(ContractError, match="StaticAnalysis slot 'static' has no rule"):
        c.validate_task_manifest(manifest(required_rules=[]))


def test_manifest_without_static_slot_may_have_empty_required_rules():
    m = manifest(
        required_receipts=[
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "review", "receipt_type": "IndependentReview"},
        ],
        required_rules=[],
    )
    assert c.validate_task_manifest(m)["required_rules"] == []


def test_manifest_reserved_supervisor_slot_name_rejected():
    slots = manifest()["required_receipts"] + [
        {"slot": c.SUPERVISOR_SLOT, "receipt_type": "Documentation"}
    ]
    with pytest.raises(ContractError, match="reserved"):
        c.validate_task_manifest(manifest(required_receipts=slots))
    assert c.SUPERVISOR_SLOT == "__supervisor__"


def test_manifest_requires_at_least_one_testrun_slot():
    slots = [
        {"slot": "static", "receipt_type": "StaticAnalysis"},
        {"slot": "review", "receipt_type": "IndependentReview"},
    ]
    with pytest.raises(ContractError, match="TestRun"):
        c.validate_task_manifest(
            manifest(required_receipts=slots, required_tests=[], allowed_commands=[])
        )


def test_manifest_requires_at_least_one_independent_review_slot():
    slots = [
        {"slot": "tests", "receipt_type": "TestRun"},
        {"slot": "static", "receipt_type": "StaticAnalysis"},
    ]
    with pytest.raises(ContractError, match="IndependentReview"):
        c.validate_task_manifest(manifest(required_receipts=slots))


def test_doc_manifest_has_review_slot_and_dropping_it_is_rejected():
    dm = doc_manifest()
    assert {s["receipt_type"] for s in dm["required_receipts"]} >= {"TestRun", "IndependentReview"}
    no_review = [s for s in dm["required_receipts"] if s["receipt_type"] != "IndependentReview"]
    with pytest.raises(ContractError, match="IndependentReview"):
        c.validate_task_manifest(doc_manifest(required_receipts=no_review))


# ------------------------------------------------------------ manifest hash


def test_manifest_sha256_matches_independent_computation_and_is_stable():
    m = manifest()
    expected = hashlib.sha256(
        json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    assert c.manifest_sha256(m) == expected == MANIFEST_SHA == mhash(m)
    assert c.manifest_sha256(copy.deepcopy(m)) == expected
    assert c.manifest_sha256(dict(reversed(list(m.items())))) == expected
    assert len(expected) == 64 and expected == expected.lower()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m.update(author_principal="someone-else"),
        lambda m: m["required_tests"].append(
            {"slot": "tests", "test_id": "t3", "acceptance": ["AC-1"]}
        ),
        lambda m: m["required_tests"][0].update(acceptance=["AC-2"]),
        lambda m: m["allowed_commands"].append({"slot": "tests", "argv": ["pytest", "-x"]}),
        lambda m: m["allowed_commands"][0]["argv"].append("--extra"),
        lambda m: m["required_rules"].append({"slot": "static", "rule_id": "R2"}),
        lambda m: m.update(acceptance=["AC-1", "AC-2", "AC-3"]),
        lambda m: m.update(role_sha256="e" * 64),
        lambda m: m.update(retry_cap=5),
        lambda m: m.update(task_id="T2"),
    ],
)
def test_manifest_sha256_changes_when_any_binding_field_changes(mutate):
    m = manifest()
    changed = copy.deepcopy(m)
    mutate(changed)
    c.validate_task_manifest(changed)  # still a valid manifest
    assert c.manifest_sha256(changed) != c.manifest_sha256(m)


def test_manifest_sha256_raises_for_invalid_manifest():
    for bad in (manifest(extra=1), {"task_id": "T"}, None, []):
        with pytest.raises(ContractError):
            c.manifest_sha256(bad)


def test_manifest_sha256_does_not_mutate_input():
    m = manifest()
    snap = copy.deepcopy(m)
    c.manifest_sha256(m)
    assert m == snap


# ------------------------------------------------------------- principals


@pytest.mark.parametrize(
    "raw,norm",
    [
        ("author-y", "author-y"),
        ("  Author-Y ", "author-y"),
        ("AUTHOR-Y  ", "author-y"),
        ("Straße", "strasse"),
        # NFKC: full-width letters and hyphen, ligature, circled letters, nbsp
        ("ＡＵＴＨＯＲ－Ｙ", "author-y"),
        ("ｒｅｖｉｅｗｅｒ", "reviewer"),
        ("ﬁle", "file"),
        ("ⓐⓑ", "ab"),
        (" x ", "x"),
        ("　Ａ　", "a"),
    ],
)
def test_normalize_principal(raw, norm):
    assert c.normalize_principal(raw) == norm


def test_normalize_principal_nfkc_form_equals_ascii_form():
    # The point of NFKC: a spoofed spelling and the real name compare equal.
    assert c.normalize_principal("ＡＵＴＨＯＲ－Ｙ") == c.normalize_principal("author-y")
    assert c.normalize_principal("ａuthor-y") == c.normalize_principal("AUTHOR-Y")


@pytest.mark.parametrize("bad", ["", "   ", "\t\n", None, 5, b"x", ["a"]])
def test_normalize_principal_rejects_empty_or_non_string(bad):
    with pytest.raises(ContractError):
        c.normalize_principal(bad)


@pytest.mark.parametrize(
    "bad",
    [
        "a​b",  # zero-width space (Cf) inside
        "author-y​",  # trailing zero-width space
        "​author-y",  # leading zero-width space
        "a‍b",  # zero-width joiner (Cf)
        "﻿author-y",  # BOM / zero-width no-break space (Cf)
        "a­b",  # soft hyphen (Cf)
        "a‮b",  # right-to-left override (Cf)
        "a\x00b",  # NUL (Cc)
        "a\nb",  # embedded newline (Cc)
        "a\rb",
        "a\tb",  # embedded tab (Cc)
        "author-y\n",  # trailing newline: rejected BEFORE strip, not stripped away
        "\nauthor-y",
        "\tauthor-y\n",
        "author-y\t",
        "a\x7fb",  # DEL (Cc)
        "​",  # only a zero-width char: rejected as a control/format character
    ],
)
def test_normalize_principal_rejects_control_and_format_characters(bad):
    with pytest.raises(ContractError, match="control, format, invisible or filler"):
        c.normalize_principal(bad)


def test_normalize_principal_zero_width_variant_is_not_silently_equal_to_the_real_name():
    # Without the Cc/Cf rejection these two would normalize differently, letting
    # an author review under 'author​-y'; now the spoof does not normalize at all.
    assert c.normalize_principal("author-y") == "author-y"
    with pytest.raises(ContractError):
        c.normalize_principal("author​-y")


@pytest.mark.parametrize("field", ["reviewer_principal", "author_principal"])
@pytest.mark.parametrize("bad", ["rev​iewer", "rev\x00iewer", "reviewer\n", "﻿reviewer"])
def test_review_receipt_principal_with_control_or_format_char_fails_validate_receipt(field, bad):
    r = receipt("IndependentReview")
    r[field] = bad
    with pytest.raises(ContractError, match="control, format, invisible or filler"):
        c.validate_receipt(r)


@pytest.mark.parametrize("bad", ["author​-y", "author-y\n", "﻿author-y", "author\x00y"])
def test_manifest_author_principal_with_control_or_format_char_is_rejected(bad):
    with pytest.raises(ContractError, match="control, format, invisible or filler"):
        c.validate_task_manifest(manifest(author_principal=bad))


_INVISIBLE_PRINCIPALS = [
    pytest.param("alice️", "FE0F", id="variation-selector-16"),
    pytest.param("al︀ice", "FE00", id="variation-selector-1-inner"),
    pytest.param("alice\U000e0100", "E0100", id="variation-selector-supplement"),
    pytest.param("alice͏", "034F", id="combining-grapheme-joiner"),
    pytest.param("aliceㅤ", "1160", id="hangul-filler"),  # NFKC maps U+3164 -> U+1160; message reports the composed code point
    pytest.param("ﾠalice", "1160", id="halfwidth-hangul-filler"),
    pytest.param("ali឴ce", "17B4", id="khmer-inviting-vowel"),
    pytest.param("alice឵", "17B5", id="khmer-inherent-vowel"),
    pytest.param("aliceᅟ", "115F", id="hangul-choseong-filler"),
    pytest.param("aliceᅠ", "1160", id="hangul-jungseong-filler"),
    pytest.param("alice͸", "0378", id="unassigned-code-point"),
]


@pytest.mark.parametrize("bad,hexcode", _INVISIBLE_PRINCIPALS)
def test_normalize_principal_rejects_invisible_and_filler_characters(bad, hexcode):
    with pytest.raises(ContractError, match="control, format, invisible or filler") as info:
        c.normalize_principal(bad)
    assert f"U+{hexcode}" in str(info.value)


def test_normalize_principal_variation_selector_is_not_silently_equal_to_plain_name():
    assert c.normalize_principal("alice") == "alice"
    with pytest.raises(ContractError):
        c.normalize_principal("alice️")


@pytest.mark.parametrize("field", ["reviewer_principal", "author_principal"])
@pytest.mark.parametrize("bad,hexcode", _INVISIBLE_PRINCIPALS)
def test_review_receipt_principal_with_invisible_char_fails_validate_receipt(field, bad, hexcode):
    r = receipt("IndependentReview")
    r[field] = bad
    with pytest.raises(ContractError, match="control, format, invisible or filler"):
        c.validate_receipt(r)


@pytest.mark.parametrize("bad,hexcode", _INVISIBLE_PRINCIPALS)
def test_manifest_author_principal_with_invisible_char_is_rejected(bad, hexcode):
    with pytest.raises(ContractError, match="control, format, invisible or filler"):
        c.validate_task_manifest(manifest(author_principal=bad))


def test_derive_result_of_review_with_hidden_char_principal_raises_not_pass():
    # A reviewer name that only differs from the author by a zero-width char must
    # never derive PASS: the contract rejects it outright.
    r = unsigned_receipt(
        "IndependentReview", result="FAIL", reviewer_principal="reviewer-x", author_principal="author-y"
    )
    r["reviewer_principal"] = "author​-y"
    with pytest.raises(ContractError):
        c.derive_result(r)


@pytest.mark.parametrize("field", ["reviewer_principal", "author_principal"])
def test_review_principal_whitespace_only_rejected(field):
    r = receipt("IndependentReview")
    r[field] = "   "
    with pytest.raises(ContractError, match=field):
        c.validate_receipt(r)


# ------------------------------------------------- receipts: reserved slot


def test_supervisor_slot_accepts_documentation_receipt():
    r = supervisor_receipt("WORKER_LOST")
    assert r["slot"] == c.SUPERVISOR_SLOT
    assert c.validate_receipt(r) == r


@pytest.mark.parametrize("rtype", ["TestRun", "StaticAnalysis", "IndependentReview"])
def test_supervisor_slot_rejects_non_documentation_receipts(rtype):
    r = receipt(rtype, slot=c.SUPERVISOR_SLOT)
    with pytest.raises(ContractError, match="reserved"):
        c.validate_receipt(r)


def test_receipt_missing_manifest_sha256_rejected_by_name():
    r = receipt()
    del r["manifest_sha256"]
    with pytest.raises(ContractError, match="manifest_sha256"):
        c.validate_receipt(r)


# ===================================================================== signing


def test_test_keys_are_long_enough_and_pairwise_distinct():
    keys = [KEY, SUPERVISOR_KEY, OPERATOR_KEY, WRONG_KEY]
    assert all(isinstance(k, bytes) and len(k) >= signing.MIN_KEY_BYTES for k in keys)
    assert len(set(keys)) == len(keys)
    assert signing.MIN_KEY_BYTES == 32


@pytest.mark.parametrize("key", [b"", b"k" * 31, "k" * 40, None, 5, [b"k" * 32]])
def test_sign_and_verify_reject_invalid_keys(key):
    body = {"a": 1}
    with pytest.raises(ContractError, match="key"):
        signing.sign(body, key)
    with pytest.raises(ContractError, match="key"):
        signing.verify(dict(body, signature="a" * 64), key)


def test_sign_accepts_exactly_32_bytes_and_bytearray():
    body = {"a": 1}
    sig = signing.sign(body, b"k" * 32)
    assert len(sig) == 64
    assert signing.sign(body, bytearray(b"k" * 32)) == sig
    assert signing.verify(dict(body, signature=sig), b"k" * 32) is True


def test_sign_default_label_is_receipt_label_and_matches_independent_hmac():
    body = {"b": 2, "a": [1]}
    expected = hmac.new(
        KEY, signing.RECEIPT_LABEL + c.canonical_bytes(body), hashlib.sha256
    ).hexdigest()
    assert signing.sign(body, KEY) == expected == signing.sign(body, KEY, signing.RECEIPT_LABEL)


def test_labels_are_distinct_non_empty_bytes():
    assert signing.RECEIPT_LABEL != signing.WAIVER_LABEL
    assert signing.RECEIPT_LABEL and signing.WAIVER_LABEL


def test_signature_under_one_label_does_not_verify_under_the_other():
    body = {"x": 1}
    as_receipt = dict(body, signature=signing.sign(body, OPERATOR_KEY, signing.RECEIPT_LABEL))
    as_waiver = dict(body, signature=signing.sign(body, OPERATOR_KEY, signing.WAIVER_LABEL))
    assert as_receipt["signature"] != as_waiver["signature"]
    assert signing.verify(as_receipt, OPERATOR_KEY, signing.RECEIPT_LABEL)
    assert not signing.verify(as_receipt, OPERATOR_KEY, signing.WAIVER_LABEL)
    assert signing.verify(as_waiver, OPERATOR_KEY, signing.WAIVER_LABEL)
    assert not signing.verify(as_waiver, OPERATOR_KEY, signing.RECEIPT_LABEL)
    assert not signing.verify(as_waiver, OPERATOR_KEY)  # default label = receipt


@pytest.mark.parametrize("label", [b"", "text", None, 5])
def test_sign_and_verify_reject_invalid_labels(label):
    with pytest.raises(ContractError, match="label"):
        signing.sign({"a": 1}, KEY, label)
    with pytest.raises(ContractError, match="label"):
        signing.verify({"a": 1, "signature": "a" * 64}, KEY, label)


def test_verify_wrong_key_and_tamper_are_false_not_exceptions():
    r = receipt()
    assert signing.verify(r, KEY)
    assert not signing.verify(r, WRONG_KEY)
    assert not signing.verify(r, SUPERVISOR_KEY)
    tampered = dict(r, runner_id="attacker")
    assert not signing.verify(tampered, KEY)
    for bad in ("x", None, [], 5):
        assert signing.verify(bad, KEY) is False
    no_sig = {k: v for k, v in r.items() if k != "signature"}
    assert signing.verify(no_sig, KEY) is False
    assert signing.verify(dict(r, signature=123), KEY) is False


def test_sign_refuses_object_that_already_has_signature():
    with pytest.raises(ContractError, match="signature"):
        signing.sign(receipt(), KEY)
