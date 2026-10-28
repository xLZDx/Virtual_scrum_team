"""Focused acceptance tests for the S2 Store-backed dispatch pub/sub contract."""
from __future__ import annotations

import json
import os as host_os
import posixpath
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


REQUEST_ID = "a" * 32
GENERATION = "generation-s2-1"
AUDIENCE = "997:990:/system.slice/vst-dispatcher.service"


def _ready_dispatch_fixture(tmp_path, *, model_provenance_digest="d" * 64):
    clock = FakeClock(1000)
    manifest = base_manifest(
        task_id="task-dispatch-1", story_id="story-dispatch-1", project_id="vst",
    )
    store = Store(
        str(tmp_path / "dispatch.db"), clock, event_key=EVENT_KEY,
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
    return store, supervisor, manifest, epoch, generation, body


def _submit(supervisor, body, *, principal="Codex"):
    return supervisor.accept_dispatch_intent(principal=principal, **body)


def test_owner_intent_is_atomically_bound_and_idempotently_replayed(tmp_path):
    store, supervisor, manifest, epoch, _generation, body = _ready_dispatch_fixture(tmp_path)
    try:
        accepted = _submit(supervisor, body)
        assert accepted == _submit(supervisor, body)
        assert accepted["principal"] == "Codex"
        assert accepted["task_id"] == manifest["task_id"]
        assert accepted["slot"] == "tests"
        assert (accepted["attempt"], accepted["epoch"], accepted["run_id"]) == (
            1, epoch, "run-s2-1",
        )
        assert accepted["request_id"] == REQUEST_ID
        assert accepted["service_generation"] == GENERATION
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
    finally:
        store.close()


@pytest.mark.parametrize(
    ("principal", "slot", "request_id", "expected_kind"),
    [
        ("OtherOwner", "tests", "b" * 32, "epoch"),
        ("Codex", "static", "c" * 32, "slot"),
        ("Codex", "tests", "not-a-request-id", "argument"),
    ],
)
def test_invalid_owner_slot_or_request_id_cannot_publish_an_intent(
    tmp_path, principal, slot, request_id, expected_kind,
):
    store, supervisor, _manifest, _epoch, _generation, body = _ready_dispatch_fixture(tmp_path)
    try:
        invalid = {**body, "slot": slot, "request_id": request_id}
        with pytest.raises(StoreError) as raised:
            _submit(supervisor, invalid, principal=principal)
        assert raised.value.kind == expected_kind
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 0
        assert store.verify_event_chain()
    finally:
        store.close()


def test_reusing_request_id_with_changed_payload_is_refused(tmp_path):
    store, supervisor, _manifest, _epoch, _generation, body = _ready_dispatch_fixture(tmp_path)
    try:
        _submit(supervisor, body)
        with pytest.raises(StoreError) as raised:
            _submit(supervisor, {**body, "slot": "other-tests"})
        assert raised.value.kind == "duplicate"
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 1
        assert store.verify_event_chain()
    finally:
        store.close()


def test_supervisor_subscription_revalidates_generation_and_live_owner_lease(tmp_path):
    store, supervisor, _manifest, _epoch, generation, body = _ready_dispatch_fixture(tmp_path)
    try:
        accepted = _submit(supervisor, body)
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


def test_supervisor_subscription_does_not_deliver_after_live_lease_is_released(tmp_path):
    store, supervisor, manifest, epoch, _generation, body = _ready_dispatch_fixture(tmp_path)
    try:
        accepted = _submit(supervisor, body)
        store.release_lease(manifest["task_id"], "runner-1", epoch)

        result = supervisor.next_dispatch_intent(cursor=None, audience=AUDIENCE)

        assert result["intent"] is None
        assert result["cursor_idle"]["sequence"] >= accepted["event_seq"]
    finally:
        store.close()


def test_dispatch_cursor_is_bound_to_mac_generation_and_subscriber(tmp_path):
    store, supervisor, _manifest, _epoch, generation, body = _ready_dispatch_fixture(tmp_path)
    try:
        accepted = _submit(supervisor, body)
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
def test_subscription_propagates_systemic_store_errors_without_advancing_replay(tmp_path, monkeypatch, failure):
    store, supervisor, _manifest, _epoch, _generation, body = _ready_dispatch_fixture(tmp_path)
    try:
        accepted = _submit(supervisor, body)

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


def test_grant_forwarding_uses_exact_intent_and_replays_one_cached_grant(tmp_path, monkeypatch):
    store, supervisor, manifest, epoch, _generation, body = _ready_dispatch_fixture(tmp_path)
    try:
        _submit(supervisor, body)
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


def test_supervisor_rpc_derives_principal_from_peer_and_limits_operations(tmp_path):
    store, supervisor, _manifest, _epoch, _generation, body = _ready_dispatch_fixture(tmp_path)
    try:
        api = SimpleNamespace(supervisor=supervisor)
        owner = SupervisorPeer(
            role="dispatch_owner", uid=1200, gid=1200,
            cgroup="/system.slice/vst-owner.service",
            operations=frozenset({"submit_dispatch_intent"}), principal="Codex",
        )
        accepted = AuthenticatedSupervisorAPI._dispatch(api, "submit_dispatch_intent", body, owner)
        assert accepted["principal"] == "Codex"
        assert "principal" not in body

        with pytest.raises(ContractError, match="not authorized"):
            AuthenticatedSupervisorAPI._dispatch(
                api, "submit_dispatch_intent", {**body, "principal": "Attacker"}, owner,
            )
        dispatcher = SupervisorPeer(
            role="dispatcher", uid=1201, gid=1201,
            cgroup="/system.slice/vst-dispatcher.service",
            operations=frozenset({"issue_dispatch_grant", "next_dispatch_intent"}),
        )
        with pytest.raises(ContractError, match="not authorized"):
            AuthenticatedSupervisorAPI._dispatch(api, "submit_dispatch_intent", body, dispatcher)
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
