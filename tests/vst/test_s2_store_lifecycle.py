"""S2 external anchor, restart reconciliation, and lease ordering journeys."""
from __future__ import annotations

import shutil
import os

import pytest

from tools.vst.lifecycle import AnchorError, FileExternalAnchor
from tools.vst.supervisor import Supervisor
from tools.vst.store import Store, StoreError
from tests.vst.e1e4_helpers import (
    EVENT_KEY, HEAD, HEAD2, KEY, STORY, SUPERVISOR_KEY, TASK, new_env, receipt,
)

EVENT = b"s2-store-event-key-0123456789-abcdef"
SUPERVISOR = b"s2-store-supervisor-key-0123456789-abcdef"


@pytest.mark.skipif(os.name != "posix", reason="NOT_RUN: FileExternalAnchor permissions/locking acceptance requires POSIX sandbox")
def test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork(tmp_path):
    anchor = FileExternalAnchor(str(tmp_path / "outside" / "anchor.jsonl"), EVENT)
    from tools.vst.lifecycle import signed_checkpoint
    genesis = signed_checkpoint(0, "0" * 64, EVENT)
    assert anchor.compare_and_append(None, genesis) == genesis
    signed = signed_checkpoint(1, "a" * 64, EVENT)
    assert anchor.compare_and_append(genesis, signed) == signed
    assert anchor.compare_and_append(None, signed) == signed
    assert anchor.compare_and_append(None, signed) == signed
    fork = signed_checkpoint(1, "b" * 64, EVENT)
    with pytest.raises(AnchorError, match="different head|conflict"):
        anchor.compare_and_append(signed, fork)


@pytest.mark.skipif(os.name != "posix", reason="NOT_RUN: external anchor restore detection requires POSIX sandbox")
def test_external_anchor_detects_restored_older_database_and_locks_writes(tmp_path):
    db, anchor_path = tmp_path / "state.db", tmp_path / "anchor.jsonl"
    with Store(str(db), event_key=EVENT, anchor_path=str(anchor_path)) as store:
        store.record_event("task", "actor", "NOTE", {"phase": "old"})
        old_copy = tmp_path / "old.db"
        store._conn.execute("PRAGMA wal_checkpoint(FULL)")
        shutil.copy2(db, old_copy)
        store.record_event("task", "actor", "NOTE", {"phase": "new"})
    with Store(str(old_copy), event_key=EVENT, anchor_path=str(anchor_path)) as restored:
        assert not restored.reconciliation_complete
        with pytest.raises(StoreError, match="integrity|anchor"):
            restored.record_event("task", "actor", "NOTE", {})


def test_sandbox_mode_requires_anchor_and_supervisor_reconciliation_key(tmp_path):
    with pytest.raises(StoreError, match="external anchor"):
        Store(str(tmp_path / "missing-anchor.db"), event_key=EVENT, sandbox_mode=True, supervisor_key=SUPERVISOR)
    with pytest.raises(StoreError, match="supervisor key"):
        Store(str(tmp_path / "missing-key.db"), event_key=EVENT, sandbox_mode=True, anchor_path=str(tmp_path / "anchor"))


@pytest.mark.skipif(os.name != "posix", reason="NOT_RUN: interrupted anchor recovery requires POSIX sandbox")
def test_exactly_one_event_ahead_is_recovered_before_mutation(tmp_path):
    db, anchor = tmp_path / "recovery.db", tmp_path / "anchor.jsonl"
    with Store(str(db), event_key=EVENT, anchor_path=str(anchor)) as store:
        store.record_event("task", "actor", "NOTE", {"before": True})
        # Model a crash after database commit by removing only the latest external line.
        lines = anchor.read_bytes().splitlines(keepends=True)
        anchor.write_bytes(b"".join(lines[:-1]))
    with Store(str(db), event_key=EVENT, anchor_path=str(anchor)) as recovered:
        assert recovered.reconciliation_complete
        assert recovered.event_anchor()[0] == 1


@pytest.mark.parametrize("anchor_state", [
    "database_more_than_one_event_ahead",
    "anchor_missing_for_nonempty_database",
    "anchor_tampered_or_malformed",
    "interruption_during_anchor_append",
    "restart_during_interrupted_recovery",
])
@pytest.mark.skip(reason="NOT_RUN: POSIX external-anchor failure state requires the provisioned sandbox and safe interruption injection; no synthetic anchor result is accepted")
def test_unavailable_posix_anchor_failure_states_not_run(anchor_state):
    pytest.skip(anchor_state)


def test_store_and_supervisor_refuse_lease_start_or_decision_before_reconciliation(tmp_path):
    store, _, epoch = new_env(str(tmp_path / "reconcile.db"))
    try:
        supervisor = Supervisor(store, operation_backend=object())
        store._reconciliation_complete = False
        store._integrity_locked = True
        started = []
        with pytest.raises(StoreError, match="reconciliation"):
            supervisor.start_worker(lambda: started.append(True))
        with pytest.raises(StoreError, match="reconciliation"):
            supervisor.evaluate_gate(TASK, HEAD, epoch, KEY)
        with pytest.raises(StoreError, match="reconciliation"):
            supervisor.create_receipt("receipt-key", {}, STORY, KEY)
        assert not started
        # A lease is itself a worker-start authorization and must obey the same barrier.
        with pytest.raises(StoreError, match="reconciliation"):
            store.acquire_lease(
                TASK, STORY, "runner-1", epoch, 1, 30,
                supervisor_key=SUPERVISOR_KEY,
            )
    finally:
        store.close()


def test_supervisor_consumes_a_synthetic_probe_once_for_one_run(tmp_path):
    """Protocol fixture only; these booleans do not claim a real sandbox result."""
    import hashlib
    from tools.vst.preflight import PROBE_LABEL, SPEC_PATH
    from tools.vst.signing import sign

    probe_key = b"s2-probe-once-key-0123456789-abcdef"
    spec_sha = hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
    checks = {
        "automount_disabled": True, "interop_disabled": True, "no_container_socket": True,
        "non_root": True, "external_egress_blocked": True, "loopback_canary": True,
        "empty_external_allowlist": True,
    }
    body = {
        "run_id": "unit-run-1", "spec_sha256": spec_sha, "nonce": "unit-nonce-1",
        "checked_properties": checks, "result": "PASS", "inventory": {"fixture": True},
    }
    probe = {**body, "signature": sign(body, probe_key, PROBE_LABEL)}
    with Store(str(tmp_path / "probe-once.db"), event_key=EVENT_KEY) as store:
        store.sandbox_mode = True  # exercise run-bound supervisor logic, not host isolation
        supervisor = Supervisor(
            store, operation_backend=object(), run_id="unit-run-1",
            probe_nonce="unit-nonce-1", probe_key=probe_key,
        )
        starts = []
        assert supervisor.start_worker(lambda: starts.append("first"), probe=probe) is None
        assert starts == ["first"]
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_probes WHERE run_id = ?", ("unit-run-1",)
        ).fetchone()[0] == 1
        with pytest.raises(StoreError, match="already authorized"):
            supervisor.start_worker(lambda: starts.append("duplicate"), probe=probe)
        assert starts == ["first"]
        restarted = Supervisor(
            store, operation_backend=object(), run_id="unit-run-1",
            probe_nonce="unit-nonce-1", probe_key=probe_key,
        )
        with pytest.raises(StoreError, match="already consumed"):
            restarted.start_worker(lambda: starts.append("restart-reuse"), probe=probe)
        assert starts == ["first"]


def test_supervisor_receipt_replay_is_idempotent_and_payload_conflict_fails(tmp_path):
    store, _, epoch = new_env(str(tmp_path / "receipt-idempotency.db"))
    try:
        store.acquire_lease(
            TASK, STORY, "runner-1", epoch, 1, 30,
            supervisor_key=SUPERVISOR_KEY,
        )
        supervisor = Supervisor(store, operation_backend=object())
        candidate = receipt("TestRun", key=KEY, epoch=epoch, candidate_head=HEAD)
        first = supervisor.create_receipt("receipt-once", candidate, STORY, KEY)
        replay = supervisor.create_receipt("receipt-once", candidate, STORY, KEY)
        assert first == replay
        assert store._conn.execute(
            "SELECT COUNT(*) FROM receipts WHERE task_id = ?", (TASK,)
        ).fetchone()[0] == 1
        changed = {**candidate, "candidate_head": HEAD2}
        with pytest.raises(StoreError, match="different operation or payload"):
            supervisor.create_receipt("receipt-once", changed, STORY, KEY)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM receipts WHERE task_id = ?", (TASK,)
        ).fetchone()[0] == 1
    finally:
        store.close()

