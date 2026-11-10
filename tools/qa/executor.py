"""U3-2: one test-executor interface with two executors (operator decision OD-2: build both, compare).

An executor takes a QA category and an exact candidate head and returns ONE report envelope
(ExecutorReport). Two implementations exist behind the closed registry in get_executor():

    vst-native    tools/qa/executor_native.py  wraps tools.qa.run + tools.qa.gate_check (Windows, per-id)
    aeve-sandbox  tools/qa/executor_aeve.py    wraps `aeve sandbox project-test` (Docker, coarse only)

The envelope never invents data. A field an executor cannot fill is None and is named in
`not_available`; judge() then caps the verdict at COARSE_ONLY, so an executor without per-id
accounting can never be APPROVABLE through id-level rules. Anything that did not run is
NOT_RUN (or BLOCKED/INCONCLUSIVE), never PASS. This module runs no tests and starts no
executor; it only defines the envelope, the verdict rules, the registry and one bounded
child-process helper shared by both executors.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import subprocess
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from tools.qa.registry import ALL_CATEGORIES

EXECUTOR_NATIVE = "vst-native"
EXECUTOR_AEVE = "aeve-sandbox"
EXECUTOR_IDS = (EXECUTOR_NATIVE, EXECUTOR_AEVE)
_EXECUTOR_CLASSES = {
    EXECUTOR_NATIVE: ("tools.qa.executor_native", "NativeExecutor"),
    EXECUTOR_AEVE: ("tools.qa.executor_aeve", "AeveSandboxExecutor"),
}

RESULTS = ("PASS", "FAIL", "INCONCLUSIVE", "BLOCKED", "NOT_RUN")
APPROVABLE = "APPROVABLE"
COARSE_ONLY = "COARSE_ONLY"
NON_APPROVING = "NON_APPROVING"
VERDICTS = (APPROVABLE, COARSE_ONLY, NON_APPROVING)

# Fields that carry per-id accounting. None means NOT_AVAILABLE for this executor.
ID_FIELDS = (
    "expected_ids", "collected_ids", "passed_ids", "skipped_ids", "failed_ids",
    "uncollected_ids", "xfail_ids",
)
# Every field that may legitimately be None because the executor cannot fill it.
NOT_AVAILABLE_FIELDS = ID_FIELDS + ("head_after", "exit_code")

SUPPORTED_CATEGORIES = frozenset(ALL_CATEGORIES)
PASS_THROUGH_ENV = ("PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT")

_HEX_HEAD = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_DIGEST = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Z0-9_]{1,64}\Z")


class ExecutorError(Exception):
    """A typed refusal: the executor did not run, or its output could not be trusted.

    `code` is a stable upper-case machine-readable code; `detail` is a short human text.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        if not _CODE.fullmatch(code):
            raise ValueError("ExecutorError code must match [A-Z0-9_]{1,64}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- canonical JSON / freezing

def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def loads_strict(text: str) -> Any:
    """json.loads that refuses duplicate object keys and non-finite numbers."""

    def refuse_constant(name: str) -> Any:
        raise ValueError(f"non-finite JSON number {name}")

    return json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=refuse_constant)


def freeze(value: Any) -> Any:
    """Recursively read-only copy: dict -> MappingProxyType, list/tuple -> tuple."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


def thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): thaw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw(v) for v in value]
    return value


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(thaw(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- the envelope

@dataclass(frozen=True)
class ExecutorReport:
    """One executor run. id fields are tuples, or None meaning NOT_AVAILABLE for this executor."""

    category: str
    executor_id: str
    expected_head: str                      # the head the caller asked for
    candidate_head: str | None              # the head the executor says it ran
    head_after: str | None
    result: str                             # one of RESULTS
    exit_code: int | None
    expected_ids: tuple[str, ...] | None
    collected_ids: tuple[str, ...] | None
    passed_ids: tuple[str, ...] | None
    skipped_ids: tuple[str, ...] | None
    failed_ids: tuple[str, ...] | None
    uncollected_ids: tuple[str, ...] | None
    xfail_ids: tuple[str, ...] | None
    artifact_digests: Mapping[str, str]
    not_run_reasons: Mapping[str, str]
    not_available: tuple[str, ...]          # exactly the NOT_AVAILABLE_FIELDS that are None
    reasons: tuple[str, ...]                # executor-supplied explanation texts
    native_verdict: str | None              # the executor's own verdict, when it has one (native only)
    native_reason_codes: tuple[str, ...]
    raw_record_sha256: str                  # sha256 of the canonical JSON of raw_record
    raw_record: Mapping[str, Any]           # read-only copy of the executor's raw record


def build_report(
    *,
    category: str,
    executor_id: str,
    expected_head: str,
    candidate_head: str | None,
    head_after: str | None,
    result: str,
    exit_code: int | None,
    ids: Mapping[str, tuple[str, ...] | list[str] | None],
    artifact_digests: Mapping[str, str],
    not_run_reasons: Mapping[str, str],
    reasons: tuple[str, ...] | list[str],
    native_verdict: str | None,
    native_reason_codes: tuple[str, ...] | list[str],
    raw_record: Mapping[str, Any],
) -> ExecutorReport:
    """Assemble and strictly validate a report; not_available and the raw digest are computed here."""
    unknown = set(ids) - set(ID_FIELDS)
    if unknown:
        raise ExecutorError("REPORT_INVALID", f"unknown id field(s): {sorted(unknown)}")
    values = {name: (None if ids.get(name) is None else tuple(ids[name])) for name in ID_FIELDS}
    probe = {"head_after": head_after, "exit_code": exit_code, **values}
    not_available = tuple(name for name in NOT_AVAILABLE_FIELDS if probe[name] is None)
    report = ExecutorReport(
        category=category,
        executor_id=executor_id,
        expected_head=expected_head,
        candidate_head=candidate_head,
        head_after=head_after,
        result=result,
        exit_code=exit_code,
        artifact_digests=MappingProxyType(dict(artifact_digests)),
        not_run_reasons=MappingProxyType(dict(not_run_reasons)),
        not_available=not_available,
        reasons=tuple(reasons),
        native_verdict=native_verdict,
        native_reason_codes=tuple(native_reason_codes),
        raw_record_sha256=canonical_sha256(raw_record),
        raw_record=freeze(raw_record),
        **values,
    )
    validate_report(report)
    return report


def _bad(detail: str) -> ExecutorError:
    return ExecutorError("REPORT_INVALID", detail)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_str_tuple(name: str, value: object, *, allow_none: bool) -> None:
    if value is None:
        if allow_none:
            return
        raise _bad(f"{name} must not be None")
    if not isinstance(value, tuple) or not all(isinstance(item, str) and item for item in value):
        raise _bad(f"{name} must be a tuple of non-empty strings")


def validate_report(report: Any) -> None:
    """Strict structural validation. Raises ExecutorError(REPORT_INVALID); returns None when well-formed.

    Structure only: duplicate ids, failed ids, head mismatches etc. are verdict matters for judge().
    """
    if not isinstance(report, ExecutorReport):
        raise _bad("not an ExecutorReport")
    if report.executor_id not in EXECUTOR_IDS:
        raise _bad("executor_id is not in the closed set")
    if not isinstance(report.category, str) or not report.category:
        raise _bad("category must be a non-empty string")
    if not isinstance(report.expected_head, str) or not _HEX_HEAD.fullmatch(report.expected_head):
        raise _bad("expected_head must be a 40-hex commit id")
    for name in ("candidate_head", "head_after"):
        value = getattr(report, name)
        if value is not None and not (isinstance(value, str) and _HEX_HEAD.fullmatch(value)):
            raise _bad(f"{name} must be None or a 40-hex commit id")
    if report.result not in RESULTS:
        raise _bad(f"result {report.result!r} is not one of {RESULTS}")
    if report.exit_code is not None and not _is_int(report.exit_code):
        raise _bad("exit_code must be None or an int")
    for name in ID_FIELDS:
        _check_str_tuple(name, getattr(report, name), allow_none=True)
    expected_na = tuple(name for name in NOT_AVAILABLE_FIELDS if getattr(report, name) is None)
    if tuple(report.not_available) != expected_na:
        raise _bad(f"not_available {report.not_available!r} differs from the None fields {expected_na!r}")
    if not isinstance(report.artifact_digests, Mapping) or not all(
        isinstance(k, str) and k and isinstance(v, str) and _DIGEST.fullmatch(v)
        for k, v in report.artifact_digests.items()
    ):
        raise _bad("artifact_digests must map names to sha256 digests")
    if not isinstance(report.not_run_reasons, Mapping) or not all(
        isinstance(k, str) and k and isinstance(v, str) for k, v in report.not_run_reasons.items()
    ):
        raise _bad("not_run_reasons must map names to strings")
    _check_str_tuple("reasons", report.reasons, allow_none=False)
    if report.native_verdict is not None and report.native_verdict not in (APPROVABLE, "NON_APPROVING"):
        raise _bad("native_verdict must be None, APPROVABLE or NON_APPROVING")
    if not isinstance(report.native_reason_codes, tuple) or not all(
        isinstance(code, str) and code for code in report.native_reason_codes
    ):
        raise _bad("native_reason_codes must be a tuple of strings")
    if not isinstance(report.raw_record, Mapping) or isinstance(report.raw_record, dict):
        raise _bad("raw_record must be a read-only mapping")
    if not isinstance(report.raw_record_sha256, str) or not _HEX64.fullmatch(report.raw_record_sha256):
        raise _bad("raw_record_sha256 must be a sha256 hex digest")
    if canonical_sha256(report.raw_record) != report.raw_record_sha256:
        raise _bad("raw_record_sha256 does not match raw_record")


# ---------------------------------------------------------------- verdict

def judge(report: ExecutorReport) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Return (verdict, reasons) with verdict in {APPROVABLE, COARSE_ONLY, NON_APPROVING}.

    APPROVABLE only when every per-id field is available, everything expected passed, the head
    never moved and (for the native executor) the native gate agreed. An executor with any id
    field NOT_AVAILABLE can reach COARSE_ONLY at best. Never raises: an invalid report is
    NON_APPROVING with REPORT_INVALID.
    """
    try:
        validate_report(report)
    except ExecutorError as exc:
        return NON_APPROVING, (("REPORT_INVALID", exc.detail),)
    reasons: list[tuple[str, str]] = []

    def fail(code: str, detail: str) -> None:
        reasons.append((code, detail))

    if report.category not in SUPPORTED_CATEGORIES:
        fail("UNSUPPORTED_CATEGORY", f"category {report.category!r} is not a supported QA category")
    if report.result != "PASS":
        fail(f"RESULT_{report.result}", f"result is {report.result}")
    if report.exit_code is None:
        fail("EXIT_MISSING", "no exit code was reported")
    elif report.exit_code != 0:
        fail("EXIT_NONZERO", f"exit code is {report.exit_code}")
    if report.candidate_head is None:
        fail("STALE_HEAD", "the executor reported no candidate head")
    elif report.candidate_head != report.expected_head:
        fail("STALE_HEAD", "candidate head differs from the expected head")
    if report.head_after is None:
        fail("HEAD_AFTER_MISSING", "head after the run is not available")
    elif report.head_after != report.expected_head:
        fail("STALE_HEAD", "HEAD moved during the run or differs from the expected head")

    available = {name: getattr(report, name) for name in ID_FIELDS if getattr(report, name) is not None}
    for name, code in (
        ("failed_ids", "FAILED_IDS"), ("skipped_ids", "SKIPPED_IDS"),
        ("uncollected_ids", "UNCOLLECTED_IDS"), ("xfail_ids", "XFAIL_IDS"),
    ):
        if available.get(name):
            fail(code, f"{name} is not empty ({len(available[name])})")
    for name, value in available.items():
        if len(value) != len(set(value)):
            fail("DUPLICATE_ID", f"{name} holds a duplicate")
    if "expected_ids" in available and "passed_ids" in available:
        expected, passed = set(available["expected_ids"]), set(available["passed_ids"])
        if not expected:
            fail("NO_EXPECTED_IDS", "no expected id was reported")
        if expected - passed:
            fail("NOT_ALL_PASSED", f"{len(expected - passed)} expected id(s) did not pass")
        if passed - expected:
            fail("UNKNOWN_ID", f"{len(passed - expected)} passed id(s) were not expected")

    if report.executor_id == EXECUTOR_NATIVE:
        if report.native_verdict != APPROVABLE:
            fail("NATIVE_NON_APPROVING", f"native gate verdict is {report.native_verdict}")
        if report.not_available:
            fail("NATIVE_FIELDS_MISSING", f"native record lacks {list(report.not_available)}")

    if reasons:
        return NON_APPROVING, tuple(reasons)
    missing_ids = [name for name in ID_FIELDS if name not in available]
    if missing_ids:
        return COARSE_ONLY, (
            ("COARSE_ONLY", f"per-id fields NOT_AVAILABLE for {report.executor_id}: {missing_ids}"),
        )
    return APPROVABLE, ()


# ---------------------------------------------------------------- interface and registry

@runtime_checkable
class TestExecutor(Protocol):
    executor_id: str

    def run(self, category: str, *, repo_root: Any, expected_head: str, **options: Any) -> ExecutorReport:
        """Run one category against the exact expected_head, or raise ExecutorError."""
        ...


def get_executor(executor_id: str, **constructor_options: Any) -> TestExecutor:
    """Closed registry: only the ids in EXECUTOR_IDS resolve; anything else is UNKNOWN_EXECUTOR."""
    target = _EXECUTOR_CLASSES.get(executor_id) if isinstance(executor_id, str) else None
    if target is None:
        raise ExecutorError("UNKNOWN_EXECUTOR", f"executor id must be one of {list(EXECUTOR_IDS)}")
    module = importlib.import_module(target[0])
    executor = getattr(module, target[1])(**constructor_options)
    if executor.executor_id != executor_id:
        raise ExecutorError("EXECUTOR_ID_MISMATCH", "implementation reports a different executor_id")
    return executor


def require_category(category: object) -> str:
    if not isinstance(category, str) or category not in SUPPORTED_CATEGORIES:
        raise ExecutorError("UNSUPPORTED_CATEGORY", f"category must be one of {sorted(SUPPORTED_CATEGORIES)}")
    return category


def require_head(value: object, name: str = "expected_head") -> str:
    if not isinstance(value, str) or not _HEX_HEAD.fullmatch(value):
        raise ExecutorError("HEAD_INVALID", f"{name} must be a lowercase 40-hex commit id")
    return value


def require_options(options: Mapping[str, Any], *, required: tuple[str, ...], optional: tuple[str, ...]) -> None:
    unknown = sorted(set(options) - set(required) - set(optional))
    if unknown:
        raise ExecutorError("UNKNOWN_OPTION", f"unsupported option(s): {unknown}")
    missing = [name for name in required if name not in options]
    if missing:
        raise ExecutorError("MISSING_OPTION", f"required option(s) missing: {missing}")


# ---------------------------------------------------------------- bounded child process

@dataclass(frozen=True)
class ChildResult:
    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool


_TASKKILL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")


def _kill_tree(process: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run([_TASKKILL, "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=15, check=False, shell=False)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        process.kill()
    except OSError:
        pass


def _pump(stream: Any, cap: int, sink: list[bytes], flags: dict[str, bool], key: str) -> None:
    total = 0
    while True:
        chunk = stream.read(65536)
        if not chunk:
            return
        total += len(chunk)
        if total > cap:
            flags[key] = True
            return
        sink.append(chunk)


def run_child(
    argv: list[str], *, cwd: str, env: Mapping[str, str], timeout: float,
    stdout_cap: int, stderr_cap: int,
) -> ChildResult:
    """Run a fixed argv without a shell, bounded by a wall-clock timeout and output caps.

    On timeout or cap breach the whole process tree is killed (taskkill /T /F on Windows).
    Modeled on tools/uc/adapter.py run_review. Raises ExecutorError(EXEC_FAILED) if it cannot start.
    """
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, env=dict(env), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
        )
    except OSError as exc:
        raise ExecutorError("EXEC_FAILED", f"{type(exc).__name__}: {str(exc)[:160]}") from exc
    out: list[bytes] = []
    err: list[bytes] = []
    flags: dict[str, bool] = {}
    threads = [
        threading.Thread(target=_pump, args=(process.stdout, stdout_cap, out, flags, "stdout"), daemon=True),
        threading.Thread(target=_pump, args=(process.stderr, stderr_cap, err, flags, "stderr"), daemon=True),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    timed_out = False
    while process.poll() is None:
        if flags.get("stdout") or flags.get("stderr"):
            _kill_tree(process)
            break
        if time.monotonic() > deadline:
            timed_out = True
            _kill_tree(process)
            break
        time.sleep(0.05)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
    for thread in threads:
        thread.join(timeout=5)
    return ChildResult(
        returncode=process.returncode, stdout=b"".join(out), stderr=b"".join(err),
        timed_out=timed_out, stdout_truncated=bool(flags.get("stdout")),
        stderr_truncated=bool(flags.get("stderr")),
    )
