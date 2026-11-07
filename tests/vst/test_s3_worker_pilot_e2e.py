"""S3 pilot journeys through the real in-repository Store and Supervisor.

These tests use isolated synthetic Git repositories and SQLite stores. They do
not invoke sandbox mode, external candidate tools, or operating-system kill
paths; real sandbox acceptance requires the provisioned signed-probe boundary.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace

import pytest

from tools.vst.pilot import _response as _pilot_response
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
from tools.vst.store import StoreError
from tools.vst.supervisor import Supervisor
from tools.vst.worker_adapter import (
    Checkpoint,
    ResumeRequest,
    StopRequest,
    WorkerError,
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


def _prespend(fixture, units: int) -> None:
    """Charge the authoritative Store ledger directly so a boundary can be reached."""
    fixture.store.charge_idempotent(
        "s3-e2e-prespend", fixture.task_id, units,
        supervisor_key=fixture.supervisor_key,
        expected_cap=fixture.manifest["cost_cap"], expected_spent=0,
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


def test_s3_stop_first_epoch_fence_prevents_late_worker_commit(pilot_env):
    """S3-M02: STOP before publication lock prevents the stopped attempt from writing."""
    fixture, pilot, repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)
    stop_responses = []

    def stop_before_publication_lock(checkpoint):
        if checkpoint is Checkpoint.BEFORE_EDIT:
            # The adapter invokes this checkpoint before taking the shared
            # publication lock. Complete the durable STOP before returning to
            # start(), which then resumes and must reject its stale fence.
            stop_responses.append(pilot.stop(_stop_request(original)))

    pilot.adapter.checkpoint_hook = stop_before_publication_lock
    initial_contents = (repository / "src" / "synthetic.py").read_text(encoding="utf-8")
    initial_head = _git(repository, "rev-parse", "--verify", "HEAD")

    response = pilot.start(original)

    assert len(stop_responses) == 1
    stopped = stop_responses[0]
    assert stopped.state is WorkerState.INCONCLUSIVE
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1
    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error is not None
    assert response.error.code is WorkerErrorCode.FENCE_REJECTED
    assert _git(repository, "rev-parse", "--verify", "HEAD") == initial_head
    assert (repository / "src" / "synthetic.py").read_text(encoding="utf-8") == initial_contents
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1
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


def test_s3_budget_over_cap_request_is_blocked_without_spend_or_write(pilot_env):
    """S3 AC-12: a request already at the cap starts no worker and writes nothing."""
    fixture, pilot, repository, candidate_revision = pilot_env
    cap = fixture.manifest["cost_cap"]
    _prespend(fixture, cap)
    over = replace(_request(fixture, candidate_revision), budget_spent=cap)
    initial_head = _git(repository, "rev-parse", "--verify", "HEAD")

    blocked = pilot.start(over)

    assert blocked.state is WorkerState.BLOCKED
    assert blocked.error is not None
    assert blocked.error.code is WorkerErrorCode.BUDGET_EXHAUSTED
    assert "Store budget cap" in blocked.error.message or "Store refused lease" in blocked.error.message
    assert _git(repository, "rev-parse", "--verify", "HEAD") == initial_head
    assert (repository / "src" / "synthetic.py").read_text(encoding="utf-8") == "value = 'base'\n"
    receipts = fixture.store.receipts_for_task(fixture.task_id)
    assert [r["check_description"] for r in receipts] == ["BUDGET_EXCEEDED"]


def test_s3_budget_exact_cap_attempt_completes_with_zero_remaining(pilot_env):
    """S3 AC-12: an attempt that exactly consumes the cap may complete."""
    fixture, pilot, repository, candidate_revision = pilot_env
    cap = fixture.manifest["cost_cap"]
    _prespend(fixture, cap - 1)
    exact = replace(_request(fixture, candidate_revision), budget_spent=cap - 1)

    done = pilot.start(exact)

    assert done.state is WorkerState.SUCCEEDED
    # The cap is now fully consumed: any further unit is refused by the Store ledger.
    with pytest.raises(StoreError) as refused:
        fixture.store.charge_idempotent(
            "s3-e2e-extra-unit", fixture.task_id, 1,
            supervisor_key=fixture.supervisor_key,
            expected_cap=cap, expected_spent=cap,
        )
    assert refused.value.kind == "budget"
    assert done.candidate_head == _git(repository, "rev-parse", "--verify", "HEAD")


def _resume_for(original, second):
    return ResumeRequest(
        operation_key=second.operation_key,
        prior_operation_key=original.operation_key,
        prior_attempt_id=original.attempt_id,
        prior_attempt=original.attempt,
        prior_epoch=original.epoch,
        request=second,
        remaining_budget=original.budget_cap - original.budget_units,
    )


def _commit_count(repository, candidate_revision: str) -> int:
    return int(_git(repository, "rev-list", "--count", f"{candidate_revision}..HEAD"))


def _install_failing_adapter(pilot):
    """Wrap the real adapter so every worker invocation reports a worker failure."""
    real_adapter = pilot.adapter

    class AlwaysFailing:
        def __init__(self):
            self.calls = 0

        def __getattr__(self, name):
            return getattr(real_adapter, name)

        def start(self, request):
            self.calls += 1
            return _pilot_response(request, WorkerState.FAILED, error=WorkerError(
                WorkerErrorCode.EXECUTION_FAILED, "synthetic worker failure"))

        def resume(self, request):
            return self.start(request.request)

    failing = AlwaysFailing()
    pilot.adapter = failing
    return real_adapter, failing


def test_s3_failed_attempt_is_replayed_then_retried_once_through_resume(pilot_env):
    """S3 AC-11 / m10: FAILED is stored once; resume retries it as a new attempt."""
    fixture, pilot, repository, candidate_revision = pilot_env
    first = _request(fixture, candidate_revision)
    real_adapter, failing = _install_failing_adapter(pilot)

    failed = pilot.start(first)
    assert failed.state is WorkerState.FAILED
    assert failed.error is not None
    assert failed.error.code is WorkerErrorCode.EXECUTION_FAILED
    assert pilot.start(first).state is WorkerState.FAILED
    assert failing.calls == 1
    assert _commit_count(repository, candidate_revision) == 0

    pilot.adapter = real_adapter
    second = _request(fixture, candidate_revision, attempt=2, epoch=first.epoch + 1)
    retried = pilot.resume(_resume_for(first, second))

    assert retried.state is WorkerState.SUCCEEDED
    assert retried.candidate_head == _git(repository, "rev-parse", "--verify", "HEAD")
    assert _commit_count(repository, candidate_revision) == 1
    assert fixture.store.current_epoch(fixture.story_id) == first.epoch + 1
    # The failed attempt stays visible and unchanged; the retry is its own record.
    assert pilot.status(first).state is WorkerState.FAILED
    assert pilot.status(second).state is WorkerState.SUCCEEDED
    # start() still accepts only attempt 1.
    again = pilot.start(second)
    assert again.state is WorkerState.BLOCKED
    assert again.error is not None
    assert again.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert _commit_count(repository, candidate_revision) == 1
    assert fixture.store.receipts_for_task(fixture.task_id) == []


def test_s3_retry_cap_exhaustion_refuses_third_resume_without_advancing_epoch(pilot_env):
    """m10: retry_cap=1 allows two failed attempts; a third resume is refused up front."""
    fixture, pilot, repository, candidate_revision = pilot_env
    assert fixture.manifest["retry_cap"] == 1
    first = _request(fixture, candidate_revision)
    _real, failing = _install_failing_adapter(pilot)

    assert pilot.start(first).state is WorkerState.FAILED
    second = _request(fixture, candidate_revision, attempt=2, epoch=first.epoch + 1)
    assert pilot.resume(_resume_for(first, second)).state is WorkerState.FAILED
    assert fixture.store.current_epoch(fixture.story_id) == first.epoch + 1
    assert failing.calls == 2

    third = _request(fixture, candidate_revision, attempt=3, epoch=first.epoch + 2)
    exhausted = pilot.resume(_resume_for(second, third))

    assert exhausted.state is WorkerState.BLOCKED
    assert exhausted.error is not None
    assert exhausted.error.code is WorkerErrorCode.RETRY_EXHAUSTED
    assert failing.calls == 2
    assert fixture.store.current_epoch(fixture.story_id) == first.epoch + 1
    assert _commit_count(repository, candidate_revision) == 0
    assert pilot.status(first).state is WorkerState.FAILED
    assert pilot.status(second).state is WorkerState.FAILED


def test_s3_resume_replay_after_post_epoch_failure_succeeds_and_changed_payload_fails_closed(
    pilot_env,
):
    """M1: once epoch_resume committed, an honest replay succeeds; a changed payload cannot."""
    fixture, pilot, repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)
    _inject_app_checkpoint_interrupt(pilot)
    assert pilot.start(original).state is WorkerState.INCONCLUSIVE
    pilot.adapter.checkpoint_hook = None

    second = _request(fixture, candidate_revision, attempt=2, epoch=original.epoch + 1)
    real_execute = pilot._execute_attempt
    calls = {"count": 0}

    def fail_once_after_epoch(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("injected supervisor failure after the epoch advance")
        return real_execute(*args, **kwargs)

    pilot._execute_attempt = fail_once_after_epoch
    with pytest.raises(RuntimeError, match="injected supervisor failure"):
        pilot.resume(_resume_for(original, second))
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1
    assert _commit_count(repository, candidate_revision) == 0

    # A changed payload (different content, consistent effect key) must fail closed.
    changed = _request(
        fixture, candidate_revision, attempt=2, epoch=original.epoch + 1,
        content="value = 'tampered'\n",
    )
    refused = pilot.resume(_resume_for(original, changed))
    assert refused.state in {WorkerState.BLOCKED, WorkerState.INCONCLUSIVE}
    assert _commit_count(repository, candidate_revision) == 0
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1

    # The honest replay now reaches the Store and completes exactly once.
    replayed = pilot.resume(_resume_for(original, second))
    assert replayed.state is WorkerState.SUCCEEDED
    assert _commit_count(repository, candidate_revision) == 1
    assert (repository / "src" / "synthetic.py").read_text(encoding="utf-8") == "value = 'candidate'\n"
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1
    assert pilot.resume(_resume_for(original, second)) == replayed
    assert _commit_count(repository, candidate_revision) == 1


def test_s3_resume_with_different_sandbox_run_id_and_timeout_is_not_a_duplicate(pilot_env):
    """M2: per-attempt sandbox_run_id/timeout_sec are not part of the effect payload."""
    fixture, pilot, repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)

    def interrupt(checkpoint):
        if checkpoint == Checkpoint.AFTER_COMMIT_BEFORE_RESPONSE:
            raise InterruptedAfterEditBeforeCommit("deterministic post-commit checkpoint")

    pilot.adapter.checkpoint_hook = interrupt
    interrupted = pilot.start(original)
    assert interrupted.state is WorkerState.INCONCLUSIVE
    assert _commit_count(repository, candidate_revision) == 1
    pilot.adapter.checkpoint_hook = None

    second = replace(
        _request(fixture, candidate_revision, attempt=2, epoch=original.epoch + 1),
        sandbox_run_id="synthetic-other-run", timeout_sec=original.timeout_sec + 7,
    )
    response = pilot.resume(_resume_for(original, second))

    assert response.state is WorkerState.SUCCEEDED
    assert response.effect_key == original.effect_key
    assert response.candidate_head == _git(repository, "rev-parse", "--verify", "HEAD")
    assert _commit_count(repository, candidate_revision) == 1


def _make_side_commit(repository, candidate_revision: str, path: str, content: str) -> str:
    """Create a commit on a side branch off the candidate revision; leave HEAD where it was."""
    original_ref = _git(repository, "rev-parse", "--abbrev-ref", "HEAD")
    _git(repository, "checkout", "-q", "-b", "side-branch", candidate_revision)
    target = repository / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repository, "add", "--", path)
    _git(repository, "commit", "-q", "-m", "side commit")
    head = _git(repository, "rev-parse", "--verify", "HEAD")
    _git(repository, "checkout", "-q", original_ref)
    return head


@pytest.mark.parametrize("case", ["nonexistent", "not_descendant", "out_of_scope"])
def test_s3_succeeded_claim_with_bad_candidate_head_is_inconclusive(pilot_env, case):
    """M3: a SUCCEEDED head must be a real in-scope descendant of the candidate revision."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    if case == "nonexistent":
        bad_head, code = "a" * 40, WorkerErrorCode.RECONCILIATION_REQUIRED
    elif case == "not_descendant":
        empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        bad_head = _git(repository, "commit-tree", empty_tree, "-m", "orphan")
        code = WorkerErrorCode.RECONCILIATION_REQUIRED
    else:
        bad_head = _make_side_commit(repository, candidate_revision, "docs/outside.txt", "x\n")
        code = WorkerErrorCode.SCOPE_DENIED

    def lying_start(req):
        return _pilot_response(
            req, WorkerState.SUCCEEDED, candidate_head=bad_head,
            changed_paths=(req.change_path,), progress="forged success",
        )

    pilot.adapter.start = lying_start
    response = pilot.start(request)

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error is not None
    assert response.error.code is code
    assert fixture.store.receipts_for_task(fixture.task_id) == []


def test_s3_real_success_passes_candidate_head_verification(pilot_env):
    """M3: the verification does not reject a genuine descendant, in-scope commit."""
    fixture, pilot, repository, candidate_revision = pilot_env
    response = pilot.start(_request(fixture, candidate_revision))

    assert response.state is WorkerState.SUCCEEDED
    assert response.error is None
    assert response.candidate_head == _git(repository, "rev-parse", "--verify", "HEAD")
    assert _git(repository, "diff", "--name-only", candidate_revision, response.candidate_head) == "src/synthetic.py"


def test_s3_marker_commit_on_another_branch_is_not_replayed(pilot_env):
    """m8: a marker commit outside HEAD history is never trusted as the durable effect."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    marker = f"vst-worker-effect {request.effect_key}"
    original_ref = _git(repository, "rev-parse", "--abbrev-ref", "HEAD")
    _git(repository, "checkout", "-q", "-b", "side-branch", candidate_revision)
    (repository / "src" / "synthetic.py").write_text(request.change_content, encoding="utf-8")
    _git(repository, "add", "--", "src/synthetic.py")
    _git(repository, "commit", "-q", "-m", marker)
    side_head = _git(repository, "rev-parse", "--verify", "HEAD")
    _git(repository, "checkout", "-q", original_ref)
    assert _git(repository, "rev-parse", "--verify", "HEAD") == candidate_revision

    response = pilot.start(request)

    assert response.state is WorkerState.SUCCEEDED
    assert response.candidate_head != side_head
    assert response.progress == "synthetic change committed"
    assert response.candidate_head == _git(repository, "rev-parse", "--verify", "HEAD")
    assert _commit_count(repository, candidate_revision) == 1


def test_s3_marker_commit_with_different_blob_is_not_replayed(pilot_env):
    """m8: a marker commit on HEAD carrying other content is not the requested effect."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    marker = f"vst-worker-effect {request.effect_key}"
    (repository / "src" / "synthetic.py").write_text("value = 'other'\n", encoding="utf-8")
    _git(repository, "add", "--", "src/synthetic.py")
    _git(repository, "commit", "-q", "-m", marker)
    wrong_head = _git(repository, "rev-parse", "--verify", "HEAD")

    response = pilot.start(request)

    assert response.state is WorkerState.SUCCEEDED
    assert response.candidate_head != wrong_head
    assert response.progress == "synthetic change committed"
    assert (repository / "src" / "synthetic.py").read_text(encoding="utf-8") == "value = 'candidate'\n"
    assert _commit_count(repository, candidate_revision) == 2


def test_s3_missing_probe_and_wrong_sandbox_run_id_are_not_persisted_and_retryable(pilot_env):
    """m1/m3: transient setup refusals do not poison the operation key."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)

    fixture.store.sandbox_mode = True
    try:
        missing = pilot.start(request)
        assert missing.state is WorkerState.BLOCKED
        assert missing.error is not None
        assert missing.error.code is WorkerErrorCode.UNAVAILABLE
        wrong_run = pilot.start(request, probe={"nonce": "synthetic-nonce"})
        assert wrong_run.state is WorkerState.BLOCKED
        assert wrong_run.error is not None
        assert wrong_run.error.code is WorkerErrorCode.INVALID_REQUEST
    finally:
        fixture.store.sandbox_mode = False

    assert fixture.store.lookup_idempotent_operation(
        request.operation_key, operation="s3_attempt") is None
    assert fixture.store.lookup_idempotent_operation(
        request.operation_key, operation="s3_resume") is None
    assert _commit_count(repository, candidate_revision) == 0

    retried = pilot.start(request)
    assert retried.state is WorkerState.SUCCEEDED
    assert _commit_count(repository, candidate_revision) == 1


def test_s3_operation_key_stored_under_another_operation_is_blocked_invalid_request(pilot_env):
    """m2: a duplicate-kind Store lookup error is a typed BLOCKED answer, not a raw raise."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    fixture.store.execute_idempotent(
        request.operation_key, "unrelated_operation", {"seed": 1}, lambda _conn: {"seed": 1},
    )

    started = pilot.start(request)
    status = pilot.status(request)

    for response in (started, status):
        assert response.state is WorkerState.BLOCKED
        assert response.error is not None
        assert response.error.code is WorkerErrorCode.INVALID_REQUEST
    assert _commit_count(repository, candidate_revision) == 0
    assert fixture.store.receipts_for_task(fixture.task_id) == []


def test_s3_stop_progress_records_adapter_stop_outcome(pilot_env):
    """m5: the typed adapter.stop result is visible in STOP progress on the success path."""
    fixture, pilot, _repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)
    _inject_app_checkpoint_interrupt(pilot)
    assert pilot.start(original).state is WorkerState.INCONCLUSIVE

    response = pilot.stop(_stop_request(original))

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.progress is not None
    assert "adapter_stop=STOPPED:INTERRUPTED" in response.progress
    assert response.progress.startswith(f"new_fence={original.epoch + 1}")
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1


# AC-5 (fresh signed probe), AC-6 (actual WSL boundary), and runtime behavior
# across WSL are intentionally NOT_RUN: this file has no trusted probe issuer,
# and a synthetic signed fixture cannot establish the host boundary.
