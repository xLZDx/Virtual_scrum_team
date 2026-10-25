"""Focused falsifying tests for previously unmapped S4 Python entrypoints."""
from __future__ import annotations

import pytest

from tools.vst.contracts import ContractError, validate_task_manifest_v2
from tools.vst.store import StoreError
from tools.vst.supervisor import Supervisor
from tests.vst.e1e4_helpers import (
    KEY, OPERATOR_KEY, STORY, SUPERVISOR_KEY, TASK,
    new_env, receipt,
)


def test_api_validate_task_manifest_v2_rejects_missing_contract_fields():
    with pytest.raises(ContractError, match=r"task_manifest_v2: missing field\(s\):"):
        validate_task_manifest_v2({"contract_version": 2})


def test_api_acquire_epoch_idempotent_replay_keeps_one_new_epoch(tmp_path):
    store, _, epoch = new_env(str(tmp_path / "epoch.db"))
    try:
        acquired = store.acquire_epoch_idempotent(
            "epoch-op-1", STORY, epoch, "owner-b", 30,
        )
        replayed = store.acquire_epoch_idempotent(
            "epoch-op-1", STORY, epoch, "owner-b", 30,
        )
        assert acquired == replayed == epoch + 1
        assert store.current_epoch(STORY) == epoch + 1
    finally:
        store.close()


def test_api_resume_epoch_idempotent_rejects_unrecorded_outcome_without_mutation(tmp_path):
    store, _, epoch = new_env(str(tmp_path / "resume-epoch.db"))
    try:
        with pytest.raises(StoreError, match="recorded application checkpoint"):
            store.resume_epoch_idempotent(
                "resume-op-1", TASK, STORY, 1, epoch, "missing-outcome", None,
                "owner-a", "owner-b", 30,
            )
        assert store.current_epoch(STORY) == epoch
    finally:
        store.close()


def test_api_charge_idempotent_replay_updates_budget_once(tmp_path):
    store, _, _ = new_env(str(tmp_path / "charge-idempotent.db"))
    try:
        remaining = store.charge_idempotent(
            "charge-op-1", TASK, 3, supervisor_key=SUPERVISOR_KEY,
            expected_cap=100, expected_spent=0,
        )
        replay = store.charge_idempotent(
            "charge-op-1", TASK, 3, supervisor_key=SUPERVISOR_KEY,
            expected_cap=100, expected_spent=0,
        )
        assert remaining == replay == 97
        after_replay = store.charge_idempotent(
            "charge-op-2", TASK, 0, supervisor_key=SUPERVISOR_KEY,
            expected_cap=100, expected_spent=3,
        )
        assert after_replay == 97
    finally:
        store.close()


def test_api_append_manual_override_rejects_unsigned_record_without_control_write(tmp_path):
    store, _, _ = new_env(str(tmp_path / "override.db"))
    supervisor = Supervisor(store, operation_backend=object(), failure_threshold=1,
                            operator_key=OPERATOR_KEY)
    supervisor.provider_failed("provider-failure-1")
    before = store.control_events()
    try:
        with pytest.raises(StoreError, match="operator signature is invalid"):
            store.append_manual_override({"id": "unsigned-override"}, operator_key=OPERATOR_KEY)
        assert store.control_events() == before
    finally:
        store.close()


def test_api_begin_action_rejects_mismatched_transaction_id_without_write(tmp_path):
    store, _, _ = new_env(str(tmp_path / "begin-action.db"))
    before = store.control_events()
    try:
        with pytest.raises(StoreError, match="action_id must match"):
            store.begin_action("intent-1", {"action": "start", "action_id": "other"})
        assert store.control_events() == before
    finally:
        store.close()


def test_api_startup_reconcile_verifies_current_store_history(tmp_path):
    store, _, _ = new_env(str(tmp_path / "reconcile.db"))
    try:
        store.record_event("local-task", "test", "NOTE", {"state": "before-reconcile"})
        store.startup_reconcile()
        assert store.reconciliation_complete is True
        assert store.verify_event_chain() is True
    finally:
        store.close()


def test_api_lookup_idempotent_operation_returns_bound_completed_result(tmp_path):
    store, _, _ = new_env(str(tmp_path / "lookup-operation.db"))
    payload = {"target": "local"}
    try:
        assert store.execute_idempotent(
            "lookup-op-1", "local-test", payload, lambda _conn: {"value": 7}
        ) == {"value": 7}
        result = store.lookup_idempotent_operation(
            "lookup-op-1", operation="local-test", payload=payload, check_payload=True,
        )
        assert result == {
            "operation": "local-test",
            "payload_sha256": result["payload_sha256"],
            "state": "COMPLETED",
            "result": {"value": 7},
        }
        with pytest.raises(StoreError, match="different payload"):
            store.lookup_idempotent_operation(
                "lookup-op-1", operation="local-test", payload={"target": "changed"},
                check_payload=True,
            )
    finally:
        store.close()


def test_api_stop_attempt_fenced_advances_epoch_and_fences_live_lease(tmp_path):
    store, _, epoch = new_env(str(tmp_path / "stop-fenced.db"))
    store.acquire_lease(TASK, STORY, "runner-1", epoch, 1, 30,
                        supervisor_key=SUPERVISOR_KEY)
    try:
        result = store.stop_attempt_fenced(
            "stop-op-1", TASK, STORY, 1, epoch, "owner-a", "operator requested stop", "operator",
        )
        assert result["state"] == "INCONCLUSIVE"
        assert result["new_epoch"] == epoch + 1
        assert result["lease_fenced"] is True
        assert store.current_epoch(STORY) == epoch + 1
        with pytest.raises(StoreError, match="lease|epoch|owner"):
            store.append_receipt(receipt("TestRun", key=KEY, epoch=epoch), STORY, KEY)
        assert store.receipts_for_task(TASK) == []
    finally:
        store.close()


def test_api_append_receipt_idempotent_replays_one_receipt(tmp_path):
    store, _, epoch = new_env(str(tmp_path / "receipt-idempotent.db"))
    store.acquire_lease(TASK, STORY, "runner-1", epoch, 1, 30,
                        supervisor_key=SUPERVISOR_KEY)
    candidate = receipt("TestRun", key=KEY, epoch=epoch)
    try:
        first = store.append_receipt_idempotent("receipt-op-1", candidate, STORY, KEY)
        replay = store.append_receipt_idempotent("receipt-op-1", candidate, STORY, KEY)
        assert first == replay
        assert len(store.receipts_for_task(TASK)) == 1
        changed = {**candidate, "candidate_head": "f" * 40}
        with pytest.raises(StoreError, match="different operation or payload"):
            store.append_receipt_idempotent("receipt-op-1", changed, STORY, KEY)
        assert len(store.receipts_for_task(TASK)) == 1
    finally:
        store.close()


def test_api_consume_preflight_is_one_time_and_records_probe(tmp_path):
    store, _, _ = new_env(str(tmp_path / "preflight.db"))
    args = ("run-1", "nonce-1", "a" * 64, "b" * 64)
    try:
        store.consume_preflight(*args)
        event_anchor = store.event_anchor()
        assert store.verify_event_chain() is True
        with pytest.raises(StoreError, match="already consumed"):
            store.consume_preflight(*args)
        assert store.event_anchor() == event_anchor
    finally:
        store.close()


def test_api_prepare_run_binds_fresh_run_and_probe_nonce(tmp_path):
    store, _, _ = new_env(str(tmp_path / "prepare-run.db"))
    store.sandbox_mode = True
    supervisor = Supervisor(
        store, operation_backend=object(), run_id="prior-run", probe_nonce="prior-nonce",
        probe_key=b"s4-test-probe-key-0123456789-abcdef",
        operator_key=OPERATOR_KEY,
    )
    try:
        supervisor.prepare_run("next-run", "next-nonce")
        assert supervisor.run_id == "next-run"
        assert supervisor.probe_nonce == "next-nonce"
        with pytest.raises(StoreError, match="fresh and non-empty"):
            supervisor.prepare_run("next-run", "different-nonce")
    finally:
        store.close()


def test_api_supervisor_resume_runs_only_from_stopped_lifecycle(tmp_path):
    store, _, _ = new_env(str(tmp_path / "supervisor-resume.db"))
    supervisor = Supervisor(store, operation_backend=object())
    try:
        assert supervisor.start_worker(lambda: "started") == "started"
        supervisor.stop(lambda: None, lambda: None, action_id="stop-before-resume")
        assert supervisor.lifecycle_state == "STOPPED"
        assert supervisor.resume(lambda: "next-epoch", action_id="resume-after-stop") == "next-epoch"
        assert supervisor.lifecycle_state == "READY"
    finally:
        store.close()
