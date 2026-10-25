"""Hash-bound S4 seeded failures exercised against unchanged VST APIs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.qa import registry
from tools.qa.pytest_pass_plugin import record_seeded_failure_observation
from tools.vst import diffgate, gate
from tools.vst.contracts import derive_result
from tests.vst.e1e4_helpers import (
    EPOCH, HEAD, KEY, SUPERVISOR_KEY, bound, manifest,
)

pytest_plugins = ("tools.qa.pytest_pass_plugin",)
ROOT = Path(__file__).resolve().parents[2]
HERE = "tests/qa/test_s4_seeded_failures.py"


def _fixture(fixture_id: str, test_name: str) -> tuple[dict, str, str]:
    loaded_registry, _ = registry.load_registry(ROOT)
    catalog, _ = registry.load_seeded_failure_catalog(ROOT, loaded_registry)
    fixture = next(row for row in catalog["fixtures"] if row["fixture_id"] == fixture_id)
    expected_id = f"{HERE}::{test_name}"
    assert fixture["test_id"] == expected_id
    digest = hashlib.sha256(
        json.dumps(
            fixture["input"], sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    assert fixture["input_sha256"] == digest
    return fixture["input"], digest, fixture["expected_rejection"]


def _record(fixture_id: str, digest: str, expected: str, observed: str, test_name: str) -> None:
    assert observed == expected
    record_seeded_failure_observation(
        fixture_id=fixture_id,
        input_sha256=digest,
        expected_rejection=expected,
        observed_rejection=observed,
        test_id=f"{HERE}::{test_name}",
    )


def test_seeded_stale_head_rejects_current_gate_decision():
    fixture_id = "stale-head"
    input_data, digest, expected = _fixture(
        fixture_id, "test_seeded_stale_head_rejects_current_gate_decision",
    )
    task = manifest()
    receipts = [
        bound(task, "TestRun", candidate_head=input_data["receipt_head"]),
        bound(task, "StaticAnalysis"),
        bound(task, "IndependentReview"),
    ]
    decision = gate.evaluate(
        task, receipts, input_data["current_head"], input_data["current_epoch"], KEY,
        supervisor_key=SUPERVISOR_KEY,
    )
    reasons = " | ".join(decision["reasons"]).lower()
    observed = "STALE_HEAD" if "stale head" in reasons else "NO_REJECTION"
    assert decision["verdict"] != "APPROVE"
    _record(fixture_id, digest, expected, observed,
            "test_seeded_stale_head_rejects_current_gate_decision")


def test_seeded_missing_receipt_is_non_approving():
    fixture_id = "missing-required-receipt"
    input_data, digest, expected = _fixture(
        fixture_id, "test_seeded_missing_receipt_is_non_approving",
    )
    task = manifest()
    slot_types = {row["slot"]: row["receipt_type"] for row in task["required_receipts"]}
    receipts = [
        bound(task, receipt_type)
        for slot, receipt_type in slot_types.items()
        if slot != input_data["missing_slot"]
    ]
    decision = gate.evaluate(
        task, receipts, HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
    )
    reasons = " | ".join(decision["reasons"]).lower()
    observed = (
        "MISSING_REQUIRED_RECEIPT"
        if f"missing receipt for slot '{input_data['missing_slot']}'" in reasons
        else "NO_REJECTION"
    )
    assert decision["verdict"] != "APPROVE"
    _record(fixture_id, digest, expected, observed,
            "test_seeded_missing_receipt_is_non_approving")


def test_seeded_invalid_signature_is_rejected():
    fixture_id = "invalid-signature"
    input_data, digest, expected = _fixture(
        fixture_id, "test_seeded_invalid_signature_is_rejected",
    )
    task = manifest()
    forged = bound(task, "TestRun")
    forged["signature"] = input_data["signature"]
    decision = gate.evaluate(
        task,
        [forged, bound(task, "StaticAnalysis"), bound(task, "IndependentReview")],
        HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
    )
    reasons = " | ".join(decision["reasons"]).lower()
    observed = "INVALID_SIGNATURE" if "invalid signature" in reasons else "NO_REJECTION"
    assert decision["verdict"] != "APPROVE"
    _record(fixture_id, digest, expected, observed,
            "test_seeded_invalid_signature_is_rejected")


def test_seeded_out_of_scope_diff_fails():
    fixture_id = "out-of-scope-diff"
    input_data, digest, expected = _fixture(
        fixture_id, "test_seeded_out_of_scope_diff_fails",
    )
    evidence = diffgate.check_diff(
        manifest_sha256=input_data["manifest_sha256"],
        base_head=input_data["base_head"],
        candidate_head=input_data["candidate_head"],
        changed_paths=input_data["changed_paths"],
        allowed_paths=input_data["allowed_paths"],
        diff_bytes=b"seeded out-of-scope diff",
    )
    observed = evidence["reason"]
    assert evidence["verdict"] == "FAIL"
    _record(fixture_id, digest, expected, observed,
            "test_seeded_out_of_scope_diff_fails")


def test_seeded_skipped_required_id_derives_failure():
    fixture_id = "skipped-required-id"
    input_data, digest, expected = _fixture(
        fixture_id, "test_seeded_skipped_required_id_derives_failure",
    )
    receipt = bound(
        manifest(), "TestRun",
        expected_test_ids=input_data["expected_test_ids"],
        executed_test_ids=input_data["executed_test_ids"],
        skipped_test_ids=input_data["skipped_test_ids"],
        xfail_test_ids=input_data["xfail_test_ids"],
    )
    observed = (
        "SKIPPED_REQUIRED_ID"
        if (receipt["result"] == "FAIL"
            and set(input_data["skipped_test_ids"]) & set(input_data["expected_test_ids"]))
        else "NO_REJECTION"
    )
    assert derive_result(receipt) == "FAIL"
    _record(fixture_id, digest, expected, observed,
            "test_seeded_skipped_required_id_derives_failure")


def test_seeded_artifact_digest_mismatch_is_non_approving():
    fixture_id = "artifact-digest-mismatch"
    input_data, digest, expected = _fixture(
        fixture_id, "test_seeded_artifact_digest_mismatch_is_non_approving",
    )
    task = manifest()
    test_run = bound(
        task, "TestRun",
        artifact_digests={input_data["artifact_path"]: input_data["claimed_sha256"]},
    )
    receipts = [test_run, bound(task, "StaticAnalysis"), bound(task, "IndependentReview")]
    decision = gate.evaluate(
        task, receipts, HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
        artifact_resolver=lambda _path: input_data["observed_sha256"],
    )
    reasons = " | ".join(decision["reasons"]).lower()
    observed = (
        "ARTIFACT_DIGEST_MISMATCH"
        if "digest mismatch" in reasons else "NO_REJECTION"
    )
    assert decision["verdict"] != "APPROVE"
    _record(fixture_id, digest, expected, observed,
            "test_seeded_artifact_digest_mismatch_is_non_approving")
