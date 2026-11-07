"""Fixture-only end-to-end checks for the S2 root dispatch authority chain.

All SQLite state and Ed25519 keys are disposable. These tests stop at durable
Store reservation and never launch a worker or claim production authorization.
"""
from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

from tools.vst.contracts import ContractError, canonical_bytes
from tools.vst.dispatch_issuance import ISSUANCE_OPERATION, canonical_sha256
from tools.vst.execution_grant import _openssl_signature
from tools.vst.root_dispatch_issuer import public_key_fingerprint
from tools.vst.store import StoreError
from tests.vst.e1e4_helpers import manifest
from tests.vst.test_s2_assignment_basis import _readiness


@pytest.fixture
def signing_keys():
    """Create two distinct synthetic keys in protected disposable POSIX storage."""
    if os.name != "posix" or os.geteuid() != 0:
        pytest.skip("synthetic root-dispatch signing fixture requires the designated root-owned POSIX test environment")
    openssl = shutil.which("openssl")
    if not openssl:
        pytest.skip("OpenSSL unavailable for disposable signing fixtures")
    directory = tempfile.TemporaryDirectory(prefix="vst-s2-root-issuer-", dir="/root")
    paths = {}
    try:
        for name in ("dispatch", "grant"):
            private = Path(directory.name) / f"{name}-private.pem"
            public = Path(directory.name) / f"{name}-public.pem"
            subprocess.run([openssl, "genpkey", "-algorithm", "ED25519", "-out", str(private)],
                           check=True, cwd="/", stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            os.chmod(private, 0o600)
            subprocess.run([openssl, "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                           check=True, cwd="/", stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            os.chmod(public, 0o644)
            paths[name] = {"private": str(private), "public": str(public)}
        paths["openssl"] = openssl
        paths["dispatch"]["fingerprint"] = public_key_fingerprint(paths["dispatch"]["public"])
        paths["grant"]["fingerprint"] = public_key_fingerprint(paths["grant"]["public"])
        assert paths["dispatch"]["fingerprint"] != paths["grant"]["fingerprint"]
        yield paths
    finally:
        directory.cleanup()


def _configured(signing_keys):
    """Return isolated Store/Supervisor fixture with independently read providers."""
    store, supervisor, policy, policy_sha, operation_id, handoff = _readiness(manifest())
    dispatch = signing_keys["dispatch"]
    grant = signing_keys["grant"]
    issuer = {
        "enabled": True,
        "key_id": "fixture-delegated-key",
        "public_key_fingerprint": dispatch["fingerprint"],
        "maximum_ttl_seconds": 300,
        "minimum_safety_slack_seconds": 1,
        "private_key_path": dispatch["private"],
        "public_key_path": dispatch["public"],
        "openssl_path": signing_keys["openssl"],
        "signer": {
            "key_id": "fixture-delegated-key",
            "key_class": "DELEGATED_V1",
            "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
            "public_key_fingerprint": dispatch["fingerprint"],
        },
    }
    # Providers read an independently mutable holder and return copies, so the
    # check does not accidentally compare a cache with itself.
    live = {"issuer": copy.deepcopy(issuer), "trust": {}}
    supervisor.root_dispatch_issuer = copy.deepcopy(issuer)
    supervisor.root_dispatch_issuer_provider = lambda: copy.deepcopy(live["issuer"])
    supervisor.dispatch_instruction_trust_keys = {}
    supervisor.dispatch_instruction_trust_provider = lambda: copy.deepcopy(live["trust"])
    supervisor.dispatch_instruction_openssl_path = signing_keys["openssl"]
    supervisor.execution_grant_key_id = "fixture-execution-grant-key"
    supervisor.execution_grant_private_key_path = grant["private"]
    supervisor.execution_grant_openssl_path = signing_keys["openssl"]
    supervisor.execution_grant_trust_keys = {supervisor.execution_grant_key_id: grant["public"]}
    supervisor.model_provenance_verifier = lambda _model, _digest: True
    supervisor.model_provenance_digest_provider = lambda _model: "d" * 64
    # _readiness seeds this test-only consumed-probe row; setting the in-process
    # latch models an already-admitted test fixture, not a genuine E5 probe.
    supervisor._probe_consumed = True
    return store, supervisor, policy, policy_sha, operation_id, handoff, live, issuer


def _issue_and_accept(signing_keys):
    store, supervisor, policy, _policy_sha, operation_id, _handoff, live, issuer = _configured(signing_keys)
    from tools.vst.supervisor_service import AuthenticatedSupervisorAPI, SupervisorPeer
    api = object.__new__(AuthenticatedSupervisorAPI)
    api.supervisor = supervisor
    peer = SupervisorPeer(
        "delegated_issuer", 981, 983, "/system.slice/vst-delegated-issuer.service",
        frozenset({"issue_root_dispatch_instruction"}),
    )
    envelope = api._dispatch(
        "issue_root_dispatch_instruction", {"assignment_operation_id": operation_id}, peer,
    )
    accepted = supervisor.accept_dispatch_intent(principal="Codex", instruction=envelope)
    replay = supervisor.accept_dispatch_intent(principal="Codex", instruction=envelope)
    assert replay == accepted
    assert accepted["request_id"] == envelope["request_id"]
    return store, supervisor, policy, operation_id, envelope, accepted, live, issuer


def _signer_for_wrong_class(signing_keys):
    return {
        "key_id": "fixture-legacy-key", "key_class": "LEGACY_V1",
        "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
        "public_key_fingerprint": signing_keys["dispatch"]["fingerprint"],
    }


def test_positive_root_issue_accept_exact_replay_grant_claim_and_reserve(signing_keys):
    """TP-35: exact completed issuance flows through admission, grant and Store reserve."""
    store, supervisor, _policy, _operation_id, envelope, accepted, _live, issuer = _issue_and_accept(
        signing_keys,
    )
    try:
        proof = store.dispatch_issuance_for_envelope(
            envelope,
            lambda signer, payload, signature: (
                signer == issuer["signer"]
                and _openssl_signature(
                    signing_keys["openssl"], key_path=signing_keys["dispatch"]["public"],
                    payload=payload, signature=signature, private=False,
                ) is True
            ),
        )
        assert proof["state"] == "COMPLETED"
        assert proof["envelope"] == envelope
        assert proof["intent"]["assignment_operation_id"]
        assert accepted["instruction"] == envelope
        assert store.find_dispatch_intent(envelope["request_id"])["instruction"] == envelope

        grant = supervisor.issue_dispatch_intent_grant(request_id=envelope["request_id"])
        exact_replay = supervisor.issue_dispatch_intent_grant(request_id=envelope["request_id"])
        assert canonical_bytes(exact_replay) == canonical_bytes(grant)
        grant_op = store._conn.execute(
            "SELECT operation_key, payload_sha256, result FROM supervisor_operations "
            "WHERE operation='dispatch_grant'",
        ).fetchone()
        assert grant_op is not None
        assert grant_op["operation_key"] == f"dispatch-grant:{envelope['request_id']}"
        assert grant_op["result"].encode("utf-8") == canonical_bytes(grant)
        grant_payload = {
            "request_id": envelope["request_id"],
            "service_generation": grant["service_generation"],
            "issuance_operation_key": proof["intent"]["operation_key"],
            "issuance_envelope_sha256": hashlib.sha256(canonical_bytes(envelope)).hexdigest(),
        }
        assert grant_op["payload_sha256"] == canonical_sha256(grant_payload)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation='dispatch_grant'",
        ).fetchone()[0] == 1

        assert supervisor.claim_runner_execution(grant) is None
        # A duplicate claim remains non-replayable while PENDING; the exception
        # is reserved for validating this exact claim during reservation.
        with pytest.raises(StoreError):
            supervisor.claim_runner_execution(grant)
        claim = store.runner_execution_claim_status(
            grant, active_service_generation=grant["service_generation"],
        )
        assert claim["state"] == "PENDING"
        reserved = supervisor.reserve_runner_execution(grant)
        assert reserved["state"] == "EXECUTION_RESERVED"
        with pytest.raises(StoreError, match="unreserved PENDING"):
            supervisor.reserve_runner_execution(grant)
        assert store.runner_execution_claim_status(
            grant, active_service_generation=grant["service_generation"],
        )["state"] == "EXECUTION_RESERVED"
    finally:
        store.close()


def test_altered_signed_grant_bytes_cannot_create_runner_claim(signing_keys):
    store, supervisor, _policy, _operation_id, envelope, _accepted, _live, _issuer = _issue_and_accept(
        signing_keys,
    )
    try:
        grant = supervisor.issue_dispatch_intent_grant(request_id=envelope["request_id"])
        altered = {**grant, "task_id": "caller-selected-task"}
        with pytest.raises(StoreError):
            supervisor.claim_runner_execution(altered)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM runner_execution_claims",
        ).fetchone()[0] == 0
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation='dispatch_grant'",
        ).fetchone()[0] == 1
    finally:
        store.close()


@pytest.mark.parametrize("linkage", ["absent", "mismatch"])
def test_dispatch_grant_operation_collision_cannot_omit_or_change_issuance_linkage(
    signing_keys, linkage,
):
    store, supervisor, _policy, _operation_id, envelope, _accepted, _live, _issuer = _issue_and_accept(
        signing_keys,
    )
    payload = {
        "request_id": envelope["request_id"],
        "service_generation": supervisor.service_generation_provider(),
    }
    if linkage == "mismatch":
        payload.update({
            "issuance_operation_key": "dispatch-issue:caller-selected",
            "issuance_envelope_sha256": "f" * 64,
        })
    operation_key = f"dispatch-grant:{envelope['request_id']}"
    try:
        store.execute_idempotent(
            operation_key, "dispatch_grant", payload,
            lambda _conn: {"fixture": "foreign-payload"},
        )
        with pytest.raises(StoreError, match="payload|operation"):
            supervisor.issue_dispatch_intent_grant(request_id=envelope["request_id"])
        assert store._conn.execute(
            "SELECT COUNT(*) FROM runner_execution_claims",
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_delegated_origin_without_dispatch_grant_link_stays_fail_closed_when_issuer_disabled(
    signing_keys, monkeypatch,
):
    """A missing durable grant link cannot downgrade an authenticated delegated assignment."""
    store, supervisor, _policy, _operation_id, envelope, _accepted, live, issuer = _issue_and_accept(
        signing_keys,
    )
    try:
        grant = supervisor.issue_dispatch_intent_grant(request_id=envelope["request_id"])
        # The exact assignment operation and accepted delegated instruction remain
        # durable. Simulate a missing source lookup without violating the Store's
        # append-only journal guard. Disabling issuer must not reclassify as legacy.
        monkeypatch.setattr(store, "_dispatch_grant_source_locked", lambda _conn, _grant: None)
        live["issuer"] = {**issuer, "enabled": False}
        with pytest.raises(StoreError, match="no immutable dispatch-grant association"):
            store.dispatch_issuance_target_for_grant(grant)
        with pytest.raises(StoreError, match="no immutable dispatch-grant association"):
            supervisor.claim_runner_execution(grant)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM runner_execution_claims",
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_reservation_own_pending_exemption_does_not_ignore_unrelated_predecessor(monkeypatch):
    """The reservation-only exception must not waive a different unresolved claim."""
    store, *_ = _readiness(manifest())

    class Rows:
        def fetchall(self):
            return [
                {"grant_id": "unrelated-predecessor", "task_id": "T-assignment-basis",
                 "slot": "tests", "attempt": 1},
                {"grant_id": "exact-reservation", "task_id": "T-assignment-basis",
                 "slot": "tests", "attempt": 2},
            ]

    class Connection:
        def execute(self, *_args):
            return Rows()

    monkeypatch.setattr(
        store, "_runner_execution_states_locked",
        lambda _conn, grant_id: [{"state": "PENDING"}],
    )
    monkeypatch.setattr(
        store, "_runner_attempt_successor_eligibility_locked",
        lambda _conn, _task, _slot, _attempt: None,
    )
    try:
        with pytest.raises(StoreError, match="unrelated-predecessor.*PENDING.*blocks"):
            store._guard_runner_task_continuation_locked(
                Connection(), "T-assignment-basis", reservation_grant_id="exact-reservation",
            )
    finally:
        store.close()


def test_started_issuance_with_changed_basis_becomes_unknown_and_is_never_resigned(
    signing_keys, monkeypatch,
):
    from tools.vst import root_dispatch_issuer as issuer_module

    store, supervisor, _policy, _policy_sha, operation_id, _handoff, _live, _issuer = _configured(
        signing_keys,
    )
    original_basis = store.authenticated_assignment_basis
    calls = {"basis": 0, "private_sign": 0}
    original_sign = issuer_module._openssl_signature

    def change_basis_at_sign_boundary(*args, **kwargs):
        calls["basis"] += 1
        snapshot = original_basis(*args, **kwargs)
        if calls["basis"] == 2:
            snapshot = {**snapshot, "handoff": {**snapshot["handoff"], "runner_id": "changed-runner"}}
        return snapshot

    def count_private_sign(*args, **kwargs):
        if kwargs.get("private") is True:
            calls["private_sign"] += 1
        return original_sign(*args, **kwargs)

    monkeypatch.setattr(store, "authenticated_assignment_basis", change_basis_at_sign_boundary)
    monkeypatch.setattr(issuer_module, "_openssl_signature", count_private_sign)
    try:
        with pytest.raises(StoreError, match="failed closed"):
            supervisor.issue_root_dispatch_instruction(assignment_operation_id=operation_id)
        assert calls["private_sign"] == 0
        row = store._conn.execute(
            "SELECT operation_key FROM supervisor_operations WHERE operation=?",
            (ISSUANCE_OPERATION,),
        ).fetchone()
        assert row is not None
        records = store._dispatch_issuance_records_locked(store._conn, row["operation_key"])
        assert records[-1]["event"] == "SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN"

        monkeypatch.setattr(store, "authenticated_assignment_basis", original_basis)
        with pytest.raises(StoreError, match="failed closed"):
            supervisor.issue_root_dispatch_instruction(assignment_operation_id=operation_id)
        assert calls["private_sign"] == 0
    finally:
        store.close()


def test_expired_completed_issuance_replay_never_signs_a_second_time(
    signing_keys, monkeypatch,
):
    from datetime import datetime, timedelta, timezone
    from tools.vst import root_dispatch_issuer as issuer_module, supervisor as supervisor_module

    store, supervisor, _policy, _policy_sha, operation_id, _handoff, _live, _issuer = _configured(
        signing_keys,
    )
    calls = {"private_sign": 0}
    original_sign = issuer_module._openssl_signature

    def count_private_sign(*args, **kwargs):
        if kwargs.get("private") is True:
            calls["private_sign"] += 1
        return original_sign(*args, **kwargs)

    monkeypatch.setattr(issuer_module, "_openssl_signature", count_private_sign)
    try:
        supervisor.issue_root_dispatch_instruction(assignment_operation_id=operation_id)
        assert calls["private_sign"] == 1
        original_datetime = datetime
        expired_now = original_datetime.now(timezone.utc) + timedelta(seconds=180)

        class FrozenFutureDateTime(original_datetime):
            @classmethod
            def now(cls, tz=None):
                return expired_now if tz is None else expired_now.astimezone(tz)

        monkeypatch.setattr(supervisor_module, "datetime", FrozenFutureDateTime)
        with pytest.raises(StoreError, match="failed closed"):
            supervisor.issue_root_dispatch_instruction(assignment_operation_id=operation_id)
        assert calls["private_sign"] == 1
    finally:
        store.close()


@pytest.mark.parametrize("changed_source", ["issuer_config", "trust_registry"])
def test_live_provider_change_between_root_signature_and_admission_refuses_acceptance(
    signing_keys, changed_source,
):
    store, supervisor, _policy, _policy_sha, operation_id, _handoff, live, issuer = _configured(
        signing_keys,
    )
    try:
        envelope = supervisor.issue_root_dispatch_instruction(
            assignment_operation_id=operation_id,
        )
        if changed_source == "issuer_config":
            live["issuer"] = {**issuer, "enabled": False}
        else:
            live["trust"] = {"new-key": {"revoked": True}}
        with pytest.raises(StoreError, match="issuer|registry|trust"):
            supervisor.accept_dispatch_intent(principal="Codex", instruction=envelope)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation='dispatch_intent'",
        ).fetchone()[0] == 0
    finally:
        store.close()


@pytest.mark.parametrize("changed_source", ["issuer_config", "trust_registry"])
def test_live_provider_change_between_acceptance_and_grant_refuses_grant(
    signing_keys, changed_source,
):
    store, supervisor, _policy, operation_id, envelope, _accepted, live, issuer = _issue_and_accept(
        signing_keys,
    )
    try:
        if changed_source == "issuer_config":
            live["issuer"] = {**issuer, "enabled": False}
        else:
            live["trust"] = {"new-key": {"revoked": True}}
        with pytest.raises(StoreError, match="issuer|registry|trust"):
            supervisor.issue_dispatch_intent_grant(request_id=envelope["request_id"])
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation='dispatch_grant'",
        ).fetchone()[0] == 0
    finally:
        store.close()


@pytest.mark.parametrize("stale_authority", ["policy", "generation", "probe", "lease", "budget"])
def test_current_assignment_or_execution_authority_mismatch_refuses_admission(
    signing_keys, stale_authority,
):
    store, supervisor, policy, _policy_sha, _operation_id, handoff, live, _issuer = _configured(
        signing_keys,
    )
    try:
        envelope = supervisor.issue_root_dispatch_instruction(
            assignment_operation_id=handoff["assignment_operation_id"],
        )
        if stale_authority == "policy":
            revoked = copy.deepcopy(policy)
            revoked["revocation_id"] = "fixture-revoked-policy"
            supervisor.assignment_policy_provider = lambda: revoked
        elif stale_authority == "generation":
            supervisor.service_generation_provider = lambda: "fixture-new-generation"
        elif stale_authority == "probe":
            supervisor._probe_consumed = False
        elif stale_authority == "lease":
            store.release_lease(handoff["task_id"], handoff["runner_id"], handoff["epoch"])
        else:
            store._conn.execute(
                "UPDATE budget SET spent=cap+1 WHERE task_id=?", (handoff["task_id"],),
            )
        accepted_before = store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation='dispatch_intent'",
        ).fetchone()[0]
        with pytest.raises((StoreError, ContractError)):
            supervisor.accept_dispatch_intent(principal="Codex", instruction=envelope)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation='dispatch_intent'",
        ).fetchone()[0] == accepted_before
    finally:
        store.close()


@pytest.mark.parametrize("changed_source", ["issuer_config", "trust_registry"])
def test_live_provider_revocation_prevents_new_issuance_without_cached_fallback(
    signing_keys, changed_source,
):
    store, supervisor, _policy, _policy_sha, operation_id, _handoff, live, issuer = _configured(
        signing_keys,
    )
    if changed_source == "issuer_config":
        live["issuer"] = {**issuer, "enabled": False}
    else:
        live["trust"] = {"key-revoked-after-startup": {"revoked": True}}
    try:
        with pytest.raises(StoreError, match="issuer|registry|trust"):
            supervisor.issue_root_dispatch_instruction(assignment_operation_id=operation_id)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation=?",
            (ISSUANCE_OPERATION,),
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_wrong_key_class_is_rejected_before_any_issuance_side_effect(signing_keys):
    from tools.vst.dispatch_issuance import validate_key_binding

    store, _supervisor, _policy, _policy_sha, _operation_id, _handoff, _live, _issuer = _configured(
        signing_keys,
    )
    before = store._conn.execute("SELECT COUNT(*) FROM supervisor_operations").fetchone()[0]
    try:
        with pytest.raises(ContractError, match="DELEGATED_V1"):
            validate_key_binding(_signer_for_wrong_class(signing_keys))
        assert store._conn.execute("SELECT COUNT(*) FROM supervisor_operations").fetchone()[0] == before
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation=?",
            (ISSUANCE_OPERATION,),
        ).fetchone()[0] == 0
    finally:
        store.close()


@pytest.mark.parametrize("request_kind", ["wrong-role", "extra-field", "malformed-id"])
def test_root_issuance_rpc_accepts_only_delegated_issuer_operation_id(
    signing_keys, request_kind,
):
    from tools.vst.supervisor_service import AuthenticatedSupervisorAPI, SupervisorPeer

    store, supervisor, _policy, _policy_sha, operation_id, _handoff, _live, _issuer = _configured(
        signing_keys,
    )
    api = object.__new__(AuthenticatedSupervisorAPI)
    api.supervisor = supervisor
    body = {"assignment_operation_id": operation_id}
    peer = SupervisorPeer(
        "delegated_issuer", 981, 983, "/system.slice/vst-delegated-issuer.service",
        frozenset({"issue_root_dispatch_instruction"}),
    )
    if request_kind == "wrong-role":
        peer = SupervisorPeer(
            "dispatcher", 982, 984, "/system.slice/vst-dispatcher.service",
            frozenset({"issue_root_dispatch_instruction"}),
        )
    elif request_kind == "extra-field":
        body["task_id"] = "caller-selected"
    elif request_kind == "malformed-id":
        body["assignment_operation_id"] = "not-an-operation-id"
    try:
        with pytest.raises((ContractError, StoreError)):
            api._dispatch("issue_root_dispatch_instruction", body, peer)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation=?",
            (ISSUANCE_OPERATION,),
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_root_issuance_rpc_disabled_feature_refuses_without_signing(signing_keys):
    from tools.vst.supervisor_service import AuthenticatedSupervisorAPI, SupervisorPeer

    store, supervisor, _policy, _policy_sha, operation_id, _handoff, live, issuer = _configured(
        signing_keys,
    )
    live["issuer"] = {**issuer, "enabled": False}
    api = object.__new__(AuthenticatedSupervisorAPI)
    api.supervisor = supervisor
    peer = SupervisorPeer(
        "delegated_issuer", 981, 983, "/system.slice/vst-delegated-issuer.service",
        frozenset({"issue_root_dispatch_instruction"}),
    )
    try:
        with pytest.raises(StoreError, match="issuer|configuration|unavailable"):
            api._dispatch(
                "issue_root_dispatch_instruction", {"assignment_operation_id": operation_id}, peer,
            )
        assert store._conn.execute(
            "SELECT COUNT(*) FROM supervisor_operations WHERE operation=?",
            (ISSUANCE_OPERATION,),
        ).fetchone()[0] == 0
    finally:
        store.close()


@pytest.mark.parametrize("boundary", ["claim", "reserve"])
def test_live_revocation_between_grant_and_runner_boundary_refuses_authority(
    signing_keys, boundary,
):
    store, supervisor, _policy, _operation_id, envelope, _accepted, live, issuer = _issue_and_accept(
        signing_keys,
    )
    try:
        grant = supervisor.issue_dispatch_intent_grant(request_id=envelope["request_id"])
        if boundary == "reserve":
            assert supervisor.claim_runner_execution(grant) is None
        live["issuer"] = {**issuer, "enabled": False}
        with pytest.raises(StoreError, match="issuer|trust|delegated"):
            if boundary == "claim":
                supervisor.claim_runner_execution(grant)
            else:
                supervisor.reserve_runner_execution(grant)
        status = store.runner_execution_claim_status(
            grant, active_service_generation=grant["service_generation"],
        )
        assert status["state"] == ("NOT_FOUND" if boundary == "claim" else "PENDING")
    finally:
        store.close()
