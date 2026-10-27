"""Focused safe contracts for the S2 persistent runner boundary."""
from __future__ import annotations

import base64
import copy
import hashlib

import pytest

from tools.vst import contracts
from tools.vst.runner_service import (
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


def _store_with_claim_basis(
    manifest: dict, clock: FakeClock, *, execution_resolution_key: bytes | None = None,
    slots: int = 1,
):
    store = Store(
        ":memory:", clock, event_key=EVENT_KEY,
        execution_resolution_key=execution_resolution_key,
    )
    store.init_slots(slots)
    store.open_story(manifest["story_id"], manifest["project_id"], manifest["phase"])
    epoch = store.acquire_epoch(manifest["story_id"], "test-owner", ttl_sec=1800)
    assert epoch == 2
    store.register_task(manifest)
    store.acquire_lease(
        manifest["task_id"], manifest["story_id"], "runner-1", epoch, 1, 1200,
        supervisor_key=SUPERVISOR_KEY,
    )
    store.ensure_preflight_consumed("run-1", "nonce-1", "a" * 64, "b" * 64)
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


def _make_indeterminate_predecessor(*, reserve: bool = True):
    manifest, *_ = _authority_fixture()
    clock = FakeClock(1000)
    store = _store_with_claim_basis(
        manifest, clock, execution_resolution_key=EXECUTION_RESOLUTION_KEY,
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
        with pytest.raises(StoreError, match="deadline exceeds"):
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
    })()
    server.supervisor = type("Supervisor", (), {
        "previous_receipt": lambda *_args: None,
    })()

    class FakeAuthority:
        def __init__(self, *_args, **_kwargs):
            self.reservation_confirmed = False
            self.completion_confirmed = False

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
    })()
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
    }
    monkeypatch.setattr(runner_service, "_read_root_controlled_json", lambda *_args, **_kwargs: dict(config))

    loaded = load_runner_service_config("/etc/vst-runner/runner-service.json")
    assert loaded.daemon_gid == 988

    missing_gid = dict(config)
    del missing_gid["daemon_gid"]
    monkeypatch.setattr(runner_service, "_read_root_controlled_json", lambda *_args, **_kwargs: missing_gid)
    with pytest.raises(contracts.ContractError, match="fields do not match"):
        load_runner_service_config("/etc/vst-runner/runner-service.json")


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


def _fake_execution_authority(grant, *, claim, claim_status, reserve, monkeypatch):
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
    authority._reserve = reserve
    authority._complete = lambda _grant, _receipt: None
    authority._claimed = False
    authority._reserved = False
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
    store, manifest, clock, grant, predecessor_state = _make_indeterminate_predecessor()
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
    store, manifest, clock, grant, predecessor_state = _make_indeterminate_predecessor(reserve=False)
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
