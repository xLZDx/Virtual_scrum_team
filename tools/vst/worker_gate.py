"""U5-1: S3 worker output through the deterministic diff gate (Windows-local, no WSL).

Fail closed on every error. Verdicts:

* ACCEPTED - the deterministic diff gate passed, no path hazard, no protected path,
  every change inside the declared scope, the diff text is fully valid git diff grammar and
  agrees with the declared changed paths, and every required isolation property is
  VERIFIED (or CALLER_ASSERTED where only a caller-reported value exists; listed in the proof).
* REFUSED  - a definite policy violation (out of scope, protected path, path trick,
  link/submodule/non-standard mode, diff/paths mismatch, isolation property FAILED, diff gate FAIL).
* BLOCKED  - the decision cannot be made (malformed or missing worker output, missing
  or broken diff gate, unparsable or oversized diff, unverifiable required isolation property,
  unexpected exception). BLOCKED is never an acceptance. If refusal and block reasons both
  exist the verdict is REFUSED and both are listed.

The diff gate (tools/vst/diffgate.py) is reused unchanged. It cannot express: case-folded
scope comparison, a protected path that is also listed as allowed, Windows aliases (8.3 names,
trailing dots/spaces, device names, NTFS streams), or checking the diff text against the
declared paths. This module adds those checks on top and refuses; it never relaxes the gate.
The module checks consistency of what it is given, not provenance. The isolation proof is a
statement of what was checked, not an OS sandbox.
"""
from __future__ import annotations

import importlib
import os
import re
import stat
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .worker_adapter import WorkerResponse, WorkerState

ACCEPTED = "ACCEPTED"
REFUSED = "REFUSED"
BLOCKED = "BLOCKED"

PROOF_SCHEMA = "vst-worker-isolation-proof-v1"
ISOLATION_MODE = "windows-local-no-wsl"
VERIFIED = "VERIFIED"            # computed here from the file system or the data itself
CALLER_ASSERTED = "CALLER_ASSERTED"  # only a caller-reported value was compared
NOT_VERIFIED = "NOT_VERIFIED"    # not checked, or the check could not complete
FAILED = "FAILED"                # checked and violated

MAX_DIFF_BYTES = 8 * 1024 * 1024
MAX_HEADER_LINE = 4096
MAX_CHANGED_PATHS = 128

# Always protected, on top of the caller list and of diffgate.is_blocked_path.
DEFAULT_PROTECTED_COMPONENTS = (".git", ".github", ".gitlab", ".hooks", ".husky", ".harness", ".claude")  # any depth
DEFAULT_PROTECTED_BASENAMES = ("AGENTS.md", "CLAUDE.md", ".gitattributes", ".gitmodules")  # any depth
DEFAULT_PROTECTED_PREFIXES = ("tools/vst", ".harness-tools")  # repository root prefix

REQUIRED_PROPERTIES = (
    "worktree_separate_from_main_checkout",
    "base_commit_pinned",
    "worktree_head_matches_candidate",
    "network_flag_not_requested",
    "paths_normalized",
    "link_and_reparse_point_check_on_changed_paths",
)
# Properties that can only ever be CALLER_ASSERTED (never VERIFIED) because only caller strings exist.
CALLER_ONLY_PROPERTIES = ("base_commit_pinned", "worktree_head_matches_candidate", "network_flag_not_requested")

# Properties this module does NOT check. Always listed NOT_VERIFIED, never promotable.
NOT_VERIFIED_PROPERTIES = {
    "os_sandbox": "no OS sandbox or job object is applied or inspected on Windows-local without WSL",
    "process_containment": "worker process tree is not contained or enumerated; it may spawn processes",
    "network_enforcement": "only the request flag is read; no firewall or network namespace is verified",
    "worker_identity_separation": "tools/vst/sandbox.py identity checks are POSIX-only; no distinct Windows identity or ACL is verified",
    "writes_outside_worktree": "writes by the worker outside the worktree are not detected",
    "resource_limits": "CPU, memory, disk and time limits are not verified at the OS level",
    "short_name_aliases_on_disk": "8.3 aliases are refused by name pattern only; GetShortPathName is not queried",
    "check_time_vs_use_time": "link checks are a point-in-time lstat walk; later changes are not detected",
    "rename_and_symlink_evidence_completeness": "the adapter reports no rename or link data; it is derived from the diff text and the caller",
}

_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_DRIVE = re.compile(r"[A-Za-z]:")
_SHORT_NAME = re.compile(r"~\d")
_BAD_CHARS = set('<>"|?*')
_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"} | {
    f"{prefix}{digit}" for prefix in ("COM", "LPT") for digit in "0123456789¹²³"
}
_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?\Z")
_MODE_LINE = re.compile(r"(old mode|new mode|deleted file mode|new file mode) (\d{6})\Z")
_INDEX_LINE = re.compile(r"index [0-9a-f]{7,64}\.\.[0-9a-f]{7,64}(?: (\d{6}))?\Z")
_SIMILARITY = re.compile(r"(?:dis)?similarity index \d{1,3}%\Z")
_BINARY_FILES = re.compile(r"Binary files .+ and .+ differ\Z")
_STANDARD_MODES = ("100644", "100755")
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class _Blocked(Exception):
    """Internal: the decision cannot be made."""


def _show(value: object) -> str:
    """Safe echo of untrusted text in a reason detail."""
    return ascii(value)[:200]


@dataclass(frozen=True)
class IsolationContext:
    """What the caller states about the isolated worktree; the proof checks what it can."""

    worktree_root: str
    main_checkout_root: str
    network_requested: bool
    pinned_base_head: str  # commit the caller states the worktree was created at (caller-reported)
    worktree_head: str | None = None  # HEAD the caller states the worktree has now (caller-reported)
    lstat: Callable[[str], Any] = field(default=os.lstat, compare=False)
    realpath: Callable[[str], str] = field(default=os.path.realpath, compare=False)


@dataclass(frozen=True)
class WorkerGateVerdict:
    verdict: str
    reasons: tuple[tuple[str, str], ...]
    diff_evidence: dict | None
    isolation_proof: dict | None

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "reasons": [{"code": c, "detail": d} for c, d in self.reasons],
            "diff_evidence": self.diff_evidence,
            "isolation_proof": self.isolation_proof,
        }


# ---------------------------------------------------------------------------- path hazards
def path_hazards(path: object) -> list[str]:
    """Return hazard codes for one repo-relative path; an empty list means no hazard found.

    A ``.git`` component is not a hazard here: it is a protected path (PROTECTED_PATH).
    """
    if not isinstance(path, str) or not path:
        return ["MALFORMED_PATH"]
    found: list[str] = []
    if "\0" in path or any(ord(ch) < 32 or ord(ch) == 0x7F for ch in path):
        found.append("CONTROL_CHARACTER")
    if path.startswith(("\\\\", "//")):
        found.append("UNC_PATH")
    elif path.startswith(("\\", "/")):
        found.append("ABSOLUTE_PATH")
    if _DRIVE.match(path):
        found.append("DRIVE_LETTER")
    if "\\" in path:
        found.append("BACKSLASH")
    if len(path.encode("utf-8", "surrogatepass")) > 512:
        found.append("PATH_TOO_LONG")
    for part in path.replace("\\", "/").split("/"):
        if part in ("", ".", ".."):
            found.append("TRAVERSAL_OR_EMPTY_COMPONENT")
            continue
        if ":" in part:
            found.append("ALTERNATE_DATA_STREAM_OR_DRIVE")
        if part.endswith((".", " ")):
            found.append("TRAILING_DOT_OR_SPACE")
        if _BAD_CHARS & set(part):
            found.append("RESERVED_CHARACTER")
        if part.split(".")[0].rstrip(" ").upper() in _RESERVED:
            found.append("RESERVED_DEVICE_NAME")
        if _SHORT_NAME.search(part):
            found.append("SHORT_NAME_ALIAS")
        if unicodedata.normalize("NFKC", part) != part:
            found.append("UNICODE_COMPATIBILITY_FORM")
        if len(part) > 255:
            found.append("COMPONENT_TOO_LONG")
    return list(dict.fromkeys(found))


def _fold_key(path: str) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFKC", p).casefold() for p in path.split("/"))


def _protect_parts(path: str) -> tuple[str, ...]:
    """Case-folded components with Windows stream suffixes and trailing dots/spaces removed."""
    parts = []
    for part in path.replace("\\", "/").split("/"):
        part = unicodedata.normalize("NFKC", part.split(":", 1)[0]).casefold()
        parts.append(part.rstrip(". "))
    return tuple(parts)


def _entry_problem(entry: object) -> str | None:
    """Weak check for a protected-path entry: it may name `.git`, so no canonical-path rule."""
    if not isinstance(entry, str) or not entry:
        return "empty or non-string entry"
    value = entry[:-1] if entry.endswith("/") else entry
    if not value or "\\" in value or "\0" in value or value.startswith("/") or _DRIVE.match(value):
        return "empty, backslash, NUL, absolute or drive-letter entry"
    if any(part in ("", ".", "..") for part in value.split("/")):
        return "traversal or empty component"
    return None


_DEFAULT_COMPONENT_SET = frozenset(c.casefold() for c in DEFAULT_PROTECTED_COMPONENTS)
_DEFAULT_BASENAME_SET = frozenset(b.casefold() for b in DEFAULT_PROTECTED_BASENAMES)
_DEFAULT_PREFIX_KEYS = tuple(_protect_parts(p) for p in DEFAULT_PROTECTED_PREFIXES)


def _caller_keys(entries: list[str]) -> list[tuple[str, ...]]:
    keys = []
    for entry in entries:
        problem = _entry_problem(entry)
        if problem:
            raise _Blocked(f"protected path entry is malformed ({problem}): {_show(entry)}")
        keys.append(_protect_parts(entry[:-1] if entry.endswith("/") else entry))
    return keys


def _is_protected(path: str, caller_keys: list[tuple[str, ...]]) -> bool:
    parts = _protect_parts(path)
    if _DEFAULT_COMPONENT_SET & set(parts) or parts[-1] in _DEFAULT_BASENAME_SET:
        return True
    return any(parts[: len(key)] == key for key in list(_DEFAULT_PREFIX_KEYS) + caller_keys)


# ---------------------------------------------------------------------------- diff text
def parse_diff_paths(diff_bytes: bytes) -> dict:
    """Validate the whole diff as git diff grammar and extract path facts.

    Accepted grammar only: optional blank lines, then `diff --git` blocks made of extended
    header lines (modes, index, similarity, rename/copy), optional `---`/`+++`, hunks whose
    line counts match their `@@` header, `Binary files ... differ`, or `GIT binary patch`.
    Anything else (preamble text, stray `---`/`+++`, `diff --cc`, truncated or over-long
    hunks, quoted paths, oversize input) raises _Blocked.
    """
    if not isinstance(diff_bytes, bytes) or len(diff_bytes) > MAX_DIFF_BYTES:
        raise _Blocked("diff is not bytes or exceeds the size cap")
    try:
        text = diff_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _Blocked("diff is not valid UTF-8") from exc
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    blocks: list[dict] = []
    state = "pre"
    old_rem = new_rem = 0
    for line in lines:
        if state == "hunk":
            first = line[:1]
            if first == " ":
                old_rem -= 1
                new_rem -= 1
            elif first == "-":
                old_rem -= 1
            elif first == "+":
                new_rem -= 1
            elif first != "\\":
                raise _Blocked("hunk body is shorter than its header says")
            if old_rem < 0 or new_rem < 0:
                raise _Blocked("hunk body is longer than its header says")
            if old_rem == 0 and new_rem == 0:
                state = "between"
            continue
        if state == "binary" and not line.startswith("diff --git "):
            continue
        if len(line) > MAX_HEADER_LINE:
            raise _Blocked("header line exceeds the size cap")
        if line.startswith("diff --git "):
            if state in ("minus", "post"):
                raise _Blocked("block ends after --- without hunks")
            rest = line[len("diff --git "):]
            if '"' in rest or not rest.startswith("a/"):
                raise _Blocked("diff header is quoted or not in a/ b/ form")
            pairs = [(rest[2:i], rest[i + 3:]) for i in range(len(rest)) if rest.startswith(" b/", i)]
            equal = [p for p in pairs if p[0] == p[1]]
            pair = pairs[0] if len(pairs) == 1 else (equal[0] if len(equal) == 1 else None)
            blocks.append({"pair": pair, "rename": [None, None], "copy": [None, None],
                           "modes": [], "minus": None, "plus": None})
            state = "head"
            continue
        if state == "pre":
            if line == "":
                continue
            raise _Blocked("text before the first diff header")
        block = blocks[-1]
        if state == "head":
            match_mode = _MODE_LINE.fullmatch(line)
            match_index = _INDEX_LINE.fullmatch(line)
            if match_mode:
                block["modes"].append((match_mode.group(1), match_mode.group(2)))
            elif match_index:
                if match_index.group(1):
                    block["modes"].append(("index", match_index.group(1)))
            elif _SIMILARITY.fullmatch(line):
                pass
            elif line.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
                kind, word, value = line.split(" ", 2)
                if value.startswith('"') or not value:
                    raise _Blocked("quoted or empty rename/copy path")
                block[kind][0 if word == "from" else 1] = value
            elif line.startswith("--- "):
                block["minus"] = line[4:]
                state = "minus"
            elif _BINARY_FILES.fullmatch(line):
                state = "done"
            elif line == "GIT binary patch":
                state = "binary"
            else:
                raise _Blocked("unrecognised diff header line")
            continue
        if state == "minus":
            if not line.startswith("+++ "):
                raise _Blocked("--- line without +++ line")
            block["plus"] = line[4:]
            state = "post"
            continue
        if state in ("post", "between"):
            if state == "between" and line.startswith("\\"):
                continue
            match = _HUNK.fullmatch(line)
            if not match:
                raise _Blocked("line outside any recognised diff block grammar")
            old_rem = int(match.group(2)) if match.group(2) is not None else 1
            new_rem = int(match.group(4)) if match.group(4) is not None else 1
            state = "between" if old_rem == 0 and new_rem == 0 else "hunk"
            continue
        raise _Blocked("line outside any recognised diff block grammar")
    if state in ("hunk", "minus", "post") or not blocks:
        raise _Blocked("diff is empty, truncated or has no diff header")

    paths: set[str] = set()
    renames: list[tuple[str, str]] = []
    links: set[str] = set()
    gitlinks: set[str] = set()
    badmodes: set[str] = set()
    removed: set[str] = set()
    for block in blocks:
        if all(block["rename"]):
            old_path, new_path = block["rename"]
            current = {old_path, new_path}
            renames.append((old_path, new_path))
            removed.add(old_path)
        elif all(block["copy"]):
            old_path, new_path = block["copy"]
            current = {new_path}
        elif any(block["rename"]) or any(block["copy"]):
            raise _Blocked("incomplete rename or copy header")
        elif block["pair"] is not None and block["pair"][0] == block["pair"][1]:
            old_path = new_path = block["pair"][1]
            current = {new_path}
        else:
            raise _Blocked("diff header paths are ambiguous")
        if block["pair"] is not None and (all(block["rename"]) or all(block["copy"])) \
                and block["pair"] != (old_path, new_path):
            raise _Blocked("diff header disagrees with its rename/copy lines")
        for marker, value, expected in (("minus", block["minus"], old_path), ("plus", block["plus"], new_path)):
            if value is None:
                continue
            value = value[:-1] if value.endswith("\t") else value
            if value != "/dev/null" and value != ("a/" if marker == "minus" else "b/") + expected:
                raise _Blocked("---/+++ path disagrees with the diff header")
        for kind, mode in block["modes"]:
            if kind == "deleted file mode":
                removed.add(new_path)
            if mode == "120000":
                links |= current
            elif mode == "160000":
                gitlinks |= current
            elif mode not in _STANDARD_MODES:
                badmodes |= current
        paths |= current
        if len(paths) > MAX_CHANGED_PATHS:
            raise _Blocked("diff names more paths than the cap")
    return {"paths": paths, "renames": renames, "links": links, "gitlinks": gitlinks,
            "badmodes": badmodes, "removed": removed}


# ---------------------------------------------------------------------------- isolation proof
def build_isolation_proof(
    *, context: IsolationContext, base_head: object, manifest_base_head: object,
    changed_paths: Iterable[str], candidate_head: object = None, removed_paths: Iterable[str] = (),
) -> dict:
    """List what was checked (VERIFIED / CALLER_ASSERTED / FAILED / NOT_VERIFIED) and what never is."""
    props: dict[str, dict] = {}

    def put(name: str, status: str, detail: str) -> None:
        props[name] = {"property": name, "status": status, "detail": detail}

    paths = sorted(set(changed_paths))
    # 1 worktree separate from main checkout: real resolution, both roots must exist
    name = REQUIRED_PROPERTIES[0]
    try:
        context.lstat(context.worktree_root)
        context.lstat(context.main_checkout_root)
        wt = os.path.normcase(context.realpath(context.worktree_root))
        main = os.path.normcase(context.realpath(context.main_checkout_root))
        if not (os.path.isabs(wt) and os.path.isabs(main)):
            put(name, NOT_VERIFIED, "roots are not absolute paths")
        elif os.path.splitdrive(wt)[0] != os.path.splitdrive(main)[0]:
            put(name, VERIFIED, "resolved roots are on different drives; disjoint")
        elif wt == main or os.path.commonpath([wt, main]) in (wt, main):
            put(name, FAILED, "worktree equals or is nested with the main checkout")
        else:
            put(name, VERIFIED, "both roots exist and their resolved paths are disjoint")
    except (TypeError, ValueError, OSError):
        put(name, NOT_VERIFIED, "a root does not exist or could not be resolved")
    # 2 base commit pinned (caller-reported value compared with the manifest)
    name = REQUIRED_PROPERTIES[1]
    if not (isinstance(base_head, str) and _HEX40.fullmatch(base_head)):
        put(name, NOT_VERIFIED, "caller-reported worktree base is not a lowercase 40-hex commit id")
    elif base_head != manifest_base_head:
        put(name, FAILED, "caller-reported worktree base differs from the manifest base head")
    else:
        put(name, CALLER_ASSERTED, "caller-reported worktree base equals the manifest base head; git was not read")
    # 3 worktree HEAD equals the candidate (caller-reported)
    name = REQUIRED_PROPERTIES[2]
    reported = context.worktree_head
    if not (isinstance(reported, str) and _HEX40.fullmatch(reported)):
        put(name, NOT_VERIFIED, "no caller-reported worktree HEAD")
    elif reported != candidate_head:
        put(name, NOT_VERIFIED, "caller-reported worktree HEAD differs from the candidate head")
    else:
        put(name, CALLER_ASSERTED, "caller-reported worktree HEAD equals the candidate head; git was not read")
    # 4 network flag (request flag only)
    name = REQUIRED_PROPERTIES[3]
    if context.network_requested is False:
        put(name, CALLER_ASSERTED, "request flag network_requested is False; enforcement is NOT verified")
    elif context.network_requested is True:
        put(name, FAILED, "network access was requested")
    else:
        put(name, NOT_VERIFIED, "network_requested is not a boolean")
    # 5 paths normalized
    name = REQUIRED_PROPERTIES[4]
    bad = [p for p in paths if path_hazards(p)]
    if not paths:
        put(name, NOT_VERIFIED, "no changed paths to check")
    elif bad:
        put(name, FAILED, f"{len(bad)} path(s) with hazards")
    else:
        put(name, VERIFIED, f"{len(paths)} path(s) free of the hazards listed in WORKER_GATE.md")
    # 6 links / reparse points
    put(REQUIRED_PROPERTIES[5], *_link_check(context, paths, set(removed_paths)))
    for key, reason in NOT_VERIFIED_PROPERTIES.items():
        put(key, NOT_VERIFIED, reason)
    return {
        "schema": PROOF_SCHEMA,
        "isolation_mode": ISOLATION_MODE,
        "worktree_head_reported": _show(reported),
        "candidate_head": _show(candidate_head),
        "properties": list(props.values()),
    }


def _link_check(context: IsolationContext, paths: list[str], removed: set[str]) -> tuple[str, str]:
    try:
        root_stat = context.lstat(context.worktree_root)
    except (OSError, TypeError, ValueError):
        return NOT_VERIFIED, "worktree root could not be inspected"
    if not hasattr(root_stat, "st_file_attributes"):
        return NOT_VERIFIED, "platform reports no reparse attributes; junctions cannot be detected"
    if not paths:
        return NOT_VERIFIED, "no paths to inspect"
    inspected = 0
    try:
        root_real = os.path.normcase(context.realpath(context.worktree_root))
        for rel in paths:
            current = context.worktree_root
            complete = True
            for part in rel.split("/"):
                current = os.path.join(current, part)
                try:
                    info = context.lstat(current)
                except FileNotFoundError:
                    if rel in removed:
                        complete = False
                        break
                    return NOT_VERIFIED, f"changed path {_show(rel)} does not exist in the worktree"
                inspected += 1
                if not hasattr(info, "st_file_attributes"):
                    return NOT_VERIFIED, "component reports no reparse attributes"
                if stat.S_ISLNK(info.st_mode) or (info.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT):
                    return FAILED, f"link or reparse point on path component {_show(part)}"
            if complete:
                try:
                    real = os.path.normcase(context.realpath(os.path.join(context.worktree_root, *rel.split("/"))))
                    inside = os.path.commonpath([root_real, real]) == root_real
                except ValueError:
                    inside = False
                if not inside:
                    return FAILED, f"resolved path of {_show(rel)} leaves the worktree"
    except (OSError, TypeError, ValueError):
        return NOT_VERIFIED, "link check could not complete"
    if inspected == 0:
        return NOT_VERIFIED, "no path component could be inspected"
    return VERIFIED, f"{inspected} path component(s) of {len(paths)} path(s) inspected at check time"


def proof_is_honest(proof: object) -> bool:
    """True when no entry is promoted: not-checked ones stay NOT_VERIFIED, caller-only ones are never VERIFIED."""
    try:
        items = proof["properties"]
        status = {p["property"]: p["status"] for p in items}
        if len(status) != len(items):
            return False
    except (KeyError, TypeError):
        return False
    known = set(REQUIRED_PROPERTIES) | set(NOT_VERIFIED_PROPERTIES)
    if set(status) != known:
        return False
    if any(status[n] != NOT_VERIFIED for n in NOT_VERIFIED_PROPERTIES):
        return False
    if any(status[n] == VERIFIED for n in CALLER_ONLY_PROPERTIES):
        return False
    return all(value in (VERIFIED, CALLER_ASSERTED, FAILED, NOT_VERIFIED) for value in status.values())


# ---------------------------------------------------------------------------- the gate
def _load_diffgate():
    module = importlib.import_module((__package__ or "tools.vst") + ".diffgate")
    for name in ("check_diff", "is_blocked_path", "normalize_path"):
        if not callable(getattr(module, name, None)):
            raise ImportError(f"diffgate.{name} is missing")
    return module


def _str_seq(value: object, name: str, *, allow_empty: bool) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple, set, frozenset)):
        raise _Blocked(f"{name} must be a list or tuple of strings")
    items = list(value)
    if (not items and not allow_empty) or any(not isinstance(i, str) for i in items):
        raise _Blocked(f"{name} must be a{'' if allow_empty else ' non-empty'} sequence of strings")
    return items


def gate_worker_change(
    *, manifest_sha256: object, base_head: object, candidate_head: object,
    changed_paths: object, allowed_paths: object, protected_paths: object,
    diff_bytes: object, isolation: object,
    symlink_paths: Iterable[str] = (), rename_pairs: Iterable[tuple[str, str]] = (),
) -> WorkerGateVerdict:
    """Run one worker change through the diff gate; never raises, never accepts on error.

    The consumer must apply exactly the ``diff_bytes`` given here; nothing binds them to a
    later copy. Hazardous entries in ``allowed_paths`` never match a change and are not passed
    to the diff gate.
    """
    refuse: list[tuple[str, str]] = []
    block: list[tuple[str, str]] = []
    evidence: dict | None = None
    proof: dict | None = None
    try:
        try:
            gate = _load_diffgate()
        except Exception as exc:  # missing, broken or tampered module
            return _verdict(BLOCKED, [("DIFFGATE_UNAVAILABLE", type(exc).__name__)], None, None)
        if not (isinstance(manifest_sha256, str) and _HEX64.fullmatch(manifest_sha256)):
            raise _Blocked("manifest_sha256 must be lowercase SHA-256")
        if not (isinstance(base_head, str) and _HEX40.fullmatch(base_head)):
            raise _Blocked("base_head must be a lowercase 40-hex commit id")
        if not (isinstance(candidate_head, str) and _HEX40.fullmatch(candidate_head)):
            raise _Blocked("candidate_head must be a lowercase 40-hex commit id")
        if candidate_head == base_head:
            raise _Blocked("candidate_head equals base_head; no worker commit to check")
        if not isinstance(diff_bytes, bytes) or not diff_bytes:
            raise _Blocked("diff_bytes must be non-empty bytes")
        if len(diff_bytes) > MAX_DIFF_BYTES:
            raise _Blocked("diff_bytes exceeds the size cap")
        if not isinstance(isolation, IsolationContext):
            raise _Blocked("isolation context is missing")
        changed = _str_seq(changed_paths, "changed_paths", allow_empty=False)
        if len(set(changed)) > MAX_CHANGED_PATHS:
            raise _Blocked("changed_paths exceeds the path-count cap")
        allowed = _str_seq(allowed_paths, "allowed_paths", allow_empty=False)
        protected = _str_seq(protected_paths, "protected_paths", allow_empty=True)
        extra_links = _str_seq(list(symlink_paths), "symlink_paths", allow_empty=True)
        extra_renames = list(rename_pairs)
        if any(not (isinstance(p, tuple) and len(p) == 2 and all(isinstance(s, str) for s in p)) for p in extra_renames):
            raise _Blocked("rename_pairs must be (source, destination) string pairs")
        try:
            caller_keys = _caller_keys(protected)
        except _Blocked as exc:  # a bad caller entry must not hide refusals
            block.append(("MALFORMED_INPUT", str(exc)))
            caller_keys = []

        # path hazards (Windows aliases, UNC, streams, traversal)
        hazardous = False
        for path in changed:
            for code in path_hazards(path):
                refuse.append((f"PATH_HAZARD_{code}", _show(path)))
                hazardous = True
        # diff text must be valid git diff grammar and agree with the declared paths
        removed: set[str] = set()
        try:
            parsed = parse_diff_paths(diff_bytes)
        except _Blocked as exc:
            block.append(("DIFF_UNPARSABLE", str(exc)))
            parsed = None
        if parsed is not None:
            if parsed["paths"] != set(changed):
                refuse.append(("DIFF_PATH_MISMATCH", "declared changed paths differ from paths in the diff text"))
            if parsed["gitlinks"]:
                refuse.append(("SUBMODULE_CHANGE", _show(sorted(parsed["gitlinks"]))))
            if parsed["badmodes"]:
                refuse.append(("NONSTANDARD_MODE", _show(sorted(parsed["badmodes"]))))
            extra_links = list(extra_links) + sorted(parsed["links"])
            extra_renames = extra_renames + parsed["renames"]
            removed = parsed["removed"]
        # protected paths regardless of scope (diffgate lets a protected class through when allowed)
        touched = set(changed) | {p for pair in extra_renames for p in pair}
        for path in sorted(touched):
            if _is_protected(path, caller_keys) or (not path_hazards(path) and gate.is_blocked_path(path)):
                refuse.append(("PROTECTED_PATH", _show(path)))
        # exact scope match; case variants are named but still refused
        safe_allowed = [p for p in allowed if not path_hazards(p)]
        allowed_set = set(safe_allowed)
        folded_allowed = {_fold_key(p) for p in safe_allowed}
        for path in changed:
            if path not in allowed_set and not path_hazards(path):
                code = "CASE_VARIANT_OF_ALLOWED_PATH" if _fold_key(path) in folded_allowed else "OUT_OF_SCOPE_PATH"
                refuse.append((code, _show(path)))
        # isolation proof
        proof = build_isolation_proof(
            context=isolation, base_head=isolation.pinned_base_head, manifest_base_head=base_head,
            changed_paths=changed, candidate_head=candidate_head, removed_paths=removed)
        for item in proof["properties"]:
            name = item["property"]
            if name not in REQUIRED_PROPERTIES:
                continue
            if item["status"] == FAILED:
                refuse.append(("ISOLATION_VIOLATION", name))
            elif item["status"] == VERIFIED or (item["status"] == CALLER_ASSERTED and name in CALLER_ONLY_PROPERTIES):
                continue
            else:
                block.append(("ISOLATION_NOT_VERIFIED", name))
        # the deterministic diff gate itself
        if not hazardous:
            try:
                evidence = gate.check_diff(
                    manifest_sha256=manifest_sha256, base_head=base_head, candidate_head=candidate_head,
                    changed_paths=changed, allowed_paths=safe_allowed, diff_bytes=diff_bytes,
                    symlink_paths=extra_links, rename_pairs=extra_renames)
            except Exception as exc:
                block.append(("DIFFGATE_ERROR", type(exc).__name__))
            else:
                if not isinstance(evidence, dict) or evidence.get("verdict") not in ("PASS", "FAIL"):
                    block.append(("DIFFGATE_EVIDENCE_MALFORMED", "verdict is not PASS or FAIL"))
                    evidence = None
                elif evidence["verdict"] == "FAIL":
                    refuse.append(("DIFFGATE_" + re.sub(r"[^A-Z_]", "?", str(evidence.get("reason")))[:60], "deterministic diff gate returned FAIL"))
                elif (evidence.get("candidate_head") != candidate_head
                      or evidence.get("changed_paths") != sorted(set(changed))):
                    block.append(("DIFFGATE_EVIDENCE_MISMATCH", "evidence does not bind this change"))
    except _Blocked as exc:
        block.append(("MALFORMED_INPUT", str(exc)))
    except Exception as exc:  # fail closed on anything unexpected
        block.append(("INTERNAL_ERROR", type(exc).__name__))
    if refuse:
        return _verdict(REFUSED, refuse + block, evidence, proof)
    if block:
        return _verdict(BLOCKED, block, evidence, proof)
    return _verdict(ACCEPTED, [("DIFFGATE_PASS", "all checks passed")], evidence, proof)


def gate_worker_response(
    response: object, *, manifest_sha256: object, base_head: object, allowed_paths: object,
    protected_paths: object, diff_bytes: object, isolation: object,
    symlink_paths: Iterable[str] = (), rename_pairs: Iterable[tuple[str, str]] = (),
) -> WorkerGateVerdict:
    """Gate a WorkerResponse (tools/vst/worker_adapter.py); anything else is BLOCKED."""
    try:
        if not isinstance(response, WorkerResponse):
            return _verdict(BLOCKED, [("MALFORMED_WORKER_OUTPUT", "not a WorkerResponse")], None, None)
        if response.state is not WorkerState.SUCCEEDED or response.candidate_head is None:
            return _verdict(BLOCKED, [("WORKER_NOT_SUCCEEDED", str(getattr(response.state, "value", "?")))], None, None)
        if response.manifest_sha256 != manifest_sha256:
            return _verdict(BLOCKED, [("MANIFEST_MISMATCH", "response is bound to another manifest")], None, None)
        return gate_worker_change(
            manifest_sha256=manifest_sha256, base_head=base_head, candidate_head=response.candidate_head,
            changed_paths=response.changed_paths, allowed_paths=allowed_paths,
            protected_paths=protected_paths, diff_bytes=diff_bytes, isolation=isolation,
            symlink_paths=symlink_paths, rename_pairs=rename_pairs)
    except Exception as exc:
        return _verdict(BLOCKED, [("INTERNAL_ERROR", type(exc).__name__)], None, None)


def _verdict(verdict: str, reasons: list[tuple[str, str]], evidence: dict | None, proof: dict | None) -> WorkerGateVerdict:
    return WorkerGateVerdict(verdict, tuple(reasons), evidence, proof)
