"""Vendor-neutral, bounded worker protocol for one VST story attempt.

The protocol carries identity and fencing context on every operation. A worker
reports execution state only; receipts, phase transitions, and gate decisions
remain owned by the VST Store and Supervisor.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
MAX_CHANGE_BYTES = 64 * 1024
MAX_PROGRESS_BYTES = 4 * 1024
MAX_EVIDENCE_REFS = 32
MAX_ALLOWED_PATHS = 128
MAX_PATH_BYTES = 512
_GIT_SHORT_NAME = re.compile(r"git~\d+", re.IGNORECASE)


def is_canonical_repo_path(path: object) -> bool:
    """True only for the one accepted form: relative, forward-slash, no aliases.

    Rejects backslashes, control characters (including DEL), empty/dot/dot-dot
    components, any ``:`` (drive letters and NTFS streams), any ``.git``
    component, Windows short-name aliases of it (``GIT~1``) and components that
    end in a dot or a space (silently stripped by Windows).
    """
    if not isinstance(path, str) or not path:
        return False
    try:
        if len(path.encode("utf-8")) > MAX_PATH_BYTES:
            return False
    except UnicodeEncodeError:
        return False
    if "\\" in path or path.startswith("/") or any(
        ord(character) < 32 or ord(character) == 0x7F for character in path
    ):
        return False
    return all(
        part not in {"", ".", ".."} and ":" not in part and part.casefold() != ".git"
        and not part.endswith((".", " ")) and _GIT_SHORT_NAME.fullmatch(part) is None
        for part in path.split("/")
    )


def operation_key_for(operation: str, run_id: str, attempt_id: str) -> str:
    """Derive stable operation keys without exposing unrestricted caller text."""
    if operation not in {"attempt", "stop"}:
        raise ValueError("unsupported worker operation key kind")
    digest = hashlib.sha256(f"{operation}\0{run_id}\0{attempt_id}".encode("utf-8")).hexdigest()[:32]
    return f"s3-{operation}-{digest}"


def effect_key_for(
    run_id: str,
    candidate_id: str,
    candidate_revision: str,
    manifest_sha256: str,
    task_id: str,
    story_id: str,
    base_head: str,
    allowed_paths: tuple[str, ...],
    change_path: str,
    change_content: str,
) -> str:
    """Bind one semantic edit across fenced attempts for safe backend dedupe."""
    payload = [run_id, candidate_id, candidate_revision, manifest_sha256,
               task_id, story_id, base_head, list(allowed_paths), change_path, change_content]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "s3-effect-" + hashlib.sha256(encoded).hexdigest()[:32]


class WorkerState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"


class WorkerErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    SCOPE_DENIED = "SCOPE_DENIED"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    INTERRUPTED = "INTERRUPTED"
    FENCE_REJECTED = "FENCE_REJECTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    UNSUPPORTED_STATE = "UNSUPPORTED_STATE"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"


class Checkpoint(str, Enum):
    BEFORE_EDIT = "before_edit"
    AFTER_EDIT_BEFORE_COMMIT = "after_edit_before_commit"
    AFTER_COMMIT_BEFORE_RESPONSE = "after_commit_before_response"


@dataclass(frozen=True)
class WorkerError:
    code: WorkerErrorCode
    message: str
    retryable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.code, WorkerErrorCode):
            raise ValueError("worker error code must be a WorkerErrorCode")
        if not isinstance(self.message, str) or not self.message.strip() or len(self.message) > 512:
            raise ValueError("worker error message must contain 1..512 characters")
        if type(self.retryable) is not bool:
            raise ValueError("worker error retryable must be a boolean")


@dataclass(frozen=True)
class WorkerRequest:
    """Identity, budget, fence, and one bounded synthetic edit."""

    operation_key: str
    effect_key: str
    run_id: str
    attempt_id: str
    candidate_id: str
    candidate_revision: str
    manifest_sha256: str
    task_id: str
    story_id: str
    attempt: int
    epoch: int
    fence: int
    budget_cap: int
    budget_spent: int
    budget_units: int
    allowed_paths: tuple[str, ...]
    change_path: str
    change_content: str
    invocation_id: str
    sandbox_run_id: str
    base_head: str
    timeout_sec: int = 60

    def __post_init__(self) -> None:
        for field_name in (
            "operation_key", "effect_key", "run_id", "attempt_id", "candidate_id", "task_id",
            "story_id", "invocation_id", "sandbox_run_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
                raise ValueError(f"{field_name} must be a bounded identifier")
        if self.operation_key != operation_key_for("attempt", self.run_id, self.attempt_id):
            raise ValueError("operation_key is not derived from this run and attempt")
        if not isinstance(self.candidate_revision, str) or not _HEX40.fullmatch(self.candidate_revision):
            raise ValueError("candidate_revision must be a lowercase 40-character git id")
        if not isinstance(self.base_head, str) or not _HEX40.fullmatch(self.base_head):
            raise ValueError("base_head must be a lowercase 40-character git id")
        if not isinstance(self.manifest_sha256, str) or not _HEX64.fullmatch(self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
        for field_name in ("attempt", "epoch", "fence", "timeout_sec"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
        if self.fence != self.epoch:
            raise ValueError("fence must equal the Store epoch fencing token")
        for field_name in ("budget_cap", "budget_spent", "budget_units"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.budget_units < 1:
            raise ValueError("a worker start must reserve at least one budget unit")
        if (not isinstance(self.allowed_paths, tuple) or not self.allowed_paths
                or len(self.allowed_paths) > MAX_ALLOWED_PATHS):
            raise ValueError("allowed_paths must contain 1..128 paths")
        if any(not is_canonical_repo_path(path) for path in self.allowed_paths):
            raise ValueError("allowed_paths entries must be canonical relative forward-slash paths")
        if len(set(self.allowed_paths)) != len(self.allowed_paths):
            raise ValueError("allowed_paths entries must be unique")
        if not is_canonical_repo_path(self.change_path) or self.change_path not in self.allowed_paths:
            raise ValueError("change_path must be canonical and included in allowed_paths")
        if not isinstance(self.change_content, str):
            raise ValueError("change_content must be text")
        if len(self.change_content.encode("utf-8")) > MAX_CHANGE_BYTES:
            raise ValueError("change_content exceeds the 64 KiB request limit")
        expected_effect_key = effect_key_for(
            self.run_id, self.candidate_id, self.candidate_revision,
            self.manifest_sha256, self.task_id, self.story_id, self.base_head,
            self.allowed_paths, self.change_path, self.change_content,
        )
        if self.effect_key != expected_effect_key:
            raise ValueError("effect_key does not bind the semantic worker edit")


@dataclass(frozen=True)
class StopRequest:
    """Bound STOP intent; ``authorized_actor`` is audit identity only.

    Authentication of the caller is outside this protocol object and must be
    supplied by the trusted call boundary.
    """

    operation_key: str
    effect_key: str
    run_id: str
    attempt_id: str
    attempt: int
    candidate_id: str
    candidate_revision: str
    manifest_sha256: str
    task_id: str
    story_id: str
    sandbox_run_id: str
    allowed_paths: tuple[str, ...]
    budget_cap: int
    budget_units: int
    budget_remaining: int
    epoch: int
    fence: int
    reason: str
    authorized_actor: str
    invocation_id: str
    timeout_sec: int = 5

    def __post_init__(self) -> None:
        for field_name in (
            "operation_key", "effect_key", "run_id", "attempt_id", "candidate_id",
            "task_id", "story_id", "sandbox_run_id", "authorized_actor", "invocation_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
                raise ValueError(f"{field_name} must be a bounded identifier")
        if not isinstance(self.reason, str) or not self.reason.strip() or len(self.reason) > 512:
            raise ValueError("stop reason must contain 1..512 characters")
        for field_name in ("attempt", "epoch", "fence", "timeout_sec"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
        if self.fence != self.epoch:
            raise ValueError("fence must equal the Store epoch fencing token")
        if self.operation_key != operation_key_for("stop", self.run_id, self.attempt_id):
            raise ValueError("stop operation key is not derived from this run and attempt")
        if not isinstance(self.candidate_revision, str) or not _HEX40.fullmatch(self.candidate_revision):
            raise ValueError("candidate_revision must be a lowercase git id")
        if not isinstance(self.manifest_sha256, str) or not _HEX64.fullmatch(self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
        if (not isinstance(self.allowed_paths, tuple) or not self.allowed_paths
                or len(self.allowed_paths) > MAX_ALLOWED_PATHS
                or any(not is_canonical_repo_path(path) for path in self.allowed_paths)
                or len(set(self.allowed_paths)) != len(self.allowed_paths)):
            raise ValueError("allowed_paths must contain at most 128 unique safe relative paths")
        if isinstance(self.budget_remaining, bool) or not isinstance(self.budget_remaining, int) or self.budget_remaining < 0:
            raise ValueError("budget_remaining must be a non-negative integer")
        for field_name in ("budget_cap", "budget_units"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.budget_units > self.budget_cap:
            raise ValueError("budget_units cannot exceed budget_cap")


@dataclass(frozen=True)
class ResumeRequest:
    operation_key: str
    prior_operation_key: str
    prior_attempt_id: str
    prior_attempt: int
    prior_epoch: int
    request: WorkerRequest
    remaining_budget: int
    prior_receipt_sha256: str | None = None

    def __post_init__(self) -> None:
        for name in ("operation_key", "prior_operation_key", "prior_attempt_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
                raise ValueError(f"{name} must be a bounded identifier")
        if not isinstance(self.request, WorkerRequest):
            raise ValueError("resume request must include a WorkerRequest")
        if isinstance(self.remaining_budget, bool) or not isinstance(self.remaining_budget, int) or self.remaining_budget < 0:
            raise ValueError("remaining_budget must be a non-negative integer")
        if self.prior_receipt_sha256 is not None and (
            not isinstance(self.prior_receipt_sha256, str) or not _HEX64.fullmatch(self.prior_receipt_sha256)
        ):
            raise ValueError("prior_receipt_sha256 must be a lowercase SHA-256 digest")
        if self.operation_key != self.request.operation_key:
            raise ValueError("resume operation key must match the request operation key")
        if self.prior_operation_key != operation_key_for(
            "attempt", self.request.run_id, self.prior_attempt_id
        ):
            raise ValueError("prior_operation_key does not match the prior attempt")
        if isinstance(self.prior_epoch, bool) or not isinstance(self.prior_epoch, int) or self.prior_epoch < 1:
            raise ValueError("prior_epoch must be a positive integer")
        if isinstance(self.prior_attempt, bool) or not isinstance(self.prior_attempt, int) or self.prior_attempt < 1:
            raise ValueError("prior_attempt must be a positive integer")
        if self.request.attempt != self.prior_attempt + 1 or self.request.attempt_id == self.prior_attempt_id:
            raise ValueError("resume requires a new attempt id and attempt number")
        if self.request.epoch <= self.prior_epoch:
            raise ValueError("resume requires a newer Store epoch fence")


@dataclass(frozen=True)
class WorkerResponse:
    run_id: str
    attempt_id: str
    operation_key: str
    effect_key: str
    candidate_id: str
    candidate_revision: str
    manifest_sha256: str
    epoch: int
    fence: int
    invocation_id: str
    sandbox_run_id: str
    state: WorkerState
    progress: str = ""
    evidence_refs: tuple[str, ...] = ()
    candidate_head: str | None = None
    changed_paths: tuple[str, ...] = ()
    checkpoint: Checkpoint | None = None
    error: WorkerError | None = None
    elapsed_ms: int = 0
    budget_remaining: int | None = None
    budget_cap: int = 0
    budget_units: int = 0

    def __post_init__(self) -> None:
        for field_name in ("run_id", "attempt_id", "candidate_id", "invocation_id", "sandbox_run_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
                raise ValueError(f"response {field_name} must be a bounded identifier")
        for field_name in ("operation_key", "effect_key"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
                raise ValueError(f"response {field_name} must be a bounded identifier")
        if not isinstance(self.candidate_revision, str) or not _HEX40.fullmatch(self.candidate_revision):
            raise ValueError("response candidate_revision must be a lowercase git id")
        if not isinstance(self.manifest_sha256, str) or not _HEX64.fullmatch(self.manifest_sha256):
            raise ValueError("response manifest_sha256 must be a lowercase SHA-256 digest")
        for field_name in ("epoch", "fence", "elapsed_ms", "budget_cap", "budget_units"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"response {field_name} must be a non-negative integer")
        if self.budget_remaining is not None and (
            isinstance(self.budget_remaining, bool) or not isinstance(self.budget_remaining, int)
            or self.budget_remaining < 0
        ):
            raise ValueError("response budget_remaining must be a non-negative integer")
        if self.fence != self.epoch or not isinstance(self.state, WorkerState):
            raise ValueError("response requires a typed state and matching Store epoch fence")
        if not isinstance(self.progress, str) or len(self.progress.encode("utf-8")) > MAX_PROGRESS_BYTES:
            raise ValueError("response progress exceeds its 4 KiB bound")
        if (not isinstance(self.evidence_refs, tuple) or len(self.evidence_refs) > MAX_EVIDENCE_REFS
                or any(not isinstance(item, str) or len(item) > 256 for item in self.evidence_refs)):
            raise ValueError("evidence_refs must be a tuple of at most 32 bounded references")
        if (not isinstance(self.changed_paths, tuple)
                or len(self.changed_paths) > MAX_ALLOWED_PATHS
                or any(not is_canonical_repo_path(path) for path in self.changed_paths)):
            raise ValueError("changed_paths must contain at most 128 canonical paths")
        if self.candidate_head is not None and (
            not isinstance(self.candidate_head, str) or not _HEX40.fullmatch(self.candidate_head)
        ):
            raise ValueError("candidate_head must be a lowercase git id")
        if self.checkpoint is not None and not isinstance(self.checkpoint, Checkpoint):
            raise ValueError("checkpoint must be a named Checkpoint")
        if self.error is not None and not isinstance(self.error, WorkerError):
            raise ValueError("error must be a WorkerError")
        if self.state == WorkerState.SUCCEEDED and (self.candidate_head is None or self.error is not None):
            raise ValueError("SUCCEEDED requires a candidate head and no error")
        if self.state != WorkerState.SUCCEEDED and self.candidate_head is not None:
            raise ValueError("only SUCCEEDED may include a candidate head")
        if self.state in {WorkerState.FAILED, WorkerState.STOPPED, WorkerState.INCONCLUSIVE, WorkerState.BLOCKED} and self.error is None:
            raise ValueError("terminal non-success state requires a typed error")


class StoryWorkerAdapter(Protocol):
    """All candidate backends share these operations; none returns a VST verdict."""

    def start(self, request: WorkerRequest) -> WorkerResponse: ...

    def status(self, request: WorkerRequest) -> WorkerResponse: ...

    def stop(self, request: StopRequest) -> WorkerResponse: ...

    def resume(self, request: ResumeRequest) -> WorkerResponse: ...

