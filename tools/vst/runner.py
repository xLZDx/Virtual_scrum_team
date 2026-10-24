"""Runner: executes allowed commands, builds a TestRun receipt and signs it.

The runner is the only component that holds the worker signing key. The key is
a function argument: it is never written to disk, never logged, never placed in
the receipt, never passed to a child process and never looked up in the cwd.

Safety rules enforced BEFORE any process starts (ContractError):
- the manifest is validated and the receipt is bound to it (task_id,
  role_sha256 and manifest_sha256 come from the manifest);
- `slot` must be a TestRun slot of the manifest;
- every argv must EXACTLY equal an `allowed_commands` entry of that slot;
- set(expected_test_ids) must equal the manifest `required_tests` ids of the
  slot, and covered_acceptance must be a subset of manifest acceptance;
- timeouts <= manifest timeout_sec (the retry_cap bound is per epoch and is
  enforced by the store, not here: attempt numbers are global);
- artifact paths are repo-style relative paths (no absolute path, no `..`, no
  drive letter) that stay under the run directory `cwd` and pass through no
  symlink or junction.

Execution (subprocess.Popen, shell=False):
- the child gets a MINIMAL EXPLICIT environment: only the allowlisted names in
  ENV_ALLOWLIST copied from the runner process (PATH, SYSTEMROOT, TEMP ...) plus
  PYTHONIOENCODING and the caller's explicit `extra_env`. No other inherited
  variable (tokens, API keys) reaches the child. stdin is /dev/null.
  `extra_env` is an ALLOWLIST: every name must fully match VST_[A-Z0-9_]+
  (case-sensitive upper case); anything else (PATH, PYTHONPATH, LD_*, DYLD_*,
  lower-case or mixed-case names, ...) is rejected with ContractError (a
  ValueError) before anything runs. FORBIDDEN_ENV_NAMES is kept as
  documentation of the loader/search names that can never match.
- stdout and stderr are captured through reader threads with a hard cap of
  `max_output_bytes` per stream (default 1 MiB); the excess is drained and
  dropped. A command whose output was truncated is recorded with exit code -3
  (EXIT_OUTPUT_TRUNCATED), which makes the derived result FAIL (the parser saw
  partial output). The truncated flag is also available in the optional
  `report` dict.
- process-tree containment. Strict Windows mode creates the process suspended,
  assigns it to a Job Object created with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
  then resumes its primary thread. Assignment or resume failure terminates and
  refuses the command before it executes. On EVERY exit path the runner calls
  TerminateJobObject and then CloseHandle. Non-strict Windows callers retain the
  legacy best-effort taskkill fallback. POSIX: the process group
  (the child is started in its own session) is killed with SIGKILL on timeout
  and after a normal exit. Timeout exit code -1.
- capture completeness: after both pipes were joined, a reader thread that is
  still alive, a read error of any kind (any Exception in the reader), or a root
  process that is still running 10 s after the kill, means the captured output
  may be incomplete. On any exception inside the run (including a failed
  reader-thread start) the whole tree is killed (POSIX process group, Windows
  Job Object / taskkill /T) and the pipes are closed after the readers are
  joined. That command is recorded with exit code -4
  (EXIT_CAPTURE_INCOMPLETE, fail-closed: the derived result is FAIL) and
  report['capture_incomplete'] is True. This takes precedence over -1 and -3.
- `timeout_sec` is the per-command limit; `deadline_sec` is the overall limit
  across all commands (both default to the manifest timeout_sec). A command
  that cannot start before the deadline is recorded as -1 without running.

Exit code conventions recorded in the receipt: the process exit code, -1
timeout / deadline, -2 executable or cwd missing or the process cannot be
started (any OSError), -3 output truncated, -4 output capture incomplete.

Artifacts are hashed AFTER the commands; a missing, non-regular, symlinked or
escaping artifact gets the all-zero digest (FAIL).

Standard library only; no network.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Callable

from .contracts import (
    MISSING_ARTIFACT_DIGEST,
    ContractError,
    _req_hex,
    _req_int,
    _req_str,
    _req_str_list,
    _validate_repo_path,
    canonical_bytes,
    derive_result,
    manifest_sha256,
    validate_receipt,
    validate_task_manifest,
    TRUSTED_PARSER_CATALOG,
)
from .signing import MIN_KEY_BYTES, sign

EXIT_TIMEOUT = -1
EXIT_MISSING_EXECUTABLE = -2
EXIT_OUTPUT_TRUNCATED = -3
EXIT_CAPTURE_INCOMPLETE = -4
DEFAULT_MAX_OUTPUT_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES_LIMIT = 64 * 1024 * 1024
MAX_COUNTER = 2**31 - 1
ENV_ALLOWLIST = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "TEMP",
    "TMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
)
FORBIDDEN_ENV_NAMES = frozenset(
    {
        *ENV_ALLOWLIST,
        "PATH",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONHOME",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
    }
)
FORBIDDEN_ENV_PREFIXES = ("DYLD_",)
# extra_env is an allowlist: only these names reach a child (case-sensitive upper case).
_EXTRA_ENV_NAME = re.compile(r"VST_[A-Z0-9_]+")
_CHUNK = 64 * 1024
_JOIN_SEC = 5.0


def file_sha256(path: str) -> str:
    """sha256 hex of a file, read in 64 KiB chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def artifact_digests(paths: list[str]) -> dict[str, str]:
    """Map every path to the sha256 hex of its content."""
    return {path: file_sha256(path) for path in paths}


def receipt_without_signature(receipt: dict) -> dict:
    """Shallow copy of a receipt without its 'signature' field."""
    return {k: v for k, v in receipt.items() if k != "signature"}


def build_environment(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    """Minimal child environment: allowlisted names + PYTHONIOENCODING + extra_env."""
    env = {name: os.environ[name] for name in ENV_ALLOWLIST if name in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    if extra_env:
        env.update(extra_env)
    return env


# ------------------------------------------------------------- path containment


def _is_link(path: str) -> bool:
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    return bool(isjunction is not None and isjunction(path))


def contained_artifact_path(cwd: str, rel: str) -> str | None:
    """Real path of `rel` under `cwd`, or None if it escapes or crosses a link.

    `rel` must already satisfy contracts._validate_repo_path. Every component
    below cwd is checked for symlinks/junctions and the resolved path must stay
    inside the resolved cwd. A path that does not exist yet is allowed.
    """
    base = os.path.realpath(cwd)
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    current = base
    for part in parts:
        current = os.path.join(current, part)
        if _is_link(current):
            return None
    real = os.path.realpath(current)
    norm_base = os.path.normcase(base)
    norm_real = os.path.normcase(real)
    try:
        if os.path.commonpath([norm_base, norm_real]) != norm_base:
            return None
    except ValueError:
        return None
    return real


def _hash_artifacts(paths: list[str], cwd: str) -> dict[str, str]:
    """sha256 of each artifact under cwd; unreadable/escaping/non-file -> all-zero."""
    digests: dict[str, str] = {}
    for path in paths:
        real = contained_artifact_path(cwd, path)
        if real is None or not os.path.isfile(real):
            digests[path] = MISSING_ARTIFACT_DIGEST
            continue
        try:
            digests[path] = file_sha256(real)
        except OSError:
            digests[path] = MISSING_ARTIFACT_DIGEST
    return digests


# ------------------------------------------------------------------- execution


class _Capture:
    """Reads one pipe in a thread, keeping at most `cap` bytes."""

    def __init__(self, stream, cap: int) -> None:
        self._stream = stream
        self._cap = cap
        self.data = bytearray()
        self.truncated = False
        self.read_error = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            while True:
                chunk = self._stream.read(_CHUNK)
                if not chunk:
                    break
                room = self._cap - len(self.data)
                if room > 0:
                    self.data += chunk[:room]
                if len(chunk) > max(room, 0):
                    self.truncated = True
        except Exception:  # noqa: BLE001 - any reader failure means incomplete output
            self.read_error = True

    def finish(self) -> None:
        self._thread.join(_JOIN_SEC)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    @property
    def incomplete(self) -> bool:
        """True if the reader is still running after the join or a read failed."""
        return self._thread.is_alive() or self.read_error

    def text(self) -> str:
        return bytes(self.data).decode("utf-8", errors="replace")


_CREATE_SUSPENDED = 0x00000004


def _spawn_kwargs(*, suspended: bool = False) -> dict:
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if suspended:
            flags |= _CREATE_SUSPENDED  # documented Win32 creation flag
        return {"creationflags": flags}
    return {"start_new_session": True}


def _taskkill_tree(pid: int) -> None:
    """Windows: taskkill /T /F on pid; every failure is ignored."""
    try:
        root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        exe = os.path.join(root, "System32", "taskkill.exe")
        if not os.path.isfile(exe):
            exe = "taskkill"
        subprocess.run(
            [exe, "/PID", str(pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass


_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_TERMINATE_EXIT_CODE = 1
_WIN_API = None  # lazily built ctypes namespace (Windows only)


def _win_api():
    """Windows only: kernel32 job-object bindings with explicit, 64-bit safe types.

    Built lazily so that importing this module never touches ctypes.wintypes or
    kernel32 on non-Windows platforms. Returns None if the bindings cannot be
    built (the caller then falls back to taskkill).
    """
    global _WIN_API
    if os.name != "nt":
        return None
    if _WIN_API is not None:
        return _WIN_API or None
    try:
        import ctypes
        from ctypes import wintypes

        class _BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),  # ULONG_PTR
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class _ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimits),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        k32.AssignProcessToJobObject.restype = wintypes.BOOL
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k32.TerminateJobObject.restype = wintypes.BOOL
        k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k32.CloseHandle.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        class _ThreadEntry32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
            ]

        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k32.Thread32First.restype = wintypes.BOOL
        k32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ThreadEntry32)]
        k32.Thread32Next.restype = wintypes.BOOL
        k32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ThreadEntry32)]
        k32.OpenThread.restype = wintypes.HANDLE
        k32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k32.ResumeThread.restype = wintypes.DWORD
        k32.ResumeThread.argtypes = [wintypes.HANDLE]
        _WIN_API = type("_WinApi", (), {
            "ctypes": ctypes, "k32": k32, "ExtendedLimits": _ExtendedLimits,
            "ThreadEntry32": _ThreadEntry32})
        return _WIN_API
    except Exception:  # noqa: BLE001 - any binding failure means "no job object"
        _WIN_API = False
        return None


class _JobObject:
    """Windows Job Object that kills every member when terminated or closed.

    Created with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, so even if the runner dies
    the OS kills the whole tree when the last handle closes. Descendants of a
    member are members too, and membership survives the exit of the root, which
    is what taskkill /T cannot do after the root has exited. Strict callers
    create the process suspended, assign it, and resume it only after successful
    assignment. Compatibility callers retain the legacy taskkill fallback.
    """

    def __init__(self, api, handle) -> None:
        self._api = api
        self._handle = handle

    @classmethod
    def attach(cls, proc: subprocess.Popen) -> "_JobObject | None":
        """Create a kill-on-close job and assign `proc` to it, or return None."""
        api = _win_api()
        if api is None:
            return None
        k32 = api.k32
        job = None
        try:
            job = k32.CreateJobObjectW(None, None)
            if not job:
                return None
            limits = api.ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not k32.SetInformationJobObject(
                job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                api.ctypes.byref(limits), api.ctypes.sizeof(limits),
            ):
                raise OSError("SetInformationJobObject failed")
            process_handle = getattr(proc, "_handle", None)
            if process_handle is None or not k32.AssignProcessToJobObject(
                job, int(process_handle)
            ):
                raise OSError("AssignProcessToJobObject failed")
            return cls(api, job)
        except Exception:  # noqa: BLE001 - never let job setup break the run
            if job:
                try:
                    k32.CloseHandle(job)
                except Exception:  # noqa: BLE001
                    pass
            return None

    def terminate_and_close(self) -> None:
        """TerminateJobObject then CloseHandle; idempotent, never raises."""
        handle, self._handle = self._handle, None
        if not handle:
            return
        try:
            self._api.k32.TerminateJobObject(handle, _JOB_TERMINATE_EXIT_CODE)
        except Exception:  # noqa: BLE001
            pass
        try:
            self._api.k32.CloseHandle(handle)
        except Exception:  # noqa: BLE001
            pass


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill the child and all its descendants; never raises."""
    if os.name == "nt":
        _taskkill_tree(proc.pid)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        proc.kill()
    except OSError:
        pass


def _resume_suspended_primary_thread(pid: int) -> bool:
    """Resume a CREATE_SUSPENDED process using documented Win32 APIs.

    The process has not executed user code and cannot create threads yet, so
    its Toolhelp thread snapshot identifies the primary thread without using
    CPython's private Popen handles or undocumented Windows APIs. The pinned
    Python 3.14 subprocess implementation closes the CreateProcess thread
    handle, so public Popen methods cannot resume it directly.
    """
    api = _win_api()
    if api is None:
        return False
    k32 = api.k32
    invalid_handle = api.ctypes.c_void_p(-1).value
    snapshot = k32.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
    if not snapshot or snapshot == invalid_handle:
        return False
    thread = None
    try:
        entry = api.ThreadEntry32()
        entry.dwSize = api.ctypes.sizeof(entry)
        more = bool(k32.Thread32First(snapshot, api.ctypes.byref(entry)))
        while more:
            if entry.th32OwnerProcessID == pid:
                thread = k32.OpenThread(0x0002, False, entry.th32ThreadID)  # THREAD_SUSPEND_RESUME
                break
            more = bool(k32.Thread32Next(snapshot, api.ctypes.byref(entry)))
        if not thread:
            return False
        # The process was created with exactly one suspend count. Any other
        # result means it did not enter the expected state; fail closed.
        return k32.ResumeThread(thread) == 1
    except Exception:  # noqa: BLE001 - strict callers refuse on API failure
        return False
    finally:
        if thread:
            k32.CloseHandle(thread)
        k32.CloseHandle(snapshot)


def _run_one(
    argv: list[str], cwd: str, limit_sec: float, env: dict[str, str], cap: int,
    *, require_job_object: bool = False, worker_uid: int | None = None,
    worker_gid: int | None = None, capture_stream_digests: bool = False,
) -> tuple[int, str, dict]:
    """Run one argv without a shell; return (exit_code, stdout_text, info)."""
    info = {
        "stdout_truncated": False,
        "stderr_truncated": False,
        "timed_out": False,
        "capture_incomplete": False,
        "job_object": False,
    }
    try:
        proc = subprocess.Popen(
            argv,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            bufsize=0,
            **({"user": worker_uid, "group": worker_gid, "extra_groups": ()}
               if worker_uid is not None and worker_gid is not None else {}),
            **_spawn_kwargs(suspended=os.name == "nt" and require_job_object),
        )
    except OSError:
        # Missing executable, missing/invalid cwd, no permission, or any other
        # OS-level failure to start. Non-OSError exceptions propagate.
        return EXIT_MISSING_EXECUTABLE, "", info
    job: _JobObject | None = None
    out: _Capture | None = None
    err: _Capture | None = None
    completed = False
    kill_failed = False
    try:
        # Windows: put the child in a kill-on-close Job Object right away so every
        # descendant dies on any exit path, even after the root has exited. Strict
        # callers refuse to run when assignment fails; compatibility callers retain
        # taskkill fallback and report job_object=False.
        job = _JobObject.attach(proc) if os.name == "nt" else None
        info["job_object"] = job is not None
        if os.name == "nt" and require_job_object and job is None:
            info["job_object_refused"] = True
            _kill_tree(proc)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                kill_failed = True
            completed = True
            # Do not run the requested command without confirmed job containment.
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()
            return EXIT_CAPTURE_INCOMPLETE, "", {**info, "capture_incomplete": True}
        if os.name == "nt" and require_job_object and not _resume_suspended_primary_thread(proc.pid):
            info["job_object_refused"] = True
            if job is not None:
                job.terminate_and_close()
                job = None
            _kill_tree(proc)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                kill_failed = True
            completed = True
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()
            return EXIT_CAPTURE_INCOMPLETE, "", {**info, "capture_incomplete": True}
        out = _Capture(proc.stdout, cap)
        err = _Capture(proc.stderr, cap)
        try:
            proc.wait(timeout=limit_sec)
        except subprocess.TimeoutExpired:
            info["timed_out"] = True
            if job is not None:
                job.terminate_and_close()
            _kill_tree(proc)  # taskkill /T /F fallback (also the no-job path)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                kill_failed = True  # the root survived the kill: output is unreliable
        else:
            if job is not None:
                job.terminate_and_close()
            elif os.name == "nt":
                _taskkill_tree(proc.pid)  # no job: best effort, failures ignored
            else:
                try:  # reap stray members of the process group
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
        completed = True
    finally:
        if job is not None:
            job.terminate_and_close()  # idempotent; covers unexpected exceptions
        if not completed:
            # ANY exception (including a failed reader-thread start): kill the
            # whole tree (process group on POSIX, taskkill /T on Windows).
            _kill_tree(proc)
        for capture in (out, err):
            if capture is not None:
                capture.finish()
        for capture, stream in ((out, proc.stdout), (err, proc.stderr)):
            # Close the pipe only when its reader is gone (never under a live read).
            if stream is not None and (capture is None or not capture.alive):
                try:
                    stream.close()
                except Exception:  # noqa: BLE001
                    pass
    assert out is not None and err is not None
    info["stdout_truncated"] = out.truncated
    info["stderr_truncated"] = err.truncated
    info["capture_incomplete"] = out.incomplete or err.incomplete or kill_failed
    if capture_stream_digests:
        info["stdout_bytes"] = len(out.data)
        info["stdout_sha256"] = hashlib.sha256(out.data).hexdigest()
        info["stderr_bytes"] = len(err.data)
        info["stderr_sha256"] = hashlib.sha256(err.data).hexdigest()
    if info["capture_incomplete"]:
        code = EXIT_CAPTURE_INCOMPLETE
    elif info["timed_out"]:
        code = EXIT_TIMEOUT
    elif out.truncated or err.truncated:
        code = EXIT_OUTPUT_TRUNCATED
    else:
        code = proc.returncode if proc.returncode is not None else EXIT_TIMEOUT
    return code, out.text(), info


# ------------------------------------------------------------------ validation


def _check_commands(commands: object) -> list[list[str]]:
    if not isinstance(commands, list) or not commands:
        raise ContractError("commands: must be a non-empty list")
    for index, argv in enumerate(commands):
        if not isinstance(argv, list) or not argv:
            raise ContractError(f"commands[{index}]: must be a non-empty argv list")
        for part in argv:
            if not isinstance(part, str) or not part:
                raise ContractError(f"commands[{index}]: argv items must be non-empty str")
    return commands


def _check_env(extra_env: object) -> dict[str, str]:
    if extra_env is None:
        return {}
    if not isinstance(extra_env, dict):
        raise ContractError("extra_env: must be a dict of str to str")
    for name, value in extra_env.items():
        if (
            not isinstance(name, str)
            or not name
            or "=" in name
            or "\0" in name
            or not isinstance(value, str)
            or "\0" in value
        ):
            raise ContractError("extra_env: names and values must be valid str")
        if _EXTRA_ENV_NAME.fullmatch(name) is None:
            raise ContractError(
                f"extra_env: name {name!r} is not allowed; only names matching "
                "VST_[A-Z0-9_]+ (upper case) are passed to a child"
            )
    return dict(extra_env)


def _prepare(
    *,
    manifest: object,
    slot: object,
    attempt: object,
    epoch: object,
    candidate_head: object,
    resolved_model: object,
    invocation_id: object,
    runner_id: object,
    key: object,
    commands: object,
    expected_test_ids: object,
    test_result_parser: object,
    covered_acceptance: object,
    artifact_paths: object,
    prev_receipt_sha256: object,
    cwd: object,
    created_at: object,
    timeout_sec: object,
    deadline_sec: object,
    max_output_bytes: object,
    extra_env: object,
) -> tuple[dict, str, list[list[str]], int, int, dict[str, str]]:
    """Validate everything; return (manifest, manifest_hash, argvs, per_cmd, deadline, env)."""
    valid = validate_task_manifest(manifest)
    manifest_hash = manifest_sha256(valid)
    for name, value in (
        ("slot", slot),
        ("resolved_model", resolved_model),
        ("invocation_id", invocation_id),
        ("runner_id", runner_id),
        ("created_at", created_at),
    ):
        _req_str(value, name)
    slot_types = {s["slot"]: s["receipt_type"] for s in valid["required_receipts"]}
    if slot_types.get(slot) != "TestRun":
        raise ContractError(f"slot: {slot!r} is not a TestRun slot of the manifest")
    _req_int(attempt, "attempt", 1, MAX_COUNTER)
    _req_int(epoch, "epoch", 1, MAX_COUNTER)
    # No retry_cap bound here: attempt numbers are global across epochs, so the
    # per-epoch bound (retry_cap + 1 attempts per slot in the current epoch) is
    # enforced by Store.append_receipt, which knows the epoch history.
    _req_hex(candidate_head, "candidate_head", 40)
    if attempt == 1:
        if prev_receipt_sha256 is not None:
            raise ContractError("prev_receipt_sha256: must be null when attempt == 1")
    else:
        _req_hex(prev_receipt_sha256, "prev_receipt_sha256", 64)
    if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES:
        raise ContractError(f"key: must be bytes of length >= {MIN_KEY_BYTES}")
    argvs = _check_commands(commands)
    allowed = [c["argv"] for c in valid["allowed_commands"] if c["slot"] == slot]
    for index, argv in enumerate(argvs):
        if argv not in allowed:
            raise ContractError(f"commands[{index}]: argv is not in allowed_commands for {slot!r}")
    _req_str_list(expected_test_ids, "expected_test_ids", unique=True)
    required_ids = sorted(t["test_id"] for t in valid["required_tests"] if t["slot"] == slot)
    if sorted(expected_test_ids) != required_ids:  # type: ignore[arg-type]
        raise ContractError("expected_test_ids: must equal the manifest required tests of the slot")
    _req_str_list(covered_acceptance, "covered_acceptance")
    for acc in covered_acceptance:  # type: ignore[union-attr]
        if acc not in valid["acceptance"]:
            raise ContractError(f"covered_acceptance: {acc!r} is not in manifest acceptance")
    if not isinstance(cwd, str) or not cwd:
        raise ContractError("cwd: must be a non-empty str")
    _req_str_list(artifact_paths, "artifact_paths", unique=True)
    for path in artifact_paths:  # type: ignore[union-attr]
        _validate_repo_path(path, f"artifact_paths[{path!r}]")
        if contained_artifact_path(cwd, path) is None:
            raise ContractError(
                f"artifact_paths[{path!r}]: escapes the run directory or crosses a symlink"
            )
    limit = valid["timeout_sec"]
    per_command = limit if timeout_sec is None else _req_int(timeout_sec, "timeout_sec", 1, limit)
    deadline = limit if deadline_sec is None else _req_int(deadline_sec, "deadline_sec", 1, limit)
    _req_int(max_output_bytes, "max_output_bytes", 1, MAX_OUTPUT_BYTES_LIMIT)
    if not callable(test_result_parser):
        raise ContractError("test_result_parser: must be callable")
    return valid, manifest_hash, argvs, per_command, deadline, build_environment(_check_env(extra_env))


def run_and_sign(
    *,
    manifest: dict,
    slot: str,
    attempt: int,
    epoch: int,
    candidate_head: str,
    resolved_model: str,
    invocation_id: str,
    runner_id: str,
    key: bytes,
    commands: list[list[str]],
    expected_test_ids: list[str],
    test_result_parser: Callable[[str], tuple[list[str], list[str], list[str]]],
    covered_acceptance: list[str],
    artifact_paths: list[str],
    prev_receipt_sha256: str | None,
    cwd: str,
    created_at: str,
    timeout_sec: int | None = None,
    deadline_sec: int | None = None,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    extra_env: dict[str, str] | None = None,
    report: dict | None = None,
) -> dict:
    """Execute allowed commands, parse test ids, return a signed TestRun receipt.

    The parser receives the joined stdout of all commands and returns
    (executed, skipped, xfail) test ids. The result is always computed with
    contracts.derive_result, never taken from the caller. task_id, role_sha256
    and manifest_sha256 of the receipt come from `manifest`.

    All inputs are validated before any command starts (ContractError); see the
    module docstring for the rules. A missing cwd or executable is not a
    validation error: it is recorded as exit_code -2. artifact_paths (required,
    may be empty) are hashed AFTER the commands ran, resolved against cwd.

    If `report` is a dict it is filled with {"commands": [{"stdout_truncated",
    "stderr_truncated", "timed_out", "capture_incomplete", "job_object",
    "skipped_by_deadline"}, ...], "capture_incomplete": bool}. "job_object" is
    True only if the command ran inside a Windows Job Object (always False on
    POSIX, for commands skipped by the deadline and for -2 start failures).
    """
    valid, manifest_hash, argvs, per_command, deadline_sec_n, env = _prepare(
        manifest=manifest, slot=slot, attempt=attempt, epoch=epoch,
        candidate_head=candidate_head, resolved_model=resolved_model,
        invocation_id=invocation_id, runner_id=runner_id, key=key,
        commands=commands, expected_test_ids=expected_test_ids,
        test_result_parser=test_result_parser, covered_acceptance=covered_acceptance,
        artifact_paths=artifact_paths, prev_receipt_sha256=prev_receipt_sha256,
        cwd=cwd, created_at=created_at, timeout_sec=timeout_sec,
        deadline_sec=deadline_sec, max_output_bytes=max_output_bytes,
        extra_env=extra_env,
    )
    deadline_at = time.monotonic() + deadline_sec_n
    recorded: list[dict] = []
    outputs: list[str] = []
    infos: list[dict] = []
    for argv in argvs:
        remaining = deadline_at - time.monotonic()
        if remaining <= 0:
            recorded.append({"argv": list(argv), "exit_code": EXIT_TIMEOUT})
            outputs.append("")
            infos.append(
                {"stdout_truncated": False, "stderr_truncated": False,
                 "timed_out": False, "capture_incomplete": False,
                 "job_object": False, "skipped_by_deadline": True}
            )
            continue
        exit_code, stdout, info = _run_one(
            list(argv), cwd, min(float(per_command), remaining), env, max_output_bytes,
            require_job_object=True,
        )
        info["skipped_by_deadline"] = False
        recorded.append({"argv": list(argv), "exit_code": exit_code})
        outputs.append(stdout)
        infos.append(info)
    if report is not None:
        report["commands"] = infos
        report["capture_incomplete"] = any(info["capture_incomplete"] for info in infos)

    executed, skipped, xfail = test_result_parser("\n".join(outputs))

    receipt = {
        "receipt_id": f"{valid['task_id']}:{slot}:{attempt}:{invocation_id}",
        "receipt_type": "TestRun",
        "task_id": valid["task_id"],
        "manifest_sha256": manifest_hash,
        "slot": slot,
        "attempt": attempt,
        "prev_receipt_sha256": prev_receipt_sha256,
        "candidate_head": candidate_head,
        "epoch": epoch,
        "runner_id": runner_id,
        "role_sha256": valid["role_sha256"],
        "resolved_model": resolved_model,
        "invocation_id": invocation_id,
        # Placeholder only: derive_result computes FAIL/PASS/INCONCLUSIVE from
        # the evidence for any PASS/FAIL given value.
        "result": "FAIL",
        "created_at": created_at,
        "expected_test_ids": list(expected_test_ids),
        "executed_test_ids": list(executed),
        "skipped_test_ids": list(skipped),
        "xfail_test_ids": list(xfail),
        "commands": recorded,
        "covered_acceptance": list(covered_acceptance),
        "artifact_digests": _hash_artifacts(list(artifact_paths), cwd),
    }
    receipt["result"] = derive_result(receipt)
    receipt["signature"] = sign(receipt_without_signature(receipt), key)
    return validate_receipt(receipt)


def _git_bytes(cwd: str, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
            timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContractError(f"cannot derive repository evidence: {exc}") from exc
    if result.returncode != 0:
        raise ContractError("git evidence command failed")
    return result.stdout


def _derive_head(cwd: str) -> str:
    head = _git_bytes(cwd, "rev-parse", "--verify", "HEAD").decode("ascii", "strict").strip()
    _req_hex(head, "repository HEAD", 40)
    return head


def _diff_paths(
    cwd: str, base_head: str, *, exclude_untracked: set[str] | None = None,
) -> tuple[bytes, list[str], list[tuple[str, str]], list[str]]:
    excluded = set(exclude_untracked or ())
    raw = _git_bytes(cwd, "diff", "--binary", "--find-renames", base_head, "--")
    untracked_raw = _git_bytes(cwd, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    all_untracked = sorted(path for path in untracked_raw.decode("utf-8", "surrogateescape").split("\0") if path)
    if any(not isinstance(path, str) or not path or os.path.isabs(path) or
           ".." in path.replace("\\", "/").split("/") for path in excluded):
        raise ContractError("excluded QA artifact path is invalid")
    untracked = [path for path in all_untracked if path not in excluded]
    for path in untracked:
        full_path = os.path.join(cwd, path)
        if os.path.islink(full_path):
            continue
        if not os.path.isfile(full_path):
            raise ContractError("untracked candidate contains a non-regular filesystem object")
        mode = os.stat(full_path, follow_symlinks=False).st_mode & 0o777
        raw += b"\0VST-UNTRACKED\0" + path.encode("utf-8", "surrogateescape") + b"\0"
        raw += mode.to_bytes(2, "big")
        with open(full_path, "rb") as handle:
            data = handle.read()
        raw += hashlib.sha256(data).digest() + len(data).to_bytes(8, "big") + data
    names = _git_bytes(cwd, "diff", "--name-status", "-z", "--find-renames", base_head, "--")
    fields = names.decode("utf-8", "surrogateescape").split("\0")
    changed: list[str] = list(untracked)
    renames: list[tuple[str, str]] = []
    i = 0
    while i < len(fields) and fields[i]:
        status = fields[i]
        i += 1
        if status.startswith("R") or status.startswith("C"):
            if i + 1 >= len(fields):
                raise ContractError("malformed git rename evidence")
            source, target = fields[i], fields[i + 1]
            i += 2
            changed.append(target)
            renames.append((source, target))
        else:
            if i >= len(fields):
                raise ContractError("malformed git path evidence")
            changed.append(fields[i])
            i += 1
    raw_names = _git_bytes(cwd, "diff", "--raw", "-z", "--find-renames", base_head, "--")
    raw_fields = raw_names.decode("utf-8", "surrogateescape").split("\0")
    symlinks: set[str] = set()
    i = 0
    while i < len(raw_fields) and raw_fields[i]:
        metadata = raw_fields[i].split()
        i += 1
        if len(metadata) < 5 or i >= len(raw_fields):
            raise ContractError("malformed raw git mode evidence")
        first = raw_fields[i]
        i += 1
        second = None
        if metadata[4].startswith(("R", "C")):
            if i >= len(raw_fields):
                raise ContractError("malformed raw git rename evidence")
            second = raw_fields[i]
            i += 1
        if metadata[0].lstrip(":") == "120000" or metadata[1] == "120000":
            symlinks.add(first)
            if second is not None:
                symlinks.add(second)
    symlinks.update(path for path in changed if os.path.islink(os.path.join(cwd, path)))
    return raw, changed, renames, sorted(symlinks)


QA_REPORT_MAX_BYTES = 1024 * 1024
QA_EVENTS_MAX_BYTES = 256 * 1024
QA_REPORT_METADATA_FIELDS = frozenset({
    "category", "dependency_lock_path", "dependency_lock_sha256",
    "interpreter_version", "pytest_version", "runtime_id",
    "category_registry_path", "category_registry_sha256",
    "category_source_head", "coverage_state",
    "stdout_artifact_path", "stderr_artifact_path",
    "seeded_catalog_path", "seeded_catalog_sha256", "seeded_failure_fixtures",
})
QA_CATEGORIES = frozenset({"functional", "integration", "api", "e2e", "seeded-failure"})
_FIXTURE_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_REJECTION_CODE_RE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


def _validate_qa_report_request(
    paths: list[str], cwd: str, slot: str, report_path: str | None,
    events_path: str | None, metadata: dict | None,
) -> None:
    """Validate report inputs before the first manifest command starts."""
    requested = (report_path is not None, events_path is not None, metadata is not None)
    if not any(requested):
        return
    if not all(requested):
        raise ContractError("QA report path, test events path, and metadata must be supplied together")
    for name, path in (("report_artifact_path", report_path), ("test_events_path", events_path)):
        _req_str(path, name)
        _validate_repo_path(path, name)
        if path not in paths:
            raise ContractError(f"{name} must be predeclared in artifact_paths")
        if contained_artifact_path(cwd, path) is None:
            raise ContractError(f"{name} escapes the run directory or crosses a link")
        full_path = os.path.join(cwd, path)
        if os.path.lexists(full_path):
            raise ContractError(f"{name} must not exist before the command starts")
        try:
            tracked = subprocess.run(
                ["git", "ls-files", "--", path], cwd=cwd,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ContractError(f"cannot verify generated QA artifact is untracked: {exc}") from exc
        if tracked.returncode != 0 or tracked.stdout:
            raise ContractError(f"generated QA artifact path must not be tracked: {path}")
        if not os.path.isdir(os.path.dirname(full_path)):
            raise ContractError(f"{name} parent directory must exist before the command starts")
    assert report_path is not None and events_path is not None and metadata is not None
    if not isinstance(metadata, dict) or set(metadata) != QA_REPORT_METADATA_FIELDS:
        raise ContractError("report_metadata has missing or unexpected fields")
    if report_path == events_path:
        raise ContractError("QA report and pytest events paths must be distinct")
    category = _req_str(metadata["category"], "report_metadata.category")
    if category not in QA_CATEGORIES:
        raise ContractError("report_metadata.category is not a primary QA category")
    if category != slot:
        raise ContractError("QA report category must match the manifest TestRun slot")
    if metadata["coverage_state"] not in ("PARTIAL", "COMPLETE"):
        raise ContractError("report_metadata.coverage_state must be PARTIAL or COMPLETE")
    _req_hex(metadata["category_source_head"], "report_metadata.category_source_head", 40)
    for field in ("interpreter_version", "pytest_version", "runtime_id"):
        value = _req_str(metadata[field], f"report_metadata.{field}")
        if len(value) > 128 or any(ord(char) < 32 for char in value):
            raise ContractError(f"report_metadata.{field} is invalid or too long")
    if (metadata["runtime_id"] != "Ubuntu-24.04" or
            metadata["interpreter_version"] != "3.12.3" or
            metadata["pytest_version"] != "7.4.4"):
        raise ContractError("QA report runtime metadata does not match the pinned environment")
    lock_path = _req_str(metadata["dependency_lock_path"], "report_metadata.dependency_lock_path")
    _validate_repo_path(lock_path, "report_metadata.dependency_lock_path")
    if lock_path not in paths:
        raise ContractError("dependency lock must be a predeclared artifact")
    expected_hash = _req_hex(metadata["dependency_lock_sha256"], "report_metadata.dependency_lock_sha256", 64)
    lock_full_path = contained_artifact_path(cwd, lock_path)
    if (lock_full_path is None or not os.path.isfile(lock_full_path) or
            file_sha256(lock_full_path) != expected_hash):
        raise ContractError("dependency lock is missing, unsafe, or has a different hash")
    seeded_catalog_path = _req_str(metadata["seeded_catalog_path"], "report_metadata.seeded_catalog_path")
    _validate_repo_path(seeded_catalog_path, "report_metadata.seeded_catalog_path")
    if seeded_catalog_path not in paths:
        raise ContractError("seeded-failure catalog must be a predeclared artifact")
    seeded_catalog_hash = _req_hex(metadata["seeded_catalog_sha256"], "report_metadata.seeded_catalog_sha256", 64)
    seeded_catalog_full_path = contained_artifact_path(cwd, seeded_catalog_path)
    if (seeded_catalog_full_path is None or not os.path.isfile(seeded_catalog_full_path) or
            file_sha256(seeded_catalog_full_path) != seeded_catalog_hash):
        raise ContractError("seeded-failure catalog is missing, unsafe, or has a different hash")
    try:
        tracked_catalog = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", seeded_catalog_path], cwd=cwd,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=5, check=False,
        )
        with open(seeded_catalog_full_path, "rb") as handle:
            catalog_raw = handle.read(128 * 1024 + 1)
        catalog_value = json.loads(catalog_raw.decode("utf-8"))
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"seeded-failure catalog cannot be validated: {exc}") from exc
    if (tracked_catalog.returncode != 0 or len(catalog_raw) > 128 * 1024 or
            not isinstance(catalog_value, dict) or catalog_value.get("schema_version") != 1):
        raise ContractError("seeded-failure catalog must be bounded, tracked schema version 1")
    if category == "seeded-failure":
        if catalog_value.get("state") != "SUPPORTED" or catalog_value.get("fixtures") != metadata["seeded_failure_fixtures"]:
            raise ContractError("seeded-failure report fixtures differ from the tracked catalog")
    elif metadata["seeded_failure_fixtures"]:
        raise ContractError("non-seeded QA category cannot include seeded-failure observations")
    fixture_rows = metadata["seeded_failure_fixtures"]
    if not isinstance(fixture_rows, list) or len(fixture_rows) > 256:
        raise ContractError("seeded_failure_fixtures must be a bounded list")
    if (category == "seeded-failure") != bool(fixture_rows):
        raise ContractError("seeded-failure report fixtures must match the seeded-failure category")
    fixture_ids: set[str] = set()
    fixture_test_ids: set[str] = set()
    for fixture in fixture_rows:
        if not isinstance(fixture, dict) or set(fixture) != {
            "fixture_id", "input", "input_sha256", "expected_rejection", "test_id",
        }:
            raise ContractError("seeded-failure report fixture has missing or unexpected fields")
        fixture_id = fixture["fixture_id"]
        if not isinstance(fixture_id, str) or not _FIXTURE_ID_RE.fullmatch(fixture_id) or fixture_id in fixture_ids:
            raise ContractError("seeded-failure report fixture ID is invalid or duplicated")
        fixture_ids.add(fixture_id)
        if not isinstance(fixture["input"], dict):
            raise ContractError("seeded-failure fixture input must be a JSON object")
        input_hash = _req_hex(fixture["input_sha256"], "seeded_failure_fixture.input_sha256", 64)
        if hashlib.sha256(canonical_bytes(fixture["input"])).hexdigest() != input_hash:
            raise ContractError("seeded-failure fixture input hash does not match canonical input")
        if (not isinstance(fixture["expected_rejection"], str) or
                not _REJECTION_CODE_RE.fullmatch(fixture["expected_rejection"])):
            raise ContractError("seeded-failure expected rejection code is invalid")
        test_id = _req_str(fixture["test_id"], "seeded_failure_fixture.test_id")
        if "::" not in test_id or len(test_id) > 1024 or test_id in fixture_test_ids:
            raise ContractError("seeded-failure test ID is invalid or duplicated")
        fixture_test_ids.add(test_id)
    registry_path = _req_str(metadata["category_registry_path"], "report_metadata.category_registry_path")
    _validate_repo_path(registry_path, "report_metadata.category_registry_path")
    if registry_path not in paths:
        raise ContractError("category registry must be a predeclared artifact")
    registry_hash = _req_hex(metadata["category_registry_sha256"], "report_metadata.category_registry_sha256", 64)
    registry_full_path = contained_artifact_path(cwd, registry_path)
    if (registry_full_path is None or not os.path.isfile(registry_full_path) or
            file_sha256(registry_full_path) != registry_hash):
        raise ContractError("category registry is missing, unsafe, or has a different hash")
    for name in ("stdout_artifact_path", "stderr_artifact_path"):
        log_path = _req_str(metadata[name], f"report_metadata.{name}")
        _validate_repo_path(log_path, f"report_metadata.{name}")
        if log_path not in paths or log_path in (report_path, events_path):
            raise ContractError(f"{name} must be a distinct predeclared artifact")
        full_log_path = os.path.join(cwd, log_path)
        if contained_artifact_path(cwd, log_path) is None or os.path.lexists(full_log_path):
            raise ContractError(f"{name} is unsafe or already exists")
        try:
            tracked = subprocess.run(
                ["git", "ls-files", "--", log_path], cwd=cwd,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ContractError(f"cannot verify generated QA artifact is untracked: {exc}") from exc
        if tracked.returncode != 0 or tracked.stdout:
            raise ContractError(f"generated QA artifact path must not be tracked: {log_path}")
        if not os.path.isdir(os.path.dirname(full_log_path)):
            raise ContractError(f"{name} parent directory must exist before the command starts")
    qa_paths = [report_path, events_path, metadata["dependency_lock_path"],
                metadata["category_registry_path"], metadata["seeded_catalog_path"],
                metadata["stdout_artifact_path"],
                metadata["stderr_artifact_path"]]
    if len(qa_paths) != len(set(qa_paths)):
        raise ContractError("QA report, events, registry, lock, and stream artifacts must be distinct")


def _git_changed_paths(cwd: str) -> list[str]:
    """Return bounded repository-relative status paths, never environment values."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=cwd,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContractError(f"cannot derive pre-run dirty state: {exc}") from exc
    if result.returncode != 0:
        raise ContractError("cannot derive pre-run dirty state")
    records = result.stdout.split(b"\0")
    if records and records[-1] == b"":
        records.pop()
    if len(records) > 2000:
        raise ContractError("pre-run dirty state exceeds the bounded path count")
    paths = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4 or record[2:3] != b" ":
            raise ContractError("Git returned malformed pre-run dirty state")
        raw_path = record[3:]
        if not raw_path or len(raw_path) > 1024:
            raise ContractError("pre-run dirty path is empty or exceeds the size limit")
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractError("pre-run dirty path is not UTF-8") from exc
        if os.path.isabs(path) or ".." in path.replace("\\", "/").split("/"):
            raise ContractError("pre-run dirty path is not repository-relative")
        path = "".join(char if char.isprintable() else "?" for char in path)
        if record[:2] in (b"R ", b" C", b"RC", b"R") or b"R" in record[:2] or b"C" in record[:2]:
            if index >= len(records):
                raise ContractError("Git rename/copy status is missing its source path")
            source = records[index]
            index += 1
            if not source or len(source) > 1024:
                raise ContractError("Git rename/copy source path is invalid")
            try:
                source_path = source.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ContractError("Git rename/copy source path is not UTF-8") from exc
            if os.path.isabs(source_path) or ".." in source_path.replace("\\", "/").split("/"):
                raise ContractError("Git rename/copy source path is not repository-relative")
            source_path = "".join(char if char.isprintable() else "?" for char in source_path)
            paths.append(source_path.replace("\\", "/"))
        paths.append(path.replace("\\", "/"))
    if len(paths) > 1000:
        raise ContractError("pre-run dirty state exceeds the bounded path count")
    return sorted(set(paths))


def _read_qa_test_events(
    cwd: str, events_path: str | None, artifact_paths: list[str],
    parsed_passed: list[str], parsed_skipped: list[str], parsed_xfail: list[str],
    expected_exit_status: int,
) -> tuple[dict | None, str | None]:
    if events_path is None:
        return None, None
    if events_path not in artifact_paths:
        return None, "EVENT_PATH_NOT_DECLARED"
    full_path = contained_artifact_path(cwd, events_path)
    if full_path is None:
        return None, "EVENT_PATH_INVALID"
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(full_path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            file_stat = os.fstat(handle.fileno())
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size > QA_EVENTS_MAX_BYTES:
                return None, "EVENT_FILE_SIZE_OR_TYPE_INVALID"
            raw = handle.read(QA_EVENTS_MAX_BYTES + 1)
    except OSError:
        return None, "EVENT_FILE_MISSING_OR_UNREADABLE"
    if len(raw) > QA_EVENTS_MAX_BYTES:
        return None, "EVENT_FILE_TOO_LARGE"
    try:
        events = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "EVENT_FILE_MALFORMED"
    expected_keys = {
        "schema_version", "collected_ids", "passed_ids", "skipped_ids",
        "xfail_ids", "failed_ids", "collection_errors", "exit_status",
        "seeded_failure_observations",
    }
    if not isinstance(events, dict) or set(events) != expected_keys or events.get("schema_version") != 2:
        return None, "EVENT_SCHEMA_INVALID"
    id_fields = ("collected_ids", "passed_ids", "skipped_ids", "xfail_ids", "failed_ids")
    ids: dict[str, list[str]] = {}
    for field in id_fields:
        value = events[field]
        if (not isinstance(value, list) or len(value) > 10000 or
                any(not isinstance(item, str) or not item or len(item) > 1024 for item in value) or
                len(value) != len(set(value))):
            return None, "EVENT_TEST_IDS_INVALID"
        ids[field] = value
    errors = events["collection_errors"]
    if (not isinstance(errors, list) or len(errors) > 256 or
            any(not isinstance(item, str) or len(item) > 1024 for item in errors)):
        return None, "EVENT_COLLECTION_ERRORS_INVALID"
    observations = events["seeded_failure_observations"]
    if not isinstance(observations, list) or len(observations) > 256:
        return None, "EVENT_SEEDED_FAILURE_OBSERVATIONS_INVALID"
    seen_fixture_ids: set[str] = set()
    for observation in observations:
        if not isinstance(observation, dict) or set(observation) != {
            "fixture_id", "input_sha256", "expected_rejection",
            "observed_rejection", "test_id",
        }:
            return None, "EVENT_SEEDED_FAILURE_OBSERVATION_SCHEMA_INVALID"
        fixture_id = observation["fixture_id"]
        input_hash = observation["input_sha256"]
        expected = observation["expected_rejection"]
        observed = observation["observed_rejection"]
        test_id = observation["test_id"]
        if (not isinstance(fixture_id, str) or not _FIXTURE_ID_RE.fullmatch(fixture_id) or
                fixture_id in seen_fixture_ids or not isinstance(input_hash, str) or
                not re.fullmatch(r"[0-9a-f]{64}", input_hash) or
                not isinstance(expected, str) or not _REJECTION_CODE_RE.fullmatch(expected) or
                not isinstance(observed, str) or not _REJECTION_CODE_RE.fullmatch(observed) or
                not isinstance(test_id, str) or len(test_id) > 1024 or "::" not in test_id):
            return None, "EVENT_SEEDED_FAILURE_OBSERVATION_INVALID"
        seen_fixture_ids.add(fixture_id)
    status = events["exit_status"]
    if not isinstance(status, int) or isinstance(status, bool) or status < 0:
        return None, "EVENT_EXIT_STATUS_INVALID"
    if status != expected_exit_status:
        return None, "EVENT_AND_COMMAND_EXIT_STATUS_MISMATCH"
    outcome_sets = [set(ids[field]) for field in id_fields[1:]]
    if any(outcome_sets[i] & outcome_sets[j] for i in range(len(outcome_sets)) for j in range(i + 1, len(outcome_sets))):
        return None, "EVENT_OUTCOMES_OVERLAP"
    if set(ids["collected_ids"]) != set().union(*outcome_sets):
        return None, "EVENT_COLLECTION_OUTCOMES_MISMATCH"
    if set(parsed_passed) != set(ids["passed_ids"]):
        return None, "PARSER_AND_EVENT_PASS_IDS_MISMATCH"
    if parsed_skipped or parsed_xfail:
        return None, "PARSER_AND_EVENT_SKIP_IDS_MISMATCH"
    return events, None


def _build_qa_report(
    *, metadata: dict, task_id: str, slot: str, manifest_hash: str,
    candidate_head: str, initial_head: str, changed_paths: list[str],
    commands: list[dict], infos: list[dict], expected_ids: list[str],
    executed_ids: list[str], skipped_ids: list[str], xfail_ids: list[str],
    events: dict | None, event_error: str | None, artifact_paths: list[str],
    report_artifact_path: str, test_events_path: str | None, cwd: str,
    started_at: str, ended_at: str, duration_ms: int,
) -> dict:
    event_collected = [] if events is None else events["collected_ids"]
    event_skipped = [] if events is None else events["skipped_ids"]
    event_xfail = [] if events is None else events["xfail_ids"]
    event_failed = [] if events is None else events["failed_ids"]
    event_errors = [] if events is None else events["collection_errors"]
    observed_fixtures = [] if events is None else events["seeded_failure_observations"]
    expected_fixtures = metadata["seeded_failure_fixtures"]
    if metadata["category"] != "seeded-failure":
        expected_fixtures = []
    expected_by_id = {fixture["fixture_id"]: fixture for fixture in expected_fixtures}
    observed_by_id = {fixture["fixture_id"]: fixture for fixture in observed_fixtures}
    fixture_mismatches = []
    if set(expected_by_id) != set(observed_by_id):
        fixture_mismatches.extend(sorted(set(expected_by_id) ^ set(observed_by_id)))
    for fixture_id in sorted(set(expected_by_id) & set(observed_by_id)):
        expected = expected_by_id[fixture_id]
        observed = observed_by_id[fixture_id]
        if (observed["input_sha256"] != expected["input_sha256"] or
                observed["expected_rejection"] != expected["expected_rejection"] or
                observed["observed_rejection"] != expected["expected_rejection"] or
                observed["test_id"] != expected["test_id"]):
            fixture_mismatches.append(fixture_id)
    seeded_failures_valid = not fixture_mismatches
    expected_set = set(expected_ids)
    collected_set = set(event_collected)
    unexpected = sorted(collected_set - expected_set)
    uncollected = sorted(expected_set - collected_set)
    non_report_paths = [path for path in artifact_paths if path != report_artifact_path]
    external_digests = _hash_artifacts(non_report_paths, cwd)
    command_ok = bool(commands) and all(item["exit_code"] == 0 for item in commands)
    complete = (
        metadata["coverage_state"] == "COMPLETE" and
        events is not None and event_error is None and command_ok and
        initial_head == candidate_head and not event_errors and
        external_digests.get(metadata["dependency_lock_path"]) == metadata["dependency_lock_sha256"] and
        external_digests.get(metadata["category_registry_path"]) == metadata["category_registry_sha256"] and
        external_digests.get(metadata["seeded_catalog_path"]) == metadata["seeded_catalog_sha256"] and
        not event_skipped and not event_xfail and not event_failed and
        not unexpected and not uncollected and set(executed_ids) == expected_set and
        not skipped_ids and not xfail_ids and seeded_failures_valid
    )
    observed_acceptance_failure = bool(
        (commands and not command_ok) or event_failed or event_skipped or event_xfail or
        unexpected or uncollected or skipped_ids or xfail_ids or event_errors
        or not seeded_failures_valid
    )
    # v2 intentionally derives INCONCLUSIVE when no test ID executed at all,
    # even if collection/outcome evidence explains that zero-run condition.
    result = "PASS" if complete else (
        "FAIL" if observed_acceptance_failure and executed_ids else "INCONCLUSIVE"
    )
    report = {
        "schema_version": 1,
        "task_id": task_id,
        "slot": slot,
        "category": metadata["category"],
        "category_coverage_state": metadata["coverage_state"],
        "category_source_head": metadata["category_source_head"],
        "manifest_sha256": manifest_hash,
        "candidate_head": candidate_head,
        "source_head_before": initial_head,
        "dirty_paths_before": changed_paths,
        "environment": {
            "runtime_id": metadata["runtime_id"],
            "interpreter_version": metadata["interpreter_version"],
            "pytest_version": metadata["pytest_version"],
            "dependency_lock_path": metadata["dependency_lock_path"],
            "dependency_lock_sha256": metadata["dependency_lock_sha256"],
            "environment_variable_names": sorted(
                set(build_environment().keys()) | {
                    "VST_QA_EVENTS_PATH", "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                }
            ),
        },
        "category_registry": {
            "path": metadata["category_registry_path"],
            "sha256": metadata["category_registry_sha256"],
        },
        "seeded_failure_catalog": {
            "path": metadata["seeded_catalog_path"],
            "sha256": metadata["seeded_catalog_sha256"],
        },
        "execution": {
            "argv_and_exit_codes": commands,
            "capture": infos,
            "stdout_reference": metadata["stdout_artifact_path"],
            "stderr_reference": metadata["stderr_artifact_path"],
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
        },
        "tests": {
            "expected_ids": expected_ids,
            "collected_ids": event_collected,
            "executed_ids": executed_ids,
            "skipped_ids": event_skipped,
            "xfail_ids": event_xfail,
            "failed_ids": event_failed,
            "unexpected_ids": unexpected,
            "uncollected_ids": uncollected,
            "collection_errors": event_errors,
        },
        "seeded_failures": {
            "fixtures": expected_fixtures,
            "observations": observed_fixtures,
            "mismatched_fixture_ids": sorted(set(fixture_mismatches)),
        },
        "test_events_path": test_events_path,
        "test_events_error": event_error,
        "artifact_digests": external_digests,
        "result": result,
    }
    normalized = dict(report)
    normalized_execution = dict(report["execution"])
    normalized_execution.pop("started_at")
    normalized_execution.pop("ended_at")
    normalized_execution.pop("duration_ms")
    normalized["execution"] = normalized_execution
    report["normalized_sha256"] = hashlib.sha256(canonical_bytes(normalized)).hexdigest()
    return report


def _write_qa_report(cwd: str, relative_path: str, report: dict) -> None:
    full_path = contained_artifact_path(cwd, relative_path)
    if full_path is None:
        raise ContractError("QA report path became unsafe before writing")
    payload = canonical_bytes(report)
    if len(payload) > QA_REPORT_MAX_BYTES:
        raise ContractError("QA report exceeds the bounded report size")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(full_path, flags, 0o600)
    except OSError as exc:
        raise ContractError(f"QA report cannot be created exclusively: {exc}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise ContractError(f"QA report could not be written completely: {exc}") from exc


def _write_stream_reference(cwd: str, relative_path: str, stream: str, infos: list[dict]) -> None:
    if stream not in ("stdout", "stderr"):
        raise ContractError("invalid QA stream reference")
    empty_digest = hashlib.sha256(b"").hexdigest()
    records = [{
        "sha256": info.get(f"{stream}_sha256", empty_digest),
        "captured_bytes": info.get(f"{stream}_bytes", 0),
        "truncated": bool(info.get(f"{stream}_truncated", False)),
        "capture_incomplete": bool(info.get("capture_incomplete", False)),
    } for info in infos]
    _write_qa_report(cwd, relative_path, {"schema_version": 1, "stream": stream, "commands": records})


def run_manifest_commands(
    *, manifest: dict, slot: str, attempt: int, epoch: int, resolved_model: str,
    invocation_id: str, runner_id: str, signer_socket: str, cwd: str,
    worker_uid: int, worker_gid: int,
    created_at: str, prev_receipt_sha256: str | None = None,
    artifact_paths: list[str] | None = None, timeout_sec: int | None = None,
    deadline_sec: int | None = None, max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    extra_env: dict[str, str] | None = None, report: dict | None = None,
    report_artifact_path: str | None = None,
    test_events_path: str | None = None,
    report_metadata: dict | None = None,
) -> dict:
    """Run every manifest-pinned v2 command, derive HEAD, and request signatures.

    The worker does not supply a candidate head, commands, parser callable, or
    signing key. The authenticated signer signs the exact evidence request and
    the separate deterministic diff-gate body.
    """
    from .diffgate import git_diff_evidence
    from .sandbox import (require_distinct_worker_identity,
                          require_runner_can_access_signer,
                          require_worker_cannot_access_signer)
    from .signer import authorize_runner_over_socket, sign_diff_over_socket, sign_over_socket

    valid = validate_task_manifest(manifest)
    if valid.get("contract_version") != 2:
        raise ContractError("run_manifest_commands requires manifest contract v2")
    for name, value in (("slot", slot), ("resolved_model", resolved_model),
                        ("invocation_id", invocation_id), ("runner_id", runner_id),
                        ("created_at", created_at), ("cwd", cwd), ("signer_socket", signer_socket)):
        _req_str(value, name)
    if not os.path.isdir(cwd):
        raise ContractError("cwd must be an existing repository directory")
    if os.name != "posix":
        raise ContractError("v2 worker execution requires a POSIX identity boundary")
    if (not isinstance(worker_uid, int) or isinstance(worker_uid, bool) or worker_uid < 1 or
            not isinstance(worker_gid, int) or isinstance(worker_gid, bool) or worker_gid < 1):
        raise ContractError("worker_uid and worker_gid must be positive POSIX ids")
    require_distinct_worker_identity(worker_uid)
    require_runner_can_access_signer(signer_socket)
    require_worker_cannot_access_signer(signer_socket, worker_uid=worker_uid, worker_gid=worker_gid)
    authorize_runner_over_socket(signer_socket)
    _req_int(attempt, "attempt", 1, MAX_COUNTER)
    _req_int(epoch, "epoch", 1, MAX_COUNTER)
    if prev_receipt_sha256 is not None:
        _req_hex(prev_receipt_sha256, "prev_receipt_sha256", 64)
    if attempt == 1 and prev_receipt_sha256 is not None:
        raise ContractError("prev_receipt_sha256 must be null when attempt == 1")
    slot_types = {entry["slot"]: entry["receipt_type"] for entry in valid["required_receipts"]}
    if slot_types.get(slot) != "TestRun":
        raise ContractError("slot is not a TestRun slot in the manifest")
    manifest_hash = manifest_sha256(valid)
    pinned = [item for item in valid["mandatory_commands"] if item["slot"] == slot]
    if not pinned:
        raise ContractError("manifest has no mandatory commands for this slot")
    if report_artifact_path is not None and len(pinned) != 1:
        raise ContractError("QA event evidence currently requires exactly one pinned pytest command")
    argvs = [item["argv"] for item in pinned]
    required_ids = sorted(item["test_id"] for item in valid["required_tests"] if item["slot"] == slot)
    acceptance = sorted({a for item in valid["required_tests"] if item["slot"] == slot for a in item["acceptance"]})
    limit = valid["timeout_sec"]
    per_command = limit if timeout_sec is None else _req_int(timeout_sec, "timeout_sec", 1, limit)
    deadline = limit if deadline_sec is None else _req_int(deadline_sec, "deadline_sec", 1, limit)
    _req_int(max_output_bytes, "max_output_bytes", 1, MAX_OUTPUT_BYTES_LIMIT)
    paths = [] if artifact_paths is None else artifact_paths
    _req_str_list(paths, "artifact_paths", unique=True)
    for path in paths:
        _validate_repo_path(path, f"artifact_paths[{path!r}]")
        if contained_artifact_path(cwd, path) is None:
            raise ContractError(f"artifact path escapes run directory: {path!r}")
    _validate_qa_report_request(
        paths, cwd, slot, report_artifact_path, test_events_path, report_metadata
    )
    started_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    started_monotonic = time.monotonic()
    initial_head = _derive_head(cwd)
    initial_changed_paths = _git_changed_paths(cwd)
    env = build_environment(_check_env(extra_env))
    if report_artifact_path is not None:
        # The native QA lane pins its plugin set in the tracked manifest.
        # Prevent ambient site-installed pytest entry points from changing
        # discovery or execution outside that manifest.
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    deadline_at = time.monotonic() + deadline
    commands: list[dict] = []
    parser_results: list[dict] = []
    infos: list[dict] = []
    for item in pinned:
        parser_key = (item["parser_id"], item["parser_version"], item["parser_sha256"])
        parser = TRUSTED_PARSER_CATALOG.get(parser_key)
        if parser is None:
            raise ContractError("manifest parser is not present in trusted built-in catalog")
        remaining = deadline_at - time.monotonic()
        if remaining <= 0:
            exit_code, stdout = EXIT_TIMEOUT, ""
            info = {"stdout_truncated": False, "stderr_truncated": False, "timed_out": False,
                    "capture_incomplete": False, "job_object": False, "skipped_by_deadline": True}
        else:
            exit_code, stdout, info = _run_one(
                item["argv"], cwd, min(float(per_command), remaining), env,
                max_output_bytes, require_job_object=True,
                worker_uid=worker_uid, worker_gid=worker_gid,
                capture_stream_digests=report_artifact_path is not None,
            )
            info["skipped_by_deadline"] = False
        parsed = parser(stdout)
        if (not isinstance(parsed, tuple) or len(parsed) != 3 or
                any(not isinstance(group, list) or any(not isinstance(x, str) for x in group) for group in parsed)):
            raise ContractError("trusted parser returned invalid typed results")
        executed, skipped, xfail = parsed
        commands.append({"argv": list(item["argv"]), "exit_code": exit_code})
        parser_results.append({
            "argv": list(item["argv"]), "parser_id": item["parser_id"],
            "parser_version": item["parser_version"], "parser_sha256": item["parser_sha256"],
            "parser_result": {"executed_test_ids": executed, "skipped_test_ids": skipped,
                              "xfail_test_ids": xfail},
        })
        infos.append(info)
    candidate_head = _derive_head(cwd)
    executed_all = [test_id for result in parser_results for test_id in result["parser_result"]["executed_test_ids"]]
    skipped_all = [test_id for result in parser_results for test_id in result["parser_result"]["skipped_test_ids"]]
    xfail_all = [test_id for result in parser_results for test_id in result["parser_result"]["xfail_test_ids"]]
    ended_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    duration_ms = max(0, int((time.monotonic() - started_monotonic) * 1000))
    events, event_error = _read_qa_test_events(
        cwd, test_events_path, paths, executed_all, skipped_all, xfail_all,
        commands[-1]["exit_code"] if commands else EXIT_MISSING_EXECUTABLE,
    )
    if report_artifact_path is not None:
        _write_stream_reference(
            cwd, report_metadata["stdout_artifact_path"], "stdout", infos
        )
        _write_stream_reference(
            cwd, report_metadata["stderr_artifact_path"], "stderr", infos
        )
        qa_report = _build_qa_report(
            metadata=report_metadata or {}, task_id=valid["task_id"], slot=slot,
            manifest_hash=manifest_hash, candidate_head=candidate_head,
            initial_head=initial_head, changed_paths=initial_changed_paths,
            commands=commands, infos=infos, expected_ids=required_ids,
            executed_ids=executed_all, skipped_ids=skipped_all,
            xfail_ids=xfail_all, events=events, event_error=event_error,
            artifact_paths=paths, report_artifact_path=report_artifact_path,
            test_events_path=test_events_path, cwd=cwd, started_at=started_at,
            ended_at=ended_at, duration_ms=duration_ms,
        )
        _write_qa_report(cwd, report_artifact_path, qa_report)
        if event_error is not None or events is None:
            raise ContractError(
                f"QA test events are missing or inconsistent ({event_error}); no receipt signed"
            )
    digests = _hash_artifacts(paths, cwd)
    if report_artifact_path is not None:
        if MISSING_ARTIFACT_DIGEST in digests.values():
            raise ContractError("a predeclared QA artifact is missing or unsafe; no signer request was sent")
        preflight_result = derive_result({
            "receipt_type": "TestRun", "result": "PASS",
            "artifact_digests": digests, "executed_test_ids": executed_all,
            "expected_test_ids": required_ids, "commands": commands,
            "skipped_test_ids": skipped_all, "xfail_test_ids": xfail_all,
        })
        if qa_report["result"] != preflight_result:
            raise ContractError(
                f"QA report result {qa_report['result']} disagrees with v2 evidence result "
                f"{preflight_result}; no signer request was sent"
            )
    generated_qa_artifacts = set()
    if report_artifact_path is not None:
        generated_qa_artifacts = {
            report_artifact_path, test_events_path,
            report_metadata["stdout_artifact_path"],
            report_metadata["stderr_artifact_path"],
        }
    diff_bytes, changed, renames, symlinks = _diff_paths(
        cwd, valid["base_head"], exclude_untracked=generated_qa_artifacts
    )
    diff = git_diff_evidence(cwd, valid, candidate_head, diff_bytes, changed,
                             symlink_paths=symlinks, rename_pairs=renames)
    request_id = uuid.uuid4().hex
    diff["signature"] = sign_diff_over_socket(signer_socket, f"{request_id}:diff", {k: v for k, v in diff.items()})
    request = {
        "request_id": request_id, "task_id": valid["task_id"], "slot": slot,
        "attempt": attempt, "epoch": epoch, "manifest_sha256": manifest_hash,
        "candidate_head": candidate_head, "commands": commands,
        "parser_results": parser_results, "artifact_digests": digests,
    }
    request_sig = sign_over_socket(signer_socket, request)
    receipt = {
        "contract_version": 2,
        "receipt_id": f"{valid['task_id']}:{slot}:{attempt}:{invocation_id}",
        "receipt_type": "TestRun", "task_id": valid["task_id"],
        "manifest_sha256": manifest_hash, "slot": slot, "attempt": attempt,
        "prev_receipt_sha256": prev_receipt_sha256, "candidate_head": candidate_head,
        "epoch": epoch, "runner_id": runner_id, "role_sha256": valid["role_sha256"],
        "resolved_model": resolved_model, "invocation_id": invocation_id,
        "result": "FAIL", "created_at": created_at, "expected_test_ids": required_ids,
        "executed_test_ids": executed_all, "skipped_test_ids": skipped_all,
        "xfail_test_ids": xfail_all, "commands": commands,
        "covered_acceptance": acceptance, "artifact_digests": digests,
        "parser_results": parser_results, "diff_gate": diff,
        "runner_attestation": {"request": request, "signature": request_sig},
        "signature": request_sig,
    }
    receipt["result"] = derive_result(receipt)
    if report is not None:
        report["commands"] = infos
        report["capture_incomplete"] = any(info["capture_incomplete"] for info in infos)
        report["candidate_head"] = candidate_head
        report["diff_gate"] = diff
    return validate_receipt(receipt)
