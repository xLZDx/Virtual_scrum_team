"""U2-6 (D): gate refusals for the U2 bridge facts on v3 StaticAnalysis receipts.

Receipts are produced by the real receipt_builder, signed with the analyzer-authority key and judged by
gate.evaluate with a real frozen rule catalog and a throwaway git repository. The four U2-4 reasons are
STATIC_FINDINGS_PRESENT, MODEL_RESIDUAL_OPEN, ROLE_TABLE_DRIFT and AEVE_HEAD_DRIFT; all are hard (never waivable)
and a refused run never burns its one-shot nonce. v1 and v2 behaviour is checked as unchanged.
"""

from __future__ import annotations

import copy

import pytest

from tools.vst import analyzer_authority as aa
from tools.vst import analyzer_evidence as ae
from tools.vst import contracts, gate
from tools.vst.contracts import ContractError

from tests.vst import u2_helpers as U
from tests.vst.e1e4_helpers import EPOCH, HEAD, KEY, OPERATOR_KEY, SUPERVISOR_KEY, happy_receipts, manifest, receipt

CODES = ("STATIC_FINDINGS_PRESENT", "MODEL_RESIDUAL_OPEN", "ROLE_TABLE_DRIFT", "AEVE_HEAD_DRIFT")
OTHER_TABLE = "9a" * 32
OTHER_HEAD = "9a" * 20


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return U.make_world(tmp_path_factory.mktemp("u2-gate"))


def run(world, *, waiver=None, nonces=None, pinned_edit=None, **static_kw):
    """Build one static run, trust it, evaluate. Returns (decision, nonces, receipt, payload)."""
    receipt_, payload = U.static_run(world, **static_kw)
    nonces = nonces if nonces is not None else U.Nonces()
    trust = U.make_trust(world, receipt_, payload, nonces=nonces, pinned_edit=pinned_edit)
    return U.evaluate(world, receipt_, trust, waiver=waiver), nonces, receipt_, payload


def text(decision):
    return U.reasons_text(decision)


def rules(world):
    ids = list(world.catalog.required_rule_ids)
    assert len(ids) >= 2  # the frozen catalog has many required rules; two are enough for the partial-coverage cases
    return ids


def forge(**fields):
    """Edit applied to both the receipt body and the payload: a bridge fact the analyzer authority signs."""
    def edit(doc):
        doc.update(copy.deepcopy(fields))
    return edit


# ----------------------------------------------------------------------------------------------- base
def test_base_approve_for_a_fully_local_clean_role_with_pinned_table_and_head(world):
    decision, nonces, receipt_, payload = run(world)
    assert decision["verdict"] == "APPROVE", decision["reasons"]
    assert decision["reasons"] == [] and decision["acceptance_unmet"] == []
    assert contracts.receipt_sha256(receipt_) in decision["required_receipt_hashes"]
    assert nonces.used == [payload["nonce"]]  # consumed exactly once, after the final verdict


def test_the_base_approve_is_bound_to_the_exact_head(world):
    decision, nonces, _, _ = run(world, )
    assert decision["verdict"] == "APPROVE"
    stale = U.evaluate(world, *_signed_pair(world), head="f" * 40)
    assert stale["verdict"] != "APPROVE"


def _signed_pair(world):
    receipt_, payload = U.static_run(world)
    return receipt_, U.make_trust(world, receipt_, payload)


def test_a_v3_manifest_without_analyzer_trust_is_no_go(world):
    receipt_, _ = U.static_run(world)
    decision = U.evaluate(world, receipt_, None)
    assert decision["verdict"] == "NO_GO" and "v3 gate requires analyzer_trust" in text(decision)


def test_missing_evidence_for_the_receipt_is_not_an_approval(world):
    receipt_, payload = U.static_run(world)
    trust = U.make_trust(world, receipt_, payload)
    trust["runs"] = {}
    decision = U.evaluate(world, receipt_, trust)
    assert decision["verdict"] == "MODIFY" and "evidence missing" in text(decision)


# ----------------------------------------------------------------------------- STATIC_FINDINGS_PRESENT
@pytest.mark.parametrize("severity,bridge", [("NIT", "LOW"), ("MINOR", "MEDIUM"), ("MAJOR", "HIGH"), ("BLOCKER", "CRITICAL")])
def test_any_role_finding_severity_is_a_hard_refusal(world, severity, bridge):
    result = U.role_result(world.head, status="FINDINGS", findings=[U.uc_finding(severity)])
    decision, nonces, receipt_, _ = run(world, role_res=result)
    assert (receipt_["findings_count"], receipt_["highest_severity"]) == (1, bridge)
    assert decision["verdict"] == "MODIFY"
    assert "STATIC_FINDINGS_PRESENT" in text(decision) and "findings_count 1" in text(decision)
    assert nonces.used == []


@pytest.mark.parametrize("severity", ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"])
def test_any_receipt_finding_severity_is_a_hard_refusal_even_for_a_clean_role(world, severity):
    finding = U.report_finding(rule=rules(world)[0], severity=severity)
    decision, nonces, receipt_, _ = run(world, findings=[finding])
    assert receipt_["findings_count"] == 0 and len(receipt_["findings"]) == 1
    assert decision["verdict"] == "MODIFY"
    assert "STATIC_FINDINGS_PRESENT" in text(decision) and "1 receipt finding(s)" in text(decision)
    assert nonces.used == []


def test_a_signed_findings_count_alone_is_enough_without_any_receipt_finding(world):
    decision, _, receipt_, _ = run(world, edit=forge(findings_count=3, highest_severity="LOW"))
    assert receipt_["findings"] == []
    assert "STATIC_FINDINGS_PRESENT" in text(decision) and "0 receipt finding(s), findings_count 3" in text(decision)
    assert decision["verdict"] == "MODIFY"


def test_findings_are_refused_with_non_full_coverage_too(world):
    ids = rules(world)
    finding = U.report_finding(rule=ids[-1], severity="LOW")
    decision, nonces, receipt_, _ = run(world, unsupported=[ids[0]], findings=[finding])
    assert receipt_["coverage"] == "PARTIAL"
    assert decision["verdict"] == "MODIFY"
    assert "STATIC_FINDINGS_PRESENT" in text(decision)  # not masked by the coverage reason
    assert "coverage is not FULL" in text(decision)
    assert nonces.used == []


def test_findings_with_a_waiver_present_still_end_in_modify(world):
    result = U.role_result(world.head, status="FINDINGS", findings=[U.uc_finding("NIT")])
    decision, nonces, _, _ = run(world, role_res=result, waiver=U.signed_waiver(world))
    assert decision["verdict"] == "MODIFY"
    assert decision["waiver_record"] is None and decision["human_approvals"] == []
    assert "STATIC_FINDINGS_PRESENT" in text(decision) and nonces.used == []


def test_findings_with_non_full_coverage_and_a_waiver_still_end_in_modify(world):
    ids = rules(world)
    decision, nonces, _, _ = run(world, unsupported=[ids[0]], findings=[U.report_finding(rule=ids[-1])],
                                 waiver=U.signed_waiver(world))
    assert decision["verdict"] == "MODIFY" and decision["waiver_record"] is None
    assert nonces.used == []


def test_control_the_same_waiver_does_approve_partial_coverage_without_findings(world):
    # Shows the waiver machinery works here, so the refusals above are caused by the U2 hard reasons.
    decision, _, _, _ = run(world, unsupported=[rules(world)[0]], waiver=U.signed_waiver(world))
    assert decision["verdict"] == "APPROVED_WITH_WAIVER", decision["reasons"]
    assert decision["waiver_record"] == "W-U2"


# ------------------------------------------------------------------------------ MODEL_RESIDUAL_OPEN
@pytest.mark.parametrize("residual", [["model-judgment"], ["a-one", "b-two"], [f"r{i}" for i in range(8)]])
def test_a_signed_model_residual_is_a_hard_refusal_and_burns_no_nonce(world, residual):
    decision, nonces, receipt_, _ = run(world, edit=forge(model_residual=residual))
    assert receipt_["result"] == "PASS" and receipt_["model_residual"] == residual  # the receipt itself looks fine
    assert decision["verdict"] == "MODIFY"
    assert f"MODEL_RESIDUAL_OPEN: {', '.join(residual)}" in text(decision)
    assert "STATIC_FINDINGS_PRESENT" not in text(decision)
    assert nonces.used == []


def test_model_residual_is_not_waivable(world):
    decision, nonces, _, _ = run(world, edit=forge(model_residual=["model-judgment"]), waiver=U.signed_waiver(world))
    assert decision["verdict"] == "MODIFY" and decision["waiver_record"] is None and decision["human_approvals"] == []
    assert "MODEL_RESIDUAL_OPEN" in text(decision) and nonces.used == []


def test_model_residual_is_refused_with_non_full_coverage_too(world):
    decision, _, _, _ = run(world, edit=forge(model_residual=["model-judgment"]), unsupported=[rules(world)[0]])
    assert "MODEL_RESIDUAL_OPEN" in text(decision) and "coverage is not FULL" in text(decision)
    assert decision["verdict"] == "MODIFY"


def test_a_residual_that_the_builder_itself_never_offers_pass_for(world):
    result = U.role_result(world.head, klass="LOCAL_PLUS_MODEL", status="FINDINGS", findings=[U.uc_finding("MINOR")],
                           residual=["model-judgment"])
    decision, nonces, receipt_, _ = run(world, role_res=result)
    assert receipt_["result"] == "INCONCLUSIVE"
    assert "MODEL_RESIDUAL_OPEN" in text(decision) and "STATIC_FINDINGS_PRESENT" in text(decision)
    assert nonces.used == []


# ------------------------------------------------------------------ ROLE_TABLE_DRIFT / AEVE_HEAD_DRIFT
DELETE = object()


def pin_edit(name, value):
    def edit(pinned):
        out = dict(pinned)
        if value is DELETE:
            out.pop(name)
        else:
            out[name] = value
        return out
    return edit


TABLE_PINS = {
    "missing": DELETE, "none": None, "int": 5, "bool": True, "bytes": U.TABLE_SHA.encode(), "list": [U.TABLE_SHA],
    "upper": U.TABLE_SHA.upper(), "short": U.TABLE_SHA[:63], "long": U.TABLE_SHA + "0", "zero": "0" * 64,
    "empty": "", "different": OTHER_TABLE, "newline": U.TABLE_SHA + "\n",
}
HEAD_PINS = {
    "missing": DELETE, "none": None, "int": 5, "bool": True, "bytes": U.AEVE_HEAD.encode(), "list": [U.AEVE_HEAD],
    "upper": U.AEVE_HEAD.upper(), "short": U.AEVE_HEAD[:39], "sha256-length": "d4" * 32, "zero": "0" * 40,
    "empty": "", "different": OTHER_HEAD, "newline": U.AEVE_HEAD + "\n",
}


@pytest.mark.parametrize("label", list(TABLE_PINS))
def test_ROLE_TABLE_DRIFT(world, label):
    decision, nonces, _, _ = run(world, pinned_edit=pin_edit("role_table_sha256", TABLE_PINS[label]))
    assert decision["verdict"] == "MODIFY"
    assert "ROLE_TABLE_DRIFT" in text(decision) and "AEVE_HEAD_DRIFT" not in text(decision)
    assert nonces.used == []


@pytest.mark.parametrize("label", list(HEAD_PINS))
def test_AEVE_HEAD_DRIFT(world, label):
    decision, nonces, _, _ = run(world, pinned_edit=pin_edit("aeve_head", HEAD_PINS[label]))
    assert decision["verdict"] == "MODIFY"
    assert "AEVE_HEAD_DRIFT" in text(decision) and "ROLE_TABLE_DRIFT" not in text(decision)
    assert nonces.used == []


@pytest.mark.parametrize("pinned", ["not a dict", None, 7, [], ["role_table_sha256"]])
def test_a_pinned_block_that_is_not_a_mapping_reports_both_drifts(world, pinned):
    decision, nonces, _, _ = run(world, pinned_edit=lambda p: pinned)
    assert decision["verdict"] == "MODIFY"
    assert "ROLE_TABLE_DRIFT" in text(decision) and "AEVE_HEAD_DRIFT" in text(decision)
    assert nonces.used == []


def test_drift_is_refused_with_waiver_and_with_non_full_coverage(world):
    decision, nonces, _, _ = run(world, pinned_edit=pin_edit("aeve_head", OTHER_HEAD), unsupported=[rules(world)[0]],
                                 waiver=U.signed_waiver(world))
    assert decision["verdict"] == "MODIFY" and decision["waiver_record"] is None
    assert "AEVE_HEAD_DRIFT" in text(decision) and "coverage is not FULL" in text(decision)
    assert nonces.used == []


def test_a_different_table_digest_in_the_receipt_than_in_the_gate_pin_is_drift_even_when_the_evidence_agrees(world):
    # receipt, payload, evidence and expectation all say OTHER_TABLE; only the gate-owned pin says TABLE_SHA
    receipt_, payload = U.static_run(world, edit=forge(role_table_sha256=OTHER_TABLE))
    trust = U.make_trust(world, receipt_, payload)
    trust["pinned"]["role_table_sha256"] = U.TABLE_SHA
    decision = U.evaluate(world, receipt_, trust)
    assert decision["verdict"] == "MODIFY" and "ROLE_TABLE_DRIFT" in text(decision)


def test_the_pin_is_never_taken_from_the_runs_expectation(world):
    receipt_, payload = U.static_run(world, edit=forge(aeve_head=OTHER_HEAD))
    trust = U.make_trust(world, receipt_, payload)
    trust["pinned"].pop("aeve_head")
    assert "AEVE_HEAD_DRIFT" in text(U.evaluate(world, receipt_, trust))


# ------------------------------------------------------------------------- all four reasons together
def test_all_four_reasons_are_reported_in_one_pass(world):
    result = U.role_result(world.head, status="FINDINGS", findings=[U.uc_finding("BLOCKER")], residual=["model-judgment"])
    decision, nonces, _, _ = run(
        world, role_res=result,
        pinned_edit=lambda p: {**p, "role_table_sha256": OTHER_TABLE, "aeve_head": OTHER_HEAD})
    assert decision["verdict"] == "MODIFY"
    for code in CODES:
        assert text(decision).count(code) == 1, code
    assert nonces.used == []


def test_all_four_reasons_survive_a_waiver_and_partial_coverage(world):
    result = U.role_result(world.head, status="FINDINGS", findings=[U.uc_finding("NIT")], residual=["model-judgment"])
    decision, nonces, _, _ = run(
        world, role_res=result, unsupported=[rules(world)[0]], waiver=U.signed_waiver(world),
        pinned_edit=lambda p: {**p, "role_table_sha256": OTHER_TABLE, "aeve_head": OTHER_HEAD})
    assert decision["verdict"] == "MODIFY" and decision["waiver_record"] is None
    assert all(code in text(decision) for code in CODES) and "coverage is not FULL" in text(decision)
    assert nonces.used == []


# --------------------------------------------------------------------- replay over a changed bridge fact
@pytest.mark.parametrize("field,new", [
    ("role_table_sha256", OTHER_TABLE), ("aeve_head", OTHER_HEAD), ("reviewed_paths_sha256", "9a" * 32),
])
def test_old_signed_evidence_does_not_back_a_receipt_with_a_changed_bridge_fact(world, field, new):
    _, old_payload = U.static_run(world)
    old_evidence = aa.sign_analyzer_evidence(old_payload, U.ANALYZER_KEY, U.OTHER_ROLE_KEYS)
    receipt_, payload = U.static_run(world, edit=forge(**{field: new}))  # new receipt, pins follow it (no drift)
    nonces = U.Nonces()
    trust = U.make_trust(world, receipt_, payload, nonces=nonces, evidence=old_evidence)
    decision = U.evaluate(world, receipt_, trust)
    assert decision["verdict"] == "MODIFY"
    assert "analyzer authority evidence rejected" in text(decision)
    assert not any(code in text(decision) for code in CODES)  # only the replay is the problem here
    assert nonces.used == []


@pytest.mark.parametrize("field,new", [("findings_count", 2), ("model_residual", ["model-judgment"])])
def test_old_clean_evidence_cannot_launder_a_receipt_that_now_carries_findings_or_residual(world, field, new):
    _, old_payload = U.static_run(world)
    old_evidence = aa.sign_analyzer_evidence(old_payload, U.ANALYZER_KEY, U.OTHER_ROLE_KEYS)
    edit = forge(findings_count=2, highest_severity="LOW") if field == "findings_count" else forge(model_residual=new)
    receipt_, payload = U.static_run(world, edit=edit)
    nonces = U.Nonces()
    decision = U.evaluate(world, receipt_, U.make_trust(world, receipt_, payload, nonces=nonces, evidence=old_evidence))
    assert decision["verdict"] == "MODIFY" and nonces.used == []
    assert ("STATIC_FINDINGS_PRESENT" if field == "findings_count" else "MODEL_RESIDUAL_OPEN") in text(decision)


def test_a_spent_nonce_makes_the_second_evaluation_no_go(world):
    first, nonces, receipt_, payload = run(world)
    assert first["verdict"] == "APPROVE"
    again = U.evaluate(world, receipt_, U.make_trust(world, receipt_, payload, nonces=nonces))
    assert again["verdict"] == "NO_GO" and "nonce replayed" in text(again)
    assert again["human_approvals"] == [] and again["waiver_record"] is None


def test_the_receipt_signed_by_a_non_authority_key_is_rejected(world):
    receipt_, payload = U.static_run(world)
    body = {k: v for k, v in receipt_.items() if k != "signature"}
    forged = {**body, "signature": contracts_sign(body, U.SIGNER_KEY)}
    decision = U.evaluate(world, forged, U.make_trust(world, forged, payload))
    assert decision["verdict"] != "APPROVE" and "invalid signature" in text(decision)


def contracts_sign(body, key):
    from tools.vst import signing
    return signing.sign(body, key, contracts.RECEIPT_V3_LABEL)


# -------------------------------------------------------------------------------- v1 / v2 unchanged
def test_v1_gate_behaviour_is_unchanged_and_ignores_analyzer_trust():
    base = gate.evaluate(manifest(), happy_receipts(), HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
                         operator_key=OPERATOR_KEY)
    assert base["verdict"] == "APPROVE" and base["reasons"] == []
    with_trust = gate.evaluate(manifest(), happy_receipts(), HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
                               operator_key=OPERATOR_KEY, analyzer_trust={"junk": 1})
    assert with_trust == base
    assert not any(code in " ".join(base["reasons"]) for code in CODES)


@pytest.mark.parametrize("extra", ["findings_count", "model_residual", "role_table_sha256", "aeve_head"])
def test_a_v1_static_receipt_carrying_a_bridge_field_is_invalid_at_the_gate(extra):
    value = {"findings_count": 0, "model_residual": [], "role_table_sha256": "a1" * 32, "aeve_head": "d4" * 20}[extra]
    receipts = [receipt("TestRun"), receipt("StaticAnalysis", **{extra: value}), receipt("IndependentReview")]
    decision = gate.evaluate(manifest(), receipts, HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
                             operator_key=OPERATOR_KEY)
    assert decision["verdict"] != "APPROVE" and "invalid" in text(decision)


def test_v2_gate_behaviour_is_unchanged_by_the_presence_of_analyzer_trust():
    from tests.vst.test_s2_runner_lifecycle import SIGNER_KEY, _authority_fixture, _authority_receipt

    m, registry, reviewer_key, keys = _authority_fixture()
    receipts = [
        _authority_receipt("TestRun", "tests", keys["signer"], m),
        _authority_receipt("StaticAnalysis", "static", KEY, m),
        _authority_receipt("IndependentReview", "review", reviewer_key, m),
        _authority_receipt("Documentation", "doc", KEY, m),
    ]

    def evaluate(**extra):
        return gate.evaluate(m, receipts, "a" * 40, 2, KEY, supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
                             reviewer_registry=registry, reviewer_keys={"reviewer-key-1": reviewer_key},
                             signer_key=SIGNER_KEY, event_key=keys["event"], **extra)

    plain = evaluate()
    assert evaluate(analyzer_trust={"junk": 1}) == plain
    assert plain["verdict"] != "NO_GO"
    assert not any(code in " ".join(plain["reasons"]) for code in CODES)


def test_a_v3_receipt_does_not_satisfy_a_v2_manifest_and_a_v2_receipt_does_not_satisfy_v3(world):
    receipt_, payload = U.static_run(world)
    trust = U.make_trust(world, receipt_, payload)
    v2_static = receipt("StaticAnalysis", contract_version=2, manifest_sha256=world.manifest_sha)
    decision = U.evaluate(world, receipt_, trust, receipts=[world.tests, v2_static, world.review])
    assert decision["verdict"] != "APPROVE" and "contract version does not match manifest" in text(decision)


# ------------------------------------------------------------------- evidence-record pin-check cases
def record(world, receipt_, decision, **facts):
    return ae.build_evidence_record(manifest=world.manifest, receipt=receipt_, decision=decision, facts=facts)


PINS_OK = {"pinned_role_table_sha256": U.TABLE_SHA, "pinned_aeve_head": U.AEVE_HEAD}


def test_pin_checks_are_pass_for_an_approving_decision_with_equal_pins(world):
    decision, _, receipt_, _ = run(world)
    rec = record(world, receipt_, decision, **PINS_OK)
    assert (rec["role_table_sha256_pin_check"], rec["aeve_head_pin_check"]) == ("PASS", "PASS")
    assert rec["signature_verified"] is True and rec["gate_verdict"] == "APPROVE"
    assert rec["role_table_sha256"] == U.TABLE_SHA and rec["aeve_head"] == U.AEVE_HEAD
    assert ae.verify_evidence_record(rec, expected_head=world.head, expected_manifest_sha256=world.manifest_sha)


def test_pin_checks_are_not_run_without_pins_and_without_a_receipt(world):
    decision, _, receipt_, _ = run(world)
    rec = record(world, receipt_, decision)
    assert (rec["role_table_sha256_pin_check"], rec["aeve_head_pin_check"]) == ("NOT_RUN", "NOT_RUN")
    no_receipt = ae.build_evidence_record(decision=decision, facts=PINS_OK)
    assert (no_receipt["role_table_sha256_pin_check"], no_receipt["aeve_head_pin_check"]) == ("NOT_RUN", "NOT_RUN")
    assert no_receipt["role_table_sha256"]["label"] == "NOT_RUN"


def test_a_pin_that_differs_from_the_receipt_is_fail_under_a_refusing_decision(world):
    decision, _, receipt_, _ = run(world, pinned_edit=pin_edit("role_table_sha256", OTHER_TABLE))
    assert decision["verdict"] == "MODIFY"
    rec = record(world, receipt_, decision, pinned_role_table_sha256=OTHER_TABLE, pinned_aeve_head=U.AEVE_HEAD)
    assert rec["role_table_sha256_pin_check"] == "FAIL"
    assert rec["aeve_head_pin_check"] == "NOT_RUN"  # equal pin but the decision is not APPROVE, so never PASS
    assert rec["signature_verified"]["label"] == "NOT_RUN"


def test_equal_pins_under_a_findings_refusal_are_not_run_never_pass(world):
    result = U.role_result(world.head, status="FINDINGS", findings=[U.uc_finding("NIT")])
    decision, _, receipt_, _ = run(world, role_res=result)
    rec = record(world, receipt_, decision, **PINS_OK)
    assert (rec["role_table_sha256_pin_check"], rec["aeve_head_pin_check"]) == ("NOT_RUN", "NOT_RUN")
    assert rec["findings_count"] == 1 and rec["highest_severity"] == "LOW"


def test_pass_that_contradicts_a_drift_reason_raises(world):
    decision, _, receipt_, _ = run(world, pinned_edit=pin_edit("role_table_sha256", OTHER_TABLE))
    assert "ROLE_TABLE_DRIFT" in text(decision)
    with pytest.raises(ContractError) as info:
        record(world, receipt_, decision, pinned_role_table_sha256=U.TABLE_SHA)  # claims the receipt matched its pin
    assert "contradicts the decision reason ROLE_TABLE_DRIFT" in str(info.value)


def test_pass_that_contradicts_an_aeve_head_drift_reason_raises(world):
    decision, _, receipt_, _ = run(world, pinned_edit=pin_edit("aeve_head", OTHER_HEAD))
    with pytest.raises(ContractError) as info:
        record(world, receipt_, decision, pinned_aeve_head=U.AEVE_HEAD)
    assert "AEVE_HEAD_DRIFT" in str(info.value)


@pytest.mark.parametrize("facts", [
    {"pinned_role_table_sha256": OTHER_TABLE}, {"pinned_aeve_head": OTHER_HEAD},
])
def test_fail_under_approve_raises(world, facts):
    decision, _, receipt_, _ = run(world)
    assert decision["verdict"] == "APPROVE"
    with pytest.raises(ContractError) as info:
        record(world, receipt_, decision, **facts)
    assert "FAIL contradicts an accepting decision" in str(info.value)


@pytest.mark.parametrize("facts", [
    {"pinned_role_table_sha256": OTHER_TABLE}, {"pinned_aeve_head": OTHER_HEAD},
])
def test_fail_under_approve_with_waiver_raises(world, facts):
    decision, _, receipt_, _ = run(world, unsupported=[rules(world)[0]], waiver=U.signed_waiver(world))
    assert decision["verdict"] == "APPROVED_WITH_WAIVER"
    with pytest.raises(ContractError) as info:
        record(world, receipt_, decision, **facts)
    assert "FAIL contradicts an accepting decision" in str(info.value)


@pytest.mark.parametrize("bad", [123, True, b"x", ["a"], {"a": 1}, 1.5])
def test_a_non_string_pin_is_refused(world, bad):
    decision, _, receipt_, _ = run(world)
    with pytest.raises(ContractError):
        record(world, receipt_, decision, pinned_role_table_sha256=bad)


def test_unknown_facts_are_refused_and_the_record_digest_catches_tampering(world):
    decision, _, receipt_, _ = run(world)
    with pytest.raises(ContractError):
        record(world, receipt_, decision, pinned_something_else=U.TABLE_SHA)
    rec = record(world, receipt_, decision, pinned_role_table_sha256=U.TABLE_SHA)
    forged = dict(rec, role_table_sha256_pin_check="FAIL" if rec["role_table_sha256_pin_check"] == "PASS" else "PASS")
    assert not ae.verify_evidence_record(forged, expected_head=world.head, expected_manifest_sha256=world.manifest_sha)
    assert not ae.verify_evidence_record(rec, expected_head="f" * 40, expected_manifest_sha256=world.manifest_sha)
