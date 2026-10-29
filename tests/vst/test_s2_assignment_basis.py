"""Synthetic Store contract tests for the S2 read-only assignment-basis candidate.

These fixtures model an operation journal row that a future authenticated writer
would persist. They are not evidence of a production writer, key, peer, or policy.
"""
from __future__ import annotations

import copy
import hashlib
import time
from datetime import datetime, timezone

import pytest

from tools.vst import contracts
from tools.vst.assignment_basis import (
    OPERATION,
    POLICY_SCHEMA,
    assignment_operation_id,
    validate_policy,
)
from tools.vst.store import GENESIS_HASH, Store, StoreError
from tools.vst.supervisor import Supervisor
from tools.vst.contracts import ContractError
from tests.vst.e1e4_helpers import EVENT_KEY, SUPERVISOR_KEY, manifest as base_manifest


REQUEST_SCHEMA = "VST_S2_ASSIGNMENT_BOOTSTRAP_REQUEST_V1"
GENERATION = "synthetic-generation-1"
RUN_ID = "synthetic-run-1"
PROBE_SHA256 = "c" * 64


def _policy(manifest: dict) -> dict:
    now = int(time.time())
    return {
        "schema": POLICY_SCHEMA,
        "policy_id": "synthetic-policy-1",
        "repository": "Virtual_scrum_team",
        "sprint_id": "39b7cc253f5d",
        "source_head": "a" * 40,
        "manifest_sha256": "b" * 64,
        "owner_principal": "Codex",
        "allowed_assignments": [{
            "story_id": manifest["story_id"],
            "task_id": manifest["task_id"],
            "project_id": manifest["project_id"],
            "phase": manifest["phase"],
            "task_manifest_sha256": contracts.manifest_sha256(manifest),
            "test_run_slots": ["tests"],
        }],
        "bootstrap_peer": {
            "role": "assignment_bootstrap", "uid": 980, "gid": 982,
            "cgroup": "/system.slice/vst-assignment-bootstrap.service",
        },
        "issuer_peer": {
            "role": "delegated_issuer", "uid": 981, "gid": 983,
            "cgroup": "/system.slice/vst-delegated-issuer.service",
        },
        "allowed_bootstrap_operations": ["open_story", "register_task", "acquire_epoch", "acquire_lease"],
        "maximum_handoff_ttl_seconds": 300,
        "runner_id": "runner-1",
        "owner_ttl_seconds": 1800,
        "lease_ttl_seconds": 1200,
        "valid_from_utc": datetime.fromtimestamp(now - 60, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at_utc": datetime.fromtimestamp(now + 3600, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "revocation_id": "synthetic-revocation-1",
    }


def _readiness(manifest: dict, *, store_mutation: str | None = None,
               journal_mutation: str | None = None, runner_id: str = "runner-1",
               supervisor_run_id: str | None = RUN_ID,
               handoff_generation: str = GENERATION):
    """Create disposable live Store state and a synthetic completed handoff row."""
    now = time.time()
    manifest = copy.deepcopy(manifest)
    manifest["task_id"] = "T-assignment-basis"
    manifest["story_id"] = "story-assignment-basis"
    manifest["required_receipts"] = [
        {"slot": "tests", "receipt_type": "TestRun"},
        {"slot": "review", "receipt_type": "IndependentReview"},
    ]
    # Rebuild derived manifest lists after replacing the receipt set.
    manifest = base_manifest(
        task_id=manifest["task_id"], story_id=manifest["story_id"],
        required_receipts=manifest["required_receipts"],
    )
    policy = _policy(manifest)
    policy_copy, policy_sha256 = validate_policy(policy)
    store = Store(":memory:", clock=lambda: now, event_key=EVENT_KEY)
    store.init_slots(1)
    store.open_story(manifest["story_id"], manifest["project_id"], manifest["phase"])
    epoch = store.acquire_epoch(manifest["story_id"], "Codex", ttl_sec=1800)
    store.register_task(manifest)
    store.acquire_lease(
        manifest["task_id"], manifest["story_id"], runner_id, epoch, 1, 1200,
        supervisor_key=SUPERVISOR_KEY,
    )
    store.ensure_preflight_consumed(RUN_ID, "synthetic-nonce-1", "d" * 64, PROBE_SHA256)

    request = {
        "schema": REQUEST_SCHEMA,
        "request_id": "0123456789abcdef0123456789abcdef",
        "story_id": manifest["story_id"],
        "task_id": manifest["task_id"],
        "task_manifest": manifest,
        "slot": "tests",
        "attempt": 1,
        "run_id": RUN_ID,
    }
    operation_id = assignment_operation_id(request, policy_sha256=policy_sha256)
    lease_id = int(store._conn.execute(
        "SELECT lease_id FROM leases WHERE task_id = ? AND attempt = 1", (manifest["task_id"],),
    ).fetchone()[0])
    issued = datetime.fromtimestamp(now, timezone.utc).replace(microsecond=0)
    handoff = {
        "schema": OPERATION,
        "assignment_operation_id": operation_id,
        "policy_id": policy_copy["policy_id"],
        "policy_sha256": policy_sha256,
        "repository": policy_copy["repository"],
        "sprint_id": policy_copy["sprint_id"],
        "source_head": policy_copy["source_head"],
        "manifest_sha256": policy_copy["manifest_sha256"],
        "bootstrap_peer": copy.deepcopy(policy_copy["bootstrap_peer"]),
        "assignment_principal": "Codex",
        "bootstrap_request": copy.deepcopy(request),
        "task_id": manifest["task_id"],
        "story_id": manifest["story_id"],
        "project_id": manifest["project_id"],
        "phase": manifest["phase"],
        "task_manifest_sha256": contracts.manifest_sha256(manifest),
        "slot": "tests",
        "attempt": 1,
        "epoch": epoch,
        "lease_id": lease_id,
        "runner_id": runner_id,
        "run_id": RUN_ID,
        "service_generation": handoff_generation,
        "probe_sha256": PROBE_SHA256,
        "issued_at_utc": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at_utc": datetime.fromtimestamp(now + 120, timezone.utc).replace(
            microsecond=0,
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if store_mutation == "stale_epoch":
        handoff["epoch"] += 1
    elif store_mutation == "stale_lease":
        handoff["lease_id"] += 1
    elif store_mutation == "missing_probe":
        handoff["run_id"] = "absent-probe-run"
        handoff["bootstrap_request"]["run_id"] = handoff["run_id"]
        request = copy.deepcopy(handoff["bootstrap_request"])
        handoff["assignment_operation_id"] = assignment_operation_id(
            handoff["bootstrap_request"], policy_sha256=policy_sha256,
        )
        operation_id = handoff["assignment_operation_id"]
    elif store_mutation == "wrong_runner":
        handoff["runner_id"] = "runner-other"
    if journal_mutation == "wrong_task_manifest_digest":
        handoff["task_manifest_sha256"] = "f" * 64
    elif journal_mutation == "wrong_policy_digest":
        handoff["policy_sha256"] = "f" * 64
    elif journal_mutation == "wrong_assignment_principal":
        handoff["assignment_principal"] = "caller-selected"
    elif journal_mutation == "changed_bootstrap_manifest":
        handoff["bootstrap_request"]["task_manifest"]["scope"] = ["other.py"]
    elif journal_mutation == "unknown_handoff_field":
        handoff["unreviewed"] = "must not be stripped"
    body = {key: value for key, value in handoff.items() if key != "handoff_sha256"}
    handoff["handoff_sha256"] = hashlib.sha256(contracts.canonical_bytes(body)).hexdigest()
    payload = {
        "request": copy.deepcopy(handoff["bootstrap_request"]),
        "bootstrap_peer": policy_copy["bootstrap_peer"],
        "policy_sha256": policy_sha256,
    }
    if journal_mutation == "wrong_payload":
        payload["request"] = {**request, "request_id": "f" * 32}

    # This is only a synthetic future-writer journal fixture, not an authenticated
    # production assignment or proof that a production writer currently exists.
    if journal_mutation in {"wrong_actor", "duplicate_event"}:
        result_text = contracts.canonical_bytes(handoff).decode("utf-8")
        payload_sha = hashlib.sha256(contracts.canonical_bytes(payload)).hexdigest()
        with store._tx() as conn:
            conn.execute(
                "INSERT INTO supervisor_operations(operation_key, operation, payload_sha256, result) "
                "VALUES (?, ?, ?, ?)",
                (operation_id, OPERATION, payload_sha, result_text),
            )
            event_actor = "unauthenticated" if journal_mutation == "wrong_actor" else "supervisor"
            event = {
                "event": "SUPERVISOR_OPERATION", "operation": OPERATION,
                "payload_sha256": payload_sha,
                "result_sha256": hashlib.sha256(result_text.encode("utf-8")).hexdigest(),
            }
            store._record_event_locked(conn, operation_id, event_actor, "NOTE", event)
            if journal_mutation == "duplicate_event":
                store._record_event_locked(conn, operation_id, "supervisor", "NOTE", event)
    else:
        store.execute_idempotent(operation_id, OPERATION, payload, lambda _conn: handoff)
    supervisor = Supervisor(
        store, operation_backend=object(), assignment_policy=policy_copy, run_id=supervisor_run_id,
        assignment_policy_provider=lambda: policy_copy,
    )
    # Assignment-basis needs the active generation, whereas execution-grant
    # signer configuration is intentionally absent from this source-only fixture.
    supervisor.service_generation_provider = lambda: GENERATION
    return store, supervisor, policy_copy, policy_sha256, operation_id, handoff


def _snapshot(store: Store) -> tuple:
    with store._read_tx() as conn:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        )]
        return tuple(
            (table, tuple(tuple(row) for row in conn.execute(f'SELECT * FROM "{table}"')))
            for table in tables
        )


def test_assignment_basis_reads_verified_handoff_and_live_basis_without_store_mutation(monkeypatch):
    manifest = base_manifest()
    store, supervisor, _policy_obj, _policy_sha, operation_id, handoff = _readiness(manifest)
    observed_connections = []
    original = store._execution_grant_basis_locked

    def observe_locked(conn, *args, **kwargs):
        assert conn.in_transaction
        observed_connections.append(conn)
        return original(conn, *args, **kwargs)

    monkeypatch.setattr(store, "_execution_grant_basis_locked", observe_locked)
    before = _snapshot(store)
    try:
        response = supervisor.assignment_basis(assignment_operation_id=operation_id)
        assert response == {
            "schema": "VST_S2_ASSIGNMENT_BASIS_RESPONSE_V1",
            "assignment_operation_id": operation_id,
            "handoff_sha256": handoff["handoff_sha256"],
            "policy_id": "synthetic-policy-1", "policy_sha256": supervisor.assignment_policy_sha256,
            "repository": "Virtual_scrum_team", "sprint_id": "39b7cc253f5d",
            "source_head": "a" * 40, "manifest_sha256": "b" * 64,
            "task_id": handoff["task_id"], "story_id": handoff["story_id"],
            "task_manifest_sha256": handoff["task_manifest_sha256"], "slot": "tests",
            "attempt": 1, "epoch": handoff["epoch"], "lease_id": handoff["lease_id"],
            "runner_id": "runner-1", "principal": "Codex", "run_id": RUN_ID,
            "probe_sha256": PROBE_SHA256,
            "authority_expires_at_utc": handoff["expires_at_utc"],
            "service_generation": GENERATION,
        }
        assert len(observed_connections) == 1
        assert _snapshot(store) == before
    finally:
        store.close()


def test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment():
    store, _supervisor, policy, policy_sha, operation_id, stored_handoff = _readiness(base_manifest())
    try:
        snapshot = store.authenticated_assignment_basis(
            operation_id, policy=policy, policy_sha256=policy_sha,
            active_service_generation=GENERATION, expected_run_id=RUN_ID,
        )
        assert snapshot["handoff"] == stored_handoff
        assert "payload_sha256" not in snapshot["handoff"]
        persisted = store._conn.execute(
            "SELECT result FROM supervisor_operations WHERE operation_key=?", (operation_id,),
        ).fetchone()["result"]
        assert contracts.canonical_bytes(snapshot["handoff"]).decode("utf-8") == persisted
    finally:
        store.close()


def test_verified_database_history_preserves_each_event_prefix_without_writing():
    store, _supervisor, _policy_obj, _policy_sha, _operation_id, _handoff = _readiness(base_manifest())
    try:
        before = _snapshot(store)
        history = store._verified_database_history()
        event_count = store._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert history[0] == (0, GENESIS_HASH)
        assert len(history) == event_count + 1
        assert history[-1] == store._verified_database_head()
        assert _snapshot(store) == before
    finally:
        store.close()


@pytest.mark.parametrize("mutation", ["stale_epoch", "stale_lease", "missing_probe", "wrong_runner"])
def test_assignment_basis_refuses_handoff_not_bound_to_live_store_snapshot(mutation):
    store, supervisor, _policy_obj, _policy_sha, operation_id, _handoff = _readiness(
        base_manifest(), store_mutation=mutation,
    )
    try:
        with pytest.raises((StoreError, ContractError)):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
    finally:
        store.close()


def test_assignment_basis_refuses_operation_row_with_noncanonical_payload_binding():
    store, supervisor, _policy_obj, _policy_sha, operation_id, _handoff = _readiness(
        base_manifest(), journal_mutation="wrong_payload",
    )
    try:
        with pytest.raises(StoreError, match="payload digest"):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
    finally:
        store.close()


@pytest.mark.parametrize("journal_mutation", [
    "wrong_task_manifest_digest", "wrong_policy_digest", "wrong_assignment_principal",
    "changed_bootstrap_manifest", "unknown_handoff_field",
])
def test_assignment_basis_refuses_handoff_that_breaks_exact_source_bindings(journal_mutation):
    store, supervisor, _policy_obj, _policy_sha, operation_id, _handoff = _readiness(
        base_manifest(), journal_mutation=journal_mutation,
    )
    try:
        with pytest.raises((StoreError, ContractError)):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
    finally:
        store.close()


@pytest.mark.parametrize("journal_mutation", ["wrong_actor", "duplicate_event"])
def test_assignment_basis_refuses_untrusted_or_ambiguous_journal_event(journal_mutation):
    store, supervisor, _policy_obj, _policy_sha, operation_id, _handoff = _readiness(
        base_manifest(), journal_mutation=journal_mutation,
    )
    try:
        with pytest.raises(StoreError, match="event identity"):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
    finally:
        store.close()


@pytest.mark.parametrize("operation_id", ["0" * 64, "not-an-operation-id"])
def test_assignment_basis_refuses_unknown_or_malformed_operation_id(operation_id):
    store, supervisor, _policy_obj, _policy_sha, _known_id, _handoff = _readiness(base_manifest())
    try:
        with pytest.raises((StoreError, ContractError)):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
    finally:
        store.close()


def test_assignment_basis_refuses_legacy_operation_without_authenticated_handoff():
    store, supervisor, _policy_obj, _policy_sha, _operation_id, _handoff = _readiness(base_manifest())
    try:
        legacy_id = "e" * 64
        store.execute_idempotent(legacy_id, "legacy_assignment", {"task": "T1"}, lambda _conn: {})
        with pytest.raises(StoreError, match="not found"):
            supervisor.assignment_basis(assignment_operation_id=legacy_id)
    finally:
        store.close()


def test_assignment_basis_refuses_changed_or_missing_trusted_policy_provider():
    store, supervisor, policy, _policy_sha, operation_id, _handoff = _readiness(base_manifest())
    try:
        changed = copy.deepcopy(policy)
        changed["revocation_id"] = "synthetic-revoked-policy"
        supervisor.assignment_policy_provider = lambda: changed
        with pytest.raises(StoreError, match="changed or was revoked"):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
        supervisor.assignment_policy_provider = lambda: (_ for _ in ()).throw(OSError("policy absent"))
        with pytest.raises(StoreError, match="unreadable or invalid"):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
        supervisor.assignment_policy_provider = lambda: policy
        supervisor.assignment_policy = None
        with pytest.raises(StoreError, match="not provisioned"):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
        supervisor.assignment_policy = policy
        supervisor.service_generation_provider = None
        with pytest.raises(StoreError, match="not provisioned"):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
    finally:
        store.close()


def test_assignment_basis_refuses_handoff_from_previous_service_generation():
    store, supervisor, _policy_obj, _policy_sha, operation_id, _handoff = _readiness(
        base_manifest(), handoff_generation="synthetic-generation-previous",
    )
    try:
        supervisor.service_generation_provider = lambda: "synthetic-generation-after-restart"
        with pytest.raises(StoreError, match="stale Supervisor run or generation"):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
    finally:
        store.close()


def test_assignment_basis_rejects_consumed_handoff_from_previous_supervisor_run():
    store, supervisor, _policy_obj, _policy_sha, operation_id, _handoff = _readiness(
        base_manifest(), supervisor_run_id="synthetic-run-current",
    )
    try:
        with pytest.raises(StoreError, match="stale Supervisor run or generation"):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
    finally:
        store.close()


def test_assignment_basis_refuses_expired_root_policy(monkeypatch):
    from tools.vst import supervisor as supervisor_module

    store, supervisor, policy, _policy_sha, operation_id, _handoff = _readiness(base_manifest())
    expiry = datetime.strptime(policy["expires_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc,
    )

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return expiry.replace(year=expiry.year + 1)

    monkeypatch.setattr(supervisor_module, "datetime", FrozenDateTime)
    try:
        with pytest.raises(StoreError, match="not currently valid"):
            supervisor.assignment_basis(assignment_operation_id=operation_id)
    finally:
        store.close()


def test_rpc_assignment_basis_rejects_wrong_role_and_caller_selected_fields():
    from tools.vst.supervisor_service import AuthenticatedSupervisorAPI, SupervisorPeer

    store, supervisor, _policy_obj, _policy_sha, operation_id, _handoff = _readiness(base_manifest())
    api = object.__new__(AuthenticatedSupervisorAPI)
    api.supervisor = supervisor
    dispatcher = SupervisorPeer("dispatcher", 1, 1, "/system.slice/dispatcher", frozenset({"issue_dispatch_grant"}))
    issuer = SupervisorPeer("delegated_issuer", 2, 2, "/system.slice/issuer", frozenset({"assignment_basis"}))
    try:
        with pytest.raises(ContractError, match="not authorized"):
            api._dispatch("assignment_basis", {"schema": "VST_S2_ASSIGNMENT_BASIS_REQUEST_V1",
                                                "assignment_operation_id": operation_id}, dispatcher)
        with pytest.raises(ContractError, match="closed schema"):
            api._dispatch("assignment_basis", {"schema": "VST_S2_ASSIGNMENT_BASIS_REQUEST_V1",
                                                "assignment_operation_id": operation_id,
                                                "task_id": "caller-selected"}, issuer)
        response = api._dispatch("assignment_basis", {
            "schema": "VST_S2_ASSIGNMENT_BASIS_REQUEST_V1",
            "assignment_operation_id": operation_id,
        }, issuer)
        assert response["assignment_operation_id"] == operation_id
    finally:
        store.close()
