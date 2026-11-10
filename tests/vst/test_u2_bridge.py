"""U2-6 (C): negative cases for the U2 bridge facts, the analyzer payload and the v3 receipt builder.

* validate_bridge_facts: each of the six fields, wrong type, bool/int confusion, zero hash, ordering, enum, consistency;
* v1/v2 receipts never accept bridge fields, v3 StaticAnalysis requires them, other v3 types refuse them;
* analyzer payload tamper per field makes verify_analyzer_evidence fail;
* bridge_facts_from_role_result refusals;
* build_static_receipt: one test group per RB_* refusal code, on a throwaway git repository.

Synthetic data only. The product code is never edited or monkeypatched.
"""

from __future__ import annotations

import copy

import pytest

from tools.vst import analyzer_authority as aa
from tools.vst import contracts, signing
from tools.vst.analyzer_adapter import Outcome, bridge_facts_from_role_result
from tools.vst.contracts import ContractError, validate_bridge_facts
from tools.vst.receipt_builder import build_static_receipt

from tests.vst import u2_helpers as U
from tests.vst.e1e4_helpers import unsigned_receipt

HEAD = "a1" * 20
FACTS = {
    "role_table_sha256": "a1" * 32, "aeve_head": "d4" * 20, "model_residual": ["model-judgment"],
    "reviewed_paths_sha256": "b2" * 32, "findings_count": 0, "highest_severity": "NONE",
}


def facts(**over):
    doc = copy.deepcopy(FACTS)
    doc.update(over)
    return doc


# ---------------------------------------------------------------------------------- validate_bridge_facts
def test_valid_facts_are_accepted_with_and_without_a_context_prefix():
    validate_bridge_facts(facts())
    validate_bridge_facts(facts(model_residual=[], findings_count=2, highest_severity="HIGH"), "payload.")


@pytest.mark.parametrize("field,value", [
    ("role_table_sha256", "0" * 64), ("role_table_sha256", "A1" * 32), ("role_table_sha256", "a1" * 31),
    ("role_table_sha256", "a1" * 32 + "0"), ("role_table_sha256", 5), ("role_table_sha256", None),
    ("role_table_sha256", True), ("role_table_sha256", b"a1" * 32), ("role_table_sha256", ["a1" * 32]),
    ("reviewed_paths_sha256", "0" * 64), ("reviewed_paths_sha256", "B2" * 32), ("reviewed_paths_sha256", ""),
    ("reviewed_paths_sha256", None), ("reviewed_paths_sha256", 0),
    ("aeve_head", "d4" * 32), ("aeve_head", "D4" * 20), ("aeve_head", "d4" * 19), ("aeve_head", "HEAD"),
    ("aeve_head", None), ("aeve_head", 40), ("aeve_head", True), ("aeve_head", "d4" * 20 + "\n"),
])
def test_a_malformed_hash_or_head_is_refused(field, value):
    with pytest.raises(ContractError) as info:
        validate_bridge_facts(facts(**{field: value}))
    assert field in str(info.value)


def test_the_context_prefix_names_the_failing_field():
    with pytest.raises(ContractError) as info:
        validate_bridge_facts(facts(aeve_head="x"), "analyzer payload.")
    assert str(info.value).startswith("analyzer payload.aeve_head")


@pytest.mark.parametrize("residual", [
    ["b-two", "a-one"], ["a-one", "a-one"], [f"r{i}" for i in range(9)], ["Upper"], [""], ["has space"], [None], [1],
    [["x"]], ["-lead"], ["a" * 65], "model-judgment", ("a-one",), None, {"a-one": 1}, 7, True,
])
def test_a_malformed_model_residual_is_refused(residual):
    with pytest.raises(ContractError) as info:
        validate_bridge_facts(facts(model_residual=residual))
    assert "model_residual" in str(info.value)


@pytest.mark.parametrize("residual", [[], ["a-one"], ["a-b", "a_b"], [f"r{i}" for i in range(8)], ["0-digit-first"]])
def test_a_sorted_unique_residual_up_to_eight_tokens_is_accepted(residual):
    validate_bridge_facts(facts(model_residual=residual))


@pytest.mark.parametrize("count", [True, False, 1.0, 0.0, "1", None, -1, [1]])
def test_findings_count_must_be_a_non_negative_int_and_never_a_bool(count):
    with pytest.raises(ContractError) as info:
        validate_bridge_facts(facts(findings_count=count, highest_severity="NONE"))
    assert "findings_count" in str(info.value)


@pytest.mark.parametrize("severity", ["none", "INFO", "SEVERE", "", None, 0, True, ["LOW"], "LOW "])
def test_highest_severity_must_be_in_the_closed_enum(severity):
    with pytest.raises(ContractError) as info:
        validate_bridge_facts(facts(findings_count=1, highest_severity=severity))
    assert "highest_severity" in str(info.value)


@pytest.mark.parametrize("severity", ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
def test_every_real_severity_needs_a_positive_count(severity):
    validate_bridge_facts(facts(findings_count=3, highest_severity=severity))
    with pytest.raises(ContractError):
        validate_bridge_facts(facts(findings_count=0, highest_severity=severity))


def test_none_severity_needs_a_zero_count():
    with pytest.raises(ContractError):
        validate_bridge_facts(facts(findings_count=1, highest_severity="NONE"))


@pytest.mark.parametrize("field", list(U.BRIDGE_FIELDS))
def test_a_missing_field_does_not_pass_silently(field):
    doc = facts()
    del doc[field]
    with pytest.raises((ContractError, KeyError)):
        validate_bridge_facts(doc)


# ------------------------------------------------------- receipt versions: bridge fields only in v3 StaticAnalysis
def _v1_static():
    item = unsigned_receipt("StaticAnalysis")
    item["signature"] = "f0" * 32
    return item


def _v2_static():
    item = unsigned_receipt("StaticAnalysis", contract_version=2)
    item["signature"] = "f0" * 32
    return item


@pytest.mark.parametrize("builder", [_v1_static, _v2_static], ids=["v1", "v2"])
def test_v1_and_v2_static_receipts_validate_without_bridge_fields(builder):
    assert contracts.validate_receipt(builder())["receipt_type"] == "StaticAnalysis"


@pytest.mark.parametrize("builder", [_v1_static, _v2_static], ids=["v1", "v2"])
@pytest.mark.parametrize("field", list(U.BRIDGE_FIELDS))
def test_v1_and_v2_receipts_carrying_a_bridge_field_are_rejected(builder, field):
    item = builder()
    item[field] = FACTS[field]
    with pytest.raises(ContractError) as info:
        contracts.validate_receipt(item)
    assert field in str(info.value)


@pytest.mark.parametrize("builder", [_v1_static, _v2_static], ids=["v1", "v2"])
def test_v1_and_v2_receipts_carrying_all_bridge_fields_are_rejected(builder):
    item = {**builder(), **FACTS}
    with pytest.raises(ContractError):
        contracts.validate_receipt(item)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return U.make_world(tmp_path_factory.mktemp("u2-bridge"))


@pytest.mark.parametrize("which", ["tests", "review", "documentation"])
def test_non_static_v3_receipts_never_accept_bridge_fields(world, which):
    if which == "documentation":
        item = unsigned_receipt("Documentation", contract_version=3)
        item["signature"] = "f0" * 32
    else:
        item = copy.deepcopy(getattr(world, which))
    assert contracts.validate_receipt(item)["contract_version"] == 3  # valid before the field is added
    for field in U.BRIDGE_FIELDS:
        forged = {**item, field: FACTS[field]}
        with pytest.raises(ContractError) as info:
            contracts.validate_receipt(forged)
        assert field in str(info.value)


def test_a_v3_static_receipt_built_by_the_builder_validates(world):
    receipt, _ = U.static_run(world)
    validated = contracts.validate_receipt(receipt)
    assert validated["contract_version"] == 3 and validated["result"] == "PASS"
    assert {f: validated[f] for f in U.BRIDGE_FIELDS} == {
        "role_table_sha256": U.TABLE_SHA, "aeve_head": U.AEVE_HEAD, "model_residual": [],
        "reviewed_paths_sha256": U.paths_sha(U.PATHS), "findings_count": 0, "highest_severity": "NONE"}


@pytest.mark.parametrize("field", list(U.BRIDGE_FIELDS))
def test_a_v3_static_receipt_without_a_bridge_field_is_rejected(world, field):
    receipt, _ = U.static_run(world)
    del receipt[field]
    with pytest.raises(ContractError) as info:
        contracts.validate_receipt(receipt)
    assert field in str(info.value)


@pytest.mark.parametrize("field,value", [
    ("role_table_sha256", "0" * 64), ("aeve_head", "d4" * 32), ("model_residual", ["b", "a"]),
    ("reviewed_paths_sha256", "0" * 64), ("findings_count", True), ("highest_severity", "NONE"),
])
def test_a_v3_static_receipt_with_a_malformed_bridge_field_is_rejected(world, field, value):
    receipt, _ = U.static_run(world)
    receipt[field] = value
    receipt["findings_count"] = receipt["findings_count"] if field != "highest_severity" else 1
    with pytest.raises(ContractError):
        contracts.validate_receipt(receipt)


# ------------------------------------------------------------------------- analyzer payload tamper per field
def _signed_payload(world):
    _, payload = U.static_run(world)
    evidence = aa.sign_analyzer_evidence(payload, U.ANALYZER_KEY, U.OTHER_ROLE_KEYS)
    return payload, evidence


def _verify(evidence, expected, nonces=None):
    nonces = nonces or U.Nonces()
    ok = aa.verify_analyzer_evidence(evidence, U.ANALYZER_KEY, expected_binding=expected, consume_nonce=nonces,
                                     other_role_keys=U.OTHER_ROLE_KEYS, consume=False)
    return ok, nonces


def _binding(payload):
    return {k: copy.deepcopy(v) for k, v in payload.items() if k != "type"}


def test_untampered_evidence_verifies_and_consume_false_leaves_the_nonce_alone(world):
    payload, evidence = _signed_payload(world)
    ok, nonces = _verify(evidence, _binding(payload))
    assert ok is True and nonces.used == []


TAMPER = {
    "role_table_sha256": "9a" * 32,
    "aeve_head": "9a" * 20,
    "model_residual": ["model-judgment"],
    "reviewed_paths_sha256": "9a" * 32,
    "findings_count": 2,
    "highest_severity": "CRITICAL",
}


@pytest.mark.parametrize("field", list(U.BRIDGE_FIELDS))
def test_tampering_a_bridge_field_in_the_signed_evidence_fails_verification(world, field):
    payload, evidence = _signed_payload(world)
    forged = copy.deepcopy(evidence)
    forged[field] = TAMPER[field]
    if field == "findings_count":
        forged["highest_severity"] = "LOW"  # shape stays valid, so only the signature can catch the change
    if field == "highest_severity":
        forged["findings_count"] = 1
    assert _verify(forged, _binding(payload))[0] is False


@pytest.mark.parametrize("field", list(U.BRIDGE_FIELDS))
def test_a_verifier_expectation_that_differs_in_a_bridge_field_fails_verification(world, field):
    payload, evidence = _signed_payload(world)
    expected = _binding(payload)
    expected[field] = TAMPER[field]
    if field == "highest_severity":
        expected["findings_count"] = 1
    if field == "findings_count":
        expected["highest_severity"] = "CRITICAL"
    assert _verify(evidence, expected)[0] is False


@pytest.mark.parametrize("field,value", [
    ("findings_count", False), ("model_residual", ()), ("aeve_head", None), ("role_table_sha256", None),
])
def test_type_confusion_in_evidence_is_rejected_without_raising(world, field, value):
    payload, evidence = _signed_payload(world)
    forged = copy.deepcopy(evidence)
    forged[field] = value
    assert _verify(forged, _binding(payload))[0] is False


def test_re_signing_a_tampered_payload_with_the_wrong_key_fails(world):
    payload, _ = _signed_payload(world)
    payload["findings_count"], payload["highest_severity"] = 1, "LOW"  # differs from what the real signer signed
    forged = {**payload, "signature": signing.sign(payload, U.SIGNER_KEY, signing.ANALYZER_AUTHORITY_LABEL)}
    assert _verify(forged, _binding(payload))[0] is False


@pytest.mark.parametrize("field,value", [
    ("role_table_sha256", "0" * 64), ("aeve_head", "d4" * 32), ("model_residual", ["b", "a"]),
    ("reviewed_paths_sha256", "z" * 64), ("findings_count", True), ("highest_severity", "NONE-ish"),
])
def test_the_payload_builder_and_signer_refuse_malformed_bridge_facts(world, field, value):
    _, payload = U.static_run(world)
    payload[field] = value
    with pytest.raises(ContractError):
        aa.validate_analyzer_payload(payload)
    with pytest.raises(ContractError):
        aa.sign_analyzer_evidence(payload, U.ANALYZER_KEY, U.OTHER_ROLE_KEYS)


@pytest.mark.parametrize("field", list(U.BRIDGE_FIELDS))
def test_a_payload_without_a_bridge_field_is_refused(world, field):
    _, payload = U.static_run(world)
    del payload[field]
    with pytest.raises(ContractError):
        aa.validate_analyzer_payload(payload)


def test_the_receipt_and_the_payload_carry_identical_independent_bridge_facts(world):
    body, payload = build_static_receipt(**U.builder_kwargs(
        world.repo, world.head, role_result=U.role_result(world.head, status="FINDINGS", findings=[U.uc_finding("BLOCKER")],
                                                           residual=["model-judgment"])))
    assert {f: body[f] for f in U.BRIDGE_FIELDS} == {f: payload[f] for f in U.BRIDGE_FIELDS}
    assert body["highest_severity"] == "CRITICAL" and body["findings_count"] == 1
    body["model_residual"].append("zz-added")
    assert payload["model_residual"] == ["model-judgment"]  # no aliasing between the two outputs


# ------------------------------------------------------------------- bridge_facts_from_role_result refusals
def bridge(head=None, paths=U.PATHS, role=U.ROLE, expected=None, **role_kw):
    head = head or HEAD
    result = role_kw.pop("result", None) or U.role_result(head, paths, **role_kw)
    return bridge_facts_from_role_result(result, role, list(paths), expected_base_revision=expected or head)


def refused_with(fragment, **kw):
    with pytest.raises(ContractError) as info:
        bridge(**kw)
    assert fragment in str(info.value), str(info.value)


def test_bridge_facts_of_a_clean_local_role():
    out = bridge()
    assert out == {"role_table_sha256": U.TABLE_SHA, "aeve_head": U.AEVE_HEAD, "model_residual": [],
                   "reviewed_paths_sha256": U.paths_sha(U.PATHS), "findings_count": 0, "highest_severity": "NONE"}


@pytest.mark.parametrize("severity,mapped", [("NIT", "LOW"), ("MINOR", "MEDIUM"), ("MAJOR", "HIGH"), ("BLOCKER", "CRITICAL")])
def test_severity_mapping_and_count(severity, mapped):
    out = bridge(status="FINDINGS", findings=[U.uc_finding("NIT"), U.uc_finding(severity, line=9)])
    assert (out["findings_count"], out["highest_severity"]) == (2, mapped if severity != "NIT" else "LOW")


def test_the_highest_of_several_severities_wins():
    out = bridge(status="FINDINGS", findings=[U.uc_finding("BLOCKER"), U.uc_finding("NIT", line=4), U.uc_finding("MAJOR", line=5)])
    assert out["highest_severity"] == "CRITICAL" and out["findings_count"] == 3


def test_an_advisory_result_cannot_back_a_receipt():
    refused_with("purpose is not 'receipt'", purpose="advisory")


def test_a_changed_paths_hash_of_another_path_set_is_refused():
    refused_with("changed_paths_sha256 differs", changed_sha=U.paths_sha(["src/a.py"]))


def test_a_narrower_reviewed_set_than_the_requested_one_is_refused():
    result = U.role_result(HEAD, U.PATHS)
    with pytest.raises(ContractError) as info:
        bridge_facts_from_role_result(result, U.ROLE, ["src/a.py"], expected_base_revision=HEAD)
    assert "changed_paths_sha256 differs" in str(info.value)


def test_a_wider_reviewed_set_than_the_requested_one_is_refused():
    result = U.role_result(HEAD, U.PATHS)
    with pytest.raises(ContractError):
        bridge_facts_from_role_result(result, U.ROLE, [*U.PATHS, "src/c.py"], expected_base_revision=HEAD)


def test_reviewed_path_order_does_not_matter():
    result = U.role_result(HEAD, U.PATHS)
    forward = bridge_facts_from_role_result(result, U.ROLE, ["docs/b.md", "src/a.py"], expected_base_revision=HEAD)
    backward = bridge_facts_from_role_result(result, U.ROLE, ["src/a.py", "docs/b.md"], expected_base_revision=HEAD)
    assert forward == backward


def test_a_stale_base_revision_is_refused():
    refused_with("base_revision differs", expected="f" * 40)


@pytest.mark.parametrize("expected", ["", "abc", "A" * 40, "f" * 39, "f" * 64, None, 5])
def test_a_malformed_expected_base_revision_is_refused(expected):
    result = U.role_result(HEAD)
    with pytest.raises(ContractError):
        bridge_facts_from_role_result(result, U.ROLE, U.PATHS, expected_base_revision=expected)


def test_a_missing_role_is_refused():
    refused_with("exactly one entry", role="python-reviewer")


@pytest.mark.parametrize("role", ["", None, 5])
def test_an_empty_or_non_string_role_is_refused(role):
    result = U.role_result(HEAD)
    with pytest.raises(ContractError):
        bridge_facts_from_role_result(result, role, U.PATHS, expected_base_revision=HEAD)


def test_a_duplicate_role_entry_is_refused():
    twin = U.role_result(HEAD)["roles"][0]
    refused_with("invalid", extra_entries=[copy.deepcopy(twin)])


@pytest.mark.parametrize("status", ["PARTIAL", "NOT_COVERED", "NOT_RUN", "BLOCKED"])
def test_a_status_other_than_clean_or_findings_is_refused(status):
    refused_with("neither CLEAN nor FINDINGS", status=status)


def test_uncovered_scope_is_refused():
    refused_with("uncovered scope", status="FINDINGS", findings=[U.uc_finding()], uncovered=["unit-gap"])


def test_a_local_plus_model_role_without_a_residual_is_refused():
    refused_with("without a model_residual", klass="LOCAL_PLUS_MODEL", status="FINDINGS", findings=[U.uc_finding()])


def test_a_local_plus_model_role_with_a_residual_keeps_it_as_a_copy():
    result = U.role_result(HEAD, klass="LOCAL_PLUS_MODEL", status="FINDINGS", findings=[U.uc_finding()],
                           residual=["a-one", "b-two"])
    out = bridge_facts_from_role_result(result, U.ROLE, U.PATHS, expected_base_revision=HEAD)
    assert out["model_residual"] == ["a-one", "b-two"]
    out["model_residual"].append("z")
    assert result["roles"][0]["model_residual"] == ["a-one", "b-two"]


def test_a_zero_role_table_digest_is_refused():
    with pytest.raises(ContractError):
        bridge(table_sha="0" * 64)


@pytest.mark.parametrize("result", [None, [], "result", 7, {}, {"schema_version": "uc.role-result.v1"}])
def test_a_malformed_role_result_is_refused_as_contract_error(result):
    with pytest.raises(ContractError) as info:
        bridge_facts_from_role_result(result, U.ROLE, U.PATHS, expected_base_revision=HEAD)
    assert "role result: invalid" in str(info.value)


@pytest.mark.parametrize("paths", [[], (), "src/a.py", None, ["/abs.py"], ["../x.py"], ["a\\b.py"], ["src/*.py"], ["src//a.py"],
                                   ["src/a.py", "src/a.py"], [""], [5], ["c:/x.py"]])
def test_bad_reviewed_paths_are_refused(paths):
    result = U.role_result(HEAD)
    with pytest.raises(ContractError):
        bridge_facts_from_role_result(result, U.ROLE, paths, expected_base_revision=HEAD)


def test_the_role_result_is_not_mutated_by_the_bridge():
    result = U.role_result(HEAD, status="FINDINGS", findings=[U.uc_finding()], residual=["a-one"])
    before = copy.deepcopy(result)
    bridge_facts_from_role_result(result, U.ROLE, U.PATHS, expected_base_revision=HEAD)
    assert result == before


# ------------------------------------------------------------------------------------- receipt builder: RB_*
def kw_for(world, **over):
    return U.builder_kwargs(world.repo, world.head, **over)


def code_of(world, **over):
    return U.refusal_code(build_static_receipt, **kw_for(world, **over))


def test_happy_path_returns_a_pass_receipt_and_matching_payload(world):
    body, payload = build_static_receipt(**kw_for(world))
    assert body["result"] == "PASS" and body["contract_version"] == 3 and "signature" not in body
    assert payload["type"] == aa.ANALYZER_EVIDENCE_TYPE and payload["candidate_head"] == world.head
    assert {f: body[f] for f in U.BRIDGE_FIELDS} == {f: payload[f] for f in U.BRIDGE_FIELDS}
    assert body["analysis_scope"] == payload["analysis_scope"] == sorted(U.PATHS)
    assert contracts.validate_receipt({**body, "signature": "0" * 63 + "1"})["result"] == "PASS"


def test_the_builder_is_deterministic_and_does_not_mutate_its_inputs(world):
    kw = kw_for(world)
    before = copy.deepcopy({k: v for k, v in kw.items() if k != "adapter_result"})
    first = build_static_receipt(**kw)
    second = build_static_receipt(**kw)
    assert first == second
    assert {k: v for k, v in kw.items() if k != "adapter_result"} == before


@pytest.mark.parametrize("status,findings,residual,klass,expected", [
    ("FINDINGS", [U.uc_finding("NIT")], [], "LOCAL", "INCONCLUSIVE"),
    ("FINDINGS", [U.uc_finding("BLOCKER")], ["model-judgment"], "LOCAL_PLUS_MODEL", "INCONCLUSIVE"),
    ("FINDINGS", [U.uc_finding("MINOR")], ["model-judgment"], "LOCAL", "INCONCLUSIVE"),
])
def test_a_role_with_findings_or_residual_is_never_offered_pass(world, status, findings, residual, klass, expected):
    body, _ = build_static_receipt(**kw_for(world, role_result=U.role_result(
        world.head, status=status, findings=findings, residual=residual, klass=klass)))
    assert body["result"] == expected and body["findings_count"] == len(findings)


def test_a_report_finding_of_any_severity_makes_the_receipt_inconclusive_even_for_a_clean_role(world):
    for severity in ("INFO", "LOW", "MEDIUM"):
        adapter = U.adapter_result(world.repo, world.head, findings=[U.report_finding(severity=severity)])
        body, _ = build_static_receipt(**kw_for(world, adapter_result=adapter))
        assert body["result"] == "INCONCLUSIVE" and len(body["findings"]) == 1


# --- RB_ARG_INVALID
ARG_CASES = {
    "short-nonce": {"nonce": "short"}, "non-string-nonce": {"nonce": 123456789012345678},
    "bad-head": {"candidate_head": "xyz"}, "upper-head": {"candidate_head": "A" * 40},
    "bad-manifest-sha": {"manifest_sha256": "E" * 64}, "bad-role-sha": {"role_sha256": "c" * 63},
    "id-with-space": {"receipt_id": "bad id"}, "empty-id": {"task_id": ""}, "id-int": {"slot": 5},
    "model-with-slash": {"resolved_model": "a/b"}, "created-no-z": {"created_at": "2026-11-10T00:00:00"},
    "created-space": {"created_at": "2026-11-10 00:00:00Z"}, "created-offset": {"created_at": "2026-11-10T00:00:00+01:00"},
    "epoch-zero": {"epoch": 0}, "epoch-bool": {"epoch": True}, "attempt-bool": {"attempt": True},
    "attempt-2-without-prev": {"attempt": 2, "prev_receipt_sha256": None},
    "attempt-1-with-prev": {"attempt": 1, "prev_receipt_sha256": "f0" * 32},
    "attempt-2-bad-prev": {"attempt": 2, "prev_receipt_sha256": "zz"},
    "acceptance-duplicate": {"covered_acceptance": ["AC-2", "AC-2"]},
    "acceptance-bad-id": {"covered_acceptance": ["bad id"]}, "acceptance-str": {"covered_acceptance": "AC-2"},
    "adapter-not-a-result": {"adapter_result": {"report": 1}}, "root-not-a-path": {"snapshot_root": 5},
    "role-empty": {"role": ""}, "role-int": {"role": 5},
}


@pytest.mark.parametrize("name", list(ARG_CASES))
def test_RB_ARG_INVALID(world, name):
    assert code_of(world, **ARG_CASES[name]) == "RB_ARG_INVALID"


def test_RB_ARG_INVALID_for_over_nested_input(world):
    deep: list = []
    for _ in range(5000):
        deep = [deep]
    assert code_of(world, role_result={"nest": deep}) == "RB_ARG_INVALID"


# --- RB_PATHS_INVALID
@pytest.mark.parametrize("paths", [
    [], (), "src/a.py", None, ["src/a.py", "src/a.py"], ["/etc/passwd"], ["../x.py"], ["src/../a.py"], ["src/*.py"],
    ["src\\a.py"], ["c:/a.py"], [""], [5], ["src//a.py"],
])
def test_RB_PATHS_INVALID_for_reviewed_paths(world, paths):
    assert code_of(world, reviewed_paths=paths) == "RB_PATHS_INVALID"


@pytest.mark.parametrize("paths", [[], "x", None, ["docs/b.md", "docs/b.md"], ["../x.py"]])
def test_RB_PATHS_INVALID_for_required_paths(world, paths):
    assert code_of(world, required_paths=paths) == "RB_PATHS_INVALID"


def test_RB_PATHS_INVALID_when_the_adapter_refuses_the_path_spelling(world):
    paths = ["SRC/a.py", "docs/b.md"]  # tracked spelling is src/a.py
    result = U.role_result(world.head, paths)
    assert code_of(world, reviewed_paths=paths, required_paths=paths, role_result=result) == "RB_PATHS_INVALID"


# --- RB_REQUIRED_PATH_UNCOVERED / RB_REVIEWED_PATH_EXTRA
def test_RB_REQUIRED_PATH_UNCOVERED_for_a_required_path_that_was_not_reviewed(world):
    assert code_of(world, required_paths=[*U.PATHS, "src/c.py"]) == "RB_REQUIRED_PATH_UNCOVERED"


def test_RB_REQUIRED_PATH_UNCOVERED_for_a_narrow_reviewed_set_even_with_a_matching_role_hash(world):
    narrow = ["src/a.py"]  # the diff gate requires both paths, the review covered only one
    result = U.role_result(world.head, narrow)
    adapter = U.adapter_result(world.repo, world.head, narrow)
    msg = None
    try:
        build_static_receipt(**kw_for(world, reviewed_paths=narrow, required_paths=U.PATHS, role_result=result,
                                      adapter_result=adapter))
    except ContractError as exc:
        msg = str(exc)
    assert msg is not None and msg.startswith("RB_REQUIRED_PATH_UNCOVERED") and "docs/b.md" in msg


def test_RB_REVIEWED_PATH_EXTRA_for_a_superset(world):
    extra = [*U.PATHS, "src/c.py"]
    assert code_of(world, reviewed_paths=extra) == "RB_REVIEWED_PATH_EXTRA"


# --- RB_BRIDGE_REFUSED
BRIDGE_CASES = {
    "advisory": lambda h: U.role_result(h, purpose="advisory"),
    "other-path-hash": lambda h: U.role_result(h, changed_sha=U.paths_sha(["src/a.py"])),
    "stale-base-revision": lambda h: U.role_result("1" * 40),
    "role-absent": lambda h: U.role_result(h, role="python-reviewer", klass="LOCAL_PLUS_MODEL", status="FINDINGS",
                                           findings=[U.uc_finding()], residual=["a-one"]),
    "partial-status": lambda h: U.role_result(h, status="PARTIAL", residual=["a-one"]),
    "not-run-status": lambda h: U.role_result(h, status="NOT_RUN"),
    "uncovered": lambda h: U.role_result(h, status="FINDINGS", findings=[U.uc_finding()], uncovered=["unit-gap"]),
    "lpm-empty-residual": lambda h: U.role_result(h, klass="LOCAL_PLUS_MODEL", status="FINDINGS", findings=[U.uc_finding()]),
    "zero-table-digest": lambda h: U.role_result(h, table_sha="0" * 64),
    "unsorted-residual": lambda h: U.role_result(h, status="FINDINGS", findings=[U.uc_finding()], residual=["b-two", "a-one"]),
    "empty-document": lambda h: {},
    "not-a-document": lambda h: ["result"],
    "unknown-key": lambda h: {**U.role_result(h), "extra": 1},
}


@pytest.mark.parametrize("name", list(BRIDGE_CASES))
def test_RB_BRIDGE_REFUSED(world, name):
    assert code_of(world, role_result=BRIDGE_CASES[name](world.head)) == "RB_BRIDGE_REFUSED"


# --- RB_TREE_NOT_CLEAN (each case works on its own repository)
def _fresh(tmp_path):
    repo, head = U.make_repo(tmp_path, "fresh")
    return repo, head, U.builder_kwargs(repo, head)  # the kwargs (incl. the adapter tree digest) are taken while clean


def test_RB_TREE_NOT_CLEAN_for_a_modified_tracked_file(tmp_path):
    repo, head, kw = _fresh(tmp_path)
    (repo / "src" / "a.py").write_bytes(b"x = 2\n")
    assert U.refusal_code(build_static_receipt, **kw) == "RB_TREE_NOT_CLEAN"


def test_RB_TREE_NOT_CLEAN_for_an_untracked_file(tmp_path):
    repo, head, kw = _fresh(tmp_path)
    (repo / "junk.txt").write_bytes(b"untracked\n")
    assert U.refusal_code(build_static_receipt, **kw) == "RB_TREE_NOT_CLEAN"


def test_RB_TREE_NOT_CLEAN_for_a_staged_but_uncommitted_change(tmp_path):
    repo, head, kw = _fresh(tmp_path)
    (repo / "docs" / "b.md").write_bytes(b"# changed\n")
    U.git(repo, "add", "docs/b.md")
    assert U.refusal_code(build_static_receipt, **kw) == "RB_TREE_NOT_CLEAN"


def test_RB_TREE_NOT_CLEAN_when_head_is_not_the_candidate_head(tmp_path):
    repo, head, _ = _fresh(tmp_path)
    other = "1" * 40
    kw = U.builder_kwargs(repo, head, candidate_head=other, role_result=U.role_result(other))
    assert U.refusal_code(build_static_receipt, **kw) == "RB_TREE_NOT_CLEAN"


def test_RB_TREE_NOT_CLEAN_for_a_reviewed_path_that_is_not_tracked(tmp_path):
    repo, head, _ = _fresh(tmp_path)
    paths = ["docs/ghost.md", "src/a.py"]
    kw = U.builder_kwargs(repo, head, paths=U.PATHS, reviewed_paths=paths, required_paths=paths,
                          role_result=U.role_result(head, paths))
    assert U.refusal_code(build_static_receipt, **kw) == "RB_TREE_NOT_CLEAN"


def test_RB_TREE_NOT_CLEAN_for_a_directory_that_is_not_a_repository(tmp_path):
    repo, head, kw = _fresh(tmp_path)
    plain = tmp_path / "plain"
    plain.mkdir()
    kw["snapshot_root"] = str(plain)
    assert U.refusal_code(build_static_receipt, **kw) == "RB_TREE_NOT_CLEAN"


def test_RB_TREE_NOT_CLEAN_for_a_missing_root(tmp_path):
    repo, head, kw = _fresh(tmp_path)
    kw["snapshot_root"] = str(tmp_path / "does-not-exist")
    assert U.refusal_code(build_static_receipt, **kw) == "RB_TREE_NOT_CLEAN"


def test_RB_TREE_NOT_CLEAN_for_a_repository_config_that_can_run_a_program(tmp_path):
    repo, head, kw = _fresh(tmp_path)
    with open(repo / ".git" / "config", "a", encoding="utf-8") as handle:
        handle.write("[alias]\n\tx = !echo hostile\n")
    assert U.refusal_code(build_static_receipt, **kw) == "RB_TREE_NOT_CLEAN"


# --- RB_REPORT_TREE_MISMATCH
def test_RB_REPORT_TREE_MISMATCH_for_a_report_bound_to_another_head(world):
    adapter = U.adapter_result(world.repo, world.head, candidate_head="2" * 40)
    assert code_of(world, adapter_result=adapter) == "RB_REPORT_TREE_MISMATCH"


def test_RB_REPORT_TREE_MISMATCH_for_a_report_without_a_bound_head(world):
    adapter = U.adapter_result(world.repo, world.head, candidate_head=None)
    assert code_of(world, adapter_result=adapter) == "RB_REPORT_TREE_MISMATCH"


def test_RB_REPORT_TREE_MISMATCH_when_the_adapter_tree_digest_differs(world):
    adapter = U.adapter_result(world.repo, world.head, source_tree_sha256="f1" * 32)
    assert code_of(world, adapter_result=adapter) == "RB_REPORT_TREE_MISMATCH"


def test_RB_REPORT_TREE_MISMATCH_when_the_report_tree_digest_differs(world):
    adapter = U.adapter_result(world.repo, world.head, body_over={"source_tree_sha256": "f1" * 32})
    assert code_of(world, adapter_result=adapter) == "RB_REPORT_TREE_MISMATCH"


def test_RB_REPORT_TREE_MISMATCH_when_the_report_scope_is_narrower_than_the_reviewed_set(world):
    adapter = U.adapter_result(world.repo, world.head, body_over={"analysis_scope": ["src/a.py"]})
    assert code_of(world, adapter_result=adapter) == "RB_REPORT_TREE_MISMATCH"


# --- RB_ANALYZER_REFUSED
@pytest.mark.parametrize("outcome", [Outcome.TIMEOUT, Outcome.CRASH, Outcome.INVALID_OUTPUT, Outcome.OUTPUT_CAP])
def test_RB_ANALYZER_REFUSED_for_a_run_that_did_not_finish(world, outcome):
    adapter = U.adapter_result(world.repo, world.head, outcome=outcome)
    assert code_of(world, adapter_result=adapter) == "RB_ANALYZER_REFUSED"


def test_RB_ANALYZER_REFUSED_for_unknown_bindings(world):
    adapter = U.adapter_result(world.repo, world.head, blocking_unknown=("license",))
    assert code_of(world, adapter_result=adapter) == "RB_ANALYZER_REFUSED"


def test_RB_ANALYZER_REFUSED_for_an_adapter_result_without_a_report(world):
    adapter = U.adapter_result(world.repo, world.head, with_report=False)
    assert code_of(world, adapter_result=adapter) == "RB_ANALYZER_REFUSED"


def test_RB_ANALYZER_REFUSED_for_a_report_with_a_missing_key(world):
    adapter = U.adapter_result(world.repo, world.head)
    broken = {k: v for k, v in adapter.report.body.items() if k != "coverage"}
    adapter = U.replace(adapter, report=type(adapter.report)(body=broken))
    assert code_of(world, adapter_result=adapter) == "RB_ANALYZER_REFUSED"


def test_RB_ANALYZER_REFUSED_for_a_malformed_analyzer_digest(world):
    adapter = U.adapter_result(world.repo, world.head, body_over={"analyzer_sha256": "G" * 64})
    assert code_of(world, adapter_result=adapter) == "RB_ANALYZER_REFUSED"


# --- RB_RECEIPT_INVALID
@pytest.mark.parametrize("body_over,findings", [
    ({"covered_rules": ["R2"]}, ()),                                    # rule partition contradicts rule_statuses
    ({"coverage": "PARTIAL"}, ()),                                      # coverage contradicts the partition
    ({}, [U.report_finding(rule="R9")]),                                # finding for a rule that was not checked
    ({}, [U.report_finding(path="src/zzz.py")]),                        # finding path outside analysis_scope
    ({}, [U.report_finding(severity="SEVERE")]),                        # severity outside the receipt enum
    ({}, [U.report_finding(line=0)]),                                   # line must be >= 1
])
def test_RB_RECEIPT_INVALID(world, body_over, findings):
    adapter = U.adapter_result(world.repo, world.head, body_over=body_over, findings=findings)
    assert code_of(world, adapter_result=adapter) == "RB_RECEIPT_INVALID"


# --- RB_SECRET_LIKE_VALUE
def test_RB_SECRET_LIKE_VALUE_for_a_secret_in_a_role_result_text(world):
    assert code_of(world, role_result=U.role_result(world.head, iteration_id=U.FAKE_SECRET)) == "RB_SECRET_LIKE_VALUE"


def test_RB_SECRET_LIKE_VALUE_for_a_secret_in_a_role_result_finding(world):
    finding = U.uc_finding(path=f"src/{U.FAKE_SECRET}.py")
    result = U.role_result(world.head, status="FINDINGS", findings=[finding])
    assert code_of(world, role_result=result) == "RB_SECRET_LIKE_VALUE"


def test_RB_SECRET_LIKE_VALUE_for_a_secret_in_a_report_finding(world):
    adapter = U.adapter_result(world.repo, world.head,
                               findings=[U.report_finding(ref=f"reports/{U.FAKE_SECRET}.json")])
    assert code_of(world, adapter_result=adapter) == "RB_SECRET_LIKE_VALUE"


@pytest.mark.parametrize("field,value", [
    ("profile_id", "password:Abcdefgh12"), ("analyzer_version", "AKIAABCDEFGH1234"), ("analyzer_id", "ghp_abcdefghij1234"),
])
def test_RB_SECRET_LIKE_VALUE_for_a_secret_in_analyzer_provenance(world, field, value):
    adapter = U.adapter_result(world.repo, world.head, body_over={field: value})
    assert code_of(world, adapter_result=adapter) == "RB_SECRET_LIKE_VALUE"


@pytest.mark.parametrize("field,value", [
    ("resolved_model", "AKIAABCDEFGH1234"), ("covered_acceptance", [U.FAKE_SECRET]), ("run_id", "sk-abcdefghijklmnop1234"),
    ("invocation_id", "xoxb-12345-67890"),
])
def test_RB_SECRET_LIKE_VALUE_for_a_secret_in_a_scalar_argument(world, field, value):
    assert code_of(world, **{field: value}) == "RB_SECRET_LIKE_VALUE"


def test_RB_SECRET_LIKE_VALUE_for_a_secret_in_a_narrow_reviewed_path_name(world):
    secret_path = f"src/{U.FAKE_SECRET}.py"
    assert code_of(world, reviewed_paths=[secret_path], required_paths=[secret_path],
                   role_result=U.role_result(world.head, [secret_path])) == "RB_SECRET_LIKE_VALUE"


def test_the_secret_scan_runs_before_the_tree_is_touched(tmp_path):
    repo, head, kw = _fresh(tmp_path)
    kw["role_result"] = U.role_result(head, iteration_id=U.FAKE_SECRET)
    (repo / "junk.txt").write_bytes(b"dirty tree would be RB_TREE_NOT_CLEAN\n")
    assert U.refusal_code(build_static_receipt, **kw) == "RB_SECRET_LIKE_VALUE"


def test_a_refusal_message_never_echoes_the_secret(world):
    with pytest.raises(ContractError) as info:
        build_static_receipt(**kw_for(world, role_result=U.role_result(world.head, iteration_id=U.FAKE_SECRET)))
    assert U.FAKE_SECRET not in str(info.value)
