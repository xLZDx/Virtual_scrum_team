"""Synthetic failures exercised through unchanged VST validation interfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.qa.fixtures import input_sha256, record_fixture_observation
from tools.vst.contracts import (
    ContractError,
    derive_result,
    validate_gate_decision,
    validate_receipt,
    validate_task_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs" / "qa" / "fixtures.json"


def _fixture(fixture_id: str) -> dict[str, Any]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert catalog["status"] == "SUPPORTED"
    fixture = next(row for row in catalog["fixtures"] if row["fixture_id"] == fixture_id)
    assert fixture["input_sha256"] == input_sha256(fixture["input"])
    return fixture


def test_s4_seeded_invalid_task_manifest_is_rejected_and_observed():
    fixture = _fixture("QA-SEED-INVALID-TASK-MANIFEST")
    assert fixture["source_interface"] == "tools.vst.contracts.validate_task_manifest"
    assert fixture["test_id"] == (
        "tests/qa/test_s4_seeded_failure_contracts.py::"
        "test_s4_seeded_invalid_task_manifest_is_rejected_and_observed"
    )
    assert fixture["expected_rejection"] == "FAIL"

    with pytest.raises(ContractError, match="task_manifest_v2: missing field"):
        validate_task_manifest(fixture["input"])

    record_fixture_observation(fixture["fixture_id"], "FAIL")


def test_s4_seeded_invalid_approve_decision_is_rejected_and_observed():
    fixture = _fixture("QA-SEED-APPROVE-WITH-UNMET-REASONS")
    assert fixture["source_interface"] == "tools.vst.contracts.validate_gate_decision"
    assert fixture["test_id"] == (
        "tests/qa/test_s4_seeded_failure_contracts.py::"
        "test_s4_seeded_invalid_approve_decision_is_rejected_and_observed"
    )
    assert fixture["expected_rejection"] == "FAIL"

    with pytest.raises(ContractError, match="verdict APPROVE requires empty reasons"):
        validate_gate_decision(fixture["input"])

    record_fixture_observation(fixture["fixture_id"], "FAIL")


def test_s4_seeded_skipped_required_test_derives_fail_and_is_observed():
    fixture = _fixture("QA-SEED-SKIPPED-REQUIRED-TEST")
    assert fixture["source_interface"] == "tools.vst.contracts.derive_result"
    assert fixture["test_id"] == (
        "tests/qa/test_s4_seeded_failure_contracts.py::"
        "test_s4_seeded_skipped_required_test_derives_fail_and_is_observed"
    )
    assert fixture["expected_rejection"] == "FAIL"

    receipt = validate_receipt(fixture["input"])
    observed = derive_result(receipt)

    assert observed == "FAIL"
    record_fixture_observation(fixture["fixture_id"], observed)
