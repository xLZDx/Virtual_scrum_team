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
import re
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.qa.gate_check import APPROVABLE, NON_APPROVING, GateCheck, check_report, select_record
from tools.qa.registry import ValidatedRegistry
from tools.qa.report import sha256_bytes


EVIDENCE_DIR = "docs/sdlc/evidence/qa"
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_ARTIFACT_FILE_BYTES = 32 * 1024 * 1024
BRIDGE_CODES = frozenset({"REPORT_UNREADABLE", "CATEGORY_PATH_MISMATCH", "BAD_EXPECTED_HEAD"})

_KINDS = {"report.jsonl": "report", "stdout.txt": "stdout", "stderr.txt": "stderr"}
_QA_PATH = re.compile(
    r"docs/sdlc/evidence/qa/(?P<category>[a-z][a-z0-9-]{0,31})\.(?P<kind>report\.jsonl|stdout\.txt|stderr\.txt)\Z"
)
_CATEGORY = re.compile(r"[a-z][a-z0-9-]{0,31}\Z")
_HEAD = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_QA_SEGMENTS = tuple(EVIDENCE_DIR.split("/"))
_REPARSE_POINT = 0x400


class _BridgeReadError(Exception):
    """Internal: an evidence file cannot be read under the bridge's safety rules."""


@dataclass(frozen=True)
class _Loaded:
    check: GateCheck
    raw: Mapping[str, bytes]  # full file bytes by kind (report/stdout/stderr); empty unless all three were read


def _non_approving(code: str, detail: str) -> GateCheck:
    return GateCheck(NON_APPROVING, ((code, detail),))


def _is_link_like(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _read_regular(root: Path, relative: str, cap: int) -> bytes:
    """Read one repo-relative posix path: no link/junction on any component, regular file, bounded size."""
    current = root
    parts = relative.split("/")
    for index, part in enumerate(parts):
        current = current / part
        info = os.lstat(current)
        if _is_link_like(info):
            raise _BridgeReadError("a path component is a link or reparse point")
        last = index == len(parts) - 1
        if last:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise _BridgeReadError("evidence file is not a unique regular file")
        elif not stat.S_ISDIR(info.st_mode):
            raise _BridgeReadError("a path component is not a directory")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(current, flags)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise _BridgeReadError("evidence file is not a unique regular file")
        if opened.st_size > cap:
            raise _BridgeReadError("evidence file exceeds the size bound")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                raise _BridgeReadError("evidence file exceeds the size bound")
            chunks.append(chunk)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if len(data) != opened.st_size:
        raise _BridgeReadError("evidence file changed while being read")
    return data


def _range_slice(data: bytes, rng: Any) -> bytes:
    if not isinstance(rng, dict) or set(rng) != {"start", "end"}:
        raise _BridgeReadError("artifact range is missing or malformed")
    start, end = rng["start"], rng["end"]
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (start, end)):
        raise _BridgeReadError("artifact range bounds are not integers")
    if not 0 <= start <= end <= len(data):
        raise _BridgeReadError("artifact range lies outside the artifact file")
    return data[start:end]


def _load(repo_root: str | os.PathLike[str], category: str, expected_head: str,
          registry: ValidatedRegistry) -> _Loaded:
    """The single read-and-verify code path shared by the resolver and qa_gate_reasons. Never raises."""
    try:
        if not isinstance(expected_head, str) or not _HEAD.fullmatch(expected_head):
            return _Loaded(_non_approving("BAD_EXPECTED_HEAD", "expected head is not a full lowercase hex commit id"), {})
        if not isinstance(category, str) or not _CATEGORY.fullmatch(category) or (
            category not in registry.category_profile_test_ids
        ):
            return _Loaded(_non_approving("UNKNOWN_CATEGORY", "category is not in the registry's closed set"), {})
        root = Path(repo_root).resolve(strict=True)
        if not root.is_dir():
            return _Loaded(_non_approving("REPORT_UNREADABLE", "repository root is not a directory"), {})
        paths = {kind: f"{EVIDENCE_DIR}/{category}.{suffix}" for suffix, kind in _KINDS.items()}
        try:
            report_raw = _read_regular(root, paths["report"], MAX_REPORT_BYTES)
            stdout_raw = _read_regular(root, paths["stdout"], MAX_ARTIFACT_FILE_BYTES)
            stderr_raw = _read_regular(root, paths["stderr"], MAX_ARTIFACT_FILE_BYTES)
            record = select_record(report_raw.splitlines())
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
        return _Loaded(check, raw if check.approvable else {})
    except Exception as exc:  # fail closed: nothing here may become an approval
        return _Loaded(_non_approving("REPORT_UNREADABLE", f"bridge failure ({type(exc).__name__})"), {})


def qa_gate_reasons(
    repo_root: str | os.PathLike[str], category: str, *, expected_head: str, registry: ValidatedRegistry
) -> GateCheck:
    """Diagnostics: the typed verdict the resolver would act on for one category. Never raises."""
    return _load(repo_root, category, expected_head, registry).check


def _is_qa_owned(path: str) -> bool:
    """True when the path names, in any spelling, a location inside the QA evidence directory.

    Backslashes, '.', empty segments and letter case are normalized, and the directory may appear after a
    prefix (absolute path) or before '..' segments: all of these are QA-owned and therefore strict-or-None,
    never handed to the fallback.
    """
    parts = [p for p in path.replace("\\", "/").casefold().split("/") if p not in {"", "."}]
    width = len(_QA_SEGMENTS)
    return any(tuple(parts[i:i + width]) == _QA_SEGMENTS for i in range(len(parts) - width + 1))


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
    - Any other path under docs/sdlc/evidence/qa/ (traversal, absolute, backslash, unknown category or
      suffix, non-str): None.
    - A path outside that directory: fallback(path) when given (an exception or non-str result becomes
      None), else None.
    """

    def resolve(path: str) -> str | None:
        try:
            if not isinstance(path, str):
                return None
            if not _is_qa_owned(path):
                if fallback is None:
                    return None
                value = fallback(path)
                return value if isinstance(value, str) else None
            match = _QA_PATH.fullmatch(path)
            if match is None:
                return None
            loaded = _load(repo_root, match.group("category"), expected_head, registry)
            if not loaded.check.approvable:
                return None
            return sha256_bytes(loaded.raw[_KINDS[match.group("kind")]])
        except Exception:  # fail closed
            return None

    return resolve


__all__ = [
    "APPROVABLE", "BRIDGE_CODES", "EVIDENCE_DIR", "MAX_ARTIFACT_FILE_BYTES", "MAX_REPORT_BYTES",
    "make_qa_artifact_resolver", "qa_gate_reasons",
]
