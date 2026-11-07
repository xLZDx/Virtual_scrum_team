"""Acceptance tests for signed S2 dispatch-instruction provenance."""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from tools.vst.contracts import ContractError, canonical_bytes
from tools.vst.dispatch_instruction import (
    DISPATCH_INSTRUCTION_DOMAIN,
    DISPATCH_INSTRUCTION_PURPOSE,
    dispatch_instruction_signing_bytes,
    validate_dispatch_instruction,
    verify_dispatch_instruction,
)
from tools.vst.store import Store, StoreError
from tools.vst.supervisor_service import AuthenticatedSupervisorAPI, SupervisorPeer
from tests.vst.s2_dispatch_instruction_fixtures import DispatchInstructionKeyPair
from tests.vst.test_s2_store_backed_pubsub import (
    _ready_dispatch_fixture,
    _submit,
)


def _body() -> dict:
    return {
        "request_id": "8" * 32,
        "task_id": "task-signed-dispatch",
        "slot": "tests",
        "attempt": 1,
        "epoch": 2,
        "run_id": "run-signed-dispatch",
    }


def _raw_signed(keypair: DispatchInstructionKeyPair, body: dict) -> dict:
    """Create a signature over malformed schema to prove parser rejection precedes trust."""
    signature = keypair._sign_payload(
        body, DISPATCH_INSTRUCTION_DOMAIN + canonical_bytes(body),
    )["signature"]
    return {**body, "signature": signature}


def test_valid_ed25519_instruction_binds_exact_envelope_and_mapped_principal(
    dispatch_instruction_keypair,
):
    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_body())

    verified = verify_dispatch_instruction(
        envelope, keypair.trust_registry, expected_principal="Codex",
        openssl_path=keypair.openssl_path,
    )

    assert verified == {
        "principal": "Codex",
        "key_id": keypair.key_id,
        "instruction": envelope,
    }
    assert dispatch_instruction_signing_bytes(envelope).startswith(DISPATCH_INSTRUCTION_DOMAIN)
    assert {key for key in envelope if key != "signature"} == {
        "version", "algorithm", "purpose", "request_id", "task_id", "slot",
        "attempt", "epoch", "run_id", "key_id", "expires_at",
    }


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("version", 2),
        ("algorithm", "HMAC"),
        ("purpose", "VST_E5_OPERATOR_ATTESTATION_V1"),
        ("request_id", "9" * 32),
        ("task_id", "other-task"),
        ("slot", "other-slot"),
        ("attempt", 3),
        ("epoch", 4),
        ("run_id", "other-run"),
        ("key_id", "revoked-or-unknown-key"),
        ("expires_at", "2030-01-01T00:00:00Z"),
    ],
    ids=[
        "version", "algorithm", "purpose", "request-id", "task", "slot",
        "attempt", "epoch", "run", "key-id", "expiry",
    ],
)
def test_mutating_any_signed_field_invalidates_instruction(
    dispatch_instruction_keypair, field, replacement,
):
    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_body())
    tampered = {**envelope, field: replacement}

    with pytest.raises(ContractError):
        verify_dispatch_instruction(
            tampered, keypair.trust_registry, expected_principal="Codex",
            openssl_path=keypair.openssl_path,
        )


def test_invalid_signature_unknown_key_wrong_principal_and_revocation_refuse(
    dispatch_instruction_keypair,
):
    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_body())
    changed_signature = envelope["signature"][:-1] + (
        "A" if envelope["signature"][-1] != "A" else "B"
    )

    with pytest.raises(ContractError, match="signature"):
        verify_dispatch_instruction(
            {**envelope, "signature": changed_signature}, keypair.trust_registry,
            expected_principal="Codex", openssl_path=keypair.openssl_path,
        )
    with pytest.raises(ContractError, match="trusted"):
        verify_dispatch_instruction(
            envelope, {}, expected_principal="Codex", openssl_path=keypair.openssl_path,
        )
    with pytest.raises(ContractError, match="trusted"):
        verify_dispatch_instruction(
            envelope, keypair.trust_registry, expected_principal="GPT-PM",
            openssl_path=keypair.openssl_path,
        )


def test_expired_signed_instruction_is_refused(dispatch_instruction_keypair):
    keypair = dispatch_instruction_keypair
    expired = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ",
    )
    envelope = keypair.sign(_body(), expires_at=expired)

    with pytest.raises(ContractError, match="expired"):
        verify_dispatch_instruction(
            envelope, keypair.trust_registry, expected_principal="Codex",
            openssl_path=keypair.openssl_path,
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("extra", "fields do not match"),
        ("missing", "fields do not match"),
        ("noncanonical-time", "expiry is not canonical"),
        ("wrong-purpose", "algorithm or purpose"),
        ("wrong-algorithm", "algorithm or purpose"),
    ],
)
def test_malformed_or_expanded_envelope_is_refused_even_with_signature(
    dispatch_instruction_keypair, change, message,
):
    keypair = dispatch_instruction_keypair
    body = {
        "version": 1,
        "algorithm": "Ed25519",
        "purpose": DISPATCH_INSTRUCTION_PURPOSE,
        **_body(),
        "key_id": keypair.key_id,
        "expires_at": "2030-01-01T00:00:00Z",
    }
    if change == "extra":
        body["command"] = "caller-selected"
    elif change == "missing":
        body.pop("attempt")
    elif change == "noncanonical-time":
        body["expires_at"] = "2030-1-01T00:00:00Z"
    elif change == "wrong-purpose":
        body["purpose"] = "VST_E5_OPERATOR_ATTESTATION_V1"
    elif change == "wrong-algorithm":
        body["algorithm"] = "HMAC"
    envelope = _raw_signed(keypair, body)

    with pytest.raises(ContractError, match=message):
        verify_dispatch_instruction(
            envelope, keypair.trust_registry, expected_principal="Codex",
            openssl_path=keypair.openssl_path,
        )


def test_untrusted_request_fields_cannot_add_authority(dispatch_instruction_keypair):
    keypair = dispatch_instruction_keypair
    body = {
        "version": 1,
        "algorithm": "Ed25519",
        "purpose": DISPATCH_INSTRUCTION_PURPOSE,
        **_body(),
        "key_id": keypair.key_id,
        "expires_at": "2030-01-01T00:00:00Z",
        "worker": "vst-worker",
        "command": "arbitrary",
        "model": "untrusted-model",
        "grant": {"value": "untrusted"},
    }
    envelope = _raw_signed(keypair, body)

    with pytest.raises(ContractError, match="fields do not match"):
        validate_dispatch_instruction(envelope)


def test_dispatch_owner_client_forwards_the_exact_signed_envelope(dispatch_instruction_keypair):
    from tools.vst.dispatch_owner_client import DispatchOwnerClient

    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_body())
    sent: list[dict] = []

    class Transport:
        def submit_dispatch_intent(self, **kwargs):
            sent.append(kwargs)
            return {
                "instruction": kwargs["instruction"],
                "key_id": keypair.key_id,
                "principal": "Codex",
                **_body(),
            }

        def ack_dispatch_intent(self, **kwargs):
            return kwargs

        def replay_dispatch_outcome(self, **kwargs):
            return None

    client = DispatchOwnerClient(
        principal="Codex", trust_registry=keypair.trust_registry,
        openssl_path=keypair.openssl_path, transport=Transport(),
    )

    result = client.submit(envelope)

    assert sent == [{"instruction": envelope}]
    assert result["instruction"] == envelope


def test_rpc_and_supervisor_independently_verify_before_store_acceptance(
    tmp_path, dispatch_instruction_keypair, monkeypatch,
):
    keypair = dispatch_instruction_keypair
    store, supervisor, _manifest, _epoch, _generation, body, _keypair = _ready_dispatch_fixture(
        tmp_path, keypair,
    )
    import tools.vst.dispatch_instruction as instruction_module

    original_verify = instruction_module.verify_dispatch_instruction
    calls: list[str] = []

    def counting_verify(*args, **kwargs):
        calls.append("verify")
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(instruction_module, "verify_dispatch_instruction", counting_verify)
    owner = SupervisorPeer(
        role="dispatch_owner", uid=1200, gid=1200,
        cgroup="/system.slice/vst-owner.service",
        operations=frozenset({
            "submit_dispatch_intent", "replay_dispatch_outcome", "ack_dispatch_intent",
        }), principal="Codex",
    )
    api = SimpleNamespace(supervisor=supervisor)
    envelope = keypair.sign(body)
    try:
        result = AuthenticatedSupervisorAPI._dispatch(
            api, "submit_dispatch_intent", {"instruction": envelope}, owner,
        )
        assert result["instruction"] == envelope
        assert calls == ["verify", "verify"]
        assert store.verify_event_chain()
    finally:
        store.close()


def test_legacy_unsigned_rpc_cannot_publish_an_intent(tmp_path, dispatch_instruction_keypair):
    keypair = dispatch_instruction_keypair
    store, supervisor, _manifest, _epoch, _generation, body, _keypair = _ready_dispatch_fixture(
        tmp_path, keypair,
    )
    owner = SupervisorPeer(
        role="dispatch_owner", uid=1200, gid=1200,
        cgroup="/system.slice/vst-owner.service",
        operations=frozenset({
            "submit_dispatch_intent", "replay_dispatch_outcome", "ack_dispatch_intent",
        }), principal="Codex",
    )
    try:
        with pytest.raises(ContractError, match="not authorized"):
            AuthenticatedSupervisorAPI._dispatch(
                SimpleNamespace(supervisor=supervisor),
                "submit_dispatch_intent", body, owner,
            )
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_store_persists_exact_signed_envelope_and_rejects_rebound_request_id(
    tmp_path, dispatch_instruction_keypair,
):
    keypair = dispatch_instruction_keypair
    store, supervisor, _manifest, _epoch, _generation, body, _keypair = _ready_dispatch_fixture(
        tmp_path, keypair,
    )
    envelope = keypair.sign(body)
    try:
        accepted = supervisor.accept_dispatch_intent(principal="Codex", instruction=envelope)
        persisted = store.find_dispatch_intent(body["request_id"], principal="Codex")
        assert persisted["instruction"] == envelope
        assert persisted["key_id"] == keypair.key_id
        assert persisted["payload_digest"] == accepted["payload_digest"]
        assert store.verify_event_chain()

        changed = keypair.sign(body, expires_at="2030-01-01T00:00:00Z")
        with pytest.raises(StoreError) as raised:
            supervisor.accept_dispatch_intent(principal="Codex", instruction=changed)
        assert raised.value.kind == "duplicate"
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 1
    finally:
        store.close()


def test_revoked_instruction_key_blocks_delivery_and_grant(tmp_path, dispatch_instruction_keypair):
    keypair = dispatch_instruction_keypair
    store, supervisor, _manifest, _epoch, _generation, body, _keypair = _ready_dispatch_fixture(
        tmp_path, keypair,
    )
    try:
        _submit(supervisor, body, keypair)
        supervisor.dispatch_instruction_trust_keys = {}

        delivery = supervisor.next_dispatch_intent(cursor=None, audience="997:990:/system.slice/vst-dispatcher.service")
        assert delivery["intent"] is None
        with pytest.raises(StoreError) as raised:
            supervisor.issue_dispatch_intent_grant(request_id=body["request_id"])
        assert raised.value.kind == "authorization"
    finally:
        store.close()


@pytest.mark.parametrize("field", ["slot", "attempt", "epoch", "task_id", "run_id"])
def test_signed_request_still_requires_matching_store_authority(
    tmp_path, dispatch_instruction_keypair, field,
):
    keypair = dispatch_instruction_keypair
    store, supervisor, _manifest, _epoch, _generation, body, _keypair = _ready_dispatch_fixture(
        tmp_path, keypair,
    )
    changed = {**body, field: f"wrong-{field}" if field in {"task_id", "slot", "run_id"} else 999}
    try:
        with pytest.raises(StoreError):
            _submit(supervisor, changed, keypair)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'DISPATCH_INTENT_ACCEPTED'",
        ).fetchone()[0] == 0
        assert store.verify_event_chain()
    finally:
        store.close()


def test_legacy_unsigned_store_event_fails_closed_during_history_replay(
    tmp_path, dispatch_instruction_keypair,
):
    keypair = dispatch_instruction_keypair
    store, supervisor, _manifest, _epoch, _generation, body, _keypair = _ready_dispatch_fixture(
        tmp_path, keypair,
    )
    try:
        # This fixture simulates a pre-envelope event through the old data shape, without
        # altering the hash-chain bytes after insertion. Startup/history validation must refuse it.
        from tools.vst.contracts import canonical_bytes

        with store._tx() as conn:
            legacy_payload = {
                "principal": "Codex", **body,
                "service_generation": "generation-s2-1", "lease_id": 1,
                "payload_digest": "0" * 64, "manifest_digest": "1" * 64,
            }
            store._record_event_locked(
                conn, body["task_id"], "Codex", "DISPATCH_INTENT_ACCEPTED", legacy_payload,
            )

        assert store.verify_event_chain()
        with pytest.raises(StoreError):
            supervisor.issue_dispatch_intent_grant(request_id=body["request_id"])

        database_path, event_key = store._path, store._event_key
        store.close()
        replayed = Store(database_path, event_key=event_key)
        try:
            with pytest.raises(
                StoreError, match="stored dispatch intent event binding is invalid",
            ):
                replayed.startup_reconcile()
            assert replayed._integrity_locked
        finally:
            replayed.close()
    finally:
        store.close()
