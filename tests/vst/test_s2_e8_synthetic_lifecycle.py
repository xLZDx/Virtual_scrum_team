"""Functional contract for the local synthetic E8 lifecycle report.

These tests exercise repository fixtures only. An unsigned root-captured synthetic probe is
supplied so the supervisor's protocol path can run, but it is not evidence of host isolation or
E8 acceptance.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import tempfile

import pytest

from tools.vst import preflight, slice as slice_module

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
    return {
        "run_id": run_id,
        "spec_sha256": spec_sha256,
        "nonce": nonce,
        "checked_properties": dict(CHECKED_PROPERTIES),
        "result": "PASS",
        "inventory": {
            "mount_table": [],
            "windows_drive_mounts": [],
            "wsl_interop_present": False,
            "wsl_interop_enabled": False,
            "uid": 1001,
            "gid": 1001,
            "container_socket_paths_present": [],
            "container_socket_inventory_complete": True,
            "blocked_egress_target": ["198.51.100.1", 9],
            "blocked_egress_probe_scope": "single reserved-target smoke probe; does not prove egress policy",
            "network_policy_attestation": attestation,
            "environment_variable_names": [],
            "observed_at_monotonic_ns": 1,
        },
    }


@pytest.fixture(scope="module")
def lifecycle_report():
    """Run once in a disposable root and remove it even when pytest retains tmp_path."""
    with tempfile.TemporaryDirectory(prefix="s2-e8-synthetic-lifecycle-") as temp_root:
        workdir = os.path.join(temp_root, "work")
        yield slice_module.run_lifecycle_scenarios(
            workdir,
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


def test_restricted_process_stop_resume_and_mutation_scenarios_remain_unrun(lifecycle_report):
    restricted = lifecycle_report["restricted_scenarios"]

    assert restricted["child_process_self_exit"] == "NOT_RUN"
    assert restricted["process_kill_containment"] == "NOT_RUN"
    assert restricted["stop"] == "NOT_RUN"
    assert restricted["crash_resume_and_store_restart"] == "NOT_RUN"
    assert restricted["out_of_scope_write_attempt"] == "NOT_RUN"
    assert restricted["out_of_scope_target_created"] is False
    assert restricted["external_egress_attempt"] == "NOT_RUN"
    assert lifecycle_report["restart_idempotency"]["scenario"] == "NOT_RUN"


def test_report_marks_budget_overflow_as_rejected(lifecycle_report):
    budget = lifecycle_report["budget_exhaustion"]

    assert budget["remaining_at_exact_cap"] == 0
    assert budget["overflow_rejected"] is True
    assert budget["overflow_outcome"] == "REJECTED"
    assert budget["new_lease_budget_rejected"] is True


def test_bounded_synthetic_candidate_report_has_no_worker_remote(lifecycle_report):
    candidate = lifecycle_report["synthetic_candidate"]

    assert re.fullmatch(r"[0-9a-f]{40}", candidate["candidate_head"])
    assert candidate["worker_has_remote_config"] is False
    assert "synthetic_gate_verdict" in candidate
    assert "gate_verdict" not in candidate
    assert candidate["receipt_retry_returned_same_result"] is True


def test_caller_probe_values_are_not_upgraded_to_environment_egress_evidence(lifecycle_report):
    observations = lifecycle_report["caller_supplied_probe_observations"]

    assert len(observations["runs"]) == 1
    assert all(
        run["scope"] == "caller_supplied_probe_data_not_independent_environment_evidence"
        for run in observations["runs"]
    )
    assert all(run["reported_external_egress_blocked"] is True for run in observations["runs"])
    assert observations["real_environment_egress_verified"] is False


def test_store_is_closed_when_supervisor_setup_fails(monkeypatch):
    captured_fixtures = []
    fixture_type = slice_module.SliceFixture

    def capture_fixture(*args, **kwargs):
        fixture = fixture_type(*args, **kwargs)
        captured_fixtures.append(fixture)
        return fixture

    monkeypatch.setattr(slice_module, "SliceFixture", capture_fixture)
    expected_error = RuntimeError("synthetic supervisor setup failure")

    def fail_supervisor(*args, **kwargs):
        raise expected_error

    monkeypatch.setattr(slice_module, "Supervisor", fail_supervisor)

    with tempfile.TemporaryDirectory(prefix="s2-e8-setup-failure-") as temp_root:
        workdir = os.path.join(temp_root, "work")
        with pytest.raises(RuntimeError) as raised:
            slice_module.run_lifecycle_scenarios(
                workdir,
                probe_provider=_synthetic_probe,
            )

    assert raised.value is expected_error
    assert len(captured_fixtures) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        captured_fixtures[0].store._conn.execute("SELECT 1")

