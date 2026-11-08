"""AEVE CLI adapter (sprint U1, task U1-5).

Calls ``aeve review`` as an isolated child process and returns its parsed response, or raises
AdapterBlocked. Anything unexpected is BLOCKED, never a lenient parse into a clean result.

Isolation of the child: neutral working directory outside the reviewed root, interpreter flags
-P -s -B (no working directory or user site on the import path, no bytecode), an explicit minimal
environment with a pinned application-data location, shell=False, a stdout size cap, a timeout,
and termination of the whole process tree on timeout or cap breach. The request file lives in a
private temporary directory, never inside the reviewed repository.
"""

from __future__ import annotations

import json
import os
import signal
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from uc import aeve_probe  # noqa: E402

AEVE_REQUEST_SCHEMA = "aeve.review.request.v2"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_STDOUT_CAP = 8 * 1024 * 1024
STDERR_CAP = 64 * 1024
OK_EXIT_CODES = (0, 3)
REQUIRED_RESPONSE_KEYS = (
    "status", "request_id", "head", "snapshot_sha256", "iteration_id", "executor_ids",
    "results", "findings", "uncovered", "llm_calls", "executed_project_code", "source_modified", "dirty",
)


class AdapterBlocked(Exception):
    """The review could not be obtained; ``reason`` is a stable code and the result is BLOCKED."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class AeveRefused(AdapterBlocked):
    """AEVE answered with a short refusal envelope (no head or results); ``aeve_status``/``aeve_reason`` say why."""

    def __init__(self, aeve_status: str, aeve_reason: str) -> None:
        super().__init__("AEVE_REFUSED", f"{aeve_status}: {aeve_reason}")
        self.aeve_status = aeve_status
        self.aeve_reason = aeve_reason


_REASON = re.compile(r"^[A-Z0-9_]{1,64}$")


def build_aeve_request(
    *,
    request_id: str,
    root: str,
    base_revision: str,
    changed_paths: list[str],
    review_domains: list[str] | None = None,
    executor_ids: list[str] | None = None,
    profile_ids: list[str] | None = None,
    criteria: list[str] | None = None,
    iteration_of: str | None = None,
    allow_dirty: bool = False,
) -> dict:
    return {
        "schema_version": AEVE_REQUEST_SCHEMA,
        "request_id": request_id,
        "root": root,
        "base_revision": base_revision,
        "changed_paths": list(changed_paths),
        "review_domains": list(review_domains or []),
        "profile_ids": list(profile_ids or []),
        "executor_ids": list(executor_ids or []),
        "criteria": list(criteria or []),
        "iteration_of": iteration_of,
        "allow_dirty": bool(allow_dirty),
    }


_TASKKILL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")


def _kill_tree(process: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run([_TASKKILL, "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=15, check=False, shell=False)
        else:
            # Kill the entire process group (all children)
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                process.kill()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        process.kill()
    except OSError:
        pass


def _pump(stream, cap: int, sink: list[bytes], flag: dict, key: str) -> None:
    total = 0
    while True:
        chunk = stream.read(65536)
        if not chunk:
            return
        total += len(chunk)
        if total > cap:
            flag[key] = True
            return
        sink.append(chunk)


def _child_env(aeve_root: pathlib.Path, state_dir: pathlib.Path) -> dict[str, str]:
    env = aeve_probe.build_child_env(aeve_root)
    env["LOCALAPPDATA"] = str(state_dir)
    env["APPDATA"] = str(state_dir)
    return env


def run_review(
    aeve_request: dict,
    *,
    aeve_root: pathlib.Path,
    state_dir: pathlib.Path,
    python: str | None = None,
    command_prefix: list[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    stdout_cap: int = DEFAULT_STDOUT_CAP,
    require_clean_tree: bool = False,
) -> dict:
    """Run one review and return the validated AEVE response, or raise AdapterBlocked."""
    aeve_root = aeve_root.resolve()
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AdapterBlocked("STATE_DIR_UNUSABLE", type(exc).__name__) from exc
    if require_clean_tree and aeve_request.get("allow_dirty"):
        raise AdapterBlocked("DIRTY_NOT_ALLOWED_FOR_RECEIPT", "allow_dirty must be false for a receipt request")
    prefix = command_prefix or [python or sys.executable, "-P", "-s", "-B", "-m", "aeve"]
    with tempfile.TemporaryDirectory(prefix="uc-review-", ignore_cleanup_errors=True) as private:
        request_path = pathlib.Path(private) / "request.json"
        request_path.write_text(json.dumps(aeve_request, sort_keys=True), encoding="utf-8")
        argv = [*prefix, "review", "--request", str(request_path)]
        try:
            preexec = os.setpgrp if os.name != "nt" else None
            process = subprocess.Popen(
                argv, cwd=private, env=_child_env(aeve_root, state_dir),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                preexec_fn=preexec,
            )
        except OSError as exc:
            raise AdapterBlocked("EXEC_FAILED", str(exc)[:200]) from exc
        out_chunks: list[bytes] = []
        err_chunks: list[bytes] = []
        flags: dict[str, bool] = {}
        threads = [
            threading.Thread(target=_pump, args=(process.stdout, stdout_cap, out_chunks, flags, "stdout"), daemon=True),
            threading.Thread(target=_pump, args=(process.stderr, STDERR_CAP, err_chunks, flags, "stderr"), daemon=True),
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
    if timed_out:
        raise AdapterBlocked("TIMEOUT", f"exceeded {timeout}s; process tree terminated")
    if flags.get("stdout"):
        raise AdapterBlocked("OUTPUT_TOO_LARGE", f"stdout exceeded {stdout_cap} bytes")
    if flags.get("stderr"):
        raise AdapterBlocked("OUTPUT_TOO_LARGE", f"stderr exceeded {STDERR_CAP} bytes")
    exit_code = process.returncode
    if exit_code not in OK_EXIT_CODES:
        raise AdapterBlocked("AEVE_EXIT", f"exit {exit_code}")
    raw = b"".join(out_chunks)
    if b"\x00" in raw:
        raise AdapterBlocked("BAD_OUTPUT", "NUL byte in output")
    try:
        response = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise AdapterBlocked("BAD_OUTPUT", "output is not UTF-8 JSON") from exc
    return check_response(response, aeve_request, exit_code, require_clean_tree)


def check_response(response: object, aeve_request: dict, exit_code: int, require_clean_tree: bool = False) -> dict:
    if not isinstance(response, dict):
        raise AdapterBlocked("BAD_OUTPUT", "response is not a JSON object")
    if response.get("status") in ("NOT_COVERED", "BLOCKED", "INVALID") and "head" not in response:
        # Short refusal envelope. It carries no review output, so only its reason is used; the
        # zero-model, zero-execution flags and the request id are checked when AEVE reports them.
        if "findings" in response or "results" in response:
            raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "refusal envelope carries review output")
        if response.get("request_id", aeve_request["request_id"]) != aeve_request["request_id"]:
            raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "request_id differs from the request")
        if response.get("llm_calls", 0) != 0 or response.get("executed_project_code", False) is not False                 or response.get("source_modified", False) is not False:
            raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "refusal reports model calls, project-code execution or source modification")
        reason = response.get("reason")
        if not isinstance(reason, str) or not _REASON.match(reason):
            raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "refusal has no well-formed reason")
        raise AeveRefused(response["status"], reason)
    for key in REQUIRED_RESPONSE_KEYS:
        if key not in response:
            raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", f"response lacks {key}")
    if response["request_id"] != aeve_request["request_id"]:
        raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "request_id differs from the request")
    if response["head"] != aeve_request["base_revision"]:
        raise AdapterBlocked("HEAD_MOVED", "response head differs from the requested base_revision")
    if response["llm_calls"] != 0 or response["executed_project_code"] is not False or response["source_modified"] is not False:
        raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "response reports model calls, project-code execution or source modification")
    if not isinstance(response["results"], list) or not isinstance(response["findings"], list) \
            or not isinstance(response["executor_ids"], list):
        raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "results, findings or executor_ids is not a list")
    if require_clean_tree and response["dirty"] is not False:
        raise AdapterBlocked("DIRTY_TREE", "the reviewed tree was dirty")
    status = response["status"]
    if status not in ("COMPLETE", "PARTIAL", "FINDINGS"):
        raise AdapterBlocked("AEVE_STATUS", "unexpected overall status")  # ERROR, STALE_INPUT, anything unknown
    if response.get("ledger_persisted") is False:
        raise AdapterBlocked("AEVE_LEDGER_NOT_PERSISTED", "AEVE could not record the review")
    if (exit_code == 0) != (status == "COMPLETE" and not response["findings"]):
        raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "exit code disagrees with the status and findings")
    requested = set(aeve_request.get("executor_ids") or [])
    seen_ids = set()
    for item in response["results"]:
        if not isinstance(item, dict) or not isinstance(item.get("executor_id"), str) or not isinstance(item.get("status"), str):
            raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "a result lacks a string executor_id or status")
        if item["executor_id"] in seen_ids:
            raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "duplicate executor result")
        seen_ids.add(item["executor_id"])
    if requested and not seen_ids <= requested:
        raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "result for an executor that was not requested")
    for finding in response["findings"]:
        if not isinstance(finding, dict) or finding.get("executor_id") not in seen_ids:
            raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "a finding is not attributed to a returned executor result")
    if "finding_count" in response and response["finding_count"] != len(response["findings"]):
        raise AdapterBlocked("AEVE_CONTRACT_VIOLATION", "finding_count differs from the findings list")
    return response
