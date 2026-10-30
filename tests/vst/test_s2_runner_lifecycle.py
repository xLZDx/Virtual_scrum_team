"""S2 runner boundary and supervisor lifecycle journeys."""
from __future__ import annotations

import os
import hashlib
import inspect
import io
import json
import sqlite3
import struct
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from tools.vst import contracts
from tools.vst import runner
from tools.vst.lifecycle import STOP_TRANSITIONS, transition
from tools.vst.runner import _derive_head, run_manifest_commands
from tools.vst.signer import AuthenticatedSigner, validate_signing_request
from tools.vst.signing import (
    DIFF_GATE_LABEL, RECEIPT_V2_LABEL, REVIEWER_LABEL, REVIEWER_REGISTRY_LABEL,
    OPERATOR_MANUAL_OVERRIDE_LABEL, SIGNING_REQUEST_LABEL, sign, verify,
)
from tools.vst.supervisor import Supervisor
from tools.vst.store import ACTION_RESOLUTION_LABEL, Store, StoreError
from tests.vst.e1e4_helpers import (
    EVENT_KEY, KEY, OPERATOR_KEY, SUPERVISOR_KEY, TASK,
    manifest as base_manifest, unsigned_receipt,
)


KEY = b"s2-test-runner-key-0123456789-abcdef"
EVENT = b"s2-test-event-key-0123456789-abcdef"
SIGNER_KEY = b"s2-test-isolated-signer-key-0123456789"
_WORKER_HELPER_HEAD = "a" * 40
_WORKER_HELPER_PATH = "/usr/local/libexec/vst-s4-worker-exec-" + _WORKER_HELPER_HEAD


def signed_action_resolution(action_id, action, attempt, completed, resolution_id, *, key=OPERATOR_KEY):
    body = {
        "action_id": action_id,
        "action": action,
        "attempt": attempt,
        "completed": completed,
        "resolution_id": resolution_id,
        "evidence_sha256": "e" * 64,
    }
    return {**body, "signature": sign(body, key, ACTION_RESOLUTION_LABEL)}


class Backend:
    def __init__(self, remote: str, repo: str | None = None):
        self.remote = remote
        self.repo = repo
        self.calls: list[tuple[str, str]] = []

    def push(self, payload: dict, *, operation_key: str):
        self.calls.append(("push", operation_key))
        if self.repo is None:
            raise AssertionError("local synthetic repo is required to populate bare remote objects")
        subprocess.run(["git", "-C", self.repo, "push", self.remote,
                        f"{payload['head']}:refs/heads/{payload['branch']}"], check=True, capture_output=True)
        return {"head": payload["head"]}

    def open_pull_request(self, payload: dict, *, operation_key: str):
        self.calls.append(("pull_request", operation_key))
        return {"number": len(self.calls), **payload}


def git(*args: str, cwd: str | None = None) -> str:
    result = subprocess.run(["git", *( ["-C", cwd] if cwd else []), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def test_lifecycle_transition_table_rejects_unlisted_pairs():
    assert set(STOP_TRANSITIONS) == {
        ("RUNNING", "STOP"), ("STOPPING", "CLEANUP_COMPLETE"),
        ("STOPPED", "RESUME"), ("RUNNING", "ROLLBACK"),
        ("ROLLING_BACK", "CLEANUP_COMPLETE"), ("READY", "START"),
    }
    for (state, event), row in STOP_TRANSITIONS.items():
        next_state, cleanup = transition(state, event)
        assert (next_state, cleanup) == (row["next_state"], row["cleanup_action"])
        assert row["trigger"] == "supervisor"
    with pytest.raises(ValueError, match="unsupported lifecycle transition"):
        transition("READY", "STOP")


def _manual_override_record(
    episode_id, config_id="breaker-config-v1", *, record_id="override-1",
    verdict="REVIEW_REQUIRED",
):
    body = {
        "id": record_id,
        "action": "manual_override",
        "breaker_state": "PAUSED_PROVIDER",
        "breaker_episode_id": episode_id,
        "breaker_config_id": config_id,
        "verdict": verdict,
        "evidence_sha256": "d" * 64,
    }
    return {**body, "signature": sign(body, OPERATOR_KEY, OPERATOR_MANUAL_OVERRIDE_LABEL)}


def _paused_supervisor(tmp_path, *, record_sink=None):
    db = tmp_path / "state.db"
    store = Store(str(db), event_key=EVENT)
    supervisor = Supervisor(
        store, operation_backend=object(), failure_threshold=2,
        manual_override_recorder=record_sink or (lambda record: None),
        operator_key=OPERATOR_KEY,
    )
    supervisor.provider_failed("override-episode-failure-1")
    supervisor.provider_failed("override-episode-failure-2")
    return store, supervisor


def test_breaker_requires_operator_signed_override_bound_to_active_episode(tmp_path):
    recorded = []
    store, supervisor = _paused_supervisor(tmp_path, record_sink=recorded.append)
    try:
        started = []
        with pytest.raises(StoreError, match="breaker is open"):
            supervisor.start_worker(lambda: started.append(True))
        assert started == []

        valid = _manual_override_record("override-episode-failure-2")
        unsigned = {key: value for key, value in valid.items() if key != "signature"}
        with pytest.raises(StoreError, match="signature must bind|signature is invalid"):
            supervisor.manual_override(unsigned)

        tampered = {**valid, "verdict": "REVIEW_DEFERRED"}
        with pytest.raises(StoreError, match="signature is invalid"):
            supervisor.manual_override(tampered)
        plain_approve = _manual_override_record(
            "override-episode-failure-2", record_id="override-approve", verdict="APPROVE",
        )
        with pytest.raises(StoreError, match="cannot be represented as plain APPROVE"):
            supervisor.manual_override(plain_approve)

        for wrong_episode, wrong_config in (
            ("some-other-episode", "breaker-config-v1"),
            ("override-episode-failure-2", "some-other-config"),
        ):
            wrong = _manual_override_record(wrong_episode, wrong_config)
            with pytest.raises(StoreError, match="stale for the current breaker episode"):
                supervisor.manual_override(wrong)
        assert recorded == []

        supervisor.manual_override(valid)
        assert recorded == [valid]
        assert supervisor.breaker_state == "CLOSED"
        assert supervisor.start_worker(lambda: "started") == "started"
    finally:
        store.close()


def test_manual_override_replay_is_stale_after_a_later_breaker_episode(tmp_path):
    store, supervisor = _paused_supervisor(tmp_path)
    try:
        original = _manual_override_record("override-episode-failure-2")
        supervisor.manual_override(original)
        supervisor.provider_failed("override-episode-failure-3")
        supervisor.provider_failed("override-episode-failure-4")
        assert supervisor.breaker_state == "PAUSED_PROVIDER"
        with pytest.raises(StoreError, match="prior override cannot clear a later breaker episode"):
            supervisor.manual_override(original)
    finally:
        store.close()


def test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it(tmp_path):
    db = tmp_path / "durable-breaker.db"
    store = Store(str(db), event_key=EVENT)
    supervisor = Supervisor(store, operation_backend=object(), failure_threshold=2)
    supervisor.provider_failed("provider-failure-1")
    supervisor.provider_failed("provider-failure-2")
    assert supervisor.breaker_state == "PAUSED_PROVIDER"
    store.close()

    restarted_store = Store(str(db), event_key=EVENT)
    restarted = Supervisor(restarted_store, operation_backend=object(), failure_threshold=2)
    assert restarted.breaker_state == "PAUSED_PROVIDER"
    assert restarted.provider_failures == 2
    started = []
    with pytest.raises(StoreError, match="breaker is open"):
        restarted.start_worker(lambda: started.append(True))
    assert not started

    before = restarted_store.control_events()
    restarted.provider_succeeded("provider-success-after-pause")
    assert restarted.breaker_state == "PAUSED_PROVIDER"
    assert restarted_store.control_events() == before
    restarted_store.close()

    final_store = Store(str(db), event_key=EVENT)
    try:
        final = Supervisor(final_store, operation_backend=object(), failure_threshold=2)
        assert final.breaker_state == "PAUSED_PROVIDER"
        assert final.provider_failures == 2
    finally:
        final_store.close()


def test_stale_second_supervisor_cannot_start_after_peer_opens_persisted_breaker(tmp_path):
    db = tmp_path / "stale-breaker-start.db"
    store_a = Store(str(db), event_key=EVENT)
    store_b = Store(str(db), event_key=EVENT)
    try:
        first = Supervisor(store_a, operation_backend=object(), failure_threshold=2)
        stale = Supervisor(store_b, operation_backend=object(), failure_threshold=2)
        assert stale.breaker_state == "CLOSED"
        first.provider_failed("stale-test-failure-1")
        first.provider_failed("stale-test-failure-2")
        assert first.breaker_state == "PAUSED_PROVIDER"
        assert stale.breaker_state == "CLOSED"  # Cached view is intentionally stale.

        started = []
        with pytest.raises(StoreError, match="breaker is open"):
            stale.start_worker(lambda: started.append(True), action_id="stale-breaker-start")
        assert started == []
    finally:
        store_b.close()
        store_a.close()


def test_failed_start_side_effect_blocks_restart_until_verified_reconciliation(tmp_path):
    db = tmp_path / "unresolved-start.db"
    store = Store(str(db), event_key=EVENT)
    supervisor = Supervisor(store, operation_backend=object(), operator_key=OPERATOR_KEY)
    side_effects = []

    def start_then_raise():
        side_effects.append("started")
        raise RuntimeError("callback failed after side effect")

    with pytest.raises(RuntimeError, match="after side effect"):
        supervisor.start_worker(start_then_raise, action_id="start-uncertain-1")
    assert side_effects == ["started"]
    assert supervisor.lifecycle_state == "BLOCKED_RECOVERY"
    store.close()

    restarted_store = Store(str(db), event_key=EVENT)
    try:
        restarted = Supervisor(restarted_store, operation_backend=object(), operator_key=OPERATOR_KEY)
        assert restarted.lifecycle_state == "BLOCKED_RECOVERY"
        attempted = []
        with pytest.raises(StoreError, match="requires reconciliation"):
            restarted.start_worker(lambda: attempted.append("must-not-run"), action_id="start-new")
        assert attempted == []

        restarted.reconcile_action(
            "start-uncertain-1", completed=True, resolution_id="verified-worker-start-1",
            resolution_record=signed_action_resolution(
                "start-uncertain-1", "start", 1, True, "verified-worker-start-1",
            ),
        )
        assert restarted.lifecycle_state == "RUNNING"
        assert side_effects == ["started"]
    finally:
        restarted_store.close()


def test_reconciliation_rejects_unsigned_false_and_accepts_signed_operator_resolution(tmp_path):
    db = tmp_path / "signed-reconciliation.db"
    store = Store(str(db), event_key=EVENT)
    supervisor = Supervisor(store, operation_backend=object(), operator_key=OPERATOR_KEY)

    def no_effect_failure():
        raise RuntimeError("confirmed no start effect")

    with pytest.raises(RuntimeError, match="no start effect"):
        supervisor.start_worker(no_effect_failure, action_id="reconcile-false-start")
    assert supervisor.lifecycle_state == "BLOCKED_RECOVERY"

    with pytest.raises(StoreError, match="operator-signed reconciliation record is required"):
        supervisor.reconcile_action(
            "reconcile-false-start", completed=False, resolution_id="unsigned-no-effect",
        )

    forged = signed_action_resolution(
        "reconcile-false-start", "start", 1, False, "forged-no-effect", key=b"wrong-operator-key-0123456789-abcdef",
    )
    with pytest.raises(StoreError, match="signature is invalid"):
        supervisor.reconcile_action(
            "reconcile-false-start", completed=False, resolution_id="forged-no-effect",
            resolution_record=forged,
        )
    assert supervisor.lifecycle_state == "BLOCKED_RECOVERY"

    resolution_id = "operator-confirmed-no-effect"
    supervisor.reconcile_action(
        "reconcile-false-start", completed=False, resolution_id=resolution_id,
        resolution_record=signed_action_resolution(
            "reconcile-false-start", "start", 1, False, resolution_id,
        ),
    )
    assert supervisor.lifecycle_state == "READY"
    callback_calls = []
    assert supervisor.start_worker(
        lambda: callback_calls.append("retry") or "started",
        action_id="reconcile-false-start",
    ) == "started"
    assert callback_calls == ["retry"]
    store.close()


def test_replay_keeps_invalid_legacy_reconciliation_unresolved(tmp_path):
    db = tmp_path / "legacy-reconciliation.db"
    store = Store(str(db), event_key=EVENT)
    supervisor = Supervisor(store, operation_backend=object(), operator_key=OPERATOR_KEY)
    with pytest.raises(RuntimeError, match="legacy simulated failure"):
        supervisor.start_worker(
            lambda: (_ for _ in ()).throw(RuntimeError("legacy simulated failure")),
            action_id="legacy-start-action",
        )

    store._append_control_event(
        "CONTROL_ACTION_RECONCILED", "legacy-unverified-resolution",
        {
            "action_id": "legacy-start-action", "action": "start", "attempt": 1,
            "completed": False, "resolution_id": "arbitrary-legacy-claim",
            "group_id": "legacy-start-action",
        },
    )
    store.close()

    restarted_store = Store(str(db), event_key=EVENT)
    try:
        restarted = Supervisor(restarted_store, operation_backend=object(), operator_key=OPERATOR_KEY)
        assert restarted.lifecycle_state == "BLOCKED_RECOVERY"
        assert restarted._action_status["legacy-start-action"]["status"] == "unknown"
        callback_calls = []
        with pytest.raises(StoreError, match="requires reconciliation"):
            restarted.start_worker(lambda: callback_calls.append(True), action_id="new-start-after-legacy")
        assert callback_calls == []
    finally:
        restarted_store.close()


@pytest.mark.parametrize("flow", ["stop", "rollback"])
def test_restart_resumes_the_correct_cleanup_phase_after_reconciliation(tmp_path, flow):
    db = tmp_path / f"{flow}-cleanup-recovery.db"
    store = Store(str(db), event_key=EVENT)
    supervisor = Supervisor(store, operation_backend=object(), operator_key=OPERATOR_KEY)
    supervisor.start_worker(lambda: "started", action_id=f"{flow}-initial-start")
    primary_calls = []
    cleanup_calls = []

    def primary_action():
        primary_calls.append(flow)

    def cleanup_action():
        cleanup_calls.append(flow)
        if len(cleanup_calls) == 1:
            raise RuntimeError("cleanup did not complete")

    with pytest.raises(RuntimeError, match="cleanup did not complete"):
        if flow == "stop":
            supervisor.stop(primary_action, cleanup_action, action_id=f"{flow}-action-1")
        else:
            supervisor.rollback(primary_action, cleanup_action, action_id=f"{flow}-action-1")
    assert primary_calls == [flow]
    assert cleanup_calls == [flow]
    store.close()

    restarted_store = Store(str(db), event_key=EVENT)
    try:
        restarted = Supervisor(restarted_store, operation_backend=object(), operator_key=OPERATOR_KEY)
        assert restarted.lifecycle_state == "BLOCKED_RECOVERY"
        restarted.reconcile_action(
            f"{flow}-action-1", completed=False, resolution_id=f"verified-{flow}-cleanup-not-complete",
            resolution_record=signed_action_resolution(
                f"{flow}-action-1:cleanup",
                "stop_cleanup" if flow == "stop" else "rollback_cleanup",
                1, False, f"verified-{flow}-cleanup-not-complete",
            ),
        )
        expected_phase = "STOPPING" if flow == "stop" else "ROLLING_BACK"
        assert restarted.lifecycle_state == expected_phase

        if flow == "stop":
            restarted.stop(primary_action, cleanup_action)
        else:
            restarted.rollback(primary_action, cleanup_action)
        assert restarted.lifecycle_state == "STOPPED"
        assert primary_calls == [flow]
        assert cleanup_calls == [flow, flow]
    finally:
        restarted_store.close()


def test_two_cached_ready_supervisors_allow_only_one_concurrent_start_callback(tmp_path):
    db = tmp_path / "concurrent-supervisor-start.db"
    store_a = Store(str(db), event_key=EVENT)
    supervisor_a = Supervisor(store_a, operation_backend=object())
    ready_b = threading.Event()
    first_callback_entered = threading.Event()
    second_attempt_done = threading.Event()
    callbacks = []
    second_results = []

    def run_supervisor_b():
        store_b = Store(str(db), event_key=EVENT)
        try:
            supervisor_b = Supervisor(store_b, operation_backend=object())
            assert supervisor_b.lifecycle_state == "READY"
            ready_b.set()
            assert first_callback_entered.wait(timeout=10)
            try:
                supervisor_b.start_worker(
                    lambda: callbacks.append("b"), action_id="concurrent-start-b",
                )
            except BaseException as exc:
                second_results.append(exc)
            else:
                second_results.append("started")
        finally:
            second_attempt_done.set()
            store_b.close()

    thread_b = threading.Thread(target=run_supervisor_b)
    thread_b.start()
    assert ready_b.wait(timeout=10)
    assert supervisor_a.lifecycle_state == "READY"

    def first_start_callback():
        callbacks.append("a")
        first_callback_entered.set()
        assert second_attempt_done.wait(timeout=10)
        return "started-a"

    try:
        assert supervisor_a.start_worker(
            first_start_callback, action_id="concurrent-start-a",
        ) == "started-a"
    finally:
        thread_b.join(timeout=15)
        store_a.close()

    assert not thread_b.is_alive()
    assert callbacks == ["a"]
    assert len(second_results) == 1
    assert isinstance(second_results[0], StoreError)


def test_idempotent_push_and_pull_request_use_local_bare_remote(tmp_path):
    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    repo.mkdir()
    git("init", cwd=str(repo))
    git("config", "user.name", "Synthetic", cwd=str(repo))
    git("config", "user.email", "synthetic@example.invalid", cwd=str(repo))
    (repo / "note.txt").write_text("synthetic\n", encoding="utf-8")
    git("add", "note.txt", cwd=str(repo)); git("commit", "-m", "synthetic", cwd=str(repo))
    head = git("rev-parse", "HEAD", cwd=str(repo))
    with Store(str(tmp_path / "state.db"), event_key=EVENT) as store:
        backend = Backend(str(remote), str(repo))
        supervisor = Supervisor(store, operation_backend=backend)
        payload = {"branch": "s2-candidate", "head": head}
        first = supervisor.simulate_push("push-1", payload)
        again = supervisor.simulate_push("push-1", payload)
        assert first == again and backend.calls == [("push", "push-1")]
        assert git("--git-dir", str(remote), "rev-parse", "refs/heads/s2-candidate") == head
        pr = {"head": head, "title": "Synthetic"}
        assert supervisor.simulate_pull_request("pr-1", pr) == supervisor.simulate_pull_request("pr-1", pr)
        assert [kind for kind, _ in backend.calls] == ["push", "pull_request"]
        with pytest.raises(StoreError):
            supervisor.simulate_push("push-1", {"branch": "other", "head": head})


def test_external_backend_callback_runs_outside_store_anchor_transaction(tmp_path):
    db, anchor_path = tmp_path / "external-callback.db", tmp_path / "external-callback.anchor"
    primary = Store(str(db), event_key=EVENT, anchor_path=str(anchor_path), busy_timeout_sec=1)
    callback_write_finished = threading.Event()
    callback_errors = []

    class ConcurrentBackend:
        def push(self, payload, *, operation_key):
            def write_from_other_store():
                independent = None
                try:
                    independent = Store(str(db), event_key=EVENT, anchor_path=str(anchor_path), busy_timeout_sec=1)
                    independent.record_event("concurrent", "observer", "NOTE", {"operation": operation_key})
                except BaseException as exc:
                    callback_errors.append(exc)
                finally:
                    if independent is not None:
                        independent.close()
                    callback_write_finished.set()

            writer = threading.Thread(target=write_from_other_store, daemon=True)
            writer.start()
            assert callback_write_finished.wait(timeout=5), "independent Store write waited behind backend transaction"
            writer.join(timeout=1)
            assert not writer.is_alive()
            return {"operation_key": operation_key, "head": payload["head"]}

    try:
        supervisor = Supervisor(primary, operation_backend=ConcurrentBackend())
        result = supervisor.simulate_push("outside-tx-push", {"head": "a" * 40})
        assert result["operation_key"] == "outside-tx-push"
        assert callback_errors == []
        assert primary.verify_event_chain()
    finally:
        primary.close()


def _synthetic_git_source(tmp_path, *, filename="candidate.txt"):
    from tools.vst.slice import SyntheticOperationBackend

    remote, repo = tmp_path / "target.git", tmp_path / "source"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    repo.mkdir()
    git("init", cwd=str(repo))
    git("config", "user.name", "Synthetic", cwd=str(repo))
    git("config", "user.email", "synthetic@example.invalid", cwd=str(repo))
    (repo / filename).write_text("base commit\n", encoding="utf-8")
    git("add", filename, cwd=str(repo))
    git("commit", "-m", "base", cwd=str(repo))
    return remote, repo, SyntheticOperationBackend(
        str(remote), source_repo=str(repo), command_timeout_sec=10,
    )


class _FakeBoundedGitStream:
    def __init__(self, *, fail_read=False):
        self.fail_read = fail_read
        self.closed = False

    def read(self, _size):
        if self.fail_read:
            raise OSError("injected pipe read failure")
        return b""

    def close(self):
        self.closed = True


class _FakeBoundedGitProcess:
    def __init__(self, *, fail_stdout_read=False):
        self.stdout = _FakeBoundedGitStream(fail_read=fail_stdout_read)
        self.stderr = _FakeBoundedGitStream()
        self._finished = threading.Event()
        self.waited = False

    def poll(self):
        return -9 if self._finished.is_set() else None

    def kill(self):
        self._finished.set()

    def wait(self, timeout=None):
        if not self._finished.wait(timeout):
            raise subprocess.TimeoutExpired(["fake-bounded-git"], timeout)
        self.waited = True
        return -9


def _bare_bounded_git_backend(tmp_path):
    from tools.vst.slice import SyntheticOperationBackend

    return SyntheticOperationBackend(
        str(tmp_path / "unused-target.git"),
        source_repo=str(tmp_path / "unused-source"),
        command_timeout_sec=1,
    )


def test_bounded_git_reader_start_failure_kills_reaps_and_closes(monkeypatch, tmp_path):
    """VST-017: startup failure cannot bypass bounded child cleanup."""
    from tools.vst import slice as slice_module

    backend = _bare_bounded_git_backend(tmp_path)
    process = _FakeBoundedGitProcess()
    monkeypatch.setattr(slice_module.subprocess, "Popen", lambda *args, **kwargs: process)

    def fail_thread_start(_thread):
        raise RuntimeError("injected reader startup failure")

    monkeypatch.setattr(slice_module.threading.Thread, "start", fail_thread_start)
    with pytest.raises(RuntimeError, match="injected reader startup failure"):
        backend._run_bounded_git(["git", "--version"], env={})

    assert process.poll() == -9 and process.waited
    assert process.stdout.closed and process.stderr.closed


def test_bounded_git_thread_constructor_failure_kills_reaps_and_closes(monkeypatch, tmp_path):
    """VST-017: reader thread construction failure cannot bypass child cleanup."""
    from tools.vst import slice as slice_module

    backend = _bare_bounded_git_backend(tmp_path)
    process = _FakeBoundedGitProcess()
    monkeypatch.setattr(slice_module.subprocess, "Popen", lambda *args, **kwargs: process)

    def fail_thread_constructor(*args, **kwargs):
        raise MemoryError("injected thread construction failure")

    monkeypatch.setattr(slice_module.threading, "Thread", fail_thread_constructor)
    with pytest.raises(MemoryError, match="injected thread construction failure"):
        backend._run_bounded_git(["git", "--version"], env={})

    assert process.poll() == -9 and process.waited
    assert process.stdout.closed and process.stderr.closed


def test_bounded_git_reader_failure_kills_reaps_and_fails_closed(monkeypatch, tmp_path):
    """VST-017: pipe read failure cannot produce a successful partial result."""
    from tools.vst import slice as slice_module

    backend = _bare_bounded_git_backend(tmp_path)
    process = _FakeBoundedGitProcess(fail_stdout_read=True)
    monkeypatch.setattr(slice_module.subprocess, "Popen", lambda *args, **kwargs: process)

    with pytest.raises(RuntimeError, match="stdout capture failed"):
        backend._run_bounded_git(["git", "--version"], env={})

    assert process.poll() == -9 and process.waited
    assert process.stdout.closed and process.stderr.closed


def test_hook_free_publication_transfers_source_only_commit_without_running_pre_push(tmp_path, monkeypatch):
    from tools.vst import slice as slice_module

    remote, repo, backend = _synthetic_git_source(tmp_path)
    head = git("rev-parse", "HEAD", cwd=str(repo))
    source_only = subprocess.run(
        ["git", "--git-dir", str(remote), "cat-file", "-e", f"{head}^{{commit}}"],
        capture_output=True, check=False,
    )
    assert source_only.returncode != 0

    hook = repo / ".git" / "hooks" / "pre-push"
    marker = repo / "pre-push-marker"
    hook.write_text("#!/bin/sh\nprintf invoked > pre-push-marker\n", encoding="utf-8")
    os.chmod(hook, 0o755)

    hook_validation_remote = tmp_path / "hook-validation.git"
    subprocess.run(["git", "init", "--bare", str(hook_validation_remote)], check=True, capture_output=True)
    git("remote", "add", "hook-validation", str(hook_validation_remote), cwd=str(repo))
    git("push", "hook-validation", "HEAD:refs/heads/validation", cwd=str(repo))
    assert marker.read_text(encoding="utf-8").strip() == "invoked"
    marker.unlink()

    for name, value in {
        "pack.threads": "64",
        "pack.windowMemory": "1g",
        "pack.window": "999",
        "pack.deltaCacheSize": "1073741824",
        "pack.deltaCacheLimit": "1073741824",
    }.items():
        git("config", name, value, cwd=str(repo))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "pack.threads")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "64")
    real_popen = slice_module.subprocess.Popen
    captured_source = {}

    def capture_source_pack(command, *args, **kwargs):
        if "pack-objects" in command:
            captured_source["command"] = list(command)
            captured_source["env"] = dict(kwargs["env"])
        return real_popen(command, *args, **kwargs)

    monkeypatch.setattr(slice_module.subprocess, "Popen", capture_source_pack)

    result = backend.push({"branch": "candidate", "head": head}, operation_key="publish-source-only")

    assert result == {
        "operation_key": "publish-source-only",
        "ref": "refs/heads/candidate",
        "head": head,
    }
    assert git("--git-dir", str(remote), "rev-parse", "refs/heads/candidate") == head
    assert git("--git-dir", str(remote), "cat-file", "-t", head) == "commit"
    assert not marker.exists(), "source-controlled pre-push hook executed during publication"
    source_command = captured_source["command"]
    for option in (
        ("-c", "pack.threads=1"), ("-c", "pack.windowMemory=16m"),
        ("-c", "pack.window=10"), ("-c", "pack.deltaCacheSize=16777216"),
        ("-c", "pack.deltaCacheLimit=32768"),
    ):
        assert any(source_command[index:index + 2] == list(option) for index in range(len(source_command) - 1))
    source_env = captured_source["env"]
    assert source_env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert source_env["GIT_CONFIG_GLOBAL"] == os.devnull
    snapshot_objects = source_env["GIT_OBJECT_DIRECTORY"]
    assert ".vst-source-snapshot-" in snapshot_objects
    assert os.path.realpath(snapshot_objects) != os.path.realpath(repo / ".git" / "objects")
    assert source_env["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert source_env["GIT_NO_LAZY_FETCH"] == "1"
    assert "GIT_CONFIG_COUNT" not in source_env
    assert "GIT_CONFIG_KEY_0" not in source_env
    assert "GIT_CONFIG_VALUE_0" not in source_env


def test_source_object_alternates_are_rejected_before_pack_or_index_writer(tmp_path, monkeypatch):
    from tools.vst import slice as slice_module

    remote, repo, backend = _synthetic_git_source(tmp_path, filename="alternate.txt")
    head = git("rev-parse", "HEAD", cwd=str(repo))
    foreign = tmp_path / "foreign-objects.git"
    subprocess.run(["git", "init", "--bare", str(foreign)], check=True, capture_output=True)
    alternates = repo / ".git" / "objects" / "info" / "alternates"
    alternates.parent.mkdir(exist_ok=True)
    alternates.write_text(str(foreign / "objects") + "\n", encoding="utf-8")
    real_popen = slice_module.subprocess.Popen
    writers = []

    def reject_if_writer(command, *args, **kwargs):
        if "pack-objects" in command or "index-pack" in command:
            writers.append(list(command))
            raise AssertionError("object writer started before alternate rejection")
        return real_popen(command, *args, **kwargs)

    monkeypatch.setattr(slice_module.subprocess, "Popen", reject_if_writer)
    with pytest.raises(RuntimeError, match="synthetic source object alternates are unsupported"):
        backend.push({"branch": "alternate", "head": head}, operation_key="alternate-source")
    assert writers == []


def test_bounded_source_preflight_rejects_before_pack_or_index_writer(tmp_path, monkeypatch):
    from tools.vst import slice as slice_module

    _, repo, backend = _synthetic_git_source(tmp_path, filename="preflight.txt")
    head = git("rev-parse", "HEAD", cwd=str(repo))
    backend._MAX_SOURCE_OBJECT_COUNT = 0
    real_popen = slice_module.subprocess.Popen
    writers = []

    def reject_if_writer(command, *args, **kwargs):
        if "pack-objects" in command or "index-pack" in command:
            writers.append(list(command))
            raise AssertionError("object writer started before source preflight rejection")
        return real_popen(command, *args, **kwargs)

    monkeypatch.setattr(slice_module.subprocess, "Popen", reject_if_writer)
    with pytest.raises(RuntimeError, match="source repository exceeds the 250,000 object limit"):
        backend.push({"branch": "too-many", "head": head}, operation_key="source-count-cap")
    assert writers == []


@pytest.mark.parametrize("state", [b"I", b"P"], ids=["in-progress-promotes-to-poisoned", "already-poisoned"])
def test_poisoned_or_interrupted_target_refuses_before_object_writer(tmp_path, monkeypatch, state):
    from tools.vst import slice as slice_module

    remote, repo, backend = _synthetic_git_source(tmp_path, filename="poison.txt")
    head = git("rev-parse", "HEAD", cwd=str(repo))
    lock_path = remote / ".vst-object-storage.lock"
    lock_path.write_bytes(b"\0" + state)
    real_run = slice_module.subprocess.run
    real_popen = slice_module.subprocess.Popen
    commands = []
    writers = []

    def capture_run(command, *args, **kwargs):
        commands.append(list(command))
        return real_run(command, *args, **kwargs)

    def reject_writer(command, *args, **kwargs):
        if "pack-objects" in command or "index-pack" in command:
            writers.append(list(command))
            raise AssertionError("object writer started on poisoned target")
        return real_popen(command, *args, **kwargs)

    monkeypatch.setattr(slice_module.subprocess, "run", capture_run)
    monkeypatch.setattr(slice_module.subprocess, "Popen", reject_writer)
    with pytest.raises(StoreError, match="synthetic target.*poisoned|interrupted object write"):
        backend.push({"branch": "blocked", "head": head}, operation_key="poison-refusal")
    assert not any("hash-object" in command for command in commands)
    assert writers == []
    assert lock_path.read_bytes()[1:2] == b"P"


def test_synthetic_backend_fast_forward_and_conflicting_branch_and_pr_refs(tmp_path):
    remote, repo, backend = _synthetic_git_source(tmp_path)
    base_head = git("rev-parse", "HEAD", cwd=str(repo))
    first = backend.push({"branch": "candidate", "head": base_head}, operation_key="branch-base")
    assert git("--git-dir", str(remote), "rev-parse", first["ref"]) == base_head

    (repo / "candidate.txt").write_text("fast-forward commit\n", encoding="utf-8")
    git("add", "candidate.txt", cwd=str(repo))
    git("commit", "-m", "fast-forward", cwd=str(repo))
    fast_forward_head = git("rev-parse", "HEAD", cwd=str(repo))
    fast_forward = backend.push(
        {"branch": "candidate", "head": fast_forward_head}, operation_key="branch-fast-forward",
    )
    assert fast_forward["head"] == fast_forward_head
    assert git("--git-dir", str(remote), "rev-parse", fast_forward["ref"]) == fast_forward_head

    git("branch", "divergent", base_head, cwd=str(repo))
    git("checkout", "divergent", cwd=str(repo))
    (repo / "divergent.txt").write_text("divergent commit\n", encoding="utf-8")
    git("add", "divergent.txt", cwd=str(repo))
    git("commit", "-m", "divergent", cwd=str(repo))
    divergent_head = git("rev-parse", "HEAD", cwd=str(repo))
    with pytest.raises(StoreError, match="not a fast-forward"):
        backend.push({"branch": "candidate", "head": divergent_head}, operation_key="branch-divergent")
    assert git("--git-dir", str(remote), "rev-parse", "refs/heads/candidate") == fast_forward_head

    pr_payload = {"head": base_head, "title": "Synthetic PR"}
    pr_result = backend.open_pull_request(pr_payload, operation_key="pr-stable-key")
    assert git("--git-dir", str(remote), "rev-parse", pr_result["ref"]) == base_head
    assert backend.open_pull_request(pr_payload, operation_key="pr-stable-key") == pr_result
    with pytest.raises(StoreError, match="remote idempotency key reused with different payload"):
        backend.open_pull_request(
            {"head": fast_forward_head, "title": "Changed PR"}, operation_key="pr-stable-key",
        )
    assert git("--git-dir", str(remote), "rev-parse", pr_result["ref"]) == base_head

    conflicting_pr_key = "pr-ref-conflict"
    conflicting_pr_ref = (
        "refs/pull-requests/"
        + hashlib.sha256(conflicting_pr_key.encode("utf-8")).hexdigest()[:20]
        + "/head"
    )
    git("--git-dir", str(remote), "update-ref", conflicting_pr_ref, fast_forward_head)
    with pytest.raises(StoreError, match="pull-request key already points at a different head"):
        backend.open_pull_request(
            {"head": base_head, "title": "Conflicting existing ref"},
            operation_key=conflicting_pr_key,
        )
    assert git("--git-dir", str(remote), "rev-parse", conflicting_pr_ref) == fast_forward_head


def test_cumulative_target_storage_cap_rejects_before_pack_process_starts(tmp_path, monkeypatch):
    from tools.vst import slice as slice_module

    remote, repo, backend = _synthetic_git_source(tmp_path, filename="cap.txt")
    head = git("rev-parse", "HEAD", cwd=str(repo))
    payload = {"branch": "capped", "head": head}
    # Persist the operation binding first so publication reaches the pack preflight.
    backend._bind_operation("push", "cap-operation", payload)
    current_bytes = backend._target_object_storage_bytes()
    backend._MAX_PACK_BYTES = 64
    backend._MAX_PACK_INDEX_BYTES = 64
    backend._MAX_TARGET_OBJECT_STORAGE_BYTES = current_bytes + 127
    real_popen = slice_module.subprocess.Popen
    pack_processes = []

    def forbid_pack_process(command, *args, **kwargs):
        if "pack-objects" in command or "index-pack" in command:
            pack_processes.append(list(command))
            raise AssertionError("pack process started despite cumulative-storage preflight rejection")
        return real_popen(command, *args, **kwargs)

    monkeypatch.setattr(slice_module.subprocess, "Popen", forbid_pack_process)
    with pytest.raises(StoreError, match="synthetic target object storage cap would be exceeded"):
        backend.push(payload, operation_key="cap-operation")
    assert pack_processes == []
    assert backend._target_object_storage_bytes() == current_bytes
    with pytest.raises(RuntimeError):
        backend.ref_head("refs/heads/capped")


def test_target_storage_lock_times_out_on_another_process_then_releases_normally(tmp_path):
    from tools.vst.slice import SyntheticOperationBackend

    remote = tmp_path / "storage-lock.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    backend = SyntheticOperationBackend(
        str(remote), source_repo=str(remote), command_timeout_sec=1,
    )
    lock_path = remote / ".vst-object-storage.lock"
    with backend._target_storage_lock():
        pass

    child_code = r'''import os, sys
path = sys.argv[1]
stream = open(path, "a+b")
if os.fstat(stream.fileno()).st_size == 0:
    stream.write(b"\0")
    stream.flush()
stream.seek(0)
if os.name == "nt":
    import msvcrt
    msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
else:
    import fcntl
    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
print("LOCKED", flush=True)
sys.stdin.readline()
stream.seek(0)
if os.name == "nt":
    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
else:
    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
stream.close()
'''
    child = subprocess.Popen(
        [sys.executable, "-c", child_code, str(lock_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout.readline().strip() == "LOCKED"
        with pytest.raises(TimeoutError, match="timed out waiting for synthetic target storage lock"):
            with backend._target_storage_lock():
                pass
    finally:
        if child.stdin is not None and not child.stdin.closed:
            child.stdin.write("release\n")
            child.stdin.flush()
            child.stdin.close()
        assert child.wait(timeout=10) == 0, "lock-holder child did not release and exit normally"


def test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key(tmp_path, monkeypatch):
    from tools.vst import slice as slice_module

    remote, repo, backend = _synthetic_git_source(tmp_path, filename="timeout.txt")
    head = git("rev-parse", "HEAD", cwd=str(repo))

    db = tmp_path / "timeout-operation.db"
    store = Store(str(db), event_key=EVENT)
    supervisor = Supervisor(store, operation_backend=backend)
    real_popen = slice_module.subprocess.Popen
    injected = {"done": False}
    observed_timeout = []

    def timeout_once(command, *args, **kwargs):
        if not injected["done"] and command[0] == "git" and "pack-objects" in command:
            injected["done"] = True
            observed_timeout.append(backend.command_timeout_sec)
            raise subprocess.TimeoutExpired(command, backend.command_timeout_sec)
        return real_popen(command, *args, **kwargs)

    monkeypatch.setattr(slice_module.subprocess, "Popen", timeout_once)
    payload = {"branch": "timeout-candidate", "head": head}
    try:
        with pytest.raises(TimeoutError, match="Git source pack import exceeded its time limit"):
            supervisor.simulate_push("timeout-retry-key", payload)
        assert injected["done"] and observed_timeout == [10]
        row = store._conn.execute(
            "SELECT operation, payload_sha256, result FROM supervisor_operations WHERE operation_key = ?",
            ("timeout-retry-key",),
        ).fetchone()
        assert row["operation"] == "push"
        assert json.loads(row["result"]) == {"_vst_state": "PENDING"}
        intent_count = store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE task_id = ? AND actor = 'supervisor'",
            ("timeout-retry-key",),
        ).fetchone()[0]
        assert intent_count >= 2  # durable intent and UNKNOWN timeout outcome
        store.close()

        restarted_store = Store(str(db), event_key=EVENT)
        restarted = Supervisor(restarted_store, operation_backend=backend)
        result = restarted.simulate_push("timeout-retry-key", payload)
        assert result == {
            "operation_key": "timeout-retry-key",
            "ref": "refs/heads/timeout-candidate",
            "head": head,
        }
        assert git("--git-dir", str(remote), "rev-parse", "refs/heads/timeout-candidate") == head
        completed = restarted.simulate_push("timeout-retry-key", payload)
        assert completed == result
        assert backend.push(payload, operation_key="timeout-retry-key") == result
        with pytest.raises(StoreError, match="remote idempotency key reused with different payload"):
            backend.push(
                {"branch": "conflicting-candidate", "head": head},
                operation_key="timeout-retry-key",
            )
        assert restarted_store._conn.execute(
            "SELECT result FROM supervisor_operations WHERE operation_key = ?",
            ("timeout-retry-key",),
        ).fetchone()[0] == json.dumps({"_vst_state": "PENDING"}, sort_keys=True, separators=(",", ":"))
        completion_count = restarted_store._conn.execute(
            "SELECT COUNT(*) FROM events WHERE task_id = ? AND payload LIKE '%SUPERVISOR_EXTERNAL_OPERATION_COMPLETED%'",
            ("timeout-retry-key",),
        ).fetchone()[0]
        assert completion_count == 1
        completion_payload = json.loads(restarted_store._conn.execute(
            "SELECT payload FROM events WHERE task_id = ? AND payload LIKE '%SUPERVISOR_EXTERNAL_OPERATION_COMPLETED%'",
            ("timeout-retry-key",),
        ).fetchone()[0])
        assert completion_payload["result"] == result
        restarted_store.close()
    finally:
        if store._conn is not None:
            store.close()


def test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides(tmp_path):
    repo = tmp_path / "synthetic-repo"
    repo.mkdir()
    git("init", cwd=str(repo))
    git("config", "user.name", "Synthetic", cwd=str(repo))
    git("config", "user.email", "synthetic@example.invalid", cwd=str(repo))
    observed = []
    for index in range(3):
        (repo / "candidate.txt").write_text(f"candidate-{index}\n", encoding="utf-8")
        git("add", "candidate.txt", cwd=str(repo))
        git("commit", "-m", f"candidate {index}", cwd=str(repo))
        observed.append(_derive_head(str(repo)))
    assert len(set(observed)) == 3
    assert all(git("cat-file", "-t", head, cwd=str(repo)) == "commit" for head in observed)
    api = inspect.signature(run_manifest_commands).parameters
    assert "manifest" in api and "cwd" in api
    for forbidden in ("candidate_head", "commands", "parser", "test_result_parser", "key", "signing_key"):
        assert forbidden not in api
    assert all(len(head) == 40 for head in observed)


@pytest.mark.parametrize("override", ["candidate_head", "commands", "parser", "test_result_parser", "key", "signing_key"])
def test_runner_rejects_caller_supplied_head_parser_key_or_commands(override):
    arguments = {
        "manifest": {}, "slot": "tests", "attempt": 1, "epoch": 1,
        "resolved_model": "synthetic", "invocation_id": "inv-1", "runner_id": "runner-1",
        "signer_socket": "unused", "cwd": ".", "worker_uid": 1, "worker_gid": 1,
        "worker_exec_helper_head": _WORKER_HELPER_HEAD,
        "worker_exec_helper_path": _WORKER_HELPER_PATH,
        "verify_worker_exec_helper": lambda: None,
        "created_at": "2026-10-24T00:00:00Z",
    }
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        run_manifest_commands(**arguments, **{override: object()})


class _RequestConnection:
    """In-process protocol peer; this does not model or claim OS identity isolation."""

    def __init__(self, payload: bytes, uid: int = 4242):
        self.chunks = [payload, b""]
        self.uid = uid
        self.response = b""
        self.timeout = None

    def settimeout(self, value):
        self.timeout = value

    def getsockopt(self, _level, _option, _size):
        return struct.pack("3i", 101, self.uid, 4242)

    def recv(self, _size):
        return self.chunks.pop(0) if self.chunks else b""

    def sendall(self, response: bytes):
        self.response = response


def _signer_protocol_request(request_id="request-1", candidate_head="a" * 40):
    parser_id, parser_version, parser_sha = next(iter(contracts.TRUSTED_PARSER_CATALOG))
    argv = ["python", "-c", "print('PASS t1')"]
    return {
        "request_id": request_id,
        "task_id": "task-1",
        "slot": "tests",
        "attempt": 1,
        "epoch": 1,
        "manifest_sha256": "b" * 64,
        "candidate_head": candidate_head,
        "commands": [{"argv": argv, "exit_code": 0}],
        "parser_results": [{
            "argv": argv, "parser_id": parser_id, "parser_version": parser_version,
            "parser_sha256": parser_sha,
            "parser_result": {"executed_test_ids": ["t1"], "skipped_test_ids": [], "xfail_test_ids": []},
        }],
        "artifact_digests": {},
    }


def _handle_signer_protocol(monkeypatch, server, request):
    import tools.vst.signer as signer_module

    monkeypatch.setattr(signer_module.socket, "SO_PEERCRED", 1, raising=False)
    connection = _RequestConnection(json.dumps(request).encode("utf-8"))
    server._handle(connection)
    return json.loads(connection.response)


def test_signing_request_exact_schema_and_replay_protocol_without_os_claim(monkeypatch):
    server = object.__new__(AuthenticatedSigner)
    server.runner_uid = 4242
    server.runner_gid = None
    server.require_pinned_daemon = False
    server.key = SIGNER_KEY
    server._ledger = sqlite3.connect(":memory:")
    server._ledger.execute("CREATE TABLE requests (request_id TEXT PRIMARY KEY, payload BLOB NOT NULL, signature TEXT NOT NULL)")
    server._lock = threading.Lock()
    request = _signer_protocol_request()
    assert set(validate_signing_request(request)) == {
        "request_id", "task_id", "slot", "attempt", "epoch", "manifest_sha256",
        "candidate_head", "commands", "parser_results", "artifact_digests",
    }
    first = _handle_signer_protocol(monkeypatch, server, request)
    replay = _handle_signer_protocol(monkeypatch, server, request)
    assert set(first) == {"signature"} and first == replay
    assert verify({**request, "signature": first["signature"]}, SIGNER_KEY, SIGNING_REQUEST_LABEL)
    assert server._ledger.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1
    changed = {**request, "candidate_head": "c" * 40}
    rejected = _handle_signer_protocol(monkeypatch, server, changed)
    assert rejected.get("error") == "invalid_request"
    assert "different payload" in rejected.get("detail", "")
    assert server._ledger.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1
    malformed = {**request, "unexpected": True, "request_id": "bad-request"}
    assert _handle_signer_protocol(monkeypatch, server, malformed).get("error") == "invalid_request"
    server._ledger.close()


@pytest.mark.parametrize("mutation", [
    lambda request: request.pop("candidate_head"),
    lambda request: request.update(epoch=True),
    lambda request: request["commands"][0].update(argv=["python", "-c", "different"]),
    lambda request: request["parser_results"][0].update(parser_sha256="0" * 64),
])
def test_signer_rejects_malformed_signing_evidence(mutation):
    request = _signer_protocol_request("malformed")
    mutation(request)
    with pytest.raises(contracts.ContractError):
        validate_signing_request(request)


def _authority_fixture():
    reviewer_key = b"s2-reviewer-authority-key-0123456789"
    entries = [{"principal": "reviewer-x", "key_id": "reviewer-key-1"}]
    registry_body = {"version": "registry-1", "entries": entries}
    registry = {
        **registry_body,
        "signature": sign(registry_body, OPERATOR_KEY, REVIEWER_REGISTRY_LABEL),
    }
    m = base_manifest(required_receipts=[
        {"slot": "tests", "receipt_type": "TestRun"},
        {"slot": "static", "receipt_type": "StaticAnalysis"},
        {"slot": "review", "receipt_type": "IndependentReview"},
        {"slot": "doc", "receipt_type": "Documentation"},
    ])
    m.update({
        "contract_version": 2,
        "reviewer_registry": {
            "version": "registry-1",
            "sha256": hashlib.sha256(contracts.canonical_bytes(registry_body)).hexdigest(),
        },
        "mandatory_commands": [{
            "slot": "tests", "argv": ["pytest", "-q"],
            "parser_id": "vst.pass-lines", "parser_version": "1",
            "parser_sha256": next(iter(contracts.TRUSTED_PARSER_CATALOG))[2],
        }],
        "change_scope": {"allowed_paths": ["src/app.py", "tests/test_app.py"]},
    })
    keys = {
        "worker": KEY,
        "supervisor": SUPERVISOR_KEY,
        "operator": OPERATOR_KEY,
        "event": EVENT_KEY,
        "signer": SIGNER_KEY,
        "reviewer": reviewer_key,
    }
    return m, registry, reviewer_key, keys


def _authority_receipt(receipt_type, slot, signing_key, manifest_obj, reviewer_key_id="reviewer-key-1"):
    manifest_sha = contracts.manifest_sha256(manifest_obj)
    candidate = unsigned_receipt(
        receipt_type,
        contract_version=2,
        task_id=TASK,
        manifest_sha256=manifest_sha,
        slot=slot,
        candidate_head="a" * 40,
        epoch=2,
    )
    if receipt_type == "IndependentReview":
        candidate["reviewer_key_id"] = reviewer_key_id
    elif receipt_type == "TestRun":
        parser_id, parser_version, parser_sha = next(iter(contracts.TRUSTED_PARSER_CATALOG))
        argv = ["pytest", "-q"]
        parser_result = {
            "executed_test_ids": ["t1", "t2"],
            "skipped_test_ids": [], "xfail_test_ids": [],
        }
        parser_results = [{
            "argv": argv, "parser_id": parser_id, "parser_version": parser_version,
            "parser_sha256": parser_sha, "parser_result": parser_result,
        }]
        request = {
            "request_id": "authority-request", "task_id": TASK, "slot": slot,
            "attempt": 1, "epoch": 2, "manifest_sha256": manifest_sha,
            "candidate_head": "a" * 40,
            "commands": [{"argv": argv, "exit_code": 0}],
            "parser_results": parser_results, "artifact_digests": {},
        }
        request_signature = sign(request, signing_key, SIGNING_REQUEST_LABEL)
        diff_body = {
            "manifest_sha256": manifest_sha, "candidate_head": "a" * 40,
            "diff_sha256": "d" * 64, "changed_paths": [],
            "verdict": "PASS", "reason": "PASS",
        }
        diff_gate = {
            **diff_body,
            "signature": sign(diff_body, SIGNER_KEY, DIFF_GATE_LABEL),
        }
        candidate.update({
            "parser_results": parser_results,
            "diff_gate": diff_gate,
            "runner_attestation": {"request": request, "signature": request_signature},
            "signature": request_signature,
        })
        return candidate
    signature_label = REVIEWER_LABEL if receipt_type == "IndependentReview" else RECEIPT_V2_LABEL
    candidate["signature"] = sign(candidate, signing_key, signature_label)
    return candidate


def _gate_authority_check(receipt_obj, manifest_obj, registry, reviewer_key):
    from tools.vst import gate

    decision = gate.evaluate(
        manifest_obj, [receipt_obj], "a" * 40, 2, KEY,
        supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
        reviewer_registry=registry, reviewer_keys={"reviewer-key-1": reviewer_key},
        signer_key=SIGNER_KEY, event_key=EVENT_KEY,
    )
    return decision["reasons"]


@pytest.mark.parametrize("receipt_type,slot,allowed_key", [
    ("TestRun", "tests", "signer"),
    ("IndependentReview", "review", "reviewer"),
    ("StaticAnalysis", "static", "worker"),
    ("Documentation", "doc", "worker"),
    ("Documentation", "__supervisor__", "supervisor"),
])
@pytest.mark.parametrize("key_kind", ["worker", "supervisor", "operator", "event", "signer", "reviewer"])
def test_gate_routes_each_v2_receipt_to_its_designated_authority(receipt_type, slot, allowed_key, key_kind):
    m, registry, reviewer_key, keys = _authority_fixture()
    candidate = _authority_receipt(receipt_type, slot, keys[key_kind], m)
    reasons = _gate_authority_check(candidate, m, registry, reviewer_key)
    invalid_signature = any("invalid signature" in reason for reason in reasons)
    assert invalid_signature is (key_kind != allowed_key)


class _MockChild:
    def __init__(self, pid, events):
        self.pid = pid
        self.stdout = io.BytesIO(b"synthetic stdout")
        self.stderr = io.BytesIO(b"")
        self.returncode = 0
        self._events = events

    def wait(self, timeout=None):
        self._events.append("wait")
        return self.returncode


def _job_object_setup_failure_api(close_outcomes):
    events = []
    close_calls = []

    class FakeKernel32:
        @staticmethod
        def CreateJobObjectW(_attributes, _name):
            events.append("create_job")
            return 700

        @staticmethod
        def SetInformationJobObject(*_args):
            events.append("configure_job")
            return False

        @staticmethod
        def CloseHandle(handle):
            close_calls.append(handle)
            events.append(f"close_job_{len(close_calls)}")
            outcome = close_outcomes[len(close_calls) - 1]
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

    class FakeLimits:
        def __init__(self):
            self.BasicLimitInformation = SimpleNamespace(LimitFlags=0)

    api = SimpleNamespace(
        k32=FakeKernel32,
        ExtendedLimits=FakeLimits,
        ctypes=SimpleNamespace(byref=lambda value: value, sizeof=lambda _value: 1),
    )
    return api, events, close_calls


@pytest.mark.parametrize(
    ("close_outcomes", "expected_log"),
    [
        ([False, True], False),
        ([RuntimeError("first close failed"), True], False),
        ([False, False], True),
        ([RuntimeError("first close failed"), RuntimeError("second close failed")], True),
    ],
    ids=["false-then-success", "exception-then-success", "persistent-false", "persistent-exception"],
)
def test_job_object_attach_setup_failure_retries_close_and_logs_only_if_cleanup_fails(
    monkeypatch, caplog, close_outcomes, expected_log,
):
    api, events, close_calls = _job_object_setup_failure_api(close_outcomes)
    monkeypatch.setattr(runner, "_win_api", lambda: api)

    attached = runner._JobObject.attach(SimpleNamespace(_handle=123))

    assert attached is None
    assert events == ["create_job", "configure_job", "close_job_1", "close_job_2"]
    assert close_calls == [700, 700]
    if expected_log:
        assert "failed to close Windows Job Object after setup failure" in caplog.text
    else:
        assert "failed to close Windows Job Object after setup failure" not in caplog.text


def test_strict_windows_launch_stays_fail_closed_after_job_setup_cleanup_failure(
    monkeypatch, caplog,
):
    api, close_events, close_calls = _job_object_setup_failure_api([False, False])
    run_events = []
    resume_calls = []
    monkeypatch.setattr(runner, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(runner, "_win_api", lambda: api)

    def popen(argv, **_kwargs):
        run_events.append("create_suspended")
        assert argv == ["synthetic-command"]
        return _MockChild(4242, run_events)

    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    monkeypatch.setattr(runner, "_kill_tree", lambda _child: run_events.append("cleanup"))
    monkeypatch.setattr(
        runner, "_resume_suspended_primary_thread",
        lambda _pid: resume_calls.append("resumed"),
    )

    code, output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {}, 1024, require_job_object=True,
    )

    assert code == runner.EXIT_CAPTURE_INCOMPLETE
    assert output == ""
    assert info["job_object_refused"] is True
    assert resume_calls == []
    assert run_events == ["create_suspended", "cleanup", "wait"]
    assert close_events == ["create_job", "configure_job", "close_job_1", "close_job_2"]
    assert close_calls == [700, 700]
    assert "failed to close Windows Job Object after setup failure" in caplog.text


def _install_mock_windows_run(monkeypatch, *, failure=None):
    events = []
    command_callbacks = []
    jobs = []
    monkeypatch.setattr(runner, "os", SimpleNamespace(name="nt"))

    def popen(argv, **kwargs):
        flags = kwargs.get("creationflags", 0)
        suspended = bool(flags & runner._CREATE_SUSPENDED)
        events.append("create_suspended" if suspended else "create_running")
        child = _MockChild(4242, events)
        if not suspended:
            events.append("command_callback")
            command_callbacks.append(argv)
        return child

    class MockJob:
        def __init__(self):
            self.closed = False

        def terminate_and_close(self):
            if not self.closed:
                self.closed = True
                events.append("job_cleanup")
                return True
            return True

    class Pointer:
        def __init__(self, value):
            self.value = (1 << 64) - 1 if value == -1 else value

    class ThreadEntry:
        def __init__(self):
            self.dwSize = 0
            self.th32OwnerProcessID = 0
            self.th32ThreadID = 0

    class FakeKernel32:
        @staticmethod
        def CreateToolhelp32Snapshot(flags, process_id):
            events.append("thread_snapshot")
            return 900

        @staticmethod
        def Thread32First(snapshot, entry):
            events.append("thread_discovery")
            if failure == "thread_discovery":
                return False
            entry.th32OwnerProcessID = 4242
            entry.th32ThreadID = 77
            return True

        @staticmethod
        def Thread32Next(snapshot, entry):
            return False

        @staticmethod
        def OpenThread(access, inherit, thread_id):
            events.append("open_primary_thread")
            return 901

        @staticmethod
        def ResumeThread(thread):
            events.append("resume_primary_thread")
            return 0 if failure == "resume" else 1

        @staticmethod
        def CloseHandle(handle):
            events.append("close_win32_handle")
            return True

    api = SimpleNamespace(
        ctypes=SimpleNamespace(c_void_p=Pointer, sizeof=lambda value: 1, byref=lambda value: value),
        k32=FakeKernel32,
        ThreadEntry32=ThreadEntry,
    )
    resume_real = runner._resume_suspended_primary_thread

    def attach_job(child):
        events.append("assign_job" if failure != "assignment" else "assign_job_failed")
        if failure == "assignment":
            return None
        job = MockJob()
        jobs.append(job)
        return job

    def resume_primary_thread(pid):
        resumed = resume_real(pid)
        if resumed:
            events.append("command_callback")
            command_callbacks.append(["synthetic-command"])
        return resumed

    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    monkeypatch.setattr(runner, "_JobObject", SimpleNamespace(attach=attach_job))
    monkeypatch.setattr(runner, "_win_api", lambda: api)
    monkeypatch.setattr(runner, "_resume_suspended_primary_thread", resume_primary_thread)
    monkeypatch.setattr(runner, "_kill_tree", lambda child: events.append("process_cleanup"))
    monkeypatch.setattr(runner, "_taskkill_tree", lambda pid: events.append("legacy_tree_cleanup"))
    return events, command_callbacks, jobs


def test_strict_windows_launch_suspends_assigns_job_then_resumes_before_command(monkeypatch):
    events, callbacks, jobs = _install_mock_windows_run(monkeypatch)
    code, output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {}, 1024, require_job_object=True,
    )
    assert code == 0
    assert output == "synthetic stdout"
    assert info["job_object"] is True
    assert events[0] == "create_suspended"
    assert events.index("create_suspended") < events.index("assign_job")
    assert events.index("assign_job") < events.index("thread_snapshot")
    assert events.index("thread_snapshot") < events.index("thread_discovery")
    assert events.index("thread_discovery") < events.index("resume_primary_thread")
    assert events.index("resume_primary_thread") < events.index("command_callback")
    assert callbacks == [["synthetic-command"]]
    assert jobs[0].closed


@pytest.mark.parametrize("failure", ["assignment", "thread_discovery", "resume"])
def test_strict_windows_launch_failure_cleans_up_without_running_command(monkeypatch, failure):
    events, callbacks, jobs = _install_mock_windows_run(
        monkeypatch, failure=failure,
    )
    code, output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {}, 1024, require_job_object=True,
    )
    assert code == runner.EXIT_CAPTURE_INCOMPLETE
    assert output == ""
    assert info["job_object_refused"] is True
    assert callbacks == []
    assert "process_cleanup" in events
    assert "wait" in events
    if failure == "assignment":
        assert "thread_discovery" not in events
        assert jobs == []
    else:
        assert jobs and jobs[0].closed


def test_nonstrict_windows_launch_keeps_unsuspended_compatibility_path(monkeypatch):
    events, callbacks, _jobs = _install_mock_windows_run(monkeypatch)
    code, _output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {}, 1024, require_job_object=False,
    )
    assert code == 0
    assert info["job_object"] is True
    assert callbacks == [["synthetic-command"]]
    assert events[0] == "create_running"
    assert events.index("command_callback") < events.index("assign_job")
    assert "resume_primary_thread" not in events


def test_posix_launch_keeps_session_based_compatibility_path(monkeypatch):
    events = []
    callbacks = []

    def popen(argv, **kwargs):
        assert kwargs.get("start_new_session") is True
        assert "creationflags" not in kwargs
        events.append("create_running")
        callbacks.append(argv)
        return _MockChild(4243, events)

    monkeypatch.setattr(
        runner, "os", SimpleNamespace(name="posix", killpg=lambda pid, sig: events.append("posix_group_cleanup")),
    )
    monkeypatch.setattr(runner, "signal", SimpleNamespace(SIGKILL=9))
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    code, output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {}, 1024, require_job_object=False,
    )
    assert code == 0
    assert output == "synthetic stdout"
    assert info["job_object"] is False
    assert callbacks == [["synthetic-command"]]
    assert "posix_group_cleanup" in events


def _posix_runner_os(monkeypatch):
    posix_os = SimpleNamespace(**vars(os))
    posix_os.name = "posix"
    monkeypatch.setattr(runner, "os", posix_os)
    monkeypatch.setattr(runner, "_POSIX_CGROUP_CLEANUP_FAILED", threading.Event())

    @contextmanager
    def synthetic_process_lock(_deadline):
        yield

    monkeypatch.setattr(runner, "_posix_cgroup_process_lock", synthetic_process_lock)
    return posix_os


def test_posix_admission_lock_validates_private_runtime_and_lock_file(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    calls = []
    actual_os = os

    class FakeStat:
        def __init__(self, mode):
            self.st_mode = mode
            self.st_uid = 1001

    posix_os = SimpleNamespace(**vars(actual_os))
    posix_os.name = "posix"
    posix_os.geteuid = lambda: 1001
    posix_os.stat = lambda _path, follow_symlinks=False: FakeStat(
        runner.stat.S_IFDIR | 0o700
    )
    posix_os.open = lambda path, flags, mode=0o777: calls.append(
        ("open", path, flags, mode)
    ) or 41
    posix_os.fstat = lambda _fd: FakeStat(runner.stat.S_IFREG | 0o600)
    posix_os.close = lambda fd: calls.append(("close", fd))
    monkeypatch.setattr(runner, "os", posix_os)
    monkeypatch.setattr(runner, "_POSIX_CGROUP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setattr(runner._DelegatedCgroup, "reconcile_stale", lambda _deadline: calls.append("reconcile"))

    fake_fcntl = SimpleNamespace(LOCK_EX=2, LOCK_NB=4)
    fake_fcntl.flock = lambda fd, operation: calls.append(("flock", fd, operation))
    monkeypatch.setitem(sys.modules, "fcntl", fake_fcntl)

    with runner._posix_cgroup_process_lock(10.0):
        calls.append("admitted")

    assert calls[0][0] == "open"
    assert calls[1] == ("flock", 41, fake_fcntl.LOCK_EX | fake_fcntl.LOCK_NB)
    assert calls[2] == "reconcile"
    assert calls[3] == "admitted"
    assert calls[4] == ("close", 41)


@pytest.mark.parametrize(
    "bad_mode",
    [
        runner.stat.S_IFDIR | 0o777,
        runner.stat.S_IFDIR | 0o755,
        runner.stat.S_IFLNK | 0o700,
    ],
)
def test_posix_admission_lock_refuses_untrusted_runtime_directory(monkeypatch, tmp_path, bad_mode):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    opened = []
    posix_os = SimpleNamespace(**vars(os))
    posix_os.name = "posix"
    posix_os.geteuid = lambda: 1001
    posix_os.stat = lambda _path, follow_symlinks=False: SimpleNamespace(
        st_mode=bad_mode, st_uid=1001
    )
    posix_os.open = lambda *args, **kwargs: opened.append(args)
    monkeypatch.setattr(runner, "os", posix_os)
    monkeypatch.setattr(runner, "_POSIX_CGROUP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(LOCK_EX=2, LOCK_NB=4))

    with pytest.raises(OSError, match="runtime directory"):
        with runner._posix_cgroup_process_lock(10.0):
            pytest.fail("untrusted runtime directory must not admit a worker")
    assert opened == []


def test_posix_admission_lock_refuses_non_private_lock_file(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    opened = []
    posix_os = SimpleNamespace(**vars(os))
    posix_os.name = "posix"
    posix_os.geteuid = lambda: 1001
    posix_os.stat = lambda _path, follow_symlinks=False: SimpleNamespace(
        st_mode=runner.stat.S_IFDIR | 0o700, st_uid=1001
    )
    posix_os.open = lambda *args, **kwargs: 42
    posix_os.fstat = lambda _fd: SimpleNamespace(
        st_mode=runner.stat.S_IFREG | 0o640, st_uid=1001
    )
    posix_os.close = lambda fd: opened.append(("close", fd))
    monkeypatch.setattr(runner, "os", posix_os)
    monkeypatch.setattr(runner, "_POSIX_CGROUP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(LOCK_EX=2, LOCK_NB=4))

    with pytest.raises(OSError, match="private runner-owned"):
        with runner._posix_cgroup_process_lock(10.0):
            pytest.fail("unsafe lock file must not admit a worker")
    assert opened == [("close", 42)]


def test_posix_admission_lock_deadline_refuses_contended_flock(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    calls = []
    posix_os = SimpleNamespace(**vars(os))
    posix_os.name = "posix"
    posix_os.geteuid = lambda: 1001
    posix_os.stat = lambda _path, follow_symlinks=False: SimpleNamespace(
        st_mode=runner.stat.S_IFDIR | 0o700, st_uid=1001
    )
    posix_os.open = lambda *args, **kwargs: 43
    posix_os.fstat = lambda _fd: SimpleNamespace(
        st_mode=runner.stat.S_IFREG | 0o600, st_uid=1001
    )
    posix_os.close = lambda fd: calls.append(("close", fd))
    monkeypatch.setattr(runner, "os", posix_os)
    monkeypatch.setattr(runner, "_POSIX_CGROUP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setattr(runner._DelegatedCgroup, "reconcile_stale", lambda _deadline: calls.append("reconcile"))

    now = [10.0]
    fake_time = SimpleNamespace(
        monotonic=lambda: now[0],
        sleep=lambda seconds: (calls.append(("sleep", seconds)), now.__setitem__(0, now[0] + seconds)),
    )
    monkeypatch.setattr(runner, "time", fake_time)
    fake_fcntl = SimpleNamespace(LOCK_EX=2, LOCK_NB=4)

    def contended_flock(fd, operation):
        calls.append(("flock", fd, operation))
        raise BlockingIOError("lock held by another runner")

    fake_fcntl.flock = contended_flock
    monkeypatch.setitem(sys.modules, "fcntl", fake_fcntl)

    with pytest.raises(TimeoutError, match="admission lock deadline expired"):
        with runner._posix_cgroup_process_lock(10.05):
            pytest.fail("contended lock must not admit a worker")

    assert calls[0] == ("flock", 43, fake_fcntl.LOCK_EX | fake_fcntl.LOCK_NB)
    assert calls[-1] == ("close", 43)
    assert "reconcile" not in calls
    sleeps = [call[1] for call in calls if isinstance(call, tuple) and call[0] == "sleep"]
    assert sleeps
    assert sum(sleeps) <= 0.05 + 1e-9


def test_posix_stale_cgroup_reconciliation_removes_only_owned_scope(monkeypatch, tmp_path):
    parent = tmp_path / "runner-cgroup"
    parent.mkdir()
    stale = parent / f"vst-command-123-{'a' * 32}"
    stale.mkdir()
    (stale / "cgroup.events").write_text("populated 0\n", encoding="ascii")
    (stale / "cgroup.procs").write_text("", encoding="ascii")
    unrelated = parent / "other-service"
    unrelated.mkdir()
    removed = []
    deadline = time.monotonic() + 5.0
    monkeypatch.setattr(runner._DelegatedCgroup, "_runner_parent", lambda: str(parent))
    real_rmdir = os.rmdir

    def remove_synthetic_cgroup(path):
        removed.append((path, deadline - time.monotonic()))
        if path == str(stale):
            # Ordinary temporary files stand in for virtual cgroup control files.
            os.remove(os.path.join(path, "cgroup.events"))
            os.remove(os.path.join(path, "cgroup.procs"))
        real_rmdir(path)

    monkeypatch.setattr(runner.os, "rmdir", remove_synthetic_cgroup)
    runner._DelegatedCgroup.reconcile_stale(deadline)

    assert len(removed) == 1
    assert removed[0][0] == str(stale)
    assert 0 < removed[0][1] <= 5.0
    assert not stale.exists()
    assert unrelated.is_dir()


def test_posix_stale_cgroup_reconciliation_fails_closed_on_malformed_scope(monkeypatch, tmp_path):
    parent = tmp_path / "runner-cgroup"
    parent.mkdir()
    malformed = parent / "vst-command-not-a-owned-scope"
    malformed.mkdir()
    cleanup_calls = []
    monkeypatch.setattr(runner._DelegatedCgroup, "_runner_parent", lambda: str(parent))
    monkeypatch.setattr(
        runner._DelegatedCgroup, "kill_and_remove",
        lambda *args, **kwargs: cleanup_calls.append((args, kwargs)) or True,
    )

    with pytest.raises(OSError, match="unrecognized runner command cgroup"):
        runner._DelegatedCgroup.reconcile_stale(time.monotonic() + 5.0)
    assert cleanup_calls == []
    assert malformed.is_dir()


def test_posix_stale_cgroup_reconciliation_refuses_unconfirmed_cleanup(monkeypatch, tmp_path):
    parent = tmp_path / "runner-cgroup"
    parent.mkdir()
    stale = parent / f"vst-command-123-{'b' * 32}"
    stale.mkdir()
    (stale / "cgroup.events").write_text("populated 0\n", encoding="ascii")
    (stale / "cgroup.procs").write_text("", encoding="ascii")
    monkeypatch.setattr(runner._DelegatedCgroup, "_runner_parent", lambda: str(parent))

    def refuse_cgroup_removal(_path):
        raise OSError("synthetic kernel refused cgroup removal")

    monkeypatch.setattr(
        runner.os, "rmdir", refuse_cgroup_removal,
    )

    with pytest.raises(OSError, match="verified empty stale command scope could not be removed"):
        runner._DelegatedCgroup.reconcile_stale(time.monotonic() + 5.0)
    assert stale.is_dir()


def test_distinct_uid_launch_refuses_when_process_lock_or_reconciliation_fails(monkeypatch):
    _posix_runner_os(monkeypatch)
    downstream = []

    @contextmanager
    def unavailable_lock(_deadline):
        raise OSError("stale scope could not be confirmed empty")
        yield

    monkeypatch.setattr(runner, "_posix_cgroup_process_lock", unavailable_lock)
    monkeypatch.setattr(runner._DelegatedCgroup, "create", lambda: downstream.append("cgroup"))
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *args, **kwargs: downstream.append("popen"))

    code, output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {"PATH": "/worker/bin"}, 1024,
        worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
    )

    assert code == runner.EXIT_CAPTURE_INCOMPLETE
    assert output == ""
    assert info["capture_incomplete"] is True
    assert "could not be confirmed empty" in info["posix_cgroup_refused"]
    assert downstream == []


class _ObservedCgroup:
    def __init__(self, events, *, attach_error=None, cleanup_result=True, kill_pid=False):
        self.events = events
        self.attach_error = attach_error
        self.cleanup_result = cleanup_result
        self.kill_pid = kill_pid
        self.pid = None

    def attach(self, pid):
        self.events.append("attach")
        self.pid = pid
        if self.attach_error:
            raise self.attach_error

    def kill_and_remove(self, timeout=10.0):
        self.events.append("kill_and_remove")
        if self.kill_pid and self.pid is not None:
            try:
                os.kill(self.pid, runner.signal.SIGKILL)
            except ProcessLookupError:
                pass
        if not self.cleanup_result:
            runner._POSIX_CGROUP_CLEANUP_FAILED.set()
        return self.cleanup_result


def test_distinct_uid_worker_refuses_launch_when_delegated_cgroup_is_unavailable(monkeypatch):
    _posix_runner_os(monkeypatch)
    calls = []

    def unavailable():
        raise OSError("no delegated cgroup")

    monkeypatch.setattr(runner._DelegatedCgroup, "create", unavailable)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
    code, output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {"PATH": "/usr/bin"}, 1024,
        worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
    )

    assert code == runner.EXIT_CAPTURE_INCOMPLETE
    assert output == ""
    assert info["capture_incomplete"] is True
    assert "no delegated cgroup" in info["posix_cgroup_refused"]
    assert calls == []


def test_distinct_uid_launch_preserves_expired_absolute_deadline_at_admission(monkeypatch):
    _posix_runner_os(monkeypatch)
    monkeypatch.setattr(runner, "_POSIX_CGROUP_RUN_LOCK", threading.Lock())
    monkeypatch.setattr(runner.time, "monotonic", lambda: 200.0)
    downstream_calls = []
    scope = _ObservedCgroup([])

    def create_scope():
        downstream_calls.append("cgroup_create")
        return scope

    def unexpected_popen(*_args, **_kwargs):
        downstream_calls.append("popen")
        raise OSError("unexpected Popen after expired deadline")

    monkeypatch.setattr(runner._DelegatedCgroup, "create", create_scope)
    monkeypatch.setattr(runner.subprocess, "Popen", unexpected_popen)

    code, output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {"PATH": "/worker/bin"}, 1024,
        worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
        _deadline_at=199.0,
    )

    assert code == runner.EXIT_TIMEOUT
    assert output == ""
    assert info["timed_out"] is True
    assert info["skipped_by_deadline"] is True
    assert info["admission_wait_expired"] is True
    assert info["capture_incomplete"] is False
    assert downstream_calls == []


class _GateChild:
    def __init__(self, events, reader, *, timeout_once=False):
        self.pid = 4243
        self.stdout = io.BytesIO(b"synthetic stdout")
        self.stderr = io.BytesIO(b"")
        self.returncode = 0
        self.events = events
        self.reader = reader
        self.timeout_once = timeout_once
        self.wait_count = 0

    def wait(self, timeout=None):
        self.events.append("wait")
        self.wait_count += 1
        if self.timeout_once and self.wait_count == 1:
            raise subprocess.TimeoutExpired("gate-child", timeout)
        self.reader.join(timeout=2)
        return self.returncode

    def poll(self):
        return self.returncode if not self.reader.is_alive() and self.wait_count else None


def _install_gate_popen(monkeypatch, events, *, timeout_once=False, on_popen=None):
    def fake_popen(argv, **kwargs):
        assert argv[0] == _WORKER_HELPER_PATH
        if on_popen is not None:
            on_popen(argv)
        assert kwargs["env"] == {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
        assert kwargs["pass_fds"]
        script_at = argv.index("-c")
        env_fd = os.dup(int(argv[script_at + 2]))
        gate_fd = os.dup(int(argv[script_at + 3]))

        def read_gate():
            env_data = bytearray()
            while True:
                chunk = os.read(env_fd, 65536)
                if not chunk:
                    break
                env_data.extend(chunk)
            events.append(("worker_env_loaded", json.loads(env_data) if env_data else {}))
            release = os.read(gate_fd, 1)
            if release == b"1":
                events.append("exec_after_gate")
            else:
                events.append("gate_closed_without_exec")
            os.close(env_fd)
            os.close(gate_fd)

        reader = threading.Thread(target=read_gate, daemon=True)
        reader.start()
        return _GateChild(events, reader, timeout_once=timeout_once)

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        runner, "_write_pipe_before_deadline",
        lambda fd, data, _deadline, _proc: runner.os.write(fd, data),
    )


def test_versioned_helper_identity_callback_runs_before_spawn(monkeypatch):
    _posix_runner_os(monkeypatch)
    events = []
    scope = _ObservedCgroup(events)
    monkeypatch.setattr(runner._DelegatedCgroup, "create", lambda: scope)
    _install_gate_popen(
        monkeypatch, events,
        on_popen=lambda argv: events.append(("popen", argv[0])),
    )

    code, _output, _info = runner._run_one(
        ["synthetic-command"], ".", 1, {"PATH": "/worker/bin"}, 1024,
        worker_uid=1001, worker_gid=1001,
        worker_exec_helper_path=_WORKER_HELPER_PATH,
        _before_spawn=lambda: events.append("helper_identity_verified"),
    )

    assert code == 0
    assert events.index("helper_identity_verified") < events.index(
        ("popen", _WORKER_HELPER_PATH)
    )
    assert ("popen", "/usr/local/libexec/vst-s4-worker-exec") not in events


def test_versioned_helper_identity_mismatch_refuses_spawn_without_fallback(monkeypatch):
    _posix_runner_os(monkeypatch)
    events = []
    scope = _ObservedCgroup(events)
    monkeypatch.setattr(runner._DelegatedCgroup, "create", lambda: scope)
    _install_gate_popen(
        monkeypatch, events,
        on_popen=lambda argv: events.append(("popen", argv[0])),
    )

    def reject_changed_helper():
        events.append("helper_identity_mismatch")
        raise contracts.ContractError("configured worker helper identity changed")

    with pytest.raises(contracts.ContractError, match="identity changed"):
        runner._run_one(
            ["synthetic-command"], ".", 1, {"PATH": "/worker/bin"}, 1024,
            worker_uid=1001, worker_gid=1001,
            worker_exec_helper_path=_WORKER_HELPER_PATH,
            _before_spawn=reject_changed_helper,
        )

    assert "helper_identity_mismatch" in events
    assert not any(isinstance(event, tuple) and event[0] == "popen" for event in events)
    assert "kill_and_remove" in events


def test_distinct_uid_cgroup_gate_orders_attach_environment_and_exec(monkeypatch):
    posix_os = _posix_runner_os(monkeypatch)
    events = []
    scope = _ObservedCgroup(events)
    monkeypatch.setattr(runner._DelegatedCgroup, "create", lambda: scope)
    _install_gate_popen(monkeypatch, events)
    real_write = os.write

    def observed_write(fd, data):
        if data == b"1":
            events.append("gate_released")
        return real_write(fd, data)

    posix_os.write = observed_write
    worker_env = {"PATH": "/worker/bin", "VST_SENTINEL": "payload"}
    code, output, info = runner._run_one(
        ["synthetic-command", "argument"], ".", 1, worker_env, 1024,
        worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
    )

    assert code == 0
    assert output == "synthetic stdout"
    assert info["capture_incomplete"] is False
    assert events.index("attach") < events.index("gate_released") < events.index("exec_after_gate")
    loaded_env = next(value for event in events if isinstance(event, tuple)
                      for name, value in [event] if name == "worker_env_loaded")
    assert loaded_env == worker_env
    assert events[-1] == "kill_and_remove"


def test_distinct_uid_attach_failure_closes_gate_without_exec(monkeypatch):
    _posix_runner_os(monkeypatch)
    events = []
    scope = _ObservedCgroup(events, attach_error=OSError("attach denied"))
    monkeypatch.setattr(runner._DelegatedCgroup, "create", lambda: scope)
    _install_gate_popen(monkeypatch, events)

    code, output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {"PATH": "/worker/bin"}, 1024,
        worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
    )

    assert code == runner.EXIT_CAPTURE_INCOMPLETE
    assert output == ""
    assert info["capture_incomplete"] is True
    assert "attach denied" in info["posix_cgroup_refused"]
    assert "gate_closed_without_exec" in events
    assert "exec_after_gate" not in events


@pytest.mark.parametrize("scenario", ["normal_exit", "timeout"])
def test_distinct_uid_cgroup_gate_cleans_scope_on_exit_and_timeout(monkeypatch, scenario):
    _posix_runner_os(monkeypatch)
    events = []
    scope = _ObservedCgroup(events)
    monkeypatch.setattr(runner._DelegatedCgroup, "create", lambda: scope)
    _install_gate_popen(monkeypatch, events, timeout_once=(scenario == "timeout"))
    real_write = os.write
    runner.os.write = lambda fd, data: real_write(fd, data)
    timeout = 0.001 if scenario == "timeout" else 1

    code, _output, info = runner._run_one(
        ["synthetic-command"], ".", timeout, {"PATH": "/worker/bin"}, 1024,
        worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
    )

    assert "kill_and_remove" in events
    assert info["capture_incomplete"] is False
    assert info["timed_out"] is (scenario == "timeout")
    assert code == (runner.EXIT_TIMEOUT if scenario == "timeout" else 0)


def test_distinct_uid_cgroup_cleanup_failure_is_non_approving(monkeypatch):
    _posix_runner_os(monkeypatch)
    events = []
    scope = _ObservedCgroup(events, cleanup_result=False)
    monkeypatch.setattr(runner._DelegatedCgroup, "create", lambda: scope)
    _install_gate_popen(monkeypatch, events)
    real_write = os.write
    runner.os.write = lambda fd, data: real_write(fd, data)

    code, _output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {"PATH": "/worker/bin"}, 1024,
        worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
    )

    assert code == runner.EXIT_CAPTURE_INCOMPLETE
    assert info["capture_incomplete"] is True
    assert events.count("kill_and_remove") == 2  # immediate attempt plus finally retry


def test_unconfirmed_cgroup_cleanup_latches_later_distinct_uid_launches(monkeypatch):
    _posix_runner_os(monkeypatch)
    events = []
    scope = _ObservedCgroup(events, cleanup_result=False)
    monkeypatch.setattr(runner._DelegatedCgroup, "create", lambda: scope)
    _install_gate_popen(monkeypatch, events)
    runner.os.write = lambda fd, data: os.write(fd, data)

    first_code, _output, first_info = runner._run_one(
        ["synthetic-command", "first"], ".", 1, {"PATH": "/worker/bin"}, 1024,
        worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
    )
    assert first_code == runner.EXIT_CAPTURE_INCOMPLETE
    assert first_info["capture_incomplete"] is True
    assert runner._POSIX_CGROUP_CLEANUP_FAILED.is_set()

    later_calls = []
    monkeypatch.setattr(
        runner._DelegatedCgroup, "create",
        lambda: later_calls.append("cgroup_create"),
    )
    monkeypatch.setattr(
        runner.subprocess, "Popen",
        lambda *args, **kwargs: later_calls.append("popen"),
    )
    second_code, second_output, second_info = runner._run_one(
        ["synthetic-command", "second"], ".", 1, {"PATH": "/worker/bin"}, 1024,
        worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
    )

    assert second_code == runner.EXIT_CAPTURE_INCOMPLETE
    assert second_output == ""
    assert second_info["capture_incomplete"] is True
    assert "prior cleanup was not confirmed" in second_info["posix_cgroup_refused"]
    assert later_calls == []


def test_concurrent_distinct_uid_launch_waits_for_cleanup_latch_admission(monkeypatch):
    _posix_runner_os(monkeypatch)

    class ObservedLock:
        """Expose when the second launch has reached the serialized boundary."""
        def __init__(self):
            self._lock = threading.Lock()
            self._guard = threading.Lock()
            self._entries = 0
            self.second_waiting = threading.Event()

        def acquire(self, timeout=-1):
            with self._guard:
                self._entries += 1
                if self._entries == 2:
                    self.second_waiting.set()
            return self._lock.acquire(timeout=timeout)

        def release(self):
            self._lock.release()

    run_lock = ObservedLock()
    monkeypatch.setattr(runner, "_POSIX_CGROUP_RUN_LOCK", run_lock)
    cleanup_entered = threading.Event()
    finish_cleanup = threading.Event()
    events = []

    class BlockingFailedCleanupCgroup:
        def attach(self, pid):
            events.append(("attach", pid))

        def kill_and_remove(self, timeout=10.0):
            events.append("cleanup_started")
            if not cleanup_entered.is_set():
                cleanup_entered.set()
                assert finish_cleanup.wait(timeout=5)
            runner._POSIX_CGROUP_CLEANUP_FAILED.set()
            events.append("cleanup_unconfirmed")
            return False

    scope = BlockingFailedCleanupCgroup()
    created = []

    def create_scope():
        created.append("cgroup_create")
        return scope

    monkeypatch.setattr(runner._DelegatedCgroup, "create", create_scope)
    _install_gate_popen(monkeypatch, events)
    original_popen = runner.subprocess.Popen
    popen_calls = []

    def observed_popen(argv, **kwargs):
        popen_calls.append(argv)
        return original_popen(argv, **kwargs)

    monkeypatch.setattr(runner.subprocess, "Popen", observed_popen)
    results = {}

    def run(command):
        results[command] = runner._run_one(
            ["synthetic-command", command], ".", 2,
            {"PATH": "/worker/bin"}, 1024,
            worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
        )

    first = threading.Thread(target=run, args=("first",), daemon=True)
    second = threading.Thread(target=run, args=("second",), daemon=True)
    first.start()
    try:
        assert cleanup_entered.wait(timeout=5)
        second.start()
        assert run_lock.second_waiting.wait(timeout=5)

        # The first command is still inside unconfirmed cgroup cleanup. The
        # second must not reach cgroup creation or Popen while that state is
        # unresolved.
        assert not finish_cleanup.is_set()
        assert created == ["cgroup_create"]
        assert len(popen_calls) == 1

        finish_cleanup.set()
        first.join(timeout=5)
        second.join(timeout=5)
    finally:
        finish_cleanup.set()
        first.join(timeout=5)
        if second.ident is not None:
            second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    first_code, _first_output, first_info = results["first"]
    second_code, second_output, second_info = results["second"]
    assert first_code == runner.EXIT_CAPTURE_INCOMPLETE
    assert first_info["capture_incomplete"] is True
    assert second_code == runner.EXIT_CAPTURE_INCOMPLETE
    assert second_output == ""
    assert second_info["capture_incomplete"] is True
    assert "prior cleanup was not confirmed" in second_info["posix_cgroup_refused"]
    assert created == ["cgroup_create"]
    assert len(popen_calls) == 1
    assert events.count("cleanup_unconfirmed") == 2


def test_distinct_uid_launch_skips_after_lock_wait_exhausts_command_budget(monkeypatch):
    _posix_runner_os(monkeypatch)

    class ObservedLock:
        def __init__(self):
            self._lock = threading.Lock()
            self._guard = threading.Lock()
            self._acquire_calls = 0
            self.waiting_launch = threading.Event()

        def acquire(self, timeout=-1):
            with self._guard:
                self._acquire_calls += 1
                if self._acquire_calls == 2:
                    self.waiting_launch.set()
            return self._lock.acquire(timeout=timeout)

        def release(self):
            self._lock.release()

    run_lock = ObservedLock()
    monkeypatch.setattr(runner, "_POSIX_CGROUP_RUN_LOCK", run_lock)
    assert run_lock.acquire()
    downstream_calls = []
    monkeypatch.setattr(
        runner._DelegatedCgroup, "create",
        lambda: downstream_calls.append("cgroup_create"),
    )
    monkeypatch.setattr(
        runner.subprocess, "Popen",
        lambda *args, **kwargs: downstream_calls.append("popen"),
    )
    results = []

    def queued_launch():
        results.append(runner._run_one(
            ["synthetic-command"], ".", 0.05,
            {"PATH": "/worker/bin"}, 1024,
            worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
        ))

    launch = threading.Thread(target=queued_launch, daemon=True)
    try:
        launch.start()
        assert run_lock.waiting_launch.wait(timeout=2)
        launch.join(timeout=2)
    finally:
        run_lock.release()
        launch.join(timeout=2)

    assert not launch.is_alive()
    assert len(results) == 1
    code, output, info = results[0]
    assert code == runner.EXIT_TIMEOUT
    assert output == ""
    assert info["timed_out"] is True
    assert info["skipped_by_deadline"] is True
    assert info["admission_wait_expired"] is True
    assert info["capture_incomplete"] is False
    assert downstream_calls == []


@pytest.mark.parametrize("cleanup_result", [True, False])
def test_distinct_uid_gate_environment_timeout_cleans_scope_and_refuses_exec(
    monkeypatch, cleanup_result,
):
    _posix_runner_os(monkeypatch)
    events = []
    scope = _ObservedCgroup(events, cleanup_result=cleanup_result)
    monkeypatch.setattr(runner._DelegatedCgroup, "create", lambda: scope)
    deadline_handoff = runner._write_pipe_before_deadline
    _install_gate_popen(monkeypatch, events)
    monkeypatch.setattr(runner, "_write_pipe_before_deadline", deadline_handoff)

    class GateHandoffTimeoutClock:
        """Expire only at pipe handoff, after admission and the initial guard."""
        def __init__(self):
            self.values = iter((100.0, 100.0, 100.0, 100.0, 102.0))
            self.calls = 0

        def monotonic(self):
            self.calls += 1
            try:
                return next(self.values)
            except StopIteration as exc:
                raise AssertionError("unexpected monotonic clock read") from exc

    clock = GateHandoffTimeoutClock()
    monkeypatch.setattr(runner.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(runner.select, "select", lambda *_a: ([], [], []))

    code, output, info = runner._run_one(
        ["synthetic-command"], ".", 1, {"PATH": "/worker/bin"}, 1024,
        worker_uid=1001, worker_gid=1001, worker_exec_helper_path=_WORKER_HELPER_PATH,
    )

    assert output == ""
    assert info["timed_out"] is True
    assert info["posix_gate_timeout"] is True
    assert info["capture_incomplete"] is (not cleanup_result)
    assert code == (runner.EXIT_TIMEOUT if cleanup_result else runner.EXIT_CAPTURE_INCOMPLETE)
    assert clock.calls == 5
    assert events.count("kill_and_remove") == 1
    assert "attach" not in events
    assert "gate_closed_without_exec" in events
    assert "exec_after_gate" not in events


def test_run_and_sign_stops_after_incomplete_cleanup_and_records_later_command_not_run(
    monkeypatch, tmp_path,
):
    commands = [["synthetic-command", "first"], ["synthetic-command", "second"]]
    manifest = base_manifest(allowed_commands=[{"slot": "tests", "argv": argv} for argv in commands])
    launched = []

    def incomplete(argv, *_args, **_kwargs):
        launched.append(argv)
        return runner.EXIT_CAPTURE_INCOMPLETE, "", {
            "stdout_truncated": False, "stderr_truncated": False,
            "timed_out": False, "capture_incomplete": True, "job_object": False,
        }

    monkeypatch.setattr(runner, "_run_one", incomplete)
    report = {}
    receipt = runner.run_and_sign(
        manifest=manifest, slot="tests", attempt=1, epoch=1,
        candidate_head="a" * 40, resolved_model="synthetic", invocation_id="inv-s2-stop",
        runner_id="runner-s2", key=KEY, commands=commands, expected_test_ids=["t1", "t2"],
        test_result_parser=lambda _output: ([], [], []), covered_acceptance=["AC-1"],
        artifact_paths=[], prev_receipt_sha256=None, cwd=str(tmp_path),
        created_at="2026-10-27T00:00:00Z", timeout_sec=30, deadline_sec=30, report=report,
    )

    assert launched == [commands[0]]
    assert receipt["result"] == "INCONCLUSIVE"
    assert receipt["executed_test_ids"] == []
    assert [entry["exit_code"] for entry in receipt["commands"]] == [
        runner.EXIT_CAPTURE_INCOMPLETE, runner.EXIT_CAPTURE_INCOMPLETE,
    ]
    assert report["capture_incomplete"] is True
    assert report["commands"][1]["skipped_after_capture_incomplete"] is True


def test_run_manifest_commands_stops_after_incomplete_cleanup_and_records_later_command_not_run(
    monkeypatch, tmp_path,
):
    import tools.vst.execution_grant as execution_grant
    import tools.vst.sandbox as sandbox
    import tools.vst.signer as signer

    posix_os = _posix_runner_os(monkeypatch)
    posix_os.geteuid = lambda: 997
    posix_os.getegid = lambda: 988
    monkeypatch.setattr(execution_grant, "os", posix_os)
    manifest, _registry, _reviewer_key, _keys = _authority_fixture()
    parser_id, parser_version, parser_digest = next(iter(contracts.TRUSTED_PARSER_CATALOG))
    commands = [["synthetic-command", "first"], ["synthetic-command", "second"]]
    manifest["allowed_commands"] = [{"slot": "tests", "argv": argv} for argv in commands]
    manifest["mandatory_commands"] = [
        {"slot": "tests", "argv": argv, "parser_id": parser_id,
         "parser_version": parser_version, "parser_sha256": parser_digest}
        for argv in commands
    ]
    grant = {
        "version": 1, "key_id": "grant-key-1", "grant_id": "grant-1",
        "request_id": "request-1", "audience": "vst-runner-service-v1",
        "service_generation": "generation-1",
        "manifest_sha256": contracts.manifest_sha256(manifest),
        "task_id": manifest["task_id"], "slot": "tests", "attempt": 1,
        "epoch": 2, "run_id": "run-1", "invocation_id": "inv-s2-stop-v2",
        "runner_id": "runner-s2", "resolved_model": "synthetic",
        "model_provenance_sha256": "e" * 64, "execution_deadline_sec": 30,
        "issued_at": 1000.0, "claim_expires_at": 1030.0,
        "expires_at": 1090.0, "signature": "isolated-test-grant",
    }

    def verify_isolated_grant(received, trusted_keys, *, audience, service_generation, openssl_path):
        assert received == grant
        assert trusted_keys == {"grant-key-1": "/isolated-test/grant.pub"}
        assert audience == grant["audience"]
        assert service_generation == grant["service_generation"]
        assert openssl_path == "/isolated-test/openssl"
        return dict(grant)

    monkeypatch.setattr(execution_grant, "verify_execution_grant", verify_isolated_grant)
    claim_calls = []
    reserve_calls = []
    completed_receipts = []

    def claim(received):
        claim_calls.append(received)
        return None

    def reserve(received):
        reserve_calls.append(received)
        return {
            "state": "EXECUTION_RESERVED", "grant_id": received["grant_id"],
            "payload_sha256": hashlib.sha256(contracts.canonical_bytes(received)).hexdigest(),
            "service_generation": "generation-1",
        }

    authority = execution_grant.ExecutionAuthority(
        grant, daemon_uid=997, service_generation="generation-1",
        trusted_keys={"grant-key-1": "/isolated-test/grant.pub"},
        openssl_path="/isolated-test/openssl", audience=grant["audience"],
        daemon_boundary_check=lambda: True,
        claim=claim,
        claim_status=lambda _received: {"state": "PENDING", "service_generation": "generation-1"},
        terminalize_no_execution=lambda _received, _reason: None,
        reserve=reserve,
        complete=lambda _received, receipt: completed_receipts.append(receipt),
    )
    monkeypatch.setattr(sandbox, "require_distinct_worker_identity", lambda _uid: None)
    monkeypatch.setattr(sandbox, "require_runner_can_access_signer", lambda _socket: None)
    monkeypatch.setattr(sandbox, "require_worker_cannot_access_signer", lambda *_a, **_k: None)
    monkeypatch.setattr(signer, "authorize_runner_over_socket", lambda _socket, **_kwargs: None)
    monkeypatch.setattr(
        signer, "sign_diff_over_socket",
        lambda _socket, _request_id, evidence, **_kwargs: sign(evidence, SIGNER_KEY, DIFF_GATE_LABEL),
    )
    monkeypatch.setattr(
        signer, "sign_over_socket",
        lambda _socket, request, **_kwargs: sign(request, SIGNER_KEY, SIGNING_REQUEST_LABEL),
    )
    monkeypatch.setattr(runner, "_derive_head", lambda _cwd: "a" * 40)
    monkeypatch.setattr(runner, "_diff_paths", lambda *_a: (b"", [], [], []))
    launched = []
    pre_spawn_callbacks = []

    def incomplete(argv, *_args, **kwargs):
        pre_spawn = kwargs["_before_spawn"]
        pre_spawn()
        pre_spawn_callbacks.append("reserved-and-verified")
        launched.append(argv)
        return runner.EXIT_CAPTURE_INCOMPLETE, "", {
            "stdout_truncated": False, "stderr_truncated": False,
            "timed_out": False, "capture_incomplete": True, "job_object": False,
        }

    monkeypatch.setattr(runner, "_run_one", incomplete)
    report = {}
    receipt = runner.run_manifest_commands(
        manifest=manifest, slot="tests", attempt=1, epoch=2, resolved_model="synthetic",
        invocation_id="inv-s2-stop-v2", runner_id="runner-s2", signer_socket="unused",
        cwd=str(tmp_path), worker_uid=999, worker_gid=989,
        worker_exec_helper_head=_WORKER_HELPER_HEAD,
        worker_exec_helper_path=_WORKER_HELPER_PATH,
        verify_worker_exec_helper=lambda: None,
        run_id="run-1", model_provenance_sha256="e" * 64,
        execution_authority=authority,
        created_at="2026-10-27T00:00:00Z", timeout_sec=30, deadline_sec=30, report=report,
    )

    assert launched == [commands[0]]
    assert pre_spawn_callbacks == ["reserved-and-verified"]
    assert len(claim_calls) == 1
    assert len(reserve_calls) == 1
    assert len(completed_receipts) == 1
    assert authority.reservation_confirmed is True
    assert authority.completion_confirmed is True
    assert receipt["result"] == "INCONCLUSIVE"
    assert receipt["executed_test_ids"] == []
    assert [entry["exit_code"] for entry in receipt["commands"]] == [
        runner.EXIT_CAPTURE_INCOMPLETE, runner.EXIT_CAPTURE_INCOMPLETE,
    ]
    assert receipt["parser_results"][1]["parser_result"] == {
        "executed_test_ids": [], "skipped_test_ids": [], "xfail_test_ids": [],
    }
    assert report["capture_incomplete"] is True
    assert report["commands"][1]["skipped_after_capture_incomplete"] is True


@pytest.mark.skipif(os.name == "nt", reason="NOT_RUN: POSIX account and Unix-socket permissions are unavailable on Windows")
def test_posix_worker_cannot_read_signer_or_key_file():
    """Drop a child to the provisioned worker identity; all key/socket data is disposable."""
    import grp
    import json
    import pwd
    import shutil
    import socket
    import sys
    import tempfile

    from tools.vst.sandbox import require_private_key, require_worker_cannot_access_signer

    assert os.geteuid() == 0, "run this identity-boundary test in the root test harness"
    worker = pwd.getpwnam("vst-worker")
    runner = pwd.getpwnam("vst-runner")
    signer = pwd.getpwnam("vst-signer")
    runner_gid = grp.getgrnam("vst-runner").gr_gid
    signer_gid = grp.getgrnam("vst-signer").gr_gid
    worker_groups = set(os.getgrouplist(worker.pw_name, worker.pw_gid))
    assert worker.pw_uid not in {runner.pw_uid, signer.pw_uid}
    assert worker.pw_gid not in {runner_gid, signer_gid}
    assert worker_groups.isdisjoint({runner_gid, signer_gid})

    fixture_root = tempfile.mkdtemp(prefix="vst-worker-boundary-", dir="/tmp")
    os.chmod(fixture_root, 0o755)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    keys_dir = None
    ipc_dir = None
    try:
        keys_dir = os.path.join(fixture_root, "synthetic-trust-roots")
        os.mkdir(keys_dir)
        os.chmod(keys_dir, 0o700)
        key_paths = []
        for role in ("worker", "supervisor", "operator", "event", "reviewer", "runner-signer"):
            key_path = os.path.join(keys_dir, role + ".key")
            with open(key_path, "wb") as stream:
                stream.write(b"synthetic-only-key-fixture")
            os.chmod(key_path, 0o600)
            os.chown(key_path, signer.pw_uid, signer.pw_gid)
            require_private_key(key_path, owner_uid=signer.pw_uid)
            key_paths.append(key_path)
        os.chown(keys_dir, signer.pw_uid, signer.pw_gid)

        ipc_dir = os.path.join(fixture_root, "synthetic-signer-ipc")
        os.mkdir(ipc_dir)
        socket_path = os.path.join(ipc_dir, "fixture.sock")
        listener.bind(socket_path)
        listener.listen(1)
        os.chmod(ipc_dir, 0o710)
        os.chmod(socket_path, 0o660)
        os.chown(socket_path, signer.pw_uid, runner_gid)
        os.chown(ipc_dir, 0, runner_gid)
        require_worker_cannot_access_signer(
            socket_path, worker_uid=worker.pw_uid, worker_gid=worker.pw_gid,
        )

        child = r'''import json, os, socket, sys
paths, socket_path = sys.argv[1:-1], sys.argv[-1]
denied = 0
for path in paths:
    try:
        with open(path, "rb") as stream:
            stream.read(1)
    except PermissionError:
        denied += 1
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    try:
        client.connect(socket_path)
        socket_denied = False
    except PermissionError:
        socket_denied = True
finally:
    client.close()
print(json.dumps({"uid": os.getuid(), "gid": os.getgid(), "groups": os.getgroups(),
                  "key_files_denied": denied, "socket_connect_denied": socket_denied}))
if denied != len(paths) or not socket_denied:
    raise SystemExit(2)
'''

        def drop_to_worker():
            os.setgroups(os.getgrouplist(worker.pw_name, worker.pw_gid))
            os.setgid(worker.pw_gid)
            os.setuid(worker.pw_uid)

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        completed = subprocess.run(
            [sys.executable, "-c", child, *key_paths, socket_path],
            cwd=repo_root,
            env={"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, check=False, preexec_fn=drop_to_worker,
        )
        assert completed.returncode == 0, "worker identity probe failed"
        observed = json.loads(completed.stdout)
        assert observed["uid"] == worker.pw_uid
        assert observed["gid"] == worker.pw_gid
        assert set(observed["groups"]).isdisjoint({runner_gid, signer_gid})
        assert observed["key_files_denied"] == len(key_paths)
        assert observed["socket_connect_denied"] is True
    finally:
        listener.close()
        for fixture_dir in (keys_dir, ipc_dir):
            if fixture_dir is not None and os.path.isdir(fixture_dir):
                os.chown(fixture_dir, 0, 0)
                os.chmod(fixture_dir, 0o700)
        shutil.rmtree(fixture_root)


@pytest.mark.skipif(os.name == "nt", reason="NOT_RUN: POSIX worker capabilities require the provisioned WSL sandbox")
def test_runner_drops_uid_change_capabilities_before_worker_command():
    """VST-011: actual runner launch drops capabilities before the worker command."""
    import pwd

    runner_account = pwd.getpwnam("vst-runner")
    worker_account = pwd.getpwnam("vst-worker")
    signer_account = pwd.getpwnam("vst-signer")
    if os.geteuid() != runner_account.pw_uid:
        pytest.skip("requires runner UID with the provisioned ambient capability profile")

    cap_setgid_setuid = (1 << 6) | (1 << 7)
    with open("/proc/self/status", encoding="ascii") as status_file:
        current_status = {
            line.split(":", 1)[0]: line.split(":", 1)[1].strip()
            for line in status_file
            if ":" in line
        }
    if int(current_status.get("CapAmb", "0"), 16) & cap_setgid_setuid != cap_setgid_setuid:
        pytest.skip("requires runner AmbientCapabilities=CAP_SETGID,CAP_SETUID")

    child = r'''import json, os, sys
status = {}
with open("/proc/self/status", encoding="ascii") as stream:
    for line in stream:
        if line.startswith(("CapEff:", "CapPrm:", "CapInh:", "CapAmb:")):
            name, value = line.split(":", 1)
            status[name] = value.strip()
try:
    os.setuid(int(sys.argv[1]))
    can_change_uid = True
except PermissionError:
    can_change_uid = False
print(json.dumps({"caps": status, "can_change_uid": can_change_uid}))
if can_change_uid or any(int(value, 16) != 0 for value in status.values()):
    raise SystemExit(2)
'''
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    installed_head = _derive_head(repo_root)
    assert len(installed_head) == 40
    code, output, info = runner._run_one(
        [sys.executable, "-c", child, str(signer_account.pw_uid)],
        repo_root, 5, {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
        4096, worker_uid=worker_account.pw_uid, worker_gid=worker_account.pw_gid,
        worker_exec_helper_path=(
            "/usr/local/libexec/vst-s4-worker-exec-" + installed_head
        ),
    )

    assert code == 0, f"worker capability probe failed: {output!r} {info!r}"
    result = json.loads(output)
    assert result["can_change_uid"] is False
    assert set(result["caps"]) == {"CapEff", "CapPrm", "CapInh", "CapAmb"}
    assert all(int(value, 16) == 0 for value in result["caps"].values())


@pytest.mark.parametrize("scenario", [
    "posix_process_group_cleanup",
    "post_exit_descendant_cleanup",
    "key_file_permissions_for_worker_identity",
    "windows_parent_job_nesting",
])
@pytest.mark.skip(reason="NOT_RUN: E4 platform containment requires the provisioned POSIX sandbox or an authorized nested Windows Job Object host; process-kill/kill-table execution is explicitly prohibited")
def test_e4_platform_containment_scenarios_not_run(scenario):
    pytest.skip(scenario)

