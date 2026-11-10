"""U3-5: bridge from the no-skip QA verifier (gate_check) to the VST gate's artifact_resolver hook.

tools/vst/gate.py already denies a deciding TestRun receipt whose artifact_digests do not equal
artifact_resolver(path), and denies by default when no resolver is given. Nothing built a resolver, so a
skipped / uncollected required test could still be offered to the gate. make_qa_artifact_resolver closes that
gap: a path under docs/sdlc/evidence/qa/ resolves to a digest ONLY when the lane report behind it is
APPROVABLE according to tools.qa.gate_check.check_report for the expected head.

This module adds no gate authority, no keys and no waiver path. It never signs, never waives and never raises
out of the resolver: every failure is "None" (the gate then reports a digest mismatch). Waivers stay governed
by tools/vst/gate.py and ADR-0001.
"""

from __future__ import annotations

import os
import posixpath
import re
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.qa import run as _run
from tools.qa.gate_check import APPROVABLE, NON_APPROVING, GateCheck, check_report, select_record
from tools.qa.registry import ValidatedRegistry
from tools.qa.report import sha256_bytes


EVIDENCE_DIR = "docs/sdlc/evidence/qa"
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_ARTIFACT_FILE_BYTES = 32 * 1024 * 1024
MAX_DETAIL_CHARS = 200
BRIDGE_CODES = frozenset({
    "REPORT_UNREADABLE", "CATEGORY_PATH_MISMATCH", "BAD_EXPECTED_HEAD", "EVIDENCE_TOO_LARGE",
})

_KINDS = {"report.jsonl": "report", "stdout.txt": "stdout", "stderr.txt": "stderr"}
_QA_PATH = re.compile(
    r"docs/sdlc/evidence/qa/(?P<category>[a-z][a-z0-9-]{0,31})\.(?P<kind>report\.jsonl|stdout\.txt|stderr\.txt)\Z"
)
_CATEGORY = re.compile(r"[a-z][a-z0-9-]{0,31}\Z")
_HEAD = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_FALLBACK_SAFE = re.compile(r"[A-Za-z0-9_./-]+\Z")
_ABS_IN_TEXT = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|(?:(?<=\s)|^)/)[^\s'\"]*")
_QA_SEGMENTS = tuple(EVIDENCE_DIR.split("/"))
_REPARSE_POINT = 0x400


class _BridgeReadError(Exception):
    """Internal: an evidence file cannot be read under the bridge's safety rules."""


class _TooLarge(_BridgeReadError):
    """Internal: an evidence file is larger than its cap."""


@dataclass(frozen=True)
class _Loaded:
    check: GateCheck
    raw: Mapping[str, bytes | bytearray]  # full file bytes by kind; empty unless the check is APPROVABLE


def _non_approving(code: str, detail: str) -> GateCheck:
    return GateCheck(NON_APPROVING, ((code, detail),))


def _is_link_like(info: Any) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def read_regular_file(root: Path, relative: str, cap: int) -> bytes | bytearray:
    """Read one repo-relative posix path with the bridge's no-link rules; also usable by a fallback resolver.

    No symlink / junction / reparse point on any component, directories on the way, a regular file with one
    hard link, the opened file is the lstat'ed file, size at most ``cap`` (else _TooLarge), read into one
    preallocated buffer. Raises OSError or an internal error; callers must fail closed.
    """
    current = root
    parts = relative.split("/")
    info: Any = None
    for index, part in enumerate(parts):
        current = current / part
        info = os.lstat(current)
        if _is_link_like(info):
            raise _BridgeReadError("a path component is a link or reparse point")
        if index == len(parts) - 1:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise _BridgeReadError("evidence file is not a unique regular file")
        elif not stat.S_ISDIR(info.st_mode):
            raise _BridgeReadError("a path component is not a directory")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(current, flags)
    with os.fdopen(fd, "rb", buffering=0) as handle:
        opened = os.fstat(handle.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise _BridgeReadError("evidence file is not a unique regular file")
        if (opened.st_ino, opened.st_dev) != (info.st_ino, info.st_dev):
            raise _BridgeReadError("the opened file is not the file that was checked")
        size = opened.st_size
        if size > cap:
            raise _TooLarge("evidence file exceeds the size bound")
        buffer = bytearray(size)
        view = memoryview(buffer)
        filled = 0
        while filled < size:
            count = handle.readinto(view[filled:])
            if not count:
                break
            filled += count
        if filled != size or handle.read(1):
            raise _BridgeReadError("evidence file changed while being read")
    return buffer


def _range_slice(data: bytes | bytearray, rng: Any) -> bytes:
    """The run's appended range; it must be the tail of the file (a later append would be a later record)."""
    if not isinstance(rng, dict) or set(rng) != {"start", "end"}:
        raise _BridgeReadError("artifact range is missing or malformed")
    start, end = rng["start"], rng["end"]
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (start, end)):
        raise _BridgeReadError("artifact range bounds are not integers")
    if not 0 <= start <= end == len(data):
        raise _BridgeReadError("artifact range is not the tail of the artifact file")
    return bytes(data[start:end])


def _sanitize(text: str) -> str:
    patterns = (_run._SENSITIVE, _run._BEARER, _run._TOKENS, _run._PEM_OPEN, _run._USER_PATH,
                _run._USER_PATH_FWD, _ABS_IN_TEXT)
    for pattern in patterns:
        text = pattern.sub("<redacted>", text)
    return text[:MAX_DETAIL_CHARS]


def _clean(check: GateCheck) -> GateCheck:
    return GateCheck(check.verdict, tuple((str(code), _sanitize(str(detail))) for code, detail in check.reasons))


def _paths(category: str) -> dict[str, str]:
    return {kind: f"{EVIDENCE_DIR}/{category}.{suffix}" for suffix, kind in _KINDS.items()}


def _load(repo_root: str | os.PathLike[str], category: str, expected_head: str,
          registry: ValidatedRegistry) -> _Loaded:
    """The single read-and-verify code path shared by the resolver and qa_gate_reasons. Never raises."""
    try:
        loaded = _load_inner(repo_root, category, expected_head, registry)
        return _Loaded(_clean(loaded.check), loaded.raw if loaded.check.approvable else {})
    except Exception as exc:  # fail closed: nothing here may become an approval
        return _Loaded(_non_approving("REPORT_UNREADABLE", f"bridge failure ({type(exc).__name__})"), {})


def _load_inner(repo_root: str | os.PathLike[str], category: str, expected_head: str,
                registry: ValidatedRegistry) -> _Loaded:
    if not isinstance(expected_head, str) or not _HEAD.fullmatch(expected_head):
        return _Loaded(_non_approving("BAD_EXPECTED_HEAD", "expected head is not a full lowercase hex commit id"), {})
    if not isinstance(category, str) or not _CATEGORY.fullmatch(category) or (
        category not in registry.category_profile_test_ids
    ):
        return _Loaded(_non_approving("UNKNOWN_CATEGORY", "category is not in the registry's closed set"), {})
    root = Path(repo_root).resolve(strict=True)
    if not root.is_dir():
        return _Loaded(_non_approving("REPORT_UNREADABLE", "repository root is not a directory"), {})
    paths = _paths(category)
    try:
        report_raw = read_regular_file(root, paths["report"], MAX_REPORT_BYTES)
        stdout_raw = read_regular_file(root, paths["stdout"], MAX_ARTIFACT_FILE_BYTES)
        stderr_raw = read_regular_file(root, paths["stderr"], MAX_ARTIFACT_FILE_BYTES)
        record = select_record([bytes(line) for line in report_raw.splitlines()])
    except _TooLarge:
        return _Loaded(_non_approving(
            "EVIDENCE_TOO_LARGE", "append-only evidence exceeds the size cap; an operator archive step is required"), {})
    except (OSError, ValueError, _BridgeReadError) as exc:
        return _Loaded(_non_approving("REPORT_UNREADABLE", f"evidence could not be read ({type(exc).__name__})"), {})
    raw = {"report": report_raw, "stdout": stdout_raw, "stderr": stderr_raw}
    # The record's digests cover only the byte range this run appended to the append-only artifacts.
    try:
        ranges = record.get("artifact_ranges")
        if not isinstance(ranges, dict):
            raise _BridgeReadError("artifact_ranges is missing")
        artifact_bytes = {
            "stdout": _range_slice(stdout_raw, ranges.get("stdout")),
            "stderr": _range_slice(stderr_raw, ranges.get("stderr")),
        }
    except _BridgeReadError as exc:
        return _Loaded(_non_approving("ARTIFACT_UNVERIFIED", str(exc)), {})
    check = check_report(record, registry, expected_head=expected_head, artifact_bytes=artifact_bytes)
    extra: list[tuple[str, str]] = []
    if record.get("category") != category:
        extra.append(("CATEGORY_PATH_MISMATCH", "the record's category differs from the report path's category"))
    recorded_paths = record.get("artifact_paths")
    if not isinstance(recorded_paths, dict) or any(
        recorded_paths.get(kind) != paths[kind] for kind in ("report", "stdout", "stderr")
    ):
        extra.append(("ARTIFACT_INVENTORY", "recorded artifact paths differ from the fixed category paths"))
    if extra:
        check = GateCheck(NON_APPROVING, tuple(check.reasons) + tuple(extra))
    return _Loaded(check, raw)


def qa_gate_reasons(
    repo_root: str | os.PathLike[str], category: str, *, expected_head: str, registry: ValidatedRegistry
) -> GateCheck:
    """Diagnostics: the typed verdict the resolver would act on for one category. Never raises.

    Reason details are redacted (secret / absolute-path patterns) and bounded to MAX_DETAIL_CHARS.
    """
    return _load(repo_root, category, expected_head, registry).check


def _qa_segments_in(path: str) -> bool:
    parts = [p for p in path.replace("\\", "/").casefold().split("/") if p not in {"", "."}]
    width = len(_QA_SEGMENTS)
    return any(tuple(parts[i:i + width]) == _QA_SEGMENTS for i in range(len(parts) - width + 1))


def _is_qa_owned(path: str) -> bool:
    """True when the raw or the normalized spelling names a location inside the QA evidence directory."""
    normalized = posixpath.normpath(path.replace("\\", "/"))
    return _qa_segments_in(path) or _qa_segments_in(normalized)


def _fallback_eligible(path: str) -> bool:
    """Allowlist for handing a path to the caller's fallback: a plain, canonical, relative, non-QA path."""
    if not _FALLBACK_SAFE.fullmatch(path) or path.startswith("/"):
        return False
    if any(seg in {"", ".", ".."} or seg.endswith(".") for seg in path.split("/")):
        return False
    if posixpath.normpath(path) != path:
        return False
    return not _is_qa_owned(path)


def _fingerprint(root: Path, category: str) -> tuple[Any, ...] | None:
    try:
        rows = []
        for relative in _paths(category).values():
            info = os.lstat(root.joinpath(*relative.split("/")))
            rows.append((info.st_size, info.st_mtime_ns, info.st_ino, info.st_mode))
        return tuple(rows)
    except Exception:  # noqa: BLE001 - no fingerprint, no reuse
        return None


def make_qa_artifact_resolver(
    repo_root: str | os.PathLike[str],
    *,
    expected_head: str,
    registry: ValidatedRegistry,
    fallback: Callable[[str], str | None] | None = None,
) -> Callable[[str], str | None]:
    """Build the gate's artifact_resolver for QA evidence.

    - Exact QA report / stdout / stderr path of a category in the registry's closed set: the sha256 of the
      file's raw bytes, only when that category's report is APPROVABLE for expected_head and the record's
      category equals the path's category. Anything else: None.
    - Any other spelling that names the QA directory (traversal, absolute, backslash, case, unknown category
      or suffix, non-str): None, never the fallback.
    - Any other path: fallback(path) only if it is a plain canonical relative path (allowlist above) outside
      the QA directory; the fallback result must be 64 lowercase hex or it becomes None. Anything not
      eligible: None. A fallback reading files must use read_regular_file (no-link reader).

    One loaded snapshot per category is reused inside this resolver instance while the three files'
    (size, mtime_ns, inode, mode) are unchanged, so the report, stdout and stderr digests that belong to one
    receipt come from one verified snapshot.
    """
    cache: dict[str, tuple[tuple[Any, ...], _Loaded]] = {}

    def load(category: str) -> _Loaded:
        root = Path(repo_root).resolve(strict=True)
        before = _fingerprint(root, category)
        hit = cache.get(category)
        if before is not None and hit is not None and hit[0] == before:
            return hit[1]
        loaded = _load(repo_root, category, expected_head, registry)
        if before is not None and _fingerprint(root, category) == before:
            cache[category] = (before, loaded)
        else:
            cache.pop(category, None)
        return loaded

    def resolve(path: str) -> str | None:
        try:
            if not isinstance(path, str):
                return None
            if _is_qa_owned(path):
                match = _QA_PATH.fullmatch(path)
                if match is None:
                    return None
                loaded = load(match.group("category"))
                if not loaded.check.approvable:
                    return None
                return sha256_bytes(bytes(loaded.raw[_KINDS[match.group("kind")]]))
            if fallback is None or not _fallback_eligible(path):
                return None
            value = fallback(path)
            return value if isinstance(value, str) and _DIGEST.fullmatch(value) else None
        except Exception:  # fail closed
            return None

    return resolve


__all__ = [
    "APPROVABLE", "BRIDGE_CODES", "EVIDENCE_DIR", "MAX_ARTIFACT_FILE_BYTES", "MAX_DETAIL_CHARS",
    "MAX_REPORT_BYTES", "make_qa_artifact_resolver", "qa_gate_reasons", "read_regular_file",
]
