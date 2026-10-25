"""S3 pilot journeys through the real in-repository Store and Supervisor.

These tests use isolated synthetic Git repositories and SQLite stores. They do
not invoke sandbox mode, external candidate tools, or operating-system kill
paths; real sandbox acceptance requires the provisioned signed-probe boundary.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace

import pytest

from tools.vst.pilot import (
    HandWrittenWorkerAdapter,
    InterruptedAfterEditBeforeCommit,
    SyntheticStoryPilot,
)
from tools.vst.slice import (
    EVENT_KEY,
    OPERATOR_KEY,
    SLICE_KEY,
    SUPERVISOR_KEY,
    FakeClock,
    HandWrittenWorker,
    SliceFixture,
)
from tools.vst.supervisor import Supervisor
from tools.vst.worker_adapter import (
    Checkpoint,
    ResumeRequest,
    StopRequest,
    WorkerErrorCode,
    WorkerRequest,
    WorkerState,
    effect_key_for,
    operation_key_for,
)


def _git(repository, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args], check=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


@pytest.fixture
def pilot_env(tmp_path):
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
    candidate_revision = _git(repository, "rev-parse", "--verify", "HEAD")

    fixture = SliceFixture(
        str(tmp_path / "control"), SLICE_KEY, FakeClock(),
        supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
        event_key=EVENT_KEY,
    )
    worker = HandWrittenWorker(str(repository))
    adapter = HandWrittenWorkerAdapter(
        worker, candidate_id="synthetic-candidate", candidate_revision=candidate_revision,
    )
    supervisor = Supervisor(fixture.store, operation_backend=object())
    pilot = SyntheticStoryPilot(fixture, supervisor, adapter)
    yield fixture, pilot, repository, candidate_revision
    fixture.close()


def _request(fixture, candidate_revision: str, *, attempt: int = 1, epoch: int | None = None,
             path: str = "src/synthetic.py", content: str = "value = 'candidate'\n"):
    run_id = "s3-e2e-run"
    attempt_id = f"attempt-{attempt}"
    actual_epoch = fixture.epoch if epoch is None else epoch
    operation_key = operation_key_for("attempt", run_id, attempt_id)
    allowed_paths = (path,)
    effect_key = effect_key_for(
        run_id, "synthetic-candidate", candidate_revision,
        fixture.manifest_hash, fixture.task_id, fixture.story_id,
        fixture.current_head, allowed_paths, path, content,
    )
    return WorkerRequest(
        operation_key=operation_key,
        effect_key=effect_key,
        run_id=run_id,
        attempt_id=attempt_id,
        candidate_id="synthetic-candidate",
        candidate_revision=candidate_revision,
        manifest_sha256=fixture.manifest_hash,
        task_id=fixture.task_id,
        story_id=fixture.story_id,
        attempt=attempt,
        epoch=actual_epoch,
        fence=actual_epoch,
        budget_cap=fixture.manifest["cost_cap"],
        budget_spent=attempt - 1,
        budget_units=1,
        allowed_paths=allowed_paths,
        change_path=path,
        change_content=content,
        invocation_id=f"invocation-{attempt}",
        sandbox_run_id="synthetic-local-run",
        base_head=fixture.current_head,
    )


def _stop_request(original):
    return StopRequest(
        operation_key=operation_key_for("stop", original.run_id, original.attempt_id),
        effect_key=original.effect_key,
        run_id=original.run_id,
        attempt_id=original.attempt_id,
        attempt=original.attempt,
        candidate_id=original.candidate_id,
        candidate_revision=original.candidate_revision,
        manifest_sha256=original.manifest_sha256,
        task_id=original.task_id,
        story_id=original.story_id,
        sandbox_run_id=original.sandbox_run_id,
        allowed_paths=original.allowed_paths,
        budget_cap=original.budget_cap,
        budget_units=original.budget_units,
        budget_remaining=original.budget_cap - original.budget_units,
        epoch=original.epoch,
        fence=original.fence,
        reason="operator requested stop",
        authorized_actor="synthetic-operator",
        invocation_id=original.invocation_id,
    )


def _inject_app_checkpoint_interrupt(pilot):
    def interrupt(checkpoint):
        if checkpoint == Checkpoint.AFTER_EDIT_BEFORE_COMMIT:
            raise InterruptedAfterEditBeforeCommit("deterministic app checkpoint")

    pilot.adapter.checkpoint_hook = interrupt


def test_s3_pilot_commits_only_the_manifest_scoped_synthetic_change(pilot_env):
    """S3 AC-1/AC-2/AC-3: Store lease, adapter edit, bounded path, no self approval."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)

    response = pilot.start(request)

    assert response.state == WorkerState.SUCCEEDED
    assert response.changed_paths == ("src/synthetic.py",)
    assert response.candidate_head == _git(repository, "rev-parse", "--verify", "HEAD")
    assert (repository / "src" / "synthetic.py").read_text(encoding="utf-8") == "value = 'candidate'\n"
    assert fixture.store.receipts_for_task(fixture.task_id) == []
    assert pilot.status(request) == response
    assert not hasattr(response, "verdict")


def test_s3_pilot_rejects_out_of_scope_edit_before_worker_invocation(pilot_env):
    """S3 AC-1/AC-2: request scope must match the registered story manifest."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision, path="docs/outside.txt")

    response = pilot.start(request)

    assert response.state == WorkerState.BLOCKED
    assert response.error is not None
    assert response.error.code == WorkerErrorCode.SCOPE_DENIED
    assert _git(repository, "rev-parse", "--verify", "HEAD") == candidate_revision
    assert fixture.store.receipts_for_task(fixture.task_id) == []


def test_s3_app_checkpoint_can_resume_same_effect_under_new_store_epoch(pilot_env):
    """S3 AC-3: named app checkpoint resumes without OS process termination."""
    fixture, pilot, repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)

    _inject_app_checkpoint_interrupt(pilot)
    interrupted = pilot.start(original)
    assert interrupted.state == WorkerState.INCONCLUSIVE
    assert interrupted.checkpoint == Checkpoint.AFTER_EDIT_BEFORE_COMMIT
    assert interrupted.error is not None
    assert interrupted.error.code == WorkerErrorCode.INTERRUPTED

    next_epoch = original.epoch + 1
    resumed = _request(fixture, candidate_revision, attempt=2, epoch=next_epoch)
    resume = ResumeRequest(
        operation_key=resumed.operation_key,
        prior_operation_key=original.operation_key,
        prior_attempt_id=original.attempt_id,
        prior_attempt=original.attempt,
        prior_epoch=original.epoch,
        request=resumed,
        remaining_budget=original.budget_cap - original.budget_units,
    )
    pilot.adapter.checkpoint_hook = None

    response = pilot.resume(resume)

    assert response.state == WorkerState.SUCCEEDED
    assert response.effect_key == original.effect_key
    assert response.candidate_head == _git(repository, "rev-parse", "--verify", "HEAD")
    assert fixture.store.current_epoch(fixture.story_id) == next_epoch
    assert len(fixture.store.receipts_for_task(fixture.task_id)) == 0


def test_s3_stop_fences_interrupted_attempt_idempotently_and_rejects_stale_start(pilot_env):
    """S3 AC-4: durable STOP fences the lease; stale epoch cannot start or receipt."""
    fixture, pilot, _repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)

    def interrupt(checkpoint):
        if checkpoint == Checkpoint.AFTER_EDIT_BEFORE_COMMIT:
            raise InterruptedAfterEditBeforeCommit("deterministic app checkpoint")

    pilot.adapter.checkpoint_hook = interrupt
    interrupted = pilot.start(original)
    assert interrupted.state == WorkerState.INCONCLUSIVE

    stop = _stop_request(original)

    first = pilot.stop(stop)
    replay = pilot.stop(stop)
    assert first.state == replay.state == WorkerState.INCONCLUSIVE
    assert first.error is not None
    assert first.error.message == (
        "epoch fenced; adapter.stop completed but worker process cleanup is NOT_VERIFIED"
    )
    assert replay.error == first.error
    assert first.progress == replay.progress
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1
    stale = pilot.start(original)
    assert stale.state == WorkerState.BLOCKED
    assert stale.error is not None
    assert stale.error.code == WorkerErrorCode.FENCE_REJECTED
    assert fixture.store.receipts_for_task(fixture.task_id) == []


def test_s3_stop_cleanup_exception_preserves_fence_and_hides_exception_text(pilot_env, monkeypatch):
    """S3 AC-4: cleanup failures remain non-approving and safely diagnosable."""
    fixture, pilot, _repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)
    _inject_app_checkpoint_interrupt(pilot)
    interrupted = pilot.start(original)
    assert interrupted.state is WorkerState.INCONCLUSIVE

    secret = "PRIVATE_CLEANUP_DETAIL"

    def fail_cleanup(_request):
        raise RuntimeError(secret)

    monkeypatch.setattr(pilot.adapter, "stop", fail_cleanup)
    response = pilot.stop(_stop_request(original))

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error is not None
    assert response.error.code is WorkerErrorCode.INTERRUPTED
    assert response.error.message == (
        "epoch fenced; adapter.stop raised RuntimeError; worker process cleanup is NOT_VERIFIED"
    )
    assert secret not in response.error.message
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1
    assert response.progress == f"new_fence={original.epoch + 1}"
    assert fixture.store.receipts_for_task(fixture.task_id) == []
    stale = pilot.start(original)
    assert stale.state is WorkerState.BLOCKED
    assert stale.error is not None
    assert stale.error.code is WorkerErrorCode.FENCE_REJECTED


@pytest.mark.parametrize("name", ["X" * 65, "invalid name"])
def test_s3_stop_cleanup_exception_class_falls_back_to_bounded_safe_name(
    pilot_env, monkeypatch, name,
):
    """S3 AC-4: non-identifier and overlong exception types are not serialized."""
    fixture, pilot, _repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)
    _inject_app_checkpoint_interrupt(pilot)
    assert pilot.start(original).state is WorkerState.INCONCLUSIVE

    error_type = type("CleanupProblem", (Exception,), {})
    error_type.__name__ = name

    def fail_cleanup(_request):
        raise error_type("untrusted details")

    monkeypatch.setattr(pilot.adapter, "stop", fail_cleanup)
    response = pilot.stop(_stop_request(original))

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error is not None
    assert "adapter.stop raised UnknownError;" in response.error.message
    assert name not in response.error.message
    assert "untrusted details" not in response.error.message
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1


def test_s3_candidate_identity_cannot_be_self_selected(pilot_env):
    """S3 AC-2: caller supplied candidate identity/revision mismatch is blocked."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    forged_candidate = "caller-selected-candidate"
    forged = replace(
        request,
        candidate_id=forged_candidate,
        effect_key=effect_key_for(
            request.run_id, forged_candidate, request.candidate_revision,
            request.manifest_sha256, request.task_id, request.story_id,
            request.base_head, request.allowed_paths, request.change_path,
            request.change_content,
        ),
    )

    response = pilot.start(forged)

    assert response.state == WorkerState.BLOCKED
    assert response.error is not None
    assert response.error.code == WorkerErrorCode.INVALID_REQUEST
    assert _git(repository, "rev-parse", "--verify", "HEAD") == candidate_revision
    assert fixture.store.receipts_for_task(fixture.task_id) == []


# AC-5 (fresh signed probe), AC-6 (actual WSL boundary), and runtime behavior
# across WSL are intentionally NOT_RUN: this file has no trusted probe issuer,
# and a synthetic signed fixture cannot establish the host boundary.
