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
        timeout = min(self.timeout_sec, request.timeout_sec)
        # Only commits reachable from the candidate HEAD are searched (no --all),
        # so a marker on an unrelated ref or branch is never trusted.
        completed = _run_git(
            self.worker.repository,
            ["log", "HEAD", "--format=%H%x00%s", "--fixed-strings", "--grep", marker, "--"],
            timeout,
        )
        if completed.returncode:
            raise RuntimeError("could not inspect synthetic worker operation history")
        expected_blob = request.change_content.encode("utf-8")
        for line in completed.stdout.decode("ascii", "replace").splitlines():
            head, separator, subject = line.partition("\x00")
            if not (separator and subject == marker and len(head) == 40):
                continue
            # The marker text alone is not proof: the commit must descend from
            # the trusted candidate revision and carry exactly the requested blob.
            if _run_git(
                self.worker.repository,
                ["merge-base", "--is-ancestor", request.candidate_revision, head], timeout,
            ).returncode:
                continue
            blob = _run_git(
                self.worker.repository, ["cat-file", "blob", f"{head}:{request.change_path}"], timeout,
            )
            if blob.returncode == 0 and blob.stdout == expected_blob:
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
        commit_verifier: Callable[[WorkerRequest, WorkerResponse], WorkerResponse | None] | None = None,
    ):
        """``commit_verifier`` is the only way a non-HandWrittenWorkerAdapter may
        report SUCCEEDED: it receives the request and the SUCCEEDED response and
        returns None to accept or a downgraded response to refuse. Without it
        (the safe default) every SUCCEEDED claim from such an adapter is
        refused as unverified; the HandWritten adapter is verified against its
        own trusted repository instead.
        """
        if commit_verifier is not None and not callable(commit_verifier):
            raise TypeError("commit_verifier must be callable")
        self.commit_verifier = commit_verifier
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
        # Only fields bound by effect_key: per-attempt values (sandbox_run_id,
        # timeout_sec) would make an honest resume collide as a duplicate.
        return {
            "effect_key": request.effect_key,
            "run_id": request.run_id,
            "candidate_id": request.candidate_id,
            "candidate_revision": request.candidate_revision,
            "manifest_sha256": request.manifest_sha256,
            "task_id": request.task_id,
            "story_id": request.story_id,
            "base_head": request.base_head,
            "allowed_paths": list(request.allowed_paths),
            "change_path": request.change_path,
            "change_content": request.change_content,
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
        try:
            current_epoch = store.current_epoch(request.story_id)
        except StoreError as exc:
            return _store_failure(request, exc, "epoch lookup")
        if request.epoch != current_epoch or request.fence != request.epoch:
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
        fresh_effect: bool = False,
    ) -> WorkerResponse:
        rejected = self._validate_request(request)
        if rejected is not None:
            return rejected
        operation_payload = self._operation_payload(request, resume_context)
        try:
            prior, replay = self._stored_response(
                request.operation_key, operation, payload=operation_payload
            )
        except StoreError as exc:
            return _store_failure(request, exc, "operation lookup")
        if replay is not None:
            if replay.run_id != request.run_id or replay.attempt_id != request.attempt_id:
                return _response(request, WorkerState.BLOCKED, error=WorkerError(
                    WorkerErrorCode.INVALID_REQUEST, "stored start response identity differs"))
            # Re-verify on every replay: the stored claim is never trusted blindly.
            return self._validate_response(request, replay)
        if prior is not None:
            return _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED,
                "prior start intent has no completed result; use the guarded resume path",
            ))
        stop_key = operation_key_for("stop", request.run_id, request.attempt_id)
        try:
            stopped = self.fixture.store.lookup_idempotent_operation(
                stop_key, operation="stop_attempt_fenced"
            )
        except StoreError as exc:
            return _store_failure(request, exc, "STOP lookup")
        if stopped is not None:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.FENCE_REJECTED, "attempt has a durable STOP record"))
        # These refusals are transient caller/setup conditions. They are not
        # persisted, so the same operation key can be retried with a valid probe
        # instead of being replayed as a permanent COMPLETED refusal. (This also
        # removes the former hard-coded "s3_attempt" operation name that collided
        # with the "s3_resume" key of a resume.)
        if self.fixture.store.sandbox_mode and probe is None:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNAVAILABLE, "fresh signed sandbox probe is required"))
        if self.fixture.store.sandbox_mode and request.sandbox_run_id != self.supervisor.run_id:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.INVALID_REQUEST, "sandbox run id differs from the supervisor-bound probe"))
        if not self._record_attempt_binding(request, operation):
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED,
                "durable attempt identity binding conflicts or cannot be recorded"))

        # Lease acquisition happens BEFORE the durable external intent. Rule:
        # transient refusals (slot, lease) are returned unpersisted, exactly like
        # the missing-probe refusal, so the same operation key stays retryable
        # (an intent row would otherwise replay the refusal forever or look like
        # an unresolved start). Terminal refusals (epoch, retry, terminal,
        # budget) stay fail-closed and ARE persisted as a completed BLOCKED
        # result. The acquired lease is released if nothing past the lease
        # (the budget charge) happened before an exception escaped.
        try:
            self.fixture.store.acquire_lease(
                request.task_id, request.story_id, self.fixture.runner_id,
                request.epoch, request.attempt, self.lease_ttl_sec,
                supervisor_key=self.fixture.supervisor_key,
            )
        except StoreError as exc:
            refusal_code = _LEASE_REFUSAL_CODES.get(exc.kind)
            if refusal_code is None:
                return _store_failure(request, exc, "lease acquisition")
            refusal = _response(request, WorkerState.BLOCKED, error=WorkerError(
                refusal_code, f"Store refused lease: {exc.kind}",
            ))
            if exc.kind in _TRANSIENT_LEASE_KINDS:
                return refusal
            try:
                stored_refusal = self.fixture.store.execute_external_idempotent(
                    request.operation_key, operation, operation_payload,
                    lambda: _response_dict(refusal),
                )
                return self._validate_response(request, _response_from_dict(stored_refusal))
            except StoreError as inner:
                return _store_failure(request, inner, "attempt")

        def perform() -> dict:
            validation = self._validate_request(request)
            if validation is not None:
                self._release_unstarted_lease(request)
                if validation.state != WorkerState.BLOCKED:
                    # A Store failure is not a verdict on the request: leave the
                    # intent unresolved instead of persisting it as COMPLETED.
                    raise RuntimeError("request validation was inconclusive")
                return _response_dict(validation)
            def run_attempt() -> dict:
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
                response = self._run_effect(
                    request, remaining, resume_context, fresh_effect=fresh_effect)
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
        except StoreError as exc:
            self._release_unstarted_lease(request)
            response = _store_failure(request, exc, "attempt")
        except Exception as exc:
            self._release_unstarted_lease(request)
            response = _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED, _exception_label(exc),
            ))
        return self._validate_response(request, response)

    def _release_unstarted_lease(self, request: WorkerRequest) -> None:
        """Release the pre-intent lease when the attempt never reached the budget charge.

        Past the charge the lease follows the normal outcome rules (kept while
        the result is uncertain). A failed release leaves the lease to expire
        by TTL; it never changes the response.
        """
        try:
            charged = self.fixture.store.lookup_idempotent_operation(
                _derived_key("budget", request.operation_key), operation="budget_charge",
            )
            if charged is None:
                self.fixture.store.release_lease(
                    request.task_id, self.fixture.runner_id, request.epoch)
        except StoreError:
            pass

    def _run_effect(
        self, request: WorkerRequest, remaining: int,
        resume_context: ResumeRequest | None = None,
        *, fresh_effect: bool = False,
    ) -> WorkerResponse:
        try:
            epoch_now = self.fixture.store.current_epoch(request.story_id)
        except StoreError as exc:
            return _store_failure(request, exc, "epoch lookup")
        if epoch_now != request.fence:
            return _response(request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.FENCE_REJECTED, "Store epoch changed before worker invocation"),
                budget_remaining=remaining)
        payload = self._effect_payload(request)

        def effect() -> dict:
            response = (
                self.adapter.start(request) if resume_context is None
                else self.adapter.resume(resume_context)
            )
            # No git verification here: a transient git failure must not be cached
            # in the stored effect. The outer validation re-verifies on every call.
            return _response_dict(self._validate_response(request, response, verify=False))

        # A retry after a recorded FAILED attempt must not replay that attempt's
        # completed effect result, so it gets its own per-attempt Store key. The
        # adapter still dedupes the Git effect through the effect_key marker.
        store_effect_key = (
            _derived_key("effect-retry", request.operation_key) if fresh_effect else request.effect_key
        )
        try:
            result = self.fixture.store.execute_external_idempotent(
                store_effect_key, "s3_worker_effect", payload, effect
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
                error=WorkerError(WorkerErrorCode.RECONCILIATION_REQUIRED, _exception_label(exc)),
                budget_remaining=remaining,
            )
        return _response_from_dict(result)

    def status(self, request: WorkerRequest) -> WorkerResponse:
        if not isinstance(request, WorkerRequest):
            raise TypeError("request must be a WorkerRequest")
        operation = "s3_attempt" if request.attempt == 1 else "s3_resume"
        try:
            stored, response = self._stored_response(request.operation_key, operation)
        except StoreError as exc:
            return _store_failure(request, exc, "status lookup")
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
        adapter_stop_note = ""
        adapter_stop_state: WorkerState | None = None
        try:
            adapter_stop = self.adapter.stop(request)
            if isinstance(adapter_stop, WorkerResponse):
                adapter_stop_state = adapter_stop.state
                adapter_stop_note = f"; adapter_stop={adapter_stop.state.value}" + (
                    "" if adapter_stop.error is None else f":{adapter_stop.error.code.value}"
                )
            else:
                adapter_stop_note = "; adapter_stop=UNTYPED"
        except Exception as exc:
            cleanup_error_type = _bounded_exception_type(exc)
        if cleanup_error_type is not None:
            cleanup_message = (
                "epoch fenced; adapter.stop raised "
                f"{cleanup_error_type}; worker process cleanup is NOT_VERIFIED"
            )
        elif adapter_stop_state in {WorkerState.FAILED, WorkerState.BLOCKED}:
            cleanup_message = (
                f"epoch fenced; adapter.stop reported {adapter_stop_state.value}; "
                "worker process cleanup is NOT_VERIFIED"
            )
        elif adapter_stop_state is None:
            cleanup_message = (
                "epoch fenced; adapter.stop returned an untyped result; "
                "worker process cleanup is NOT_VERIFIED"
            )
        else:
            cleanup_message = (
                "epoch fenced; adapter.stop completed but worker process cleanup is NOT_VERIFIED"
            )
        return _stop_response(
            request, WorkerState.INCONCLUSIVE,
            WorkerError(WorkerErrorCode.INTERRUPTED, cleanup_message),
            progress=f"new_fence={result['new_epoch']}{adapter_stop_note}",
        )

    def resume(self, request: ResumeRequest, *, probe: dict | None = None) -> WorkerResponse:
        if not isinstance(request, ResumeRequest):
            raise TypeError("request must be a ResumeRequest")
        new_request = request.request
        prior_operation = "s3_attempt" if request.prior_attempt == 1 else "s3_resume"
        resume_payload = self._operation_payload(new_request, request)
        try:
            prior = self.fixture.store.lookup_idempotent_operation(
                request.prior_operation_key, operation=prior_operation
            )
            existing_resume, replay = self._stored_response(
                request.operation_key, "s3_resume", payload=resume_payload
            )
        except StoreError as exc:
            return _store_failure(new_request, exc, "resume lookup")
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
        prior_failed = (
            prior_response.state == WorkerState.FAILED and prior_response.error is not None
            and prior_response.error.code == WorkerErrorCode.EXECUTION_FAILED
        )
        prior_interrupted = (
            prior_response.state == WorkerState.INCONCLUSIVE and prior_response.error is not None
            and prior_response.error.code == WorkerErrorCode.INTERRUPTED
        )
        if not (prior_failed or prior_interrupted):
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNSUPPORTED_STATE,
                "resume requires a recorded application checkpoint or a worker-failed attempt"))
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
        try:
            outcome_result = self.fixture.store.lookup_idempotent_operation(
                outcome_key, operation="s3_attempt_outcome"
            )
        except StoreError as exc:
            return _store_failure(new_request, exc, "outcome lookup")
        if outcome_result is None or outcome_result["state"] != "COMPLETED":
            return _response(new_request, WorkerState.INCONCLUSIVE, error=WorkerError(
                WorkerErrorCode.RECONCILIATION_REQUIRED, "prior app checkpoint is not durably reconciled"))
        recovery = outcome_result["result"]
        if not isinstance(recovery, dict):
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNSUPPORTED_STATE, "prior recovery result is malformed"))
        if prior_failed:
            if (recovery.get("state") != WorkerState.FAILED.value
                    or recovery.get("error_code") != WorkerErrorCode.EXECUTION_FAILED.value
                    or recovery.get("checkpoint") is not None):
                return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                    WorkerErrorCode.UNSUPPORTED_STATE, "prior recovery result does not match the failed attempt"))
        elif recovery.get("checkpoint") not in {
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
        try:
            epoch_already_applied = (
                self._applied_resume_epoch(epoch_operation_key) == new_request.epoch
            )
        except StoreError as exc:
            return _store_failure(new_request, exc, "resume epoch lookup")
        # When this exact resume already advanced the epoch durably, a retry must
        # reach the Store's idempotent replay: the prior-epoch fence and the
        # (possibly consumed) probe no longer describe the current Store state.
        # _execute_attempt still validates the request against the new epoch, and
        # the Store replay rejects any changed payload.
        # The probe signature/attestation is always verified; only the
        # not-yet-seen run/nonce check is skipped on the applied path, because
        # the first call legitimately consumed them.
        if self.fixture.store.sandbox_mode and not self._valid_unconsumed_resume_probe(
            probe, new_request.sandbox_run_id, check_unseen=not epoch_already_applied,
        ):
            return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                WorkerErrorCode.UNAVAILABLE,
                "resume probe signature/attestation is invalid or its run/nonce is not fresh"))
        if not epoch_already_applied:
            # Validate all non-transition request bindings against the current
            # Store state before creating the durable resume binding or advancing
            # the epoch. The actual request already carries the next epoch.
            prior_fence_request = replace(
                new_request, epoch=request.prior_epoch, fence=request.prior_epoch,
            )
            rejected = self._validate_request(prior_fence_request)
            if rejected is not None:
                return _response(new_request, rejected.state, error=rejected.error)
            # Refuse before the durable epoch advance so an exhausted retry cap
            # cannot strand the story with a new owner and no lease.
            try:
                failed_attempts = self.fixture.store.failed_attempts(new_request.task_id)
            except StoreError as exc:
                return _store_failure(new_request, exc, "retry cap lookup")
            if failed_attempts >= int(self.fixture.manifest["retry_cap"]) + 1:
                return _response(new_request, WorkerState.BLOCKED, error=WorkerError(
                    WorkerErrorCode.RETRY_EXHAUSTED, "manifest retry cap reached; no further attempt"))
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
            return _store_failure(new_request, exc, "resume fence")
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
            new_request, "s3_resume", probe=probe, resume_context=request,
            fresh_effect=prior_failed,
        )

    def _applied_resume_epoch(self, epoch_operation_key: str) -> int | None:
        """Epoch of an already-committed epoch_resume operation, else None."""
        stored = self.fixture.store.lookup_idempotent_operation(
            epoch_operation_key, operation="epoch_resume"
        )
        if stored is None or stored["state"] != "COMPLETED":
            return None
        result = stored.get("result")
        epoch = result.get("epoch") if isinstance(result, dict) else None
        return epoch if isinstance(epoch, int) and not isinstance(epoch, bool) else None

    def _valid_unconsumed_resume_probe(
        self, probe: dict | None, run_id: str, *, check_unseen: bool = True,
    ) -> bool:
        """Verify signatures before Store epoch mutation without consuming the probe."""
        if not isinstance(probe, dict):
            return False
        nonce = probe.get("nonce")
        if not isinstance(nonce, str) or not nonce.strip():
            return False
        if check_unseen and (
            run_id in self.supervisor._seen_run_ids
            or nonce in self.supervisor._seen_probe_nonces
        ):
            return False
        # Current preflight API: probes are unsigned in-memory Supervisor
        # observations; there is no probe key and no separate network-policy
        # attestation. validate_fresh_probe checks the exact schema, the
        # run/nonce/spec identity, freshness and the network isolation
        # properties (egress isolated, only "lo", profile hash present).
        # This is a verification gate: any unexpected failure, including an
        # ImportError/AttributeError, fails CLOSED (False -> BLOCKED/UNAVAILABLE).
        try:
            from .preflight import SPEC_PATH, validate_fresh_probe
            spec_sha256 = hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
            return validate_fresh_probe(
                probe, run_id=run_id, spec_sha256=spec_sha256, nonce=nonce,
            ) is True
        except Exception:
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

    def _verify_candidate_commit(
        self, request: WorkerRequest, response: WorkerResponse,
    ) -> WorkerResponse | None:
        """Check a SUCCEEDED claim against the trusted candidate repository.

        The head must be a real commit descending from the trusted candidate
        revision, and everything changed since that revision must stay inside
        allowed_paths. Any failure, timeout or non-zero git status downgrades
        the claim to INCONCLUSIVE; nothing is promoted on a failed check.
        The committed blob at change_path must equal change_content. Fail-closed:
        an adapter other than the HandWritten one is accepted only through the
        injected commit_verifier; without one its SUCCEEDED claim is refused.
        """
        if not isinstance(self.adapter, HandWrittenWorkerAdapter):
            observed = f"observed candidate_head={response.candidate_head}"
            if self.commit_verifier is None:
                return _response(
                    request, WorkerState.INCONCLUSIVE, error=WorkerError(
                        WorkerErrorCode.UNSUPPORTED_STATE,
                        "no commit verifier is configured for this adapter; SUCCEEDED is not promoted"),
                    progress=observed)
            try:
                verdict = self.commit_verifier(request, response)
            except Exception as exc:
                return _response(
                    request, WorkerState.INCONCLUSIVE, error=WorkerError(
                        WorkerErrorCode.RECONCILIATION_REQUIRED,
                        f"commit verifier failed: {_bounded_exception_type(exc)}"),
                    progress=observed)
            if verdict is None or isinstance(verdict, WorkerResponse):
                return verdict
            return _response(
                request, WorkerState.INCONCLUSIVE, error=WorkerError(
                    WorkerErrorCode.UNSUPPORTED_STATE, "commit verifier returned an untyped verdict"),
                progress=observed)
        repository = self.adapter.worker.repository
        head = response.candidate_head
        timeout = min(self.adapter.timeout_sec, request.timeout_sec)

        def refuse(code: WorkerErrorCode, message: str) -> WorkerResponse:
            return _response(
                request, WorkerState.INCONCLUSIVE, error=WorkerError(code, message),
                progress=f"observed candidate_head={head}",
            )

        try:
            if _run_git(repository, ["cat-file", "-e", f"{head}^{{commit}}"], timeout).returncode:
                return refuse(WorkerErrorCode.RECONCILIATION_REQUIRED,
                              "reported candidate head is not a commit in the candidate repository")
            if _run_git(
                repository, ["merge-base", "--is-ancestor", request.candidate_revision, head], timeout,
            ).returncode:
                return refuse(WorkerErrorCode.RECONCILIATION_REQUIRED,
                              "reported candidate head does not descend from the trusted candidate revision")
            diff = _run_git(
                repository,
                ["diff", "--name-only", "-z", "--no-renames", request.candidate_revision, head, "--"],
                timeout,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return refuse(WorkerErrorCode.RECONCILIATION_REQUIRED,
                          f"candidate commit verification failed: {type(exc).__name__}")
        if diff.returncode:
            return refuse(WorkerErrorCode.RECONCILIATION_REQUIRED,
                          "could not list the paths changed by the reported candidate head")
        changed = {item.decode("utf-8", "replace") for item in diff.stdout.split(b"\0") if item}
        if not changed:
            return refuse(WorkerErrorCode.RECONCILIATION_REQUIRED,
                          "candidate head introduces no change relative to the trusted revision")
        if not changed.issubset(set(request.allowed_paths)):
            return refuse(WorkerErrorCode.SCOPE_DENIED,
                          "candidate commit changes paths outside allowed_paths")
        try:
            blob = _run_git(
                repository, ["cat-file", "blob", f"{head}:{request.change_path}"], timeout)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return refuse(WorkerErrorCode.RECONCILIATION_REQUIRED,
                          f"candidate commit verification failed: {type(exc).__name__}")
        if blob.returncode:
            return refuse(WorkerErrorCode.RECONCILIATION_REQUIRED,
                          "could not read the committed change_path blob")
        if blob.stdout != request.change_content.encode("utf-8"):
            return refuse(WorkerErrorCode.RECONCILIATION_REQUIRED,
                          "committed content at change_path differs from the requested change_content")
        return None

    def _validate_response(
        self, request: WorkerRequest, response: WorkerResponse, *, verify: bool = True,
    ) -> WorkerResponse:
        """Validate identity/scope/fence; ``verify=False`` skips the re-runnable
        commit verification so it is never cached inside a stored effect."""
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
            try:
                epoch_now = self.fixture.store.current_epoch(request.story_id)
            except StoreError as exc:
                return _store_failure(request, exc, "epoch lookup")
            if epoch_now != request.fence:
                # Keep the commit the worker reported: the effect may be durable
                # even though the claim can no longer be promoted.
                return _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
                    WorkerErrorCode.FENCE_REJECTED, "epoch changed after worker completion"),
                    progress=f"observed candidate_head={response.candidate_head}")
            if verify:
                verification = self._verify_candidate_commit(request, response)
                if verification is not None:
                    return verification
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


_LEASE_REFUSAL_CODES = {
    "epoch": WorkerErrorCode.FENCE_REJECTED,
    "lease": WorkerErrorCode.RECONCILIATION_REQUIRED,
    "slot": WorkerErrorCode.UNAVAILABLE,
    "retry": WorkerErrorCode.RETRY_EXHAUSTED,
    "terminal": WorkerErrorCode.UNSUPPORTED_STATE,
    "budget": WorkerErrorCode.BUDGET_EXHAUSTED,
}
_INTEGRITY_KINDS = frozenset({"integrity", "chain", "append_only"})
# Lease refusals that can clear on their own (a slot frees up, a live lease is
# released or reaped): returned unpersisted so the operation key stays retryable.
_TRANSIENT_LEASE_KINDS = frozenset({"slot", "lease"})
# Explicit allow-list of Store error kinds that look retryable. Every other kind
# (integrity, chain, append_only, schema, signature, authorization, supervisor,
# manifest, key, lifecycle, epoch, argument, ...) is terminal for the caller:
# BLOCKED and marked "not retryable", never INCONCLUSIVE.
_TRANSIENT_STORE_KINDS = frozenset({"busy", "slot", "lease"})


def _run_git(repository: str, args: list[str], timeout: float) -> subprocess.CompletedProcess:
    """Run one bounded, read-only git command with the hardened child environment."""
    return subprocess.run(
        ["git", *args], cwd=repository, env=build_environment(),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=timeout,
    )


def _exception_label(exc: Exception) -> str:
    """Bounded exception class name plus the StoreError kind, never exception text."""
    name = _bounded_exception_type(exc)
    kind = getattr(exc, "kind", None) if isinstance(exc, StoreError) else None
    if isinstance(kind, str) and kind.isidentifier() and len(kind) <= 32:
        if kind in _INTEGRITY_KINDS:
            suffix = " (integrity; not retryable)"
        elif kind not in _TRANSIENT_STORE_KINDS:
            suffix = " (not retryable)"
        else:
            suffix = ""
        return f"{name}: kind={kind}{suffix}"
    return name


def _store_failure(request: WorkerRequest, exc: StoreError, context: str) -> WorkerResponse:
    """Typed response for a Store failure.

    Only the explicit transient kinds (busy, slot, lease) are INCONCLUSIVE and
    retryable; duplicate is INVALID_REQUEST; every other kind is terminal.
    """
    kind = getattr(exc, "kind", None)
    if kind == "duplicate":
        return _response(request, WorkerState.BLOCKED, error=WorkerError(
            WorkerErrorCode.INVALID_REQUEST,
            f"{context}: idempotency key reused with a different operation or payload"))
    if kind not in _TRANSIENT_STORE_KINDS:
        return _response(request, WorkerState.BLOCKED, error=WorkerError(
            WorkerErrorCode.RECONCILIATION_REQUIRED, f"{context}: {_exception_label(exc)}"))
    return _response(request, WorkerState.INCONCLUSIVE, error=WorkerError(
        WorkerErrorCode.RECONCILIATION_REQUIRED, f"{context}: {_exception_label(exc)}"))


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
