"""Runner: executes a command list, builds a TestRun receipt and signs it.

The runner is the only component that holds the signing key. The key is a
function argument: it is never written to disk, never logged, never placed in
the receipt, and never looked up in the worker's cwd.

Commands run with subprocess.run(argv, shell=False): no shell is involved.
Exit code conventions recorded in the receipt: the process exit code, -1 when
the command timed out, -2 when the executable (or cwd) does not exist or the
process cannot be started (any OSError). Inputs are validated before any command
runs; artifacts are hashed after the commands and bound into the receipt.

Standard library only; no network.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from typing import Callable

from .contracts import (
    MISSING_ARTIFACT_DIGEST,
    ContractError,
    _req_hex,
    _req_int,
    _req_str,
    _req_str_list,
    derive_result,
    validate_receipt,
)
from .signing import sign

EXIT_TIMEOUT = -1
EXIT_MISSING_EXECUTABLE = -2
_CHUNK = 64 * 1024


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


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _run_one(argv: list[str], cwd: str, timeout_sec: int) -> tuple[int, str]:
    """Run one argv without a shell; return (exit_code, stdout)."""
    try:
        done = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        return EXIT_TIMEOUT, _as_text(exc.stdout)
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        # Missing executable, missing/invalid cwd (Windows raises
        # NotADirectoryError for a missing cwd), or no permission to execute.
        return EXIT_MISSING_EXECUTABLE, ""
    except OSError:
        # Any other OS-level failure to start the process. Non-OSError
        # exceptions are deliberately not caught.
        return EXIT_MISSING_EXECUTABLE, ""
    return done.returncode, _as_text(done.stdout)


def _validate_inputs(
    *,
    task_id: object,
    slot: object,
    attempt: object,
    epoch: object,
    candidate_head: object,
    role_sha256: object,
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
    timeout_sec: object,
    created_at: object,
) -> list[list[str]]:
    """Validate every receipt-level input; raise ContractError before any run.

    A cwd that does not exist is NOT an error here (it yields exit_code -2).
    """
    for name, value in (
        ("task_id", task_id),
        ("slot", slot),
        ("resolved_model", resolved_model),
        ("invocation_id", invocation_id),
        ("runner_id", runner_id),
        ("created_at", created_at),
    ):
        _req_str(value, name)
    _req_int(attempt, "attempt", 1)
    _req_int(epoch, "epoch", 1)
    _req_hex(candidate_head, "candidate_head", 40)
    _req_hex(role_sha256, "role_sha256", 64)
    if attempt == 1:
        if prev_receipt_sha256 is not None:
            raise ContractError("prev_receipt_sha256: must be null when attempt == 1")
    else:
        _req_hex(prev_receipt_sha256, "prev_receipt_sha256", 64)
    if not isinstance(key, (bytes, bytearray)) or len(key) == 0:
        raise ContractError("key: must be non-empty bytes")
    argvs = _check_commands(commands)
    _req_str_list(expected_test_ids, "expected_test_ids")
    _req_str_list(covered_acceptance, "covered_acceptance")
    _req_str_list(artifact_paths, "artifact_paths")
    _req_int(timeout_sec, "timeout_sec", 1)
    if not isinstance(cwd, str):
        raise ContractError("cwd: must be a str")
    if not callable(test_result_parser):
        raise ContractError("test_result_parser: must be callable")
    return argvs


def _hash_artifacts(paths: list[str], cwd: str) -> dict[str, str]:
    """sha256 of each artifact (relative paths resolve against cwd).

    A path that cannot be read after the run is recorded with the all-zero
    digest; derive_result turns that into FAIL.
    """
    digests: dict[str, str] = {}
    for path in paths:
        try:
            digests[path] = file_sha256(os.path.join(cwd, path))
        except OSError:
            digests[path] = MISSING_ARTIFACT_DIGEST
    return digests


def run_and_sign(
    *,
    task_id: str,
    slot: str,
    attempt: int,
    epoch: int,
    candidate_head: str,
    role_sha256: str,
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
    timeout_sec: int,
    created_at: str,
) -> dict:
    """Execute commands, parse test ids, and return a signed TestRun receipt.

    The parser receives the joined stdout of all commands and returns
    (executed, skipped, xfail) test ids. The result is always computed with
    contracts.derive_result, never taken from the caller.

    All inputs are validated before any command starts (ContractError). A
    missing cwd or executable is not a validation error: it is recorded as
    exit_code -2. artifact_paths (required, may be empty) are hashed AFTER the
    commands ran, relative paths resolved against cwd; an unreadable artifact
    gets the all-zero digest, which makes the derived result FAIL.
    """
    argvs = _validate_inputs(
        task_id=task_id, slot=slot, attempt=attempt, epoch=epoch,
        candidate_head=candidate_head, role_sha256=role_sha256,
        resolved_model=resolved_model, invocation_id=invocation_id,
        runner_id=runner_id, key=key, commands=commands,
        expected_test_ids=expected_test_ids,
        test_result_parser=test_result_parser,
        covered_acceptance=covered_acceptance, artifact_paths=artifact_paths,
        prev_receipt_sha256=prev_receipt_sha256, cwd=cwd,
        timeout_sec=timeout_sec, created_at=created_at,
    )
    recorded: list[dict] = []
    outputs: list[str] = []
    for argv in argvs:
        exit_code, stdout = _run_one(list(argv), cwd, timeout_sec)
        recorded.append({"argv": list(argv), "exit_code": exit_code})
        outputs.append(stdout)

    executed, skipped, xfail = test_result_parser("\n".join(outputs))

    receipt = {
        "receipt_id": f"{task_id}:{slot}:{attempt}:{invocation_id}",
        "receipt_type": "TestRun",
        "task_id": task_id,
        "slot": slot,
        "attempt": attempt,
        "prev_receipt_sha256": prev_receipt_sha256,
        "candidate_head": candidate_head,
        "epoch": epoch,
        "runner_id": runner_id,
        "role_sha256": role_sha256,
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


def receipt_without_signature(receipt: dict) -> dict:
    """Shallow copy of a receipt without its 'signature' field."""
    return {k: v for k, v in receipt.items() if k != "signature"}
