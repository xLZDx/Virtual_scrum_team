"""Functional contract for the local synthetic E8 lifecycle report.

These tests exercise repository fixtures only. A signed fixture probe is supplied so the
supervisor's existing protocol path can run, but it is not evidence of host isolation or E8
acceptance.
"""
from __future__ import annotations

import hashlib
import tempfile

import pytest

from tools.vst import preflight, slice as slice_module

PROBE_KEY = b"s2-e8-synthetic-probe-key-0123456789"
CHECKED_PROPERTIES = {
    "automount_disabled": True,
    "interop_disabled": True,
    "no_container_socket": True,
    "non_root": True,
    "external_egress_blocked": True,
    "loopback_canary": True,
    "empty_external_allowlist": True,
}


def _synthetic_probe(run_id: str, nonce: str) -> dict:
    """Build a protocol-valid probe fixture with explicitly synthetic provenance."""
    spec_sha256 = hashlib.sha256(preflight.SPEC_PATH.read_bytes()).hexdigest()
    attestation = preflight.sign_network_policy_attestation(
        {
            "run_id": run_id,
            "spec_sha256": spec_sha256,
            "nonce": nonce,
            "environment_id": "synthetic-test-fixture-only",
            "policy_sha256": "a" * 64,
            "evidence_sha256": "b" * 64,
            "empty_external_allowlist": True,
            "no_container_socket": True,
            "no_unapproved_host_paths": True,
        },
        slice_module.OPERATOR_KEY,
    )
    return preflight.sign_inventory(
        {
            "run_id": run_id,
            "spec_sha256": spec_sha256,
            "nonce": nonce,
            "checked_properties": dict(CHECKED_PROPERTIES),
            "result": "PASS",
            "inventory": {
                "fixture": True,
                "container_socket_inventory_complete": True,
                "network_policy_attestation": attestation,
            },
        },
        PROBE_KEY,
    )


@pytest.fixture(scope="module")
def lifecycle_report():
    """Run once in a disposable root and remove it even when pytest retains tmp_path."""
    with tempfile.TemporaryDirectory(prefix="s2-e8-synthetic-lifecycle-") as workdir:
        yield slice_module.run_lifecycle_scenarios(
            workdir,
            probe_key=PROBE_KEY,
            probe_provider=_synthetic_probe,
        )


def test_report_explicitly_does_not_claim_real_e8_acceptance(lifecycle_report):
    scope = lifecycle_report["scope"]

    assert scope["environment_scope"] == "synthetic"
    assert scope["e8_acceptance"] == "NOT_ESTABLISHED"
    assert scope["real_e5_e6_s1_environment_qualification"] == "NOT_RUN"
    assert scope["real_blocked_egress_attempt"] == "NOT_RUN"
    assert scope["external_candidate_comparison"] == "NOT_RUN"
    assert scope["operator_worker_choice"] == "NOT_ESTABLISHED"


def test_restricted_process_crash_is_not_run_or_claimed_as_containment(lifecycle_report):
    report = lifecycle_report["crash_stop_resume"]
    outcomes = {item["step"]: item for item in report["observed_outcomes"]}
    child_exit = outcomes["worker_child_self_exit_after_partial_edit"]

    assert child_exit["outcome"] == "NOT_RUN"
    assert child_exit["reason"] == "restricted_process_crash_scenario_not_executed"
    assert child_exit["exit_code"] is None
    assert report["child_self_exit_scenario"] == "NOT_RUN"
    assert report["child_exit_code"] is None
    assert report["process_kill_containment_proven"] is False


def test_out_of_scope_edit_is_rejected_before_target_creation(lifecycle_report):
    report = lifecycle_report["crash_stop_resume"]

    assert report["out_of_scope_write_rejected"] is True
    assert report["out_of_scope_target_absent"] is True


def test_existing_stop_cleanup_precedes_fresh_epoch_resume(lifecycle_report):
    report = lifecycle_report["crash_stop_resume"]
    outcomes = {item["step"]: item for item in report["observed_outcomes"]}

    assert report["stop_cleanup_completed_before_resume"] is True
    assert report["stop_was_injected"] is False
    assert outcomes["existing_supervisor_stop_call_and_cleanup"]["outcome"] == "COMPLETED"
    assert outcomes["existing_supervisor_stop_call_and_cleanup"]["injected_stop_scenario"] is False
    assert report["fresh_epoch_resumed"] is True
    assert report["resumed_epoch"] > report["expired_epoch"]


def test_report_marks_budget_overflow_as_rejected(lifecycle_report):
    budget = lifecycle_report["budget_exhaustion"]

    assert budget["remaining_at_exact_cap"] == 0
    assert budget["overflow_rejected"] is True
    assert budget["overflow_outcome"] == "REJECTED"


def test_caller_probe_values_are_not_upgraded_to_environment_egress_evidence(lifecycle_report):
    observations = lifecycle_report["caller_supplied_probe_observations"]

    assert len(observations["runs"]) == 2
    assert all(
        run["scope"] == "caller_supplied_probe_data_not_independent_environment_evidence"
        for run in observations["runs"]
    )
    assert all(run["reported_external_egress_blocked"] is True for run in observations["runs"])
    assert observations["real_environment_egress_verified"] is False

