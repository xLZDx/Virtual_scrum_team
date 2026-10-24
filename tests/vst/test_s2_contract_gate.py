"""S2 E1 reviewer-registry checks and S2.D1/D2 gate acceptance regressions."""

import hashlib

import pytest

from tools.vst import contracts, gate, signing
from tools.vst.contracts import ContractError, TRUSTED_PARSER_CATALOG, validate_receipt
from tests.vst.e1e4_helpers import (
    EPOCH, HEAD, KEY, OPERATOR_KEY, SUPERVISOR_KEY, happy_receipts,
    manifest, unsigned_receipt,
)


def _v2_manifest():
    m = manifest()
    parser_id, parser_version, parser_digest = next(iter(TRUSTED_PARSER_CATALOG))
    m.update({
        "contract_version": 2,
        "reviewer_registry": {"version": "registry-1", "sha256": "d" * 64},
        "mandatory_commands": [{"slot": "tests", "argv": ["pytest", "-q"],
                                "parser_id": parser_id, "parser_version": parser_version,
                                "parser_sha256": parser_digest}],
        "change_scope": {"allowed_paths": ["src/app.py", "tests/test_app.py"]},
    })
    return m


@pytest.mark.parametrize("mutation", [
    lambda m: m["mandatory_commands"].pop(),
    lambda m: m["mandatory_commands"][0].update(parser_id="untrusted.parser"),
    lambda m: m["mandatory_commands"][0].update(parser_version="99"),
    lambda m: m["mandatory_commands"][0].update(parser_sha256="e" * 64),
])
def test_v2_manifest_rejects_missing_or_untrusted_mandatory_parser_pin(mutation):
    m = _v2_manifest()
    mutation(m)
    with pytest.raises(ContractError):
        contracts.validate_task_manifest(m)


def test_gate_refuses_caller_supplied_parser_implementation():
    m = manifest()
    decision = gate.evaluate(
        m, happy_receipts(), HEAD, EPOCH, KEY,
        supervisor_key=SUPERVISOR_KEY,
        parser_catalog={("caller.parser", "1", "a" * 64): lambda _: ([], [], [])},
    )
    assert decision["verdict"] == "MODIFY"
    assert any("parser_catalog must be the trusted built-in catalog" in r for r in decision["reasons"])


def _signed_registry(entries, *, version="registry-1", key=OPERATOR_KEY):
    registry = {"version": version, "entries": entries}
    registry["signature"] = signing.sign(registry, key, signing.REVIEWER_REGISTRY_LABEL)
    return registry


def test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key():
    from tools.vst.gate import _reviewer_registry_ok
    reviewer_key = b"reviewer-key-0123456789-abcdefghij"
    entries = [{"principal": "Reviewer-X", "key_id": "reviewer-x-key"}]
    m = _v2_manifest()
    m["reviewer_registry"]["sha256"] = hashlib.sha256(
        contracts.canonical_bytes({"version": "registry-1", "entries": entries})
    ).hexdigest()
    errors = []
    mapping = _reviewer_registry_ok(
        _signed_registry(entries), m, OPERATOR_KEY, {"reviewer-x-key": reviewer_key}, errors
    )
    assert mapping == {"reviewer-x": "reviewer-x-key"}
    assert errors == []


@pytest.mark.parametrize("failure", ["wrong_key", "stale_version", "digest_mismatch", "duplicate_principal"])
def test_reviewer_registry_failures_do_not_produce_a_trusted_mapping(failure):
    from tools.vst.gate import _reviewer_registry_ok
    entries = [{"principal": "reviewer-x", "key_id": "reviewer-x-key"}]
    version = "registry-1"
    key = OPERATOR_KEY
    if failure == "wrong_key":
        key = KEY
    elif failure == "stale_version":
        version = "registry-old"
    elif failure == "duplicate_principal":
        entries.append({"principal": "REVIEWER-X", "key_id": "reviewer-x-key-2"})
    m = _v2_manifest()
    if failure != "digest_mismatch":
        m["reviewer_registry"]["sha256"] = hashlib.sha256(
            contracts.canonical_bytes({"version": version, "entries": entries})
        ).hexdigest()
    registry = _signed_registry(entries, version=version, key=key)
    errors = []
    result = _reviewer_registry_ok(registry, m, OPERATOR_KEY, {"reviewer-x-key": KEY}, errors)
    assert errors
    if failure in {"wrong_key", "stale_version"}:
        assert result == {}
    if failure == "duplicate_principal":
        assert "reviewer registry contains duplicate principal or key id" in errors


def _valid_v2_receipt(receipt_type):
    item = unsigned_receipt(receipt_type, contract_version=2)
    if receipt_type == "IndependentReview":
        item["reviewer_key_id"] = "reviewer-x-key"
    elif receipt_type == "TestRun":
        parser_id, parser_version, parser_sha = next(iter(TRUSTED_PARSER_CATALOG))
        parsed = {"executed_test_ids": ["t1", "t2"], "skipped_test_ids": [], "xfail_test_ids": []}
        parser_results = [{"argv": ["pytest", "-q"], "parser_id": parser_id,
                          "parser_version": parser_version, "parser_sha256": parser_sha,
                          "parser_result": parsed}]
        diff = {"manifest_sha256": contracts.manifest_sha256(_v2_manifest()),
                "candidate_head": HEAD, "diff_sha256": "e" * 64, "changed_paths": [],
                "verdict": "PASS", "reason": "PASS", "signature": "f" * 64}
        request = {"request_id": "req-1", "task_id": "T1", "slot": "tests", "attempt": 1,
                   "epoch": EPOCH, "manifest_sha256": diff["manifest_sha256"],
                   "candidate_head": HEAD, "commands": [{"argv": ["pytest", "-q"], "exit_code": 0}],
                   "parser_results": parser_results, "artifact_digests": {}}
        item.update({"parser_results": parser_results, "diff_gate": diff,
                     "runner_attestation": {"request": request, "signature": "a" * 64}})
    unsigned = {k: v for k, v in item.items() if k != "signature"}
    item["signature"] = signing.sign(unsigned, KEY, signing.RECEIPT_V2_LABEL)
    return item


@pytest.mark.parametrize("receipt_type", ["TestRun", "StaticAnalysis", "IndependentReview", "Documentation"])
def test_v2_contract_accepts_each_receipt_type_with_its_required_fields(receipt_type):
    validated = validate_receipt(_valid_v2_receipt(receipt_type))
    assert validated["receipt_type"] == receipt_type
    assert validated["contract_version"] == 2


@pytest.mark.parametrize("collision", [
    "worker-supervisor", "worker-operator", "worker-signer", "worker-event", "worker-reviewer",
    "supervisor-operator", "supervisor-signer", "supervisor-event", "supervisor-reviewer",
    "operator-signer", "operator-event", "operator-reviewer", "signer-event", "signer-reviewer",
    "event-reviewer",
])
def test_v2_trust_root_keys_are_pairwise_distinct(collision):
    names = {"worker": KEY, "supervisor": SUPERVISOR_KEY, "operator": OPERATOR_KEY,
             "signer": b"signer-key-0123456789-abcdefghij",
             "event": b"event-key-0123456789-abcdefghijk",
             "reviewer": b"reviewer-key-0123456789-abcdefghij"}
    a, b = collision.split("-")
    names[b] = names[a]
    entries = [{"principal": "reviewer-x", "key_id": "reviewer-x-key"}]
    m = _v2_manifest()
    m["reviewer_registry"]["sha256"] = hashlib.sha256(
        contracts.canonical_bytes({"version": "registry-1", "entries": entries})
    ).hexdigest()
    result = gate.evaluate(
        m, [], HEAD, EPOCH, names["worker"], supervisor_key=names["supervisor"],
        operator_key=names["operator"], reviewer_registry=_signed_registry(entries),
        reviewer_keys={"reviewer-x-key": names["reviewer"]}, signer_key=names["signer"],
        event_key=names["event"],
    )
    assert result["verdict"] != "APPROVE"
    if "reviewer" in collision:
        assert any(
            "reviewer keys must differ from worker, supervisor, operator, signer, and event keys" in reason
            for reason in result["reasons"]
        )
    else:
        assert any("keys must be pairwise distinct" in reason for reason in result["reasons"])


@pytest.mark.parametrize("reviewer_principal", ["unknown-reviewer", "author-y"])
def test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review(reviewer_principal):
    reviewer_key = b"reviewer-key-0123456789-abcdefghij"
    principal = "author-y" if reviewer_principal == "author-y" else "reviewer-x"
    entries = [{"principal": principal, "key_id": "reviewer-x-key"}]
    m = _v2_manifest()
    m["reviewer_registry"]["sha256"] = hashlib.sha256(
        contracts.canonical_bytes({"version": "registry-1", "entries": entries})
    ).hexdigest()
    registry = _signed_registry(entries)
    review = _valid_v2_receipt("IndependentReview")
    review["manifest_sha256"] = contracts.manifest_sha256(m)
    review["reviewer_principal"] = reviewer_principal
    review["author_principal"] = "author-y"
    review["signature"] = signing.sign(
        {k: v for k, v in review.items() if k != "signature"}, reviewer_key, signing.REVIEWER_LABEL
    )
    result = gate.evaluate(
        m, [review], HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
        operator_key=OPERATOR_KEY, reviewer_registry=registry,
        reviewer_keys={"reviewer-x-key": reviewer_key}, signer_key=b"signer-key-0123456789-abcdefghij",
        event_key=b"event-key-0123456789-abcdefghijk",
    )
    assert result["verdict"] != "APPROVE"
    if reviewer_principal == "unknown-reviewer":
        assert any("reviewer principal/key does not match signed registry" in reason
                   for reason in result["reasons"])
    else:
        assert any("manifest author principal is registered as a reviewer" in reason
                   for reason in result["reasons"])


@pytest.mark.parametrize("result", ["FAIL", "MODIFY", "NO_GO", "PASS"])
def test_v2_waiver_scope_never_includes_failure_or_review_rejection(result):
    waiver = {
        "record_id": "W-S2", "operator": "operator-1", "task_id": "T1",
        "epoch": EPOCH, "head": HEAD, "manifest_sha256": "a" * 64,
        "waived_slots": ["tests"], "waived_acceptance": ["AC-1"],
        "expires_epoch": EPOCH, "waived_results": [result],
    }
    waiver["signature"] = signing.sign(waiver, OPERATOR_KEY, signing.WAIVER_LABEL)
    ok, _, _, problems = gate._evaluate_waiver(
        waiver, OPERATOR_KEY, {"task_id": "T1"}, "a" * 64, HEAD, EPOCH,
        ["tests"], ["AC-1"], [result], True,
    )
    assert not ok
    assert any("waived_results must contain only" in p for p in problems)


@pytest.mark.parametrize("result", ["NOT_RUN", "INCONCLUSIVE", "BLOCKED"])
def test_v2_waiver_allows_only_named_non_execution_results(result):
    waiver = {
        "record_id": "W-S2", "operator": "operator-1", "task_id": "T1",
        "epoch": EPOCH, "head": HEAD, "manifest_sha256": "a" * 64,
        "waived_slots": ["tests"], "waived_acceptance": ["AC-1"],
        "expires_epoch": EPOCH, "waived_results": [result],
    }
    waiver["signature"] = signing.sign(waiver, OPERATOR_KEY, signing.WAIVER_LABEL)
    ok, record_id, operator, problems = gate._evaluate_waiver(
        waiver, OPERATOR_KEY, {"task_id": "T1"}, "a" * 64, HEAD, EPOCH,
        ["tests"], ["AC-1"], [result], True,
    )
    assert (ok, record_id, operator, problems) == (True, "W-S2", "operator-1", [])

