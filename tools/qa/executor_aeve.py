"""U3-2 executor B: `aeve sandbox project-test` (Docker Desktop, clean exact HEAD) behind the common interface.

AEVE is used exactly as it is (D:\\Repo\\AEVE is read-only here, its ledger is never read). The child is
launched in the style of tools/uc/aeve_probe.py and tools/uc/adapter.py: `python -P -s -B -m aeve ...`,
the minimal environment from aeve_probe.build_child_env (AEVE src on PYTHONPATH, no bytecode, no user
site), a neutral working directory outside the candidate, shell=False, wall-clock bound, output caps and
process-tree kill. The AEVE pin check mirrors tools/uc/router.py: the probed AEVE head and matrix digest
must equal the caller-supplied pin, and the AEVE checkout must have NO tracked changes and NO untracked
source files (a missing count is a refusal). The probe and pin check run BEFORE the profile is read and
again AFTER the child exits.

No mutation run is ever performed or accepted. Before anything starts, the tracked profile is read and
REFUSED unless max_mutants == 0 and mutation_paths == []; a result that nevertheless reports mutations,
or whose profile_sha256 differs from the vetted bytes, is refused too. The envelope carries no per-test
ids: every id field is NOT_AVAILABLE and judge() caps this executor at COARSE_ONLY unconditionally.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from tools.qa.executor import (
    EXECUTOR_AEVE, ExecutorError, ExecutorReport, assert_trusted_git, build_report, loads_strict,
    require_category, require_head, require_options, run_child,
)
from tools.qa.registry import RegistryError, git_head, git_root, safe_git
from tools.uc import aeve_probe

DOCKER_EXE = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"   # hard-coded by AEVE itself
DEFAULT_AEVE_ROOT = Path(r"D:\Repo\AEVE")
PROFILE_SCHEMA = "g4.project_test_profile.v1"
RESULT_SCHEMA = "g4.project_test.v1"
MAX_PROFILE_BYTES = 64 * 1024
MAX_WALL_TIMEOUT_SECONDS = 60
CHILD_GRACE_SECONDS = 180          # image/container setup and cleanup around AEVE's own wall bound
CHILD_STDOUT_CAP = 64 * 1024       # AEVE prints ONE compact JSON line
CHILD_STDERR_CAP = 64 * 1024
CLEANUP_UNCONFIRMED = "container cleanup unconfirmed; inspect Docker for a leftover container"

STATUSES = frozenset({"COMPLETE", "INVALID", "BLOCKED", "TIMEOUT", "CANCELLED", "FAILED", "NEEDS_REVIEW"})
_REQUIRED_KEYS = frozenset({"schema_version", "status", "reason_code", "executed_project_code", "llm_calls"})
_ALLOWED_KEYS = _REQUIRED_KEYS | frozenset({
    "run_id", "source_head", "profile_sha256", "bundle_sha256", "input_sha256", "image_digest",
    "cleanup_state", "baseline_runs", "baseline_exit_codes", "mutation_count", "mutation_counts",
    "output_sha256", "result_sha256", "container_id", "prior_failure_code",
})
_DIGEST_KEYS = ("profile_sha256", "bundle_sha256", "output_sha256", "result_sha256")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE = re.compile(r"(?:sha256:)?([0-9a-f]{64})\Z")
_CODE = re.compile(r"[A-Z0-9_]{1,64}\Z")
_PROFILE_PATH = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@+/-]{0,239}\Z")
_REQUIRED_OPTIONS = ("profile", "aeve_pin")
_OPTIONAL_OPTIONS = ("wall_timeout_seconds",)


# ---------------------------------------------------------------- profile gate (mutation refusal)

def _profile_path(value: Any) -> str:
    if not isinstance(value, str) or not _PROFILE_PATH.fullmatch(value) or "\\" in value or ":" in value:
        raise ExecutorError(
            "PROFILE_INVALID", "profile must be a canonical repository-relative POSIX path starting with [A-Za-z0-9]"
        )
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise ExecutorError("PROFILE_INVALID", "profile path must not contain empty, '.' or '..' parts")
    return value


def check_profile_bytes(raw: bytes) -> dict[str, Any]:
    """Parse the tracked profile strictly; REFUSE (MUTATION_PROFILE_REFUSED) unless it excludes mutation."""
    if len(raw) > MAX_PROFILE_BYTES:
        raise ExecutorError("PROFILE_INVALID", "profile exceeds the size bound")
    try:
        profile = loads_strict(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError, MemoryError):
        raise ExecutorError("PROFILE_INVALID", "profile is not strict UTF-8 JSON") from None
    if not isinstance(profile, dict) or profile.get("schema_version") != PROFILE_SCHEMA:
        raise ExecutorError("PROFILE_INVALID", f"profile schema_version must be {PROFILE_SCHEMA}")
    max_mutants, mutation_paths = profile.get("max_mutants"), profile.get("mutation_paths")
    if isinstance(max_mutants, bool) or max_mutants != 0 or mutation_paths != []:
        raise ExecutorError(
            "MUTATION_PROFILE_REFUSED",
            "profile must have max_mutants == 0 and mutation_paths == [] (mutation runs are forbidden)",
        )
    return profile


def _read_profile(root: Path, relative: str) -> bytes:
    path = root.joinpath(*relative.split("/"))
    try:
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)() or not path.is_file():
            raise ExecutorError("PROFILE_INVALID", "profile is not a regular file in the worktree")
        if path.stat().st_size > MAX_PROFILE_BYTES:
            raise ExecutorError("PROFILE_INVALID", "profile exceeds the size bound")
        raw = path.read_bytes()
    except OSError:
        raise ExecutorError("PROFILE_INVALID", "profile could not be read") from None
    try:
        tracked = safe_git(root, "ls-files", "--error-unmatch", "--", relative)
        dirty = safe_git(root, "status", "--porcelain", "--", relative)
    except RegistryError:
        raise ExecutorError("PROFILE_NOT_TRACKED", "profile is not a tracked file of the candidate") from None
    if not tracked.strip() or dirty.strip():
        raise ExecutorError("PROFILE_NOT_TRACKED", "profile is untracked or differs from the committed content")
    return raw


# ---------------------------------------------------------------- AEVE pin (mirrors tools/uc/router.py)

def check_aeve_pin(record: dict[str, Any], pin: dict[str, Any]) -> None:
    """Same rules as router.py: head and matrix digest equal the pin; no tracked changes; no untracked
    source files; a missing count is a refusal."""
    if pin["head"] != record.get("aeve_head") or pin["matrix_digest_sha256"] != (record.get("matrix") or {}).get(
        "digest_sha256"
    ):
        raise ExecutorError("AEVE_PIN_MISMATCH", "AEVE head or matrix digest differs from the supplied pin")
    tracked, untracked = record.get("tracked_dirty_paths"), record.get("untracked_source_paths")
    if (
        isinstance(tracked, bool) or not isinstance(tracked, int) or tracked != 0
        or isinstance(untracked, bool) or not isinstance(untracked, int) or untracked != 0
    ):
        raise ExecutorError(
            "AEVE_CHECKOUT_DIRTY", "the AEVE checkout has tracked changes or untracked source files (or counts are missing)"
        )


def _probe_and_check(aeve_root: Path, python: str, pin: dict[str, Any]) -> None:
    try:
        record = aeve_probe.probe(aeve_root, python=python)
    except aeve_probe.AeveProbeError as exc:
        raise ExecutorError("AEVE_PROBE_FAILED", f"{exc.reason}: {exc.detail}"[:200]) from None
    check_aeve_pin(record, pin)


# ---------------------------------------------------------------- envelope parsing and mapping

def parse_envelope(stdout: bytes) -> dict[str, Any]:
    """Strictly parse the single JSON line AEVE prints. Unknown or duplicate keys are refused."""
    if b"\x00" in stdout:
        raise ExecutorError("AEVE_BAD_OUTPUT", "NUL byte in output")
    try:
        lines = [line for line in stdout.decode("utf-8").splitlines() if line.strip()]
        if len(lines) != 1:
            raise ValueError("expected exactly one JSON line")
        envelope = loads_strict(lines[0])
    except (UnicodeError, ValueError, RecursionError, MemoryError):
        raise ExecutorError("AEVE_BAD_OUTPUT", "output is not exactly one strict JSON line") from None
    if not isinstance(envelope, dict):
        raise ExecutorError("AEVE_BAD_OUTPUT", "output is not a JSON object")
    unknown, missing = set(envelope) - _ALLOWED_KEYS, _REQUIRED_KEYS - set(envelope)
    if unknown or missing:
        raise ExecutorError(
            "AEVE_CONTRACT_VIOLATION", f"unknown keys {sorted(unknown)[:4]} or missing keys {sorted(missing)}"
        )
    return envelope


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_envelope(envelope: dict[str, Any]) -> None:
    def violation(detail: str) -> ExecutorError:
        return ExecutorError("AEVE_CONTRACT_VIOLATION", detail)

    if envelope["schema_version"] != RESULT_SCHEMA:
        raise violation(f"schema_version must be {RESULT_SCHEMA}")
    if not isinstance(envelope["status"], str) or envelope["status"] not in STATUSES:
        raise violation("unknown status")
    if not isinstance(envelope["reason_code"], str) or not _CODE.fullmatch(envelope["reason_code"]):
        raise violation("reason_code is not a well-formed code")
    if not _is_int(envelope["llm_calls"]) or envelope["llm_calls"] != 0:
        raise violation("llm_calls must be exactly 0")
    if not isinstance(envelope["executed_project_code"], bool):
        raise violation("executed_project_code is not a boolean")
    head = envelope.get("source_head")
    if head is not None and not (isinstance(head, str) and _HEX40.fullmatch(head)):
        raise violation("source_head is not a commit id")
    for key in _DIGEST_KEYS:
        value = envelope.get(key)
        if value is not None and not isinstance(value, str):
            raise violation(f"{key} is not a string")
    image = envelope.get("image_digest")
    if image is not None and (not isinstance(image, str) or not 0 < len(image) <= 200):
        raise violation("image_digest is not a bounded string")
    cleanup = envelope.get("cleanup_state")
    if cleanup is not None and not (isinstance(cleanup, str) and _CODE.fullmatch(cleanup)):
        raise violation("cleanup_state is not a well-formed code")
    runs = envelope.get("baseline_runs")
    if runs is not None and (not _is_int(runs) or runs < 0):
        raise violation("baseline_runs is not a non-negative int")
    codes = envelope.get("baseline_exit_codes")
    if codes is not None and not (
        isinstance(codes, list) and all(isinstance(run, list) and all(_is_int(c) for c in run) for run in codes)
    ):
        raise violation("baseline_exit_codes is not a list of int lists")
    count = envelope.get("mutation_count")
    counts = envelope.get("mutation_counts")
    if count is not None and not _is_int(count):
        raise violation("mutation_count is not an int")
    if counts is not None and not (isinstance(counts, dict) and all(_is_int(v) for v in counts.values())):
        raise violation("mutation_counts is not a map of ints")
    if (count or 0) != 0 or any(v != 0 for v in (counts or {}).values()):
        raise ExecutorError("MUTATION_REPORTED", "AEVE reports mutation activity; mutation runs are forbidden")


def report_from_envelope(
    envelope: dict[str, Any], *, category: str, expected_head: str, returncode: int,
    head_after: str | None, profile_sha256: str | None, profile: str | None = None,
) -> ExecutorReport:
    """Pure mapping of a parsed AEVE envelope to ExecutorReport (no I/O, runs nothing)."""
    _validate_envelope(envelope)
    status, reason = envelope["status"], envelope["reason_code"]
    source_head = envelope.get("source_head")
    if source_head is not None and source_head != expected_head:
        raise ExecutorError("STALE_HEAD", "AEVE source_head differs from expected_head")
    # Whatever the status, a profile hash AEVE reports must be the hash of the profile vetted for mutation exclusion.
    if envelope.get("profile_sha256") is not None and envelope["profile_sha256"] != profile_sha256:
        raise ExecutorError("PROFILE_HASH_MISMATCH", "AEVE reports a profile hash different from the vetted profile")
    if returncode == 0 and status != "COMPLETE":
        raise ExecutorError("AEVE_CONTRACT_VIOLATION", f"exit 0 with status {status}")
    notes: list[str] = [f"AEVE status {status}, reason {reason}"]
    image = envelope.get("image_digest")
    image_match = _IMAGE.fullmatch(image) if isinstance(image, str) else None

    if status == "COMPLETE":
        if envelope["executed_project_code"] is not True or source_head is None:
            raise ExecutorError("AEVE_CONTRACT_VIOLATION", "COMPLETE without executed project code or source_head")
        codes = envelope.get("baseline_exit_codes") or []
        runs = envelope.get("baseline_runs")
        if any(c != 0 for run in codes for c in run):
            result = "FAIL"
            notes.append("a baseline run exited non-zero")
        else:
            problems: list[str] = []
            if not codes or runs != len(codes) or any(not run for run in codes):
                problems.append("baseline exit codes are missing or incomplete")
            if returncode != 0:
                problems.append(f"CLI exit {returncode} disagrees with COMPLETE and clean baseline")
            if envelope.get("cleanup_state") != "AUTO_REMOVED":
                problems.append("container cleanup is not confirmed AUTO_REMOVED")
            if any(not (isinstance(envelope.get(k), str) and _HEX64.fullmatch(envelope[k])) for k in _DIGEST_KEYS):
                problems.append("result digests are missing or malformed")
            if image_match is None:
                problems.append("image digest is missing or not sha256:<64 hex>")
            if profile_sha256 is None or envelope.get("profile_sha256") != profile_sha256:
                problems.append("profile_sha256 is absent or differs from the profile vetted for mutation exclusion")
            if head_after != expected_head:
                problems.append("HEAD after the run is not the expected head")
            if problems:
                result = "INCONCLUSIVE"
                notes.extend(problems)
            else:
                result = "PASS"
                notes.append("coarse result: tracked-profile baseline passed; per-id accounting is NOT_AVAILABLE")
    elif status == "INVALID":
        result = "NOT_RUN"
    elif status == "BLOCKED":
        result = "BLOCKED"
    elif status in ("TIMEOUT", "CANCELLED"):
        result = "INCONCLUSIVE"
    elif status == "FAILED":
        result = "FAIL" if envelope["executed_project_code"] else "BLOCKED"
    else:  # NEEDS_REVIEW
        result = "FAIL" if reason == "BASELINE_FAILED" else "INCONCLUSIVE"

    digests = {
        key: envelope[key] for key in _DIGEST_KEYS
        if isinstance(envelope.get(key), str) and _HEX64.fullmatch(envelope[key])
    }
    if image_match is not None:
        digests["image_digest"] = image_match.group(1)    # the sha256: prefix is stripped
    return build_report(
        category=category, executor_id=EXECUTOR_AEVE, expected_head=expected_head,
        candidate_head=source_head, head_after=head_after, result=result, exit_code=returncode,
        ids={},  # every per-id field is NOT_AVAILABLE
        artifact_digests=digests,
        not_run_reasons={} if result == "PASS" else {"project-test": reason},
        reasons=notes, native_verdict=None, native_reason_codes=(), raw_record=envelope,
        profile=profile, candidate_attested=False,
    )


# ---------------------------------------------------------------- the executor

class AeveSandboxExecutor:
    """Executor B (`aeve-sandbox`): coarse only; id fields are NOT_AVAILABLE and the verdict ceiling is COARSE_ONLY."""

    executor_id = EXECUTOR_AEVE

    def __init__(self, *, aeve_root: Path | str | None = None, python: str | None = None) -> None:
        self._aeve_root = Path(aeve_root) if aeve_root is not None else DEFAULT_AEVE_ROOT
        self._python = python or sys.executable

    def run(self, category: str, *, repo_root: Any, expected_head: str, **options: Any) -> ExecutorReport:
        """Options: profile (repo-relative tracked JSON path) and aeve_pin ({"head", "matrix_digest_sha256"})
        are required; wall_timeout_seconds is optional (1..60, default 60)."""
        category = require_category(category)
        expected_head = require_head(expected_head)
        require_options(options, required=_REQUIRED_OPTIONS, optional=_OPTIONAL_OPTIONS)
        relative = _profile_path(options["profile"])
        wall = options.get("wall_timeout_seconds", MAX_WALL_TIMEOUT_SECONDS)
        if isinstance(wall, bool) or not isinstance(wall, int) or not 1 <= wall <= MAX_WALL_TIMEOUT_SECONDS:
            raise ExecutorError("OPTION_INVALID", f"wall_timeout_seconds must be an int in 1..{MAX_WALL_TIMEOUT_SECONDS}")
        pin = options["aeve_pin"]
        if not isinstance(pin, dict) or not isinstance(pin.get("head"), str) \
                or not isinstance(pin.get("matrix_digest_sha256"), str):
            raise ExecutorError("AEVE_PIN_REQUIRED", "aeve_pin needs 'head' and 'matrix_digest_sha256'")

        if os.name != "nt":
            raise ExecutorError("PLATFORM_UNSUPPORTED", "Docker Desktop at the fixed Windows path is required")
        if not os.path.isfile(DOCKER_EXE):
            raise ExecutorError("DOCKER_CLI_MISSING", "Docker Desktop CLI is absent at the fixed path")
        try:
            root = git_root(repo_root)
            if root != Path(repo_root).resolve(strict=True):
                raise ExecutorError("NOT_REPO_ROOT", "repo_root must be the repository root")
            assert_trusted_git(root)
            if git_head(root) != expected_head:
                raise ExecutorError("STALE_HEAD", "repository HEAD differs from expected_head; nothing was run")
        except RegistryError as exc:
            raise ExecutorError("REPO_UNUSABLE", str(exc)[:200]) from None

        # 1. AEVE identity and pin first, before any candidate content is read.
        _probe_and_check(self._aeve_root, self._python, pin)

        # 2. Mutation exclusion is decided from the exact profile bytes AEVE will read, before any launch.
        raw_profile = _read_profile(root, relative)
        check_profile_bytes(raw_profile)
        profile_sha256 = hashlib.sha256(raw_profile).hexdigest()

        argv = [
            self._python, "-P", "-s", "-B", "-m", "aeve", "sandbox", "project-test",
            "--root", os.fspath(root), "--profile", relative, "--wall-timeout-seconds", str(wall),
        ]
        try:
            if git_head(root) != expected_head:       # immediately before launch
                raise ExecutorError("STALE_HEAD", "HEAD moved before launch; nothing was run")
        except RegistryError as exc:
            raise ExecutorError("REPO_UNUSABLE", str(exc)[:200]) from None
        with tempfile.TemporaryDirectory(prefix="vst-aeve-exec-", ignore_cleanup_errors=True) as private:
            env = aeve_probe.build_child_env(self._aeve_root.resolve())
            env["LOCALAPPDATA"] = private      # same private state location as tools/uc/adapter.py
            env["APPDATA"] = private
            child = run_child(
                argv, cwd=private, env=env, timeout=wall + CHILD_GRACE_SECONDS,
                stdout_cap=CHILD_STDOUT_CAP, stderr_cap=CHILD_STDERR_CAP,
            )
        if child.timed_out:
            raise ExecutorError("AEVE_CHILD_TIMEOUT", f"AEVE exceeded its outer bound; process tree killed; {CLEANUP_UNCONFIRMED}")
        if child.output_incomplete:
            raise ExecutorError("AEVE_OUTPUT_TOO_LARGE", f"AEVE output was truncated or incomplete; {CLEANUP_UNCONFIRMED}")
        if child.returncode is None:
            raise ExecutorError("AEVE_NO_EXIT", f"AEVE exit status is unknown; {CLEANUP_UNCONFIRMED}")

        # 3. Re-check AEVE identity/cleanliness and the candidate HEAD after the run.
        _probe_and_check(self._aeve_root, self._python, pin)
        try:
            head_after = git_head(root)
        except RegistryError:
            head_after = None
        envelope = parse_envelope(child.stdout)
        return report_from_envelope(
            envelope, category=category, expected_head=expected_head, returncode=child.returncode,
            head_after=head_after, profile_sha256=profile_sha256, profile=relative,
        )
