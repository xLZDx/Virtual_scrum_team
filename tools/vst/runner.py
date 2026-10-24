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
- process-tree containment. Windows: right after Popen the child is assigned to
  a Job Object created with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (ctypes, stdlib
  only). On EVERY exit path (normal exit, timeout/deadline, output cap, any
  exception) the runner calls TerminateJobObject and then CloseHandle, so all
  descendants die even after the root process has exited (taskkill /T cannot do
  that: the root pid is gone). Known tiny race: the child is not created
  suspended, so a grandchild spawned before the assignment is not a member. If
  the assignment fails (e.g. the process already belongs to a non-nestable job)
  the runner falls back to taskkill /PID <pid> /T /F (failures ignored; best
  effort once the root exited) and reports job_object=False. On timeout
  taskkill /T /F is always run as an extra fallback. POSIX: the process group
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
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from typing import Callable

from .contracts import (
    MISSING_ARTIFACT_DIGEST,
    ContractError,
    _req_hex,
    _req_int,
    _req_str,
    _req_str_list,
    _validate_repo_path,
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


def _spawn_kwargs() -> dict:
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
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
        _WIN_API = type("_WinApi", (), {
            "ctypes": ctypes, "k32": k32, "ExtendedLimits": _ExtendedLimits})
        return _WIN_API
    except Exception:  # noqa: BLE001 - any binding failure means "no job object"
        _WIN_API = False
        return None


class _JobObject:
    """Windows Job Object that kills every member when terminated or closed.

    Created with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, so even if the runner dies
    the OS kills the whole tree when the last handle closes. Descendants of a
    member are members too, and membership survives the exit of the root, which
    is what taskkill /T cannot do after the root has exited. Known tiny race:
    the child is assigned right after Popen (no CREATE_SUSPENDED), so a
    grandchild spawned in that window would not be a member. Strict callers
    terminate and refuse the command when assignment fails (including when a
    parent job does not support nesting); compatibility callers may use the
    legacy taskkill fallback.
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


def _run_one(
    argv: list[str], cwd: str, limit_sec: float, env: dict[str, str], cap: int,
    *, require_job_object: bool = False, worker_uid: int | None = None,
    worker_gid: int | None = None,
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
            **_spawn_kwargs(),
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


def _diff_paths(cwd: str, base_head: str) -> tuple[bytes, list[str], list[tuple[str, str]], list[str]]:
    raw = _git_bytes(cwd, "diff", "--binary", "--find-renames", base_head, "--")
    untracked_raw = _git_bytes(cwd, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    untracked = sorted(path for path in untracked_raw.decode("utf-8", "surrogateescape").split("\0") if path)
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


def run_manifest_commands(
    *, manifest: dict, slot: str, attempt: int, epoch: int, resolved_model: str,
    invocation_id: str, runner_id: str, signer_socket: str, cwd: str,
    worker_uid: int, worker_gid: int,
    created_at: str, prev_receipt_sha256: str | None = None,
    artifact_paths: list[str] | None = None, timeout_sec: int | None = None,
    deadline_sec: int | None = None, max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    extra_env: dict[str, str] | None = None, report: dict | None = None,
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
    env = build_environment(_check_env(extra_env))
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
    digests = _hash_artifacts(paths, cwd)
    diff_bytes, changed, renames, symlinks = _diff_paths(cwd, valid["base_head"])
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
