"""Client-side schema check of SupervisorClient.next_dispatch_intent against REAL Store output.

The intent is produced by a real Supervisor/Store (accept_dispatch_intent + next_dispatch_intent);
only the transport ``call`` of the client is stubbed.
"""
from __future__ import annotations

import copy

import pytest

from tools.vst.supervisor_service import SupervisorClient, SupervisorRPCError
from tests.vst.test_s2_store_backed_pubsub import (
    AUDIENCE,
    REQUEST_ID,
    _ready_dispatch_fixture,
    _submit,
)


def _client_returning(result):
    # SupervisorClient.__init__ demands POSIX peer credentials; bypass it, stub only transport.
    client = object.__new__(SupervisorClient)
    seen = []

    def call(operation, body):
        seen.append((operation, body))
        return copy.deepcopy(result)

    client.call = call
    client.seen = seen
    return client


@pytest.fixture
def real_delivery(tmp_path, dispatch_instruction_keypair):
    store, supervisor, _m, _e, _g, body, keypair = _ready_dispatch_fixture(
        tmp_path, dispatch_instruction_keypair,
    )
    try:
        _submit(supervisor, body, keypair)
        delivery = supervisor.next_dispatch_intent(cursor=None, audience=AUDIENCE)
        assert delivery["intent"] is not None
        yield delivery
    finally:
        store.close()


def _with_intent(delivery, **changes):
    result = copy.deepcopy(delivery)
    for key, value in changes.items():
        if value is _DROP:
            result["intent"].pop(key)
        else:
            result["intent"][key] = value
    return result


_DROP = object()


def test_real_store_intent_is_accepted_unchanged(real_delivery):
    intent = real_delivery["intent"]
    assert {"instruction", "key_id"} <= set(intent)  # the shape that used to be rejected
    client = _client_returning(real_delivery)

    result = client.next_dispatch_intent(None)

    assert result == real_delivery
    assert result["intent"]["request_id"] == REQUEST_ID
    assert client.seen == [("next_dispatch_intent", {"cursor": None})]


def test_idle_result_without_intent_is_accepted(real_delivery):
    idle = {**real_delivery, "intent": None}
    assert _client_returning(idle).next_dispatch_intent(None)["intent"] is None


def test_unknown_extra_intent_key_is_rejected(real_delivery):
    result = _with_intent(real_delivery, surprise="x")
    with pytest.raises(SupervisorRPCError, match="malformed dispatch intent"):
        _client_returning(result).next_dispatch_intent(None)


def test_missing_instruction_is_rejected(real_delivery):
    result = _with_intent(real_delivery, instruction=_DROP)
    with pytest.raises(SupervisorRPCError, match="malformed dispatch intent"):
        _client_returning(result).next_dispatch_intent(None)


def test_missing_key_id_is_rejected(real_delivery):
    result = _with_intent(real_delivery, key_id=_DROP)
    with pytest.raises(SupervisorRPCError, match="malformed dispatch intent"):
        _client_returning(result).next_dispatch_intent(None)


def test_key_id_differing_from_signed_instruction_is_rejected(real_delivery):
    result = _with_intent(real_delivery, key_id="some-other-key")
    with pytest.raises(SupervisorRPCError, match="differs from signed dispatch instruction"):
        _client_returning(result).next_dispatch_intent(None)


def test_request_id_differing_from_signed_instruction_is_rejected(real_delivery):
    other = "b" * 32
    assert other != real_delivery["intent"]["request_id"]
    result = _with_intent(real_delivery, request_id=other)
    with pytest.raises(SupervisorRPCError, match="differs from signed dispatch instruction"):
        _client_returning(result).next_dispatch_intent(None)


@pytest.mark.parametrize("field,value", [
    ("task_id", "other-task"), ("slot", "other-slot"), ("attempt", 7),
    ("epoch", 9), ("run_id", "other-run"),
])
def test_each_cross_validated_field_mismatch_is_rejected(real_delivery, field, value):
    assert real_delivery["intent"][field] != value
    result = _with_intent(real_delivery, **{field: value})
    with pytest.raises(SupervisorRPCError, match="differs from signed dispatch instruction"):
        _client_returning(result).next_dispatch_intent(None)


@pytest.mark.parametrize("field,value", [
    ("slot", "tampered-slot"), ("request_id", "c" * 32), ("key_id", "tampered-key"), ("epoch", 99),
])
def test_tampered_instruction_field_is_rejected(real_delivery, field, value):
    result = copy.deepcopy(real_delivery)
    assert result["intent"]["instruction"][field] != value
    result["intent"]["instruction"][field] = value
    with pytest.raises(SupervisorRPCError):
        _client_returning(result).next_dispatch_intent(None)


def test_instruction_with_extra_key_or_missing_signature_is_rejected(real_delivery):
    extra = copy.deepcopy(real_delivery)
    extra["intent"]["instruction"]["extra"] = "x"
    with pytest.raises(SupervisorRPCError, match="invalid dispatch instruction"):
        _client_returning(extra).next_dispatch_intent(None)

    unsigned = copy.deepcopy(real_delivery)
    unsigned["intent"]["instruction"].pop("signature")
    with pytest.raises(SupervisorRPCError, match="invalid dispatch instruction"):
        _client_returning(unsigned).next_dispatch_intent(None)
