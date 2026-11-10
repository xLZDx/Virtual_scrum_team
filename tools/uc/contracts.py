"""Role request and role result contracts (sprint U1, task U1-3).

Strict validators for ``uc.role-request.v1`` and ``uc.role-result.v1``. Unknown fields are
rejected at every level. A result carries only enumerations, integers, hashes and validated
relative paths, so repository-controlled text cannot reach the orchestrator through it.
Free text exists only in the request ``criteria`` and is never executed.
"""

from __future__ import annotations

import os
import re

REQUEST_SCHEMA = "uc.role-request.v1"
RESULT_SCHEMA = "uc.role-result.v1"
BLOCKED_SCHEMA = "uc.blocked.v1"

PURPOSES = ("advisory", "receipt")
ROLE_CLASSES = ("LOCAL", "LOCAL_PLUS_MODEL", "MODEL_ONLY", "OUT_OF_SCOPE", "UNKNOWN")
ROLE_STATUSES = ("CLEAN", "FINDINGS", "PARTIAL", "NOT_COVERED", "NOT_RUN", "BLOCKED")
EXECUTOR_STATUSES = ("COMPLETE", "PARTIAL", "BLOCKED", "NOT_COVERED", "NOT_RUN")
SEVERITIES = ("NIT", "MINOR", "MAJOR", "BLOCKER")
EXIT_CODES = (0, 2, 3)

MAX_PATHS = 5000
MAX_PATH_LENGTH = 260
MAX_ROLES = 64
MAX_CRITERIA = 50
MAX_CRITERION_LENGTH = 2000
MAX_FINDINGS_PER_ROLE = 10000
MAX_LIST = 1000
MAX_MODEL_RESIDUAL = 8

_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_ROLE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_TOKEN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_HEAD = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_HEAD40 = re.compile(r"^[0-9a-f]{40}$")  # result.aeve_head only; _HEAD (40 or 64) stays for the other heads
_DRIVE = re.compile(r"^[A-Za-z]:")
_FORMAT_CHARS = frozenset("  ‪‫‬‭‮⁦⁧⁨⁩‎‏﻿")
_RESERVED_NAMES = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))})


class ContractError(ValueError):
    """A document violates its contract; ``code`` is stable, ``where`` names the field."""

    def __init__(self, code: str, where: str) -> None:
        super().__init__(f"{code} at {where}")
        self.code = code
        self.where = where


def _has_control(text: str) -> bool:
    return any(ord(ch) < 32 or 127 <= ord(ch) <= 159 or ch in _FORMAT_CHARS for ch in text)


def _object(value: object, where: str, required: set[str], optional: set[str] = frozenset()) -> dict:
    if not isinstance(value, dict):
        raise ContractError("NOT_AN_OBJECT", where)
    keys = set(value)
    missing = required - keys
    if missing:
        raise ContractError("MISSING_FIELD", f"{where}.{sorted(missing)[0]}")
    unknown = keys - required - optional
    if unknown:
        raise ContractError("UNKNOWN_FIELD", f"{where}.[unknown field]")
    return value


def _string(value: object, where: str, pattern: re.Pattern | None = None, max_len: int = 4096) -> str:
    if not isinstance(value, str) or isinstance(value, bool):
        raise ContractError("NOT_A_STRING", where)
    if len(value) > max_len or _has_control(value):
        raise ContractError("BAD_STRING", where)
    if pattern is not None and not pattern.match(value):
        raise ContractError("BAD_FORMAT", where)
    return value


def _enum(value: object, where: str, allowed: tuple) -> object:
    if value not in allowed or isinstance(value, bool):
        raise ContractError("NOT_ALLOWED_VALUE", where)
    return value


def _int(value: object, where: str, minimum: int = 0, maximum: int = 10**9) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ContractError("BAD_INTEGER", where)
    return value


def _list(value: object, where: str, max_items: int) -> list:
    if not isinstance(value, list):
        raise ContractError("NOT_A_LIST", where)
    if len(value) > max_items:
        raise ContractError("TOO_MANY_ITEMS", where)
    return value


def validate_relative_posix_path(value: object, where: str) -> str:
    """A repository-relative POSIX path: no traversal, drive, backslash, control or empty parts."""
    text = _string(value, where, max_len=MAX_PATH_LENGTH)
    if not text or text.startswith("/") or "\\" in text or _DRIVE.match(text) or ":" in text:
        raise ContractError("BAD_PATH", where)
    parts = text.split("/")
    for part in parts:
        if part in ("", ".", "..") or part != part.strip() or part.endswith("."):
            raise ContractError("BAD_PATH", where)
        if part.split(".", 1)[0].lower() in _RESERVED_NAMES:
            raise ContractError("BAD_PATH", where)
    return text


def _is_link_like(path: str) -> bool:
    """A symbolic link, or on Windows a junction or any other reparse point."""
    if os.path.islink(path):
        return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT


def reject_symlink_components(root: str, relative_path: str, where: str) -> None:
    """Refuse a path whose existing components under ``root`` include a link or reparse point."""
    current = root
    for part in relative_path.split("/"):
        current = os.path.join(current, part)
        if _is_link_like(current):
            raise ContractError("SYMLINK_COMPONENT", where)
        if not os.path.exists(current):
            return


def _normalize_root(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def validate_request(document: object, allowed_roots: list[str], *, check_symlinks: bool = False) -> dict:
    """Return the request as validated; raise ContractError on the first violation."""
    doc = _object(
        document, "request",
        {"schema_version", "request_id", "root", "base_revision", "changed_paths", "roles", "purpose"},
        {"criteria", "iteration_of"},
    )
    if doc["schema_version"] != REQUEST_SCHEMA:
        raise ContractError("WRONG_SCHEMA", "request.schema_version")
    _string(doc["request_id"], "request.request_id", _ID)
    if doc["request_id"].split(".", 1)[0].lower() in _RESERVED_NAMES:
        raise ContractError("BAD_FORMAT", "request.request_id")
    root = _string(doc["root"], "request.root", max_len=1024)
    if not os.path.isabs(root):
        raise ContractError("ROOT_NOT_ABSOLUTE", "request.root")
    allowed = {_normalize_root(item) for item in allowed_roots}
    if _normalize_root(root) not in allowed:
        raise ContractError("ROOT_NOT_ALLOWED", "request.root")
    _string(doc["base_revision"], "request.base_revision", _HEAD)
    paths = _list(doc["changed_paths"], "request.changed_paths", MAX_PATHS)
    seen = set()
    for index, item in enumerate(paths):
        where = f"request.changed_paths[{index}]"
        clean = validate_relative_posix_path(item, where)
        if clean in seen:
            raise ContractError("DUPLICATE_PATH", where)
        seen.add(clean)
        if check_symlinks:
            reject_symlink_components(root, clean, where)
    roles = _list(doc["roles"], "request.roles", MAX_ROLES)
    if not roles:
        raise ContractError("EMPTY_LIST", "request.roles")
    # Type-check first, then deduplicate (set() fails on non-hashable)
    for index, item in enumerate(roles):
        _string(item, f"request.roles[{index}]", _ROLE)
    if len(set(roles)) != len(roles):
        raise ContractError("DUPLICATE_ROLE", "request.roles")
    _enum(doc["purpose"], "request.purpose", PURPOSES)
    if "criteria" in doc:
        for index, item in enumerate(_list(doc["criteria"], "request.criteria", MAX_CRITERIA)):
            text = _string(item, f"request.criteria[{index}]", max_len=MAX_CRITERION_LENGTH)
            if "\x00" in text:
                raise ContractError("BAD_STRING", f"request.criteria[{index}]")
    if doc.get("iteration_of") is not None:
        _string(doc["iteration_of"], "request.iteration_of", _ID)
    return doc


def _validate_executor(value: object, where: str) -> dict:
    item = _object(value, where, {"id", "status", "snapshot_hash"})
    _string(item["id"], f"{where}.id", _TOKEN)
    _enum(item["status"], f"{where}.status", EXECUTOR_STATUSES)
    _string(item["snapshot_hash"], f"{where}.snapshot_hash", _HASH)
    return item


def _validate_finding(value: object, where: str) -> dict:
    item = _object(value, where, {"rule_id", "severity", "path", "line", "column", "evidence_hash"})
    _string(item["rule_id"], f"{where}.rule_id", _TOKEN)
    _enum(item["severity"], f"{where}.severity", SEVERITIES)
    validate_relative_posix_path(item["path"], f"{where}.path")
    _int(item["line"], f"{where}.line")
    _int(item["column"], f"{where}.column")
    _string(item["evidence_hash"], f"{where}.evidence_hash", _HASH)
    return item


def _validate_role_entry(value: object, where: str) -> dict:
    item = _object(
        value, where,
        {"role", "canonical_role", "class", "status", "executors", "findings", "uncovered", "model_residual"},
    )
    _string(item["role"], f"{where}.role", _ROLE)
    _string(item["canonical_role"], f"{where}.canonical_role", _ROLE)
    _enum(item["class"], f"{where}.class", ROLE_CLASSES)
    status = _enum(item["status"], f"{where}.status", ROLE_STATUSES)
    executors = [_validate_executor(e, f"{where}.executors[{i}]")
                 for i, e in enumerate(_list(item["executors"], f"{where}.executors", MAX_LIST))]
    findings = [_validate_finding(f, f"{where}.findings[{i}]")
                for i, f in enumerate(_list(item["findings"], f"{where}.findings", MAX_FINDINGS_PER_ROLE))]
    for field in ("uncovered", "model_residual"):
        for i, token in enumerate(_list(item[field], f"{where}.{field}", MAX_LIST)):
            _string(token, f"{where}.{field}[{i}]", _TOKEN)
    residual = item["model_residual"]
    # Same rule as the VST bridge: at most 8 tokens, sorted, unique (checked exactly, never repaired).
    if len(residual) > MAX_MODEL_RESIDUAL or residual != sorted(set(residual)):
        raise ContractError("BAD_MODEL_RESIDUAL", f"{where}.model_residual")
    if status == "CLEAN":
        if findings or residual or item["uncovered"]:
            raise ContractError("CLEAN_WITH_OPEN_ITEMS", where)
        if not executors or any(e["status"] != "COMPLETE" for e in executors):
            raise ContractError("CLEAN_WITHOUT_COMPLETE_EXECUTORS", where)
        if item["class"] != "LOCAL":
            # A model-assisted role is never CLEAN: the model slice is always still open.
            raise ContractError("CLEAN_FOR_NON_LOCAL_CLASS", where)
    if status == "FINDINGS" and not findings:
        raise ContractError("FINDINGS_WITHOUT_FINDINGS", where)
    if status != "FINDINGS" and status != "PARTIAL" and findings:
        raise ContractError("FINDINGS_WITH_WRONG_STATUS", where)
    return item


def changed_paths_sha256(paths: list[str]) -> str:
    """sha256 of the canonical bytes of the sorted path list.

    Canonical bytes are json.dumps(sorted(paths), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    allow_nan=False) as UTF-8: byte-identical to tools.vst.contracts.canonical_bytes, so the VST side can
    compare it with its own reviewed_paths_sha256. The router computes it from the validated request.
    """
    import hashlib
    import json

    blob = json.dumps(sorted(paths), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_result(document: object) -> dict:
    """Return the result as validated; raise ContractError on the first violation."""
    doc = _object(
        document, "result",
        {"schema_version", "request_id", "base_revision", "snapshot_hash", "iteration_id", "exit_code", "roles",
         "role_table_sha256", "aeve_head", "purpose", "changed_paths_sha256"},
    )
    if doc["schema_version"] != RESULT_SCHEMA:
        raise ContractError("WRONG_SCHEMA", "result.schema_version")
    _string(doc["request_id"], "result.request_id", _ID)
    _string(doc["base_revision"], "result.base_revision", _HEAD)
    _string(doc["snapshot_hash"], "result.snapshot_hash", _HASH)
    # U2-1: bridge facts. sha256 of the exact role_table.json bytes the router loaded, and the AEVE
    # source head the router probed and matched against the table pin before the review ran.
    _string(doc["role_table_sha256"], "result.role_table_sha256", _HASH)
    _string(doc["aeve_head"], "result.aeve_head", _HEAD40)
    # U2-3: the request purpose and the digest of the request's sorted changed_paths, copied by the router
    # from the validated request, so a receipt builder can refuse an advisory result or a different path set.
    _enum(doc["purpose"], "result.purpose", PURPOSES)
    _string(doc["changed_paths_sha256"], "result.changed_paths_sha256", _HASH)
    _string(doc["iteration_id"], "result.iteration_id", _ID)
    exit_code = _int(doc["exit_code"], "result.exit_code", 0, 3)
    _enum(exit_code, "result.exit_code", EXIT_CODES)
    roles = _list(doc["roles"], "result.roles", MAX_ROLES)
    if not roles:
        raise ContractError("EMPTY_LIST", "result.roles")
    entries = [_validate_role_entry(r, f"result.roles[{i}]") for i, r in enumerate(roles)]
    for index, entry in enumerate(entries):
        for e in entry["executors"]:
            if e["snapshot_hash"] != doc["snapshot_hash"]:
                raise ContractError("EXECUTOR_SNAPSHOT_MISMATCH", f"result.roles[{index}].executors")
    names = [e["role"] for e in entries]
    if len(set(names)) != len(names):
        raise ContractError("DUPLICATE_ROLE", "result.roles")
    all_clean = all(e["status"] == "CLEAN" for e in entries)
    if exit_code == 0 and not all_clean:
        raise ContractError("EXIT_ZERO_WITH_OPEN_ITEMS", "result.exit_code")
    if exit_code != 0 and all_clean:
        raise ContractError("EXIT_NONZERO_WHEN_CLEAN", "result.exit_code")
    return doc


def validate_blocked(document: object) -> dict:
    """The envelope returned when no role result can be produced at all."""
    doc = _object(document, "blocked", {"schema_version", "request_id", "status", "reason", "detail"})
    if doc["schema_version"] != BLOCKED_SCHEMA:
        raise ContractError("WRONG_SCHEMA", "blocked.schema_version")
    _string(doc["request_id"], "blocked.request_id", _ID)
    if doc["status"] != "BLOCKED":
        raise ContractError("NOT_ALLOWED_VALUE", "blocked.status")
    _string(doc["reason"], "blocked.reason", re.compile(r"^[A-Z0-9_]{1,64}$"))
    _string(doc["detail"], "blocked.detail", max_len=200)
    return doc

