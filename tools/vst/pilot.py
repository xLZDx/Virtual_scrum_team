"""One synthetic story through the vendor-neutral adapter and S2 authority.

The Store owns durable attempt keys, budget, leases, epochs and receipts. The
Supervisor remains the only gate authority. This module never fabricates a
verification receipt or equates worker success with story approval.
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, replace
from typing import Callable

from .slice import HandWrittenWorker, SliceFixture
from .runner import build_environment
from .supervisor import Supervisor
from .store import StoreError
from .contracts import canonical_bytes
from .worker_adapter import (
    Checkpoint,
    ResumeRequest,
    StopRequest,
    StoryWorkerAdapter,
    WorkerError,
    WorkerErrorCode,
    WorkerRequest,
    WorkerResponse,
    WorkerState,
    operation_key_for,
)


class AppLevelInterruption(RuntimeError):
    """A deterministic fixture interruption after a named adapter checkpoint."""


class InterruptedAfterEditBeforeCommit(AppLevelInterruption):
    checkpoint = Checkpoint.AFTER_EDIT_BEFORE_COMMIT


class InterruptedAfterCommitBeforeResponse(AppLevelInterruption):
    checkpoint = Checkpoint.AFTER_COMMIT_BEFORE_RESPONSE


class WorkerExecutionTimeout(RuntimeError):
    """Timeout with uncertain subprocess cleanup; recovery remains fail-closed."""


class WorkerFenceRejected(RuntimeError):
    """The Store epoch changed before the next application checkpoint."""


class HandWrittenWorkerAdapter:
    """Single-path adapter with a deterministic, Git-backed effect key.

    Replaying an effect first searches the local synthetic history for its
    unique commit marker. An edit before commit is safe to repeat because it
    writes the same bounded content. Timeouts and application checkpoints are
    reported as uncertain; no process-kill action is used here.
    """

    def __init__(
        self,
        worker: HandWrittenWorker,
        *,
        candidate_id: str,
        candidate_revision: str,
        checkpoint_hook: Callable[[Checkpoint], None] | None = None,
        timeout_sec: int = 60,
    ):
        if not isinstance(worker, HandWrittenWorker):
            raise TypeError("worker must be the in-repository HandWrittenWorker")
        if checkpoint_hook is not None and not callable(checkpoint_hook):
            raise TypeError("checkpoint_hook must be callable")
        if isinstance(timeout_sec, bool) or not isinstance(timeout_sec, int) or timeout_sec < 1:
            raise ValueError("timeout_sec must be a positive integer")
        if not isinstance(candidate_id, str) or not candidate_id.strip() or len(candidate_id) > 128:
            raise ValueError("candidate_id must be a trusted bounded identifier")
        if (not isinstance(candidate_revision, str) or len(candidate_revision) != 40
                or any(character not in "0123456789abcdef" for character in candidate_revision)):
            raise ValueError("candidate_revision must be a trusted lowercase git id")
        self.worker = worker
        self.candidate_id = candidate_id
        self.candidate_revision = candidate_revision
        self.checkpoint_hook = checkpoint_hook
        self.timeout_sec = timeout_sec
        self._active: set[tuple[str, str]] = set()
        self.fence_check: Callable[[WorkerRequest], bool] | None = None
        # SyntheticStoryPilot replaces this with its own lock so its durable
        # STOP transition and this adapter's filesystem publication serialize.
        self.publication_lock = threading.Lock()

    def _checkpoint(self, checkpoint: Checkpoint) -> None:
        if self.checkpoint_hook is not None:
            self.checkpoint_hook(checkpoint)

    def _check_fence(self, request: WorkerRequest) -> None:
        if self.fence_check is not None and not self.fence_check(request):
            raise WorkerFenceRejected("Store epoch changed at an application checkpoint")

    def _existing_effect_head(self, request: WorkerRequest) -> str | None:
        marker = f"vst-worker-effect {request.effect_key}"
        completed = subprocess.run(
            ["git", "log", "--all", "--format=%H%x00%s", "--fixed-strings", "--grep", marker],
            cwd=self.worker.repository,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=min(self.timeout_sec, request.timeout_sec),
        )
        if completed.returncode:
            raise RuntimeError("could not inspect synthetic worker operation history")
        for line in completed.stdout.decode("ascii", "replace").splitlines():
            head, separator, subject = line.partition("\x00")
            if separator and subject == marker and len(head) == 40:
                return head
        return None

    def start(self, request: WorkerRequest) -> WorkerResponse:
        if not isinstance(request, WorkerRequest):
            raise TypeError("request must be a WorkerRequest")
        if self.worker.allowed_paths != frozenset({request.change_path}):
            return _response(
                request, WorkerState.BLOCKED,
                error=WorkerError(WorkerErrorCode.SCOPE_DENIED, "pilot worker must have exactly the requested path in scope"),
            )
        if (request.candidate_id != self.candidate_id
                or request.candidate_revision != self.candidate_revision):
            return _response(
                request, WorkerState.BLOCKED,
                error=WorkerError(WorkerErrorCode.INVALID_REQUEST,
                                  "candidate identity/revision differs from trusted adapter configuration"),
            )
        identity = (request.run_id, request.attempt_id)
        self._active.add(identity)
        deadline = time.monotonic() + min(self.timeout_sec, request.timeout_sec)

        def remaining() -> float:
            seconds = deadline - time.monotonic()
            if seconds <= 0:
                raise WorkerExecutionTimeout("deadline elapsed")
            return seconds

        try:
            self._check_fence(request)
            prior_head = self._existing_effect_head(request)
            if prior_head is not None:
                self._check_fence(request)
                return _response(
                    request, WorkerState.SUCCEEDED, candidate_head=prior_head,
                    changed_paths=(request.change_path,), progress="replayed durable Git effect marker",
                )
            self._checkpoint(Checkpoint.BEFORE_EDIT)
            # This in-process lock orders all mutations made by this adapter
            # against STOP calls routed through its SyntheticStoryPilot. It
            # does not coordinate separate processes or pilot instances.
            with self.publication_lock:
                self._check_fence(request)
                self.worker.edit(
                    request.change_path, request.change_content,
                    timeout_sec=remaining(),
                )
                self._checkpoint(Checkpoint.AFTER_EDIT_BEFORE_COMMIT)
                self._check_fence(request)
                marker = f"vst-worker-effect {request.effect_key}"
                staged = subprocess.run(
                    ["git", "add", "--", request.change_path],
                    cwd=self.worker.repository, env=build_environment(),
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    check=False, timeout=remaining(),
                )
                if staged.returncode:
                    raise RuntimeError("could not stage the declared synthetic path")
                self._check_fence(request)
                # Command-scoped configuration overrides repository-local
                # core.hooksPath without changing candidate configuration.
                # An empty directory disables pre-commit and post-commit hooks.
                with tempfile.TemporaryDirectory(prefix="vst-empty-hooks-") as hooks_path:
                    committed = subprocess.run(
                        ["git", "-c", f"core.hooksPath={hooks_path}", "commit",
                         "--only", "-m", marker, "--", request.change_path],
                        cwd=self.worker.repository, env=build_environment(),
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        check=False, timeout=remaining(),
                    )
                if committed.returncode:
                    raise RuntimeError("could not commit the declared synthetic path")
                head_result = subprocess.run(
                    ["git", "rev-parse", "--verify", "HEAD"],
                    cwd=self.worker.repository, env=build_environment(),
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    check=False, timeout=remaining(),
                )
                if head_result.returncode:
                    raise RuntimeError("could not resolve the synthetic candidate head")
                head = head_result.stdout.decode("ascii", "replace").strip()
                self._check_fence(request)
                self._checkpoint(Checkpoint.AFTER_COMMIT_BEFORE_RESPONSE)
            return _response(
                request, WorkerState.SUCCEEDED, candidate_head=head,
                changed_paths=(request.change_path,), progress="synthetic change committed",
            )
        except AppLevelInterruption:
            raise
        except subprocess.TimeoutExpired as exc:
            raise WorkerExecutionTimeout(type(exc).__name__) from exc
        finally:
            self._active.discard(identity)

    def status(self, request: WorkerRequest) -> WorkerResponse:
        if not isinstance(request, WorkerRequest):
            raise TypeError("request must be a WorkerRequest")
        return _response(
            request, WorkerState.INCONCLUSIVE,
            error=WorkerError(
                WorkerErrorCode.UNAVAILABLE,
                "handwritten adapter status is recovered from the durable Store operation record",
            ),
        )

    def stop(self, request: StopRequest) -> WorkerResponse:
        if not isinstance(request, StopRequest):
            raise TypeError("request must be a StopRequest")
        # Synchronous subprocess.run calls return only after wait; this local
        # adapter has no supported asynchronous termination control.
        if (request.run_id, request.attempt_id) in self._active:
            return _stop_response(
                request, WorkerState.INCONCLUSIVE,
                WorkerError(WorkerErrorCode.TIMEOUT, "active invocation cleanup is not verified"),
            )
        return _stop_response(
            request, WorkerState.STOPPED,
            WorkerError(WorkerErrorCode.INTERRUPTED, "adapter invocation is no longer active; OS cleanup is not asserted"),
        )

    def resume(self, request: ResumeRequest) -> WorkerResponse:
        if not isinstance(request, ResumeRequest):
            raise TypeError("request must be a ResumeRequest")
        return self.start(request.request)


class SyntheticStoryPilot:
    """Persist start/status/stop/resume around one Store/Supervisor fixture."""

    def __init__(
        self,
        fixture: SliceFixture,
        supervisor: Supervisor,
        adapter: StoryWorkerAdapter,
        *,
        lease_ttl_sec: float = 600,
    ):
        if not isinstance(fixture, SliceFixture):
            raise TypeError("fixture must be a SliceFixture")
        if not isinstance(supervisor, Supervisor):
            raise TypeError("supervisor must be a Supervisor")
        for method in ("start", "status", "stop", "resume"):
            if not callable(getattr(adapter, method, None)):
                raise TypeError(f"adapter must implement {method}(...)" )
        if isinstance(lease_ttl_sec, bool) or not isinstance(lease_ttl_sec, (int, float)) or lease_ttl_sec <= 0:
            raise ValueError("lease_ttl_sec must be positive")
        self.fixture = fixture
        self.supervisor = supervisor
        self.adapter = adapter
        self.lease_ttl_sec = float(lease_ttl_sec)
        if isinstance(adapter, HandWrittenWorkerAdapter):
            # All starts and STOPs through this pilot use one local ordering
            # point. This does not serialize other processes or pilot objects.
            self._publication_lock = threading.Lock()
            adapter.publication_lock = self._publication_lock
            adapter.fence_check = lambda request: (
                fixture.store.reconciliation_complete
                and fixture.store.current_epoch(request.story_id) == request.fence
            )

    def _request_payload(self, request: WorkerRequest) -> dict:
        data = asdict(request)
        return data

    def _effect_payload(self, request: WorkerRequest) -> dict:
        return {
            "effect_key": request.effect_key,
            "run_id": request.run_id,
            "candidate_id": request.candidate_id,
            "candidate_revision": request.candidate_revision,
            "manifest_sha256": request.manifest_sha256,
            "task_id": request.task_id,
            "story_id": request.story_id,
            "sandbox_run_id": request.sandbox_run_id,
            "base_head": request.base_head,
            "allowed_paths": list(request.allowed_paths),
            "change_path": request.change_path,
            "change_content": request.change_content,
            "timeout_sec": request.timeout_sec,
        }

    def _validate_request(self, request: WorkerRequest) -> WorkerResponse | None:
        if not isinstance(request, WorkerRequest):
            raise TypeError("request must be a WorkerRequest")
        manifest = self.fixture.manifest
        store = self.fixture.store
        if request.task_id != manifest["task_id"] or request.story_id != manifest["story_id"]:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.INVALID_REQUEST, "task/story differs from the registered fixture"))
        if request.manifest_sha256 != self.fixture.manifest_hash:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.INVALID_REQUEST, "manifest digest differs from the registered fixture"))
        if tuple(request.allowed_paths) != tuple(manifest["scope"]):
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.SCOPE_DENIED, "allowed paths differ from the registered manifest"))
        if request.budget_cap > manifest["cost_cap"]:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.BUDGET_EXHAUSTED, "request budget cap exceeds the manifest cap"))
        if isinstance(self.adapter, HandWrittenWorkerAdapter) and (
            request.candidate_id != self.adapter.candidate_id
            or request.candidate_revision != self.adapter.candidate_revision
        ):
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.INVALID_REQUEST,
                "candidate identity/revision differs from trusted adapter configuration"))
        if request.epoch != store.current_epoch(request.story_id) or request.fence != request.epoch:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.FENCE_REJECTED, "request epoch/fence is stale"))
        if request.base_head != self.fixture.current_head:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.INVALID_REQUEST, "base head differs from the fixture"))
        if not store.reconciliation_complete:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED, "Store startup reconciliation is incomplete"))
        if self.supervisor.breaker_state != "CLOSED":
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNAVAILABLE, "provider breaker is open"))
        return None

    def _operation_payload(
        self, request: WorkerRequest, resume_context: ResumeRequest | None = None,
    ) -> dict:
        return {
            "request": self._request_payload(request),
            "resume": None if resume_context is None else {
                "prior_operation_key": resume_context.prior_operation_key,
                "prior_attempt_id": resume_context.prior_attempt_id,
                "prior_attempt": resume_context.prior_attempt,
                "prior_epoch": resume_context.prior_epoch,
                "remaining_budget": resume_context.remaining_budget,
            },
        }

    def _attempt_binding_payload(self, request: WorkerRequest, operation: str) -> dict:
        """Persist the identity needed to authorize a later STOP fence."""
        return {
            "operation": operation,
            "run_id": request.run_id,
            "attempt_id": request.attempt_id,
            "attempt": request.attempt,
            "operation_key": request.operation_key,
            "effect_key": request.effect_key,
            "candidate_id": request.candidate_id,
            "candidate_revision": request.candidate_revision,
            "manifest_sha256": request.manifest_sha256,
            "task_id": request.task_id,
            "story_id": request.story_id,
            "epoch": request.epoch,
            "fence": request.fence,
            "sandbox_run_id": request.sandbox_run_id,
            "allowed_paths": list(request.allowed_paths),
            "budget_cap": request.budget_cap,
            "budget_units": request.budget_units,
            "invocation_id": request.invocation_id,
        }

    def _record_attempt_binding(self, request: WorkerRequest, operation: str) -> bool:
        key = _derived_key("attempt-binding", request.operation_key)
        payload = self._attempt_binding_payload(request, operation)
        try:
            result = self.fixture.store.execute_idempotent(
                key, "s3_attempt_binding", payload, lambda _conn: payload,
            )
        except StoreError:
            return False
        return canonical_bytes(result) == canonical_bytes(payload)

    def _stored_response(
        self, operation_key: str, operation: str, *, payload: dict | None = None,
    ) -> tuple[dict | None, WorkerResponse | None]:
        lookup = {"operation": operation}
        if payload is not None:
            lookup.update({"payload": payload, "check_payload": True})
        stored = self.fixture.store.lookup_idempotent_operation(operation_key, **lookup)
        if stored is None:
            return None, None
        if stored["state"] == "COMPLETED":
            result = stored.get("result")
            if isinstance(result, dict) and "state" in result:
                try:
                    return stored, _response_from_dict(result)
                except (TypeError, ValueError, KeyError):
                    return stored, None
        return stored, None

    def start(self, request: WorkerRequest, *, probe: dict | None = None) -> WorkerResponse:
        if isinstance(request, WorkerRequest) and request.attempt != 1:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED, "attempts after the first require resume(...)"))
        return self._execute_attempt(request, "s3_attempt", probe=probe)

    def _execute_attempt(
        self,
        request: WorkerRequest,
        operation: str,
        *,
        probe: dict | None = None,
        resume_context: ResumeRequest | None = None,
    ) -> WorkerResponse:
        rejected = self._validate_request(request)
        if rejected is not None:
            return rejected
        operation_payload = self._operation_payload(request, resume_context)
        prior, replay = self._stored_response(
            request.operation_key, operation, payload=operation_payload
        )
        if replay is not None:
            if replay.run_id != request.run_id or replay.attempt_id != request.attempt_id:
                return _response(request, WorkerState.BLOCKED, error=WorkerError(
                    WorkerErrorCode.INVALID_REQUEST, "stored start response identity differs"))
            return replay
        if prior is not None:
            return _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED,
                "prior start intent has no completed result; use the guarded resume path",
            ))
        stop_key = operation_key_for("stop", request.run_id, request.attempt_id)
        stopped = self.fixture.store.lookup_idempotent_operation(
            stop_key, operation="stop_attempt_fenced"
        )
        if stopped is not None:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.FENCE_REJECTED, "attempt has a durable STOP record"))
        if self.fixture.store.sandbox_mode and probe is None:
            return self._record_blocked_start(request, WorkerError(
                WorkerErrorCode.UNAVAILABLE, "fresh signed sandbox probe is required"))
        if self.fixture.store.sandbox_mode and request.sandbox_run_id != self.supervisor.run_id:
            return self._record_blocked_start(request, WorkerError(
                WorkerErrorCode.INVALID_REQUEST, "sandbox run id differs from the supervisor-bound probe"))
        if not self._record_attempt_binding(request, operation):
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED,
                "durable attempt identity binding conflicts or cannot be recorded"))

        def perform() -> dict:
            validation = self._validate_request(request)
            if validation is not None:
                return _response_dict(validation)
            def run_attempt() -> dict:
                try:
                    self.fixture.store.acquire_lease(
                        request.task_id, request.story_id, self.fixture.runner_id,
                        request.epoch, request.attempt, self.lease_ttl_sec,
                        supervisor_key=self.fixture.supervisor_key,
                    )
                except StoreError as exc:
                    if exc.kind in {"epoch", "lease", "slot", "retry", "terminal", "budget"}:
                        return _response_dict(_response(request, WorkerState.BLOCKED, error=WorkerError(
                            WorkerErrorCode.FENCE_REJECTED if exc.kind == "epoch" else WorkerErrorCode.BUDGET_EXHAUSTED,
                            f"Store refused lease: {exc.kind}",
                        )))
                    raise
                budget_key = _derived_key("budget", request.operation_key)
                try:
                    remaining = self.fixture.store.charge_idempotent(
                        budget_key, request.task_id, request.budget_units,
                        supervisor_key=self.fixture.supervisor_key,
                        expected_cap=request.budget_cap,
                        expected_spent=request.budget_spent,
                    )
                except StoreError as exc:
                    self.fixture.store.release_lease(
                        request.task_id, self.fixture.runner_id, request.epoch
                    )
                    if exc.kind == "budget":
                        return _response_dict(_response(request, WorkerState.BLOCKED, error=WorkerError(
                            WorkerErrorCode.BUDGET_EXHAUSTED, "Store budget cap blocked worker start")))
                    if exc.kind == "budget_snapshot":
                        return _response_dict(_response(request, WorkerState.BLOCKED, error=WorkerError(
                            WorkerErrorCode.BUDGET_EXHAUSTED,
                            "caller budget snapshot differs from Store; no charge was applied")))
                    raise
                expected_remaining = request.budget_cap - request.budget_spent - request.budget_units
                if expected_remaining < 0 or remaining != expected_remaining:
                    self.fixture.store.release_lease(
                        request.task_id, self.fixture.runner_id, request.epoch
                    )
                    return _response_dict(_response(request, WorkerState.BLOCKED, error=WorkerError(
                        WorkerErrorCode.BUDGET_EXHAUSTED,
                        "request budget snapshot differs from the authoritative Store ledger",
                    ), budget_remaining=remaining))
                response = self._run_effect(request, remaining, resume_context)
                lease_can_close = (
                    response.state in {WorkerState.SUCCEEDED, WorkerState.FAILED,
                                       WorkerState.BLOCKED, WorkerState.STOPPED}
                    or (response.state == WorkerState.INCONCLUSIVE
                        and response.error is not None
                        and response.error.code == WorkerErrorCode.INTERRUPTED
                        and response.checkpoint is not None)
                )
                if lease_can_close:
                    self.fixture.store.release_lease(
                        request.task_id, self.fixture.runner_id, request.epoch
                    )
                outcome_key = _derived_key("outcome", request.operation_key)
                recovery_outcome = {
                    "state": response.state.value,
                    "error_code": None if response.error is None else response.error.code.value,
                    "checkpoint": None if response.checkpoint is None else response.checkpoint.value,
                    "execution_returned": response.error is not None and response.error.code == WorkerErrorCode.INTERRUPTED,
                    "attempt": request.attempt,
                    "epoch": request.epoch,
                }
                self.fixture.store.execute_idempotent(
                    outcome_key, "s3_attempt_outcome", recovery_outcome,
                    lambda _conn: recovery_outcome,
                )
                return _response_dict(response)
            if self.fixture.store.sandbox_mode:
                raw = self.supervisor.start_worker(
                    run_attempt, probe=probe, action_id=request.operation_key
                )
                return raw
            return run_attempt()

        try:
            stored = self.fixture.store.execute_external_idempotent(
                request.operation_key, operation, operation_payload, perform
            )
            response = _response_from_dict(stored)
        except Exception as exc:
            response = _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED, type(exc).__name__,
            ))
        return self._validate_response(request, response)

    def _record_blocked_start(self, request: WorkerRequest, error: WorkerError) -> WorkerResponse:
        response = _response(request, WorkerState.BLOCKED, error=error)
        payload = self._operation_payload(request)
        stored = self.fixture.store.execute_idempotent(
            request.operation_key, "s3_attempt", payload,
            lambda _conn: _response_dict(response),
        )
        return _response_from_dict(stored)

    def _run_effect(
        self, request: WorkerRequest, remaining: int,
        resume_context: ResumeRequest | None = None,
    ) -> WorkerResponse:
        if self.fixture.store.current_epoch(request.story_id) != request.fence:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.FENCE_REJECTED, "Store epoch changed before worker invocation"),
                budget_remaining=remaining)
        payload = self._effect_payload(request)

        def effect() -> dict:
            response = (
                self.adapter.start(request) if resume_context is None
                else self.adapter.resume(resume_context)
            )
            return _response_dict(self._validate_response(request, response))

        try:
            result = self.fixture.store.execute_external_idempotent(
                request.effect_key, "s3_worker_effect", payload, effect
            )
        except AppLevelInterruption as exc:
            return _response(
                request, WorkerState.INCONCLUSIVE,
                checkpoint=exc.checkpoint,
                error=WorkerError(WorkerErrorCode.INTERRUPTED, type(exc).__name__),
                budget_remaining=remaining,
            )
        except WorkerExecutionTimeout as exc:
            return _response(
                request, WorkerState.INCONCLUSIVE,
                error=WorkerError(WorkerErrorCode.TIMEOUT, type(exc).__name__),
                budget_remaining=remaining,
            )
        except WorkerFenceRejected as exc:
            return _response(
                request, WorkerState.INCONCLUSIVE,
                error=WorkerError(WorkerErrorCode.FENCE_REJECTED, type(exc).__name__),
                budget_remaining=remaining,
            )
        except Exception as exc:
            return _response(
                request, WorkerState.INCONCLUSIVE,
                error=WorkerError(WorkerErrorCode.RECONCILIATION_REQUIRED, type(exc).__name__),
                budget_remaining=remaining,
            )
        return _response_from_dict(result)

    def status(self, request: WorkerRequest) -> WorkerResponse:
        if not isinstance(request, WorkerRequest):
            raise TypeError("request must be a WorkerRequest")
        operation = "s3_attempt" if request.attempt == 1 else "s3_resume"
        stored, response = self._stored_response(request.operation_key, operation)
        if response is not None:
            if response.state in {WorkerState.QUEUED, WorkerState.RUNNING}:
                try:
                    observed = self.adapter.status(request)
                except Exception as exc:
                    return _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
                        WorkerErrorCode.UNSUPPORTED_STATE, type(exc).__name__))
                if isinstance(observed, WorkerResponse):
                    response = self._validate_response(request, observed)
                    if response.state in {WorkerState.SUCCEEDED, WorkerState.FAILED,
                                          WorkerState.STOPPED, WorkerState.BLOCKED}:
                        try:
                            self.fixture.store.release_lease(
                                request.task_id, self.fixture.runner_id, request.epoch
                            )
                        except StoreError:
                            return _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
                                WorkerErrorCode.FENCE_REJECTED,
                                "terminal status arrived after the Store lease was no longer current",
                            ))
                    status_payload = {
                        "request": self._request_payload(request),
                        "response": _response_dict(response),
                    }
                    status_key = _derived_key(
                        "status",
                        request.operation_key + ":" + hashlib.sha256(canonical_bytes(status_payload)).hexdigest(),
                    )
                    try:
                        saved = self.fixture.store.execute_idempotent(
                            status_key, "s3_status", status_payload,
                            lambda _conn: _response_dict(response),
                        )
                        response = _response_from_dict(saved)
                    except StoreError:
                        return _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
                            WorkerErrorCode.UNSUPPORTED_STATE, "status result conflicts with its durable binding"))
            return self._validate_response(request, response)
        if stored is None:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNAVAILABLE, "no durable start record exists"))
        return _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
            WorkerErrorCode.RECONCILIATION_REQUIRED,
            "operation is pending or uncertain; no worker status is promoted to success",
        ))

    def stop(self, request: StopRequest) -> WorkerResponse:
        if not isinstance(request, StopRequest):
            raise TypeError("request must be a StopRequest")
        manifest = self.fixture.manifest
        if (request.task_id != manifest["task_id"]
                or request.story_id != manifest["story_id"]
                or request.manifest_sha256 != self.fixture.manifest_hash
                or tuple(request.allowed_paths) != tuple(manifest["scope"])
                or request.budget_cap > manifest["cost_cap"]):
            return _stop_response(request, WorkerState.BLOCKED, WorkerError(
                WorkerErrorCode.INVALID_REQUEST,
                "STOP task/story/manifest/scope/budget differs from the registered fixture",
            ))
        if isinstance(self.adapter, HandWrittenWorkerAdapter) and (
            request.candidate_id != self.adapter.candidate_id
            or request.candidate_revision != self.adapter.candidate_revision
        ):
            return _stop_response(request, WorkerState.BLOCKED, WorkerError(
                WorkerErrorCode.INVALID_REQUEST,
                "STOP candidate identity/revision differs from trusted adapter configuration",
            ))
        prior_operation = "s3_attempt" if request.attempt == 1 else "s3_resume"
        prior_key = operation_key_for("attempt", request.run_id, request.attempt_id)
        try:
            prior = self.fixture.store.lookup_idempotent_operation(
                prior_key, operation=prior_operation,
            )
            binding_key = _derived_key("attempt-binding", prior_key)
            binding = self.fixture.store.lookup_idempotent_operation(
                binding_key, operation="s3_attempt_binding",
            )
        except StoreError:
            prior = None
            binding = None
        expected_binding = {
            "operation": prior_operation,
            "run_id": request.run_id,
            "attempt_id": request.attempt_id,
            "attempt": request.attempt,
            "operation_key": prior_key,
            "effect_key": request.effect_key,
            "candidate_id": request.candidate_id,
            "candidate_revision": request.candidate_revision,
            "manifest_sha256": request.manifest_sha256,
            "task_id": request.task_id,
            "story_id": request.story_id,
            "epoch": request.epoch,
            "fence": request.fence,
            "sandbox_run_id": request.sandbox_run_id,
            "allowed_paths": list(request.allowed_paths),
            "budget_cap": request.budget_cap,
            "budget_units": request.budget_units,
            "invocation_id": request.invocation_id,
        }
        valid_prior = prior is not None and prior.get("state") in {"PENDING", "INCONCLUSIVE"}
        if prior is not None and prior.get("state") == "COMPLETED":
            try:
                prior_response = _response_from_dict(prior.get("result"))
                valid_prior = prior_response.state in {
                    WorkerState.QUEUED, WorkerState.RUNNING, WorkerState.INCONCLUSIVE,
                }
            except (TypeError, ValueError, KeyError):
                valid_prior = False
        if (not valid_prior or binding is None or binding.get("state") != "COMPLETED"
                or canonical_bytes(binding.get("result")) != canonical_bytes(expected_binding)):
            return _stop_response(request, WorkerState.BLOCKED, WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED,
                "STOP requires a durable matching prior attempt and identity binding",
            ))
        if self.fixture.store.sandbox_mode and request.sandbox_run_id != self.supervisor.run_id:
            return _stop_response(request, WorkerState.BLOCKED, WorkerError(
                WorkerErrorCode.INVALID_REQUEST, "STOP sandbox run differs from the active supervisor run"))
        def fence_attempt() -> dict:
            return self.fixture.store.stop_attempt_fenced(
                request.operation_key, request.task_id, request.story_id,
                request.attempt, request.epoch,
                self._owner_for_attempt(request.run_id, request.attempt_id, request.attempt),
                request.reason, request.authorized_actor,
                binding={
                    "candidate_id": request.candidate_id,
                    "candidate_revision": request.candidate_revision,
                    "manifest_sha256": request.manifest_sha256,
                    "effect_key": request.effect_key,
                    "sandbox_run_id": request.sandbox_run_id,
                    "allowed_paths": list(request.allowed_paths),
                    "budget_cap": request.budget_cap,
                    "budget_units": request.budget_units,
                    "budget_remaining": request.budget_remaining,
                    "invocation_id": request.invocation_id,
                },
            )

        if isinstance(self.adapter, HandWrittenWorkerAdapter):
            # STOP's durable epoch advance and adapter worktree publication are
            # ordered in this pilot process. Release before adapter.stop so
            # cleanup diagnostics cannot hold up future fenced work.
            with self._publication_lock:
                result = fence_attempt()
        else:
            result = fence_attempt()
        # The synchronous worker adapter cannot prove OS-level termination.
        # Store epoch fencing is durable; process cleanup remains INCONCLUSIVE.
        cleanup_error_type: str | None = None
        try:
            self.adapter.stop(request)
        except Exception as exc:
            cleanup_error_type = _bounded_exception_type(exc)
        cleanup_message = (
            "epoch fenced; adapter.stop completed but worker process cleanup is NOT_VERIFIED"
            if cleanup_error_type is None else
            "epoch fenced; adapter.stop raised "
            f"{cleanup_error_type}; worker process cleanup is NOT_VERIFIED"
        )
        return _stop_response(
            request, WorkerState.INCONCLUSIVE,
            WorkerError(WorkerErrorCode.INTERRUPTED, cleanup_message),
            progress=f"new_fence={result['new_epoch']}",
        )

    def resume(self, request: ResumeRequest, *, probe: dict | None = None) -> WorkerResponse:
        if not isinstance(request, ResumeRequest):
            raise TypeError("request must be a ResumeRequest")
        new_request = request.request
        prior_operation = "s3_attempt" if request.prior_attempt == 1 else "s3_resume"
        prior = self.fixture.store.lookup_idempotent_operation(
            request.prior_operation_key, operation=prior_operation
        )
        resume_payload = self._operation_payload(new_request, request)
        existing_resume, replay = self._stored_response(
            request.operation_key, "s3_resume", payload=resume_payload
        )
        if replay is not None:
            return self._validate_response(new_request, replay)
        if existing_resume is not None:
            return _response(new_request, WorkerState.INCONCLUSIVE, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED,
                "resume operation already has an unresolved durable intent",
            ))
        if prior is None:
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED, "prior attempt has no durable operation"))
        if prior["state"] != "COMPLETED" or not isinstance(prior.get("result"), dict):
            return _response(new_request, WorkerState.INCONCLUSIVE, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED, "prior external operation has uncertain status"))
        try:
            prior_response = _response_from_dict(prior["result"])
        except (TypeError, ValueError, KeyError):
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNSUPPORTED_STATE, "prior backend response is malformed"))
        if prior_response.state != WorkerState.INCONCLUSIVE or prior_response.error is None or prior_response.error.code != WorkerErrorCode.INTERRUPTED:
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNSUPPORTED_STATE, "resume requires a recorded application checkpoint"))
        if (prior_response.attempt_id != request.prior_attempt_id
                or prior_response.epoch != request.prior_epoch
                or prior_response.run_id != new_request.run_id):
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.INVALID_REQUEST, "resume prior attempt identity/fence differs"))
        if request.remaining_budget < new_request.budget_units:
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.BUDGET_EXHAUSTED, "remaining budget is below the requested attempt cost"))
        if (prior_response.effect_key != new_request.effect_key
                or prior_response.manifest_sha256 != new_request.manifest_sha256
                or prior_response.candidate_revision != new_request.candidate_revision):
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.INVALID_REQUEST, "resume changed the prior effect or candidate binding"))
        outcome_key = _derived_key("outcome", request.prior_operation_key)
        outcome_result = self.fixture.store.lookup_idempotent_operation(
            outcome_key, operation="s3_attempt_outcome"
        )
        if outcome_result is None or outcome_result["state"] != "COMPLETED":
            return _response(new_request, WorkerState.INCONCLUSIVE, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED, "prior app checkpoint is not durably reconciled"))
        recovery = outcome_result["result"]
        if not isinstance(recovery, dict):
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNSUPPORTED_STATE, "prior recovery result is malformed"))
        if recovery.get("checkpoint") not in {
            Checkpoint.AFTER_EDIT_BEFORE_COMMIT.value,
            Checkpoint.AFTER_COMMIT_BEFORE_RESPONSE.value,
        }:
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNSUPPORTED_STATE, "checkpoint has no safe automatic resume rule"))
        expected_owner = self._owner_for_attempt(
            new_request.run_id, request.prior_attempt_id, request.prior_attempt
        )
        new_owner = self._owner_for_attempt(
            new_request.run_id, new_request.attempt_id, new_request.attempt
        )
        epoch_operation_key = _derived_key("resume-epoch", request.operation_key)
        expected_new_epoch = request.prior_epoch + 1
        if new_request.epoch != expected_new_epoch:
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.FENCE_REJECTED, "resume request must carry exactly the next epoch"))
        if self.fixture.store.sandbox_mode and probe is None:
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNAVAILABLE, "resume requires a fresh signed sandbox probe"))
        if self.fixture.store.sandbox_mode and not self._valid_unconsumed_resume_probe(
            probe, new_request.sandbox_run_id,
        ):
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNAVAILABLE,
                "resume probe signature/attestation is invalid or its run/nonce is not fresh"))
        # Validate all non-transition request bindings against the current
        # Store state before creating the durable resume binding or advancing
        # the epoch. The actual request already carries the next epoch.
        prior_fence_request = replace(
            new_request, epoch=request.prior_epoch, fence=request.prior_epoch,
        )
        rejected = self._validate_request(prior_fence_request)
        if rejected is not None:
            return _response(new_request, WorkerState.BLOCKED, error=rejected.error)
        if not self._record_attempt_binding(new_request, "s3_resume"):
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED,
                "durable resume identity binding conflicts or cannot be recorded"))
        try:
            epoch = self.fixture.store.resume_epoch_idempotent(
                epoch_operation_key,
                new_request.task_id, new_request.story_id,
                request.prior_attempt,
                request.prior_epoch,
                outcome_key,
                recovery,
                expected_owner,
                new_owner,
                self.lease_ttl_sec,
            )
        except StoreError as exc:
            return _response(new_request, WorkerState.INCONCLUSIVE, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED, f"resume fence: {exc.kind}"))
        if epoch != new_request.epoch:
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.FENCE_REJECTED, "request epoch differs from the durable resume epoch"))
        if self.fixture.store.sandbox_mode:
            if self.supervisor.lifecycle_state == "RUNNING":
                try:
                    self.supervisor.stop(
                        lambda: self._require_inactive(request.prior_attempt_id),
                        lambda: None,
                        action_id=_derived_key("lifecycle-stop", request.prior_operation_key),
                    )
                except Exception as exc:
                    return _response(new_request, WorkerState.INCONCLUSIVE, error=WorkerError(
                        WorkerErrorCode.RECONCILIATION_REQUIRED, type(exc).__name__))
            if self.supervisor.lifecycle_state == "STOPPED":
                try:
                    self.supervisor.resume(
                        lambda: epoch,
                        action_id=_derived_key("lifecycle-resume", request.operation_key),
                    )
                    self.supervisor.prepare_run(new_request.sandbox_run_id, probe["nonce"])
                except Exception as exc:
                    return _response(new_request, WorkerState.INCONCLUSIVE, error=WorkerError(
                        WorkerErrorCode.RECONCILIATION_REQUIRED, type(exc).__name__))
        return self._execute_attempt(
            new_request, "s3_resume", probe=probe, resume_context=request
        )

    def _valid_unconsumed_resume_probe(self, probe: dict | None, run_id: str) -> bool:
        """Verify signatures before Store epoch mutation without consuming the probe."""
        if not isinstance(probe, dict):
            return False
        nonce = probe.get("nonce")
        if (not isinstance(nonce, str) or not nonce.strip()
                or run_id in self.supervisor._seen_run_ids
                or nonce in self.supervisor._seen_probe_nonces):
            return False
        try:
            from .preflight import (
                SPEC_PATH, verify_fresh_probe, verify_network_policy_attestation,
            )
            spec_sha256 = hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
            if not verify_fresh_probe(
                probe, run_id=run_id, spec_sha256=spec_sha256,
                nonce=nonce, key=bytes(self.supervisor.probe_key),
            ):
                return False
            attestation = probe["inventory"].get("network_policy_attestation")
            return verify_network_policy_attestation(
                attestation, run_id=run_id, spec_sha256=spec_sha256,
                nonce=nonce, key=bytes(self.supervisor.operator_key),
            )
        except (OSError, TypeError, ValueError):
            return False

    def _owner_for_attempt(self, run_id: str, attempt_id: str, attempt: int) -> str:
        if attempt == 1:
            return self.fixture.owner
        digest = hashlib.sha256(f"{run_id}\0{attempt_id}".encode("utf-8")).hexdigest()[:24]
        return f"resume-{digest}"

    def _require_inactive(self, attempt_id: str) -> None:
        if isinstance(self.adapter, HandWrittenWorkerAdapter) and any(
            active_attempt == attempt_id for _run_id, active_attempt in self.adapter._active
        ):
            raise StoreError("handwritten adapter still reports an active invocation", kind="lifecycle")

    def _validate_response(self, request: WorkerRequest, response: WorkerResponse) -> WorkerResponse:
        if not isinstance(response, WorkerResponse):
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNSUPPORTED_STATE, "adapter response is not a typed WorkerResponse"))
        identity = (
            response.run_id == request.run_id
            and response.attempt_id == request.attempt_id
            and response.operation_key == request.operation_key
            and response.effect_key == request.effect_key
            and response.candidate_id == request.candidate_id
            and response.candidate_revision == request.candidate_revision
            and response.manifest_sha256 == request.manifest_sha256
            and response.epoch == request.epoch
            and response.fence == request.fence
            and response.invocation_id == request.invocation_id
            and response.sandbox_run_id == request.sandbox_run_id
        )
        if not identity:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.INVALID_REQUEST, "adapter response identity/fence does not match request"))
        if response.state == WorkerState.SUCCEEDED:
            if not response.changed_paths or not set(response.changed_paths).issubset(set(request.allowed_paths)):
                return _response(request, WorkerState.BLOCKED, error=WorkerError(
                    WorkerErrorCode.SCOPE_DENIED, "adapter reported changes outside allowed paths"))
            if self.fixture.store.current_epoch(request.story_id) != request.fence:
                return _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
                    WorkerErrorCode.FENCE_REJECTED, "epoch changed after worker completion"))
        return response

    def evaluate(self, request: WorkerRequest) -> dict:
        """Return only the S2 Store/Supervisor decision for current receipts."""
        response = self.status(request)
        return self.supervisor.evaluate_gate(
            request.task_id,
            response.candidate_head or request.base_head,
            self.fixture.store.current_epoch(request.story_id),
            self.fixture.key,
        )


def _bounded_exception_type(exc: Exception) -> str:
    """Return a bounded exception class name without exposing exception text."""
    name = type(exc).__name__
    if isinstance(name, str) and len(name) <= 64 and name.isascii() and name.isidentifier():
        return name
    return "UnknownError"


def _derived_key(kind: str, value: str) -> str:
    return f"s3-{kind}-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _response(
    request: WorkerRequest,
    state: WorkerState,
    *,
    error: WorkerError | None = None,
    checkpoint: Checkpoint | None = None,
    candidate_head: str | None = None,
    changed_paths: tuple[str, ...] = (),
    progress: str = "",
    budget_remaining: int | None = None,
) -> WorkerResponse:
    return WorkerResponse(
        run_id=request.run_id,
        attempt_id=request.attempt_id,
        operation_key=request.operation_key,
        effect_key=request.effect_key,
        candidate_id=request.candidate_id,
        candidate_revision=request.candidate_revision,
        manifest_sha256=request.manifest_sha256,
        epoch=request.epoch,
        fence=request.fence,
        invocation_id=request.invocation_id,
        sandbox_run_id=request.sandbox_run_id,
        state=state,
        progress=progress,
        candidate_head=candidate_head,
        changed_paths=changed_paths,
        checkpoint=checkpoint,
        error=error,
        budget_cap=request.budget_cap,
        budget_units=request.budget_units,
        budget_remaining=budget_remaining,
    )


def _stop_response(
    request: StopRequest,
    state: WorkerState,
    error: WorkerError,
    *,
    progress: str = "",
) -> WorkerResponse:
    return WorkerResponse(
        run_id=request.run_id,
        attempt_id=request.attempt_id,
        operation_key=request.operation_key,
        effect_key=request.effect_key,
        candidate_id=request.candidate_id,
        candidate_revision=request.candidate_revision,
        manifest_sha256=request.manifest_sha256,
        epoch=request.epoch,
        fence=request.fence,
        invocation_id=request.invocation_id,
        sandbox_run_id=request.sandbox_run_id,
        state=state,
        progress=progress,
        error=error,
        budget_cap=request.budget_cap,
        budget_units=request.budget_units,
        budget_remaining=request.budget_remaining,
    )


def _response_dict(response: WorkerResponse) -> dict:
    return {
        "run_id": response.run_id,
        "attempt_id": response.attempt_id,
        "operation_key": response.operation_key,
        "effect_key": response.effect_key,
        "candidate_id": response.candidate_id,
        "candidate_revision": response.candidate_revision,
        "manifest_sha256": response.manifest_sha256,
        "epoch": response.epoch,
        "fence": response.fence,
        "invocation_id": response.invocation_id,
        "sandbox_run_id": response.sandbox_run_id,
        "state": response.state.value,
        "progress": response.progress,
        "evidence_refs": list(response.evidence_refs),
        "candidate_head": response.candidate_head,
        "changed_paths": list(response.changed_paths),
        "checkpoint": None if response.checkpoint is None else response.checkpoint.value,
        "error": None if response.error is None else {
            "code": response.error.code.value,
            "message": response.error.message,
            "retryable": response.error.retryable,
        },
        "elapsed_ms": response.elapsed_ms,
        "budget_remaining": response.budget_remaining,
        "budget_cap": response.budget_cap,
        "budget_units": response.budget_units,
    }


def _response_from_dict(data: dict) -> WorkerResponse:
    error_data = data.get("error")
    error = None if error_data is None else WorkerError(
        WorkerErrorCode(error_data["code"]),
        error_data["message"],
        error_data["retryable"],
    )
    checkpoint_value = data.get("checkpoint")
    return WorkerResponse(
        run_id=data["run_id"],
        attempt_id=data["attempt_id"],
        operation_key=data["operation_key"],
        effect_key=data["effect_key"],
        candidate_id=data["candidate_id"],
        candidate_revision=data["candidate_revision"],
        manifest_sha256=data["manifest_sha256"],
        epoch=data["epoch"],
        fence=data["fence"],
        invocation_id=data["invocation_id"],
        sandbox_run_id=data["sandbox_run_id"],
        state=WorkerState(data["state"]),
        progress=data.get("progress", ""),
        evidence_refs=tuple(data.get("evidence_refs", [])),
        candidate_head=data.get("candidate_head"),
        changed_paths=tuple(data.get("changed_paths", [])),
        checkpoint=None if checkpoint_value is None else Checkpoint(checkpoint_value),
        error=error,
        elapsed_ms=data.get("elapsed_ms", 0),
        budget_remaining=data.get("budget_remaining"),
        budget_cap=data.get("budget_cap", 0),
        budget_units=data.get("budget_units", 0),
    )


