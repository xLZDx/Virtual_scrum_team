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
    env = _build_env(tmp_path, retry_cap=1)
    yield env
    env[0].close()


def _build_env(tmp_path, *, retry_cap: int):
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
        event_key=EVENT_KEY, retry_cap=retry_cap,
    )
    worker = HandWrittenWorker(str(repository))
    adapter = HandWrittenWorkerAdapter(
        worker, candidate_id="synthetic-candidate", candidate_revision=candidate_revision,
    )
    supervisor = Supervisor(fixture.store, operation_backend=object())
    pilot = SyntheticStoryPilot(fixture, supervisor, adapter)
    return fixture, pilot, repository, candidate_revision


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


# ---------------------------------------------------------------------------
# Remediation round 2 scenarios (R1-R8)
# ---------------------------------------------------------------------------

import tools.vst.pilot as pilot_module  # noqa: E402
from tools.vst.pilot import _store_failure  # noqa: E402


def _attempt_row(fixture, request, operation="s3_attempt"):
    return fixture.store.lookup_idempotent_operation(request.operation_key, operation=operation)


def _lease_statuses(fixture, request) -> list[str]:
    rows = fixture.store._conn.execute(
        "SELECT status FROM leases WHERE task_id = ? ORDER BY attempt", (request.task_id,),
    ).fetchall()
    return [row["status"] for row in rows]


class _LeaseGate:
    """Wrap Store.acquire_lease: raise ``kind`` while ``active``, else delegate."""

    def __init__(self, store, kind: str, *, times: int | None = None):
        self.real = store.acquire_lease
        self.kind = kind
        self.times = times
        self.calls = 0
        self.active = True

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.active and (self.times is None or self.calls <= self.times):
            raise StoreError(f"synthetic {self.kind} refusal", kind=self.kind)
        return self.real(*args, **kwargs)


# ---- R1: lease before intent --------------------------------------------------

@pytest.mark.parametrize("kind,code", [
    ("slot", WorkerErrorCode.UNAVAILABLE),
    ("lease", WorkerErrorCode.RECONCILIATION_REQUIRED),
])
def test_r1_transient_lease_refusal_writes_no_intent_and_same_key_is_retryable(
    pilot_env, monkeypatch, kind, code,
):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    gate = _LeaseGate(fixture.store, kind, times=1)
    monkeypatch.setattr(fixture.store, "acquire_lease", gate)

    refused = pilot.start(request)

    assert refused.state is WorkerState.BLOCKED
    assert refused.error is not None and refused.error.code is code
    assert f"Store refused lease: {kind}" in refused.error.message
    assert _attempt_row(fixture, request) is None
    assert _commit_count(repository, candidate_revision) == 0
    assert _lease_statuses(fixture, request) == []

    retried = pilot.start(request)

    assert retried.state is WorkerState.SUCCEEDED
    assert gate.calls == 2
    assert _commit_count(repository, candidate_revision) == 1
    assert _attempt_row(fixture, request)["state"] == "COMPLETED"


def test_r1_real_slot_exhaustion_is_retryable_after_a_slot_frees(pilot_env):
    """Same as above against the real Store: occupy every slot, then free them."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    assert fixture.store._conn.execute("SELECT slot_no FROM slots").fetchall()
    # Occupy every slot with a foreign holder (FK checks off only for this seeding).
    fixture.store._conn.execute("PRAGMA foreign_keys = OFF")
    try:
        with fixture.store._tx() as tx:
            tx.execute("UPDATE slots SET lease_id = 999999, expires_at = 9e18")
    finally:
        fixture.store._conn.execute("PRAGMA foreign_keys = ON")
    refused = pilot.start(request)
    assert refused.state is WorkerState.BLOCKED
    assert refused.error is not None and refused.error.code is WorkerErrorCode.UNAVAILABLE
    assert _attempt_row(fixture, request) is None
    assert _commit_count(repository, candidate_revision) == 0

    with fixture.store._tx() as tx:
        tx.execute("UPDATE slots SET lease_id = NULL, expires_at = NULL")
    assert pilot.start(request).state is WorkerState.SUCCEEDED
    assert _commit_count(repository, candidate_revision) == 1


@pytest.mark.parametrize("kind,code", [
    ("epoch", WorkerErrorCode.FENCE_REJECTED),
    ("retry", WorkerErrorCode.RETRY_EXHAUSTED),
    ("terminal", WorkerErrorCode.UNSUPPORTED_STATE),
    ("budget", WorkerErrorCode.BUDGET_EXHAUSTED),
])
def test_r1_terminal_lease_refusal_is_persisted_blocked_and_replayed_identically(
    pilot_env, monkeypatch, kind, code,
):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    gate = _LeaseGate(fixture.store, kind)
    monkeypatch.setattr(fixture.store, "acquire_lease", gate)

    first = pilot.start(request)

    assert first.state is WorkerState.BLOCKED
    assert first.error is not None and first.error.code is code
    row = _attempt_row(fixture, request)
    assert row is not None and row["state"] == "COMPLETED"
    assert gate.calls == 1

    gate.active = False  # Store would now grant the lease; the stored refusal still wins.
    second = pilot.start(request)

    assert second == first
    assert gate.calls == 1
    assert _commit_count(repository, candidate_revision) == 0
    assert _lease_statuses(fixture, request) == []


@pytest.mark.parametrize("kind,state", [
    ("schema", WorkerState.BLOCKED),
    ("busy", WorkerState.INCONCLUSIVE),
])
def test_r1_unmapped_lease_kind_goes_through_store_failure_and_is_not_persisted(
    pilot_env, monkeypatch, kind, state,
):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    monkeypatch.setattr(fixture.store, "acquire_lease", _LeaseGate(fixture.store, kind))

    response = pilot.start(request)

    assert response.state is state
    assert response.error is not None
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert response.error.message.startswith("lease acquisition: StoreError: kind=" + kind)
    assert ("(not retryable)" in response.error.message) == (state is WorkerState.BLOCKED)
    assert _attempt_row(fixture, request) is None
    assert _commit_count(repository, candidate_revision) == 0


@pytest.mark.parametrize("verdict", [WorkerState.BLOCKED, WorkerState.INCONCLUSIVE])
def test_r1_lease_is_released_when_validation_after_acquire_refuses(
    pilot_env, monkeypatch, verdict,
):
    """A lease acquired before the intent must not leak when the attempt never starts."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    real_validate = pilot._validate_request
    calls = {"count": 0}

    def validate(req):
        calls["count"] += 1
        if calls["count"] == 1:
            return real_validate(req)
        return _pilot_response(req, verdict, error=WorkerError(
            WorkerErrorCode.UNAVAILABLE, "synthetic late refusal"))

    monkeypatch.setattr(pilot, "_validate_request", validate)

    response = pilot.start(request)

    assert calls["count"] == 2
    if verdict is WorkerState.BLOCKED:
        assert response.state is WorkerState.BLOCKED
        assert response.error.code is WorkerErrorCode.UNAVAILABLE
        assert _attempt_row(fixture, request)["state"] == "COMPLETED"
    else:
        assert response.state is WorkerState.INCONCLUSIVE
        assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
        row = _attempt_row(fixture, request)
        assert row is None or row["state"] != "COMPLETED"
    assert _lease_statuses(fixture, request) == ["RELEASED"]
    assert _commit_count(repository, candidate_revision) == 0
    assert fixture.store.receipts_for_task(fixture.task_id) == []


def test_r1_lease_is_released_when_the_attempt_raises_before_the_charge(pilot_env, monkeypatch):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)

    def boom(*_a, **_k):
        raise RuntimeError("PRIVATE_BUDGET_DETAIL")

    monkeypatch.setattr(fixture.store, "charge_idempotent", boom)
    response = pilot.start(request)

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert "PRIVATE_BUDGET_DETAIL" not in response.error.message
    assert _lease_statuses(fixture, request) == ["RELEASED"]
    assert _commit_count(repository, candidate_revision) == 0


def test_r2_same_operation_key_with_different_payload_stays_blocked_invalid_request(pilot_env):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    assert pilot.start(request).state is WorkerState.SUCCEEDED
    changed = _request(fixture, candidate_revision, content="value = 'tampered'\n")

    refused = pilot.start(changed)

    assert refused.state is WorkerState.BLOCKED
    assert refused.error is not None and refused.error.code is WorkerErrorCode.INVALID_REQUEST
    assert _commit_count(repository, candidate_revision) == 1


# ---- R2: transient allow-list -------------------------------------------------

@pytest.mark.parametrize("kind", [
    "schema", "signature", "authorization", "supervisor", "manifest", "key", "lifecycle", "epoch",
])
def test_r2_non_transient_store_kinds_are_blocked_and_not_retryable(pilot_env, kind):
    fixture, _pilot, _repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)

    response = _store_failure(request, StoreError("PRIVATE_TEXT", kind=kind), "ctx")

    assert response.state is WorkerState.BLOCKED
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert response.error.message == f"ctx: StoreError: kind={kind} (not retryable)"
    assert "PRIVATE_TEXT" not in response.error.message


@pytest.mark.parametrize("kind", ["busy", "slot", "lease"])
def test_r2_transient_store_kinds_are_inconclusive_and_retryable(pilot_env, kind):
    fixture, _pilot, _repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)

    response = _store_failure(request, StoreError("PRIVATE_TEXT", kind=kind), "ctx")

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert response.error.message == f"ctx: StoreError: kind={kind}"
    assert "not retryable" not in response.error.message


def test_r2_duplicate_kind_is_blocked_invalid_request(pilot_env):
    fixture, _pilot, _repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    response = _store_failure(request, StoreError("x", kind="duplicate"), "ctx")
    assert response.state is WorkerState.BLOCKED
    assert response.error.code is WorkerErrorCode.INVALID_REQUEST


@pytest.mark.parametrize("kind,state,suffix", [
    ("schema", WorkerState.BLOCKED, " (not retryable)"),
    ("busy", WorkerState.INCONCLUSIVE, ""),
])
def test_r2_resume_fence_store_error_goes_through_store_failure(
    pilot_env, monkeypatch, kind, state, suffix,
):
    fixture, pilot, repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)
    _inject_app_checkpoint_interrupt(pilot)
    assert pilot.start(original).state is WorkerState.INCONCLUSIVE
    pilot.adapter.checkpoint_hook = None

    def fail(*_a, **_k):
        raise StoreError("synthetic", kind=kind)

    monkeypatch.setattr(fixture.store, "resume_epoch_idempotent", fail)
    second = _request(fixture, candidate_revision, attempt=2, epoch=original.epoch + 1)

    response = pilot.resume(_resume_for(original, second))

    assert response.state is state
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert response.error.message == f"resume fence: StoreError: kind={kind}{suffix}"
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch
    assert _commit_count(repository, candidate_revision) == 0


# ---- R3: probe verified on the applied-resume path -----------------------------

def _apply_resume_epoch_then_fail(fixture, pilot, candidate_revision):
    original = _request(fixture, candidate_revision)
    _inject_app_checkpoint_interrupt(pilot)
    assert pilot.start(original).state is WorkerState.INCONCLUSIVE
    pilot.adapter.checkpoint_hook = None
    second = _request(fixture, candidate_revision, attempt=2, epoch=original.epoch + 1)
    real_execute = pilot._execute_attempt

    def fail_after_epoch(*_a, **_k):
        raise RuntimeError("injected failure after the epoch advance")

    pilot._execute_attempt = fail_after_epoch
    with pytest.raises(RuntimeError, match="injected failure"):
        pilot.resume(_resume_for(original, second))
    pilot._execute_attempt = real_execute
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1
    return original, second


def test_r3_applied_resume_path_still_refuses_an_unsigned_probe(pilot_env):
    fixture, pilot, repository, candidate_revision = pilot_env
    original, second = _apply_resume_epoch_then_fail(fixture, pilot, candidate_revision)

    fixture.store.sandbox_mode = True
    try:
        response = pilot.resume(
            _resume_for(original, second), probe={"nonce": "forged-nonce", "inventory": {}},
        )
    finally:
        fixture.store.sandbox_mode = False

    assert response.state is WorkerState.BLOCKED
    assert response.error is not None and response.error.code is WorkerErrorCode.UNAVAILABLE
    assert "signature/attestation" in response.error.message
    assert _commit_count(repository, candidate_revision) == 0


def test_r3_valid_probe_with_consumed_nonce_is_accepted_only_on_the_applied_path(
    pilot_env, monkeypatch,
):
    """validate_fresh_probe is stubbed here: this isolates the seen-run/nonce rule."""
    import tools.vst.preflight as preflight

    _fixture, pilot, _repository, _candidate_revision = pilot_env
    monkeypatch.setattr(preflight, "validate_fresh_probe", lambda *a, **k: True)
    probe = {"nonce": "consumed-nonce"}
    pilot.supervisor._seen_probe_nonces.add("consumed-nonce")
    pilot.supervisor._seen_run_ids.add("consumed-run")

    assert pilot._valid_unconsumed_resume_probe(probe, "consumed-run") is False
    assert pilot._valid_unconsumed_resume_probe(probe, "consumed-run", check_unseen=False) is True
    assert pilot._valid_unconsumed_resume_probe(
        {"nonce": "  "}, "consumed-run", check_unseen=False) is False
    assert pilot._valid_unconsumed_resume_probe(None, "consumed-run", check_unseen=False) is False


# ---- R4: current_epoch StoreError never raises -----------------------------------

def _raise_store_error(kind):
    def fail(_story):
        raise StoreError("synthetic", kind=kind)
    return fail


@pytest.mark.parametrize("kind,state", [
    ("busy", WorkerState.INCONCLUSIVE), ("schema", WorkerState.BLOCKED),
])
def test_r4_start_returns_typed_response_when_current_epoch_fails(
    pilot_env, monkeypatch, kind, state,
):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    monkeypatch.setattr(fixture.store, "current_epoch", _raise_store_error(kind))

    response = pilot.start(request)

    assert response.state is state
    assert response.error is not None
    assert response.error.message.startswith("epoch lookup: StoreError: kind=" + kind)
    monkeypatch.undo()
    assert _commit_count(repository, candidate_revision) == 0
    assert _attempt_row(fixture, request) is None


@pytest.mark.parametrize("failing_call", [2, 3, 4, 5])
def test_r4_start_never_raises_when_current_epoch_fails_later_in_the_flow(
    pilot_env, monkeypatch, failing_call,
):
    fixture, pilot, _repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    real = fixture.store.current_epoch
    calls = {"count": 0}

    def flaky(story):
        calls["count"] += 1
        if calls["count"] == failing_call:
            raise StoreError("synthetic", kind="busy")
        return real(story)

    monkeypatch.setattr(fixture.store, "current_epoch", flaky)

    response = pilot.start(request)

    assert isinstance(response, pilot_module.WorkerResponse)
    assert calls["count"] >= failing_call  # the injected failure was actually reached
    assert response.state in {WorkerState.SUCCEEDED, WorkerState.INCONCLUSIVE, WorkerState.BLOCKED}


def test_r4_resume_returns_typed_response_when_current_epoch_fails(pilot_env, monkeypatch):
    fixture, pilot, repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)
    _inject_app_checkpoint_interrupt(pilot)
    assert pilot.start(original).state is WorkerState.INCONCLUSIVE
    pilot.adapter.checkpoint_hook = None
    second = _request(fixture, candidate_revision, attempt=2, epoch=original.epoch + 1)
    monkeypatch.setattr(fixture.store, "current_epoch", _raise_store_error("busy"))

    response = pilot.resume(_resume_for(original, second))

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error.message == "epoch lookup: StoreError: kind=busy"
    monkeypatch.undo()
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch
    assert _commit_count(repository, candidate_revision) == 0


# ---- R5: commit verification ------------------------------------------------------

def _fail_cat_file_probe(monkeypatch, *, times: int | None):
    real = pilot_module._run_git
    state = {"failed": 0}

    def run(repository, args, timeout):
        if args[:2] == ["cat-file", "-e"] and (times is None or state["failed"] < times):
            state["failed"] += 1
            raise subprocess.TimeoutExpired(["git"], timeout)
        return real(repository, args, timeout)

    monkeypatch.setattr(pilot_module, "_run_git", run)
    return state


def test_r5_transient_git_failure_is_inconclusive_once_and_retry_reverifies_to_success(
    pilot_env, monkeypatch,
):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    state = _fail_cat_file_probe(monkeypatch, times=1)

    first = pilot.start(request)

    assert state["failed"] == 1
    assert first.state is WorkerState.INCONCLUSIVE
    assert first.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert "candidate commit verification failed: TimeoutExpired" in first.error.message
    assert first.progress.startswith("observed candidate_head=")
    assert _commit_count(repository, candidate_revision) == 1

    second = pilot.start(request)

    assert second.state is WorkerState.SUCCEEDED
    assert second.candidate_head == _git(repository, "rev-parse", "--verify", "HEAD")
    assert _commit_count(repository, candidate_revision) == 1
    assert pilot.status(request).state is WorkerState.SUCCEEDED


def test_r5_replayed_succeeded_start_reverifies_every_call(pilot_env, monkeypatch):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    first = pilot.start(request)
    assert first.state is WorkerState.SUCCEEDED
    _fail_cat_file_probe(monkeypatch, times=None)

    replay = pilot.start(request)

    assert replay.state is WorkerState.INCONCLUSIVE
    assert replay.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    monkeypatch.undo()
    assert pilot.start(request) == first
    assert _commit_count(repository, candidate_revision) == 1


def _lying_start(pilot, head):
    def lying(req):
        return _pilot_response(
            req, WorkerState.SUCCEEDED, candidate_head=head,
            changed_paths=(req.change_path,), progress="forged success",
        )
    pilot.adapter.start = lying


def test_r5_committed_blob_differing_from_change_content_is_inconclusive(pilot_env):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    wrong = _make_side_commit(repository, candidate_revision, "src/synthetic.py", "value = 'other'\n")
    _lying_start(pilot, wrong)

    response = pilot.start(request)

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert "differs from the requested change_content" in response.error.message
    assert fixture.store.receipts_for_task(fixture.task_id) == []


def test_r5_empty_diff_is_reconciliation_required_not_scope_denied(pilot_env):
    fixture, pilot, _repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    _lying_start(pilot, candidate_revision)

    response = pilot.start(request)

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert "no change relative to the trusted revision" in response.error.message


# ---- R6: commit_verifier for non-HandWritten adapters -------------------------------

def _wrap_as_foreign_adapter(pilot):
    """A non-HandWritten adapter that delegates to the real one (real commit, SUCCEEDED)."""
    real = pilot.adapter

    class Foreign:
        def __getattr__(self, name):
            return getattr(real, name)

        def start(self, request):
            return real.start(request)

        def resume(self, request):
            return real.resume(request)

    pilot.adapter = Foreign()
    assert not isinstance(pilot.adapter, HandWrittenWorkerAdapter)


def test_r6_constructor_rejects_a_non_callable_verifier(pilot_env):
    fixture, pilot, _repository, _candidate_revision = pilot_env
    with pytest.raises(TypeError):
        SyntheticStoryPilot(fixture, pilot.supervisor, pilot.adapter, commit_verifier="nope")


def test_r6_foreign_adapter_success_without_verifier_is_inconclusive_then_promoted_on_retry(
    pilot_env,
):
    fixture, pilot, repository, candidate_revision = pilot_env
    assert pilot.commit_verifier is None
    _wrap_as_foreign_adapter(pilot)
    request = _request(fixture, candidate_revision)

    refused = pilot.start(request)

    assert refused.state is WorkerState.INCONCLUSIVE
    assert refused.error.code is WorkerErrorCode.UNSUPPORTED_STATE
    assert "no commit verifier" in refused.error.message
    assert refused.progress.startswith("observed candidate_head=")
    assert fixture.store.receipts_for_task(fixture.task_id) == []

    seen = []
    pilot.commit_verifier = lambda req, resp: seen.append((req, resp)) or None
    promoted = pilot.start(request)

    assert promoted.state is WorkerState.SUCCEEDED
    assert len(seen) >= 1 and seen[-1][0] == request
    assert seen[-1][1].state is WorkerState.SUCCEEDED
    assert _commit_count(repository, candidate_revision) == 1


def test_r6_raising_verifier_is_inconclusive_and_hides_exception_text(pilot_env):
    fixture, pilot, _repository, candidate_revision = pilot_env
    _wrap_as_foreign_adapter(pilot)

    def boom(_request, _response):
        raise RuntimeError("PRIVATE_VERIFIER_DETAIL")

    pilot.commit_verifier = boom
    response = pilot.start(_request(fixture, candidate_revision))

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert response.error.message == "commit verifier failed: RuntimeError"


@pytest.mark.parametrize("verdict", ["ok", True, {"state": "SUCCEEDED"}])
def test_r6_untyped_verifier_verdict_is_inconclusive(pilot_env, verdict):
    fixture, pilot, _repository, candidate_revision = pilot_env
    _wrap_as_foreign_adapter(pilot)
    pilot.commit_verifier = lambda _req, _resp: verdict

    response = pilot.start(_request(fixture, candidate_revision))

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error.code is WorkerErrorCode.UNSUPPORTED_STATE
    assert "untyped verdict" in response.error.message


@pytest.mark.parametrize("downgrade", [WorkerState.INCONCLUSIVE, WorkerState.BLOCKED])
def test_r6_downgrading_verifier_refuses_the_success_claim(pilot_env, downgrade):
    fixture, pilot, _repository, candidate_revision = pilot_env
    _wrap_as_foreign_adapter(pilot)
    pilot.commit_verifier = lambda req, _resp: _pilot_response(
        req, downgrade, error=WorkerError(WorkerErrorCode.SCOPE_DENIED, "verifier says no"))

    response = pilot.start(_request(fixture, candidate_revision))

    assert response.state is downgrade
    assert response.error.message == "verifier says no"
    assert fixture.store.receipts_for_task(fixture.task_id) == []


def test_r6_handwritten_adapter_ignores_the_verifier_and_uses_its_repository(pilot_env):
    fixture, pilot, repository, candidate_revision = pilot_env
    pilot.commit_verifier = lambda *_a: pytest.fail("verifier must not run for HandWritten")
    assert pilot.start(_request(fixture, candidate_revision)).state is WorkerState.SUCCEEDED
    assert _commit_count(repository, candidate_revision) == 1


# ---- R8: STOP message from adapter state ---------------------------------------------

@pytest.mark.parametrize("state,code", [
    (WorkerState.FAILED, WorkerErrorCode.EXECUTION_FAILED),
    (WorkerState.BLOCKED, WorkerErrorCode.INVALID_REQUEST),
])
def test_r8_stop_message_reports_failed_or_blocked_adapter_stop(
    pilot_env, monkeypatch, state, code,
):
    fixture, pilot, _repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)
    _inject_app_checkpoint_interrupt(pilot)
    assert pilot.start(original).state is WorkerState.INCONCLUSIVE
    monkeypatch.setattr(
        pilot.adapter, "stop",
        lambda _req: _pilot_response(original, state, error=WorkerError(code, "synthetic")),
    )

    response = pilot.stop(_stop_request(original))

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error.code is WorkerErrorCode.INTERRUPTED
    assert response.error.message == (
        f"epoch fenced; adapter.stop reported {state.value}; "
        "worker process cleanup is NOT_VERIFIED"
    )
    assert f"adapter_stop={state.value}:{code.value}" in response.progress
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch + 1


def test_r8_stop_message_for_untyped_adapter_result(pilot_env, monkeypatch):
    fixture, pilot, _repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)
    _inject_app_checkpoint_interrupt(pilot)
    assert pilot.start(original).state is WorkerState.INCONCLUSIVE
    monkeypatch.setattr(pilot.adapter, "stop", lambda _req: None)

    response = pilot.stop(_stop_request(original))

    assert response.error.message == (
        "epoch fenced; adapter.stop returned an untyped result; "
        "worker process cleanup is NOT_VERIFIED"
    )
    assert "adapter_stop=UNTYPED" in response.progress


# ---------------------------------------------------------------------------
# S3-C scenario-denominator gap tests (groups 2, 3, 4, 5, 6, 9, 10)
# ---------------------------------------------------------------------------

import hashlib  # noqa: E402
import os  # noqa: E402

from tools.vst.contracts import receipt_sha256  # noqa: E402
from tools.vst.diffgate import check_diff  # noqa: E402
from tools.vst.slice import AUTHOR, EXPECTED_TEST_IDS, REVIEWER, WRONG_KEY  # noqa: E402


def _plumbing_commit(repository, parent: str, *, put=None, remove=()) -> str:
    """Commit built with a private index: HEAD, branches and the work tree are untouched."""
    index = os.path.join(str(repository), ".git", "vst-s3c-index")
    env = dict(os.environ, GIT_INDEX_FILE=index)

    def run(*args: str, data: bytes | None = None) -> str:
        done = subprocess.run(
            ["git", "-C", str(repository), *args], check=True, env=env, input=data,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return done.stdout.decode("utf-8").strip()

    try:
        run("read-tree", parent)
        for path in remove:
            run("update-index", "--force-remove", path)
        for path, (mode, content) in (put or {}).items():
            blob = run("hash-object", "-w", "--stdin", data=content)
            run("update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}")
        tree = run("write-tree")
        return run("commit-tree", tree, "-p", parent, "-m", "plumbing candidate")
    finally:
        if os.path.exists(index):
            os.remove(index)


def _git_diff_evidence(fixture, repository, base: str, head: str) -> dict:
    """Feed the S2 diff gate from real git output (raw modes, rename detection)."""
    raw = subprocess.run(
        ["git", "-C", str(repository), "diff", "--raw", "-M", "--no-abbrev", base, head],
        check=True, stdout=subprocess.PIPE, text=True,
    ).stdout
    diff_bytes = subprocess.run(
        ["git", "-C", str(repository), "diff", "-M", base, head],
        check=True, stdout=subprocess.PIPE,
    ).stdout
    changed, symlinks, renames = [], [], []
    for line in raw.splitlines():
        meta, *paths = line.split("\t")
        old_mode, new_mode, _o, _n, status = meta.lstrip(":").split()
        changed.extend(paths)
        if "120000" in (old_mode, new_mode):
            symlinks.extend(paths)
        if status.startswith("R"):
            renames.append((paths[0], paths[1]))
    return check_diff(
        manifest_sha256=fixture.manifest_hash, base_head=base, candidate_head=head,
        changed_paths=changed, allowed_paths=fixture.manifest["scope"],
        diff_bytes=diff_bytes, symlink_paths=symlinks, rename_pairs=renames,
    )


_BASE_BLOB = b"value = 'base'\n"
_CANDIDATE_BLOB = b"value = 'candidate'\n"
# case id -> (plumbing arguments, diff-gate reason, pilot error code for the forged claim)
_G6_CASES = {
    "outside_scope": (
        {"put": {"docs/outside.txt": ("100644", b"x\n")}},
        "OUT_OF_SCOPE_PATH", WorkerErrorCode.SCOPE_DENIED),
    "protected_hook": (
        {"put": {"hooks/pre-commit": ("100755", b"#!/bin/sh\n")}},
        "BLOCKED_PATH_CLASS", WorkerErrorCode.SCOPE_DENIED),
    "protected_ci_config": (
        {"put": {".github/workflows/ci.yml": ("100644", b"on: push\n")}},
        "BLOCKED_PATH_CLASS", WorkerErrorCode.SCOPE_DENIED),
    "protected_install_script": (
        {"put": {"install.sh": ("100755", b"#!/bin/sh\n")}},
        "BLOCKED_PATH_CLASS", WorkerErrorCode.SCOPE_DENIED),
    "protected_build_config": (
        {"put": {"pyproject.toml": ("100644", b"[project]\n")}},
        "BLOCKED_PATH_CLASS", WorkerErrorCode.SCOPE_DENIED),
    "manifest_file": (
        {"put": {"docs/sdlc/task-manifest.json": ("100644", b"{}\n")}},
        "OUT_OF_SCOPE_PATH", WorkerErrorCode.SCOPE_DENIED),
    "rename_into_blocked_path": (
        {"put": {"hooks/pre-commit": ("100644", _BASE_BLOB)}, "remove": ("src/synthetic.py",)},
        "RENAME_INTO_BLOCKED_PATH", WorkerErrorCode.SCOPE_DENIED),
}


def test_g6_diff_gate_passes_the_real_pilot_commit(pilot_env):
    """Group 6 allowed worktree edit: the S2 diff gate accepts exactly the pilot's commit."""
    fixture, pilot, repository, candidate_revision = pilot_env
    response = pilot.start(_request(fixture, candidate_revision))
    assert response.state is WorkerState.SUCCEEDED

    evidence = _git_diff_evidence(fixture, repository, candidate_revision, response.candidate_head)

    assert evidence["verdict"] == "PASS" and evidence["reason"] == "PASS"
    assert evidence["changed_paths"] == ["src/synthetic.py"]
    assert evidence["candidate_head"] == response.candidate_head


@pytest.mark.parametrize("case", sorted(_G6_CASES))
def test_g6_diff_gate_fails_real_git_diffs_outside_scope_or_into_protected_paths(
    pilot_env, case,
):
    fixture, _pilot, repository, candidate_revision = pilot_env
    arguments, reason, _code = _G6_CASES[case]
    head = _plumbing_commit(repository, candidate_revision, **arguments)

    evidence = _git_diff_evidence(fixture, repository, candidate_revision, head)

    assert evidence["verdict"] == "FAIL"
    assert evidence["reason"] == reason


def test_g6_diff_gate_fails_a_real_symlink_change_even_on_an_allowed_path(pilot_env):
    fixture, _pilot, repository, candidate_revision = pilot_env
    head = _plumbing_commit(
        repository, candidate_revision, put={"src/synthetic.py": ("120000", _CANDIDATE_BLOB)})

    evidence = _git_diff_evidence(fixture, repository, candidate_revision, head)

    assert evidence["verdict"] == "FAIL" and evidence["reason"] == "SYMLINK_CHANGE"
    assert evidence["changed_paths"] == ["src/synthetic.py"]


@pytest.mark.parametrize("case", sorted(_G6_CASES))
def test_g6_pilot_refuses_a_forged_success_for_out_of_scope_or_protected_commits(
    pilot_env, case,
):
    """AC-14: the pilot never promotes such a commit and no gate APPROVE is reachable."""
    fixture, pilot, repository, candidate_revision = pilot_env
    arguments, _reason, code = _G6_CASES[case]
    request = _request(fixture, candidate_revision)
    _lying_start(pilot, _plumbing_commit(repository, candidate_revision, **arguments))

    response = pilot.start(request)

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error is not None and response.error.code is code
    assert fixture.store.receipts_for_task(fixture.task_id) == []
    assert _decide(pilot, fixture, request, fixture.current_head)["verdict"] != "APPROVE"


def test_g6_pilot_refuses_a_forged_success_that_replaced_the_file_by_a_symlink(pilot_env):
    """A symlink whose target text equals change_content must not pass the blob comparison."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    _lying_start(pilot, _plumbing_commit(
        repository, candidate_revision,
        put={"src/synthetic.py": ("120000", request.change_content.encode("utf-8"))}))

    response = pilot.start(request)

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error is not None
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert "non-regular entry" in response.error.message and "symlink" in response.error.message
    assert fixture.store.receipts_for_task(fixture.task_id) == []


def test_g6_symlink_committed_earlier_with_an_empty_new_diff_is_refused(pilot_env):
    """The trusted revision already has a symlink at change_path; the head adds no change."""
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    symlink_base = _plumbing_commit(
        repository, candidate_revision,
        put={"src/synthetic.py": ("120000", request.change_content.encode("utf-8"))})
    assert _git(repository, "ls-tree", symlink_base, "--", "src/synthetic.py").startswith("120000 blob")
    # Re-anchor the trusted revision on the symlink commit, then claim a no-op head.
    pilot.adapter.candidate_revision = symlink_base
    anchored = replace(request, candidate_revision=symlink_base, effect_key=effect_key_for(
        request.run_id, request.candidate_id, symlink_base, request.manifest_sha256,
        request.task_id, request.story_id, request.base_head, request.allowed_paths,
        request.change_path, request.change_content))
    tree = _git(repository, "rev-parse", f"{symlink_base}^{{tree}}")
    noop_head = _git(repository, "commit-tree", tree, "-p", symlink_base, "-m", "no-op")
    _lying_start(pilot, noop_head)

    response = pilot.start(anchored)

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error is not None
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert "no change relative to the trusted revision" in response.error.message
    assert fixture.store.receipts_for_task(fixture.task_id) == []


def test_g6_deleting_the_file_leaves_no_regular_entry_and_is_refused(pilot_env):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    _lying_start(pilot, _plumbing_commit(
        repository, candidate_revision, remove=("src/synthetic.py",)))

    response = pilot.start(request)

    assert response.state is WorkerState.INCONCLUSIVE
    assert response.error is not None
    assert response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert "not a regular file entry" in response.error.message
    assert fixture.store.receipts_for_task(fixture.task_id) == []


@pytest.mark.parametrize("path", [
    ".github/workflows/ci.yml", "hooks/pre-commit", "install.sh", "pyproject.toml",
    "docs/sdlc/task-manifest.json",
])
def test_g6_pilot_start_for_a_protected_or_manifest_path_never_invokes_the_worker(
    pilot_env, path,
):
    fixture, pilot, repository, candidate_revision = pilot_env
    calls = []
    real_start = pilot.adapter.start
    pilot.adapter.start = lambda req: calls.append(req) or real_start(req)

    response = pilot.start(_request(fixture, candidate_revision, path=path))

    assert response.state is WorkerState.BLOCKED
    assert response.error is not None and response.error.code is WorkerErrorCode.SCOPE_DENIED
    assert calls == []
    assert _commit_count(repository, candidate_revision) == 0
    assert fixture.store.receipts_for_task(fixture.task_id) == []


# ---- group 9: exact candidate revision mismatch -----------------------------------

def test_g9_candidate_revision_mismatch_is_blocked_without_a_write(pilot_env):
    fixture, pilot, repository, candidate_revision = pilot_env
    request = _request(fixture, candidate_revision)
    other = "e" * 40
    forged = replace(request, candidate_revision=other, effect_key=effect_key_for(
        request.run_id, request.candidate_id, other, request.manifest_sha256,
        request.task_id, request.story_id, request.base_head, request.allowed_paths,
        request.change_path, request.change_content))

    response = pilot.start(forged)

    assert response.state is WorkerState.BLOCKED
    assert response.error is not None and response.error.code is WorkerErrorCode.INVALID_REQUEST
    assert "candidate identity/revision" in response.error.message
    assert _commit_count(repository, candidate_revision) == 0
    assert _attempt_row(fixture, forged) is None


# ---- group 5: budget boundaries beyond the existing zero-remaining / exact-cap tests ----

def test_g5_one_unit_over_remaining_budget_is_blocked_and_never_overspends(pilot_env):
    fixture, pilot, repository, candidate_revision = pilot_env
    cap = fixture.manifest["cost_cap"]
    _prespend(fixture, cap - 1)
    calls = []
    real_start = pilot.adapter.start
    pilot.adapter.start = lambda req: calls.append(req) or real_start(req)
    over = replace(_request(fixture, candidate_revision), budget_spent=cap - 1, budget_units=2)

    blocked = pilot.start(over)

    assert blocked.state is WorkerState.BLOCKED
    assert blocked.error is not None and blocked.error.code is WorkerErrorCode.BUDGET_EXHAUSTED
    assert calls == []
    assert _commit_count(repository, candidate_revision) == 0
    assert _lease_statuses(fixture, over) == ["RELEASED"]
    # No excess spend: exactly one unit (the cap) is still available on the Store ledger.
    assert fixture.store.charge_idempotent(
        "s3c-last-unit", fixture.task_id, 1, supervisor_key=fixture.supervisor_key,
        expected_cap=cap, expected_spent=cap - 1) == 0
    assert blocked == pilot.start(over)  # persisted refusal replays identically


def test_g5_request_budget_cap_above_the_manifest_cap_starts_nothing(pilot_env):
    fixture, pilot, repository, candidate_revision = pilot_env
    cap = fixture.manifest["cost_cap"]
    request = replace(_request(fixture, candidate_revision), budget_cap=cap + 1)

    blocked = pilot.start(request)

    assert blocked.state is WorkerState.BLOCKED
    assert blocked.error is not None and blocked.error.code is WorkerErrorCode.BUDGET_EXHAUSTED
    assert "exceeds the manifest cap" in blocked.error.message
    assert _commit_count(repository, candidate_revision) == 0
    assert _attempt_row(fixture, request) is None
    assert _lease_statuses(fixture, request) == []


# ---- group 4: retry-cap boundary at other cap values ------------------------------------

@pytest.mark.parametrize("retry_cap", [0, 2])
def test_g4_retry_cap_boundary_allows_exactly_cap_plus_one_failed_attempts(tmp_path, retry_cap):
    fixture, pilot, repository, candidate_revision = _build_env(tmp_path, retry_cap=retry_cap)
    try:
        assert fixture.manifest["retry_cap"] == retry_cap
        _real, failing = _install_failing_adapter(pilot)
        previous = _request(fixture, candidate_revision)
        assert pilot.start(previous).state is WorkerState.FAILED
        for attempt in range(2, retry_cap + 2):
            nxt = _request(fixture, candidate_revision, attempt=attempt, epoch=previous.epoch + 1)
            assert pilot.resume(_resume_for(previous, nxt)).state is WorkerState.FAILED
            previous = nxt
        assert failing.calls == retry_cap + 1
        epoch_before = fixture.store.current_epoch(fixture.story_id)

        beyond = _request(
            fixture, candidate_revision, attempt=retry_cap + 2, epoch=previous.epoch + 1)
        refused = pilot.resume(_resume_for(previous, beyond))

        assert refused.state is WorkerState.BLOCKED
        assert refused.error is not None and refused.error.code is WorkerErrorCode.RETRY_EXHAUSTED
        assert failing.calls == retry_cap + 1
        assert fixture.store.current_epoch(fixture.story_id) == epoch_before
        assert _commit_count(repository, candidate_revision) == 0
    finally:
        fixture.close()


# ---- group 3: STOP sub-cases not asserted elsewhere ---------------------------------------

def test_g3_stop_before_any_start_is_refused_and_creates_no_fence(pilot_env):
    """Current contract: STOP needs a durable prior attempt binding; nothing is fenced."""
    fixture, pilot, repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)

    response = pilot.stop(_stop_request(original))

    assert response.state is WorkerState.BLOCKED
    assert response.error is not None and response.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert "durable matching prior attempt" in response.error.message
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch
    assert _commit_count(repository, candidate_revision) == 0
    assert fixture.store.lookup_idempotent_operation(
        _stop_request(original).operation_key, operation="stop_attempt_fenced") is None


def test_g3_late_receipt_from_the_stopped_epoch_is_rejected_by_the_store(pilot_env):
    """Group 3 late receipt: after STOP advances the epoch, the old attempt cannot append."""
    fixture, pilot, _repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)
    _inject_app_checkpoint_interrupt(pilot)
    assert pilot.start(original).state is WorkerState.INCONCLUSIVE
    assert pilot.stop(_stop_request(original)).state is WorkerState.INCONCLUSIVE
    new_epoch = fixture.store.current_epoch(fixture.story_id)
    assert new_epoch == original.epoch + 1
    fixture.store.acquire_lease(
        fixture.task_id, fixture.story_id, fixture.runner_id, new_epoch, 2, 600,
        supervisor_key=fixture.supervisor_key)
    late = fixture.make_test_receipt(1, EXPECTED_TEST_IDS, epoch=original.epoch)

    with pytest.raises(StoreError) as refused:
        fixture.append(late)

    assert refused.value.kind == "epoch"
    assert fixture.store.receipts_for_task(fixture.task_id) == []


# ---- group 2: a crash at a checkpoint without an automatic resume rule ---------------------

def test_g2_crash_at_before_edit_checkpoint_is_inconclusive_and_has_no_automatic_resume(pilot_env):
    fixture, pilot, repository, candidate_revision = pilot_env
    original = _request(fixture, candidate_revision)

    def crash(checkpoint):
        if checkpoint is Checkpoint.BEFORE_EDIT:
            raise RuntimeError("deterministic crash before the edit")

    pilot.adapter.checkpoint_hook = crash
    crashed = pilot.start(original)

    assert crashed.state is WorkerState.INCONCLUSIVE
    assert crashed.error is not None and crashed.error.code is WorkerErrorCode.RECONCILIATION_REQUIRED
    assert crashed.checkpoint is None
    assert _commit_count(repository, candidate_revision) == 0
    assert _lease_statuses(fixture, original) == ["LIVE"]  # uncertain result keeps the lease
    pilot.adapter.checkpoint_hook = None

    second = _request(fixture, candidate_revision, attempt=2, epoch=original.epoch + 1)
    refused = pilot.resume(_resume_for(original, second))

    assert refused.state is WorkerState.BLOCKED
    assert refused.error is not None and refused.error.code is WorkerErrorCode.UNSUPPORTED_STATE
    assert fixture.store.current_epoch(fixture.story_id) == original.epoch
    assert _commit_count(repository, candidate_revision) == 0


# ---- group 10: evidence chain through the real Store gate ---------------------------------

def _decide(pilot, fixture, request, head: str, **options) -> dict:
    """The S2 Store/Supervisor gate decision with the fixture's signing keys."""
    return pilot.supervisor.evaluate_gate(
        request.task_id, head, fixture.store.current_epoch(request.story_id), fixture.key,
        supervisor_key=fixture.supervisor_key, operator_key=fixture.operator_key, **options)


def _lease_for_receipts(fixture, attempt: int, epoch: int | None = None) -> None:
    fixture.store.acquire_lease(
        fixture.task_id, fixture.story_id, fixture.runner_id,
        fixture.store.current_epoch(fixture.story_id) if epoch is None else epoch,
        attempt, 600, supervisor_key=fixture.supervisor_key)


def _good_receipts(fixture, head: str, *, tests=None) -> list[dict]:
    return [
        tests if tests is not None else fixture.make_test_receipt(1, EXPECTED_TEST_IDS, head=head),
        fixture.make_static_receipt(head=head),
        fixture.make_review_receipt(REVIEWER, AUTHOR, head=head),
    ]


def _succeeded(pilot, fixture, candidate_revision):
    request = _request(fixture, candidate_revision)
    response = pilot.start(request)
    assert response.state is WorkerState.SUCCEEDED
    return request, response


def test_g10_complete_signed_receipt_set_at_the_candidate_head_is_approved(pilot_env):
    """Group 1 signed gate outcome / positive control for group 10."""
    fixture, pilot, _repository, candidate_revision = pilot_env
    request, response = _succeeded(pilot, fixture, candidate_revision)
    # S3 itself never approves: with no receipts the gate is not APPROVE.
    assert _decide(pilot, fixture, request, response.candidate_head)["verdict"] != "APPROVE"
    _lease_for_receipts(fixture, 2)
    for receipt in _good_receipts(fixture, response.candidate_head):
        fixture.append(receipt)

    decision = _decide(pilot, fixture, request, response.candidate_head)

    assert decision["verdict"] == "APPROVE"
    assert decision["unresolved_findings"] == []


def test_g10_missing_required_receipt_is_not_approval(pilot_env):
    fixture, pilot, _repository, candidate_revision = pilot_env
    request, response = _succeeded(pilot, fixture, candidate_revision)
    _lease_for_receipts(fixture, 2)
    tests, static, _review = _good_receipts(fixture, response.candidate_head)
    fixture.append(tests)
    fixture.append(static)

    decision = _decide(pilot, fixture, request, response.candidate_head)

    assert decision["verdict"] == "MODIFY"
    assert "review" in " ".join(decision["reasons"])


def test_g10_receipt_signed_with_the_wrong_key_is_rejected_by_the_store(pilot_env):
    fixture, pilot, _repository, candidate_revision = pilot_env
    request, response = _succeeded(pilot, fixture, candidate_revision)
    _lease_for_receipts(fixture, 2)
    forged = fixture.make_test_receipt(
        1, EXPECTED_TEST_IDS, head=response.candidate_head, key=WRONG_KEY)

    with pytest.raises(StoreError) as refused:
        fixture.append(forged)

    assert refused.value.kind == "signature"
    assert fixture.store.receipts_for_task(fixture.task_id) == []
    assert _decide(pilot, fixture, request, response.candidate_head)["verdict"] != "APPROVE"


def _test_receipt_with_artifact(fixture, head: str, digests: dict) -> dict:
    return fixture._build(
        "TestRun", "tests", 1, head, None, None, None, None,
        {
            "expected_test_ids": list(EXPECTED_TEST_IDS),
            "executed_test_ids": list(EXPECTED_TEST_IDS),
            "skipped_test_ids": [],
            "xfail_test_ids": [],
            "commands": [{"argv": ["synthetic-test-run"], "exit_code": 0}],
            "covered_acceptance": ["AC-1"],
            "artifact_digests": digests,
        })


def test_g10_artifact_modified_after_hashing_is_not_approval(pilot_env):
    fixture, pilot, repository, candidate_revision = pilot_env
    request, response = _succeeded(pilot, fixture, candidate_revision)
    artifact = repository / "src" / "synthetic.py"
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    _lease_for_receipts(fixture, 2)
    tests = _test_receipt_with_artifact(
        fixture, response.candidate_head, {"src/synthetic.py": digest})
    for receipt in _good_receipts(fixture, response.candidate_head, tests=tests):
        fixture.append(receipt)

    def resolver(path):
        target = repository / path
        return hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None

    def decide():
        return _decide(
            pilot, fixture, request, response.candidate_head, artifact_resolver=resolver)

    assert decide()["verdict"] == "APPROVE"
    artifact.write_text("value = 'tampered after hashing'\n", encoding="utf-8")
    tampered = decide()
    assert tampered["verdict"] == "MODIFY"
    assert any("digest mismatch" in reason for reason in tampered["reasons"])
    artifact.unlink()
    assert decide()["verdict"] == "MODIFY"


def test_g10_pilot_evaluate_returns_the_store_gate_decision(pilot_env):
    fixture, pilot, _repository, candidate_revision = pilot_env
    request, response = _succeeded(pilot, fixture, candidate_revision)

    without_receipts = pilot.evaluate(request)

    assert without_receipts == _decide(pilot, fixture, request, response.candidate_head)
    assert without_receipts["verdict"] != "APPROVE"
    _lease_for_receipts(fixture, 2)
    for receipt in _good_receipts(fixture, response.candidate_head):
        fixture.append(receipt)
    approved = pilot.evaluate(request)
    assert approved == _decide(pilot, fixture, request, response.candidate_head)
    assert approved["verdict"] == "APPROVE"


def test_g10_failed_attempt_stays_visible_after_a_later_pass(pilot_env):
    """Real pilot flow: attempt 1 FAILED (no receipt filed), attempt 2 passes and is approved."""
    fixture, pilot, repository, candidate_revision = pilot_env
    real = pilot.adapter
    first = _request(fixture, candidate_revision)
    second = _request(fixture, candidate_revision, attempt=2, epoch=first.epoch + 1)

    class Receipting:
        def __getattr__(self, name):
            return getattr(real, name)

        def start(self, request):
            return _pilot_response(request, WorkerState.FAILED, error=WorkerError(
                WorkerErrorCode.EXECUTION_FAILED, "synthetic worker failure"))

        def resume(self, resume_request):
            response = real.resume(resume_request)
            assert response.state is WorkerState.SUCCEEDED
            head, epoch = response.candidate_head, resume_request.request.epoch
            fixture.append(fixture.make_test_receipt(1, EXPECTED_TEST_IDS, head=head, epoch=epoch))
            fixture.append(fixture.make_static_receipt(head=head, epoch=epoch))
            fixture.append(fixture.make_review_receipt(REVIEWER, AUTHOR, head=head, epoch=epoch))
            return response

    pilot.adapter = Receipting()  # non-HandWritten wrapper: SUCCEEDED needs a commit verifier
    pilot.commit_verifier = lambda req, resp: None if (
        resp.candidate_head == _git(repository, "rev-parse", "--verify", "HEAD")
        and _git(repository, "show", f"{resp.candidate_head}:{req.change_path}")
        == req.change_content.strip()
    ) else _pilot_response(req, WorkerState.INCONCLUSIVE, error=WorkerError(
        WorkerErrorCode.RECONCILIATION_REQUIRED, "verifier: head/blob mismatch"))
    assert pilot.start(first).state is WorkerState.FAILED
    passed = pilot.resume(_resume_for(first, second))
    assert passed.state is WorkerState.SUCCEEDED

    assert _decide(pilot, fixture, second, passed.candidate_head)["verdict"] == "APPROVE"
    # The failed attempt is not rewritten by the later pass.
    assert pilot.status(first).state is WorkerState.FAILED
    assert pilot.status(first).error.code is WorkerErrorCode.EXECUTION_FAILED
    outcome = fixture.store.lookup_idempotent_operation(
        pilot_module._derived_key("outcome", first.operation_key), operation="s3_attempt_outcome")
    assert outcome["state"] == "COMPLETED"
    assert outcome["result"]["state"] == "FAILED"
    assert outcome["result"]["error_code"] == "EXECUTION_FAILED"
    assert pilot.status(second).state is WorkerState.SUCCEEDED


def test_g10_failed_attempt_that_filed_a_receipt_cannot_be_resumed_fail_closed(pilot_env):
    """Current contract: Store resume needs lease.wrote == 0, so a FAIL receipt blocks the resume."""
    fixture, pilot, repository, candidate_revision = pilot_env
    real = pilot.adapter
    first = _request(fixture, candidate_revision)

    class Receipting:
        def __getattr__(self, name):
            return getattr(real, name)

        def start(self, request):
            fixture.append(fixture.make_test_receipt(
                1, EXPECTED_TEST_IDS, exit_code=1, head=request.base_head))
            return _pilot_response(request, WorkerState.FAILED, error=WorkerError(
                WorkerErrorCode.EXECUTION_FAILED, "synthetic worker failure"))

    pilot.adapter = Receipting()
    assert pilot.start(first).state is WorkerState.FAILED
    second = _request(fixture, candidate_revision, attempt=2, epoch=first.epoch + 1)

    refused = pilot.resume(_resume_for(first, second))

    assert refused.state is WorkerState.BLOCKED
    assert refused.error.message == "resume fence: StoreError: kind=lifecycle (not retryable)"
    assert fixture.store.current_epoch(fixture.story_id) == first.epoch
    assert _commit_count(repository, candidate_revision) == 0
    assert [r["result"] for r in fixture.store.receipts_for_task(fixture.task_id)] == ["FAIL"]


# AC-5 (fresh signed probe), AC-6 (actual WSL boundary), and runtime behavior
# across WSL are intentionally NOT_RUN: this file has no trusted probe issuer,
# and a synthetic signed fixture cannot establish the host boundary.
