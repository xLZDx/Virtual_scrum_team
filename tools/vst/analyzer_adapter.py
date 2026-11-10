"""Bounded, read-only AEVE analyzer adapter and deterministic snapshot hashing (S5-C, VST-040).

Everything here is deterministic, token-free stdlib Python: no model call, no
network call, no signing and no key material. VST trusted code computes every
digest itself (source tree from git blob content, analyzer files, profile,
report); nothing the analyzer prints is trusted as a digest of VST-owned data.
Signing stays in analyzer_authority.sign_analyzer_evidence (never called here).

What AEVE actually exposes (read from D:\\Repo\\AEVE, never imported or executed
by this module's author):
  * ``aeve analyze --root PATH [--allow-dirty]`` captures the tracked files of
    the WHOLE git root at HEAD and prints one JSON document (schema
    ``g2.analysis.v1``, rules ``g2.rules.v15``). It has NO scope option, NO
    profile option, and prints NO rule inventory, NO head and NO per-file list.
    Exit 0 = COMPLETE, 3 = PARTIAL, 2 = blocked (stderr). --allow-dirty is never
    passed; VST additionally requires HEAD == candidate_head and a clean tree
    before and after the run, using its own git calls.
  * The only machine-readable inventory is the ``g2.*`` analysis executors in
    ``aeve.governance.matrix.EXECUTORS`` (a declaration, not proof that every
    id is emitted for every file). It is pinned below as AEVE_G2_RULE_INVENTORY.
  * AEVE provides no license text, no evidence artifacts and no signature.

Boundaries enforced HERE: argv list (no shell), scrubbed environment, neutral
empty cwd, isolated interpreter flags, analyzer pinned under analyzer_root and
re-hashed after the run, wall-clock timeout, stdout/stderr caps, input caps,
Windows: child created suspended, put in a kill-on-close Job Object, then resumed (fail
closed otherwise); POSIX: killpg of a new session (best effort, setsid escapes); and a
local git-config allowlist. NOT enforced here (NOT_RUN, S2 sandbox): OS-level
network denial, read-only mounts, CPU/memory limits. AEVE removes GIT_CONFIG_*
variables from its own git environment, so VST cannot inject -c overrides into
AEVE's git calls; the defence is the .git/config allowlist checked before and
after the run (residual risk: a config change inside the run window, and any
AEVE-internal git behaviour, is outside this module).
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .analyzer_authority import build_analyzer_payload
from .contracts import (
    FINDING_FIELDS,
    FINDING_SEVERITY,
    RULE_STATUS,
    ContractError,
    _GLOB_CHARS,
    _validate_repo_path,
    canonical_bytes,
)

SOURCE_TREE_LABEL = b"vst-git-blob-tree-v1\0"
ANALYZER_FILES_LABEL = b"vst-analyzer-files-v1\0"
REPORT_LABEL = "vst-analyzer-report-v1"
PROFILE_LABEL = "vst-aeve-profile-v1"
AEVE_SCHEMA_VERSION = "g2.analysis.v1"
AEVE_RULES_VERSION = "g2.rules.v15"
LICENSE_STATUS_UNKNOWN = "UNKNOWN"

# AEVE severity -> VST closed enum. AEVE has no MEDIUM tier; MINOR->LOW is a
# conservative, documented choice.
SEVERITY_MAP = {"BLOCKER": "CRITICAL", "MAJOR": "HIGH", "MINOR": "LOW", "INFO": "INFO"}
if not set(SEVERITY_MAP.values()) <= FINDING_SEVERITY:
    raise ImportError("SEVERITY_MAP leaves the closed VST severity enum")

# Capabilities of the ``g2.*`` analysis executors in AEVE's governance matrix at
# rules version g2.rules.v15, minus the *-ANALYSIS-ERROR guard ids (those signal
# a failed rule family, they are not checks). Anything else is UNSUPPORTED.
AEVE_G2_RULE_INVENTORY = frozenset({
    # g2.python-rules
    "PY-BARE-EXCEPT", "PY-SILENT-EXCEPT-SWALLOW", "PY-EXCEPT-SWALLOW-RETURN",
    "PY-UNAWAITED-COROUTINE", "PY-RETURN-IN-FINALLY", "PY-EXCEPT-CONTROL-FLOW-SWALLOW",
    "PY-LOST-ASYNC-TASK", "PY-MUTABLE-DEFAULT-ARG", "PY-TEST-WITHOUT-ASSERTION",
    "PY-UNCLOSED-FILE", "PY-GLOBAL-STATE", "PY-ASYNC-BLOCKING-SLEEP",
    "PY-IDENTITY-LITERAL-COMPARISON", "PY-RETRY-WITHOUT-IDEMPOTENCY-TOKEN",
    "SF-LOG-ONLY", "SF-BROAD-CATCH-CONTINUE", "SF-FALLBACK-DEFAULT",
    "SF-IGNORED-STATUS", "SF-RETRY-NO-TERMINAL", "SF-BACKGROUND-DISCARDED",
    "SF-FALSE-SUCCESS",
    "PY-ASYNC-BLOCKING-CALL", "PY-RESOURCE-NO-CM",
    "PY-LATE-BINDING-CLOSURE", "PY-NAIVE-DATETIME", "PY-DECIMAL-FROM-FLOAT",
    "PY-OPEN-NO-ENCODING", "PY-UNSAFE-EXEC-DESERIALIZE", "PY-SUBPROCESS-SHELL",
    # g2.security-rules
    "SEC-SQL-STRING-BUILD", "SEC-SSRF-PARAM-URL", "SEC-PATH-JOIN-PARAM",
    "SEC-ARCHIVE-EXTRACT-UNFILTERED", "SEC-WEAK-PASSWORD-HASH",
    "SEC-INSECURE-RANDOM-SECRET", "SEC-TLS-VERIFY-DISABLED", "SEC-DEBUG-MODE",
    "SEC-BIND-ALL-INTERFACES",
    # g2.test-assertion-rules
    "FTR-ASSERT-ALWAYS-TRUE", "FTR-DUPLICATE-TEST-NAME", "FTR-ASSERT-IN-SWALLOWING-TRY",
    "FTR-WEAK-ONLY-ASSERTIONS", "FTR-BROAD-RAISES", "FTR-SKIP-OR-XFAIL-HIDING",
    "FTR-MOCK-SELF-ASSERTION", "FTR-PATCHED-SUBJECT", "FTR-LOOP-ASSERT-MAY-BE-EMPTY",
    "FTR-SLEEP-IN-TEST",
    # g2.reliability-rules
    "REL-NET-NO-TIMEOUT", "REL-SUBPROCESS-NO-TIMEOUT", "REL-RETRY-UNBOUNDED",
    "REL-QUEUE-UNBOUNDED", "REL-CONCURRENCY-PER-ITEM", "REL-LOCK-NOT-RELEASED",
    "REL-BLOCKING-UNDER-LOCK", "REL-STATE-WRITE-NOT-ATOMIC",
    # g2.type-design-rules
    "TDA-FROZEN-MUTABLE-FIELD", "TDA-DATACLASS-MUTABLE-DEFAULT",
    "TDA-CLASS-SHARED-MUTABLE-ATTR", "TDA-INIT-PARTIAL-ATTRS", "TDA-BOOL-PARAM-CLUSTER",
    "TDA-STRINGLY-STATE", "TDA-HASH-EQ-CONTRACT", "TDA-UNIT-NAME-MISMATCH",
    # g2.comment-rules
    "CMT-DOC-PARAM-UNKNOWN", "CMT-DOC-PARAM-MISSING", "CMT-DOC-RETURNS-NO-VALUE",
    "CMT-DOC-CLAIM-CONTRADICTED", "CMT-STALE-LOCAL-REFERENCE", "CMT-COMMENTED-OUT-CODE",
    "CMT-DEBT-MARKER-UNOWNED", "CMT-DUPLICATE-DOCSTRING",
    # g2.observability-rules
    "OBS-LOG-SECRET-NAME", "OBS-ERROR-CAUSE-NOT-LOGGED", "OBS-ERROR-LOG-OMITS-ID",
    "OBS-ID-NOT-FORWARDED", "OBS-METRIC-HIGH-CARDINALITY-LABEL",
    # g2.web-boundary-rules
    "WEB-ROUTE-BODY-UNTYPED", "WEB-ROUTE-NO-RESPONSE-CONTRACT", "WEB-ROUTE-ERROR-AS-200",
    "WEB-ROUTE-EXC-DETAIL-EXPOSED", "WEB-HTTPEXCEPTION-INTERCEPTED",
    "WEB-DEPENDENCY-YIELD-NO-CLEANUP", "WEB-SESSION-MODULE-LEVEL",
    "WEB-ASYNC-ROUTE-SYNC-SESSION", "WEB-UPLOAD-UNBOUNDED-READ",
    "WEB-HTTP-RESPONSE-UNCHECKED", "WEB-RATE-LIMIT-RETRY-IMMEDIATE",
    "WEB-WEBHOOK-NO-SIGNATURE-CHECK", "WEB-CREDENTIAL-LOGGED",
    # g2.hygiene-rules
    "PRF-QUERY-IN-LOOP", "PRF-LINEAR-MEMBERSHIP-IN-LOOP", "PRF-CONCAT-IN-LOOP",
    "PRF-UNBOUNDED-CACHE", "CLN-UNUSED-IMPORT", "CLN-DUPLICATE-BODY", "SIM-NESTING-DEPTH",
    # g2.ml-temporal-rules
    "MLF-NEGATIVE-SHIFT-FEATURE", "MLF-SHUFFLED-SPLIT", "MLF-FIT-BEFORE-SPLIT", "MLF-NO-SEED",
})

# Names copied from the parent environment (compared upper-case). Everything
# else, including proxies, tokens and provider keys, is dropped.
_ENV_ALLOW = frozenset({"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "TEMP", "TMP"})
_ENV_FIXED = {
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONNOUSERSITE": "1",
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
    # Never honour system/user/candidate-independent git configuration.
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_ATTR_NOSYSTEM": "1",
}
_REPARSE_POINT = 0x400
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
)
_HEX64 = re.compile(r"[0-9a-f]{64}")
_HEX40 = re.compile(r"[0-9a-f]{40}")
_AEVE_TOP_KEYS = frozenset({
    "schema_version", "rules_version", "status", "snapshot_sha256", "analysis_sha256",
    "findings", "summary", "diagnostics", "uncovered", "executed_project_code", "llm_calls",
})
_AEVE_FINDING_KEYS = frozenset({"rule_id", "severity", "confidence", "file", "line", "message", "detail"})
_STDERR_TAIL_BYTES = 2000
# Local .git/config allowlist: anything that can name a program or load more config is refused.
_GIT_CONFIG_ALLOWED = {
    "core": frozenset({
        "repositoryformatversion", "filemode", "bare", "logallrefupdates", "symlinks",
        "ignorecase", "precomposeunicode", "autocrlf", "eol", "safecrlf", "longpaths",
    }),
    "remote": frozenset({"url", "fetch", "pushurl", "tagopt", "prune"}),
    "branch": frozenset({"remote", "merge", "rebase"}),
}
_GIT_REGULAR_MODES = frozenset({"100644", "100755"})
_GIT_STDERR_CAP = 65536
# Importable file types: every one found under a pythonpath directory must be pinned.
_IMPORTABLE_SUFFIXES = (".py", ".pyc", ".pyd", ".so", ".pth", ".dll")


# ----------------------------------------------------------------- errors/types


class AdapterError(ValueError):
    """Typed refusal raised before or around a run (scope, input, digest, binding problems)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class Outcome(str, Enum):
    OK = "OK"
    PARTIAL_WITH_FINDINGS = "PARTIAL_WITH_FINDINGS"
    TIMEOUT = "TIMEOUT"
    OUTPUT_CAP = "OUTPUT_CAP"
    CRASH = "CRASH"
    MISSING_EXECUTABLE = "MISSING_EXECUTABLE"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    # Windows containment (suspended start + kill-on-close Job Object) could not be established; the
    # analyzer was NOT run.
    CONTAINMENT_FAILED = "CONTAINMENT_FAILED"
    # A kill was required (timeout/cap) but termination of the process (tree) was not confirmed.
    TERMINATION_FAILED = "TERMINATION_FAILED"


_PAYLOAD_OUTCOMES = frozenset({Outcome.OK, Outcome.PARTIAL_WITH_FINDINGS})


@dataclass(frozen=True)
class Limits:
    timeout_seconds: float = 120.0
    max_stdout_bytes: int = 8_000_000
    max_stderr_bytes: int = 200_000
    max_file_bytes: int = 2_000_000
    max_total_input_bytes: int = 64_000_000
    max_analyzer_file_bytes: int = 16_000_000
    max_analyzer_total_bytes: int = 256_000_000
    git_timeout_seconds: float = 30.0
    max_git_listing_bytes: int = 24_000_000


@dataclass(frozen=True)
class AnalyzerSpec:
    """Pinned analyzer identity.

    argv_prefix is either (python, "-m", "aeve") together with a non-empty
    ``pythonpath`` under analyzer_root, or (path_to_launcher,) located under
    analyzer_root. Either way the executed module/launcher must be listed in
    ``analyzer_files`` (explicit sorted files hashed as the analyzer).
    """

    argv_prefix: tuple[str, ...]
    analyzer_root: Path
    analyzer_files: tuple[str, ...]
    version_file: str  # relative to analyzer_root, contains __version__ = "x"
    profile_id: str
    analyzer_id: str = "aeve"
    pythonpath: tuple[Path, ...] = ()
    rule_inventory: frozenset[str] = AEVE_G2_RULE_INVENTORY
    expected_schema_version: str = AEVE_SCHEMA_VERSION
    expected_rules_version: str = AEVE_RULES_VERSION
    version_pattern: str = r'^__version__\s*=\s*"([^"\n]+)"\s*$'
    # Explicit, documented exclusions from the pinned closure: exact repo-relative (to analyzer_root)
    # importable files under a pythonpath directory that are deliberately NOT hashed (e.g. tests).
    # They stay importable by the analyzer, so each one is a recorded gap, not a silent pass.
    pythonpath_exclusions: tuple[str, ...] = ()


@dataclass(frozen=True)
class TreeDigest:
    sha256: str
    file_sha256: Mapping[str, str]
    file_sizes: Mapping[str, int]
    total_bytes: int


@dataclass(frozen=True)
class RunResult:
    outcome: Outcome
    exit_code: int | None
    stdout: bytes
    stderr_tail: str
    elapsed_seconds: float
    argv: tuple[str, ...]
    detail: str = ""


@dataclass(frozen=True)
class AnalysisReport:
    """Closed report; ``body`` is the exact dict whose canonical bytes are hashed."""

    body: Mapping[str, Any]

    def canonical_bytes(self) -> bytes:
        return canonical_bytes(dict(self.body))

    @property
    def report_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @property
    def coverage(self) -> str:
        return self.body["coverage"]


@dataclass(frozen=True)
class AdapterResult:
    outcome: Outcome
    detail: str
    run: RunResult | None
    report: AnalysisReport | None
    source_tree_sha256: str | None
    analyzer_sha256: str | None
    profile_sha256: str | None
    analyzer_version: str | None
    candidate_head: str | None = None
    license_status: str = LICENSE_STATUS_UNKNOWN
    # Informational limits (never invented away): license, per-file confirmation, rule emission.
    unknown: tuple[str, ...] = field(default_factory=tuple)
    # Bindings that are missing; assemble_analyzer_payload refuses while any is present.
    blocking_unknown: tuple[str, ...] = field(default_factory=tuple)


# ------------------------------------------------------------ scope / path rules


def validate_scope(scope: object) -> list[str]:
    """Explicit sorted unique repo-relative '/' paths. No globs, no traversal, no absolute."""
    if not isinstance(scope, (list, tuple)) or not scope:
        raise AdapterError("SCOPE_INVALID", "scope must be a non-empty list of paths")
    paths = list(scope)
    seen_fold: set[str] = set()
    for index, rel in enumerate(paths):
        name = f"scope[{index}]"
        try:
            _validate_repo_path(rel, name)
        except ContractError as exc:
            raise AdapterError("SCOPE_PATH_REFUSED", str(exc)) from exc
        if "\\" in rel:
            raise AdapterError("SCOPE_PATH_REFUSED", f"{name}: must use '/' separators")
        if any(ch in _GLOB_CHARS for ch in rel):
            raise AdapterError("SCOPE_GLOB_REFUSED", f"{name}: glob characters are not allowed")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in rel):
            raise AdapterError("SCOPE_PATH_REFUSED", f"{name}: control characters are not allowed")
        if unicodedata.normalize("NFC", rel) != rel:
            raise AdapterError("SCOPE_PATH_REFUSED", f"{name}: must be NFC-normalized")
        for segment in rel.split("/"):
            if segment != segment.rstrip(" .") or segment.split(".")[0].upper() in _WINDOWS_RESERVED:
                raise AdapterError("SCOPE_PATH_REFUSED", f"{name}: Windows-ambiguous segment {segment!r}")
        fold = rel.casefold()
        if fold in seen_fold:
            raise AdapterError("SCOPE_DUPLICATE", f"{name}: duplicate or case-colliding path")
        seen_fold.add(fold)
    if paths != sorted(paths):
        raise AdapterError("SCOPE_UNSORTED", "scope must be sorted (code-point order)")
    return paths


def _is_link(st: os.stat_result) -> bool:
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE_POINT)


def _resolve_regular_file(real_root: str, rel: str) -> str:
    """Walk each component with lstat; refuse symlink/junction/reparse and non-regular files."""
    current = real_root
    parts = rel.split("/")
    for position, segment in enumerate(parts):
        current = os.path.join(current, segment)
        try:
            st = os.lstat(current)
        except OSError as exc:
            raise AdapterError("SCOPE_FILE_MISSING", f"{rel}: {type(exc).__name__}") from exc
        if _is_link(st):
            raise AdapterError("SCOPE_SYMLINK_REFUSED", f"{rel}: link or reparse point at {segment!r}")
        last = position == len(parts) - 1
        if last and not stat.S_ISREG(st.st_mode):
            raise AdapterError("SCOPE_NOT_REGULAR", f"{rel}: not a regular file")
        if not last and not stat.S_ISDIR(st.st_mode):
            raise AdapterError("SCOPE_NOT_REGULAR", f"{rel}: parent {segment!r} is not a directory")
    real = os.path.realpath(current)
    if not _is_under(real_root, real):
        raise AdapterError("SCOPE_ESCAPE", f"{rel}: resolves outside the root")
    return current


def _is_under(root: str, candidate: str) -> bool:
    try:
        return os.path.commonpath([os.path.normcase(root), os.path.normcase(candidate)]) == os.path.normcase(root)
    except ValueError:
        return False


def _combine(label: bytes, items: Sequence[tuple[str, int, bytes]]) -> str:
    """Layout: label | count(8) | per file: len(path)(8) path size(8) sha256(32)."""
    outer = hashlib.sha256()
    outer.update(label)
    outer.update(len(items).to_bytes(8, "big"))
    for rel, size, inner in items:
        path_bytes = rel.encode("utf-8")
        outer.update(len(path_bytes).to_bytes(8, "big"))
        outer.update(path_bytes)
        outer.update(size.to_bytes(8, "big"))
        outer.update(inner)
    return outer.hexdigest()


def tree_digest(
    root: str | os.PathLike[str],
    files: Sequence[str],
    *,
    max_file_bytes: int,
    max_total_bytes: int,
    label: bytes = ANALYZER_FILES_LABEL,
) -> TreeDigest:
    """Deterministic digest over explicit working-tree files (used for the analyzer files)."""
    paths = validate_scope(list(files))
    real_root = os.path.realpath(os.fspath(root))
    if not os.path.isdir(real_root):
        raise AdapterError("ROOT_INVALID", "root is not a directory")
    items: list[tuple[str, int, bytes]] = []
    digests: dict[str, str] = {}
    sizes: dict[str, int] = {}
    total = 0
    for rel in paths:
        full = _resolve_regular_file(real_root, rel)
        inner = hashlib.sha256()
        size = 0
        try:
            with open(full, "rb") as handle:
                while True:
                    chunk = handle.read(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    total += len(chunk)
                    if size > max_file_bytes:
                        raise AdapterError("INPUT_FILE_TOO_LARGE", f"{rel}: exceeds {max_file_bytes} bytes")
                    if total > max_total_bytes:
                        raise AdapterError("INPUT_TOTAL_TOO_LARGE", f"total exceeds {max_total_bytes} bytes")
                    inner.update(chunk)
        except OSError as exc:
            raise AdapterError("SCOPE_FILE_UNREADABLE", f"{rel}: {type(exc).__name__}") from exc
        digests[rel] = inner.hexdigest()
        sizes[rel] = size
        items.append((rel, size, inner.digest()))
    return TreeDigest(_combine(label, items), digests, sizes, total)


# ---------------------------------------------------------------- VST-run git


def _which(name: str) -> str | None:
    """PATH lookup that never consults the current directory."""
    pathext = [".exe"] if sys.platform == "win32" and not os.path.splitext(name)[1] else [""]
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory or not os.path.isabs(directory):
            continue
        for ext in pathext:
            candidate = os.path.join(directory, name + ext)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


def _git_exe() -> str:
    exe = _which("git")
    if exe is None:
        raise AdapterError("GIT_UNAVAILABLE", "git executable not found on PATH")
    return os.path.realpath(exe)


def _git(
    real_root: str, args: Sequence[str], limits: Limits, *, max_out: int | None = None
) -> bytes:
    """Run git with explicit --git-dir/--work-tree, neutral config and no pager/hooks/fsmonitor."""
    gitdir = os.path.join(real_root, ".git")
    cmd = [
        _git_exe(), "--no-optional-locks", "--literal-pathspecs",
        "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
        "-c", f"core.hooksPath={os.devnull}", "-c", "core.quotepath=false",
        f"--git-dir={gitdir}", f"--work-tree={real_root}", *args,
    ]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    cap = max_out if max_out is not None else limits.max_git_listing_bytes
    out, err = bytearray(), bytearray()
    out_over, err_over = threading.Event(), threading.Event()
    try:
        proc = subprocess.Popen(
            cmd, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=scrubbed_environment(), cwd=real_root, creationflags=flags,
        )
    except OSError as exc:
        raise AdapterError("GIT_UNAVAILABLE", f"{args[0]}: {type(exc).__name__}") from exc
    threads = [
        threading.Thread(target=_drain, args=(proc.stdout, cap, out, out_over), daemon=True),
        threading.Thread(target=_drain, args=(proc.stderr, _GIT_STDERR_CAP, err, err_over), daemon=True),
    ]
    timed_out = over = False
    try:
        for t in threads:
            t.start()
        deadline = time.monotonic() + limits.git_timeout_seconds
        while True:
            if out_over.is_set() or err_over.is_set():
                over = True
                break
            if proc.poll() is not None:
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.005)
        if over or timed_out:
            proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            raise AdapterError("GIT_KILL_FAILED", f"{args[0]}: git did not terminate") from exc
    finally:
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        for stream in (proc.stdout, proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        for t in threads:
            t.join(timeout=5)
    if over or out_over.is_set() or err_over.is_set():
        raise AdapterError("GIT_OUTPUT_LIMIT", args[0])
    if timed_out:
        raise AdapterError("GIT_TIMEOUT", args[0])
    if proc.returncode != 0:
        raise AdapterError("GIT_FAILED", f"{args[0]} exit {proc.returncode}")
    return bytes(out)


def _check_git_config(real_root: str) -> None:
    """Refuse a candidate .git whose local config could make git run a program or load more config."""
    gitdir = os.path.join(real_root, ".git")
    try:
        st = os.lstat(gitdir)
    except OSError as exc:
        raise AdapterError("GIT_LAYOUT_REFUSED", f".git: {type(exc).__name__}") from exc
    if _is_link(st) or not stat.S_ISDIR(st.st_mode):
        raise AdapterError("GIT_LAYOUT_REFUSED", ".git must be a real directory")
    config = os.path.join(gitdir, "config")
    if not os.path.exists(config):
        return
    try:
        with open(config, "rb") as handle:
            data = handle.read(65537)
        if len(data) > 65536:
            raise AdapterError("GIT_CONFIG_REFUSED", "config too large")
        text = data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise AdapterError("GIT_CONFIG_REFUSED", type(exc).__name__) from exc
    section: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.endswith("\\"):
            raise AdapterError("GIT_CONFIG_REFUSED", "line continuation is not allowed")
        header = re.fullmatch(r'\[\s*([A-Za-z0-9-]+)(?:\s+"[^"\\]*"|\.[^\s\]"]+)?\s*\]\s*(.*)', line)
        if header:
            section = header.group(1).lower()
            if section not in _GIT_CONFIG_ALLOWED:
                raise AdapterError("GIT_CONFIG_REFUSED", f"section [{section}] is not allowed")
            line = header.group(2).strip()
            if not line or line[0] in "#;":
                continue
        entry = re.fullmatch(r"([A-Za-z][A-Za-z0-9-]*)\s*(?:=.*)?", line)
        if section is None or entry is None:
            raise AdapterError("GIT_CONFIG_REFUSED", "unparsable or out-of-section config line")
        if entry.group(1).lower() not in _GIT_CONFIG_ALLOWED[section]:
            raise AdapterError("GIT_CONFIG_REFUSED", f"{section}.{entry.group(1).lower()} is not allowed")


def _check_git_binding(real_root: str, candidate_head: str, limits: Limits) -> None:
    """HEAD must equal candidate_head and the tree must be clean (tracked and untracked)."""
    if not isinstance(candidate_head, str) or _HEX40.fullmatch(candidate_head) is None:
        raise AdapterError("HEAD_INVALID", "candidate_head must be 40 lowercase hex characters")
    head = _git(real_root, ["rev-parse", "--verify", "HEAD"], limits, max_out=1000).decode("ascii", "replace").strip()
    if head != candidate_head:
        raise AdapterError("HEAD_MISMATCH", "git HEAD differs from candidate_head")
    status = _git(
        real_root,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none"],
        limits,
    )
    if status:
        raise AdapterError("TREE_DIRTY", "working tree is not clean")


def _tracked_entries(real_root: str, limits: Limits, rev: str) -> dict[str, tuple[str, str, str]]:
    listing = _git(real_root, ["ls-tree", "-r", "-z", "--full-tree", rev], limits)
    entries: dict[str, tuple[str, str, str]] = {}
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, sep, raw_path = record.partition(b"\t")
        parts = meta.decode("ascii", "replace").split(" ")
        if not sep or len(parts) != 3:
            raise AdapterError("GIT_LISTING_INVALID", "unparsable ls-tree record")
        entries[raw_path.decode("utf-8", "surrogateescape")] = (parts[0], parts[1], parts[2])
    return entries


def source_tree_digest(
    root: str | os.PathLike[str], scope: Sequence[str], candidate_head: str, limits: Limits = Limits()
) -> TreeDigest:
    """Source-tree digest over the manifest scope, hashed as git blob content at HEAD.

    Refuses: untracked scope paths, case spellings that differ from the tracked
    spelling, non-regular modes (symlink/submodule), dirty tree, HEAD mismatch.
    """
    paths = validate_scope(list(scope))
    real_root = os.path.realpath(os.fspath(root))
    if not os.path.isdir(real_root):
        raise AdapterError("ROOT_INVALID", "root is not a directory")
    _check_git_config(real_root)
    _check_git_binding(real_root, candidate_head, limits)
    tracked = _tracked_entries(real_root, limits, candidate_head)  # the verified 40-hex head, not symbolic HEAD
    fold: dict[str, int] = {}
    for name in tracked:
        fold[name.casefold()] = fold.get(name.casefold(), 0) + 1
    items: list[tuple[str, int, bytes]] = []
    digests: dict[str, str] = {}
    sizes: dict[str, int] = {}
    total = 0
    for rel in paths:
        entry = tracked.get(rel)
        if entry is None:
            if rel.casefold() in fold:
                raise AdapterError("SCOPE_CASE_MISMATCH", f"{rel}: spelling differs from the tracked path")
            raise AdapterError("SCOPE_NOT_TRACKED", f"{rel}: not tracked at HEAD")
        mode, kind, blob = entry
        if kind != "blob" or mode not in _GIT_REGULAR_MODES:
            raise AdapterError("SCOPE_NOT_REGULAR", f"{rel}: tracked as {mode} {kind}")
        if _HEX40.fullmatch(blob) is None:
            raise AdapterError("GIT_OBJECT_FORMAT_UNSUPPORTED", "only 40-hex object ids are supported")
        _resolve_regular_file(real_root, rel)  # parent junction / escape defence
        size_text = _git(real_root, ["cat-file", "-s", blob], limits, max_out=64).decode("ascii", "replace").strip()
        if not size_text.isdigit():
            raise AdapterError("GIT_LISTING_INVALID", f"{rel}: blob size unreadable")
        if int(size_text) > limits.max_file_bytes:
            raise AdapterError("INPUT_FILE_TOO_LARGE", f"{rel}: exceeds {limits.max_file_bytes} bytes")
        if total + int(size_text) > limits.max_total_input_bytes:
            raise AdapterError("INPUT_TOTAL_TOO_LARGE", f"total exceeds {limits.max_total_input_bytes} bytes")
        data = _git(real_root, ["cat-file", "blob", blob], limits, max_out=limits.max_file_bytes)
        if hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest() != blob:
            raise AdapterError("GIT_OBJECT_MISMATCH", f"{rel}: blob bytes do not match their object id")
        total += len(data)
        inner = hashlib.sha256(data)
        digests[rel] = inner.hexdigest()
        sizes[rel] = len(data)
        items.append((rel, len(data), inner.digest()))
    return TreeDigest(_combine(SOURCE_TREE_LABEL, items), digests, sizes, total)


# ------------------------------------------------------------- identity digests


def analyzer_tree_digest(spec: AnalyzerSpec, limits: Limits = Limits()) -> TreeDigest:
    """Digest (with per-file digests) of the explicit analyzer file list."""
    return tree_digest(
        spec.analyzer_root,
        spec.analyzer_files,
        max_file_bytes=limits.max_analyzer_file_bytes,
        max_total_bytes=limits.max_analyzer_total_bytes,
        label=ANALYZER_FILES_LABEL,
    )


def analyzer_digest(spec: AnalyzerSpec, limits: Limits = Limits()) -> str:
    """analyzer_sha256: VST-computed digest of the explicit analyzer file list."""
    return analyzer_tree_digest(spec, limits).sha256


def read_declared_version(spec: AnalyzerSpec, expected_sha256: str | None = None) -> str:
    """Read ``__version__`` by regex from the version file (never imports the analyzer).

    The version file must be one of analyzer_files; when ``expected_sha256`` is given the
    bytes actually read must hash to it, so the version comes from the pinned bytes.
    """
    validate_scope([spec.version_file])
    if spec.version_file not in spec.analyzer_files:
        raise AdapterError("VERSION_FILE_NOT_PINNED", "version_file must be listed in analyzer_files")
    real_root = os.path.realpath(os.fspath(spec.analyzer_root))
    full = _resolve_regular_file(real_root, spec.version_file)
    try:
        with open(full, "rb") as handle:
            data = handle.read(1_000_001)
        if len(data) > 1_000_000:
            raise AdapterError("VERSION_FILE_TOO_LARGE", spec.version_file)
        if expected_sha256 is not None and hashlib.sha256(data).hexdigest() != expected_sha256:
            raise AdapterError("VERSION_FILE_CHANGED", "version file bytes differ from the pinned digest")
        match = re.search(spec.version_pattern, data.decode("utf-8"), re.MULTILINE)
    except (OSError, UnicodeError) as exc:
        raise AdapterError("VERSION_UNREADABLE", type(exc).__name__) from exc
    if match is None:
        raise AdapterError("VERSION_UNKNOWN", "no declared version found; refusing to invent one")
    return match.group(1)


def profile_digest(spec: AnalyzerSpec) -> str:
    """profile_sha256 over the exact adapter-side profile: invocation shape, schema/rules
    version, rule inventory and severity map. AEVE ``analyze`` has no profile file."""
    body = {
        "label": PROFILE_LABEL,
        "profile_id": spec.profile_id,
        "argv_suffix": ["analyze", "--root", "<ROOT>"],
        "schema_version": spec.expected_schema_version,
        "rules_version": spec.expected_rules_version,
        "rule_inventory": sorted(spec.rule_inventory),
        "severity_map": dict(sorted(SEVERITY_MAP.items())),
    }
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _file_sha256(path: str, cap: int) -> str | None:
    try:
        digest = hashlib.sha256()
        size = 0
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    return digest.hexdigest()
                size += len(chunk)
                if size > cap:
                    return None
                digest.update(chunk)
    except OSError:
        return None


# ------------------------------------------------------------ argv / pinning


def _rel_posix(base: str, target: str) -> str:
    return os.path.relpath(target, base).replace(os.sep, "/")


def _require_closure(analyzer_root: str, entry: str, listed: set[str], excluded: set[str]) -> None:
    """Every importable file on disk under a pythonpath directory must be pinned (listed in
    analyzer_files) or explicitly excluded; links and unreadable directories are refused.
    __pycache__ is skipped because PYTHONPYCACHEPREFIX redirects bytecode to an empty dir."""
    problems: list[str] = []

    def walk_error(exc: OSError) -> None:
        raise AdapterError("ANALYZER_NOT_PINNED", f"cannot enumerate pythonpath directory: {type(exc).__name__}")

    for current, dirs, files in os.walk(entry, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in dirs:
            if _is_link(os.lstat(os.path.join(current, name))):
                raise AdapterError("ANALYZER_NOT_PINNED", f"link or reparse point at {name!r} under pythonpath")
        for name in sorted(files):
            full = os.path.join(current, name)
            if _is_link(os.lstat(full)):
                raise AdapterError("ANALYZER_NOT_PINNED", f"link or reparse point at {name!r} under pythonpath")
            if not name.lower().endswith(_IMPORTABLE_SUFFIXES):
                continue
            rel = _rel_posix(analyzer_root, full)
            if rel not in listed and rel not in excluded:
                problems.append(rel)
    if problems:
        raise AdapterError(
            "ANALYZER_NOT_PINNED",
            f"{len(problems)} importable file(s) under pythonpath are not in analyzer_files; first: {problems[0]}",
        )


def resolve_argv(spec: AnalyzerSpec, real_root: str) -> tuple[list[str], str]:
    """Return (argv, resolved_executable) exactly as it will be executed and hashed.

    The executable is resolved here (never by Popen against the cwd), isolation
    flags are added for a Python interpreter, and the analyzer module/launcher
    must be pinned under analyzer_root and listed in analyzer_files.
    Raises AdapterError('MISSING_EXECUTABLE') or ('ANALYZER_NOT_PINNED'/'ARGV_INVALID').
    """
    prefix = list(spec.argv_prefix)
    if not prefix or not all(isinstance(a, str) and a and "\0" not in a for a in prefix):
        raise AdapterError("ARGV_INVALID", "argv_prefix must be non-empty strings")
    first = prefix[0]
    if os.path.dirname(first):
        if not os.path.isabs(first):
            raise AdapterError("ARGV_INVALID", "executable path must be absolute or a bare name")
        resolved = first
    else:
        resolved = _which(first) or ""
    if not resolved or not os.path.isfile(resolved):
        raise AdapterError("MISSING_EXECUTABLE", "executable not found")
    resolved = os.path.realpath(resolved)
    analyzer_root = os.path.realpath(os.fspath(spec.analyzer_root))
    listed = set(spec.analyzer_files)
    flags: list[str] = []
    if os.path.basename(resolved).lower().startswith("python"):
        if len(prefix) < 3 or prefix[1] != "-m" or not spec.pythonpath:
            raise AdapterError("ANALYZER_NOT_PINNED", "python needs '-m MODULE' and a pythonpath under analyzer_root")
        module = prefix[2].replace(".", "/")
        pinned = False
        excluded = set(spec.pythonpath_exclusions)
        for entry in spec.pythonpath:
            real_entry = os.path.realpath(os.fspath(entry))
            if not _is_under(analyzer_root, real_entry) or not os.path.isdir(real_entry):
                raise AdapterError("ANALYZER_NOT_PINNED", "pythonpath entry is not a directory under analyzer_root")
            _require_closure(analyzer_root, real_entry, listed, excluded)
            candidate = os.path.join(real_entry, *module.split("/"), "__main__.py")
            if os.path.isfile(candidate) and _rel_posix(analyzer_root, os.path.realpath(candidate)) in listed:
                pinned = True
                break
        if not pinned:
            raise AdapterError("ANALYZER_NOT_PINNED", "module __main__.py is not a listed analyzer file under pythonpath")
        # -P/-s keep cwd and user site off sys.path while PYTHONPATH stays honoured.
        flags = ["-P", "-s"]
    else:
        if not _is_under(analyzer_root, resolved) or _rel_posix(analyzer_root, resolved) not in listed:
            raise AdapterError("ANALYZER_NOT_PINNED", "launcher is not a listed analyzer file under analyzer_root")
    return [resolved, *flags, *prefix[1:], "analyze", "--root", real_root], resolved


# ----------------------------------------------------------------- bounded runner


def scrubbed_environment(pythonpath: Sequence[Path] = ()) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() in _ENV_ALLOW}
    env.update(_ENV_FIXED)
    if pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(os.fspath(p) for p in pythonpath)
        env["PYTHONSAFEPATH"] = "1"
    return env


class _WinJob:
    """Windows Job Object with kill-on-close (ctypes, stdlib only). The child is created
    suspended, assigned here, and only then resumed, so no descendant can predate containment."""

    def __init__(self, k32: Any, handle: Any, resume: Any) -> None:
        self._k32, self._handle, self._resume = k32, handle, resume

    def resume(self, proc: subprocess.Popen) -> bool:
        return self._resume(int(proc._handle)) == 0  # type: ignore[attr-defined]  # NtResumeProcess

    def terminate(self) -> bool:
        return bool(self._handle) and bool(self._k32.TerminateJobObject(self._handle, 1))

    def close(self) -> None:
        if self._handle:
            self._k32.CloseHandle(self._handle)  # kill-on-close reaps any survivors
            self._handle = None


def _attach_job(proc: subprocess.Popen) -> _WinJob | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _Basic(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class _Extended(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _Basic), ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        ntdll.NtResumeProcess.restype = ctypes.c_long
        handle = k32.CreateJobObjectW(None, None)
        if not handle:
            return None
        info = _Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)) or not (
            k32.AssignProcessToJobObject(handle, int(proc._handle))  # type: ignore[attr-defined]
        ):
            k32.CloseHandle(handle)
            return None
        return _WinJob(k32, handle, ntdll.NtResumeProcess)
    except Exception:  # containment unavailable: the caller fails closed and does not run the analyzer
        return None


def _kill_tree(proc: subprocess.Popen, job: _WinJob | None) -> bool:
    """Kill the child and its descendants; True only if the kill call(s) reported success.

    Windows: TerminateJobObject (kernel-enforced for every process in the job, no breakaway
    allowed). POSIX: killpg of the child's own session, which is BEST EFFORT only: a descendant
    that calls setsid/setpgid escapes. A False return must be treated as an unsuccessful kill.
    """
    ok = True
    if job is not None:
        ok = job.terminate()
    elif sys.platform == "win32":
        ok = False  # no containment object: never claim a tree kill
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # group already gone
        except OSError:
            ok = False
    try:
        proc.kill()
    except OSError:
        pass
    return ok


def _drain(stream: Any, cap: int, sink: bytearray, exceeded: threading.Event) -> None:
    try:
        while True:
            chunk = stream.read1(65536) if hasattr(stream, "read1") else stream.read(65536)
            if not chunk:
                return
            room = cap - len(sink)
            if len(chunk) > room:
                sink.extend(chunk[: max(room, 0)])
                exceeded.set()
                return
            sink.extend(chunk)
    except (OSError, ValueError):
        return


def _execute(argv: list[str], pythonpath: Sequence[Path], limits: Limits) -> RunResult:
    started = time.monotonic()
    neutral = tempfile.mkdtemp(prefix="vst-aeve-")  # empty cwd: nothing from the candidate on sys.path
    # Windows: start suspended (0x4) so the Job Object is in place before the first instruction runs.
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0) | 0x4) if sys.platform == "win32" else 0
    detail = ""
    proc: subprocess.Popen | None = None
    job: _WinJob | None = None
    out, err = bytearray(), bytearray()
    out_over, err_over = threading.Event(), threading.Event()
    threads: list[threading.Thread] = []
    outcome: Outcome | None = None
    try:
        try:
            proc = subprocess.Popen(
                argv, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                # PYTHONPYCACHEPREFIX -> empty dir: no candidate/planted .pyc is ever read.
                env={**scrubbed_environment(pythonpath), "PYTHONPYCACHEPREFIX": neutral},
                cwd=neutral, creationflags=flags, start_new_session=sys.platform != "win32",
            )
        except (FileNotFoundError, PermissionError, NotADirectoryError) as exc:
            return RunResult(Outcome.MISSING_EXECUTABLE, None, b"", "", 0.0, tuple(argv), type(exc).__name__)
        except OSError as exc:
            return RunResult(Outcome.CRASH, None, b"", "", 0.0, tuple(argv), f"LAUNCH_FAILED: {type(exc).__name__}")
        if sys.platform == "win32":
            job = _attach_job(proc)  # assigned while still suspended
            if job is None or not job.resume(proc):
                _kill_tree(proc, job)  # the analyzer never ran: fail closed
                return RunResult(
                    Outcome.CONTAINMENT_FAILED, None, b"", "", time.monotonic() - started, tuple(argv),
                    "Job Object containment or resume failed; analyzer was not run",
                )
        threads = [
            threading.Thread(target=_drain, args=(proc.stdout, limits.max_stdout_bytes, out, out_over), daemon=True),
            threading.Thread(target=_drain, args=(proc.stderr, limits.max_stderr_bytes, err, err_over), daemon=True),
        ]
        for t in threads:
            t.start()
        deadline = started + limits.timeout_seconds
        while True:
            if out_over.is_set() or err_over.is_set():
                outcome = Outcome.OUTPUT_CAP
                break
            if proc.poll() is not None:
                break
            if time.monotonic() >= deadline:
                outcome = Outcome.TIMEOUT
                break
            time.sleep(0.02)
        kill_ok = True
        if outcome is not None:
            kill_ok = _kill_tree(proc, job)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            kill_ok = _kill_tree(proc, job) and kill_ok
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                kill_ok = False
        if proc.poll() is None or not kill_ok:
            outcome = Outcome.TERMINATION_FAILED
            detail = "termination of the analyzer process tree was not confirmed"
    finally:
        if proc is not None:
            if proc.poll() is None:
                _kill_tree(proc, job)
            for stream in (proc.stdout, proc.stderr):
                try:
                    if stream is not None:
                        stream.close()
                except OSError:
                    pass
        for t in threads:
            t.join(timeout=5)
        if job is not None:
            job.close()
        try:
            os.rmdir(neutral)
        except OSError:
            pass
    if outcome is None and (out_over.is_set() or err_over.is_set()):
        outcome = Outcome.OUTPUT_CAP
    code = proc.returncode if proc is not None else None
    if outcome is None:
        # AEVE: 0 = COMPLETE, 3 = PARTIAL (both print the JSON document); anything else is not a report.
        outcome = Outcome.OK if code in (0, 3) else Outcome.CRASH
    tail = bytes(err[-_STDERR_TAIL_BYTES:]).decode("utf-8", "replace")
    return RunResult(outcome, code, bytes(out), tail, time.monotonic() - started, tuple(argv), detail)


def run_analyzer(spec: AnalyzerSpec, root: str | os.PathLike[str], limits: Limits = Limits()) -> RunResult:
    """Run ``<python flags / launcher> analyze --root ROOT``: argv list, no shell, scrubbed env,
    empty cwd. Windows: fail-closed Job Object containment (tree kill is kernel-enforced);
    POSIX: killpg of a new session only (best effort). Unconfirmed kill => TERMINATION_FAILED."""
    real_root = os.path.realpath(os.fspath(root))
    try:
        argv, _ = resolve_argv(spec, real_root)
    except AdapterError as exc:
        if exc.code == "MISSING_EXECUTABLE":
            return RunResult(Outcome.MISSING_EXECUTABLE, None, b"", "", 0.0, tuple(spec.argv_prefix), str(exc))
        raise
    return _execute(argv, spec.pythonpath, limits)


# ------------------------------------------------------------------------ parser


def _invalid(message: str) -> AdapterError:
    return AdapterError("INVALID_OUTPUT", message)


def _hex64(value: object, name: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise _invalid(f"{name}: must be 64 lowercase hex characters")
    return value


def _aeve_analysis_digest(doc: Mapping[str, Any]) -> str:
    """AEVE's own integrity digest (engine.analyze): integrity only, never authenticity."""
    obj = {k: v for k, v in doc.items() if k != "analysis_sha256"}
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _flagged_paths(uncovered: Sequence[str], diagnostics: Sequence[Any]) -> set[str]:
    """Paths AEVE names in 'uncovered' ("KIND: path") or diagnostics ({"file": path})."""
    paths: set[str] = set()
    for item in uncovered:
        _, sep, rest = item.partition(": ")
        paths.add(rest if sep else item)
    for item in diagnostics:
        if isinstance(item, dict) and isinstance(item.get("file"), str):
            paths.add(item["file"])
    return paths


def parse_aeve_output(
    stdout: bytes,
    *,
    spec: AnalyzerSpec,
    scope: Sequence[str],
    required_rule_ids: Sequence[str],
    source: TreeDigest,
    analyzer_sha256: str,
    analyzer_version: str,
    profile_sha256: str,
    interpreter_sha256: str | None = None,
) -> AnalysisReport:
    """Convert AEVE JSON into the closed report. Raises AdapterError('INVALID_OUTPUT', ...)."""
    required = list(required_rule_ids)
    if (
        not required
        or not all(isinstance(r, str) and r.strip() == r and r for r in required)
        or len(set(required)) != len(required)
    ):
        raise AdapterError("RULES_INVALID", "required_rule_ids must be unique non-empty strings")
    scope_list = validate_scope(list(scope))
    scope_set = set(scope_list)
    scope_fold = {p.casefold() for p in scope_list}

    try:
        doc = json.loads(stdout.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise _invalid(f"not valid UTF-8 JSON: {type(exc).__name__}") from exc
    if not isinstance(doc, dict) or set(doc) != _AEVE_TOP_KEYS:
        raise _invalid("top-level keys do not match the g2.analysis.v1 shape")
    if doc["schema_version"] != spec.expected_schema_version:
        raise _invalid("schema_version mismatch")
    if doc["rules_version"] != spec.expected_rules_version:
        raise _invalid("rules_version differs from the pinned inventory version")
    if doc["status"] not in ("COMPLETE", "PARTIAL"):
        raise _invalid("status must be COMPLETE or PARTIAL")
    if doc["executed_project_code"] is not False or doc["llm_calls"] != 0 or isinstance(doc["llm_calls"], bool):
        raise _invalid("analyzer must report executed_project_code=false and llm_calls=0")
    aeve_snapshot = _hex64(doc["snapshot_sha256"], "snapshot_sha256")
    aeve_analysis = _hex64(doc["analysis_sha256"], "analysis_sha256")
    if _aeve_analysis_digest(doc) != aeve_analysis:
        raise _invalid("analysis_sha256 does not recompute from the document")
    uncovered, diagnostics = doc["uncovered"], doc["diagnostics"]
    if not isinstance(uncovered, list) or not all(isinstance(u, str) for u in uncovered):
        raise _invalid("uncovered must be a list of strings")
    if not isinstance(diagnostics, list) or not isinstance(doc["summary"], dict):
        raise _invalid("diagnostics/summary have the wrong type")
    raw_findings = doc["findings"]
    if not isinstance(raw_findings, list):
        raise _invalid("findings must be a list")

    # Why SUPPORTED_AND_CHECKED is withheld for inventory rules (first applicable reason wins).
    flagged_scope = sorted(_flagged_paths(uncovered, diagnostics) & scope_set)
    non_python = [p for p in scope_list if not p.lower().endswith(".py")]
    if non_python:
        downgrade = "SCOPE_NOT_ANALYZED_BY_AEVE"  # AEVE analyzes only *.py; non-.py files are never checked
    elif flagged_scope:
        downgrade = "SCOPE_PATH_UNCOVERED"
    elif doc["status"] != "COMPLETE":
        downgrade = "AEVE_STATUS_PARTIAL"
    elif uncovered or diagnostics:
        downgrade = "AEVE_UNCOVERED_PRESENT"
    else:
        downgrade = ""

    inventory = spec.rule_inventory
    statuses: list[dict[str, str]] = []
    reasons: dict[str, str] = {}
    for rule_id in sorted(required):
        if rule_id not in inventory:
            status, reason = "UNSUPPORTED", "NOT_IN_AEVE_INVENTORY"
        elif downgrade:
            status, reason = "UNSUPPORTED", downgrade
        else:
            status, reason = "SUPPORTED_AND_CHECKED", ""
        if status not in RULE_STATUS:
            raise AdapterError("INTERNAL", f"status {status!r} outside RULE_STATUS")
        statuses.append({"rule_id": rule_id, "status": status})
        if reason:
            reasons[rule_id] = reason
    checked = [s["rule_id"] for s in statuses if s["status"] == "SUPPORTED_AND_CHECKED"]
    unsupported = [s["rule_id"] for s in statuses if s["status"] == "UNSUPPORTED"]
    coverage = "FULL" if not unsupported else ("PARTIAL" if checked else "NOT_COVERED")
    if downgrade and coverage == "FULL":
        raise AdapterError("INTERNAL", "downgraded run must never be FULL")

    findings: list[dict[str, Any]] = []
    partial_findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    dropped_out_of_scope = dropped_non_required = merged_duplicates = 0
    for index, item in enumerate(raw_findings):
        ctx = f"findings[{index}]"
        if not isinstance(item, dict) or set(item) != _AEVE_FINDING_KEYS:
            raise _invalid(f"{ctx}: shape mismatch")
        rule_id, severity, path, line = item["rule_id"], item["severity"], item["file"], item["line"]
        if not isinstance(rule_id, str) or not rule_id or rule_id.endswith("-ANALYSIS-ERROR"):
            raise _invalid(f"{ctx}: invalid rule_id or analyzer-side rule failure ({rule_id!r})")
        if not isinstance(severity, str) or severity not in SEVERITY_MAP:
            raise _invalid(f"{ctx}: unknown severity")
        if not isinstance(path, str) or "\\" in path:
            raise _invalid(f"{ctx}: invalid file")
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            raise _invalid(f"{ctx}: invalid line")
        if reasons.get(rule_id) == "NOT_IN_AEVE_INVENTORY":
            raise _invalid(f"{ctx}: AEVE emitted rule {rule_id!r} that is missing from the pinned inventory")
        if rule_id not in checked and rule_id not in reasons:
            dropped_non_required += 1
            continue
        if path not in scope_set:
            if path.casefold() in scope_fold or posixpath.normpath(path) in scope_set:
                raise _invalid(f"{ctx}: finding path {path!r} aliases a scope file but is not its exact spelling")
            dropped_out_of_scope += 1
            continue
        entry = {
            "rule_id": rule_id,
            "severity": SEVERITY_MAP[severity],
            "evidence_ref": path,
            "evidence_sha256": source.file_sha256[path],
            "path": path,
            "line": line,
        }
        if tuple(sorted(entry)) != tuple(sorted(FINDING_FIELDS)):
            raise AdapterError("INTERNAL", "finding fields drifted from FINDING_FIELDS")
        key = canonical_bytes(entry).decode("ascii")
        if key in seen:
            merged_duplicates += 1
            continue
        seen.add(key)
        (findings if rule_id in checked else partial_findings).append(entry)
    order = lambda f: (f["path"], f["line"], f["rule_id"], f["severity"])  # noqa: E731
    findings.sort(key=order)
    partial_findings.sort(key=order)

    body = {
        "label": REPORT_LABEL,
        "analyzer_id": spec.analyzer_id,
        "analyzer_version": analyzer_version,
        "analyzer_sha256": analyzer_sha256,
        "interpreter_sha256": interpreter_sha256,
        "profile_id": spec.profile_id,
        "profile_sha256": profile_sha256,
        "source_tree_sha256": source.sha256,
        "analysis_scope": scope_list,
        "license_status": LICENSE_STATUS_UNKNOWN,
        "aeve_schema_version": doc["schema_version"],
        "aeve_rules_version": doc["rules_version"],
        "aeve_status": doc["status"],
        "aeve_snapshot_sha256": aeve_snapshot,
        "aeve_analysis_sha256": aeve_analysis,
        "aeve_uncovered": sorted(set(uncovered)),
        "scope_flagged_paths": flagged_scope,
        "scope_non_python_paths": non_python,
        "coverage": coverage,
        "rule_statuses": statuses,
        "covered_rules": checked,
        "unsupported_rules": unsupported,
        "unsupported_reasons": {k: reasons[k] for k in sorted(reasons)},
        "findings": findings,
        "partial_findings": partial_findings,
        "accounting": {
            "aeve_findings_total": len(raw_findings),
            "dropped_not_required_rule": dropped_non_required,
            "dropped_out_of_scope": dropped_out_of_scope,
            "merged_duplicates": merged_duplicates,
        },
    }
    return AnalysisReport(body)


# ------------------------------------------------------------------ orchestration

_INFORMATIONAL_UNKNOWN = (
    "license",
    "per_file_analysis_confirmation",  # AEVE prints no list of analyzed files
    "rule_emission_not_proven",  # inventory is a declaration; COMPLETE is the only evidence of checking
    # Not part of the pinned closure (only the interpreter file itself is hashed):
    "interpreter_runtime_and_stdlib_not_in_closure",
    "interpreter_site_packages_not_in_closure",
    "pythonpath_exclusions_are_unhashed_but_importable",  # only meaningful when exclusions are used
)


def analyze_snapshot(
    spec: AnalyzerSpec,
    snapshot_root: str | os.PathLike[str],
    scope: Sequence[str],
    required_rule_ids: Sequence[str],
    candidate_head: str,
    limits: Limits = Limits(),
) -> AdapterResult:
    """Digest inputs, run AEVE, parse, then re-verify HEAD/clean tree/source/analyzer.

    Never signs, never holds keys. ``snapshot_root`` is the exact git root of the
    candidate snapshot. Input/binding refusals before the run raise AdapterError;
    run, parse and post-run recheck failures are returned as typed outcomes.
    """
    real_root = os.path.realpath(os.fspath(snapshot_root))
    source = source_tree_digest(real_root, scope, candidate_head, limits)
    a_tree = analyzer_tree_digest(spec, limits)
    a_sha = a_tree.sha256
    if spec.version_file not in a_tree.file_sha256:
        raise AdapterError("VERSION_FILE_NOT_PINNED", "version_file must be listed in analyzer_files")
    version_sha = a_tree.file_sha256[spec.version_file]
    version = read_declared_version(spec, version_sha)  # version comes from the pinned bytes
    p_sha = profile_digest(spec)
    blocking: list[str] = []
    interp_sha: str | None = None
    run: RunResult | None = None

    def result(outcome: Outcome, detail: str, report: AnalysisReport | None = None) -> AdapterResult:
        return AdapterResult(
            outcome, detail, run, report, source.sha256, a_sha, p_sha, version, candidate_head,
            unknown=_INFORMATIONAL_UNKNOWN, blocking_unknown=tuple(blocking),
        )

    try:
        argv, resolved = resolve_argv(spec, real_root)
    except AdapterError as exc:
        if exc.code != "MISSING_EXECUTABLE":
            raise
        return result(Outcome.MISSING_EXECUTABLE, str(exc))
    interp_sha = _file_sha256(resolved, limits.max_analyzer_file_bytes)
    if interp_sha is None:
        blocking.append("interpreter_sha256")

    run = _execute(argv, spec.pythonpath, limits)
    if run.outcome is not Outcome.OK:
        return result(run.outcome, run.detail or run.stderr_tail)

    # Post-run: the analyzer, interpreter, git state and scope bytes must be unchanged.
    try:
        if analyzer_digest(spec, limits) != a_sha:
            return result(Outcome.INVALID_OUTPUT, "ANALYZER_MODIFIED_DURING_ANALYSIS")
        if read_declared_version(spec, version_sha) != version:
            return result(Outcome.INVALID_OUTPUT, "VERSION_CHANGED_DURING_ANALYSIS")
        if _file_sha256(resolved, limits.max_analyzer_file_bytes) != interp_sha:
            return result(Outcome.INVALID_OUTPUT, "INTERPRETER_MODIFIED_DURING_ANALYSIS")
        after = source_tree_digest(real_root, scope, candidate_head, limits)
    except AdapterError as exc:
        return result(Outcome.INVALID_OUTPUT, f"POST_RUN_RECHECK_FAILED: {exc}")
    if after.sha256 != source.sha256:
        return result(Outcome.INVALID_OUTPUT, "SOURCE_MODIFIED_DURING_ANALYSIS")

    try:
        report = parse_aeve_output(
            run.stdout,
            spec=spec,
            scope=scope,
            required_rule_ids=required_rule_ids,
            source=source,
            analyzer_sha256=a_sha,
            analyzer_version=f"{version}/{spec.expected_rules_version}",
            profile_sha256=p_sha,
            interpreter_sha256=interp_sha,
        )
    except AdapterError as exc:
        if exc.code in ("RULES_INVALID", "INTERNAL"):
            raise
        return result(Outcome.INVALID_OUTPUT, str(exc))
    if report.body["partial_findings"]:
        return result(Outcome.PARTIAL_WITH_FINDINGS, "findings exist for rules whose coverage was withheld", report)
    return result(Outcome.OK, "", report)


def static_analysis_fields(report: AnalysisReport) -> dict[str, Any]:
    """v3 StaticAnalysis receipt fields derivable from the report (covered_acceptance is
    manifest-derived and intentionally absent; partial_findings stay only in the report)."""
    b = report.body
    return {
        "analyzer_id": b["analyzer_id"],
        "analyzer_version": b["analyzer_version"],
        "analyzer_sha256": b["analyzer_sha256"],
        "profile_id": b["profile_id"],
        "profile_sha256": b["profile_sha256"],
        "source_tree_sha256": b["source_tree_sha256"],
        "analysis_scope": list(b["analysis_scope"]),
        "report_sha256": report.report_sha256,
        "coverage": b["coverage"],
        "covered_rules": list(b["covered_rules"]),
        "unsupported_rules": list(b["unsupported_rules"]),
        "rule_statuses": [dict(s) for s in b["rule_statuses"]],
        "findings": [dict(f) for f in b["findings"]],
    }


_UC_TO_BRIDGE_SEVERITY = {"NIT": "LOW", "MINOR": "MEDIUM", "MAJOR": "HIGH", "BLOCKER": "CRITICAL"}
_UC_SEVERITY_ORDER = ("NIT", "MINOR", "MAJOR", "BLOCKER")


def bridge_facts_from_role_result(
    role_result: Mapping[str, Any],
    role: str,
    reviewed_paths: Sequence[str],
    *,
    expected_base_revision: str,
) -> dict[str, Any]:
    """U2-1 bridge facts for one role of a uc.role-result.v1, strictly validated.

    The whole result goes through tools.uc.contracts.validate_result first (exact containers, closed
    key sets, token formats, sorted unique model_residual of at most 8 tokens, 40-hex aeve_head).
    Refused with ContractError: a result that fails that validation; a result whose base_revision
    differs from ``expected_base_revision`` (the caller passes the candidate head); no entry or more
    than one entry for ``role``; an entry whose status is not CLEAN or FINDINGS; an entry with a
    non-empty ``uncovered`` list; a LOCAL_PLUS_MODEL entry with an empty ``model_residual``;
    ``reviewed_paths`` that is not a non-empty list/tuple of unique plain repo-relative paths (a bare
    str, duplicates and an empty list are refused); (U2-3) a result whose ``purpose`` is not "receipt";
    a result whose ``changed_paths_sha256`` differs from the sha256 of the canonical bytes of
    sorted(reviewed_paths) (the same hashing as ``reviewed_paths_sha256``). model_residual is never
    repaired or reordered.

    Facts: ``role_table_sha256`` and ``aeve_head`` are the result's top-level values; ``model_residual``
    is the entry's list; ``reviewed_paths_sha256`` is the sha256 of the canonical bytes of the sorted
    path list; ``findings_count``/``highest_severity`` summarize that role's findings (U1
    NIT/MINOR/MAJOR/BLOCKER map to LOW/MEDIUM/HIGH/CRITICAL; none -> 0 / NONE). The output is also
    checked with validate_bridge_facts. No gate decision and no pin comparison happen here (U2-4).
    """
    from ..uc import contracts as uc_contracts
    from .contracts import _req_hex, _req_plain_repo_path, validate_bridge_facts

    _req_hex(expected_base_revision, "expected_base_revision", 40)
    if not isinstance(role, str) or not role:
        raise ContractError("role: must be a non-empty string")
    try:
        uc_contracts.validate_result(role_result)
    except uc_contracts.ContractError as exc:
        raise ContractError(f"role result: invalid ({exc.code} at {exc.where})") from exc
    if role_result["base_revision"] != expected_base_revision:
        raise ContractError("role result: base_revision differs from expected_base_revision")
    if role_result["purpose"] != "receipt":
        raise ContractError("role result: purpose is not 'receipt' (an advisory review cannot back a receipt)")
    entries = [e for e in role_result["roles"] if e["role"] == role]
    if len(entries) != 1:
        raise ContractError(f"role result: expected exactly one entry for role {role!r}")
    entry = entries[0]
    if entry["status"] not in ("CLEAN", "FINDINGS"):
        raise ContractError(f"role result: entry status {entry['status']!r} is neither CLEAN nor FINDINGS")
    if entry["uncovered"]:
        raise ContractError("role result: entry has uncovered scope")
    if entry["class"] == "LOCAL_PLUS_MODEL" and not entry["model_residual"]:
        raise ContractError("role result: LOCAL_PLUS_MODEL entry without a model_residual")
    if not isinstance(reviewed_paths, (list, tuple)) or not reviewed_paths:
        raise ContractError("reviewed_paths: must be a non-empty list of paths")
    for index, path in enumerate(reviewed_paths):
        _req_plain_repo_path(path, f"reviewed_paths[{index}]")
    if len(set(reviewed_paths)) != len(reviewed_paths):
        raise ContractError("reviewed_paths: must not contain duplicates")
    reviewed_hash = hashlib.sha256(canonical_bytes(sorted(reviewed_paths))).hexdigest()
    if role_result["changed_paths_sha256"] != reviewed_hash:
        raise ContractError("role result: changed_paths_sha256 differs from the hash of the reviewed paths")
    severities = [f["severity"] for f in entry["findings"]]  # validate_result closed the enum
    highest = (
        _UC_TO_BRIDGE_SEVERITY[max(severities, key=_UC_SEVERITY_ORDER.index)] if severities else "NONE"
    )
    facts = {
        "role_table_sha256": role_result["role_table_sha256"],
        "aeve_head": role_result["aeve_head"],
        "model_residual": list(entry["model_residual"]),
        "reviewed_paths_sha256": reviewed_hash,
        "findings_count": len(severities),
        "highest_severity": highest,
    }
    validate_bridge_facts(facts)
    return facts


def assemble_analyzer_payload(
    result: AdapterResult,
    *,
    manifest_sha256: str,
    run_id: str,
    nonce: str,
    candidate_head: str,
    epoch: int,
    bridge: Mapping[str, Any],
) -> dict[str, Any]:
    """Unsigned payload for analyzer_authority.sign_analyzer_evidence.

    ``bridge`` holds exactly the BRIDGE_FACT_FIELDS (see bridge_facts_from_role_result); the same dict
    must be merged into the receipt body next to static_analysis_fields(report).

    Refuses when the run was not OK/PARTIAL_WITH_FINDINGS, when any binding is still
    unknown (``blocking_unknown``), or when candidate_head differs from the head the
    run was bound to. Manifest digest, run id, nonce, head and epoch come from VST.
    """
    if result.outcome not in _PAYLOAD_OUTCOMES or result.report is None:
        raise AdapterError("NOT_OK", f"cannot assemble payload for outcome {result.outcome.value}")
    if result.blocking_unknown:
        raise AdapterError("BINDING_UNKNOWN", f"unknown bindings: {', '.join(result.blocking_unknown)}")
    if result.candidate_head is None or candidate_head != result.candidate_head:
        raise AdapterError("HEAD_MISMATCH", "candidate_head differs from the head the analysis was bound to")
    fields = static_analysis_fields(result.report)
    from .contracts import BRIDGE_FACT_FIELDS

    if not isinstance(bridge, Mapping) or set(bridge) != set(BRIDGE_FACT_FIELDS):
        raise AdapterError("BRIDGE_FACTS", f"bridge must hold exactly {list(BRIDGE_FACT_FIELDS)}")
    return build_analyzer_payload(
        analyzer_id=fields["analyzer_id"],
        analyzer_version=fields["analyzer_version"],
        analyzer_sha256=fields["analyzer_sha256"],
        profile_id=fields["profile_id"],
        profile_sha256=fields["profile_sha256"],
        source_tree_sha256=fields["source_tree_sha256"],
        report_sha256=fields["report_sha256"],
        manifest_sha256=manifest_sha256,
        run_id=run_id,
        nonce=nonce,
        candidate_head=candidate_head,
        epoch=epoch,
        analysis_scope=fields["analysis_scope"],
        **{name: bridge[name] for name in BRIDGE_FACT_FIELDS},
    )
