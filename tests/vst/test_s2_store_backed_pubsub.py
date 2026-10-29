"""Focused acceptance tests for the S2 Store-backed dispatch pub/sub contract."""
from __future__ import annotations

import json
import os as host_os
import hashlib
import posixpath
import socket
import struct
from types import SimpleNamespace

import pytest

from tools.vst import contracts
from tools.vst.contracts import ContractError
from tools.vst.runner_service import dispatch_manifest_run
from tools.vst.store import Store, StoreBusyError, StoreError
from tools.vst.supervisor import Supervisor
from tools.vst.supervisor_service import (
    AuthenticatedSupervisorAPI, SupervisorPeer,
)
from tests.vst.e1e4_helpers import (
    EVENT_KEY, FakeClock, SUPERVISOR_KEY, KEY, manifest as base_manifest,
    receipt as signed_receipt,
)
from tests.vst.s2_dispatch_instruction_fixtures import DispatchInstructionKeyPair


REQUEST_ID = "a" * 32
GENERATION = "generation-s2-1"
AUDIENCE = "997:990:/system.slice/vst-dispatcher.service"


def _ready_dispatch_fixture(
    tmp_path, dispatch_instruction_keypair: DispatchInstructionKeyPair, *,
    model_provenance_digest="d" * 64, anchor_path: str | None = None,
):
    clock = FakeClock(1000)
    manifest = base_manifest(
        task_id="task-dispatch-1", story_id="story-dispatch-1", project_id="vst",
    )
    store = Store(
        str(tmp_path / "dispatch.db"), clock, event_key=EVENT_KEY,
        anchor_path=anchor_path,
    )
    store.init_slots(1)
    store.open_story(manifest["story_id"], manifest["project_id"], manifest["phase"])
    epoch = store.acquire_epoch(manifest["story_id"], "Codex", ttl_sec=3600)
    store.register_task(manifest)
    store.acquire_lease(
        manifest["task_id"], manifest["story_id"], "runner-1", epoch, 1, 1800,
        supervisor_key=SUPERVISOR_KEY,
    )
    store.ensure_preflight_consumed(
        "run-s2-1", "nonce-s2-1", "1" * 64, "2" * 64,
    )
    generation = {"value": GENERATION}
    supervisor = Supervisor(
        store,
        operation_backend=None,
        execution_grant_key_id="test-key",
        execution_grant_private_key_path="unused-test-private-key.pem",
        execution_grant_openssl_path="openssl",
        execution_grant_trust_keys={"test-key": "unused-test-public-key.pem"},
        dispatch_instruction_trust_keys=dispatch_instruction_keypair.trust_registry,
        dispatch_instruction_openssl_path=dispatch_instruction_keypair.openssl_path,
        service_generation_provider=lambda: generation["value"],
        model_provenance_verifier=lambda _model, _digest: True,
        model_provenance_digest_provider=lambda _model: model_provenance_digest,
    )
    body = {
        "task_id": manifest["task_id"],
        "slot": "tests",
        "attempt": 1,
        "epoch": epoch,
        "run_id": "run-s2-1",
        "request_id": REQUEST_ID,
    }
    return store, supervisor, manifest, epoch, generation, body, dispatch_instruction_keypair


def _submit(supervisor, body, dispatch_instruction_keypair, *, principal="Codex"):
    instruction = dispatch_instruction_keypair.sign(body)
    return supervisor.accept_dispatch_intent(principal=principal, instruction=instruction)


def _ack_body(result: dict) -> dict:
    return {
        "request_id": result["request_id"],
        "payload_digest": result["payload_digest"],
        "event_seq": result["event_seq"],
        "result_sha256": hashlib.sha256(contracts.canonical_bytes(result)).hexdigest(),
        "service_generation": result["service_generation"],
    }


def test_dispatch_outcome_pending_marker_shares_acceptance_transaction(
    tmp_path, dispatch_instruction_keypair, monkeypatch,
):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    original_append = store._append_control_event_locked

    def fail_pending(conn, kind, event_id, payload, *args, **kwargs):
        if kind == "DISPATCH_OWNER_OUTCOME_PENDING":
            raise StoreError("injected pending-marker write failure", kind="integrity")
        return original_append(conn, kind, event_id, payload, *args, **kwargs)

    monkeypatch.setattr(store, "_append_control_event_locked", fail_pending)
    try:
        with pytest.raises(StoreError, match="pending-marker"):
            _submit(supervisor, body, keypair)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 0
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation='dispatch_intent'",
        ).fetchone()[0] == 0
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE payload LIKE '%DISPATCH_OWNER_OUTCOME_PENDING%'",
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_pending_dispatch_allows_exact_replay_and_rejects_different_request_id(
    tmp_path, dispatch_instruction_keypair,
):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        accepted = _submit(supervisor, body, keypair)
        assert _submit(supervisor, body, keypair) == accepted
        replacement = {**body, "request_id": "b" * 32}
        with pytest.raises(StoreError) as raised:
            _submit(supervisor, replacement, keypair)
        assert raised.value.kind == "lifecycle"
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 1
    finally:
        store.close()


def test_dispatch_outcome_ack_is_exact_idempotent_and_conflicts_fail_closed(
    tmp_path, dispatch_instruction_keypair,
):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        accepted = _submit(supervisor, body, keypair)
        ack = _ack_body(accepted)
        assert supervisor.ack_dispatch_intent(principal="Codex", **ack) == ack
        assert supervisor.ack_dispatch_intent(principal="Codex", **ack) == ack
        conflicting = {**ack, "result_sha256": "f" * 64}
        with pytest.raises(StoreError) as raised:
            supervisor.ack_dispatch_intent(principal="Codex", **conflicting)
        assert raised.value.kind == "integrity"
        with pytest.raises(StoreError) as principal_mismatch:
            supervisor.ack_dispatch_intent(principal="OtherOwner", **ack)
        assert principal_mismatch.value.kind == "integrity"
        notes = [
            json.loads(row[0]) for row in store._conn.execute(
                "SELECT payload FROM events WHERE kind='NOTE' AND actor='supervisor' ORDER BY seq",
            ).fetchall()
        ]
        ack_notes = [
            note for note in notes
            if note.get("_vst_control_type") == "DISPATCH_OWNER_OUTCOME_ACKNOWLEDGED"
        ]
        assert len(ack_notes) == 1
        assert ack_notes[0]["principal"] == "Codex"
        assert {key: ack_notes[0][key] for key in ack} == ack
    finally:
        store.close()


@pytest.mark.parametrize("historical_status", ["expired", "revoked"])
def test_verified_replay_returns_original_result_for_expired_or_revoked_acceptance(
    tmp_path, dispatch_instruction_keypair, monkeypatch, historical_status,
):
    from datetime import datetime, timezone
    from tools.vst import dispatch_instruction as instruction_module

    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    if historical_status == "expired":
        instruction = keypair.sign(body, expires_at="2025-01-01T00:00:00Z")
        original_verify = instruction_module.verify_dispatch_instruction

        def verify_at_acceptance(*args, **kwargs):
            kwargs["now"] = datetime(2024, 1, 1, tzinfo=timezone.utc)
            return original_verify(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(instruction_module, "verify_dispatch_instruction", verify_at_acceptance)
            accepted = supervisor.accept_dispatch_intent(principal="Codex", instruction=instruction)
    else:
        instruction = keypair.sign(body)
        accepted = supervisor.accept_dispatch_intent(principal="Codex", instruction=instruction)
        # The key was trusted when the original event was accepted and is now revoked.
        supervisor.dispatch_instruction_trust_keys = {}

    before_anchor = store.event_anchor()
    before_operations = store._conn.execute(
        "SELECT COUNT(*) FROM supervisor_operations",
    ).fetchone()[0]
    before_events = store._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    try:
        assert store.replay_dispatch_outcome(principal="Codex", instruction=instruction) == accepted
        assert accepted["service_generation"] == GENERATION
        peer = SupervisorPeer(
            role="dispatch_owner", uid=1200, gid=1200,
            cgroup="/system.slice/vst-owner.service",
            operations=frozenset({
                "submit_dispatch_intent", "replay_dispatch_outcome", "ack_dispatch_intent",
            }),
            principal="Codex",
        )
        via_rpc = AuthenticatedSupervisorAPI._dispatch(
            SimpleNamespace(supervisor=supervisor), "replay_dispatch_outcome",
            {"instruction": instruction}, peer,
        )
        assert via_rpc == accepted
        assert store.event_anchor() == before_anchor
        assert store._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before_events
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations",
        ).fetchone()[0] == before_operations
    finally:
        store.close()


def test_replay_rejects_changed_principal_envelope_or_signature(
    tmp_path, dispatch_instruction_keypair,
):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    instruction = keypair.sign(body)
    accepted = supervisor.accept_dispatch_intent(principal="Codex", instruction=instruction)
    changed_envelope = keypair.sign({**body, "slot": "static"})
    changed_key_id = {**instruction, "key_id": "different-key"}
    first = "A" if instruction["signature"][0] != "A" else "B"
    changed_signature = {**instruction, "signature": first + instruction["signature"][1:]}
    try:
        assert store.replay_dispatch_outcome(principal="GPT-PM", instruction=instruction) is None
        assert store.replay_dispatch_outcome(principal="Codex", instruction=changed_envelope) is None
        assert store.replay_dispatch_outcome(principal="Codex", instruction=changed_key_id) is None
        assert store.replay_dispatch_outcome(principal="Codex", instruction=changed_signature) is None
        assert store.replay_dispatch_outcome(principal="Codex", instruction=instruction) == accepted
    finally:
        store.close()


def test_dispatch_owner_ack_rpc_is_restricted_to_authenticated_owner_role(
    tmp_path, dispatch_instruction_keypair,
):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        accepted = _submit(supervisor, body, keypair)
        ack = _ack_body(accepted)
        api = SimpleNamespace(supervisor=supervisor)
        dispatcher = SupervisorPeer(
            role="dispatcher", uid=1201, gid=1201,
            cgroup="/system.slice/vst-dispatcher.service",
            operations=frozenset({"replay_dispatch_outcome", "ack_dispatch_intent"}),
        )
        with pytest.raises(ContractError, match="not authorized"):
            AuthenticatedSupervisorAPI._dispatch(api, "ack_dispatch_intent", ack, dispatcher)
        instruction = keypair.sign(body)
        with pytest.raises(ContractError, match="not authorized"):
            AuthenticatedSupervisorAPI._dispatch(
                api, "replay_dispatch_outcome", {"instruction": instruction}, dispatcher,
            )
        owner = SupervisorPeer(
            role="dispatch_owner", uid=1200, gid=1200,
            cgroup="/system.slice/vst-owner.service",
            operations=frozenset({
                "submit_dispatch_intent", "replay_dispatch_outcome", "ack_dispatch_intent",
            }),
            principal="Codex",
        )
        assert AuthenticatedSupervisorAPI._dispatch(
            api, "replay_dispatch_outcome", {"instruction": instruction}, owner,
        ) == accepted
        with pytest.raises(ContractError, match="not authorized"):
            AuthenticatedSupervisorAPI._dispatch(
                api, "replay_dispatch_outcome",
                {"instruction": instruction, "principal": "GPT-PM"}, owner,
            )
        assert AuthenticatedSupervisorAPI._dispatch(api, "ack_dispatch_intent", ack, owner) == ack
    finally:
        store.close()


def test_relay_ack_failure_preserves_store_pending_barrier_after_forwarding(
    tmp_path, dispatch_instruction_keypair,
):
    from tools.vst import dispatch_owner_service as owner_service

    keypair = dispatch_instruction_keypair
    store, supervisor, _manifest, _epoch, _generation, body, _keypair = _ready_dispatch_fixture(
        tmp_path, keypair,
    )

    class Transport:
        def submit_dispatch_intent(self, **kwargs):
            return supervisor.accept_dispatch_intent(principal="Codex", **kwargs)

        def replay_dispatch_outcome(self, **kwargs):
            return supervisor.replay_dispatch_outcome(principal="Codex", **kwargs)

        def ack_dispatch_intent(self, **_kwargs):
            raise StoreError("injected acknowledgement RPC failure", kind="busy")

    config = owner_service.DispatchOwnerServiceConfig(
        principal="Codex", openssl_path=keypair.openssl_path,
        trust_registry=keypair.trust_registry,
    )
    relay = owner_service.DispatchOwnerService(config, supervisor=Transport())
    instruction = keypair.sign(body)
    payload = contracts.canonical_bytes({"instruction": instruction})
    header = struct.Struct("!I")
    server, client = socket.socketpair()
    try:
        client.sendall(header.pack(len(payload)) + payload)
        client.shutdown(socket.SHUT_WR)
        outcome_unknown = relay._handle(server)
        response_size = header.unpack(client.recv(header.size))[0]
        response_bytes = bytearray()
        while len(response_bytes) < response_size:
            chunk = client.recv(response_size - len(response_bytes))
            assert chunk
            response_bytes.extend(chunk)
        response = json.loads(response_bytes)
        assert response["ok"] is True
        assert outcome_unknown is True
        with store._read_tx() as conn:
            state, pending = store._dispatch_outcome_state_locked(conn)
        assert state == "PENDING"
        assert pending["request_id"] == body["request_id"]
    finally:
        server.close()
        client.close()
        store.close()


def test_replay_after_current_admission_refusal_acks_original_generation_without_retry(
    tmp_path, dispatch_instruction_keypair,
):
    from tools.vst import dispatch_owner_service as owner_service

    keypair = dispatch_instruction_keypair
    store, supervisor, _manifest, _epoch, _generation, body, _keypair = _ready_dispatch_fixture(
        tmp_path, keypair,
    )
    accepted = _submit(supervisor, body, keypair)

    class Transport:
        def __init__(self):
            self.submit_calls = []
            self.replay_calls = []
            self.ack_calls = []

        def submit_dispatch_intent(self, **kwargs):
            self.submit_calls.append(kwargs)
            raise StoreError("current admission refusal", kind="probe")

        def replay_dispatch_outcome(self, **kwargs):
            self.replay_calls.append(kwargs)
            return supervisor.replay_dispatch_outcome(principal="Codex", **kwargs)

        def ack_dispatch_intent(self, **kwargs):
            self.ack_calls.append(kwargs)
            return supervisor.ack_dispatch_intent(principal="Codex", **kwargs)

    transport = Transport()
    config = owner_service.DispatchOwnerServiceConfig(
        principal="Codex", openssl_path=keypair.openssl_path,
        trust_registry=keypair.trust_registry,
    )
    relay = owner_service.DispatchOwnerService(config, supervisor=transport)
    instruction = keypair.sign(body)
    payload = contracts.canonical_bytes({"instruction": instruction})
    header = struct.Struct("!I")
    server, client = socket.socketpair()
    try:
        client.sendall(header.pack(len(payload)) + payload)
        client.shutdown(socket.SHUT_WR)
        outcome_unknown = relay._handle(server)
        response_size = header.unpack(client.recv(header.size))[0]
        response_bytes = bytearray()
        while len(response_bytes) < response_size:
            chunk = client.recv(response_size - len(response_bytes))
            assert chunk
            response_bytes.extend(chunk)
        response = json.loads(response_bytes)
        assert response == {"ok": True, "result": accepted}
        assert outcome_unknown is False
        assert transport.submit_calls == [{"instruction": instruction}]
        assert transport.replay_calls == [{"instruction": instruction}]
        assert transport.ack_calls == [_ack_body(accepted)]
        assert transport.ack_calls[0]["service_generation"] == accepted["service_generation"]
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 1
        with store._read_tx() as conn:
            state, pending = store._dispatch_outcome_state_locked(conn)
        assert state == "ACKNOWLEDGED"
        assert pending is None
    finally:
        server.close()
        client.close()
        store.close()


def test_pending_dispatch_barrier_survives_store_reopen(
    tmp_path, dispatch_instruction_keypair,
):
    store, _supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    db_path = str(tmp_path / "dispatch.db")
    _submit(_supervisor, body, keypair)
    store.close()
    reopened = Store(db_path, event_key=EVENT_KEY)
    try:
        with pytest.raises(StoreError) as generation_mismatch:
            reopened.accept_dispatch_intent(
                principal="Codex", instruction=keypair.sign(body),
                service_generation="generation-after-restart",
            )
        assert generation_mismatch.value.kind == "duplicate"
        with pytest.raises(StoreError) as raised:
            reopened.accept_dispatch_intent(
                principal="Codex", instruction=keypair.sign({**body, "request_id": "c" * 32}),
                service_generation=GENERATION,
            )
        assert raised.value.kind == "lifecycle"
        with reopened._read_tx() as conn:
            state, pending = reopened._dispatch_outcome_state_locked(conn)
        assert state == "PENDING"
        assert pending["request_id"] == body["request_id"]
        replay = reopened.accept_dispatch_intent(
            principal="Codex", instruction=keypair.sign(body), service_generation=GENERATION,
        )
        assert replay["request_id"] == body["request_id"]
    finally:
        reopened.close()


def test_supervisor_replays_pending_result_from_original_generation_after_rotation(
    tmp_path, dispatch_instruction_keypair,
):
    store, supervisor, _manifest, _epoch, generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    instruction = keypair.sign(body)
    try:
        accepted_g1 = supervisor.accept_dispatch_intent(
            principal="Codex", instruction=instruction,
        )
        assert accepted_g1["service_generation"] == GENERATION
        generation["value"] = "generation-after-restart"

        with pytest.raises(StoreError) as admission:
            supervisor.accept_dispatch_intent(principal="Codex", instruction=instruction)
        assert admission.value.kind == "duplicate"

        replayed = supervisor.replay_dispatch_outcome(
            principal="Codex", instruction=instruction,
        )
        assert replayed == accepted_g1
        assert replayed["service_generation"] == GENERATION
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 1
        assert supervisor.ack_dispatch_intent(
            principal="Codex", **_ack_body(replayed),
        ) == _ack_body(accepted_g1)
        ack_note = json.loads(store._conn.execute(
            "SELECT payload FROM events WHERE actor='supervisor' AND kind='NOTE' "
            "AND payload LIKE '%DISPATCH_OWNER_OUTCOME_ACKNOWLEDGED%'",
        ).fetchone()[0])
        assert ack_note["service_generation"] == GENERATION
        with store._read_tx() as conn:
            state, pending = store._dispatch_outcome_state_locked(conn)
        assert state == "ACKNOWLEDGED"
        assert pending is None
    finally:
        store.close()


@pytest.mark.skipif(
    host_os.name != "posix",
    reason="NOT_RUN: external-anchor reconciliation acceptance requires POSIX file locking",
)
def test_replay_refuses_incomplete_external_anchor_reconciliation(
    tmp_path, dispatch_instruction_keypair,
):
    anchor_path = tmp_path / "dispatch.anchor"
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair, anchor_path=str(anchor_path),
    )
    instruction = keypair.sign(body)
    try:
        supervisor.accept_dispatch_intent(principal="Codex", instruction=instruction)
        anchor_lines = anchor_path.read_bytes().splitlines(keepends=True)
        assert len(anchor_lines) > 1
        # Keep a valid signed prefix but make it stale relative to the accepted event history.
        anchor_path.write_bytes(b"".join(anchor_lines[:-1]))
        with pytest.raises(StoreError) as raised:
            supervisor.replay_dispatch_outcome(principal="Codex", instruction=instruction)
        assert raised.value.kind == "integrity"
        assert store._integrity_locked is True
    finally:
        store.close()


def test_legacy_accepted_dispatch_is_unresolved_after_store_reopen(
    tmp_path, dispatch_instruction_keypair, monkeypatch,
):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    db_path = str(tmp_path / "dispatch.db")
    original_append = store._append_control_event_locked

    def skip_pending(conn, kind, event_id, payload, *args, **kwargs):
        if kind == "DISPATCH_OWNER_OUTCOME_PENDING":
            return payload
        return original_append(conn, kind, event_id, payload, *args, **kwargs)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(store, "_append_control_event_locked", skip_pending)
            accepted = _submit(supervisor, body, keypair)
        assert accepted["request_id"] == body["request_id"]
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE payload LIKE '%DISPATCH_OWNER_OUTCOME_PENDING%'",
        ).fetchone()[0] == 0
    finally:
        store.close()

    reopened = Store(db_path, event_key=EVENT_KEY)
    try:
        with pytest.raises(StoreError) as raised:
            reopened.accept_dispatch_intent(
                principal="Codex", instruction=keypair.sign(body),
                service_generation=GENERATION,
            )
        assert raised.value.kind == "integrity"
        with pytest.raises(StoreError) as replay_error:
            reopened.replay_dispatch_outcome(principal="Codex", instruction=keypair.sign(body))
        assert replay_error.value.kind == "integrity"
    finally:
        reopened.close()


@pytest.mark.parametrize("mutation", ["malformed-binding", "ack-before-pending"])
def test_malformed_or_out_of_order_dispatch_outcome_history_fails_closed(
    tmp_path, dispatch_instruction_keypair, monkeypatch, mutation,
):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    db_path = str(tmp_path / "dispatch.db")
    original_append = store._append_control_event_locked

    def inject_invalid_order(conn, kind, event_id, payload, *args, **kwargs):
        if kind == "DISPATCH_OWNER_OUTCOME_PENDING":
            if mutation == "malformed-binding":
                payload = {**payload, "principal": "forged-principal"}
            else:
                original_append(
                    conn, "DISPATCH_OWNER_OUTCOME_ACKNOWLEDGED",
                    f"dispatch-owner-outcome:{payload['request_id']}:acknowledged", payload,
                )
        return original_append(conn, kind, event_id, payload, *args, **kwargs)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(store, "_append_control_event_locked", inject_invalid_order)
            assert _submit(supervisor, body, keypair)["request_id"] == body["request_id"]
    finally:
        store.close()

    reopened = Store(db_path, event_key=EVENT_KEY)
    try:
        assert reopened._integrity_locked is True
        assert reopened.reconciliation_complete is False
        with pytest.raises(StoreError) as replay_error:
            reopened.replay_dispatch_outcome(principal="Codex", instruction=keypair.sign(body))
        assert replay_error.value.kind == "integrity"
    finally:
        reopened.close()


def test_dispatch_outcome_history_rejects_cross_request_ack_ordering(
    tmp_path, dispatch_instruction_keypair, monkeypatch,
):
    store, supervisor, _manifest, _epoch, _generation, body_a, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    db_path = str(tmp_path / "dispatch.db")
    try:
        result_a = _submit(supervisor, body_a, keypair)
        body_b = {**body_a, "request_id": "d" * 32}
        with monkeypatch.context() as patch:
            # Bypass only the admission-state decision so the hash-valid event sequence can
            # represent the impossible legacy/interleaved history under review.
            patch.setattr(store, "_dispatch_outcome_state_locked", lambda _conn: ("OPEN", None))
            result_b = _submit(supervisor, body_b, keypair)

        for result in (result_a, result_b):
            binding = store._dispatch_outcome_binding(result)
            with monkeypatch.context() as patch:
                patch.setattr(
                    store, "_dispatch_outcome_state_locked",
                    lambda _conn, value=binding: ("PENDING", value),
                )
                supervisor.ack_dispatch_intent(
                    principal="Codex", **_ack_body(result),
                )
        assert store.verify_event_chain()
    finally:
        store.close()

    reopened = Store(db_path, event_key=EVENT_KEY)
    try:
        assert reopened._integrity_locked is True
        assert reopened.reconciliation_complete is False
        with pytest.raises(StoreError) as replay_error:
            reopened.replay_dispatch_outcome(
                principal="Codex", instruction=keypair.sign(body_a),
            )
        assert replay_error.value.kind == "integrity"
        with pytest.raises(StoreError) as raised:
            reopened.accept_dispatch_intent(
                principal="Codex", instruction=keypair.sign({**body_a, "request_id": "e" * 32}),
                service_generation=GENERATION,
            )
        assert raised.value.kind == "integrity"
    finally:
        reopened.close()


def test_store_connection_sets_and_verifies_synchronous_full(
    tmp_path, dispatch_instruction_keypair,
):
    store, *_rest = _ready_dispatch_fixture(tmp_path, dispatch_instruction_keypair)
    try:
        assert store._conn.execute("PRAGMA synchronous").fetchone()[0] == 2
    finally:
        store.close()


def test_owner_intent_is_atomically_bound_and_idempotently_replayed(
    tmp_path, dispatch_instruction_keypair,
):
    store, supervisor, manifest, epoch, generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        accepted = _submit(supervisor, body, keypair)
        assert accepted == _submit(supervisor, body, keypair)
        assert accepted["principal"] == "Codex"
        assert accepted["task_id"] == manifest["task_id"]
        assert accepted["slot"] == "tests"
        assert (accepted["attempt"], accepted["epoch"], accepted["run_id"]) == (
            1, epoch, "run-s2-1",
        )
        assert accepted["request_id"] == REQUEST_ID
        assert accepted["service_generation"] == GENERATION
        assert accepted["instruction"] == keypair.sign(body)
        assert accepted["key_id"] == keypair.key_id
        assert accepted["lease_id"] == 1
        assert accepted["manifest_digest"] == contracts.manifest_sha256(manifest)
        assert len(accepted["payload_digest"]) == 64

        rows = store._conn.execute(
            "SELECT seq, task_id, actor, kind, payload FROM events "
            "WHERE kind = 'DISPATCH_INTENT_ACCEPTED' ORDER BY seq",
        ).fetchall()
        assert len(rows) == 1
        assert int(rows[0]["seq"]) == accepted["event_seq"]
        assert rows[0]["task_id"] == manifest["task_id"]
        assert rows[0]["actor"] == "Codex"
        assert json.loads(rows[0]["payload"]) == {
            key: value for key, value in accepted.items() if key != "event_seq"
        }
        assert store.verify_event_chain()

        # Replaying identical signed bytes in another generation cannot rebind the request.
        generation["value"] = "generation-s2-2"
        with pytest.raises(StoreError) as raised:
            _submit(supervisor, body, keypair)
        assert raised.value.kind == "duplicate"
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 1
    finally:
        store.close()


@pytest.mark.parametrize(
    ("principal", "slot", "expected_kind"),
    [
        ("OtherOwner", "tests", "authorization"),
        ("Codex", "static", "slot"),
    ],
)
def test_invalid_owner_slot_or_request_id_cannot_publish_an_intent(
    tmp_path, dispatch_instruction_keypair, principal, slot, expected_kind,
):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        invalid = {**body, "slot": slot}
        with pytest.raises(StoreError) as raised:
            _submit(supervisor, invalid, keypair, principal=principal)
        assert raised.value.kind == expected_kind
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 0
        assert store.verify_event_chain()
    finally:
        store.close()


def test_invalid_request_id_cannot_publish_an_intent(tmp_path, dispatch_instruction_keypair):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        with pytest.raises(ContractError, match="request_id"):
            _submit(supervisor, {**body, "request_id": "not-a-request-id"}, keypair)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_reusing_request_id_with_changed_payload_is_refused(tmp_path, dispatch_instruction_keypair):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        _submit(supervisor, body, keypair)
        with pytest.raises(StoreError) as raised:
            _submit(supervisor, {**body, "slot": "other-tests"}, keypair)
        assert raised.value.kind == "duplicate"
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 1
        assert store.verify_event_chain()
    finally:
        store.close()


def test_supervisor_subscription_revalidates_generation_and_live_owner_lease(
    tmp_path, dispatch_instruction_keypair,
):
    store, supervisor, _manifest, _epoch, generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        accepted = _submit(supervisor, body, keypair)
        current = supervisor.next_dispatch_intent(cursor=None, audience=AUDIENCE)
        assert current["intent"]["request_id"] == REQUEST_ID
        assert current["cursor_after"]["sequence"] == accepted["event_seq"]

        generation["value"] = "generation-s2-2"
        after_restart = supervisor.next_dispatch_intent(cursor=None, audience=AUDIENCE)
        assert after_restart["intent"] is None
        assert after_restart["cursor_idle"]["service_generation"] == "generation-s2-2"

        generation["value"] = GENERATION
        store.release_epoch("story-dispatch-1", "Codex")
        store.acquire_epoch("story-dispatch-1", "GPT-PM", ttl_sec=3600)
        after_owner_change = supervisor.next_dispatch_intent(cursor=None, audience=AUDIENCE)
        assert after_owner_change["intent"] is None
        assert after_owner_change["cursor_idle"]["sequence"] >= accepted["event_seq"]
    finally:
        store.close()


def test_supervisor_subscription_does_not_deliver_after_live_lease_is_released(
    tmp_path, dispatch_instruction_keypair,
):
    store, supervisor, manifest, epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        accepted = _submit(supervisor, body, keypair)
        store.release_lease(manifest["task_id"], "runner-1", epoch)

        result = supervisor.next_dispatch_intent(cursor=None, audience=AUDIENCE)

        assert result["intent"] is None
        assert result["cursor_idle"]["sequence"] >= accepted["event_seq"]
    finally:
        store.close()


def test_dispatch_cursor_is_bound_to_mac_generation_and_subscriber(
    tmp_path, dispatch_instruction_keypair,
):
    store, supervisor, _manifest, _epoch, generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        accepted = _submit(supervisor, body, keypair)
        token = store.make_dispatch_cursor(
            sequence=accepted["event_seq"],
            service_generation=GENERATION,
            audience=AUDIENCE,
        )
        assert supervisor.next_dispatch_intent(cursor=token, audience=AUDIENCE)["intent"] is None

        tampered = {**token, "sequence": token["sequence"] - 1}
        with pytest.raises(StoreError) as raised:
            supervisor.next_dispatch_intent(cursor=tampered, audience=AUDIENCE)
        assert raised.value.kind == "cursor"
        with pytest.raises(StoreError) as raised:
            supervisor.next_dispatch_intent(cursor=token, audience="other-subscriber")
        assert raised.value.kind == "cursor"
        generation["value"] = "generation-s2-2"
        with pytest.raises(StoreError) as raised:
            supervisor.next_dispatch_intent(cursor=token, audience=AUDIENCE)
        assert raised.value.kind == "cursor"
    finally:
        store.close()


@pytest.mark.parametrize(
    "failure",
    [StoreBusyError("database busy"), StoreError("event chain damaged", kind="integrity")],
    ids=["busy", "integrity"],
)
def test_subscription_propagates_systemic_store_errors_without_advancing_replay(
    tmp_path, monkeypatch, failure, dispatch_instruction_keypair,
):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        accepted = _submit(supervisor, body, keypair)

        def fail_basis(*_args, **_kwargs):
            raise failure

        monkeypatch.setattr(store, "execution_grant_basis", fail_basis)
        with pytest.raises(StoreError) as raised:
            supervisor.next_dispatch_intent(cursor=None, audience=AUDIENCE)
        assert raised.value is failure
        # No returned idle cursor was available to the subscriber, so replay still begins at zero.
        replay = store.read_dispatch_intents(after_seq=0)
        assert replay["intents"][0]["event_seq"] == accepted["event_seq"]
    finally:
        store.close()


def test_grant_forwarding_uses_exact_intent_and_replays_one_cached_grant(
    tmp_path, monkeypatch, dispatch_instruction_keypair,
):
    store, supervisor, manifest, epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        _submit(supervisor, body, keypair)
        issued = []
        expected = {
            "task_id": manifest["task_id"], "slot": "tests", "attempt": 1,
            "epoch": epoch, "run_id": "run-s2-1", "resolved_model": manifest["model_policy"],
            "model_provenance_sha256": "d" * 64, "expected_owner": "Codex", "expected_lease_id": 1,
        }

        def issue_exact_grant(**kwargs):
            issued.append(kwargs)
            return {"grant_id": "one-grant", "bound_task": kwargs["task_id"]}

        monkeypatch.setattr(supervisor, "issue_execution_grant", issue_exact_grant)
        first = supervisor.issue_dispatch_intent_grant(request_id=REQUEST_ID)
        replay = supervisor.issue_dispatch_intent_grant(request_id=REQUEST_ID)
        assert first == replay == {"grant_id": "one-grant", "bound_task": manifest["task_id"]}
        assert issued == [expected]
        assert store.verify_event_chain()
    finally:
        store.close()


def test_supervisor_rpc_derives_principal_from_peer_and_limits_operations(
    tmp_path, dispatch_instruction_keypair,
):
    store, supervisor, _manifest, _epoch, _generation, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        api = SimpleNamespace(supervisor=supervisor)
        instruction = keypair.sign(body)
        owner = SupervisorPeer(
            role="dispatch_owner", uid=1200, gid=1200,
            cgroup="/system.slice/vst-owner.service",
            operations=frozenset({
                "submit_dispatch_intent", "replay_dispatch_outcome", "ack_dispatch_intent",
            }), principal="Codex",
        )
        accepted = AuthenticatedSupervisorAPI._dispatch(
            api, "submit_dispatch_intent", {"instruction": instruction}, owner,
        )
        assert accepted["principal"] == "Codex"
        assert "principal" not in body

        with pytest.raises(ContractError, match="not authorized"):
            AuthenticatedSupervisorAPI._dispatch(api, "submit_dispatch_intent", body, owner)

        with pytest.raises(ContractError, match="not authorized"):
            AuthenticatedSupervisorAPI._dispatch(
                api, "submit_dispatch_intent",
                {"instruction": instruction, "principal": "Attacker"}, owner,
            )
        dispatcher = SupervisorPeer(
            role="dispatcher", uid=1201, gid=1201,
            cgroup="/system.slice/vst-dispatcher.service",
            operations=frozenset({"issue_dispatch_grant", "next_dispatch_intent"}),
        )
        with pytest.raises(ContractError, match="not authorized"):
            AuthenticatedSupervisorAPI._dispatch(
                api, "submit_dispatch_intent", {"instruction": instruction}, dispatcher,
            )
    finally:
        store.close()


class _FramedRunnerResponse:
    def __init__(self, response: dict):
        payload = contracts.canonical_bytes(response)
        self.incoming = bytearray(struct.pack("!I", len(payload)) + payload)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def settimeout(self, _timeout):
        return None

    def connect(self, _path):
        return None

    def sendall(self, _payload):
        return None

    def recv(self, count):
        chunk = bytes(self.incoming[:count])
        del self.incoming[:count]
        return chunk


@pytest.mark.parametrize(
    "field",
    ["task_id", "manifest_sha256", "slot", "attempt", "epoch", "runner_id", "invocation_id"],
)
def test_dispatch_response_receipt_must_match_exact_grant(tmp_path, monkeypatch, field):
    import tools.vst.runner_service as runner_service

    manifest = base_manifest(task_id="receipt-bound-task", story_id="receipt-bound-story")
    digest = contracts.manifest_sha256(manifest)
    grant = {
        "task_id": manifest["task_id"], "manifest_sha256": digest,
        "slot": "tests", "attempt": 1, "epoch": 2,
        "runner_id": "runner-1", "invocation_id": "dispatch-invocation-1",
    }
    receipt = signed_receipt(
        "TestRun", KEY, task_id=grant["task_id"], manifest_sha256=digest,
        slot="tests", attempt=1, epoch=2, runner_id="runner-1",
        invocation_id="dispatch-invocation-1",
    )
    if field == "manifest_sha256":
        receipt[field] = "f" * 64
    elif field in {"attempt", "epoch"}:
        receipt[field] += 1
        if field == "attempt":
            receipt["prev_receipt_sha256"] = "0" * 64
    else:
        receipt[field] = "different"
    response = _FramedRunnerResponse({"status": "COMPLETE", "receipt": receipt})
    monkeypatch.setattr(runner_service, "os", SimpleNamespace(name="posix", path=posixpath))
    monkeypatch.setattr(runner_service.socket, "AF_UNIX", 1, raising=False)
    monkeypatch.setattr(runner_service.socket, "socket", lambda *_args, **_kwargs: response)

    with pytest.raises(ContractError, match="does not match the dispatched grant"):
        dispatch_manifest_run("/run/vst-runner/runner.sock", grant)


def test_dispatch_response_returns_valid_receipt_when_grant_bindings_match(monkeypatch):
    import tools.vst.runner_service as runner_service

    manifest = base_manifest(task_id="receipt-bound-task", story_id="receipt-bound-story")
    digest = contracts.manifest_sha256(manifest)
    grant = {
        "task_id": manifest["task_id"], "manifest_sha256": digest,
        "slot": "tests", "attempt": 1, "epoch": 2,
        "runner_id": "runner-1", "invocation_id": "dispatch-invocation-1",
    }
    receipt = signed_receipt(
        "TestRun", KEY, task_id=grant["task_id"], manifest_sha256=digest,
        slot="tests", attempt=1, epoch=2, runner_id="runner-1",
        invocation_id="dispatch-invocation-1",
    )
    response = _FramedRunnerResponse({"status": "COMPLETE", "receipt": receipt})
    monkeypatch.setattr(runner_service, "os", SimpleNamespace(name="posix", path=posixpath))
    monkeypatch.setattr(runner_service.socket, "AF_UNIX", 1, raising=False)
    monkeypatch.setattr(runner_service.socket, "socket", lambda *_args, **_kwargs: response)

    assert dispatch_manifest_run("/run/vst-runner/runner.sock", grant) == receipt
