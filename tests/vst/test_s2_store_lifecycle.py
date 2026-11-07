"""S2 external anchor, restart reconciliation, and lease ordering journeys."""
from __future__ import annotations

import shutil
import os
import threading
import json
import sqlite3
import time

import pytest

from tools.vst import lifecycle as lifecycle_module, store as store_module
from tools.vst.lifecycle import AnchorError, FileExternalAnchor, signed_checkpoint
from tools.vst.supervisor import Supervisor
from tools.vst.store import GENESIS_HASH, Store, StoreError
from tests.vst.e1e4_helpers import (
    EVENT_KEY, HEAD, HEAD2, KEY, OPERATOR_KEY, STORY, SUPERVISOR_KEY, TASK, new_env, receipt,
    manifest as base_manifest,
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
    with pytest.raises(AnchorError, match="different head|conflict|immediate successor"):
        anchor.compare_and_append(signed, fork)


@pytest.mark.skipif(os.name != "posix", reason="NOT_RUN: FileExternalAnchor requires POSIX sandbox")
def test_anchor_append_separates_valid_tail_without_final_newline(tmp_path):
    """VST-012: recover a valid final checkpoint without its terminating LF."""
    anchor_path = tmp_path / "anchor-without-final-lf.jsonl"
    anchor = FileExternalAnchor(str(anchor_path), EVENT)
    genesis = signed_checkpoint(0, GENESIS_HASH, EVENT)
    anchor_path.write_bytes(json.dumps(genesis, separators=(",", ":")).encode("utf-8"))

    assert anchor.read_latest() == genesis
    successor = signed_checkpoint(1, "a" * 64, EVENT)
    assert anchor.compare_and_append(genesis, successor) == successor

    lines = anchor_path.read_bytes().splitlines()
    assert [json.loads(line) for line in lines] == [genesis, successor]
    assert anchor.read_latest() == successor


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


@pytest.mark.parametrize("failure_stage", ["setup", "acquire"])
def test_coordinator_oserror_is_normalized_and_store_connection_is_closed(tmp_path, monkeypatch, failure_stage):
    """Inject coordinator failures without changing host paths or permissions."""
    real_connect = store_module.sqlite3.connect
    connections = []

    def track_connection(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(store_module.sqlite3, "connect", track_connection)

    def fail(*args, **kwargs):
        raise OSError("injected coordinator failure")

    if failure_stage == "setup":
        monkeypatch.setattr(lifecycle_module.os, "makedirs", fail)
    elif os.name == "nt":
        import msvcrt
        monkeypatch.setattr(msvcrt, "locking", fail)
    else:
        import fcntl
        monkeypatch.setattr(fcntl, "flock", fail)

    with pytest.raises(StoreError, match="coordinator setup failed: injected coordinator failure"):
        Store(
            str(tmp_path / f"coordinator-{failure_stage}.db"),
            event_key=EVENT,
            anchor_path=str(tmp_path / f"coordinator-{failure_stage}.anchor"),
        )

    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connections[0].execute("SELECT 1")


def test_coordinator_unlock_oserror_is_typed_and_releases_path_mutex(tmp_path, monkeypatch):
    anchor = FileExternalAnchor(str(tmp_path / "unlock-failure" / "anchor.jsonl"), EVENT)
    failed_once = False

    def fail_first_unlock(real_lock, unlock_mode):
        def injected(fd, mode, *extra):
            nonlocal failed_once
            if mode == unlock_mode and not failed_once:
                failed_once = True
                raise OSError("injected coordinator unlock failure")
            return real_lock(fd, mode, *extra)
        return injected

    if os.name == "nt":
        import msvcrt
        monkeypatch.setattr(
            msvcrt, "locking",
            fail_first_unlock(msvcrt.locking, msvcrt.LK_UNLCK),
        )
    else:
        import fcntl
        monkeypatch.setattr(
            fcntl, "flock",
            fail_first_unlock(fcntl.flock, fcntl.LOCK_UN),
        )

    with pytest.raises(AnchorError, match="coordinator unlock failed: injected coordinator unlock failure"):
        with anchor.transaction_lock():
            pass

    entered = threading.Event()
    failures = []

    def acquire_after_failure():
        try:
            with anchor.transaction_lock():
                entered.set()
        except BaseException as exc:
            failures.append(exc)

    retry = threading.Thread(target=acquire_after_failure, daemon=True)
    retry.start()
    assert entered.wait(timeout=5), "coordinator path mutex remained held after unlock failure"
    retry.join(timeout=5)
    assert not retry.is_alive()
    assert failures == []


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


@pytest.mark.skipif(os.name != "posix", reason="NOT_RUN: interrupted external-anchor suffix recovery requires the provisioned POSIX sandbox")
def test_multi_event_transaction_recovers_suffix_after_one_checkpoint_append(tmp_path, monkeypatch):
    db, anchor_path = tmp_path / "multi-event-recovery.db", tmp_path / "multi-event-anchor.jsonl"
    store = Store(str(db), event_key=EVENT, anchor_path=str(anchor_path))
    original_append = store._external_anchor.compare_and_append
    appended = 0

    def interrupt_after_first_append(expected, checkpoint):
        nonlocal appended
        result = original_append(expected, checkpoint)
        appended += 1
        if appended == 1:
            raise AnchorError("injected interruption after first checkpoint append")
        return result

    monkeypatch.setattr(store._external_anchor, "compare_and_append", interrupt_after_first_append)
    try:
        with pytest.raises(StoreError, match="injected interruption"):
            with store._tx() as conn:
                store._record_event_locked(conn, "task", "actor", "NOTE", {"n": 1})
                store._record_event_locked(conn, "task", "actor", "NOTE", {"n": 2})
        assert appended == 1
    finally:
        store.close()

    with Store(str(db), event_key=EVENT, anchor_path=str(anchor_path)) as recovered:
        assert recovered.reconciliation_complete
        assert recovered.verify_event_chain()
        count, head = recovered.event_anchor()
        assert count == 2
        assert recovered._external_anchor.read_latest() == signed_checkpoint(count, head, EVENT)


def test_two_store_instances_serialize_concurrent_write_and_anchor_sync(tmp_path):
    db, anchor_path = tmp_path / "concurrent-writes.db", tmp_path / "concurrent-anchor.jsonl"
    with Store(str(db), event_key=EVENT, anchor_path=str(anchor_path)):
        pass

    barrier = threading.Barrier(2)
    results = []
    failures = []

    def write_from_instance(index):
        store = None
        try:
            store = Store(str(db), event_key=EVENT, anchor_path=str(anchor_path))
            barrier.wait(timeout=10)
            store.record_event("task", f"actor-{index}", "NOTE", {"writer": index})
            barrier.wait(timeout=10)
            results.append((store.event_anchor(), store.reconciliation_complete, store._integrity_locked))
        except BaseException as exc:
            failures.append(exc)
        finally:
            if store is not None:
                store.close()

    threads = [threading.Thread(target=write_from_instance, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert all(not thread.is_alive() for thread in threads)
    assert not failures
    assert len(results) == 2
    assert all(complete and not locked for _, complete, locked in results)
    assert results[0][0] == results[1][0]
    assert results[0][0][0] == 2
    anchor = FileExternalAnchor(str(anchor_path), EVENT)
    final_count, final_head = results[0][0]
    assert anchor.read_latest() == signed_checkpoint(final_count, final_head, EVENT)


def test_gate_and_anchor_readers_racing_writer_do_not_permanently_lock_store(tmp_path):
    db, anchor_path = tmp_path / "reader-writer-race.db", tmp_path / "reader-writer-anchor.jsonl"
    with Store(str(db), event_key=EVENT, anchor_path=str(anchor_path)) as initial:
        initial.init_slots(2)
        initial.open_story(STORY, "proj", 4)
        epoch = initial.acquire_epoch(STORY, "owner-a", 600)
        initial.register_task(base_manifest())

    barrier = threading.Barrier(2)
    failures = []
    statuses = []

    def read_repeatedly():
        store = None
        try:
            store = Store(str(db), event_key=EVENT, anchor_path=str(anchor_path))
            for index in range(8):
                barrier.wait(timeout=10)
                if index % 2:
                    store.event_anchor()
                else:
                    store.evaluate_gate(
                        TASK, HEAD, epoch, KEY,
                        supervisor_key=SUPERVISOR_KEY,
                        operator_key=OPERATOR_KEY,
                        event_key=EVENT_KEY,
                    )
                statuses.append((store.reconciliation_complete, store._integrity_locked))
                barrier.wait(timeout=10)
            store.verify_event_chain()
        except BaseException as exc:
            failures.append(exc)
        finally:
            if store is not None:
                store.close()

    def write_repeatedly():
        store = None
        try:
            store = Store(str(db), event_key=EVENT, anchor_path=str(anchor_path))
            for index in range(8):
                barrier.wait(timeout=10)
                store.record_event("task", "writer", "NOTE", {"index": index})
                barrier.wait(timeout=10)
            statuses.append((store.reconciliation_complete, store._integrity_locked))
        except BaseException as exc:
            failures.append(exc)
        finally:
            if store is not None:
                store.close()

    threads = [threading.Thread(target=read_repeatedly), threading.Thread(target=write_repeatedly)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert all(not thread.is_alive() for thread in threads)
    assert not failures
    assert len(statuses) == 9
    assert all(complete and not locked for complete, locked in statuses)
    with Store(str(db), event_key=EVENT, anchor_path=str(anchor_path)) as verified:
        assert verified.reconciliation_complete
        assert verified.verify_event_chain()
        count, head = verified.event_anchor()
        assert count >= 8
        assert verified._external_anchor.read_latest() == signed_checkpoint(count, head, EVENT)


@pytest.mark.skipif(os.name != "posix", reason="NOT_RUN: POSIX external-anchor failure states require the provisioned POSIX sandbox")
@pytest.mark.parametrize("anchor_state", [
    "external_anchor_ahead_of_database",
    "external_anchor_missing_for_nonempty_database",
    "forked_checkpoint_suffix",
    "malformed_checkpoint_suffix",
    "tampered_checkpoint_suffix",
])
def test_invalid_external_anchor_suffix_fails_closed(tmp_path, anchor_state):
    db, anchor_path = tmp_path / f"{anchor_state}.db", tmp_path / f"{anchor_state}.jsonl"
    with Store(str(db), event_key=EVENT, anchor_path=str(anchor_path)) as initial:
        initial.record_event("task", "actor", "NOTE", {"valid": 1})
        initial.record_event("task", "actor", "NOTE", {"valid": 2})
        expected_latest = initial._external_anchor.read_latest()

    anchor = FileExternalAnchor(str(anchor_path), EVENT)
    if anchor_state == "external_anchor_ahead_of_database":
        anchor.compare_and_append(
            expected_latest, signed_checkpoint(3, "f" * 64, EVENT)
        )
    elif anchor_state == "external_anchor_missing_for_nonempty_database":
        os.unlink(anchor_path)
    elif anchor_state == "forked_checkpoint_suffix":
        anchor_path.write_bytes(
            (json.dumps(signed_checkpoint(0, GENESIS_HASH, EVENT)) + "\n"
             + json.dumps(signed_checkpoint(1, "e" * 64, EVENT)) + "\n").encode()
        )
    elif anchor_state == "malformed_checkpoint_suffix":
        with open(anchor_path, "ab") as stream:
            stream.write(b"{malformed checkpoint}\n")
    else:
        with open(anchor_path, "ab") as stream:
            stream.write(b'{"count":3,"head":"' + b"f" * 64 + b'","signature":"bad"}\n')

    with Store(str(db), event_key=EVENT, anchor_path=str(anchor_path)) as rejected:
        assert not rejected.reconciliation_complete
        assert rejected._integrity_locked
        with pytest.raises(StoreError, match="integrity-locked|anchor|checkpoint|database"):
            rejected.record_event("task", "actor", "NOTE", {"must_fail": True})


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


def test_record_event_rejects_caller_forged_reserved_control_note(tmp_path):
    store = Store(str(tmp_path / "forged-control-note.db"), event_key=EVENT)
    try:
        before = store._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        with pytest.raises(StoreError, match="reserved supervisor control payload"):
            store.record_event(
                "__control__", "supervisor", "NOTE",
                {"_vst_control_type": "CONTROL_BREAKER_OVERRIDE", "event_id": "forged-1"},
            )
        after = store._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert after == before
        assert store.control_events() == []
    finally:
        store.close()


def test_preflight_consumption_survives_restart_for_the_exact_observation(tmp_path):
    store_path = str(tmp_path / "runtime-store.db")
    run_id, nonce = "unit-run-1", "unit-nonce-1"
    spec_sha, observation_sha = "a" * 64, "b" * 64

    with Store(store_path, event_key=EVENT_KEY) as store:
        assert store.ensure_preflight_consumed(run_id, nonce, spec_sha, observation_sha) is True
        assert store._conn.execute(
            "SELECT run_id, nonce, spec_sha256, probe_sha256 FROM supervisor_probes"
        ).fetchall()[0][:] == (run_id, nonce, spec_sha, observation_sha)

    with Store(store_path, event_key=EVENT_KEY) as restarted:
        restarted.require_existing_preflight_consumed(run_id, nonce, spec_sha, observation_sha)
        assert restarted._conn.execute("SELECT COUNT(*) FROM supervisor_probes").fetchone()[0] == 1
        assert restarted._conn.execute(
            "SELECT COUNT(*) FROM events WHERE task_id = ? AND kind = 'NOTE'", (run_id,)
        ).fetchone()[0] == 1


@pytest.mark.parametrize("changed", ["run", "nonce", "spec", "source_config_hash"])
def test_preflight_restart_refuses_absent_or_mismatched_consumed_tuple(tmp_path, changed):
    store_path = str(tmp_path / f"runtime-store-{changed}.db")
    expected = ["unit-run-1", "unit-nonce-1", "a" * 64, "b" * 64]
    with Store(store_path, event_key=EVENT_KEY) as store:
        assert store.ensure_preflight_consumed(*expected) is True

    actual = list(expected)
    indexes = {"run": 0, "nonce": 1, "spec": 2, "source_config_hash": 3}
    actual[indexes[changed]] = (
        "different-run" if changed == "run" else
        "different-nonce" if changed == "nonce" else
        "c" * 64
    )
    with Store(store_path, event_key=EVENT_KEY) as restarted:
        with pytest.raises(StoreError, match="exact existing consumed observation tuple"):
            restarted.require_existing_preflight_consumed(*actual)


def test_existing_store_without_consumed_observation_cannot_enter_recovery(tmp_path):
    store_path = str(tmp_path / "unconsumed-existing-store.db")
    with Store(store_path, event_key=EVENT_KEY) as store:
        store.record_event("unrelated-task", "fixture", "NOTE", {"history": "exists"})

    with Store(store_path, event_key=EVENT_KEY) as restarted:
        with pytest.raises(StoreError, match="exact existing consumed observation tuple"):
            restarted.require_existing_preflight_consumed(
                "unit-run-1", "unit-nonce-1", "a" * 64, "b" * 64,
            )


def test_supervisor_worker_start_is_one_shot_after_verified_store_consumption(tmp_path):
    operator_key = b"s2-operator-once-key-0123456789-abcdef"
    with Store(str(tmp_path / "worker-start-once.db"), event_key=EVENT_KEY) as store:
        store.sandbox_mode = True
        store.ensure_preflight_consumed("unit-run-1", "unit-nonce-1", "a" * 64, "b" * 64)
        supervisor = Supervisor(
            store, operation_backend=object(), run_id="unit-run-1",
            probe_nonce="unit-nonce-1", operator_key=operator_key,
        )
        # Production sets this only after the observation has been persisted and verified.
        supervisor._probe_consumed = True
        starts = []
        supervisor.start_worker(lambda: starts.append("first"))
        with pytest.raises(StoreError, match="already consumed its one worker start"):
            supervisor.start_worker(lambda: starts.append("duplicate"))
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

