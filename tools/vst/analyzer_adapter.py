"""Bounded, read-only AEVE analyzer adapter and deterministic snapshot hashing (S5-C, VST-040).

Everything here is deterministic, token-free stdlib Python: no model call, no
network call, no signing and no key material. VST trusted code computes every
digest itself (source tree, analyzer files, profile, report); nothing the
analyzer prints is trusted as a digest of VST-owned data. Signing stays in
analyzer_authority.sign_analyzer_evidence (never called from this module).

What AEVE actually exposes (read from D:\\Repo\\AEVE, never imported or executed
by this module's author):
  * ``aeve analyze --root PATH [--allow-dirty]`` captures the tracked files of
    the WHOLE git root at HEAD and prints one JSON document (schema
    ``g2.analysis.v1``, rules ``g2.rules.v15``). It has NO scope option, NO
    profile option, and prints NO rule inventory and NO head. Exit 0 = COMPLETE,
    3 = PARTIAL, 2 = blocked (stderr). This adapter never passes --allow-dirty.
  * The only machine-readable inventory is the ``g2.*`` analysis executors in
    ``aeve.governance.matrix.EXECUTORS`` (a declaration, not proof that every
    id is emitted for every file). It is pinned below as AEVE_G2_RULE_INVENTORY
    together with the rules version it was read at.
  * AEVE provides no license text, no evidence artifacts and no signature.
    The analyzer version is read by VST from ``__version__`` in a file, the
    executable digest is computed by VST from explicit files, the license is
    reported as UNKNOWN.

Resource boundaries enforced HERE: argv list (no shell), scrubbed environment,
wall-clock timeout, stdout/stderr byte caps, per-file and total input caps, a
post-run source-tree recheck. NOT enforced here (NOT_RUN, belongs to the S2
sandbox): OS-level network denial, read-only mounts, CPU/memory limits and
killing grandchild processes. "No network use" holds by construction only in
the sense that this module opens no socket and passes no endpoint or credential.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
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

SOURCE_TREE_LABEL = b"vst-source-tree-v1\0"
REPORT_LABEL = "vst-analyzer-report-v1"
PROFILE_LABEL = "vst-aeve-profile-v1"
AEVE_SCHEMA_VERSION = "g2.analysis.v1"
AEVE_RULES_VERSION = "g2.rules.v15"
LICENSE_STATUS_UNKNOWN = "UNKNOWN"

# AEVE severity -> VST closed enum. AEVE has no MEDIUM tier; MINOR->LOW is a
# conservative, documented choice (see the hand-off ambiguity list).
SEVERITY_MAP = {"BLOCKER": "CRITICAL", "MAJOR": "HIGH", "MINOR": "LOW", "INFO": "INFO"}
assert set(SEVERITY_MAP.values()) <= FINDING_SEVERITY

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
}
_REPARSE_POINT = 0x400
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
)
_HEX64 = re.compile(r"[0-9a-f]{64}")
_AEVE_TOP_KEYS = frozenset({
    "schema_version", "rules_version", "status", "snapshot_sha256", "analysis_sha256",
    "findings", "summary", "diagnostics", "uncovered", "executed_project_code", "llm_calls",
})
_AEVE_FINDING_KEYS = frozenset({"rule_id", "severity", "confidence", "file", "line", "message", "detail"})
_STDERR_TAIL_BYTES = 2000


# ----------------------------------------------------------------- errors/types


class AdapterError(ValueError):
    """Typed refusal raised before or around a run (scope, input, digest problems)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class Outcome(str, Enum):
    OK = "OK"
    TIMEOUT = "TIMEOUT"
    OUTPUT_CAP = "OUTPUT_CAP"
    CRASH = "CRASH"
    MISSING_EXECUTABLE = "MISSING_EXECUTABLE"
    INVALID_OUTPUT = "INVALID_OUTPUT"


@dataclass(frozen=True)
class Limits:
    timeout_seconds: float = 120.0
    max_stdout_bytes: int = 8_000_000
    max_stderr_bytes: int = 200_000
    max_file_bytes: int = 2_000_000
    max_total_input_bytes: int = 64_000_000
    max_analyzer_file_bytes: int = 16_000_000
    max_analyzer_total_bytes: int = 256_000_000


@dataclass(frozen=True)
class AnalyzerSpec:
    """Pinned analyzer identity. argv_prefix e.g. (python, "-m", "aeve") or (aeve_exe,)."""

    argv_prefix: tuple[str, ...]
    analyzer_root: Path
    analyzer_files: tuple[str, ...]  # explicit sorted repo-relative files hashed as the analyzer
    version_file: str  # relative to analyzer_root, contains __version__ = "x"
    profile_id: str
    analyzer_id: str = "aeve"
    pythonpath: tuple[Path, ...] = ()
    rule_inventory: frozenset[str] = AEVE_G2_RULE_INVENTORY
    expected_schema_version: str = AEVE_SCHEMA_VERSION
    expected_rules_version: str = AEVE_RULES_VERSION
    version_pattern: str = r'^__version__\s*=\s*"([^"\n]+)"\s*$'


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
    license_status: str = LICENSE_STATUS_UNKNOWN
    unknown: tuple[str, ...] = field(default_factory=tuple)


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
    try:
        inside = os.path.commonpath([os.path.normcase(real_root), os.path.normcase(real)]) == os.path.normcase(real_root)
    except ValueError:
        inside = False
    if not inside:
        raise AdapterError("SCOPE_ESCAPE", f"{rel}: resolves outside the root")
    return current


def tree_digest(
    root: str | os.PathLike[str],
    files: Sequence[str],
    *,
    max_file_bytes: int,
    max_total_bytes: int,
    label: bytes = SOURCE_TREE_LABEL,
) -> TreeDigest:
    """Deterministic digest over an explicit sorted file list (versioned by ``label``).

    Layout: label | count(8) | per file: len(path)(8) path size(8) sha256(32).
    """
    paths = validate_scope(list(files))
    real_root = os.path.realpath(os.fspath(root))
    if not os.path.isdir(real_root):
        raise AdapterError("ROOT_INVALID", "root is not a directory")
    outer = hashlib.sha256()
    outer.update(label)
    outer.update(len(paths).to_bytes(8, "big"))
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
        path_bytes = rel.encode("utf-8")
        outer.update(len(path_bytes).to_bytes(8, "big"))
        outer.update(path_bytes)
        outer.update(size.to_bytes(8, "big"))
        outer.update(inner.digest())
    return TreeDigest(outer.hexdigest(), digests, sizes, total)


def source_tree_digest(root: str | os.PathLike[str], scope: Sequence[str], limits: Limits = Limits()) -> TreeDigest:
    """Source-tree digest over the manifest scope (the value bound as source_tree_sha256)."""
    return tree_digest(
        root, scope, max_file_bytes=limits.max_file_bytes, max_total_bytes=limits.max_total_input_bytes
    )


# ------------------------------------------------------------- identity digests


def analyzer_digest(spec: AnalyzerSpec, limits: Limits = Limits()) -> str:
    """analyzer_sha256: VST-computed digest of the explicit analyzer file list."""
    return tree_digest(
        spec.analyzer_root,
        spec.analyzer_files,
        max_file_bytes=limits.max_analyzer_file_bytes,
        max_total_bytes=limits.max_analyzer_total_bytes,
        label=b"vst-analyzer-files-v1\0",
    ).sha256


def read_declared_version(spec: AnalyzerSpec) -> str:
    """Read ``__version__`` by regex from the version file (never imports the analyzer)."""
    validate_scope([spec.version_file])
    real_root = os.path.realpath(os.fspath(spec.analyzer_root))
    full = _resolve_regular_file(real_root, spec.version_file)
    try:
        with open(full, "rb") as handle:
            data = handle.read(1_000_001)
        if len(data) > 1_000_000:
            raise AdapterError("VERSION_FILE_TOO_LARGE", spec.version_file)
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


# ----------------------------------------------------------------- bounded runner


def scrubbed_environment(pythonpath: Sequence[Path] = ()) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() in _ENV_ALLOW}
    env.update(_ENV_FIXED)
    if pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(os.fspath(p) for p in pythonpath)
    return env


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


def run_analyzer(spec: AnalyzerSpec, root: str | os.PathLike[str], limits: Limits = Limits()) -> RunResult:
    """Run ``<argv_prefix> analyze --root ROOT`` with an argv list, no shell, scrubbed env."""
    if not spec.argv_prefix or not all(isinstance(a, str) and a and "\0" not in a for a in spec.argv_prefix):
        raise AdapterError("ARGV_INVALID", "argv_prefix must be non-empty strings")
    argv = [*spec.argv_prefix, "analyze", "--root", os.fspath(root)]
    started = time.monotonic()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    try:
        proc = subprocess.Popen(
            argv,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=scrubbed_environment(spec.pythonpath),
            cwd=os.fspath(root),
            creationflags=flags,
        )
    except (FileNotFoundError, PermissionError, NotADirectoryError) as exc:
        return RunResult(Outcome.MISSING_EXECUTABLE, None, b"", "", 0.0, tuple(argv), type(exc).__name__)
    except OSError as exc:
        return RunResult(Outcome.CRASH, None, b"", "", 0.0, tuple(argv), f"LAUNCH_FAILED: {type(exc).__name__}")

    out, err = bytearray(), bytearray()
    out_over, err_over = threading.Event(), threading.Event()
    threads = [
        threading.Thread(target=_drain, args=(proc.stdout, limits.max_stdout_bytes, out, out_over), daemon=True),
        threading.Thread(target=_drain, args=(proc.stderr, limits.max_stderr_bytes, err, err_over), daemon=True),
    ]
    for t in threads:
        t.start()
    deadline = started + limits.timeout_seconds
    outcome: Outcome | None = None
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
    if outcome is not None:
        proc.kill()  # grandchildren are the S2 sandbox's job (NOT_RUN here)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        outcome = outcome or Outcome.CRASH
    for t in threads:
        t.join(timeout=5)
    if outcome is None and (out_over.is_set() or err_over.is_set()):
        outcome = Outcome.OUTPUT_CAP
    elapsed = time.monotonic() - started
    tail = bytes(err[-_STDERR_TAIL_BYTES:]).decode("utf-8", "replace")
    code = proc.returncode
    if outcome is None:
        # AEVE: 0 = COMPLETE, 3 = PARTIAL (both print the JSON document); anything else is not a report.
        outcome = Outcome.OK if code in (0, 3) else Outcome.CRASH
    return RunResult(outcome, code, bytes(out), tail, elapsed, tuple(argv), "")


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
    uncovered = doc["uncovered"]
    if not isinstance(uncovered, list) or not all(isinstance(u, str) for u in uncovered):
        raise _invalid("uncovered must be a list of strings")
    if not isinstance(doc["diagnostics"], list) or not isinstance(doc["summary"], dict):
        raise _invalid("diagnostics/summary have the wrong type")
    raw_findings = doc["findings"]
    if not isinstance(raw_findings, list):
        raise _invalid("findings must be a list")

    complete = doc["status"] == "COMPLETE"
    inventory = spec.rule_inventory
    statuses: list[dict[str, str]] = []
    reasons: dict[str, str] = {}
    for rule_id in sorted(required):
        if rule_id not in inventory:
            status, reason = "UNSUPPORTED", "NOT_IN_AEVE_INVENTORY"
        elif not complete:
            status, reason = "UNSUPPORTED", "AEVE_STATUS_PARTIAL"
        else:
            status, reason = "SUPPORTED_AND_CHECKED", ""
        assert status in RULE_STATUS
        statuses.append({"rule_id": rule_id, "status": status})
        if reason:
            reasons[rule_id] = reason
    checked = [s["rule_id"] for s in statuses if s["status"] == "SUPPORTED_AND_CHECKED"]
    unsupported = [s["rule_id"] for s in statuses if s["status"] == "UNSUPPORTED"]
    coverage = "FULL" if not unsupported else ("PARTIAL" if checked else "NOT_COVERED")

    findings: list[dict[str, Any]] = []
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
        if rule_id in unsupported:
            raise _invalid(f"{ctx}: finding for rule {rule_id!r} that VST marks UNSUPPORTED")
        if rule_id not in checked:
            dropped_non_required += 1
            continue
        if path not in scope_set:
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
        assert tuple(sorted(entry)) == tuple(sorted(FINDING_FIELDS))
        key = canonical_bytes(entry).decode("ascii")
        if key in seen:
            merged_duplicates += 1
            continue
        seen.add(key)
        findings.append(entry)
    findings.sort(key=lambda f: (f["path"], f["line"], f["rule_id"], f["severity"]))

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
        "coverage": coverage,
        "rule_statuses": statuses,
        "covered_rules": checked,
        "unsupported_rules": unsupported,
        "unsupported_reasons": {k: reasons[k] for k in sorted(reasons)},
        "findings": findings,
        "accounting": {
            "aeve_findings_total": len(raw_findings),
            "dropped_not_required_rule": dropped_non_required,
            "dropped_out_of_scope": dropped_out_of_scope,
            "merged_duplicates": merged_duplicates,
        },
    }
    return AnalysisReport(body)


# ------------------------------------------------------------------ orchestration


def analyze_snapshot(
    spec: AnalyzerSpec,
    snapshot_root: str | os.PathLike[str],
    scope: Sequence[str],
    required_rule_ids: Sequence[str],
    limits: Limits = Limits(),
) -> AdapterResult:
    """Digest inputs, run AEVE, parse, recheck the source tree. Never signs, never holds keys.

    ``snapshot_root`` must be the clean git root of the immutable candidate snapshot
    (AEVE refuses a dirty tree because --allow-dirty is never passed). Input
    refusals raise AdapterError; run/parse outcomes are returned typed.
    """
    source = source_tree_digest(snapshot_root, scope, limits)
    a_sha = analyzer_digest(spec, limits)
    version = read_declared_version(spec)
    p_sha = profile_digest(spec)
    interpreter = spec.argv_prefix[0]
    interp_sha = _file_sha256(interpreter, limits.max_analyzer_file_bytes) if os.path.isfile(interpreter) else None
    unknown = ["license"] + ([] if interp_sha else ["interpreter_sha256"]) + ["aeve_head_binding"]

    def failed(outcome: Outcome, detail: str, run: RunResult | None) -> AdapterResult:
        return AdapterResult(
            outcome, detail, run, None, source.sha256, a_sha, p_sha, version, unknown=tuple(unknown)
        )

    run = run_analyzer(spec, snapshot_root, limits)
    if run.outcome is not Outcome.OK:
        return failed(run.outcome, run.detail or run.stderr_tail, run)
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
        if exc.code == "RULES_INVALID":
            raise
        return failed(Outcome.INVALID_OUTPUT, str(exc), run)
    after = source_tree_digest(snapshot_root, scope, limits)
    if after.sha256 != source.sha256:
        return failed(Outcome.INVALID_OUTPUT, "SOURCE_MODIFIED_DURING_ANALYSIS", run)
    return AdapterResult(
        Outcome.OK, "", run, report, source.sha256, a_sha, p_sha, version, unknown=tuple(unknown)
    )


def static_analysis_fields(report: AnalysisReport) -> dict[str, Any]:
    """v3 StaticAnalysis receipt fields derivable from the report (covered_acceptance is
    manifest-derived and intentionally absent)."""
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


def assemble_analyzer_payload(
    result: AdapterResult,
    *,
    manifest_sha256: str,
    run_id: str,
    nonce: str,
    candidate_head: str,
    epoch: int,
) -> dict[str, Any]:
    """Unsigned payload for analyzer_authority.sign_analyzer_evidence. Raises if the run was
    not OK. Manifest digest, run id, nonce, head and epoch come from VST, never from AEVE."""
    if result.outcome is not Outcome.OK or result.report is None:
        raise AdapterError("NOT_OK", f"cannot assemble payload for outcome {result.outcome.value}")
    fields = static_analysis_fields(result.report)
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
    )
