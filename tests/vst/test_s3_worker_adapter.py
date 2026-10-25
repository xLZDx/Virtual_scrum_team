"""S3-AC-1..4 and Store-backed recovery contracts for the worker protocol."""
from __future__ import annotations

import subprocess
from dataclasses import replace

import pytest

from tools.vst.slice import (
    EVENT_KEY, OPERATOR_KEY, SLICE_KEY, SUPERVISOR_KEY, FakeClock,
    HandWrittenWorker, SliceFixture,
)
from tools.vst.pilot import HandWrittenWorkerAdapter
from tools.vst.store import StoreError
from tools.vst.worker_adapter import (
    Checkpoint, ResumeRequest, StopRequest, WorkerError, WorkerErrorCode,
    WorkerRequest, WorkerResponse, WorkerState, effect_key_for, operation_key_for,
)


REV = "a" * 40
HEAD = "b" * 40
MANIFEST = "c" * 64


def _git(repository, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args], check=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def request(**changes) -> WorkerRequest:
    base = dict(
        operation_key=operation_key_for("attempt", "run-1", "attempt-1"),
        effect_key="pending", run_id="run-1", attempt_id="attempt-1",
        candidate_id="handwritten-v1", candidate_revision=REV,
        manifest_sha256=MANIFEST, task_id="task-1", story_id="story-1",
        attempt=1, epoch=1, fence=1, budget_cap=5, budget_spent=0,
        budget_units=2, allowed_paths=("src/synthetic.py",),
        change_path="src/synthetic.py", change_content="value = 1\n",
        invocation_id="invoke-1", sandbox_run_id="sandbox-1", base_head=HEAD,
    )
    base.update(changes)
    base["effect_key"] = effect_key_for(
        base["run_id"], base["candidate_id"], base["candidate_revision"],
        base["manifest_sha256"], base["task_id"], base["story_id"],
        base["base_head"], base["allowed_paths"], base["change_path"],
        base["change_content"],
    )
    return WorkerRequest(**base)


def test_ac1_request_contract_enforces_identity_fence_and_payload_bounds():
    req = request()
    assert req.operation_key == operation_key_for("attempt", req.run_id, req.attempt_id)
    assert req.fence == req.epoch == 1
    for change in (
        {"fence": 2}, {"attempt": True}, {"allowed_paths": ("../outside",)},
        {"change_path": "../outside"}, {"change_content": "x" * (64 * 1024 + 1)},
        {"budget_units": 0}, {"candidate_revision": "A" * 40},
    ):
        with pytest.raises(ValueError):
            request(**change)


def test_ac1_response_contract_rejects_untyped_or_oversized_worker_claims():
    req = request()
    good = dict(
        run_id=req.run_id, attempt_id=req.attempt_id, operation_key=req.operation_key,
        effect_key=req.effect_key, candidate_id=req.candidate_id,
        candidate_revision=req.candidate_revision, manifest_sha256=req.manifest_sha256,
        epoch=1, fence=1, invocation_id=req.invocation_id,
        sandbox_run_id=req.sandbox_run_id, state=WorkerState.INCONCLUSIVE,
        error=WorkerError(WorkerErrorCode.UNAVAILABLE, "pending"),
    )
    response = WorkerResponse(**good)
    assert response.state is WorkerState.INCONCLUSIVE
    for change in ({"state": "SUCCEEDED"}, {"fence": 2}, {"progress": "x" * 4097},
                   {"evidence_refs": tuple(str(i) for i in range(33))}):
        with pytest.raises(ValueError):
            WorkerResponse(**(good | change))


def test_ac2_resume_and_stop_requests_require_new_fence_and_bound_keys():
    first = request()
    second = request(attempt_id="attempt-2", attempt=2, epoch=2, fence=2,
                     operation_key=operation_key_for("attempt", "run-1", "attempt-2"))
    resume = ResumeRequest(
        operation_key=second.operation_key, prior_operation_key=first.operation_key,
        prior_attempt_id=first.attempt_id, prior_attempt=1, prior_epoch=1,
        request=second, remaining_budget=3,
    )
    assert resume.request.attempt == 2 and resume.request.epoch > resume.prior_epoch
    with pytest.raises(ValueError, match="newer Store epoch"):
        ResumeRequest(**(resume.__dict__ | {"request": replace(second, epoch=1, fence=1)}))
    stop = StopRequest(
        operation_key=operation_key_for("stop", first.run_id, first.attempt_id),
        effect_key=first.effect_key, run_id=first.run_id, attempt_id=first.attempt_id,
        attempt=1, candidate_id=first.candidate_id, candidate_revision=first.candidate_revision,
        manifest_sha256=first.manifest_sha256, task_id=first.task_id, story_id=first.story_id,
        sandbox_run_id=first.sandbox_run_id, allowed_paths=first.allowed_paths,
        budget_cap=5, budget_units=2, budget_remaining=3, epoch=1, fence=1,
        reason="operator requested stop", authorized_actor="operator-1", invocation_id="invoke-1",
    )
    assert stop.operation_key == operation_key_for("stop", stop.run_id, stop.attempt_id)


def test_ac3_idempotency_replay_returns_original_and_rejects_changed_payload(tmp_path):
    fx = SliceFixture(str(tmp_path), SLICE_KEY, FakeClock(),
                      supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
                      event_key=EVENT_KEY)
    try:
        calls = []
        assert fx.store.execute_idempotent("op-same", "synthetic", {"x": 1},
                                           lambda _conn: calls.append(1) or {"state": "PENDING"}) == {"state": "PENDING"}
        assert fx.store.execute_idempotent("op-same", "synthetic", {"x": 1},
                                           lambda _conn: calls.append(2) or {}) == {"state": "PENDING"}
        assert calls == [1]
        with pytest.raises(StoreError, match="different operation or payload"):
            fx.store.execute_idempotent("op-same", "synthetic", {"x": 2}, lambda _conn: {})
    finally:
        fx.close()


def test_ac3_budget_exact_cap_replay_over_cap_and_stale_snapshot(tmp_path):
    fx = SliceFixture(str(tmp_path), SLICE_KEY, FakeClock(),
                      supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
                      event_key=EVENT_KEY)
    try:
        fx.store.set_budget(fx.task_id, 3)
        assert fx.store.charge_idempotent("budget-1", fx.task_id, 2,
            supervisor_key=SUPERVISOR_KEY, expected_cap=3, expected_spent=0) == 1
        assert fx.store.charge_idempotent("budget-1", fx.task_id, 2,
            supervisor_key=SUPERVISOR_KEY, expected_cap=3, expected_spent=0) == 1
        with pytest.raises(StoreError) as stale:
            fx.store.charge_idempotent("budget-stale", fx.task_id, 1,
                supervisor_key=SUPERVISOR_KEY, expected_cap=3, expected_spent=0)
        assert stale.value.kind == "budget_snapshot"
        assert fx.store.charge_idempotent("budget-exact", fx.task_id, 1,
            supervisor_key=SUPERVISOR_KEY, expected_cap=3, expected_spent=2) == 0
        with pytest.raises(StoreError) as over:
            fx.store.charge_idempotent("budget-over", fx.task_id, 1,
                supervisor_key=SUPERVISOR_KEY, expected_cap=3, expected_spent=3)
        assert over.value.kind == "budget"
        marker_count = len(fx.store.receipts_for_task(fx.task_id))
        with pytest.raises(StoreError):
            fx.store.charge_idempotent("budget-over", fx.task_id, 1,
                supervisor_key=SUPERVISOR_KEY, expected_cap=3, expected_spent=3)
        assert len(fx.store.receipts_for_task(fx.task_id)) == marker_count
    finally:
        fx.close()


def test_ac3_zero_budget_allows_zero_charge_but_blocks_positive_charge(tmp_path):
    fx = SliceFixture(str(tmp_path), SLICE_KEY, FakeClock(),
                      supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
                      event_key=EVENT_KEY)
    try:
        fx.store.set_budget(fx.task_id, 0)
        assert fx.store.charge_idempotent("budget-zero", fx.task_id, 0,
            supervisor_key=SUPERVISOR_KEY, expected_cap=0, expected_spent=0) == 0
        with pytest.raises(StoreError) as over:
            fx.store.charge_idempotent("budget-zero-over", fx.task_id, 1,
                supervisor_key=SUPERVISOR_KEY, expected_cap=0, expected_spent=0)
        assert over.value.kind == "budget"
    finally:
        fx.close()


def test_ac4_resume_accepts_only_returned_named_app_checkpoint_and_is_idempotent(tmp_path):
    fx = SliceFixture(str(tmp_path), SLICE_KEY, FakeClock(),
                      supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
                      event_key=EVENT_KEY)
    try:
        fx.begin(1)
        fx.end()
        prior_key = operation_key_for("attempt", "run-1", "attempt-1")
        outcome_key = "outcome-attempt-1"
        recovery = {
            "state": "INCONCLUSIVE", "error_code": "INTERRUPTED",
            "checkpoint": Checkpoint.AFTER_EDIT_BEFORE_COMMIT.value,
            "execution_returned": True, "attempt": 1, "epoch": fx.epoch,
        }
        fx.store.execute_idempotent(outcome_key, "s3_attempt_outcome", {"attempt": 1},
                                    lambda _conn: recovery)
        first = fx.store.resume_epoch_idempotent(
            "resume-op", fx.task_id, fx.story_id, 1, fx.epoch, outcome_key,
            recovery, fx.owner, "resume-owner", 600,
        )
        assert first == fx.epoch + 1
        assert fx.store.resume_epoch_idempotent(
            "resume-op", fx.task_id, fx.story_id, 1, fx.epoch, outcome_key,
            recovery, fx.owner, "resume-owner", 600,
        ) == first
        assert fx.store.current_epoch(fx.story_id) == first
        assert prior_key == operation_key_for("attempt", "run-1", "attempt-1")
    finally:
        fx.close()


def test_ac4_worker_state_alone_never_creates_verification_receipts(tmp_path):
    fx = SliceFixture(str(tmp_path), SLICE_KEY, FakeClock(),
                      supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
                      event_key=EVENT_KEY)
    try:
        before = fx.store.receipts_for_task(fx.task_id)
        worker_claim = WorkerResponse(
            run_id="run-1", attempt_id="attempt-1", operation_key="op-1",
            effect_key="effect-1", candidate_id="candidate-1", candidate_revision=REV,
            manifest_sha256=MANIFEST, epoch=fx.epoch, fence=fx.epoch,
            invocation_id="invoke-1", sandbox_run_id="sandbox-1",
            state=WorkerState.INCONCLUSIVE,
            error=WorkerError(WorkerErrorCode.UNAVAILABLE, "pending"),
        )
        assert worker_claim.state is WorkerState.INCONCLUSIVE
        assert fx.store.receipts_for_task(fx.task_id) == before == []
        assert fx.gate()["verdict"] != "APPROVE"
    finally:
        fx.close()


def test_ac7_commit_suppresses_repository_pre_commit_commit_msg_and_post_commit_hooks(tmp_path):
    """S3-M01: repository-local hook configuration cannot execute at commit."""
    repository = tmp_path / "candidate"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "Synthetic Worker")
    _git(repository, "config", "user.email", "worker@example.invalid")
    source = repository / "src" / "synthetic.py"
    source.parent.mkdir()
    source.write_text("value = 'base'\n", encoding="utf-8")
    _git(repository, "add", "--", "src/synthetic.py")
    _git(repository, "commit", "-m", "synthetic base")

    hooks = repository / ".git" / "candidate-hooks"
    hooks.mkdir()
    for hook_name in ("pre-commit", "commit-msg", "post-commit"):
        hook = hooks / hook_name
        hook.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$0\" >> \"$(git rev-parse --git-dir)/hook-marker\"\n",
            encoding="utf-8",
        )
        hook.chmod(hook.stat().st_mode | 0o111)
    _git(repository, "config", "core.hooksPath", str(hooks))
    marker = repository / ".git" / "hook-marker"
    assert not marker.exists()

    # Prove the temporary hooks are executable in this Git environment, then
    # clear only their disposable-fixture marker before exercising the adapter.
    source.write_text("value = 'hook calibration'\n", encoding="utf-8")
    _git(repository, "add", "--", "src/synthetic.py")
    _git(repository, "-c", f"core.hooksPath={hooks}", "commit", "-m", "hook calibration")
    assert marker.is_file()
    assert len(marker.read_text(encoding="utf-8").splitlines()) == 3
    marker.unlink()
    base_head = _git(repository, "rev-parse", "--verify", "HEAD")

    worker = HandWrittenWorker(str(repository))
    adapter = HandWrittenWorkerAdapter(
        worker, candidate_id="handwritten-v1", candidate_revision=base_head,
    )
    adapter.fence_check = lambda _request: True
    req = request(candidate_id="handwritten-v1", candidate_revision=base_head,
                  base_head=base_head)

    response = adapter.start(req)

    assert response.state is WorkerState.SUCCEEDED
    assert response.candidate_head != base_head
    assert not marker.exists()
    assert _git(repository, "config", "--get", "core.hooksPath") == str(hooks)
