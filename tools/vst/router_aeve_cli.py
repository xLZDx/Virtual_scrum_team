"""Router mode, AEVE command side (LINK2-T3, design docs/sdlc/LINK2_ROUTER_DESIGN.md D2 steps 2, 3, 6, 7 and D5, D6).

Two wrappers over `tools.uc.adapter.run_aeve_command` (the generic runner of LINK2-T3A):

- `run_packet`: pin check, `aeve packet --request <file>`, packet validation (`router_request.validate_packet`).
- `run_verify_handoff`: pin check, `aeve verify-handoff --packet <file> --result <file> --root <dir>` (ALWAYS with
  `--root`), report validation and routing outcome.

Fail closed. Every failure is a `RouterError` with a ROUTER_* code (design D6); nothing falls back to `gates` mode.
The pin check runs before any AEVE command: git HEAD must equal the pinned head and `git status --porcelain
--untracked-files=all` must print nothing, otherwise ROUTER_PIN_DRIFT (also when git cannot answer).

Report validation: schema `aeve.handoff_verify.v1`, status one of VERIFIED, REJECTED, UNKNOWN, INVALID; exit code and
status must agree (0 VERIFIED, 1 REJECTED, 2 UNKNOWN, 3 INVALID, else ROUTER_BAD_EXIT); guards (llm_calls 0,
executed_project_code false, source_modified false); `basis` is the claimed-result value; task_id and role equal the
packet; `checks[]` holds exactly the five known ids once each with PASS/FAIL/UNKNOWN; and the overall status equals the
worst check (any FAIL gives REJECTED, else any UNKNOWN gives UNKNOWN, else VERIFIED). UNKNOWN is never a pass. INVALID
carries no checks. Anything else is ROUTER_BAD_OUTPUT.

Timeout retry (D5): only ROUTER_TIMEOUT, at most `max_retries` (2) retries with a jitter pause, and only when the
adapter confirmed the child process tree dead; otherwise no retry. No other code is retried.

The result and packet files named here must already be VST-owned copies (design D2 step 5); this module never reads
the host's original result path. It writes only the temporary request file inside the adapter's private directory.
The report is returned unmodified as bytes and parsed dict; routing does not re-decide it.
"""

from __future__ import annotations

import json
import pathlib
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from ..uc import adapter, aeve_probe
from . import router_request as rr
from .router_request import RouterError

REPORT_SCHEMA = "aeve.handoff_verify.v1"
REPORT_BASIS = "CLAIMED_RESULT_NOT_INDEPENDENTLY_DIFFED"
CHECK_IDS = (
    "CHANGES_INSIDE_SCOPE",
    "EVIDENCE_DOCUMENTS_EXIST",
    "FORBIDDEN_UNTOUCHED",
    "TASK_ID_MATCH",
    "TESTS_FOR_LOGIC",
)
CHECK_STATUSES = ("PASS", "FAIL", "UNKNOWN")
EXIT_FOR_STATUS = {"VERIFIED": 0, "REJECTED": 1, "UNKNOWN": 2, "INVALID": 3}
OUTCOME_FOR_STATUS = {
    "VERIFIED": "ROUTED_VERIFIED",
    "REJECTED": "ROUTED_REJECTED",
    "UNKNOWN": "ROUTED_UNKNOWN",
    "INVALID": "ROUTER_INVALID_INPUT",
}

DEFAULT_TIMEOUT_SECONDS = adapter.DEFAULT_TIMEOUT_SECONDS  # 120 s per AEVE command (D5)
DEFAULT_STDOUT_CAP = rr.MAX_PACKET_BYTES  # 1 MiB (D5)
DEFAULT_MAX_RETRIES = 2
DEFAULT_JITTER_SECONDS = (0.5, 2.0)

# reason codes (design D6)
ROUTER_PIN_DRIFT = "ROUTER_PIN_DRIFT"
ROUTER_AEVE_MISSING = "ROUTER_AEVE_MISSING"
ROUTER_TIMEOUT = "ROUTER_TIMEOUT"
ROUTER_BAD_EXIT = "ROUTER_BAD_EXIT"
ROUTER_STATE_DIR_UNUSABLE = "ROUTER_STATE_DIR_UNUSABLE"

DEFAULT_ROLE_TABLE = pathlib.Path(__file__).resolve().parents[2] / "catalog" / "role_table.json"
_HEX40 = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class PacketResult:
    packet: dict[str, Any]
    packet_bytes: bytes
    packet_sha256: str
    exit_code: int
    retry_count: int


@dataclass(frozen=True)
class VerifyResult:
    outcome: str  # ROUTED_VERIFIED, ROUTED_REJECTED, ROUTED_UNKNOWN, ROUTER_INVALID_INPUT
    status: str  # the AEVE status, as reported
    report: dict[str, Any]
    report_bytes: bytes
    report_sha256: str
    exit_code: int
    retry_count: int
    reason: str  # AEVE reason for INVALID (ASCII-escaped, truncated), else ""


def load_pin_head(path: str | pathlib.Path = DEFAULT_ROLE_TABLE) -> str:
    """The pinned AEVE head from catalog/role_table.json; fails closed with ROUTER_PIN_DRIFT when unreadable."""
    try:
        head = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))["aeve_pin"]["head"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RouterError(ROUTER_PIN_DRIFT, f"pinned head unreadable ({type(exc).__name__})") from exc
    if not isinstance(head, str) or len(head) != 40 or not set(head) <= _HEX40:
        raise RouterError(ROUTER_PIN_DRIFT, "pinned head is not a 40-character lowercase hex string")
    return head


def check_pin(aeve_root: pathlib.Path, pin_head: str) -> None:
    """ROUTER_AEVE_MISSING when the root is not a directory; ROUTER_PIN_DRIFT when HEAD differs from the pin, the
    checkout is not clean, or git cannot answer. Starts no AEVE command."""
    if not isinstance(pin_head, str) or len(pin_head) != 40 or not set(pin_head) <= _HEX40:
        raise RouterError(ROUTER_PIN_DRIFT, "expected pin is not a 40-character lowercase hex string")
    if not pathlib.Path(aeve_root).is_dir():
        raise RouterError(ROUTER_AEVE_MISSING, "AEVE root is not a directory")
    try:
        head = aeve_probe.checkout_head(pathlib.Path(aeve_root))
        clean = aeve_probe.checkout_is_clean(pathlib.Path(aeve_root))
    except aeve_probe.AeveProbeError as exc:
        raise RouterError(ROUTER_PIN_DRIFT, f"cannot establish the AEVE checkout state ({exc.reason})") from exc
    if head != pin_head:
        raise RouterError(ROUTER_PIN_DRIFT, "AEVE HEAD differs from the pinned head")
    if not clean:
        raise RouterError(ROUTER_PIN_DRIFT, "AEVE checkout has a tracked change or an untracked file")


def _map_blocked(exc: adapter.AdapterBlocked) -> RouterError:
    reason = exc.reason
    if reason == "TIMEOUT":
        out = RouterError(ROUTER_TIMEOUT, rr.ascii_excerpt(exc.detail))
        out.tree_dead = exc.tree_dead
    elif reason == "OUTPUT_TOO_LARGE":
        out = RouterError(rr.ROUTER_SIZE_CAP, rr.ascii_excerpt(exc.detail))
    elif reason == "AEVE_EXIT":
        out = RouterError(ROUTER_BAD_EXIT, rr.ascii_excerpt(exc.detail))
    elif reason == "EXEC_FAILED":
        out = RouterError(ROUTER_AEVE_MISSING, rr.ascii_excerpt(exc.detail))
    elif reason == "STATE_DIR_UNUSABLE":
        out = RouterError(ROUTER_STATE_DIR_UNUSABLE, rr.ascii_excerpt(exc.detail))
    else:
        out = RouterError(rr.ROUTER_BAD_OUTPUT, rr.ascii_excerpt(f"{reason} {exc.detail}"))
    return out


def _run_with_retry(
    command: str,
    args: Sequence[str] | Callable[[pathlib.Path], Sequence[str]],
    *,
    aeve_root: pathlib.Path,
    state_dir: pathlib.Path,
    python: str | None,
    command_prefix: list[str] | None,
    timeout: float,
    stdout_cap: int,
    max_retries: int,
    jitter: tuple[float, float],
    sleep: Callable[[float], None],
) -> tuple[int, bytes, int]:
    """(exit_code, stdout, retry_count). Retries ROUTER_TIMEOUT only, after a confirmed-dead child tree."""
    retries = 0
    while True:
        try:
            exit_code, raw = adapter.run_aeve_command(
                command, args, aeve_root=aeve_root, state_dir=state_dir, python=python,
                command_prefix=command_prefix, timeout=timeout, stdout_cap=stdout_cap,
            )
            return exit_code, raw, retries
        except adapter.AdapterBlocked as exc:
            mapped = _map_blocked(exc)
            mapped.retry_count = retries
            if mapped.reason != ROUTER_TIMEOUT:
                raise mapped from exc
            if exc.tree_dead is not True:
                unconfirmed = RouterError(ROUTER_TIMEOUT, "child process tree not confirmed dead; no retry")
                unconfirmed.tree_dead = exc.tree_dead
                unconfirmed.retry_count = retries
                raise unconfirmed from exc
            if retries >= max_retries:
                raise mapped from exc
            retries += 1
            sleep(random.uniform(*jitter))


def run_packet(
    request: Mapping[str, Any],
    *,
    aeve_root: pathlib.Path,
    state_dir: pathlib.Path,
    pin_head: str,
    python: str | None = None,
    command_prefix: list[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    stdout_cap: int = DEFAULT_STDOUT_CAP,
    max_retries: int = DEFAULT_MAX_RETRIES,
    jitter: tuple[float, float] = DEFAULT_JITTER_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> PacketResult:
    """Pin check, then `aeve packet` on the canonical bytes of ``request``; returns the validated packet."""
    payload = rr.request_bytes(request)
    check_pin(aeve_root, pin_head)

    def packet_args(private: pathlib.Path) -> list[str]:
        path = private / "request.json"
        path.write_bytes(payload)
        return ["--request", str(path)]

    exit_code, raw, retries = _run_with_retry(
        "packet", packet_args, aeve_root=aeve_root, state_dir=state_dir, python=python,
        command_prefix=command_prefix, timeout=timeout, stdout_cap=stdout_cap,
        max_retries=max_retries, jitter=jitter, sleep=sleep,
    )
    try:
        status = rr.parse_strict_json_object(raw, "packet").get("status")
        # exit 0 means COMPLETE and exit 3 means INVALID; any other pairing is a contract break.
        if (exit_code == 0) != (status == "COMPLETE") or (exit_code == 3 and status != "INVALID"):
            raise RouterError(ROUTER_BAD_EXIT, f"packet exit {exit_code} disagrees with status")
        packet = rr.validate_packet(raw, request)
    except RouterError as exc:
        exc.retry_count = retries
        raise
    return PacketResult(packet, raw, rr.sha256_hex(raw), exit_code, retries)


def worst_status(checks: Sequence[Mapping[str, Any]]) -> str:
    """Any FAIL gives REJECTED, else any UNKNOWN gives UNKNOWN, else VERIFIED."""
    statuses = {check["status"] for check in checks}
    if "FAIL" in statuses:
        return "REJECTED"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "VERIFIED"


def _validate_checks(report: Mapping[str, Any]) -> None:
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        raise RouterError(rr.ROUTER_BAD_OUTPUT, "report checks is not a non-empty list")
    seen: set[str] = set()
    for check in checks:
        if not isinstance(check, dict):
            raise RouterError(rr.ROUTER_BAD_OUTPUT, "a check is not an object")
        check_id, status = check.get("id"), check.get("status")
        if check_id not in CHECK_IDS or check_id in seen:
            raise RouterError(rr.ROUTER_BAD_OUTPUT, "a check id is unknown or repeated")
        seen.add(check_id)
        if status not in CHECK_STATUSES:
            raise RouterError(rr.ROUTER_BAD_OUTPUT, "a check status is not PASS, FAIL or UNKNOWN")
        paths = check.get("paths")
        if not isinstance(check.get("reason"), str) or not isinstance(paths, list) \
                or not all(isinstance(item, str) for item in paths):
            raise RouterError(rr.ROUTER_BAD_OUTPUT, "a check lacks a string reason or a string path list")
    if seen != set(CHECK_IDS):
        raise RouterError(rr.ROUTER_BAD_OUTPUT, "report does not carry exactly the five known checks")


def validate_report(raw: bytes, exit_code: int, packet: Mapping[str, Any]) -> tuple[dict[str, Any], str, str]:
    """Validate the bytes `aeve verify-handoff` printed. Returns (report, AEVE status, INVALID reason or "")."""
    if len(raw) > rr.MAX_PACKET_BYTES:
        raise RouterError(rr.ROUTER_SIZE_CAP, f"report exceeds {rr.MAX_PACKET_BYTES} bytes")
    report = rr.parse_strict_json_object(raw, "report")
    if report.get("schema_version") != REPORT_SCHEMA:
        raise RouterError(rr.ROUTER_BAD_OUTPUT, "report schema_version is not aeve.handoff_verify.v1")
    status = report.get("status")
    if not isinstance(status, str) or status not in EXIT_FOR_STATUS:
        raise RouterError(rr.ROUTER_BAD_OUTPUT, "report status is not VERIFIED, REJECTED, UNKNOWN or INVALID")
    if EXIT_FOR_STATUS[status] != exit_code:
        raise RouterError(ROUTER_BAD_EXIT, f"exit {exit_code} disagrees with status {status}")
    rr.check_guards(report, rr.ROUTER_BAD_OUTPUT, "report")
    if status == "INVALID":
        reason = report.get("reason")
        if not isinstance(reason, str) or "checks" in report:
            raise RouterError(rr.ROUTER_BAD_OUTPUT, "INVALID report has no reason or carries checks")
        return report, status, rr.ascii_excerpt(reason)
    if report.get("basis") != REPORT_BASIS:
        raise RouterError(rr.ROUTER_BAD_OUTPUT, "report basis is not the claimed-result value")
    if report.get("task_id") != packet.get("task_id") or report.get("role") != packet.get("role"):
        raise RouterError(rr.ROUTER_BAD_OUTPUT, "report task_id or role differs from the packet")
    _validate_checks(report)
    if worst_status(report["checks"]) != status:
        raise RouterError(rr.ROUTER_BAD_OUTPUT, f"report status {status} differs from the worst check")
    return report, status, ""


def run_verify_handoff(
    packet_path: pathlib.Path,
    result_path: pathlib.Path,
    packet: Mapping[str, Any],
    *,
    root: pathlib.Path,
    aeve_root: pathlib.Path,
    state_dir: pathlib.Path,
    pin_head: str,
    python: str | None = None,
    command_prefix: list[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    stdout_cap: int = DEFAULT_STDOUT_CAP,
    max_retries: int = DEFAULT_MAX_RETRIES,
    jitter: tuple[float, float] = DEFAULT_JITTER_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> VerifyResult:
    """Pin check, then `aeve verify-handoff` on the two VST-owned copies with `--root`; returns the routed outcome.

    ``packet`` is the validated packet (`PacketResult.packet`); only its task_id and role are used, to bind the report.
    REJECTED, UNKNOWN and INVALID are returned (not raised) with their outcome; every contract break raises.
    """
    if root is None or not str(root):
        raise RouterError(rr.ROUTER_BAD_REQUEST, "verify-handoff always needs --root")
    check_pin(aeve_root, pin_head)
    args = ["--packet", str(packet_path), "--result", str(result_path), "--root", str(root)]
    exit_code, raw, retries = _run_with_retry(
        "verify-handoff", args, aeve_root=aeve_root, state_dir=state_dir, python=python,
        command_prefix=command_prefix, timeout=timeout, stdout_cap=stdout_cap,
        max_retries=max_retries, jitter=jitter, sleep=sleep,
    )
    try:
        report, status, reason = validate_report(raw, exit_code, packet)
    except RouterError as exc:
        exc.retry_count = retries
        raise
    return VerifyResult(OUTCOME_FOR_STATUS[status], status, report, raw, rr.sha256_hex(raw), exit_code, retries, reason)
