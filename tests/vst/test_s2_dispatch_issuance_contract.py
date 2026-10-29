"""TP-33/34/38 pure root issuance contracts; no signing authority is created here."""
from __future__ import annotations

import base64
import copy
from datetime import datetime, timezone

import pytest

from tools.vst.contracts import ContractError, canonical_bytes
from tools.vst.dispatch_issuance import (
    ISSUANCE_OPERATION, canonical_sha256, freeze_issuance_intent,
    reduce_issuance_state, validate_key_binding,
)
from tools.vst.dispatch_instruction import DISPATCH_INSTRUCTION_PURPOSE
from tools.vst.store import Store, StoreError
from tools.vst.supervisor import Supervisor
from tests.vst.test_s2_assignment_bootstrap import _fresh_fixture

NOW = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
SIGNER = {"key_id": "synthetic-delegated-key", "key_class": "DELEGATED_V1",
          "purpose": DISPATCH_INSTRUCTION_PURPOSE, "public_key_fingerprint": "e" * 64}


def _frozen_fixture():
    store, _manifest, policy, _request, invoke = _fresh_fixture()
    handoff = invoke()
    policy_digest = canonical_sha256(policy)
    expiry = "2026-10-29T12:01:00Z"
    frozen = freeze_issuance_intent(
        handoff, policy={"policy": policy, "policy_sha256": policy_digest}, signer=SIGNER,
        expires_at=expiry, authority_expires_at_utc=handoff["expires_at_utc"],
        issuer_max_ttl_seconds=60, minimum_safety_slack_seconds=10, now=NOW,
    )
    store.close()
    return frozen


def _events(frozen: dict, *, terminal: list[dict] | None = None) -> tuple[dict, list[dict]]:
    intent_event = {"type": "SUPERVISOR_DISPATCH_ISSUANCE_INTENT",
                    "operation_key": frozen["operation_key"], "operation": ISSUANCE_OPERATION,
                    "payload_sha256": frozen["payload_sha256"], "intent": copy.deepcopy(frozen)}
    events = [intent_event]
    for record in terminal or []:
        events.append({"operation_key": frozen["operation_key"],
                       "intent_sha256": canonical_sha256(frozen),
                       "unsigned_sha256": frozen["unsigned_sha256"], **record})
    row = {"operation_key": frozen["operation_key"], "operation": ISSUANCE_OPERATION,
           "payload_sha256": frozen["payload_sha256"], "result": {"_vst_state": "PENDING"}}
    return row, events


def test_freezing_binds_stable_identity_exact_v1_fields_and_ttl_boundary():
    frozen = _frozen_fixture()
    assert frozen["unsigned"] == {
        "version": 1, "algorithm": "Ed25519", "purpose": DISPATCH_INSTRUCTION_PURPOSE,
        "request_id": frozen["request_id"], "task_id": "T-bootstrap-fresh", "slot": "tests",
        "attempt": 1, "epoch": 2, "run_id": "bootstrap-run-1",
        "key_id": SIGNER["key_id"], "expires_at": "2026-10-29T12:01:00Z",
    }
    assert frozen["operation_key"].startswith("dispatch-issue:")
    assert frozen["unsigned_sha256"] == canonical_sha256(frozen["unsigned"])
    changed = copy.deepcopy(frozen["unsigned"])
    changed["task_id"] = "caller-selected"
    assert changed != frozen["unsigned"]
    with pytest.raises(ContractError, match="minimum-validity bound"):
        freeze_issuance_intent(
            frozen["handoff"], policy={"policy": frozen["policy"],
                                         "policy_sha256": frozen["policy_sha256"]},
            signer=SIGNER, expires_at="2026-10-29T12:00:59Z",
            authority_expires_at_utc=frozen["authority_expires_at_utc"],
            issuer_max_ttl_seconds=60, minimum_safety_slack_seconds=10, now=NOW,
        )


@pytest.mark.parametrize("binding", [
    {**SIGNER, "key_class": "UNKNOWN"},
    {**SIGNER, "key_class": "LEGACY_V1"},
    {**SIGNER, "purpose": "wrong-purpose"},
    {**SIGNER, "unreviewed": True},
])
def test_issuer_requires_explicit_delegated_class_purpose_and_closed_binding(binding):
    with pytest.raises(ContractError):
        validate_key_binding(binding)


def test_issuance_reducer_orders_events_and_never_grants_signing_authority():
    frozen = _frozen_fixture()
    row, events = _events(frozen)
    pending = reduce_issuance_state(row, events)
    assert pending["state"] == "PENDING" and pending["may_sign"] is False
    started = {"type": "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED"}
    row, events = _events(frozen, terminal=[started])
    unknown = reduce_issuance_state(row, events)
    assert unknown["state"] == "UNKNOWN" and unknown["may_sign"] is False
    row, events = _events(frozen, terminal=[{**started, "caller_selected": True}])
    conflict = reduce_issuance_state(row, events)
    assert conflict["state"] == "CONFLICT" and conflict["may_sign"] is False
    completed = {"type": "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED", "envelope": {},
                 "envelope_sha256": "0" * 64}
    row, events = _events(frozen, terminal=[completed,
        {"type": "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED"}])
    assert reduce_issuance_state(row, events)["state"] == "CONFLICT"
    row, events = _events(frozen, terminal=[
        {"type": "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED"},
        {"type": "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED"},
    ])
    assert reduce_issuance_state(row, events)["state"] == "CONFLICT"


def test_completed_envelope_requires_exact_signer_verifier_and_frozen_context():
    frozen = _frozen_fixture()
    started = {"type": "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED"}
    envelope = {**frozen["unsigned"],
                "signature": base64.urlsafe_b64encode(bytes(64)).decode("ascii").rstrip("=")}
    completed = {"type": "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED",
                 "envelope": envelope, "envelope_sha256": canonical_sha256(envelope)}
    row, events = _events(frozen, terminal=[started, completed])
    assert reduce_issuance_state(row, events)["state"] == "CONFLICT"
    seen = []
    def verifier(binding: dict, signing_bytes: bytes, signature: bytes):
        seen.append((binding, signing_bytes, signature))
        return True
    accepted = reduce_issuance_state(row, events, completion_verifier=verifier)
    assert accepted["state"] == "COMPLETED" and accepted["may_sign"] is False
    assert seen[0][0] == SIGNER
    assert seen[0][1].startswith(b"VST_S2_DISPATCH_INSTRUCTION_V1\0")
    assert seen[0][2] == bytes(64)
    assert reduce_issuance_state(row, events, completion_verifier=lambda *_: 1)["state"] == "CONFLICT"
    assert reduce_issuance_state(row, events, completion_verifier=lambda *_: False)["state"] == "CONFLICT"


def test_live_issuer_and_trust_providers_are_required_and_fail_closed_on_change():
    store, _manifest, _policy, _request, _invoke = _fresh_fixture()
    issuer_config = {
        "enabled": True, "key_id": SIGNER["key_id"],
        "key_class": SIGNER["key_class"], "purpose": SIGNER["purpose"],
        "public_key_fingerprint": SIGNER["public_key_fingerprint"],
        "maximum_ttl_seconds": 60, "minimum_safety_slack_seconds": 10,
    }
    trust = {"legacy-key": {"key_id": "legacy-key", "purpose": "legacy-purpose"}}
    try:
        with pytest.raises(ValueError, match="live root issuer"):
            Supervisor(store, operation_backend=object(), root_dispatch_issuer=issuer_config)
        supervisor = Supervisor(
            store, operation_backend=object(), root_dispatch_issuer=issuer_config,
            root_dispatch_issuer_provider=lambda: issuer_config,
            dispatch_instruction_trust_keys=trust,
            dispatch_instruction_trust_provider=lambda: trust,
        )
        assert supervisor._current_root_dispatch_issuer() == issuer_config

        supervisor.root_dispatch_issuer_provider = lambda: {**issuer_config, "enabled": False}
        with pytest.raises(StoreError, match="changed"):
            supervisor._current_root_dispatch_issuer()
        supervisor.root_dispatch_issuer_provider = lambda: issuer_config
        supervisor.dispatch_instruction_trust_provider = lambda: {"different": {}}
        with pytest.raises(StoreError, match="changed"):
            supervisor._current_root_dispatch_issuer()
        supervisor.dispatch_instruction_trust_provider = lambda: (_ for _ in ()).throw(OSError("absent"))
        with pytest.raises(StoreError, match="unreadable"):
            supervisor._current_root_dispatch_issuer()
    finally:
        store.close()


@pytest.mark.parametrize(("stored_result", "expected_message"), [
    ("{not-json", "operation result is malformed"),
    ('{ "_vst_state" : "PENDING" }', "operation result is not canonical"),
])
def test_store_adapter_rejects_malformed_or_noncanonical_issuance_result(
    stored_result: str, expected_message: str,
):
    row = {"result": stored_result}
    with pytest.raises(StoreError, match=expected_message):
        Store._reduce_dispatch_issuance(row, [], verifier=None)


