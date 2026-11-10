"""U5-1: S3 worker output through the deterministic diff gate (Windows-local, no WSL).

Fail closed on every error. Verdicts:

* ACCEPTED - the deterministic diff gate passed, no path hazard, no protected path,
  every change inside the declared scope, the diff text agrees with the declared
  changed paths, and the required isolation properties were VERIFIED.
* REFUSED  - a definite policy violation (out of scope, protected path, path trick,
  link/mode change, diff/paths mismatch, isolation property FAILED, diff gate FAIL).
* BLOCKED  - the decision cannot be made (malformed or missing worker output, missing
  or broken diff gate, unparsable diff, unverifiable required isolation property,
  unexpected exception). BLOCKED is never an acceptance.

The diff gate (tools/vst/diffgate.py) is reused unchanged. It cannot express: case-folded
scope comparison, a protected path that is also listed as allowed, Windows aliases (8.3 names,
trailing dots/spaces, device names, NTFS streams), or checking the diff text against the
declared paths. This module adds those checks on top and refuses; it never relaxes the gate.
The isolation proof is a statement of what was checked, not an OS sandbox.
"""
from __future__ import annotations

import importlib
import os
import re
import stat
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .worker_adapter import WorkerResponse, WorkerState, is_canonical_repo_path

ACCEPTED = "ACCEPTED"
REFUSED = "REFUSED"
BLOCKED = "BLOCKED"

PROOF_SCHEMA = "vst-worker-isolation-proof-v1"
ISOLATION_MODE = "windows-local-no-wsl"
VERIFIED = "VERIFIED"
NOT_VERIFIED = "NOT_VERIFIED"
FAILED = "FAILED"

# Always protected, on top of the caller list and of diffgate.is_blocked_path.
DEFAULT_PROTECTED_PATHS = (
    ".git", ".github", ".gitlab", ".hooks", ".husky", ".harness", ".claude",
    ".gitattributes", ".gitmodules", "AGENTS.md", "CLAUDE.md",
)

# Properties this module can actually check. All must be VERIFIED for ACCEPTED.
REQUIRED_PROPERTIES = (
    "worktree_separate_from_main_checkout",
    "base_commit_pinned",
    "network_flag_not_requested",
    "paths_normalized",
    "link_and_reparse_point_check_on_changed_paths",
)

# Properties this module does NOT check. Always listed NOT_VERIFIED, never promotable.
NOT_VERIFIED_PROPERTIES = {
    "os_sandbox": "no OS sandbox or job object is applied or inspected on Windows-local without WSL",
    "process_containment": "worker process tree is not contained or enumerated; it may spawn processes",
    "network_enforcement": "only the request flag is checked; no firewall or network namespace is verified",
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
_SYMLINK_MODES = ("new file mode 120000", "old mode 120000", "new mode 120000", "deleted file mode 120000")
_GITLINK_MODE = "160000"
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class _Blocked(Exception):
    """Internal: the decision cannot be made."""


@dataclass(frozen=True)
class IsolationContext:
    """What the caller states about the isolated worktree; the proof checks it."""

    worktree_root: str
    main_checkout_root: str
    network_requested: bool
    pinned_base_head: str  # commit the caller states the worktree was created at (caller-reported)
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
    """Return hazard codes for one repo-relative path; an empty list means no hazard found."""
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
    if not found and not is_canonical_repo_path(path):
        found.append("NOT_CANONICAL")
    return list(dict.fromkeys(found))


def _fold_key(path: str) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFKC", p).casefold() for p in path.split("/"))


def _protected_keys(entries: Iterable[str]) -> list[tuple[str, ...]]:
    keys = []
    for entry in entries:
        if not isinstance(entry, str):
            raise _Blocked("protected_paths entries must be strings")
        value = entry[:-1] if entry.endswith("/") else entry
        if path_hazards(value):
            raise _Blocked(f"protected path entry is malformed: {entry!r}")
        keys.append(_fold_key(value))
    return keys


def _is_protected(path: str, keys: list[tuple[str, ...]]) -> bool:
    folded = _fold_key(path)
    return any(folded[: len(key)] == key for key in keys)


# ---------------------------------------------------------------------------- diff text
def parse_diff_paths(diff_bytes: bytes) -> dict:
    """Extract paths, renames, link-mode paths and gitlinks from `git diff` headers.

    Raises _Blocked on anything it cannot read exactly (quoted paths, ambiguous headers).
    """
    try:
        text = diff_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _Blocked("diff is not valid UTF-8") from exc
    blocks: list[dict] = []
    for line in text.split("\n"):
        if line.startswith("diff --git "):
            rest = line[len("diff --git "):]
            if '"' in rest or not rest.startswith("a/"):
                raise _Blocked("diff header is quoted or not in a/ b/ form")
            splits = [i for i in range(len(rest)) if rest.startswith(" b/", i)]
            pairs = [(rest[2:i], rest[i + 3:]) for i in splits]
            equal = [p for p in pairs if p[0] == p[1]]
            if len(pairs) == 1:
                pair = pairs[0]
            elif len(equal) == 1:
                pair = equal[0]
            else:
                pair = None
            blocks.append({"pair": pair, "rename": [None, None], "copy": [None, None],
                           "link": False, "gitlink": False})
        elif blocks:
            block = blocks[-1]
            if line.startswith(_SYMLINK_MODES) or re.match(r"index [0-9a-f]+\.\.[0-9a-f]+ 120000$", line):
                block["link"] = True
            if line.endswith(" " + _GITLINK_MODE) and (
                    "mode" in line or line.startswith("index ")):
                block["gitlink"] = True
            for key, prefix in (("rename", "rename"), ("copy", "copy")):
                for idx, word in enumerate(("from", "to")):
                    tag = f"{prefix} {word} "
                    if line.startswith(tag):
                        value = line[len(tag):]
                        if value.startswith('"'):
                            raise _Blocked("quoted rename or copy path")
                        block[key][idx] = value
    paths: set[str] = set()
    renames: list[tuple[str, str]] = []
    links: set[str] = set()
    gitlinks: set[str] = set()
    for block in blocks:
        src, dst = block["rename"] if all(block["rename"]) else block["copy"]
        if src and dst:
            current = {dst} | ({src} if all(block["rename"]) else set())
            if all(block["rename"]):
                renames.append((src, dst))
        elif block["pair"] is not None and block["pair"][0] == block["pair"][1]:
            current = {block["pair"][1]}
        else:
            raise _Blocked("diff header paths are ambiguous")
        paths |= current
        if block["link"]:
            links |= current
        if block["gitlink"]:
            gitlinks |= current
    return {"paths": paths, "renames": renames, "links": links, "gitlinks": gitlinks}


# ---------------------------------------------------------------------------- isolation proof
def build_isolation_proof(
    *, context: IsolationContext, base_head: object, manifest_base_head: object,
    changed_paths: Iterable[str],
) -> dict:
    """List what was checked (VERIFIED / FAILED / NOT_VERIFIED) and what is never checked."""
    props: dict[str, dict] = {}

    def put(name: str, status: str, detail: str) -> None:
        props[name] = {"property": name, "status": status, "detail": detail}

    paths = list(changed_paths)
    # 1 worktree separate from main checkout
    try:
        wt = os.path.normcase(context.realpath(context.worktree_root))
        main = os.path.normcase(context.realpath(context.main_checkout_root))
        if not (os.path.isabs(wt) and os.path.isabs(main)):
            put(REQUIRED_PROPERTIES[0], NOT_VERIFIED, "roots are not absolute paths")
        elif wt == main or os.path.commonpath([wt, main]) in (wt, main):
            put(REQUIRED_PROPERTIES[0], FAILED, "worktree equals or is nested with the main checkout")
        else:
            put(REQUIRED_PROPERTIES[0], VERIFIED, "resolved worktree and main checkout are disjoint")
    except (TypeError, ValueError, OSError):
        put(REQUIRED_PROPERTIES[0], NOT_VERIFIED, "roots could not be resolved or compared")
    # 2 base commit pinned
    if not (isinstance(base_head, str) and _HEX40.fullmatch(base_head)):
        put(REQUIRED_PROPERTIES[1], NOT_VERIFIED, "base head is not a lowercase 40-hex commit id")
    elif base_head != manifest_base_head:
        put(REQUIRED_PROPERTIES[1], FAILED, "base head differs from the manifest base head")
    else:
        put(REQUIRED_PROPERTIES[1], VERIFIED, "worktree base head reported by the caller equals the manifest base head; not read from git here")
    # 3 network flag (request flag only)
    if context.network_requested is False:
        put(REQUIRED_PROPERTIES[2], VERIFIED, "request flag network_requested is False; enforcement is NOT verified")
    elif context.network_requested is True:
        put(REQUIRED_PROPERTIES[2], FAILED, "network access was requested")
    else:
        put(REQUIRED_PROPERTIES[2], NOT_VERIFIED, "network_requested is not a boolean")
    # 4 paths normalized
    bad = {p: path_hazards(p) for p in paths if path_hazards(p)}
    if not paths:
        put(REQUIRED_PROPERTIES[3], NOT_VERIFIED, "no changed paths to check")
    elif bad:
        put(REQUIRED_PROPERTIES[3], FAILED, f"{len(bad)} path(s) with hazards")
    else:
        put(REQUIRED_PROPERTIES[3], VERIFIED, f"{len(paths)} path(s) canonical, no Windows alias hazard")
    # 5 links / reparse points
    put(REQUIRED_PROPERTIES[4], *_link_check(context, paths))
    for name, reason in NOT_VERIFIED_PROPERTIES.items():
        put(name, NOT_VERIFIED, reason)
    return {
        "schema": PROOF_SCHEMA,
        "isolation_mode": ISOLATION_MODE,
        "properties": [props[name] for name in props],
    }


def _link_check(context: IsolationContext, paths: list[str]) -> tuple[str, str]:
    try:
        root_stat = context.lstat(context.worktree_root)
    except (OSError, TypeError, ValueError):
        return NOT_VERIFIED, "worktree root could not be inspected"
    if not hasattr(root_stat, "st_file_attributes"):
        return NOT_VERIFIED, "platform reports no reparse attributes; junctions cannot be detected"
    try:
        root_real = os.path.normcase(context.realpath(context.worktree_root))
        for rel in paths:
            current = context.worktree_root
            for part in rel.split("/"):
                current = os.path.join(current, part)
                try:
                    info = context.lstat(current)
                except FileNotFoundError:
                    break
                if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT):
                    return FAILED, f"link or reparse point on path component {part!r}"
            real = os.path.normcase(context.realpath(os.path.join(context.worktree_root, *rel.split("/"))))
            if os.path.commonpath([root_real, real]) != root_real:
                return FAILED, "resolved path leaves the worktree"
    except FileNotFoundError:
        return NOT_VERIFIED, "path vanished during the check"
    except (OSError, TypeError, ValueError):
        return NOT_VERIFIED, "link check could not complete"
    return VERIFIED, f"no link or reparse point on {len(paths)} existing path prefix(es) at check time"


def proof_is_honest(proof: dict) -> bool:
    """True when every not-checked property is present as NOT_VERIFIED and none is promoted."""
    try:
        status = {p["property"]: p["status"] for p in proof["properties"]}
    except (KeyError, TypeError):
        return False
    return all(status.get(name) == NOT_VERIFIED for name in NOT_VERIFIED_PROPERTIES) and all(
        status[name] in (VERIFIED, FAILED, NOT_VERIFIED) for name in status)


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
    """Run one worker change through the diff gate; never raises, never accepts on error."""
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
        if not isinstance(isolation, IsolationContext):
            raise _Blocked("isolation context is missing")
        changed = _str_seq(changed_paths, "changed_paths", allow_empty=False)
        allowed = _str_seq(allowed_paths, "allowed_paths", allow_empty=False)
        if any(path_hazards(p) for p in allowed):
            raise _Blocked("allowed_paths contains a malformed or hazardous path")
        keys = _protected_keys(list(DEFAULT_PROTECTED_PATHS) + _str_seq(protected_paths, "protected_paths", allow_empty=True))
        extra_links = _str_seq(list(symlink_paths), "symlink_paths", allow_empty=True)
        extra_renames = list(rename_pairs)
        if any(not (isinstance(p, tuple) and len(p) == 2 and all(isinstance(s, str) for s in p)) for p in extra_renames):
            raise _Blocked("rename_pairs must be (source, destination) string pairs")

        # path hazards (Windows aliases, UNC, streams, traversal)
        hazardous = False
        for path in changed:
            for code in path_hazards(path):
                refuse.append((f"PATH_HAZARD_{code}", path))
                hazardous = True
        # diff text must agree with the declared paths
        try:
            parsed = parse_diff_paths(diff_bytes)
        except _Blocked as exc:
            block.append(("DIFF_UNPARSABLE", str(exc)))
            parsed = None
        if parsed is not None:
            if parsed["paths"] != set(changed):
                refuse.append(("DIFF_PATH_MISMATCH", "declared changed paths differ from paths in the diff text"))
            if parsed["gitlinks"]:
                refuse.append(("SUBMODULE_CHANGE", ",".join(sorted(parsed["gitlinks"]))))
            extra_links = list(extra_links) + sorted(parsed["links"])
            extra_renames = extra_renames + parsed["renames"]
        # protected paths regardless of scope (diffgate lets a protected class through when allowed)
        touched = set(changed) | {p for pair in extra_renames for p in pair}
        for path in sorted(touched):
            if path_hazards(path):
                continue
            if _is_protected(path, keys) or gate.is_blocked_path(path):
                refuse.append(("PROTECTED_PATH", path))
        # exact scope match; case variants are named but still refused
        allowed_set = set(allowed)
        folded_allowed = {_fold_key(p) for p in allowed}
        for path in changed:
            if path not in allowed_set and not path_hazards(path):
                code = "CASE_VARIANT_OF_ALLOWED_PATH" if _fold_key(path) in folded_allowed else "OUT_OF_SCOPE_PATH"
                refuse.append((code, path))
        # isolation proof
        proof = build_isolation_proof(context=isolation, base_head=isolation.pinned_base_head,
                                      manifest_base_head=base_head, changed_paths=changed)
        for item in proof["properties"]:
            if item["property"] in REQUIRED_PROPERTIES:
                if item["status"] == FAILED:
                    refuse.append(("ISOLATION_VIOLATION", item["property"]))
                elif item["status"] != VERIFIED:
                    block.append(("ISOLATION_NOT_VERIFIED", item["property"]))
        # the deterministic diff gate itself
        if not hazardous:
            try:
                evidence = gate.check_diff(
                    manifest_sha256=manifest_sha256, base_head=base_head, candidate_head=candidate_head,
                    changed_paths=changed, allowed_paths=allowed, diff_bytes=diff_bytes,
                    symlink_paths=extra_links, rename_pairs=extra_renames)
            except Exception as exc:
                block.append(("DIFFGATE_ERROR", type(exc).__name__))
            else:
                if not isinstance(evidence, dict) or evidence.get("verdict") not in ("PASS", "FAIL"):
                    block.append(("DIFFGATE_EVIDENCE_MALFORMED", "verdict is not PASS or FAIL"))
                    evidence = None
                elif evidence["verdict"] == "FAIL":
                    refuse.append((f"DIFFGATE_{evidence.get('reason')}", "deterministic diff gate returned FAIL"))
                elif (evidence.get("candidate_head") != candidate_head
                      or evidence.get("changed_paths") != sorted(changed)):
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
