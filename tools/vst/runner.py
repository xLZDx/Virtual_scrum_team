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
- attempt <= retry_cap + 1; timeouts <= manifest timeout_sec;
- artifact paths are repo-style relative paths (no absolute path, no `..`, no
  drive letter) that stay under the run directory `cwd` and pass through no
  symlink or junction.

Execution (subprocess.Popen, shell=False):
- the child gets a MINIMAL EXPLICIT environment: only the allowlisted names in
  ENV_ALLOWLIST copied from the runner process (PATH, SYSTEMROOT, TEMP ...) plus
  PYTHONIOENCODING and the caller's explicit `extra_env`. No other inherited
  variable (tokens, API keys) reaches the child. stdin is /dev/null.
- stdout and stderr are captured through reader threads with a hard cap of
  `max_output_bytes` per stream (default 1 MiB); the excess is drained and
  dropped. A command whose output was truncated is recorded with exit code -3
  (EXIT_OUTPUT_TRUNCATED), which makes the derived result FAIL (the parser saw
  partial output). The truncated flag is also available in the optional
  `report` dict.
- on timeout the WHOLE process tree is killed (Windows: taskkill /T /F; POSIX:
  the process group, the child is started in its own session). Exit code -1.
- `timeout_sec` is the per-command limit; `deadline_sec` is the overall limit
  across all commands (both default to the manifest timeout_sec). A command
  that cannot start before the deadline is recorded as -1 without running.

Exit code conventions recorded in the receipt: the process exit code, -1
timeout / deadline, -2 executable or cwd missing or the process cannot be
started (any OSError), -3 output truncated.

Artifacts are hashed AFTER the commands; a missing, non-regular, symlinked or
escaping artifact gets the all-zero digest (FAIL).

Standard library only; no network.
"""

from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import threading
import time
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
)
from .signing import MIN_KEY_BYTES, sign

EXIT_TIMEOUT = -1
EXIT_MISSING_EXECUTABLE = -2
EXIT_OUTPUT_TRUNCATED = -3
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
        except (OSError, ValueError):
            pass

    def finish(self) -> None:
        self._thread.join(_JOIN_SEC)

    def text(self) -> str:
        return bytes(self.data).decode("utf-8", errors="replace")


def _spawn_kwargs() -> dict:
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return {"creationflags": flags}
    return {"start_new_session": True}


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill the child and all its descendants; never raises."""
    try:
        if os.name == "nt":
            root = os.environ.get("SYSTEMROOT", r"C:\Windows")
            exe = os.path.join(root, "System32", "taskkill.exe")
            if not os.path.isfile(exe):
                exe = "taskkill"
            subprocess.run(
                [exe, "/PID", str(proc.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def _run_one(
    argv: list[str], cwd: str, limit_sec: float, env: dict[str, str], cap: int
) -> tuple[int, str, dict]:
    """Run one argv without a shell; return (exit_code, stdout_text, info)."""
    info = {"stdout_truncated": False, "stderr_truncated": False, "timed_out": False}
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
            **_spawn_kwargs(),
        )
    except OSError:
        # Missing executable, missing/invalid cwd, no permission, or any other
        # OS-level failure to start. Non-OSError exceptions propagate.
        return EXIT_MISSING_EXECUTABLE, "", info
    out = _Capture(proc.stdout, cap)
    err = _Capture(proc.stderr, cap)
    try:
        proc.wait(timeout=limit_sec)
    except subprocess.TimeoutExpired:
        info["timed_out"] = True
        _kill_tree(proc)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    else:
        if os.name != "nt":
            try:  # reap stray members of the process group
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
    out.finish()
    err.finish()
    info["stdout_truncated"] = out.truncated
    info["stderr_truncated"] = err.truncated
    if info["timed_out"]:
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
    if attempt > valid["retry_cap"] + 1:
        raise ContractError(f"attempt: {attempt} exceeds retry_cap {valid['retry_cap']} + 1")
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
    "stderr_truncated", "timed_out", "skipped_by_deadline"}, ...]}.
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
                 "timed_out": False, "skipped_by_deadline": True}
            )
            continue
        exit_code, stdout, info = _run_one(
            list(argv), cwd, min(float(per_command), remaining), env, max_output_bytes
        )
        info["skipped_by_deadline"] = False
        recorded.append({"argv": list(argv), "exit_code": exit_code})
        outputs.append(stdout)
        infos.append(info)
    if report is not None:
        report["commands"] = infos

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
