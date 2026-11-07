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
    WorkerRequest, WorkerResponse, WorkerState, effect_key_for, is_canonical_repo_path, operation_key_for,
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


def _repo(tmp_path):
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
    return repository, _git(repository, "rev-parse", "--verify", "HEAD")


def _adapter(repository, base_head):
    adapter = HandWrittenWorkerAdapter(
        HandWrittenWorker(str(repository)), candidate_id="handwritten-v1",
        candidate_revision=base_head,
    )
    adapter.fence_check = lambda _request: True
    return adapter


def test_adapter_start_replay_is_idempotent_one_commit_same_head(tmp_path):
    repository, base = _repo(tmp_path)
    adapter = _adapter(repository, base)
    req = request(candidate_revision=base, base_head=base)
    first = adapter.start(req)
    second = adapter.start(req)
    assert first.state is second.state is WorkerState.SUCCEEDED
    assert first.candidate_head == second.candidate_head != base
    assert _git(repository, "rev-list", "--count", f"{base}..HEAD") == "1"


def test_adapter_stale_fence_rejected_before_any_mutation(tmp_path):
    from tools.vst.pilot import WorkerFenceRejected
    repository, base = _repo(tmp_path)
    adapter = _adapter(repository, base)
    adapter.fence_check = lambda _request: False
    req = request(candidate_revision=base, base_head=base)
    with pytest.raises(WorkerFenceRejected):
        adapter.start(req)
    assert _git(repository, "rev-parse", "--verify", "HEAD") == base
    assert (repository / "src" / "synthetic.py").read_text(encoding="utf-8") == "value = 'base'\n"


def test_adapter_fence_lost_after_edit_leaves_no_commit(tmp_path):
    from tools.vst.pilot import WorkerFenceRejected
    repository, base = _repo(tmp_path)
    adapter = _adapter(repository, base)
    calls = []
    adapter.fence_check = lambda _request: calls.append(1) or len(calls) < 3
    with pytest.raises(WorkerFenceRejected):
        adapter.start(request(candidate_revision=base, base_head=base))
    assert _git(repository, "rev-parse", "--verify", "HEAD") == base


def test_adapter_blocks_untrusted_candidate_and_scope_without_mutation(tmp_path):
    repository, base = _repo(tmp_path)
    adapter = _adapter(repository, base)
    other = request(candidate_id="other-v1", candidate_revision=base, base_head=base)
    blocked = adapter.start(other)
    assert blocked.state is WorkerState.BLOCKED
    assert blocked.error.code is WorkerErrorCode.INVALID_REQUEST
    wrong_rev = adapter.start(request(candidate_revision="d" * 40, base_head=base))
    assert wrong_rev.state is WorkerState.BLOCKED
    scoped = HandWrittenWorkerAdapter(
        HandWrittenWorker(str(repository), ("src/other.py",)),
        candidate_id="handwritten-v1", candidate_revision=base)
    denied = scoped.start(request(candidate_revision=base, base_head=base))
    assert denied.state is WorkerState.BLOCKED
    assert denied.error.code is WorkerErrorCode.SCOPE_DENIED
    assert _git(repository, "rev-parse", "--verify", "HEAD") == base


def test_adapter_status_never_claims_success_and_stop_reports_uncertain_cleanup(tmp_path):
    repository, base = _repo(tmp_path)
    adapter = _adapter(repository, base)
    req = request(candidate_revision=base, base_head=base)
    assert adapter.start(req).state is WorkerState.SUCCEEDED
    status = adapter.status(req)
    assert status.state is WorkerState.INCONCLUSIVE
    assert status.error.code is WorkerErrorCode.UNAVAILABLE
    stop = StopRequest(
        operation_key=operation_key_for("stop", req.run_id, req.attempt_id),
        effect_key=req.effect_key, run_id=req.run_id, attempt_id=req.attempt_id,
        attempt=1, candidate_id=req.candidate_id, candidate_revision=req.candidate_revision,
        manifest_sha256=req.manifest_sha256, task_id=req.task_id, story_id=req.story_id,
        sandbox_run_id=req.sandbox_run_id, allowed_paths=req.allowed_paths,
        budget_cap=5, budget_units=2, budget_remaining=3, epoch=1, fence=1,
        reason="stop", authorized_actor="operator-1", invocation_id="invoke-1",
    )
    assert adapter.stop(stop).state is WorkerState.STOPPED
    adapter._active.add((req.run_id, req.attempt_id))
    assert adapter.stop(stop).state is WorkerState.INCONCLUSIVE
    with pytest.raises(TypeError):
        adapter.start("not-a-request")


def test_ac1_stop_and_resume_contracts_fail_closed():
    first = request()
    with pytest.raises(ValueError):
        request(operation_key=operation_key_for("attempt", "run-1", "attempt-9"))
    second = request(attempt_id="attempt-2", attempt=2, epoch=2, fence=2,
                     operation_key=operation_key_for("attempt", "run-1", "attempt-2"))
    base = dict(operation_key=second.operation_key, prior_operation_key=first.operation_key,
                prior_attempt_id=first.attempt_id, prior_attempt=1, prior_epoch=1,
                request=second, remaining_budget=3)
    ResumeRequest(**base)
    for change in ({"prior_attempt_id": "attempt-2"}, {"operation_key": first.operation_key},
                   {"prior_operation_key": "bogus"}, {"remaining_budget": -1}):
        with pytest.raises(ValueError):
            ResumeRequest(**(base | change))


BAD_PATHS = [
    "a" + chr(92) + "b", "a:b", ".git/x", "a/.git/y", ".GIT/x", "./x", "a//b", "/abs", "../x",
    "a/../b", "a\x01b", "a\nb", "", ".", "..", "C:/x", "a/b/", "x" * 513,
]


def _stop_request(**changes) -> StopRequest:
    first = request()
    base = dict(
        operation_key=operation_key_for("stop", first.run_id, first.attempt_id),
        effect_key=first.effect_key, run_id=first.run_id, attempt_id=first.attempt_id,
        attempt=1, candidate_id=first.candidate_id, candidate_revision=first.candidate_revision,
        manifest_sha256=first.manifest_sha256, task_id=first.task_id, story_id=first.story_id,
        sandbox_run_id=first.sandbox_run_id, allowed_paths=first.allowed_paths,
        budget_cap=5, budget_units=2, budget_remaining=3, epoch=1, fence=1,
        reason="operator requested stop", authorized_actor="operator-1", invocation_id="invoke-1",
    )
    base.update(changes)
    return StopRequest(**base)


def _response(**changes) -> WorkerResponse:
    req = request()
    base = dict(
        run_id=req.run_id, attempt_id=req.attempt_id, operation_key=req.operation_key,
        effect_key=req.effect_key, candidate_id=req.candidate_id,
        candidate_revision=req.candidate_revision, manifest_sha256=req.manifest_sha256,
        epoch=1, fence=1, invocation_id=req.invocation_id,
        sandbox_run_id=req.sandbox_run_id, state=WorkerState.INCONCLUSIVE,
        error=WorkerError(WorkerErrorCode.UNAVAILABLE, "pending"),
    )
    base.update(changes)
    return WorkerResponse(**base)


def test_canonical_path_predicate_accepts_plain_and_rejects_every_alias():
    for good in ("src/a.py", "a", "dir/sub/file.txt", "a.b/c", ".github/x.yml"):
        assert is_canonical_repo_path(good), good
    for bad in BAD_PATHS + [None, 5, b"a"]:
        assert not is_canonical_repo_path(bad), bad


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_worker_request_rejects_noncanonical_allowed_paths_and_change_path(bad):
    with pytest.raises(ValueError):
        request(allowed_paths=(bad,), change_path=bad)
    with pytest.raises(ValueError):
        request(allowed_paths=("src/synthetic.py", bad))
    with pytest.raises(ValueError):
        request(change_path=bad)  # not canonical and not in allowed_paths


def test_worker_request_change_path_is_not_normalized_to_allowed_path():
    with pytest.raises(ValueError):
        request(allowed_paths=("src/synthetic.py",), change_path="src" + chr(92) + "synthetic.py")
    with pytest.raises(ValueError):
        request(allowed_paths=("src/synthetic.py",), change_path="./src/synthetic.py")
    ok = request(allowed_paths=("src/a.py", "src/b.py"), change_path="src/b.py")
    assert ok.change_path == "src/b.py"


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_stop_request_rejects_noncanonical_allowed_paths(bad):
    assert _stop_request().allowed_paths == ("src/synthetic.py",)
    with pytest.raises(ValueError):
        _stop_request(allowed_paths=(bad,))
    with pytest.raises(ValueError):
        _stop_request(allowed_paths=("src/synthetic.py", bad))


@pytest.mark.parametrize("bad", BAD_PATHS)
def test_worker_response_rejects_noncanonical_changed_paths(bad):
    assert _response(changed_paths=("src/a.py",)).changed_paths == ("src/a.py",)
    assert _response(changed_paths=()).changed_paths == ()
    with pytest.raises(ValueError):
        _response(changed_paths=(bad,))
    with pytest.raises(ValueError):
        _response(changed_paths=("src/a.py", bad))


def test_retry_exhausted_error_code_exists_and_is_accepted_on_blocked():
    assert WorkerErrorCode("RETRY_EXHAUSTED") is WorkerErrorCode.RETRY_EXHAUSTED
    blocked = _response(state=WorkerState.BLOCKED,
                        error=WorkerError(WorkerErrorCode.RETRY_EXHAUSTED, "retry cap reached"))
    assert blocked.error.code is WorkerErrorCode.RETRY_EXHAUSTED
    with pytest.raises(ValueError):
        WorkerErrorCode("RETRY_EXHAUSTED_X")


def _fixture_with_outcome(tmp_path, recovery_changes):
    fx = SliceFixture(str(tmp_path), SLICE_KEY, FakeClock(),
                      supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
                      event_key=EVENT_KEY)
    fx.begin(1)
    fx.end()
    recovery = {"state": "FAILED", "error_code": "EXECUTION_FAILED", "checkpoint": None,
                "execution_returned": False, "attempt": 1, "epoch": fx.epoch}
    recovery.update(recovery_changes)
    fx.store.execute_idempotent("outcome-attempt-1", "s3_attempt_outcome", {"attempt": 1},
                                lambda _conn: recovery)
    return fx, recovery


def _resume(fx, recovery, op="resume-op"):
    return fx.store.resume_epoch_idempotent(
        op, fx.task_id, fx.story_id, 1, fx.epoch, "outcome-attempt-1",
        recovery, fx.owner, "resume-owner", 600,
    )


def test_resume_accepts_failed_execution_failed_outcome_advances_epoch_once_and_replays(tmp_path):
    fx, recovery = _fixture_with_outcome(tmp_path, {})
    try:
        prior = fx.epoch
        first = _resume(fx, recovery)
        assert first == prior + 1
        assert _resume(fx, recovery) == first
        assert fx.store.current_epoch(fx.story_id) == first
    finally:
        fx.close()


@pytest.mark.parametrize("changes", [
    {"state": "SUCCEEDED", "error_code": None},
    {"state": "SUCCEEDED"},
    {"state": "BLOCKED"},
    {"state": "INCONCLUSIVE"},
    {"error_code": "UNAVAILABLE"},
    {"error_code": "INTERRUPTED"},
    {"execution_returned": True},
    {"checkpoint": "after_edit_before_commit"},
    {"state": "INCONCLUSIVE", "error_code": "EXECUTION_FAILED", "execution_returned": False},
])
def test_resume_rejects_non_failure_and_mixed_outcome_shapes(tmp_path, changes):
    fx, recovery = _fixture_with_outcome(tmp_path, changes)
    try:
        prior = fx.epoch
        with pytest.raises(StoreError) as err:
            _resume(fx, recovery)
        assert err.value.kind == "lifecycle"
        assert fx.store.current_epoch(fx.story_id) == prior
    finally:
        fx.close()


def test_resume_failed_outcome_bound_to_other_attempt_is_rejected(tmp_path):
    fx, recovery = _fixture_with_outcome(tmp_path, {"attempt": 2})
    try:
        with pytest.raises(StoreError) as err:
            _resume(fx, recovery)
        assert err.value.kind == "integrity"
        assert fx.store.current_epoch(fx.story_id) == fx.epoch
    finally:
        fx.close()
