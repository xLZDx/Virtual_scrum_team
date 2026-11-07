"""Focused Owner -> Supervisor -> Dispatcher and receipt-observation contracts.

These tests exercise the signed Owner relay, authenticated API dispatch handlers,
and disposable Store state. They do not exercise Windows SCM identity, named-pipe
service startup, a real Runner process, or a Windows Job Object; those remain
runtime/E2E evidence and must not be inferred from this fixture.
"""
from __future__ import annotations

import copy
import json
import socket
import struct

import pytest

from tools.vst.contracts import ContractError, canonical_bytes
from tools.vst import dispatch_owner_service as owner_service_module
from tools.vst.dispatch_owner_service import DispatchOwnerService, DispatchOwnerServiceConfig
from tools.vst.supervisor_service import AuthenticatedSupervisorAPI, SupervisorPeer
from tests.vst.test_s2_root_dispatch_integration import _configured, signing_keys


_HEADER = struct.Struct("!I")
_OWNER_OPERATIONS = frozenset({
    "submit_dispatch_intent", "replay_dispatch_outcome", "completed_dispatch_receipt",
    "ack_dispatch_intent",
})


class _AuthenticatedSupervisorTransport:
    """Route relay calls through the real API dispatcher and Supervisor/Store."""

    def __init__(self, api: AuthenticatedSupervisorAPI, peer: SupervisorPeer):
        self.api = api
        self.peer = peer

    def submit_dispatch_intent(self, **body):
        return self.api._dispatch("submit_dispatch_intent", body, self.peer)

    def replay_dispatch_outcome(self, **body):
        return self.api._dispatch("replay_dispatch_outcome", body, self.peer)

    def completed_dispatch_receipt(self, **body):
        return self.api._dispatch("completed_dispatch_receipt", body, self.peer)

    def ack_dispatch_intent(self, **body):
        return self.api._dispatch("ack_dispatch_intent", body, self.peer)


def _peer(role: str, operations: frozenset[str], *, principal: str | None = None):
    return SupervisorPeer(
        role=role,
        uid=981 if role == "delegated_issuer" else 1200,
        gid=983 if role == "delegated_issuer" else 1201,
        cgroup=f"/system.slice/vst-{role}.service",
        operations=operations,
        principal=principal,
    )


def _owner_service(api: AuthenticatedSupervisorAPI, supervisor):
    issuer = supervisor.root_dispatch_issuer
    trust_registry = {
        issuer["key_id"]: {
            "principal": "Codex",
            "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
            "public_key_path": issuer["public_key_path"],
        },
    }
    supervisor.dispatch_instruction_trust_keys = copy.deepcopy(trust_registry)
    supervisor.dispatch_instruction_trust_provider = lambda: copy.deepcopy(trust_registry)
    supervisor.dispatch_instruction_openssl_path = owner_service_module.OPENSSL_PATH
    transport = _AuthenticatedSupervisorTransport(
        api, _peer("dispatch_owner", _OWNER_OPERATIONS, principal="Codex"),
    )
    config = DispatchOwnerServiceConfig(
        principal="Codex",
        openssl_path=owner_service_module.OPENSSL_PATH,
        trust_registry=trust_registry,
    )
    return DispatchOwnerService(config, supervisor=transport)


def _owner_request(service: DispatchOwnerService, request: dict) -> dict:
    payload = canonical_bytes(request)
    server, client = socket.socketpair()
    try:
        client.sendall(_HEADER.pack(len(payload)) + payload)
        client.shutdown(socket.SHUT_WR)
        assert service._handle(server) is False
        header = client.recv(_HEADER.size)
        assert len(header) == _HEADER.size
        size = _HEADER.unpack(header)[0]
        response = bytearray()
        while len(response) < size:
            chunk = client.recv(size - len(response))
            assert chunk
            response.extend(chunk)
        return json.loads(response)
    finally:
        server.close()
        client.close()


def _submit(service: DispatchOwnerService, instruction: dict) -> dict:
    return _owner_request(service, {"instruction": instruction})


def _completed_receipt(service: DispatchOwnerService, instruction: dict) -> dict:
    return _owner_request(service, {
        "operation": "completed_receipt", "instruction": instruction,
    })


def _request_store_state(store, instruction: dict) -> tuple:
    """Snapshot persisted admission/grant/claim/receipt state around read-only polls."""
    request_id = instruction["request_id"]
    with store._read_tx() as conn:
        counts = (
            conn.execute(
                "SELECT COUNT(*) FROM supervisor_operations "
                "WHERE operation_key = ? AND operation = 'dispatch_grant'",
                (f"dispatch-grant:{request_id}",),
            ).fetchone()[0],
            conn.execute(
                "SELECT COUNT(*) FROM runner_execution_claims WHERE request_id = ?",
                (request_id,),
            ).fetchone()[0],
            conn.execute(
                "SELECT COUNT(*) FROM runner_execution_events "
                "WHERE grant_id IN (SELECT grant_id FROM runner_execution_claims WHERE request_id = ?)",
                (request_id,),
            ).fetchone()[0],
            conn.execute(
                "SELECT COUNT(*) FROM receipts WHERE task_id = ? AND slot = ?",
                (instruction["task_id"], instruction["slot"]),
            ).fetchone()[0],
        )
    return store.event_anchor(), counts


def test_signed_owner_relay_is_persisted_and_becomes_dispatchable(signing_keys):
    """An owner-signed task reaches the actual Supervisor/Store dispatcher view."""
    store, supervisor, _policy, _policy_sha, operation_id, _handoff, _live, _issuer = _configured(
        signing_keys,
    )
    api = object.__new__(AuthenticatedSupervisorAPI)
    api.supervisor = supervisor
    issuer_peer = _peer("delegated_issuer", frozenset({"issue_root_dispatch_instruction"}))
    try:
        instruction = api._dispatch(
            "issue_root_dispatch_instruction",
            {"assignment_operation_id": operation_id},
            issuer_peer,
        )
        owner_service = _owner_service(api, supervisor)

        response = _submit(owner_service, instruction)

        assert response["ok"] is True
        accepted = response["result"]
        assert accepted["instruction"] == instruction
        assert accepted["principal"] == "Codex"
        assert store.find_dispatch_intent(instruction["request_id"])["instruction"] == instruction

        dispatcher_peer = _peer("dispatcher", frozenset({
            "next_dispatch_intent", "issue_dispatch_grant",
        }))
        delivery = api._dispatch("next_dispatch_intent", {"cursor": None}, dispatcher_peer)
        assert delivery["intent"]["request_id"] == instruction["request_id"]
        assert delivery["intent"]["instruction"] == instruction

        grant = api._dispatch(
            "issue_dispatch_grant", {"request_id": instruction["request_id"]}, dispatcher_peer,
        )
        assert grant["request_id"] == instruction["request_id"]
        assert grant["task_id"] == instruction["task_id"]
        assert grant["slot"] == instruction["slot"]
    finally:
        store.close()


def test_completed_receipt_lookup_is_exact_owner_bound_and_read_only(signing_keys):
    """No grant is created by polling; wrong principal/instruction cannot observe it."""
    store, supervisor, _policy, _policy_sha, operation_id, _handoff, _live, _issuer = _configured(
        signing_keys,
    )
    api = object.__new__(AuthenticatedSupervisorAPI)
    api.supervisor = supervisor
    issuer_peer = _peer("delegated_issuer", frozenset({"issue_root_dispatch_instruction"}))
    try:
        instruction = api._dispatch(
            "issue_root_dispatch_instruction",
            {"assignment_operation_id": operation_id},
            issuer_peer,
        )
        owner_service = _owner_service(api, supervisor)
        assert _submit(owner_service, instruction)["ok"] is True

        before = _request_store_state(store, instruction)
        pending = _completed_receipt(owner_service, instruction)
        assert pending == {"ok": True, "result": None}
        assert _request_store_state(store, instruction) == before
        assert before[1][0:3] == (0, 0, 0)

        wrong_principal = _peer("dispatch_owner", _OWNER_OPERATIONS, principal="OtherOwner")
        assert api._dispatch(
            "completed_dispatch_receipt", {"instruction": instruction}, wrong_principal,
        ) is None

        changed_instruction = {**instruction, "task_id": "another-task"}
        owner_peer = _peer("dispatch_owner", _OWNER_OPERATIONS, principal="Codex")
        assert api._dispatch(
            "completed_dispatch_receipt", {"instruction": changed_instruction}, owner_peer,
        ) is None
        assert _request_store_state(store, instruction) == before
    finally:
        store.close()


def test_owner_receives_exact_receipt_only_after_store_complete(signing_keys):
    """The Owner sees the stored receipt after COMPLETE without mutating its history."""
    store, supervisor, _policy, _policy_sha, operation_id, _handoff, _live, _issuer = _configured(
        signing_keys,
    )
    api = object.__new__(AuthenticatedSupervisorAPI)
    api.supervisor = supervisor
    issuer_peer = _peer("delegated_issuer", frozenset({"issue_root_dispatch_instruction"}))
    dispatcher_peer = _peer("dispatcher", frozenset({"issue_dispatch_grant"}))
    try:
        instruction = api._dispatch(
            "issue_root_dispatch_instruction",
            {"assignment_operation_id": operation_id},
            issuer_peer,
        )
        owner_service = _owner_service(api, supervisor)
        assert _submit(owner_service, instruction)["ok"] is True

        grant = api._dispatch(
            "issue_dispatch_grant", {"request_id": instruction["request_id"]}, dispatcher_peer,
        )
        assert supervisor.claim_runner_execution(grant) is None
        assert supervisor.reserve_runner_execution(grant)["state"] == "EXECUTION_RESERVED"

        reserved = _request_store_state(store, instruction)
        pending = _completed_receipt(owner_service, instruction)
        assert pending == {"ok": True, "result": None}
        assert _request_store_state(store, instruction) == reserved

        manifest_row = store._conn.execute(
            "SELECT manifest FROM tasks WHERE task_id = ?", (grant["task_id"],),
        ).fetchone()
        assert manifest_row is not None
        manifest = json.loads(manifest_row["manifest"])
        from tests.vst.test_s2_persistent_runner_service import _receipt_for_grant
        receipt = _receipt_for_grant(grant, manifest)
        # That shared v2 receipt builder uses the default task identifier; bind the
        # fixture receipt to this accepted Store task before durable completion.
        receipt["task_id"] = grant["task_id"]
        supervisor.complete_runner_execution(grant, receipt)

        expected = store.completed_dispatch_receipt(
            request_id=instruction["request_id"], principal="Codex",
        )
        assert expected == receipt
        before_poll = _request_store_state(store, instruction)
        completed = _completed_receipt(owner_service, instruction)
        assert completed == {"ok": True, "result": expected}
        assert _request_store_state(store, instruction) == before_poll

        request = completed["result"]["runner_attestation"]["request"]
        assert request["request_id"] == instruction["request_id"]
        assert request["task_id"] == instruction["task_id"]
        assert request["slot"] == instruction["slot"]
        assert request["attempt"] == instruction["attempt"]
    finally:
        store.close()


def test_non_owner_supervisor_peer_cannot_submit_or_persist_dispatch(signing_keys):
    """The authenticated API refuses a valid instruction from the wrong peer role."""
    store, supervisor, _policy, _policy_sha, operation_id, _handoff, _live, _issuer = _configured(
        signing_keys,
    )
    api = object.__new__(AuthenticatedSupervisorAPI)
    api.supervisor = supervisor
    issuer_peer = _peer("delegated_issuer", frozenset({"issue_root_dispatch_instruction"}))
    try:
        instruction = api._dispatch(
            "issue_root_dispatch_instruction",
            {"assignment_operation_id": operation_id},
            issuer_peer,
        )
        dispatcher_peer = _peer("dispatcher", frozenset({"issue_dispatch_grant"}))

        with pytest.raises(ContractError, match="dispatch intent request is not authorized"):
            api._dispatch(
                "submit_dispatch_intent", {"instruction": instruction}, dispatcher_peer,
            )

        assert store.find_dispatch_intent(instruction["request_id"]) is None
    finally:
        store.close()
