"""Router mode, request side (LINK2-T2, design docs/sdlc/LINK2_ROUTER_DESIGN.md D2 steps 1 and 3).

Builds the `aeve.task_packet.request.v1` document from a story and validates the `aeve.task_packet.v1` packet that
`aeve packet` returns. Pure functions: no process is started, no file is read or written, no model is called.

- `build_request` checks the story fields BEFORE any AEVE call and raises `RouterError("ROUTER_BAD_REQUEST")`.
  The request is a plain dict; `request_bytes` gives its canonical form (ASCII JSON, sorted keys, compact
  separators, one trailing LF), so the same story always gives the same bytes.
- `validate_packet` takes the raw packet bytes (size cap first, `ROUTER_SIZE_CAP`), parses them strictly
  (`ROUTER_BAD_OUTPUT` for malformed JSON, duplicate keys, NUL, a non-object) and checks schema, status COMPLETE,
  that role and task_id equal the request, the AC ids, and the zero-model, zero-execution, no-modification guards
  (`ROUTER_PACKET_INVALID`).

VST does not recompute AEVE's `request_sha256` and does not depend on how AEVE normalises the request (design
section 7); it only checks that the value is a 64-character lowercase hex string and stores it as opaque.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

REQUEST_SCHEMA = "aeve.task_packet.request.v1"
PACKET_SCHEMA = "aeve.task_packet.v1"

# The five HANDOFF_ASSISTED roles (AEVE README, confirmed against the rebuilt catalog/role_table.json in LINK2-T1).
ROUTER_ROLES = (
    "implementation-engineer",
    "ml-engineer",
    "planner",
    "product-ux-reviewer",
    "ux-design-contract",
)

MAX_PACKET_BYTES = 1024 * 1024  # D5 size cap for a packet
MAX_ITEMS = 200  # AEVE _MAX_ITEMS
MAX_TEXT = 500  # AEVE _MAX_TEXT
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_AC_RE = re.compile(r"^AC-([1-9][0-9]*)$")
_REASON_LIMIT = 120

# reason codes (design D6)
ROUTER_BAD_REQUEST = "ROUTER_BAD_REQUEST"
ROUTER_PACKET_INVALID = "ROUTER_PACKET_INVALID"
ROUTER_SIZE_CAP = "ROUTER_SIZE_CAP"
ROUTER_BAD_OUTPUT = "ROUTER_BAD_OUTPUT"


class RouterError(Exception):
    """A router step failed closed; ``reason`` is a stable ROUTER_* code and the story is BLOCKED."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def ascii_excerpt(value: object, limit: int = _REASON_LIMIT) -> str:
    """Truncated, ASCII-escaped text for a reason detail (never raw foreign text)."""
    return str(value)[:limit].encode("ascii", "backslashreplace").decode("ascii")


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        raise RouterError(ROUTER_BAD_REQUEST, f"{field} must be a non-empty string of at most {MAX_TEXT} characters")
    return value


def _text_list(value: object, field: str, *, required: bool) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RouterError(ROUTER_BAD_REQUEST, f"{field} must be a list of strings")
    items = list(value)
    if (required and not items) or len(items) > MAX_ITEMS:
        raise RouterError(ROUTER_BAD_REQUEST, f"{field} must have 1..{MAX_ITEMS} items" if required else f"{field} has too many items")
    return [_text(item, f"{field}[]") for item in items]


def build_request(
    *,
    role: str,
    task_id: str,
    title: str,
    scope_paths: Sequence[str],
    acceptance: Sequence[str],
    files: Sequence[str] = (),
    forbidden_paths: Sequence[str] = (),
) -> dict[str, Any]:
    """The AEVE task packet request for one story, or RouterError(ROUTER_BAD_REQUEST). Starts no process."""
    if role not in ROUTER_ROLES:
        raise RouterError(ROUTER_BAD_REQUEST, "role is not a HANDOFF_ASSISTED role")
    if not isinstance(task_id, str) or not TASK_ID_RE.match(task_id):
        raise RouterError(ROUTER_BAD_REQUEST, "task_id does not match the allowed pattern")
    return {
        "schema_version": REQUEST_SCHEMA,
        "role": role,
        "task_id": task_id,
        "title": _text(title, "title"),
        "scope_paths": _text_list(scope_paths, "scope_paths", required=True),
        "files": _text_list(files, "files", required=False),
        "forbidden_paths": _text_list(forbidden_paths, "forbidden_paths", required=False),
        "acceptance": _text_list(acceptance, "acceptance", required=True),
    }


def request_bytes(request: Mapping[str, Any]) -> bytes:
    """Canonical bytes of a request: ASCII JSON, sorted keys, compact separators, one LF."""
    return (json.dumps(request, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


def _no_constant(name: str) -> Any:
    raise ValueError(f"constant {name}")


def parse_strict_json_object(raw: bytes, label: str) -> dict[str, Any]:
    """Parse UTF-8 JSON that must be one object; duplicate keys, NaN/Infinity, NUL, BOM raise ROUTER_BAD_OUTPUT."""
    if b"\x00" in raw:
        raise RouterError(ROUTER_BAD_OUTPUT, f"{label}: NUL byte")
    try:
        text = raw.decode("utf-8")
        if text.startswith("﻿"):
            raise ValueError("BOM")
        value = json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=_no_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise RouterError(ROUTER_BAD_OUTPUT, f"{label}: not strict UTF-8 JSON ({type(exc).__name__})") from exc
    if not isinstance(value, dict):
        raise RouterError(ROUTER_BAD_OUTPUT, f"{label}: JSON is not an object")
    return value


def is_zero(value: object) -> bool:
    """True only for the integer 0 (not False, not 0.0)."""
    return type(value) is int and value == 0


def check_guards(document: Mapping[str, Any], error_code: str, label: str) -> None:
    """llm_calls 0, executed_project_code False, source_modified False, all present."""
    if not is_zero(document.get("llm_calls")):
        raise RouterError(error_code, f"{label}: llm_calls is not 0")
    if document.get("executed_project_code") is not False:
        raise RouterError(error_code, f"{label}: executed_project_code is not false")
    if document.get("source_modified") is not False:
        raise RouterError(error_code, f"{label}: source_modified is not false")


def validate_packet(raw: bytes, request: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the bytes `aeve packet` printed against the request that produced them; return the parsed packet."""
    if len(raw) > MAX_PACKET_BYTES:
        raise RouterError(ROUTER_SIZE_CAP, f"packet exceeds {MAX_PACKET_BYTES} bytes")
    packet = parse_strict_json_object(raw, "packet")
    if packet.get("schema_version") != PACKET_SCHEMA:
        raise RouterError(ROUTER_PACKET_INVALID, "packet schema_version is not aeve.task_packet.v1")
    status = packet.get("status")
    if status == "INVALID":
        raise RouterError(ROUTER_PACKET_INVALID, "AEVE reason: " + ascii_excerpt(packet.get("reason", "")))
    if status != "COMPLETE":
        raise RouterError(ROUTER_PACKET_INVALID, "packet status is not COMPLETE")
    check_guards(packet, ROUTER_PACKET_INVALID, "packet")
    if packet.get("role") != request.get("role"):
        raise RouterError(ROUTER_PACKET_INVALID, "packet role differs from the request")
    if packet.get("task_id") != request.get("task_id"):
        raise RouterError(ROUTER_PACKET_INVALID, "packet task_id differs from the request")
    digest = packet.get("request_sha256")
    if not isinstance(digest, str) or not _SHA256_RE.match(digest):
        raise RouterError(ROUTER_PACKET_INVALID, "packet request_sha256 is not a sha256 hex string")
    acceptance = packet.get("acceptance")
    expected = len(request.get("acceptance") or [])
    if not isinstance(acceptance, list) or len(acceptance) != expected:
        raise RouterError(ROUTER_PACKET_INVALID, "packet acceptance count differs from the request")
    for index, item in enumerate(acceptance, 1):
        match = _AC_RE.match(item.get("id", "")) if isinstance(item, dict) and isinstance(item.get("id"), str) else None
        if match is None or int(match.group(1)) != index:
            raise RouterError(ROUTER_PACKET_INVALID, "packet acceptance ids are not AC-1..AC-n in order")
    if not isinstance(packet.get("scope"), dict) or not isinstance(packet.get("files"), dict):
        raise RouterError(ROUTER_PACKET_INVALID, "packet scope or files is not an object")
    return packet
