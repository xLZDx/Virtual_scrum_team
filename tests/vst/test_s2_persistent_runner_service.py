"""Focused safe contracts for the S2 persistent runner boundary."""
from __future__ import annotations

import base64
import copy
import hashlib
import stat

import pytest

from tools.vst import contracts
from tools.vst import store as store_module
from tools.vst.runner_service import (
    _verify_worker_exec_helper,
    _versioned_worker_exec_helper_path,
    dispatch_authorized_manifest_run,
    load_runner_service_config,
)
from tools.vst.signing import SIGNING_REQUEST_LABEL, sign
from tools.vst.signer import (
    AuthenticatedSigner,
    MAX_REQUEST_BYTES,
    MAX_SIGNER_RESPONSE_BYTES,
    _recv_signer_response,
)
from tools.vst.store import RUNNER_EXECUTION_RESOLUTION_LABEL, Store, StoreError
from tools.vst.supervisor_service import AuthenticatedSupervisorAPI
from tests.vst.e1e4_helpers import EVENT_KEY, FakeClock, SUPERVISOR_KEY
from tests.vst.test_s2_runner_lifecycle import (
    SIGNER_KEY, _authority_fixture, _authority_receipt,
)


def _grant(manifest: dict, *, deadline: int = 600, now: float = 1000.0) -> dict:
    return {
        "version": 1,
        "key_id": "grant-key-1",
        "grant_id": "grant-1",
        "request_id": "request-1",
        "audience": "vst-runner-service-v1",
        "service_generation": "generation-1",
        "manifest_sha256": contracts.manifest_sha256(manifest),
        "task_id": manifest["task_id"],
        "slot": "tests",
        "attempt": 1,
        "epoch": 2,
        "run_id": "run-1",
        "invocation_id": "invocation-1",
        "runner_id": "runner-1",
        "resolved_model": "test-model",
        "model_provenance_sha256": "e" * 64,
        "execution_deadline_sec": deadline,
        "issued_at": now,
        "claim_expires_at": now + 30,
        "expires_at": now + 30 + deadline + 30,
        "signature": base64.urlsafe_b64encode(bytes(64)).decode("ascii").rstrip("="),
    }


EXECUTION_RESOLUTION_KEY = b"execution-resolution-test-key-0123456789"

# Exact event-kind set from tools/vst/store.py at 7120e2c^ (schema v5, before
# DISPATCH_INTENT_ACCEPTED was added by the v5-to-v6 migration). Keep this
# historical fixture explicit so a current schema cannot masquerade as v5.
PRE_0473_SCHEMA_V5_EVENT_KINDS = frozenset({
    "EPOCH_ACQUIRED", "EPOCH_RENEWED", "EPOCH_RELEASED", "PHASE_SET",
    "TASK_REGISTERED", "LEASE_ACQUIRED", "LEASE_RELEASED", "LEASE_EXPIRED",
    "LEASE_EXPIRED_PARTIAL", "LEASE_FENCED", "RECEIPT_APPENDED",
    "BUDGET_EXCEEDED", "BUDGET_BLOCKED", "NOTE",
})


def _store_with_claim_basis(
    manifest: dict, clock: FakeClock, *, execution_resolution_key: bytes | None = None,
    slots: int = 1, story_ttl_sec: int = 1800, lease_ttl_sec: int = 1200,
    db_path: str = ":memory:",
):
    store = Store(
        db_path, clock, event_key=EVENT_KEY,
        execution_resolution_key=execution_resolution_key,
    )
    store.init_slots(slots)
    store.open_story(manifest["story_id"], manifest["project_id"], manifest["phase"])
    epoch = store.acquire_epoch(
        manifest["story_id"], "test-owner", ttl_sec=story_ttl_sec,
    )
    assert epoch == 2
    store.register_task(manifest)
    store.acquire_lease(
        manifest["task_id"], manifest["story_id"], "runner-1", epoch, 1, lease_ttl_sec,
        supervisor_key=SUPERVISOR_KEY,
    )
    store.ensure_preflight_consumed("run-1", "nonce-1", "a" * 64, "b" * 64)
    return store


def _store_with_pre_0473_schema_v5_claim_basis(
    manifest: dict, clock: FakeClock, *, db_path: str,
):
    """Create the historical v5 DDL before seeding the legacy recovery event."""
    assert store_module.SCHEMA_VERSION == 6
    assert store_module.EVENT_KINDS == PRE_0473_SCHEMA_V5_EVENT_KINDS | {
        "DISPATCH_INTENT_ACCEPTED",
    }
    version, event_kinds = store_module.SCHEMA_VERSION, store_module.EVENT_KINDS
    store_module.SCHEMA_VERSION = 5
    store_module.EVENT_KINDS = PRE_0473_SCHEMA_V5_EVENT_KINDS
    try:
        store = _store_with_claim_basis(
            manifest, clock, story_ttl_sec=3600, lease_ttl_sec=3600,
            db_path=db_path,
        )
    finally:
        store_module.SCHEMA_VERSION = version
        store_module.EVENT_KINDS = event_kinds
    with store._read_tx() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        events_ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchone()[0]
    assert "DISPATCH_INTENT_ACCEPTED" not in events_ddl
    return store


def _execution_resolution(grant: dict, *, predecessor_state: str, outcome: str,
                          resolution_id: str, key: bytes = EXECUTION_RESOLUTION_KEY) -> dict:
    attestations = {
        "NO_EXECUTION_PROVEN": "operator-attests-no-child-launch-for-grant",
        "EFFECTS_RESOLVED": "operator-attests-all-effects-resolved-for-grant",
        "EFFECTS_UNRESOLVED": "operator-attests-effects-unresolved-for-grant",
        "RECONCILIATION_REJECTED": "operator-rejects-reconciliation-for-grant",
    }
    body = {
        "version": 1,
        "resolution_id": resolution_id,
        "outcome": outcome,
        "attestation": attestations.get(outcome, "invalid-attestation"),
        "evidence_sha256": "f" * 64,
        "actor": "operator",
        "key_id": hashlib.sha256(key).hexdigest(),
        "grant_id": grant["grant_id"],
        "grant_sha256": hashlib.sha256(contracts.canonical_bytes(grant)).hexdigest(),
        "request_id": grant["request_id"],
        "invocation_id": grant["invocation_id"],
        "task_id": grant["task_id"],
        "slot": grant["slot"],
        "attempt": grant["attempt"],
        "epoch": grant["epoch"],
        "run_id": grant["run_id"],
        "service_generation": grant["service_generation"],
        "predecessor_state": predecessor_state,
    }
    return {**body, "signature": sign(body, key, RUNNER_EXECUTION_RESOLUTION_LABEL)}


def _successor_grant(manifest: dict, basis: dict, *, now: float) -> dict:
    grant = _grant(manifest, now=now)
    grant.update({
        "grant_id": f"grant-{basis['attempt']}",
        "request_id": f"request-{basis['attempt']}",
        "invocation_id": f"invocation-{basis['attempt']}",
        "attempt": basis["attempt"], "epoch": basis["epoch"],
        "runner_id": basis["runner_id"], "run_id": basis["run_id"],
        "service_generation": basis["service_generation"],
        "manifest_sha256": basis["manifest_sha256"],
        "issued_at": now, "claim_expires_at": now + 30,
        "expires_at": now + 30 + grant["execution_deadline_sec"] + 30,
    })
    return grant


def _receipt_for_grant(grant: dict, manifest: dict) -> dict:
    receipt = _authority_receipt("TestRun", "tests", SIGNER_KEY, manifest)
    receipt.update({
        "invocation_id": grant["invocation_id"], "runner_id": grant["runner_id"],
        "resolved_model": grant["resolved_model"], "attempt": grant["attempt"],
    })
    request = receipt["runner_attestation"]["request"]
    request.update({
        "request_id": grant["request_id"], "task_id": grant["task_id"],
        "slot": grant["slot"], "attempt": grant["attempt"],
        "epoch": grant["epoch"], "manifest_sha256": grant["manifest_sha256"],
    })
    signature = sign(request, SIGNER_KEY, SIGNING_REQUEST_LABEL)
    receipt["runner_attestation"]["signature"] = signature
    receipt["signature"] = signature
    return receipt


def _make_indeterminate_predecessor(
    *, reserve: bool = True, story_ttl_sec: int = 1800, lease_ttl_sec: int = 1200,
):
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, execution_resolution_key=EXECUTION_RESOLUTION_KEY,
        story_ttl_sec=story_ttl_sec, lease_ttl_sec=lease_ttl_sec,
    )
    grant = _grant(manifest, now=clock())
    assert store.claim_runner_execution(grant, active_service_generation="generation-1") is None
    predecessor_state = "PENDING"
    if reserve:
        store.reserve_runner_execution(grant, active_service_generation="generation-1")
        predecessor_state = "EXECUTION_RESERVED"
    store.mark_pending_runner_executions_indeterminate(
        current_service_generation="generation-2",
    )
    return store, manifest, clock, grant, predecessor_state


def _append_completed_pass(store: Store, manifest: dict, clock: FakeClock) -> dict:
    grant = _grant(manifest, now=clock())
    assert store.claim_runner_execution(grant, active_service_generation="generation-1") is None
    store.reserve_runner_execution(grant, active_service_generation="generation-1")
    store.complete_runner_execution(
        grant, _receipt_for_grant(grant, manifest),
        active_service_generation="generation-1",
    )
    store.release_lease(manifest["task_id"], "runner-1", grant["epoch"])
    return grant


def _append_pre_0473_v5_pending_recovery_event(
    store: Store, grant: dict, clock: FakeClock, *, changes: dict | None = None,
) -> dict:
    """Persist the exact schema-v5 pre-0473 recovery event shape into Store history."""
    with store._read_tx() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        claim = conn.execute(
            "SELECT * FROM runner_execution_claims WHERE grant_id = ?",
            (grant["grant_id"],),
        ).fetchone()
    assert claim is not None
    event = {
        "event": "RUNNER_EXECUTION_INDETERMINATE",
        "state": "INDETERMINATE",
        "grant_id": claim["grant_id"],
        "payload_sha256": claim["payload_sha256"],
        "reason": "PREDECESSOR_GENERATION_STOPPED",
        "predecessor_state": "PENDING",
        "recovery_service_generation": "generation-2",
    }
    assert set(event) == {
        "event", "state", "grant_id", "payload_sha256", "reason",
        "predecessor_state", "recovery_service_generation",
    }
    if changes:
        event.update(changes)
    with store._tx() as conn:
        conn.execute(
            "INSERT INTO runner_execution_events(grant_id, state, payload, created_at) "
            "VALUES (?, 'INDETERMINATE', ?, ?)",
            (grant["grant_id"], contracts.canonical_bytes(event).decode("utf-8"), clock()),
        )
        store._record_event_locked(
            conn, grant["grant_id"], "supervisor", "NOTE", event,
        )
    return event


def _assert_raw_store_event_chain_is_valid(store: Store) -> None:
    """Prove a legacy-shape mutation is authenticated rather than hash corruption."""
    with store._read_tx() as conn:
        rows = conn.execute(
            "SELECT ts, task_id, actor, kind, payload, prev_hash, hash "
            "FROM events ORDER BY seq"
        ).fetchall()
        previous_hash = "0" * 64
        for row in rows:
            fields = {
                name: row[name] for name in ("ts", "task_id", "actor", "kind", "payload")
            }
            assert row["prev_hash"] == previous_hash
            assert store._event_mac(previous_hash, fields) == row["hash"]
            previous_hash = row["hash"]
        count, head = store._anchor_state(conn)
        assert count == len(rows)
        assert head == previous_hash


def test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor(
    tmp_path,
):
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    db_path = str(tmp_path / "pre-0473-schema-v5.sqlite3")
    writer = _store_with_pre_0473_schema_v5_claim_basis(
        manifest, clock, db_path=db_path,
    )
    reader = None
    try:
        predecessor = _grant(manifest, now=clock())
        assert writer.claim_runner_execution(
            predecessor, active_service_generation="generation-1",
        ) is None
        legacy_event = _append_pre_0473_v5_pending_recovery_event(
            writer, predecessor, clock,
        )
        assert set(legacy_event) == {
            "event", "state", "grant_id", "payload_sha256", "reason",
            "predecessor_state", "recovery_service_generation",
        }
        _assert_raw_store_event_chain_is_valid(writer)
        writer.close()

        # Store construction runs startup reconciliation against the persisted
        # event chain, as it would when reopening a schema-v5 database.
        reader = Store(
            db_path, clock, event_key=EVENT_KEY,
            execution_resolution_key=EXECUTION_RESOLUTION_KEY,
            allow_schema_upgrade=True,
        )
        with reader._read_tx() as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
        _assert_raw_store_event_chain_is_valid(reader)
        assert reader.reconciliation_complete
        assert reader.runner_execution_claim_status(
            predecessor, active_service_generation="generation-1",
        ) == {
            "state": "INDETERMINATE", "service_generation": "generation-1",
        }

        reader.release_lease(manifest["task_id"], "runner-1", predecessor["epoch"])
        reader.acquire_lease(
            manifest["task_id"], manifest["story_id"], "runner-1", 2, 2, 3600,
            supervisor_key=SUPERVISOR_KEY,
        )
        with pytest.raises(StoreError, match="consumed run-bound preflight") as error:
            reader.execution_grant_basis(
                manifest["task_id"], "tests", 2, 2, "run-2",
                active_service_generation="generation-2",
            )
        assert error.value.kind == "probe"

        reader.ensure_preflight_consumed("run-2", "nonce-2", "c" * 64, "d" * 64)
        basis = reader.execution_grant_basis(
            manifest["task_id"], "tests", 2, 2, "run-2",
            active_service_generation="generation-2",
        )
        successor = _successor_grant(manifest, basis, now=clock())
        assert reader.claim_runner_execution(
            successor, active_service_generation="generation-2",
        ) is None
        assert reader.runner_execution_claim_status(
            predecessor, active_service_generation="generation-1",
        )["state"] == "INDETERMINATE"
    finally:
        if reader is not None:
            reader.close()
        else:
            writer.close()


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"terminal_disposition": "NO_EXECUTION"}, id="unexpected-legacy-field"),
        pytest.param({"predecessor_state": "EXECUTION_RESERVED"}, id="predecessor-mismatch"),
        pytest.param({"grant_id": "other-grant"}, id="grant-mismatch"),
        pytest.param({"payload_sha256": "0" * 64}, id="claim-digest-mismatch"),
        pytest.param({"recovery_service_generation": "generation-1"}, id="not-a-successor-generation"),
    ],
)
def test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields(
    changes: dict, tmp_path,
):
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    db_path = str(tmp_path / "malformed-pre-0473-schema-v5.sqlite3")
    store = _store_with_pre_0473_schema_v5_claim_basis(
        manifest, clock, db_path=db_path,
    )
    reader = None
    try:
        grant = _grant(manifest, now=clock())
        assert store.claim_runner_execution(
            grant, active_service_generation="generation-1",
        ) is None
        _append_pre_0473_v5_pending_recovery_event(
            store, grant, clock, changes=changes,
        )

        _assert_raw_store_event_chain_is_valid(store)
        store.close()
        reader = Store(
            db_path, clock, event_key=EVENT_KEY,
            execution_resolution_key=EXECUTION_RESOLUTION_KEY,
            allow_schema_upgrade=True,
        )
        with reader._read_tx() as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
        _assert_raw_store_event_chain_is_valid(reader)
        assert not reader.reconciliation_complete
        with pytest.raises(StoreError) as error:
            reader.runner_execution_claim_status(
                grant, active_service_generation="generation-1",
            )
        assert error.value.kind == "integrity"
    finally:
        if reader is not None:
            reader.close()
        else:
            store.close()


def _assert_successor_gates_blocked(store: Store, manifest: dict, clock: FakeClock) -> None:
    with pytest.raises(StoreError, match="blocks continuation"):
        store.acquire_lease(
            manifest["task_id"], manifest["story_id"], "runner-1", 2, 2, 1200,
            supervisor_key=SUPERVISOR_KEY,
        )
    with pytest.raises(StoreError, match="blocks continuation"):
        store.execution_grant_basis(
            manifest["task_id"], "tests", 2, 2, "run-2",
            active_service_generation="generation-2",
        )
    successor = _grant(manifest, now=clock())
    successor.update({
        "grant_id": "grant-successor", "request_id": "request-successor",
        "invocation_id": "invocation-successor", "attempt": 2,
        "run_id": "run-2", "service_generation": "generation-2",
    })
    with pytest.raises(StoreError, match="blocks continuation"):
        store.claim_runner_execution(
            successor, active_service_generation="generation-2",
        )


def test_store_claim_rejects_deadline_beyond_manifest_before_persisting_claim():
    manifest, _registry, _reviewer_key, _keys = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(manifest, clock)
    try:
        with pytest.raises(StoreError, match="full manifest run window"):
            store.claim_runner_execution(
                _grant(manifest, deadline=601, now=clock()),
                active_service_generation="generation-1",
            )
        assert store._conn.execute("SELECT COUNT(*) FROM runner_execution_claims").fetchone()[0] == 0
    finally:
        store.close()


def test_store_completion_appends_the_receipt_chain_and_replays_only_exact_complete_receipt():
    manifest, _registry, _reviewer_key, _keys = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(manifest, clock)
    grant = _grant(manifest, now=clock())
    try:
        basis = store.execution_grant_basis(
            manifest["task_id"], "tests", 1, 2, "run-1",
            active_service_generation="generation-1",
        )
        assert basis == {
            "task_id": manifest["task_id"], "slot": "tests", "attempt": 1,
            "epoch": 2, "run_id": "run-1",
            "manifest_sha256": contracts.manifest_sha256(manifest),
            "manifest_timeout_sec": manifest["timeout_sec"],
            "runner_id": "runner-1", "service_generation": "generation-1",
            "authority_expires_at": 2200.0,
        }
        assert store.claim_runner_execution(grant, active_service_generation="generation-1") is None
        assert store.verify_pending_runner_execution(
            grant, active_service_generation="generation-1",
        ) is True
        store.reserve_runner_execution(grant, active_service_generation="generation-1")
        receipt = _authority_receipt("TestRun", "tests", SIGNER_KEY, manifest)
        receipt["invocation_id"] = grant["invocation_id"]
        receipt["runner_id"] = grant["runner_id"]
        receipt["resolved_model"] = grant["resolved_model"]
        request = receipt["runner_attestation"]["request"]
        request.update({
            "request_id": grant["request_id"], "task_id": grant["task_id"],
            "slot": grant["slot"], "attempt": grant["attempt"],
            "epoch": grant["epoch"], "manifest_sha256": grant["manifest_sha256"],
        })
        signature = sign(request, SIGNER_KEY, SIGNING_REQUEST_LABEL)
        receipt["runner_attestation"]["signature"] = signature
        receipt["signature"] = signature
        store.complete_runner_execution(
            grant, receipt, active_service_generation="generation-1",
        )
        assert store.verify_pending_runner_execution(
            grant, active_service_generation="generation-1",
        ) is False

        receipts = store.receipts_for_task(manifest["task_id"])
        assert receipts == [receipt]
        assert store.previous_receipt_sha256(manifest["task_id"], "tests") == contracts.receipt_sha256(receipt)
        assert store.claim_runner_execution(
            grant, active_service_generation="generation-1",
        ) == receipt
        assert store._conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1
    finally:
        store.close()


def test_verified_pre_spawn_gap_allows_next_receipt_and_preserves_receipt_hash_chain():
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, execution_resolution_key=EXECUTION_RESOLUTION_KEY,
        story_ttl_sec=3600,
    )
    try:
        first = _append_completed_pass(store, manifest, clock)
        first_receipt = store.receipts_for_task(manifest["task_id"])[0]

        store.acquire_lease(
            manifest["task_id"], manifest["story_id"], "runner-1", 2, 2, 1200,
            supervisor_key=SUPERVISOR_KEY,
        )
        store.ensure_preflight_consumed("run-2", "nonce-2", "c" * 64, "d" * 64)
        basis2 = store.execution_grant_basis(
            manifest["task_id"], "tests", 2, 2, "run-2",
            active_service_generation="generation-1",
        )
        grant2 = _successor_grant(manifest, basis2, now=clock())
        assert store.claim_runner_execution(
            grant2, active_service_generation="generation-1",
        ) is None
        terminal = store.mark_runner_prespawn_no_execution(
            grant2, active_service_generation="generation-1",
            reason_code="RUNNER_PRESPAWN_FAILURE",
        )
        assert terminal == {
            "state": "NO_EXECUTION", "grant_id": grant2["grant_id"],
            "payload_sha256": hashlib.sha256(contracts.canonical_bytes(grant2)).hexdigest(),
            "service_generation": "generation-1",
        }
        store.release_lease(manifest["task_id"], "runner-1", 2)

        store.acquire_lease(
            manifest["task_id"], manifest["story_id"], "runner-1", 2, 3, 1200,
            supervisor_key=SUPERVISOR_KEY,
        )
        store.ensure_preflight_consumed("run-3", "nonce-3", "e" * 64, "f" * 64)
        basis3 = store.execution_grant_basis(
            manifest["task_id"], "tests", 3, 2, "run-3",
            active_service_generation="generation-1",
        )
        grant3 = _successor_grant(manifest, basis3, now=clock())
        assert store.claim_runner_execution(
            grant3, active_service_generation="generation-1",
        ) is None
        store.reserve_runner_execution(grant3, active_service_generation="generation-1")
        receipt3 = _receipt_for_grant(grant3, manifest)
        receipt3["receipt_id"] = "receipt-attempt-3"
        receipt3["prev_receipt_sha256"] = contracts.receipt_sha256(first_receipt)
        store.complete_runner_execution(
            grant3, receipt3, active_service_generation="generation-1",
        )

        receipts = store.receipts_for_task(manifest["task_id"])
        receipt_rows = [
            (receipt["slot"], receipt["attempt"], receipt["receipt_id"], receipt["receipt_type"])
            for receipt in receipts
        ]
        assert [receipt["attempt"] for receipt in receipts] == [1, 3], receipt_rows
        assert receipts[1]["prev_receipt_sha256"] == contracts.receipt_sha256(first_receipt)
        assert first["attempt"] == 1
        decision = _evaluate_store_gate(store, manifest)
        assert decision["verdict"] == "MODIFY"
        assert "attempt chain broken" not in str(decision)
    finally:
        store.close()


def test_effects_resolved_gap_links_successor_to_last_real_receipt_hash():
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, execution_resolution_key=EXECUTION_RESOLUTION_KEY,
        story_ttl_sec=3600,
    )
    try:
        _append_completed_pass(store, manifest, clock)
        first_receipt = next(
            receipt for receipt in store.receipts_for_task(manifest["task_id"])
            if receipt["slot"] == "tests" and receipt["receipt_type"] == "TestRun"
        )
        first_receipt_sha256 = contracts.receipt_sha256(first_receipt)

        store.acquire_lease(
            manifest["task_id"], manifest["story_id"], "runner-1", 2, 2, 1200,
            supervisor_key=SUPERVISOR_KEY,
        )
        store.ensure_preflight_consumed("run-2", "nonce-2", "c" * 64, "d" * 64)
        basis2 = store.execution_grant_basis(
            manifest["task_id"], "tests", 2, 2, "run-2",
            active_service_generation="generation-1",
        )
        grant2 = _successor_grant(manifest, basis2, now=clock())
        assert store.claim_runner_execution(
            grant2, active_service_generation="generation-1",
        ) is None
        store.reserve_runner_execution(grant2, active_service_generation="generation-1")
        store.mark_pending_runner_executions_indeterminate(
            current_service_generation="generation-2",
        )
        resolution = _execution_resolution(
            grant2, predecessor_state="EXECUTION_RESERVED", outcome="EFFECTS_RESOLVED",
            resolution_id="effects-resolved-gap-chain-1",
        )
        assert store.reconcile_runner_execution(resolution) == {
            "grant_id": grant2["grant_id"], "state": "RECONCILED",
            "outcome": "EFFECTS_RESOLVED", "continuation_allowed": True,
        }

        clock.advance(1201)
        store.supervisor_reap_and_mark(SUPERVISOR_KEY, "store-test-supervisor")
        store.acquire_lease(
            manifest["task_id"], manifest["story_id"], "runner-1", 2, 3, 1200,
            supervisor_key=SUPERVISOR_KEY,
        )
        store.ensure_preflight_consumed("run-3", "nonce-3", "e" * 64, "f" * 64)
        basis3 = store.execution_grant_basis(
            manifest["task_id"], "tests", 3, 2, "run-3",
            active_service_generation="generation-2",
        )
        grant3 = _successor_grant(manifest, basis3, now=clock())
        assert store.claim_runner_execution(
            grant3, active_service_generation="generation-2",
        ) is None
        store.reserve_runner_execution(grant3, active_service_generation="generation-2")
        receipt3 = _receipt_for_grant(grant3, manifest)
        receipt3["receipt_id"] = "receipt-after-effects-resolved"
        receipt3["prev_receipt_sha256"] = first_receipt_sha256
        store.complete_runner_execution(
            grant3, receipt3, active_service_generation="generation-2",
        )

        receipts = [
            receipt for receipt in store.receipts_for_task(manifest["task_id"])
            if receipt["slot"] == "tests" and receipt["receipt_type"] == "TestRun"
        ]
        receipt_rows = [
            (receipt["slot"], receipt["attempt"], receipt["receipt_id"], receipt["receipt_type"])
            for receipt in receipts
        ]
        assert [receipt["attempt"] for receipt in receipts] == [1, 3], receipt_rows
        assert receipts[0] == first_receipt
        assert receipts[1]["prev_receipt_sha256"] == first_receipt_sha256
        assert store.previous_receipt_sha256(
            manifest["task_id"], "tests",
        ) == contracts.receipt_sha256(receipts[1])
        assert _evaluate_store_gate(store, manifest)["verdict"] == "MODIFY"
    finally:
        store.close()


def test_execution_gap_rejects_reserved_predecessor_and_untrusted_gate_gap_evidence():
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, execution_resolution_key=EXECUTION_RESOLUTION_KEY,
        story_ttl_sec=3600,
    )
    try:
        _append_completed_pass(store, manifest, clock)
        store.acquire_lease(
            manifest["task_id"], manifest["story_id"], "runner-1", 2, 2, 1200,
            supervisor_key=SUPERVISOR_KEY,
        )
        store.ensure_preflight_consumed("run-2", "nonce-2", "c" * 64, "d" * 64)
        basis = store.execution_grant_basis(
            manifest["task_id"], "tests", 2, 2, "run-2",
            active_service_generation="generation-1",
        )
        grant = _successor_grant(manifest, basis, now=clock())
        assert store.claim_runner_execution(
            grant, active_service_generation="generation-1",
        ) is None
        store.reserve_runner_execution(grant, active_service_generation="generation-1")
        store.mark_pending_runner_executions_indeterminate(
            current_service_generation="generation-2",
        )
        with store._read_tx() as conn:
            assert not store._runner_receipt_gap_is_eligible_locked(
                conn, manifest["task_id"], "tests", 1, 3,
            )

        worker_key, options = _gate_options()
        with pytest.raises(
            StoreError, match="runner successor eligibility is supplied only by verified Store history",
        ):
            store.evaluate_gate(
                manifest["task_id"], "a" * 40, 2, worker_key,
                verified_successor_attempts={"tests": {2}}, **options,
            )
    finally:
        store.close()


def test_runner_prespawn_terminalization_binds_exact_claim_and_blocks_later_reserve():
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(manifest, clock)
    grant = _grant(manifest, now=clock())
    try:
        assert store.claim_runner_execution(
            grant, active_service_generation="generation-1",
        ) is None
        mismatched = copy.deepcopy(grant)
        mismatched["request_id"] = "different-request"
        with pytest.raises(StoreError, match="does not match the exact claim"):
            store.mark_runner_prespawn_no_execution(
                mismatched, active_service_generation="generation-1",
                reason_code="RUNNER_PRESPAWN_FAILURE",
            )
        with pytest.raises(StoreError, match="not recognized"):
            store.mark_runner_prespawn_no_execution(
                grant, active_service_generation="generation-1", reason_code="UNKNOWN",
            )

        result = store.mark_runner_prespawn_no_execution(
            grant, active_service_generation="generation-1",
            reason_code="RUNNER_PRESPAWN_FAILURE",
        )
        assert result["state"] == "NO_EXECUTION"
        assert store.runner_execution_claim_status(
            grant, active_service_generation="generation-1",
        ) == {
            "state": "INDETERMINATE", "service_generation": "generation-1",
            "reason_code": "RUNNER_PRESPAWN_FAILURE",
        }
        with pytest.raises(StoreError, match="not an unreserved PENDING claim"):
            store.reserve_runner_execution(grant, active_service_generation="generation-1")
        assert store.runner_execution_claim_status(
            grant, active_service_generation="generation-1",
        )["reason_code"] == "RUNNER_PRESPAWN_FAILURE"
    finally:
        store.close()


def test_pre_reserve_runner_failure_terminalizes_claim_without_calling_reserve(monkeypatch):
    from tools.vst import execution_grant as grant_module, runner, runner_service

    manifest, *_ = _authority_fixture()
    grant = _grant(manifest, deadline=30)
    calls = []

    class FakeSupervisor:
        def previous_receipt(self, *_args):
            return None

        def claim(self, _grant):
            calls.append("claim")
            return None

        def claim_status(self, _grant):
            return {"state": "PENDING", "service_generation": "generation-1"}

        def terminalize_no_execution(self, received, reason_code):
            calls.append(("no_execution", reason_code))
            return {
                "state": "NO_EXECUTION", "grant_id": received["grant_id"],
                "payload_sha256": hashlib.sha256(contracts.canonical_bytes(received)).hexdigest(),
                "service_generation": received["service_generation"],
            }

        def reserve(self, _grant):
            raise AssertionError("reserve must not run after a pre-spawn failure")

    server = object.__new__(runner_service.PersistentRunnerService)
    server.config = type("Config", (), {
        "deadline_sec": 60, "timeout_sec": 30, "daemon_uid": 997,
        "grant_trust_keys": {"grant-key-1": "/unused"},
        "openssl_path": "/unused", "audience": "vst-runner-service-v1",
        "signer_socket": "/unused/signer.sock", "repository_root": "/unused/repo",
        "worker_uid": 999, "worker_gid": 989, "max_output_bytes": 1024,
        "worker_exec_helper_head": "a" * 40,
        "worker_exec_helper_path": "/usr/local/libexec/vst-s4-worker-exec-" + "a" * 40,
    })()
    server.worker_exec_helper_identity = (1, 2, 3, 0, 988, 0o4750, "c" * 64)
    server.supervisor = FakeSupervisor()
    server._require_local_boundary = lambda: "generation-1"
    monkeypatch.setattr(grant_module, "verify_execution_grant", lambda *_args, **_kwargs: grant)
    monkeypatch.setattr(grant_module.os, "name", "posix")
    monkeypatch.setattr(grant_module.os, "geteuid", lambda: 997, raising=False)

    def fail_before_spawn(**kwargs):
        authority = kwargs["execution_authority"]
        context = {key: grant[key] for key in (
            "manifest_sha256", "task_id", "slot", "attempt", "epoch", "run_id",
            "invocation_id", "request_id", "runner_id", "resolved_model",
            "model_provenance_sha256", "execution_deadline_sec", "service_generation",
        )}
        authority.authorize_and_claim(context)
        raise OSError("signer unavailable before spawn")

    monkeypatch.setattr(runner, "run_manifest_commands", fail_before_spawn)
    with pytest.raises(OSError, match="signer unavailable before spawn"):
        server._run_grant(grant, manifest, [], "generation-1")
    assert calls == ["claim", ("no_execution", "RUNNER_PRESPAWN_FAILURE")]


@pytest.mark.parametrize("stage", ["issue", "claim", "reserve"])
def test_runner_authority_window_must_cover_manifest_timeout_and_completion_margin(stage, monkeypatch):
    from tools.vst.supervisor import Supervisor
    from tools.vst import execution_grant as grant_module

    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, story_ttl_sec=3600, lease_ttl_sec=3600,
    )
    grant = _grant(manifest, now=clock())
    grant["expires_at"] = clock() + 5000
    grant["claim_expires_at"] = clock() + 4000
    supervisor = Supervisor(
        store, operation_backend=None,
        execution_grant_key_id="grant-key-1",
        execution_grant_private_key_path="/unused/private.key",
        execution_grant_openssl_path="/unused/openssl",
        execution_grant_trust_keys={"grant-key-1": "/unused/public.key"},
        service_generation_provider=lambda: "generation-1",
        model_provenance_verifier=lambda _model, _digest: True,
    )
    monkeypatch.setattr(grant_module, "sign_execution_grant", lambda body, **_kwargs: dict(body))
    try:
        if stage == "issue":
            store._conn.execute(
                "UPDATE leases SET expires_at = ? WHERE task_id = ? AND attempt = 1",
                (clock() + 604, manifest["task_id"]),
            )
            with pytest.raises(StoreError, match="cannot cover the required run and completion margin"):
                supervisor.issue_execution_grant(
                    task_id=manifest["task_id"], slot="tests", attempt=1, epoch=2,
                    run_id="run-1", resolved_model="test-model",
                    model_provenance_sha256="e" * 64,
                )
            assert store._conn.execute(
                "SELECT COUNT(*) FROM runner_execution_claims",
            ).fetchone()[0] == 0
        elif stage == "claim":
            store._conn.execute(
                "UPDATE leases SET expires_at = ? WHERE task_id = ? AND attempt = 1",
                (clock() + 604, manifest["task_id"]),
            )
            with pytest.raises(StoreError, match="remaining owner/lease authority window"):
                store.claim_runner_execution(
                    grant, active_service_generation="generation-1",
                )
            assert store._conn.execute(
                "SELECT COUNT(*) FROM runner_execution_claims",
            ).fetchone()[0] == 0
        else:
            assert store.claim_runner_execution(
                grant, active_service_generation="generation-1",
            ) is None
            store._conn.execute(
                "UPDATE leases SET expires_at = ? WHERE task_id = ? AND attempt = 1",
                (clock() + 604, manifest["task_id"]),
            )
            with pytest.raises(StoreError, match="remaining owner/lease authority window"):
                store.reserve_runner_execution(
                    grant, active_service_generation="generation-1",
                )
            assert store.runner_execution_claim_status(
                grant, active_service_generation="generation-1",
            )["state"] == "PENDING"
    finally:
        store.close()


def test_runner_grant_uses_full_manifest_timeout_when_issuance_is_feasible(monkeypatch):
    from tools.vst.supervisor import Supervisor
    from tools.vst import execution_grant as grant_module

    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, story_ttl_sec=3600, lease_ttl_sec=3600,
    )
    supervisor = Supervisor(
        store, operation_backend=None,
        execution_grant_key_id="grant-key-1",
        execution_grant_private_key_path="/unused/private.key",
        execution_grant_openssl_path="/unused/openssl",
        execution_grant_trust_keys={"grant-key-1": "/unused/public.key"},
        service_generation_provider=lambda: "generation-1",
        model_provenance_verifier=lambda _model, _digest: True,
    )
    monkeypatch.setattr(grant_module, "sign_execution_grant", lambda body, **_kwargs: dict(body))
    try:
        grant = supervisor.issue_execution_grant(
            task_id=manifest["task_id"], slot="tests", attempt=1, epoch=2,
            run_id="run-1", resolved_model="test-model",
            model_provenance_sha256="e" * 64,
        )
        assert grant["execution_deadline_sec"] == manifest["timeout_sec"]
        assert grant["expires_at"] <= 4600.0
    finally:
        store.close()


def test_operator_reconciliation_rpc_is_versioned_and_role_pinned(monkeypatch):
    import json
    import os
    import struct
    from tools.vst import supervisor_service as rpc

    resolution = {"grant_id": "grant-1", "signature": "signed-resolution"}
    calls = []

    class FakeSupervisor:
        def reconcile_runner_execution(self, record):
            calls.append(record)
            return {"state": "RECONCILED", "grant_id": record["grant_id"]}

    class FakeConnection:
        def __init__(self, *, pid, uid, gid, operation, body):
            payload = json.dumps({"operation": operation, "body": body}).encode("utf-8")
            self.frames = [rpc._HEADER.pack(len(payload)) + payload]
            self.credentials = struct.pack("3i", pid, uid, gid)
            self.response = b""

        def settimeout(self, _seconds):
            return None

        def getsockopt(self, *_args):
            return self.credentials

        def recv(self, size):
            if not self.frames:
                return b""
            frame = self.frames[0]
            part, remainder = frame[:size], frame[size:]
            if remainder:
                self.frames[0] = remainder
            else:
                self.frames.pop(0)
            return part

        def sendall(self, response):
            self.response = response

    peers = {
        (3001, 2001): rpc.SupervisorPeer(
            "dispatcher", 3001, 2001, "/system.slice/vst-dispatcher.service",
            frozenset({"issue_grant"}),
        ),
        (997, 988): rpc.SupervisorPeer(
            "runnerd", 997, 988, "/system.slice/vst-runner.service",
            frozenset({"claim", "claim_status", "reserve", "complete", "generation",
                       "recover", "manifest", "previous_receipt", "no_execution"}),
        ),
        (3002, 2001): rpc.SupervisorPeer(
            "operator", 3002, 2001, "/system.slice/vst-operator.service",
            frozenset({"reconcile_runner_execution"}),
        ),
    }
    server = object.__new__(rpc.AuthenticatedSupervisorAPI)
    server.supervisor = FakeSupervisor()
    server.peers = peers
    server.require_peer_pidfd = True
    monkeypatch.setattr(rpc.socket, "SO_PEERCRED", 1, raising=False)
    monkeypatch.setattr(rpc, "_peer_pidfd", lambda *_args, **_kwargs: os.open(os.devnull, os.O_RDONLY))
    monkeypatch.setattr(rpc, "_pidfd_alive", lambda _fd: True)
    monkeypatch.setattr(
        rpc, "_read_peer_cgroup",
        lambda pid: {
            101: "/system.slice/vst-dispatcher.service",
            102: "/system.slice/vst-runner.service",
            103: "/system.slice/vst-operator.service",
        }[pid],
    )

    operator_conn = FakeConnection(
        pid=103, uid=3002, gid=2001, operation="reconcile_runner_execution",
        body={"version": 1, "resolution": resolution},
    )
    server._handle(operator_conn)
    operator_size = rpc._HEADER.unpack(operator_conn.response[:rpc._HEADER.size])[0]
    operator_response = json.loads(operator_conn.response[rpc._HEADER.size:rpc._HEADER.size + operator_size])
    assert operator_response == {
        "ok": True, "result": {"state": "RECONCILED", "grant_id": "grant-1"},
    }
    assert calls == [resolution]

    for pid, uid, gid in ((101, 3001, 2001), (102, 997, 988)):
        conn = FakeConnection(
            pid=pid, uid=uid, gid=gid, operation="reconcile_runner_execution",
            body={"version": 1, "resolution": resolution},
        )
        server._handle(conn)
        size = rpc._HEADER.unpack(conn.response[:rpc._HEADER.size])[0]
        response = json.loads(conn.response[rpc._HEADER.size:rpc._HEADER.size + size])
        assert response == {"error": "refused", "ok": False}
    assert calls == [resolution]

    with pytest.raises(contracts.ContractError, match="operator reconciliation request fields"):
        server._dispatch(
            "reconcile_runner_execution", {"version": True, "resolution": resolution},
        )
    assert calls == [resolution]


def _claim_successor_after_stale_pass(store: Store, manifest: dict, clock: FakeClock) -> dict:
    store.acquire_lease(
        manifest["task_id"], manifest["story_id"], "runner-1", 2, 2, 1200,
        supervisor_key=SUPERVISOR_KEY,
    )
    store.ensure_preflight_consumed("run-2", "nonce-2", "c" * 64, "d" * 64)
    basis = store.execution_grant_basis(
        manifest["task_id"], "tests", 2, 2, "run-2",
        active_service_generation="generation-1",
    )
    successor = _successor_grant(manifest, basis, now=clock())
    assert store.claim_runner_execution(
        successor, active_service_generation="generation-1",
    ) is None
    return successor


def _gate_options():
    _manifest, registry, reviewer_key, _keys = _authority_fixture()
    return _keys["worker"], {
        "supervisor_key": SUPERVISOR_KEY,
        "operator_key": _keys["operator"],
        "reviewer_registry": registry,
        "reviewer_keys": {"reviewer-key-1": reviewer_key},
        "signer_key": SIGNER_KEY,
        "event_key": EVENT_KEY,
    }


def _evaluate_store_gate(store: Store, manifest: dict) -> dict:
    worker_key, options = _gate_options()
    return store.evaluate_gate(
        manifest["task_id"], "a" * 40, 2, worker_key, **options,
    )


@pytest.mark.parametrize("newer_state", ["PENDING", "EXECUTION_RESERVED", "INDETERMINATE"])
def test_gate_refuses_stale_pass_when_newer_execution_is_unresolved(newer_state):
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, execution_resolution_key=EXECUTION_RESOLUTION_KEY,
    )
    try:
        _append_completed_pass(store, manifest, clock)
        successor = _claim_successor_after_stale_pass(store, manifest, clock)
        if newer_state in {"EXECUTION_RESERVED", "INDETERMINATE"}:
            store.reserve_runner_execution(successor, active_service_generation="generation-1")
        if newer_state == "INDETERMINATE":
            store.mark_pending_runner_executions_indeterminate(
                current_service_generation="generation-2",
            )
        with pytest.raises(StoreError, match="blocks continuation"):
            _evaluate_store_gate(store, manifest)
    finally:
        store.close()


@pytest.mark.parametrize("safe_terminal", ["COMPLETE", "EFFECTS_RESOLVED", "PENDING_PRESPAWN"])
def test_gate_stays_default_closed_and_evaluates_only_after_safe_execution_terminal(safe_terminal):
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, execution_resolution_key=EXECUTION_RESOLUTION_KEY,
    )
    try:
        _append_completed_pass(store, manifest, clock)
        successor = _claim_successor_after_stale_pass(store, manifest, clock)
        if safe_terminal == "COMPLETE":
            store.reserve_runner_execution(successor, active_service_generation="generation-1")
            receipt = _receipt_for_grant(successor, manifest)
            receipt["receipt_id"] = f"r-tests-{successor['attempt']}"
            receipt["prev_receipt_sha256"] = store.previous_receipt_sha256(
                manifest["task_id"], "tests",
            )
            store.complete_runner_execution(
                successor, receipt,
                active_service_generation="generation-1",
            )
        elif safe_terminal == "EFFECTS_RESOLVED":
            store.reserve_runner_execution(successor, active_service_generation="generation-1")
            store.mark_pending_runner_executions_indeterminate(
                current_service_generation="generation-2",
            )
            store.reconcile_runner_execution(_execution_resolution(
                successor, predecessor_state="EXECUTION_RESERVED", outcome="EFFECTS_RESOLVED",
                resolution_id="gate-effects-resolved-1",
            ))
        else:
            store.mark_pending_runner_executions_indeterminate(
                current_service_generation="generation-2",
            )

        decision = _evaluate_store_gate(store, manifest)
        # The stale PASS alone does not satisfy the other manifest receipt slots.
        assert decision["verdict"] != "APPROVE"
        if safe_terminal == "COMPLETE":
            assert len(decision["required_receipt_hashes"]) >= 1
    finally:
        store.close()


@pytest.mark.parametrize("failure", ["runner_failure", "complete_persistence_failure"])
def test_runner_service_fail_stops_every_post_reservation_failure_before_complete(
    failure, monkeypatch,
):
    from tools.vst import runner, runner_service
    from tools.vst.execution_grant import AmbiguousExecutionAuthorityError

    manifest, *_ = _authority_fixture()
    grant = _grant(manifest, deadline=30)
    server = object.__new__(runner_service.PersistentRunnerService)
    server.config = type("Config", (), {
        "deadline_sec": 60, "timeout_sec": 30, "daemon_uid": 997,
        "grant_trust_keys": {"grant-key-1": "/unused"},
        "openssl_path": "/unused", "audience": "vst-runner-service-v1",
        "signer_socket": "/unused/signer.sock", "repository_root": "/unused/repo",
        "worker_uid": 999, "worker_gid": 989, "max_output_bytes": 1024,
        "worker_exec_helper_head": "a" * 40,
        "worker_exec_helper_path": "/usr/local/libexec/vst-s4-worker-exec-" + "a" * 40,
    })()
    server.worker_exec_helper_identity = (1, 2, 3, 0, 988, 0o4750, "c" * 64)
    server.supervisor = type("Supervisor", (), {
        "previous_receipt": lambda *_args: None,
    })()

    class FakeAuthority:
        def __init__(self, *_args, **_kwargs):
            self.reservation_confirmed = False
            self.completion_confirmed = False
            self.claim_confirmed = False
            self.no_execution_confirmed = False

        def terminalize_no_execution(self, *_args):
            raise AssertionError("reserved execution must never be terminalized as no-execution")

        def fail_complete(self, _receipt):
            self.reservation_confirmed = True
            raise TimeoutError("COMPLETE persistence reply unavailable")

    monkeypatch.setattr(runner_service, "ExecutionAuthority", FakeAuthority)

    def fail_after_reservation(**kwargs):
        authority = kwargs["execution_authority"]
        authority.reservation_confirmed = True
        if failure == "complete_persistence_failure":
            authority.fail_complete({"receipt_id": "receipt-1"})
        raise RuntimeError("worker failed after reservation")

    monkeypatch.setattr(runner, "run_manifest_commands", fail_after_reservation)
    with pytest.raises(AmbiguousExecutionAuthorityError, match="before durable COMPLETE"):
        server._run_grant(grant, manifest, [], "generation-1")


def test_post_reservation_boundary_exception_confirms_reservation_and_fails_stop(monkeypatch):
    from tools.vst import runner, runner_service
    from tools.vst.execution_grant import AmbiguousExecutionAuthorityError
    import tools.vst.execution_grant as grant_module

    manifest, *_ = _authority_fixture()
    grant = _grant(manifest, deadline=30)
    boundary_calls = []

    def require_boundary():
        boundary_calls.append(len(boundary_calls) + 1)
        if len(boundary_calls) == 3:
            raise OSError("generation probe failed after reservation commit")
        return "generation-1"

    class FakeSupervisor:
        def previous_receipt(self, *_args):
            return None

        def claim(self, _grant):
            return None

        def claim_status(self, _grant):
            return {"state": "PENDING", "service_generation": "generation-1"}

        def reserve(self, received):
            return {
                "state": "EXECUTION_RESERVED", "grant_id": received["grant_id"],
                "payload_sha256": hashlib.sha256(contracts.canonical_bytes(received)).hexdigest(),
                "service_generation": received["service_generation"],
            }

        def complete(self, *_args):
            raise AssertionError("completion must not be attempted after boundary exception")

    server = object.__new__(runner_service.PersistentRunnerService)
    server.config = type("Config", (), {
        "deadline_sec": 60, "timeout_sec": 30, "daemon_uid": 997,
        "grant_trust_keys": {"grant-key-1": "/unused"},
        "openssl_path": "/unused", "audience": "vst-runner-service-v1",
        "signer_socket": "/unused/signer.sock", "repository_root": "/unused/repo",
        "worker_uid": 999, "worker_gid": 989, "max_output_bytes": 1024,
        "worker_exec_helper_head": "a" * 40,
        "worker_exec_helper_path": "/usr/local/libexec/vst-s4-worker-exec-" + "a" * 40,
    })()
    server.worker_exec_helper_identity = (1, 2, 3, 0, 988, 0o4750, "c" * 64)
    server.supervisor = FakeSupervisor()
    server._require_local_boundary = require_boundary
    monkeypatch.setattr(grant_module, "verify_execution_grant", lambda *_args, **_kwargs: grant)
    monkeypatch.setattr(grant_module.os, "name", "posix")
    monkeypatch.setattr(grant_module.os, "geteuid", lambda: 997, raising=False)
    dispatched = []
    authorities = []

    def runner_starts(**kwargs):
        authority = kwargs["execution_authority"]
        authorities.append(authority)
        context = {key: grant[key] for key in (
            "manifest_sha256", "task_id", "slot", "attempt", "epoch", "run_id",
            "invocation_id", "request_id", "runner_id", "resolved_model",
            "model_provenance_sha256", "execution_deadline_sec", "service_generation",
        )}
        authority.authorize_and_claim(context)
        authority.reserve()
        dispatched.append("child-started")

    monkeypatch.setattr(runner, "run_manifest_commands", runner_starts)
    with pytest.raises(AmbiguousExecutionAuthorityError, match="before durable COMPLETE"):
        server._run_grant(grant, manifest, [], "generation-1")

    assert boundary_calls == [1, 2, 3]
    assert len(authorities) == 1
    assert authorities[0].reservation_confirmed is True
    assert authorities[0].completion_confirmed is False
    assert dispatched == []


def test_runner_config_requires_and_loads_fixed_daemon_gid(monkeypatch):
    from tools.vst import runner_service

    config = {
        "socket_path": "/run/vst-runner/runner.sock",
        "runtime_dir": "/run/vst-runner",
        "supervisor_socket": "/run/vst-supervisor/supervisor.sock",
        "generation_record_path": "/var/lib/vst-runner/generation.json",
        "unit_name": "vst-runner.service",
        "socket_gid": 2001,
        "dispatcher_uid": 2002,
        "dispatcher_gid": 2001,
        "dispatcher_cgroup": "/system.slice/vst-dispatcher.service",
        "daemon_uid": 997,
        "daemon_gid": 988,
        "service_cgroup": "/system.slice/vst-runner.service",
        "audience": "vst-runner-service-v1",
        "runner_id": "runner-1",
        "repository_root": "/srv/vst/repo",
        "signer_socket": "/run/vst-signer/signer.sock",
        "openssl_path": "/usr/bin/openssl",
        "grant_trust_keys": {"grant-key-1": "/etc/vst-runner/grant.pub"},
        "worker_uid": 999,
        "worker_gid": 989,
        "worker_exec_helper_head": "a" * 40,
        "worker_exec_helper_source_sha256": "b" * 64,
        "worker_exec_helper_binary_sha256": "c" * 64,
        "worker_exec_helper_path": "/usr/local/libexec/vst-s4-worker-exec-" + "a" * 40,
    }
    monkeypatch.setattr(runner_service, "_verify_worker_exec_helper", lambda _config: None)
    monkeypatch.setattr(runner_service, "_read_root_controlled_json", lambda *_args, **_kwargs: dict(config))

    loaded = load_runner_service_config("/etc/vst-runner/runner-service.json")
    assert loaded.daemon_gid == 988

    missing_gid = dict(config)
    del missing_gid["daemon_gid"]
    monkeypatch.setattr(runner_service, "_read_root_controlled_json", lambda *_args, **_kwargs: missing_gid)
    with pytest.raises(contracts.ContractError, match="fields do not match"):
        load_runner_service_config("/etc/vst-runner/runner-service.json")

    missing_helper_path = dict(config)
    del missing_helper_path["worker_exec_helper_path"]
    monkeypatch.setattr(
        runner_service, "_read_root_controlled_json",
        lambda *_args, **_kwargs: missing_helper_path,
    )
    with pytest.raises(contracts.ContractError, match="fields do not match"):
        load_runner_service_config("/etc/vst-runner/runner-service.json")


def test_versioned_worker_helper_path_requires_full_lowercase_commit_id():
    assert _versioned_worker_exec_helper_path("a" * 40) == (
        "/usr/local/libexec/vst-s4-worker-exec-" + "a" * 40
    )
    for invalid in ("a" * 39, "A" * 40, "g" * 40, "../" + "a" * 37):
        with pytest.raises(contracts.ContractError, match="full lowercase commit id"):
            _versioned_worker_exec_helper_path(invalid)


@pytest.mark.parametrize("path", [
    "/usr/local/libexec/vst-s4-worker-exec",
    "/usr/local/libexec/vst-s4-worker-exec-" + "b" * 40,
    "/tmp/vst-s4-worker-exec-" + "a" * 40,
])
def test_versioned_worker_helper_rejects_unbound_path_before_filesystem(path):
    from types import SimpleNamespace

    config = SimpleNamespace(
        worker_exec_helper_head="a" * 40,
        worker_exec_helper_path=path,
    )
    with pytest.raises(contracts.ContractError, match="not the configured exact-version path"):
        _verify_worker_exec_helper(config)


def test_versioned_worker_helper_verifies_immutable_identity_and_uses_no_legacy_fallback(monkeypatch):
    from types import SimpleNamespace
    from tools.vst import runner_service

    head = "a" * 40
    path = _versioned_worker_exec_helper_path(head)
    payload = b"versioned-helper-test-binary"
    source_sha = "b" * 64
    expected_output = (
        f"schema=1 head={head} source_sha256={source_sha}\n"
    ).encode("ascii")
    file_identity = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o4750, st_uid=0, st_gid=988, st_nlink=1,
        st_dev=7, st_ino=19, st_size=len(payload),
    )
    directory_identity = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
    stat_calls = []
    read_values = [payload, b""]
    subprocess_calls = []

    def fake_stat(candidate, *, follow_symlinks=True):
        stat_calls.append(candidate)
        if candidate == path:
            return file_identity
        return directory_identity

    def fake_run(args, **_kwargs):
        subprocess_calls.append(args)
        return SimpleNamespace(returncode=0, stdout=expected_output)

    monkeypatch.setattr(runner_service.os, "O_NOFOLLOW", 0, raising=False)
    monkeypatch.setattr(runner_service.os, "stat", fake_stat)
    monkeypatch.setattr(runner_service.os, "open", lambda candidate, _flags: 41)
    monkeypatch.setattr(runner_service.os, "fstat", lambda _fd: file_identity)
    monkeypatch.setattr(runner_service.os, "read", lambda _fd, _size: read_values.pop(0))
    monkeypatch.setattr(runner_service.os, "close", lambda _fd: None)
    monkeypatch.setattr(runner_service.subprocess, "run", fake_run)
    config = SimpleNamespace(
        worker_exec_helper_head=head,
        worker_exec_helper_source_sha256=source_sha,
        worker_exec_helper_binary_sha256=hashlib.sha256(payload).hexdigest(),
        worker_exec_helper_path=path,
        daemon_gid=988,
    )

    identity = _verify_worker_exec_helper(config)

    assert identity == (7, 19, len(payload), 0, 988, 0o4750,
                        hashlib.sha256(payload).hexdigest())
    assert subprocess_calls == [[path, "--version"]]
    assert subprocess_calls[0][0] != "/usr/local/libexec/vst-s4-worker-exec"
    assert stat_calls[-1] == path


@pytest.mark.parametrize("metadata", [
    {"st_uid": 1000},
    {"st_gid": 987},
    {"st_mode": stat.S_IFREG | 0o755},
    {"st_nlink": 2},
])
def test_versioned_worker_helper_rejects_invalid_file_metadata(monkeypatch, metadata):
    from types import SimpleNamespace
    from tools.vst import runner_service

    head = "a" * 40
    path = _versioned_worker_exec_helper_path(head)
    payload = b"versioned-helper-test-binary"
    file_values = {
        "st_mode": stat.S_IFREG | 0o4750, "st_uid": 0, "st_gid": 988,
        "st_nlink": 1, "st_dev": 7, "st_ino": 19, "st_size": len(payload),
    }
    file_values.update(metadata)
    file_identity = SimpleNamespace(**file_values)
    directory_identity = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
    monkeypatch.setattr(runner_service.os, "O_NOFOLLOW", 0, raising=False)
    monkeypatch.setattr(
        runner_service.os, "stat",
        lambda candidate, **_kwargs: directory_identity if candidate != path else file_identity,
    )
    monkeypatch.setattr(runner_service.os, "open", lambda _candidate, _flags: 41)
    monkeypatch.setattr(runner_service.os, "fstat", lambda _fd: file_identity)
    monkeypatch.setattr(runner_service.os, "close", lambda _fd: None)
    config = SimpleNamespace(
        worker_exec_helper_head=head,
        worker_exec_helper_source_sha256="b" * 64,
        worker_exec_helper_binary_sha256=hashlib.sha256(payload).hexdigest(),
        worker_exec_helper_path=path,
        daemon_gid=988,
    )

    with pytest.raises(contracts.ContractError, match="owner, group, or setuid mode"):
        _verify_worker_exec_helper(config)


def test_versioned_worker_helper_rejects_digest_mismatch_before_execution(monkeypatch):
    from types import SimpleNamespace
    from tools.vst import runner_service

    head = "a" * 40
    path = _versioned_worker_exec_helper_path(head)
    payload = b"versioned-helper-test-binary"
    file_identity = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o4750, st_uid=0, st_gid=988, st_nlink=1,
        st_dev=7, st_ino=19, st_size=len(payload),
    )
    directory_identity = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
    executed = []
    monkeypatch.setattr(runner_service.os, "O_NOFOLLOW", 0, raising=False)
    monkeypatch.setattr(
        runner_service.os, "stat",
        lambda candidate, **_kwargs: directory_identity if candidate != path else file_identity,
    )
    monkeypatch.setattr(runner_service.os, "open", lambda _candidate, _flags: 41)
    reads = [payload, b""]
    monkeypatch.setattr(runner_service.os, "read", lambda _fd, _size: reads.pop(0))
    monkeypatch.setattr(runner_service.os, "fstat", lambda _fd: file_identity)
    monkeypatch.setattr(runner_service.os, "close", lambda _fd: None)
    monkeypatch.setattr(runner_service.subprocess, "run", lambda *args, **kwargs: executed.append(args))
    config = SimpleNamespace(
        worker_exec_helper_head=head,
        worker_exec_helper_source_sha256="b" * 64,
        worker_exec_helper_binary_sha256="c" * 64,
        worker_exec_helper_path=path,
        daemon_gid=988,
    )

    with pytest.raises(contracts.ContractError, match="binary digest"):
        _verify_worker_exec_helper(config)
    assert executed == []


def test_versioned_worker_helper_rejects_embedded_identity_mismatch(monkeypatch):
    from types import SimpleNamespace
    from tools.vst import runner_service

    head = "a" * 40
    path = _versioned_worker_exec_helper_path(head)
    payload = b"versioned-helper-test-binary"
    file_identity = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o4750, st_uid=0, st_gid=988, st_nlink=1,
        st_dev=7, st_ino=19, st_size=len(payload),
    )
    directory_identity = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
    monkeypatch.setattr(runner_service.os, "O_NOFOLLOW", 0, raising=False)
    monkeypatch.setattr(
        runner_service.os, "stat",
        lambda candidate, **_kwargs: directory_identity if candidate != path else file_identity,
    )
    monkeypatch.setattr(runner_service.os, "open", lambda _candidate, _flags: 41)
    reads = [payload, b""]
    monkeypatch.setattr(runner_service.os, "read", lambda _fd, _size: reads.pop(0))
    monkeypatch.setattr(runner_service.os, "fstat", lambda _fd: file_identity)
    monkeypatch.setattr(runner_service.os, "close", lambda _fd: None)
    monkeypatch.setattr(
        runner_service.subprocess, "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=b"wrong-build-identity\n"),
    )
    config = SimpleNamespace(
        worker_exec_helper_head=head,
        worker_exec_helper_source_sha256="b" * 64,
        worker_exec_helper_binary_sha256=hashlib.sha256(payload).hexdigest(),
        worker_exec_helper_path=path,
        daemon_gid=988,
    )

    with pytest.raises(contracts.ContractError, match="build identity"):
        _verify_worker_exec_helper(config)


def test_versioned_worker_helper_rejects_path_inode_change_during_verification(monkeypatch):
    from types import SimpleNamespace
    from tools.vst import runner_service

    head = "a" * 40
    path = _versioned_worker_exec_helper_path(head)
    payload = b"versioned-helper-test-binary"
    opened_identity = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o4750, st_uid=0, st_gid=988, st_nlink=1,
        st_dev=7, st_ino=19, st_size=len(payload),
    )
    replaced_identity = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o4750, st_uid=0, st_gid=988, st_nlink=1,
        st_dev=7, st_ino=20, st_size=len(payload),
    )
    directory_identity = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
    path_stats = []

    def fake_stat(candidate, **_kwargs):
        if candidate != path:
            return directory_identity
        path_stats.append(candidate)
        return replaced_identity

    monkeypatch.setattr(runner_service.os, "O_NOFOLLOW", 0, raising=False)
    monkeypatch.setattr(runner_service.os, "stat", fake_stat)
    monkeypatch.setattr(runner_service.os, "open", lambda _candidate, _flags: 41)
    reads = [payload, b""]
    monkeypatch.setattr(runner_service.os, "read", lambda _fd, _size: reads.pop(0))
    monkeypatch.setattr(runner_service.os, "fstat", lambda _fd: opened_identity)
    monkeypatch.setattr(runner_service.os, "close", lambda _fd: None)
    monkeypatch.setattr(
        runner_service.subprocess, "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=f"schema=1 head={head} source_sha256={'b' * 64}\n".encode("ascii"),
        ),
    )
    config = SimpleNamespace(
        worker_exec_helper_head=head,
        worker_exec_helper_source_sha256="b" * 64,
        worker_exec_helper_binary_sha256=hashlib.sha256(payload).hexdigest(),
        worker_exec_helper_path=path,
        daemon_gid=988,
    )

    with pytest.raises(contracts.ContractError, match="identity changed during verification"):
        _verify_worker_exec_helper(config)

    assert path_stats == [path]


def test_service_refuses_helper_identity_change_before_runner_spawn(monkeypatch):
    from tools.vst import runner, runner_service

    manifest, *_ = _authority_fixture()
    grant = _grant(manifest, deadline=30)
    expected_identity = (7, 19, 100, 0, 988, 0o4750, "c" * 64)
    changed_identity = (7, 20, 100, 0, 988, 0o4750, "d" * 64)
    server = object.__new__(runner_service.PersistentRunnerService)
    server.config = type("Config", (), {
        "deadline_sec": 60, "timeout_sec": 30, "daemon_uid": 997,
        "grant_trust_keys": {"grant-key-1": "/unused"},
        "openssl_path": "/unused", "audience": "vst-runner-service-v1",
        "signer_socket": "/unused/signer.sock", "repository_root": "/unused/repo",
        "worker_uid": 999, "worker_gid": 989, "max_output_bytes": 1024,
        "worker_exec_helper_head": "a" * 40,
        "worker_exec_helper_path": "/usr/local/libexec/vst-s4-worker-exec-" + "a" * 40,
    })()
    server.worker_exec_helper_identity = expected_identity
    server.supervisor = type("Supervisor", (), {
        "previous_receipt": lambda *_args: None,
    })()

    class FakeAuthority:
        def __init__(self, *_args, **_kwargs):
            self.reservation_confirmed = False
            self.completion_confirmed = False
            self.claim_confirmed = False
            self.no_execution_confirmed = False

    monkeypatch.setattr(runner_service, "ExecutionAuthority", FakeAuthority)
    monkeypatch.setattr(
        runner_service, "_verify_worker_exec_helper", lambda _config: changed_identity,
    )
    spawn_attempts = []

    def runner_boundary(**kwargs):
        assert kwargs["worker_exec_helper_path"] == server.config.worker_exec_helper_path
        assert kwargs["worker_exec_helper_head"] == server.config.worker_exec_helper_head
        kwargs["verify_worker_exec_helper"]()
        spawn_attempts.append("Popen")

    monkeypatch.setattr(runner, "run_manifest_commands", runner_boundary)

    with pytest.raises(contracts.ContractError, match="identity changed after service startup"):
        server._run_grant(grant, manifest, [], "generation-1")

    assert spawn_attempts == []


def test_dispatcher_obtains_supervisor_grant_before_runner_dispatch(monkeypatch):
    from tools.vst import runner_service

    grant = {"signature": "supervisor-signed-grant"}
    calls = []

    class FakeSupervisorClient:
        def __init__(self, path):
            calls.append(("supervisor", path))

        def issue_grant(self, **body):
            calls.append(("issue_grant", body))
            return grant

    def fake_dispatch(path, received_grant, *, artifact_paths, timeout_sec):
        calls.append(("runner", path, received_grant, artifact_paths, timeout_sec))
        return {"receipt": "complete"}

    monkeypatch.setattr(runner_service, "SupervisorClient", FakeSupervisorClient)
    monkeypatch.setattr(runner_service, "dispatch_manifest_run", fake_dispatch)
    result = dispatch_authorized_manifest_run(
        supervisor_socket="/run/vst-supervisor/supervisor.sock",
        runner_socket="/run/vst-runner/runner.sock",
        task_id="task-1", slot="tests", attempt=1, epoch=2, run_id="run-1",
        resolved_model="test-model", model_provenance_sha256=hashlib.sha256(b"model").hexdigest(),
        artifact_paths=["reports/test.txt"], timeout_sec=120.0,
    )

    assert result == {"receipt": "complete"}
    assert calls == [
        ("supervisor", "/run/vst-supervisor/supervisor.sock"),
        ("issue_grant", {
            "task_id": "task-1", "slot": "tests", "attempt": 1, "epoch": 2,
            "run_id": "run-1", "resolved_model": "test-model",
            "model_provenance_sha256": hashlib.sha256(b"model").hexdigest(),
        }),
        ("runner", "/run/vst-runner/runner.sock", grant, ["reports/test.txt"], 120.0),
    ]


def test_supervisor_claim_rpc_wraps_complete_receipt_in_execution_authority_shape():
    receipt = {"task_id": "task-1", "slot": "tests", "status": "PASS"}
    grant = {"grant_id": "grant-1"}

    class FakeSupervisor:
        def claim_runner_execution(self, received_grant):
            assert received_grant == grant
            return receipt

    server = object.__new__(AuthenticatedSupervisorAPI)
    server.supervisor = FakeSupervisor()

    result = server._dispatch("claim", {"grant": grant})

    assert result == {"state": "COMPLETE", "receipt": receipt}


def test_supervisor_claim_rpc_preserves_new_pending_claim_as_none():
    class FakeSupervisor:
        def claim_runner_execution(self, _received_grant):
            return None

    server = object.__new__(AuthenticatedSupervisorAPI)
    server.supervisor = FakeSupervisor()

    assert server._dispatch("claim", {"grant": {"grant_id": "grant-1"}}) is None


def _fake_execution_authority(
    grant, *, claim, claim_status, reserve, monkeypatch, terminalize_no_execution=None,
):
    from tools.vst.execution_grant import ExecutionAuthority

    import tools.vst.execution_grant as grant_module
    monkeypatch.setattr(grant_module.os, "name", "posix")
    monkeypatch.setattr(grant_module.os, "geteuid", lambda: 997, raising=False)

    authority = object.__new__(ExecutionAuthority)
    authority.grant = dict(grant)
    authority.daemon_uid = 997
    authority.service_generation = grant["service_generation"]
    authority._daemon_boundary_check = lambda: True
    authority._claim = claim
    authority._claim_status = claim_status
    authority._terminalize_no_execution = terminalize_no_execution or (
        lambda received, _reason: {
            "state": "NO_EXECUTION", "grant_id": received["grant_id"],
            "payload_sha256": hashlib.sha256(contracts.canonical_bytes(received)).hexdigest(),
            "service_generation": received["service_generation"],
        }
    )
    authority._reserve = reserve
    authority._complete = lambda _grant, _receipt: None
    authority._claimed = False
    authority._reserved = False
    authority._completed = False
    authority._no_execution_confirmed = False
    context = {
        key: grant[key] for key in (
            "manifest_sha256", "task_id", "slot", "attempt", "epoch", "run_id",
            "invocation_id", "request_id", "runner_id", "resolved_model",
            "model_provenance_sha256", "execution_deadline_sec", "service_generation",
        )
    }
    return authority, context


def test_lost_claim_reply_recovers_exact_pending_generation_then_reserves(monkeypatch):
    manifest, *_ = _authority_fixture()
    grant = _grant(manifest)
    calls = []

    def claim(received):
        calls.append(("claim", received))
        raise TimeoutError("claim reply lost after commit")

    def status(received):
        calls.append(("status", received))
        return {"state": "PENDING", "service_generation": "generation-1"}

    def reserve(received):
        calls.append(("reserve", received))
        return {
            "state": "EXECUTION_RESERVED", "grant_id": received["grant_id"],
            "payload_sha256": hashlib.sha256(contracts.canonical_bytes(received)).hexdigest(),
            "service_generation": received["service_generation"],
        }

    authority, context = _fake_execution_authority(
        grant, claim=claim, claim_status=status, reserve=reserve, monkeypatch=monkeypatch,
    )
    assert authority.authorize_and_claim(context) is None
    authority.reserve()

    assert authority._reserved is True
    assert calls == [(name, grant) for name in ("claim", "status", "reserve")]


def test_lost_reservation_reply_reports_reserved_but_never_launches(monkeypatch):
    from tools.vst.contracts import ContractError

    manifest, *_ = _authority_fixture()
    grant = _grant(manifest)
    launches = []
    status_calls = []

    authority, context = _fake_execution_authority(
        grant,
        claim=lambda _received: None,
        claim_status=lambda received: status_calls.append(received) or {
            "state": "EXECUTION_RESERVED", "service_generation": "generation-1",
        },
        reserve=lambda _received: (_ for _ in ()).throw(TimeoutError("reserve reply lost")),
        monkeypatch=monkeypatch,
    )
    assert authority.authorize_and_claim(context) is None

    def dispatch_after_reserve():
        authority.reserve()
        launches.append("child-started")

    with pytest.raises(ContractError, match="refusing to launch"):
        dispatch_after_reserve()
    assert status_calls == [grant]
    assert launches == []
    assert authority._reserved is False


@pytest.mark.parametrize("failure", ["claim_status", "reserve_status"])
def test_ambiguous_claim_or_reservation_status_is_fatal_and_never_launches(
    failure, monkeypatch,
):
    """Unknown durable authority state is fatal and cannot start a child."""
    from tools.vst.execution_grant import AmbiguousExecutionAuthorityError

    manifest, *_ = _authority_fixture()
    grant = _grant(manifest)
    child_launches = []
    status_calls = []

    def claim_status(received):
        status_calls.append(received)
        if failure == "claim_status" or failure == "reserve_status":
            raise TimeoutError("authority status unavailable")
        return {"state": "PENDING", "service_generation": "generation-1"}

    def claim(_received):
        if failure == "claim_status":
            raise TimeoutError("claim reply lost")
        return None

    authority, context = _fake_execution_authority(
        grant, claim=claim, claim_status=claim_status,
        reserve=lambda _received: (_ for _ in ()).throw(TimeoutError("reserve reply lost")),
        monkeypatch=monkeypatch,
    )
    with pytest.raises(AmbiguousExecutionAuthorityError):
        authority.authorize_and_claim(context)
        authority.reserve()
    assert child_launches == []
    assert len(status_calls) == 1


def test_exact_current_generation_not_found_is_nonfatal_refusal(monkeypatch):
    from tools.vst.contracts import ContractError

    manifest, *_ = _authority_fixture()
    grant = _grant(manifest)
    launches = []
    authority, context = _fake_execution_authority(
        grant, claim=lambda _received: (_ for _ in ()).throw(TimeoutError("claim reply lost")),
        claim_status=lambda _received: {
            "state": "NOT_FOUND", "service_generation": "generation-1",
        },
        reserve=lambda _received: None, monkeypatch=monkeypatch,
    )
    with pytest.raises(ContractError, match="not found; refusing to launch"):
        authority.authorize_and_claim(context)
        launches.append("child-started")
    assert launches == []
    assert authority._claimed is False


def test_ordinary_invalid_authority_context_is_nonfatal_and_never_launches(monkeypatch):
    from tools.vst.contracts import ContractError

    manifest, *_ = _authority_fixture()
    grant = _grant(manifest)
    launches = []
    authority, _context = _fake_execution_authority(
        grant, claim=lambda _received: None, claim_status=lambda _received: None,
        reserve=lambda _received: None, monkeypatch=monkeypatch,
    )
    with pytest.raises(ContractError, match="context does not match"):
        authority.authorize_and_claim({})
        launches.append("child-started")
    assert launches == []
    assert authority._claimed is False


@pytest.mark.parametrize("failure", ["stale_generation", "expired_grant", "lease_epoch"])
def test_store_reservation_fails_for_stale_expired_or_epoch_fenced_authority(failure):
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(manifest, clock)
    grant = _grant(manifest, now=clock())
    if failure == "expired_grant":
        grant["claim_expires_at"] = clock() + 5
        grant["expires_at"] = clock() + 10
    try:
        assert store.claim_runner_execution(
            grant, active_service_generation="generation-1",
        ) is None
        if failure == "stale_generation":
            generation = "generation-2"
        elif failure == "expired_grant":
            clock.advance(11)
            generation = "generation-1"
        else:
            clock.advance(1801)
            assert store.acquire_epoch(manifest["story_id"], "replacement-owner", ttl_sec=1800) == 3
            generation = "generation-1"

        with pytest.raises(StoreError):
            store.reserve_runner_execution(grant, active_service_generation=generation)
    finally:
        store.close()


def test_store_reservation_is_one_time():
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(manifest, clock)
    grant = _grant(manifest, now=clock())
    try:
        store.claim_runner_execution(grant, active_service_generation="generation-1")
        first = store.reserve_runner_execution(grant, active_service_generation="generation-1")
        assert first["state"] == "EXECUTION_RESERVED"
        with pytest.raises(StoreError, match="unreserved PENDING"):
            store.reserve_runner_execution(grant, active_service_generation="generation-1")
    finally:
        store.close()


@pytest.mark.parametrize("predecessor_state", ["PENDING", "EXECUTION_RESERVED"])
def test_new_generation_marks_predecessor_claim_indeterminate(predecessor_state):
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(manifest, clock)
    grant = _grant(manifest, now=clock())
    try:
        store.claim_runner_execution(grant, active_service_generation="generation-1")
        if predecessor_state == "EXECUTION_RESERVED":
            store.reserve_runner_execution(grant, active_service_generation="generation-1")

        assert store.mark_pending_runner_executions_indeterminate(
            current_service_generation="generation-2",
        ) == 1
        status = store.runner_execution_claim_status(
            grant, active_service_generation="generation-1",
        )
        assert status == {
            "state": "INDETERMINATE", "service_generation": "generation-1",
        }
    finally:
        store.close()


@pytest.mark.parametrize(
    "outcome",
    [
        None,
        "EFFECTS_UNRESOLVED",
        "RECONCILIATION_REJECTED",
    ],
)
def test_reserved_or_unsafe_reconciled_predecessor_blocks_every_successor_gate(
    outcome,
):
    store, manifest, clock, grant, predecessor_state = _make_indeterminate_predecessor()
    try:
        if outcome is not None:
            record = _execution_resolution(
                grant, predecessor_state=predecessor_state, outcome=outcome,
                resolution_id=f"resolution-{outcome.lower()}",
            )
            result = store.reconcile_runner_execution(record)
            assert result["continuation_allowed"] is False
        _assert_successor_gates_blocked(store, manifest, clock)
    finally:
        store.close()


def test_execution_reserved_predecessor_blocks_successor_gates_before_recovery():
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(manifest, clock)
    grant = _grant(manifest, now=clock())
    try:
        assert store.claim_runner_execution(grant, active_service_generation="generation-1") is None
        store.reserve_runner_execution(grant, active_service_generation="generation-1")
        _assert_successor_gates_blocked(store, manifest, clock)
    finally:
        store.close()


def test_effects_resolved_operator_record_allows_only_a_separately_authorized_successor():
    store, manifest, clock, grant, predecessor_state = _make_indeterminate_predecessor(
        story_ttl_sec=3600,
    )
    try:
        resolution = _execution_resolution(
            grant, predecessor_state=predecessor_state, outcome="EFFECTS_RESOLVED",
            resolution_id="effects-resolved-predecessor-1",
        )
        assert store.reconcile_runner_execution(resolution) == {
            "grant_id": grant["grant_id"], "state": "RECONCILED",
            "outcome": "EFFECTS_RESOLVED", "continuation_allowed": True,
        }
        clock.advance(1201)
        store.supervisor_reap_and_mark(SUPERVISOR_KEY, "store-test-supervisor")
        assert store.acquire_lease(
            manifest["task_id"], manifest["story_id"], "runner-1", 2, 2, 1200,
            supervisor_key=SUPERVISOR_KEY,
        ) is None
        store.ensure_preflight_consumed("run-2", "nonce-2", "c" * 64, "d" * 64)
        basis = store.execution_grant_basis(
            manifest["task_id"], "tests", 2, 2, "run-2",
            active_service_generation="generation-2",
        )
        successor = _successor_grant(manifest, basis, now=clock())
        assert store.claim_runner_execution(
            successor, active_service_generation="generation-2",
        ) is None
        assert store.verify_pending_runner_execution(
            successor, active_service_generation="generation-2",
        ) is True
    finally:
        store.close()


def test_pre_spawn_pending_predecessor_can_retry_only_after_normal_lease_rules():
    store, manifest, clock, grant, predecessor_state = _make_indeterminate_predecessor(
        reserve=False, story_ttl_sec=3600,
    )
    try:
        assert predecessor_state == "PENDING"
        clock.advance(1201)
        store.supervisor_reap_and_mark(SUPERVISOR_KEY, "store-test-supervisor")
        store.acquire_lease(
            manifest["task_id"], manifest["story_id"], "runner-1", 2, 2, 1200,
            supervisor_key=SUPERVISOR_KEY,
        )
        store.ensure_preflight_consumed("run-2", "nonce-2", "c" * 64, "d" * 64)
        basis = store.execution_grant_basis(
            manifest["task_id"], "tests", 2, 2, "run-2",
            active_service_generation="generation-2",
        )
        successor = _successor_grant(manifest, basis, now=clock())
        assert store.claim_runner_execution(
            successor, active_service_generation="generation-2",
        ) is None
        assert store.runner_execution_claim_status(
            successor, active_service_generation="generation-2",
        )["state"] == "PENDING"
    finally:
        store.close()


@pytest.mark.parametrize("mutation", ["tampered_signature", "mismatched_binding", "bad_hmac", "invalid_outcome"])
def test_execution_reconciliation_rejects_tampered_mismatched_or_invalid_records(mutation):
    store, manifest, clock, grant, predecessor_state = _make_indeterminate_predecessor()
    try:
        record = _execution_resolution(
            grant, predecessor_state=predecessor_state, outcome="EFFECTS_RESOLVED",
            resolution_id=f"invalid-{mutation}",
        )
        if mutation == "tampered_signature":
            record["attempt"] += 1
        elif mutation == "mismatched_binding":
            body = {key: value for key, value in record.items() if key != "signature"}
            body["request_id"] = "different-request"
            record = {**body, "signature": sign(body, EXECUTION_RESOLUTION_KEY, RUNNER_EXECUTION_RESOLUTION_LABEL)}
        elif mutation == "bad_hmac":
            body = {key: value for key, value in record.items() if key != "signature"}
            record["signature"] = sign(body, b"wrong-resolution-key-0123456789-abcdef", RUNNER_EXECUTION_RESOLUTION_LABEL)
        else:
            record["outcome"] = "UNKNOWN_OUTCOME"
            body = {key: value for key, value in record.items() if key != "signature"}
            record["signature"] = sign(body, EXECUTION_RESOLUTION_KEY, RUNNER_EXECUTION_RESOLUTION_LABEL)
        with pytest.raises(StoreError, match="signature or exact-grant binding is invalid"):
            store.reconcile_runner_execution(record)
        assert store.runner_execution_claim_status(
            grant, active_service_generation="generation-1",
        )["state"] == "INDETERMINATE"
        _assert_successor_gates_blocked(store, manifest, clock)
    finally:
        store.close()


def test_execution_reconciliation_rejects_resolution_id_reused_for_another_grant():
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, execution_resolution_key=EXECUTION_RESOLUTION_KEY, slots=2,
    )
    first = _grant(manifest, now=clock())
    try:
        assert store.claim_runner_execution(first, active_service_generation="generation-1") is None
        store.reserve_runner_execution(first, active_service_generation="generation-1")

        second_manifest = copy.deepcopy(manifest)
        second_manifest["task_id"] = "T2"
        second_manifest["story_id"] = "story-2"
        store.open_story(
            second_manifest["story_id"], second_manifest["project_id"], second_manifest["phase"],
        )
        epoch = store.acquire_epoch(second_manifest["story_id"], "test-owner-2", ttl_sec=1800)
        assert epoch == 2
        store.register_task(second_manifest)
        store.acquire_lease(
            second_manifest["task_id"], second_manifest["story_id"], "runner-2", epoch, 1, 1200,
            supervisor_key=SUPERVISOR_KEY,
        )
        store.ensure_preflight_consumed("run-2", "nonce-2", "c" * 64, "d" * 64)
        second = _grant(second_manifest, now=clock())
        second.update({
            "grant_id": "grant-second-task", "request_id": "request-second-task",
            "invocation_id": "invocation-second-task", "runner_id": "runner-2",
            "run_id": "run-2",
        })
        assert store.claim_runner_execution(second, active_service_generation="generation-1") is None
        store.reserve_runner_execution(second, active_service_generation="generation-1")
        assert store.mark_pending_runner_executions_indeterminate(
            current_service_generation="generation-2",
        ) == 2

        store.reconcile_runner_execution(_execution_resolution(
            first, predecessor_state="EXECUTION_RESERVED", outcome="EFFECTS_RESOLVED",
            resolution_id="shared-resolution-id",
        ))
        with pytest.raises(StoreError, match="resolution id is already used"):
            store.reconcile_runner_execution(_execution_resolution(
                second, predecessor_state="EXECUTION_RESERVED", outcome="EFFECTS_RESOLVED",
                resolution_id="shared-resolution-id",
            ))
    finally:
        store.close()


def test_authority_changed_before_complete_reconciliation_requires_exact_reserved_predecessor():
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, execution_resolution_key=EXECUTION_RESOLUTION_KEY,
    )
    grant = _grant(manifest, now=clock())
    try:
        assert store.claim_runner_execution(grant, active_service_generation="generation-1") is None
        store.reserve_runner_execution(grant, active_service_generation="generation-1")
        # Expiry changes authority before completion and writes the special
        # fail-closed indeterminate reason from EXECUTION_RESERVED.
        clock.advance(1201)
        with pytest.raises(StoreError, match="authority changed before completion"):
            store.complete_runner_execution(
                grant, _receipt_for_grant(grant, manifest),
                active_service_generation="generation-1",
            )
        state = store.runner_execution_claim_status(
            grant, active_service_generation="generation-1",
        )
        assert state == {"state": "INDETERMINATE", "service_generation": "generation-1"}

        for predecessor_state, outcome in (
            (None, "EFFECTS_RESOLVED"),
            ("PENDING", "EFFECTS_RESOLVED"),
            ("EXECUTION_RESERVED", "NO_EXECUTION_PROVEN"),
        ):
            record = _execution_resolution(
                grant, predecessor_state="EXECUTION_RESERVED", outcome=outcome,
                resolution_id=f"authority-change-{outcome}-{predecessor_state}",
            )
            record["predecessor_state"] = predecessor_state
            body = {key: value for key, value in record.items() if key != "signature"}
            record["signature"] = sign(body, EXECUTION_RESOLUTION_KEY, RUNNER_EXECUTION_RESOLUTION_LABEL)
            with pytest.raises(StoreError, match="signature or exact-grant binding is invalid"):
                store.reconcile_runner_execution(record)

        accepted = _execution_resolution(
            grant, predecessor_state="EXECUTION_RESERVED", outcome="EFFECTS_RESOLVED",
            resolution_id="authority-change-effects-resolved",
        )
        result = store.reconcile_runner_execution(accepted)
        assert result["continuation_allowed"] is True
        assert result["outcome"] == "EFFECTS_RESOLVED"
    finally:
        store.close()


def test_store_refuses_preflight_consumption_before_verified_startup_history():
    store = Store(":memory:", FakeClock(1000), event_key=EVENT_KEY)
    try:
        assert store.reconciliation_complete
        store._reconciliation_complete = False
        with pytest.raises(StoreError, match="verified Store history"):
            store.ensure_preflight_consumed("run-guard", "nonce-guard", "a" * 64, "b" * 64)
        assert store._conn.execute("SELECT COUNT(*) FROM supervisor_probes").fetchone()[0] == 0
    finally:
        store.close()


class _FragmentedReply:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def recv(self, _size):
        return self.chunks.pop(0) if self.chunks else b""


def test_signer_client_reads_fragmented_json_reply_to_eof():
    payload = b'{"signature":"' + (b"a" * 64) + b'"}'
    response = _recv_signer_response(_FragmentedReply([payload[:3], payload[3:11], payload[11:]]))
    assert response == {"signature": "a" * 64}


@pytest.mark.parametrize("chunks", [
    [b""],
    [b"not-json", b""],
    [b"[]", b""],
    [b"{" + (b" " * MAX_SIGNER_RESPONSE_BYTES), b""],
])
def test_signer_client_rejects_empty_malformed_non_object_or_oversized_reply(chunks):
    from tools.vst.contracts import ContractError

    with pytest.raises(ContractError):
        _recv_signer_response(_FragmentedReply(chunks))


def test_signer_server_bounds_request_and_tolerates_disconnected_client_reply(monkeypatch):
    import json
    import struct
    import tools.vst.signer as signer_module

    monkeypatch.setattr(signer_module.socket, "SO_PEERCRED", 1, raising=False)

    class FakeConnection:
        def __init__(self, payload, *, disconnect_reply=False):
            self.chunks = [payload, b""]
            self.disconnect_reply = disconnect_reply
            self.timeout = None

        def settimeout(self, value):
            self.timeout = value

        def getsockopt(self, _level, _option, _size):
            return struct.pack("3i", 101, 4242, 4242)

        def recv(self, _size):
            return self.chunks.pop(0) if self.chunks else b""

        def sendall(self, response):
            if self.disconnect_reply:
                raise BrokenPipeError("peer closed before response")
            self.response = response

    server = object.__new__(AuthenticatedSigner)
    server.runner_uid = 4242
    server.runner_gid = None
    server.require_pinned_daemon = False

    oversized = FakeConnection(b"x" * (MAX_REQUEST_BYTES + 1))
    server._handle(oversized)
    assert oversized.timeout == 10.0
    assert json.loads(oversized.response)["error"] == "invalid_request"

    disconnected = FakeConnection(b"not-json", disconnect_reply=True)
    server._handle(disconnected)
    assert disconnected.timeout == 10.0
