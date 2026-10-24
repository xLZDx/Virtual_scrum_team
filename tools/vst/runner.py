"""Runner: executes a command list, builds a TestRun receipt and signs it.

The runner is the only component that holds the signing key. The key is a
function argument: it is never written to disk, never logged, never placed in
the receipt, and never looked up in the worker's cwd.

Commands run with subprocess.run(argv, shell=False): no shell is involved.
Exit code conventions recorded in the receipt: the process exit code, -1 when
the command timed out, -2 when the executable (or cwd) does not exist.

Standard library only; no network.
"""

from __future__ import annotations

import hashlib
import subprocess
from typing import Callable

from .contracts import ContractError, derive_result, validate_receipt
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
    except FileNotFoundError:
        return EXIT_MISSING_EXECUTABLE, ""
    return done.returncode, _as_text(done.stdout)


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
    prev_receipt_sha256: str | None,
    cwd: str,
    timeout_sec: int,
    created_at: str,
) -> dict:
    """Execute commands, parse test ids, and return a signed TestRun receipt.

    The parser receives the joined stdout of all commands and returns
    (executed, skipped, xfail) test ids. The result is always computed with
    contracts.derive_result, never taken from the caller.
    """
    argvs = _check_commands(commands)
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
    }
    receipt["result"] = derive_result(receipt)
    receipt["signature"] = sign(receipt_without_signature(receipt), key)
    return validate_receipt(receipt)


def receipt_without_signature(receipt: dict) -> dict:
    """Shallow copy of a receipt without its 'signature' field."""
    return {k: v for k, v in receipt.items() if k != "signature"}
