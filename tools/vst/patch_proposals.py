"""U5-2: apply AEVE patch proposals through the deterministic diff gate (Windows-local).

Operator decision OD-8 (2026-11-08): AEVE's repair lab proposes bounded patches and never applies
one; VST applies them in the isolated worktree and the diff gate checks them; the model writes code
only for what AEVE proposed no patch for. Everything here fails closed. Verdicts as in U5-1:

* ACCEPTED - the proposal was valid, the base matched, the patch applied, the resulting diff
  passed ``worker_gate.gate_worker_change`` and the worktree now holds exactly that change.
* REFUSED  - a definite policy violation: stale base, out-of-scope or protected path, path trick,
  a gate refusal, or a model change on a path AEVE proposed a patch for.
* BLOCKED  - the decision cannot be made: malformed or oversized proposal, recipe label that does
  not match the diff, untrusted repository configuration, lock held, git failure, dirty worktree,
  timeout, unexpected exception. BLOCKED is never an acceptance.

The real AEVE proposal format (``g6.patch.v1``, AEVE origin/main src/aeve/repair/patch.py) carries
no base identity and no machine-readable bounds: each proposal is ``{file, recipe, detail, diff,
changed}`` with a per-file unified diff that has ``--- file`` / ``+++ file`` headers (no ``a/``,
``b/`` prefix, no ``diff --git`` line). The only integrity field is ``report_sha256``; it is an
integrity check of the document, not proof of who made it. AEVE has no CLI command that emits the
document, so this module takes the JSON as input and validates it strictly. Base identity is
enforced by VST: the caller states the head AEVE analysed, the worktree HEAD must equal the pinned
base, the base file bytes must be representable by AEVE's diffs, and every hunk must apply to the
base content. The recipe label is checked against the diff text (RECIPE_MISMATCH).

Nothing touches the worktree until the whole change was built in a throw-away index and object
directory and accepted by the gate. The write itself is done in Python (temp file plus os.replace),
never by git, so no smudge filter or hook can run. See docs/sdlc/u5/PATCH_PROPOSALS.md.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import worker_gate as wg
from .worker_gate import ACCEPTED, BLOCKED, REFUSED, IsolationContext, WorkerGateVerdict

PROPOSAL_SCHEMA = "g6.patch.v1"
SHARE_SCHEMA = "vst-change-origin-share-v1"
RUN_RECORD_SCHEMA = "vst-patch-run-record-v1"

MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_PROPOSALS = 256
MAX_DIFF_BYTES_PER_PROPOSAL = 512 * 1024
MAX_TOTAL_DIFF_BYTES = 4 * 1024 * 1024
MAX_FIELD_CHARS = 2000
MAX_HUNK_LINES = 100000
MAX_GIT_OUTPUT = 16 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_CONFIG_BYTES = 1024 * 1024
DEFAULT_GIT_TIMEOUT = 30.0
MIN_OVERRIDE_REASON = 10
MAX_OVERRIDE_REASON = 500
MAX_AUTHORIZED_BY = 100
MAX_OVERRIDES = 16
LOCK_NAME = "vst-u5-2.lock"
JOURNAL_NAME = "vst-u5-2.journal"

# Recipes AEVE can emit (patch.py:175-222) and the ones that carry a diff.
PATCH_RECIPES = ("trailing-whitespace", "final-newline")
NOTE_RECIPES = ("unused-import", "unsupported-language", "encoding-skip", "parse-error")
_DOCUMENT_KEYS = {"schema_version", "proposals", "proposal_count", "llm_calls", "executed_project_code",
                  "note", "status", "uncovered", "report_sha256"}
_PROPOSAL_KEYS = {"file", "recipe", "detail", "diff", "changed"}

_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HUNK = re.compile(r"@@ -(\d{1,9})(?:,(\d{1,9}))? \+(\d{1,9})(?:,(\d{1,9}))? @@\Z")
_NO_NEWLINE = "\\ No newline at end of file"
_GLOB_CHARS = set("*?[]")
_REDACTION_MARKER = "[REDACTED]"
# Characters AEVE's str.splitlines() treats as line ends besides \n (and \r), plus the BOM it strips.
_SPLITLINES_ONLY = set("\r\x0b\x0c\x1c\x1d\x1e\x85  ")
_BOM = b"\xef\xbb\xbf"
_STALE_TEXT = re.compile(r"patch does not apply|patch failed|does not match index")

_NULL = os.devnull
# Prefix of every git call. Repository-local filters, attributes, hooks, line-ending rewrites and
# fsmonitor are switched off on the command line; the repository config is also scanned (see below).
GIT_PREFIX = (
    "--literal-pathspecs",
    "-c", "core.fsmonitor=false",
    "-c", "commit.gpgsign=false",
    "-c", f"core.attributesFile={_NULL}",
    "-c", f"core.hooksPath={_NULL}",
    "-c", "core.autocrlf=false",
    "-c", "core.safecrlf=false",
    "-c", "core.quotepath=false",
)

# Repository-local configuration that can make git run a program or change content: refused.
_CONFIG_HAZARDS = (
    ("filter section", re.compile(r"^\s*\[\s*filter\b", re.I | re.M)),
    ("include or includeIf", re.compile(r"^\s*\[\s*include", re.I | re.M)),
    ("extensions", re.compile(r"^\s*\[\s*extensions\b", re.I | re.M)),
    ("diff driver section", re.compile(r"^\s*\[\s*diff\s+\"", re.I | re.M)),
    ("core.attributesFile / hooksPath / fsmonitor / worktree", re.compile(r"^\s*(attributesfile|hookspath|fsmonitor|worktree)\s*=", re.I | re.M)),
    ("attr section (attr.tree)", re.compile(r"^\s*\[\s*attr\b", re.I | re.M)),
    ("textconv or command", re.compile(r"^\s*(textconv|command)\s*=", re.I | re.M)),
)
# Attributes that can run a program or rewrite content, blocked whatever their state or value (names are
# compared case-insensitively, so a mixed-case spelling cannot slip past). `diff` and `merge` are blocked only
# with a value (a driver name); the plain `diff`, `-diff`, `merge` and `-merge` forms select no driver.
_BLOCKED_ATTRIBUTES = frozenset({"filter", "ident", "working-tree-encoding", "crlf", "export-subst"})
_DRIVER_ATTRIBUTES = frozenset({"diff", "merge"})
# Line-ending attributes that only describe the file and are allowed in exactly these spellings (operator
# decision of 2026-11-11, R-27): `text`, `-text`, `!text`, `text=auto`, `eol=lf`, `eol=crlf`, `-eol`, `!eol`.
_ALLOWED_EOL_TOKENS = frozenset({"text", "-text", "!text", "text=auto", "eol=lf", "eol=crlf", "-eol", "!eol"})
# git splits a file only at LF and treats exactly space, tab, CR and LF as blanks; \v, \f, \x85, U+2028 and the like
# are ordinary characters to git, so they must not split a line or a token here (a file holding one is refused).
_ATTRIBUTE_WHITESPACE = " \t\r\n"
_ATTRIBUTE_SPLIT = re.compile(r"[ \t\r\n]+")
_FOREIGN_SEPARATORS = re.compile("[\x0b\x0c\x1c-\x1e\x85\u2028\u2029]")


class ProposalError(Exception):
    """The proposal document or an input is malformed or untrusted; the result is BLOCKED."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _show(value: object) -> str:
    return ascii(value)[:200]


def _fold(path: str) -> str:
    return unicodedata.normalize("NFKC", path).casefold()


# ---------------------------------------------------------------------------- validation
@dataclass(frozen=True)
class ValidProposal:
    file: str
    recipe: str
    detail: str
    diff: str
    changed: bool
    added: int
    deleted: int


@dataclass(frozen=True)
class ProposalSet:
    proposals: tuple[ValidProposal, ...]
    patched_paths: tuple[str, ...]      # files with at least one patch, sorted
    no_patch_paths: tuple[str, ...]     # files AEVE only flagged (no diff); the model may write these
    report_sha256: str
    partial: bool

    @property
    def patches(self) -> tuple[ValidProposal, ...]:
        return tuple(p for p in self.proposals if p.changed)


def parse_proposal_json(raw: object) -> dict:
    """Parse a proposal document from bytes: size cap, UTF-8, no duplicate keys, no NaN/Infinity."""
    if not isinstance(raw, bytes) or not raw:
        raise ProposalError("PROPOSAL_MALFORMED", "document must be non-empty bytes")
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ProposalError("PROPOSAL_TOO_LARGE", f"document exceeds {MAX_DOCUMENT_BYTES} bytes")
    if b"\x00" in raw:
        raise ProposalError("PROPOSAL_MALFORMED", "NUL byte in document")

    def pairs(items: list[tuple[str, Any]]) -> dict:
        keys = [k for k, _ in items]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate key")
        return dict(items)

    def constant(name: str) -> Any:
        raise ValueError(f"non-finite number {name}")

    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ProposalError("PROPOSAL_MALFORMED", f"not strict UTF-8 JSON ({type(exc).__name__})") from exc
    if not isinstance(doc, dict):
        raise ProposalError("PROPOSAL_MALFORMED", "document is not a JSON object")
    return doc


def _report_hash(doc: Mapping[str, Any]) -> str:
    # Same canonical form as AEVE patch.py:245-248. An integrity check, not authenticity: anyone can recompute it.
    body = {k: v for k, v in doc.items() if k != "report_sha256"}
    return hashlib.sha256(
        json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_file(path: object) -> str:
    if not isinstance(path, str) or not path or len(path) > MAX_FIELD_CHARS:
        raise ProposalError("PROPOSAL_MALFORMED", "file is not a non-empty string")
    hazards = wg.path_hazards(path)
    if hazards:
        raise ProposalError("PROPOSAL_PATH_NOT_CANONICAL", f"{_show(path)}: {','.join(hazards)}")
    if _GLOB_CHARS & set(path) or path.startswith("-"):
        raise ProposalError("PROPOSAL_PATH_NOT_CANONICAL", f"{_show(path)}: glob character or leading dash")
    return path


def _check_diff(file: str, diff: object) -> tuple[str, int, int, list[tuple[int, int, list[str]]]]:
    """Validate one AEVE per-file unified diff; return (text, added, deleted, hunks).

    Each hunk is ``(old_len, new_len, body)`` where body holds every line after the ``@@`` line,
    including the ``\\ No newline`` markers.
    """
    if not isinstance(diff, str) or not diff:
        raise ProposalError("PROPOSAL_MALFORMED", f"empty or non-string diff for {_show(file)}")
    try:
        encoded = diff.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ProposalError("PROPOSAL_MALFORMED", "diff is not valid Unicode text") from exc
    if len(encoded) > MAX_DIFF_BYTES_PER_PROPOSAL:
        raise ProposalError("PROPOSAL_TOO_LARGE", f"diff for {_show(file)} exceeds the per-proposal cap")
    if "\x00" in diff:
        raise ProposalError("PROPOSAL_MALFORMED", "NUL in diff")
    if _REDACTION_MARKER in diff:
        raise ProposalError("PROPOSAL_REDACTED", f"diff for {_show(file)} contains a redaction marker; it cannot match the file")
    lines = (diff[:-1] if diff.endswith("\n") else diff).split("\n")
    if len(lines) < 3 or lines[0] != f"--- {file}" or lines[1] != f"+++ {file}":
        raise ProposalError("PROPOSAL_MALFORMED", f"diff headers do not name {_show(file)}")
    index, added, deleted = 2, 0, 0
    hunks: list[tuple[int, int, list[str]]] = []
    while index < len(lines):
        match = _HUNK.fullmatch(lines[index])
        if not match:
            raise ProposalError("PROPOSAL_MALFORMED", "line outside any hunk")
        old_len = int(match.group(2)) if match.group(2) is not None else 1
        new_len = int(match.group(4)) if match.group(4) is not None else 1
        if old_len > MAX_HUNK_LINES or new_len > MAX_HUNK_LINES:
            raise ProposalError("PROPOSAL_TOO_LARGE", "hunk length exceeds the cap")
        index += 1
        old_seen = new_seen = 0
        body: list[str] = []
        while old_seen < old_len or new_seen < new_len or (index < len(lines) and lines[index] == _NO_NEWLINE and body):
            if index >= len(lines):
                raise ProposalError("PROPOSAL_MALFORMED", "hunk is shorter than its header says")
            line = lines[index]
            if line == _NO_NEWLINE:
                if not body:
                    raise ProposalError("PROPOSAL_MALFORMED", "no-newline marker before any hunk line")
                body.append(line)
                index += 1
                continue
            kind = line[:1]
            if kind == " ":
                old_seen += 1
                new_seen += 1
            elif kind == "-":
                old_seen += 1
                deleted += 1
            elif kind == "+":
                new_seen += 1
                added += 1
            else:
                raise ProposalError("PROPOSAL_MALFORMED", "hunk line is not context, removal or addition")
            if old_seen > old_len or new_seen > new_len:
                raise ProposalError("PROPOSAL_MALFORMED", "hunk is longer than its header says")
            body.append(line)
            index += 1
        hunks.append((old_len, new_len, body))
    if not hunks or added + deleted == 0:
        raise ProposalError("PROPOSAL_MALFORMED", f"diff for {_show(file)} changes nothing")
    return (diff[:-1] if diff.endswith("\n") else diff), added, deleted, hunks


def _sides(body: Sequence[str]) -> tuple[list[str], list[str]]:
    old: list[str] = []
    new: list[str] = []
    for line in body:
        if line == _NO_NEWLINE:
            continue
        if line[0] == " ":
            old.append(line[1:])
            new.append(line[1:])
        elif line[0] == "-":
            old.append(line[1:])
        else:
            new.append(line[1:])
    return old, new


def _check_recipe(file: str, recipe: str, hunks: Sequence[tuple[int, int, list[str]]]) -> None:
    """The recipe label must describe the diff (mirrors AEVE patch.py:57-115): anything else is RECIPE_MISMATCH."""

    def mismatch(why: str) -> ProposalError:
        return ProposalError("RECIPE_MISMATCH", f"{recipe} for {_show(file)}: {why}")

    if recipe == "trailing-whitespace":
        # patch.py:_strip_trailing_whitespace keeps the line count and strips " \t" from line ends only.
        changed = False
        for _, _, body in hunks:
            if _NO_NEWLINE in body:
                raise mismatch("end-of-file marker in a whitespace diff")
            old, new = _sides(body)
            if len(old) != len(new):
                raise mismatch("a hunk changes the line count")
            for before, after in zip(old, new):
                if after != before.rstrip(" \t"):
                    raise mismatch("a line changes by more than trailing spaces and tabs")
                changed = changed or after != before
        if not changed:
            raise mismatch("no trailing whitespace is removed")
        return
    if recipe == "final-newline":
        # patch.py:_normalize_final_newline: either only the last line's end-of-file newline changes
        # (the marker form of patch.py:_diff), or surplus empty lines at the end are removed.
        if len(hunks) != 1:
            raise mismatch("expected exactly one hunk")
        body = hunks[0][2]
        if (len(body) >= 3 and body[-2] == _NO_NEWLINE and body[-3][:1] == "-" and body[-1][:1] == "+"
                and body[-3][1:] == body[-1][1:] and all(line[:1] == " " for line in body[:-3])):
            return
        cut = next((i for i, line in enumerate(body) if line[:1] != " "), None)
        if cut is None or any(line != "-" for line in body[cut:]):
            raise mismatch("not an end-of-file newline change")
        return
    raise mismatch("recipe carries no patch")


def validate_proposal_document(doc: object) -> ProposalSet:
    """Strictly validate an AEVE ``g6.patch.v1`` document; raise ProposalError (BLOCKED) otherwise."""
    if not isinstance(doc, dict):
        raise ProposalError("PROPOSAL_MALFORMED", "document is not an object")
    unknown = set(doc) - _DOCUMENT_KEYS
    if unknown:
        raise ProposalError("PROPOSAL_MALFORMED", f"unknown document keys {_show(sorted(map(str, unknown)))}")
    if doc.get("schema_version") != PROPOSAL_SCHEMA:
        raise ProposalError("PROPOSAL_SCHEMA_UNSUPPORTED", _show(doc.get("schema_version")))
    if not _is_int(doc.get("llm_calls")) or doc["llm_calls"] != 0:
        raise ProposalError("PROPOSAL_MALFORMED", "llm_calls must be the integer 0")
    if doc.get("executed_project_code") is not False:
        raise ProposalError("PROPOSAL_MALFORMED", "executed_project_code must be false")
    raw_list = doc.get("proposals")
    if not isinstance(raw_list, list):
        raise ProposalError("PROPOSAL_MALFORMED", "proposals is not a list")
    if len(raw_list) > MAX_PROPOSALS:
        raise ProposalError("PROPOSAL_TOO_LARGE", f"more than {MAX_PROPOSALS} proposals")
    if not _is_int(doc.get("proposal_count")) or doc["proposal_count"] != len(raw_list):
        raise ProposalError("PROPOSAL_MALFORMED", "proposal_count differs from the proposals list")
    if "note" in doc and (not isinstance(doc["note"], str) or len(doc["note"]) > MAX_FIELD_CHARS):
        raise ProposalError("PROPOSAL_MALFORMED", "note is not a short string")
    partial = False
    if "status" in doc:
        if doc["status"] != "PARTIAL":
            raise ProposalError("PROPOSAL_MALFORMED", "status, when present, must be PARTIAL")
        partial = True
    if "uncovered" in doc:
        uncovered = doc["uncovered"]
        if not isinstance(uncovered, list) or len(uncovered) > 4096 \
                or any(not isinstance(i, str) or len(i) > MAX_FIELD_CHARS for i in uncovered):
            raise ProposalError("PROPOSAL_MALFORMED", "uncovered is not a bounded list of strings")
    digest = doc.get("report_sha256")
    if not (isinstance(digest, str) and _HEX64.fullmatch(digest)):
        raise ProposalError("PROPOSAL_MALFORMED", "report_sha256 is missing or not lowercase SHA-256")
    try:
        recomputed = _report_hash(doc)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ProposalError("PROPOSAL_MALFORMED", "document cannot be canonicalised") from exc
    if recomputed != digest:
        raise ProposalError("PROPOSAL_HASH_MISMATCH", "report_sha256 does not match the document content")

    proposals: list[ValidProposal] = []
    seen: set[tuple[str, str]] = set()
    finalised: set[str] = set()
    total = 0
    for item in raw_list:
        if not isinstance(item, dict) or set(item) != _PROPOSAL_KEYS:
            raise ProposalError("PROPOSAL_MALFORMED", "a proposal does not have exactly file, recipe, detail, diff, changed")
        file = _check_file(item["file"])
        recipe, detail, changed = item["recipe"], item["detail"], item["changed"]
        if not isinstance(recipe, str) or recipe not in PATCH_RECIPES + NOTE_RECIPES:
            raise ProposalError("PROPOSAL_RECIPE_UNKNOWN", _show(recipe))
        if not isinstance(detail, str) or len(detail) > MAX_FIELD_CHARS:
            raise ProposalError("PROPOSAL_MALFORMED", "detail is not a short string")
        if not isinstance(changed, bool):
            raise ProposalError("PROPOSAL_MALFORMED", "changed is not a boolean")
        key = (_fold(file), recipe)
        if changed and key in seen:  # note-only recipes may repeat (one unused-import entry per name)
            raise ProposalError("PROPOSAL_MALFORMED", f"duplicate recipe {recipe} for {_show(file)}")
        seen.add(key)
        if changed:
            if recipe not in PATCH_RECIPES:
                raise ProposalError("PROPOSAL_MALFORMED", f"recipe {recipe} cannot carry a patch")
            text, added, deleted, hunks = _check_diff(file, item["diff"])
            _check_recipe(file, recipe, hunks)
            # AEVE emits trailing-whitespace first; final-newline is computed on its output (patch.py:196-208).
            if recipe == "final-newline":
                finalised.add(_fold(file))
            elif _fold(file) in finalised:
                raise ProposalError("RECIPE_MISMATCH", f"trailing-whitespace for {_show(file)} follows final-newline")
            total += len(text.encode("utf-8"))
            if total > MAX_TOTAL_DIFF_BYTES:
                raise ProposalError("PROPOSAL_TOO_LARGE", "total diff size exceeds the cap")
            proposals.append(ValidProposal(file, recipe, detail, text, True, added, deleted))
        else:
            if item["diff"] != "":
                raise ProposalError("PROPOSAL_MALFORMED", "a proposal with changed=false carries a diff")
            proposals.append(ValidProposal(file, recipe, detail, "", False, 0, 0))
    patched = sorted({p.file for p in proposals if p.changed})
    patched_keys = {_fold(f) for f in patched}
    flagged = sorted({p.file for p in proposals if not p.changed and _fold(p.file) not in patched_keys})
    if len(patched) > wg.MAX_CHANGED_PATHS:
        raise ProposalError("PROPOSAL_TOO_LARGE", "more patched files than the changed-path cap")
    if len(patched_keys) != len(patched):
        raise ProposalError("PROPOSAL_MALFORMED", "two patched file names differ only by case")
    return ProposalSet(tuple(proposals), tuple(patched), tuple(flagged), digest, partial)


# ---------------------------------------------------------------------------- git plumbing
@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: bytes = b""
    stderr: bytes = b""
    timed_out: bool = False


GitRunner = Callable[..., GitResult]


def _inside(path: str, folder: str) -> bool:
    try:
        a = os.path.normcase(os.path.realpath(path))
        b = os.path.normcase(os.path.realpath(folder))
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


def find_git(exclude: str | None = None) -> str | None:
    """git from an absolute PATH entry only: never the current directory, never inside ``exclude``."""
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or not os.path.isabs(entry):
            continue
        for name in ("git.exe", "git"):
            candidate = os.path.join(entry, name)
            if os.path.isfile(candidate) and not (exclude is not None and _inside(candidate, exclude)):
                return candidate
    return None  # no bare "git" fallback: process creation could search the current directory first


def build_git_env(scratch: str, *, index_file: str | None = None, objects: str | None = None,
                  alternates: str | None = None) -> dict[str, str]:
    """Fixed minimal environment for every git call; nothing is inherited except SystemRoot."""
    git_path = find_git()
    env = {
        "PATH": os.path.dirname(git_path) if git_path else "",
        "HOME": scratch, "USERPROFILE": scratch, "TEMP": scratch, "TMP": scratch,
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": _NULL,
        "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C",
        "GIT_AUTHOR_NAME": "vst-u5-2", "GIT_AUTHOR_EMAIL": "vst-u5-2@invalid",
        "GIT_COMMITTER_NAME": "vst-u5-2", "GIT_COMMITTER_EMAIL": "vst-u5-2@invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
    }
    system_root = os.environ.get("SystemRoot")
    if system_root:
        env["SystemRoot"] = system_root
    if index_file is not None:
        env["GIT_INDEX_FILE"] = index_file
    if objects is not None:
        env["GIT_OBJECT_DIRECTORY"] = objects
    if alternates is not None:
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = alternates
    return env


def default_git_runner(args: Sequence[str], *, cwd: str, env: Mapping[str, str],
                       stdin: bytes | None = None, timeout: float = DEFAULT_GIT_TIMEOUT) -> GitResult:
    """Run git with shell=False, an absolute git path, an explicit environment, cwd and timeout; never raises on git errors."""
    exe = find_git(exclude=cwd)
    if exe is None:
        return GitResult(-1, b"", b"no trusted git executable on an absolute PATH entry")
    try:
        done = subprocess.run(
            [exe, *args], cwd=cwd, env=dict(env), input=stdin, capture_output=True, timeout=timeout,
            shell=False, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return GitResult(-1, b"", b"", True)
    except OSError as exc:
        return GitResult(-1, b"", type(exc).__name__.encode("ascii", "replace"))
    return GitResult(done.returncode, done.stdout, done.stderr[:8192])


class _GitFail(Exception):
    def __init__(self, code: str, detail: str, returncode: int | None = None, stderr: bytes = b"") -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.returncode = returncode
        self.stderr = stderr


def _git(runner: GitRunner, args: Sequence[str], *, cwd: str, env: Mapping[str, str],
         timeout: float, stdin: bytes | None = None, ok: Sequence[int] = (0,)) -> GitResult:
    result = runner([*GIT_PREFIX, *args], cwd=cwd, env=env, stdin=stdin, timeout=timeout)
    if not isinstance(result, GitResult):
        raise _GitFail("GIT_RUNNER_MALFORMED", "runner did not return a GitResult")
    if result.timed_out:
        raise _GitFail("GIT_TIMEOUT", f"git {args[0]} exceeded {timeout}s")
    if len(result.stdout) > MAX_GIT_OUTPUT:
        raise _GitFail("GIT_OUTPUT_TOO_LARGE", f"git {args[0]} output exceeds the cap")
    if b"dubious ownership" in result.stderr:
        raise _GitFail("GIT_UNSAFE_DIRECTORY", "git refuses the repository owner (safe.directory)", result.returncode)
    if result.returncode not in ok:
        raise _GitFail("GIT_FAILED", f"git {args[0]} exit {result.returncode}", result.returncode, result.stderr)
    return result


def _git_text(result: GitResult) -> str:
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise _GitFail("GIT_OUTPUT_MALFORMED", "git output is not UTF-8") from exc


def _git_object(result: GitResult) -> str:
    value = _git_text(result)
    if not _HEX40.fullmatch(value):
        raise _GitFail("GIT_OUTPUT_MALFORMED", f"expected a 40-hex object id, got {_show(value)}")
    return value


def git_patch_bytes(proposal: ValidProposal) -> bytes:
    """Turn one validated AEVE diff into canonical git diff text (adds `diff --git` and a/ b/ prefixes)."""
    body = proposal.diff.split("\n")[2:]
    return (f"diff --git a/{proposal.file} b/{proposal.file}\n--- a/{proposal.file}\n+++ b/{proposal.file}\n"
            + "\n".join(body) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------- results
@dataclass(frozen=True)
class ApplyResult:
    verdict: str
    reasons: tuple[tuple[str, str], ...]
    stage: str                                  # last stage reached, see PATCH_PROPOSALS.md
    worktree_state: str                         # UNCHANGED | MODIFIED | UNKNOWN
    candidate_head: str | None = None           # identifier of the candidate commit; its objects are not kept
    candidate_tree: str | None = None
    changed_paths: tuple[str, ...] = ()
    diff_bytes: bytes | None = None
    diff_sha256: str | None = None
    report_sha256: str | None = None
    hunks_by_file: dict | None = None           # APPLIED hunks: set only for ACCEPTED (verified write); input for change_origin_share
    attempted_hunks_by_file: dict | None = None  # hunks of the built diff once the gate accepted it; never counted as applied
    no_patch_paths: tuple[str, ...] = ()
    patched_paths: tuple[str, ...] = ()         # files the document proposes a patch for (validated)
    partial: bool = False                       # AEVE marked the document PARTIAL
    file_digests: dict | None = None            # path -> {"base_sha256", "candidate_sha256"}
    gate: WorkerGateVerdict | None = None
    isolation_stage: str = "pre_materialize"
    post_materialize_verified: bool | None = None  # None: the write was never reached

    def to_dict(self) -> dict:
        gate = self.gate.to_dict() if self.gate else None
        if gate and isinstance(gate.get("isolation_proof"), dict):
            gate["isolation_proof"] = dict(
                gate["isolation_proof"], isolation_stage="pre_materialize",
                worktree_head_note=("worktree_head was set to the candidate commit id (a placeholder) before the files "
                                    "were written; it is not the real HEAD of the worktree, which is unchanged"))
        return {
            "verdict": self.verdict, "stage": self.stage, "worktree_state": self.worktree_state,
            "reasons": [{"code": c, "detail": d} for c, d in self.reasons],
            "candidate_head": self.candidate_head, "candidate_tree": self.candidate_tree,
            "changed_paths": list(self.changed_paths), "diff_sha256": self.diff_sha256,
            "report_sha256": self.report_sha256, "hunks_by_file": self.hunks_by_file,
            "attempted_hunks_by_file": self.attempted_hunks_by_file,
            "no_patch_paths": list(self.no_patch_paths), "patched_paths": list(self.patched_paths),
            "partial": self.partial, "file_digests": self.file_digests,
            "isolation_stage": self.isolation_stage,
            "post_materialize_verified": self.post_materialize_verified, "gate": gate,
        }


def _result(verdict: str, reasons: Iterable[tuple[str, str]], stage: str, state: str = "UNCHANGED", **extra: Any) -> ApplyResult:
    return ApplyResult(verdict, tuple(reasons), stage, state, **extra)


# ---------------------------------------------------------------------------- repository trust and files
def _norm_root(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.realpath(path)))


def _read_small(path: str, cap: int) -> bytes | None:
    """Bytes of a regular file up to ``cap``; None when missing; ProposalError when unreadable or too large."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ProposalError("UNTRUSTED_GIT_CONFIG", f"cannot inspect {_show(os.path.basename(path))}: {type(exc).__name__}") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_size > cap:
        raise ProposalError("UNTRUSTED_GIT_CONFIG", f"{_show(os.path.basename(path))} is not a regular file within the size cap")
    try:
        with open(path, "rb") as handle:
            return handle.read(cap + 1)
    except OSError as exc:
        raise ProposalError("UNTRUSTED_GIT_CONFIG", f"cannot read {_show(os.path.basename(path))}: {type(exc).__name__}") from exc


def _resolve_git_dirs(root: str) -> tuple[str, str]:
    """git-dir and common-dir of the worktree, from the `.git` entry itself (a directory or a gitdir pointer file)."""
    dot = os.path.join(root, ".git")
    try:
        info = os.lstat(dot)
    except OSError as exc:
        raise ProposalError("UNTRUSTED_GIT_CONFIG", "the worktree has no readable .git entry") from exc
    if stat.S_ISDIR(info.st_mode):
        git_dir = dot
    elif stat.S_ISREG(info.st_mode):
        data = _read_small(dot, 4096)
        text = (data or b"").decode("utf-8", "replace").strip()
        if not text.startswith("gitdir:") or "\n" in text:
            raise ProposalError("UNTRUSTED_GIT_CONFIG", ".git file is not a single gitdir pointer")
        target = text[len("gitdir:"):].strip()
        git_dir = os.path.normpath(target if os.path.isabs(target) else os.path.join(root, target))
    else:
        raise ProposalError("UNTRUSTED_GIT_CONFIG", ".git is a link or special file")
    if not os.path.isdir(git_dir):
        raise ProposalError("UNTRUSTED_GIT_CONFIG", "git-dir does not exist")
    common = git_dir
    pointer = _read_small(os.path.join(git_dir, "commondir"), 4096)
    if pointer is not None:
        rel = pointer.decode("utf-8", "replace").strip()
        common = os.path.normpath(rel if os.path.isabs(rel) else os.path.join(git_dir, rel))
    if not os.path.isdir(common):
        raise ProposalError("UNTRUSTED_GIT_CONFIG", "common git dir does not exist")
    if _norm_root(git_dir) != _norm_root(common) and not _inside(git_dir, os.path.join(common, "worktrees")):
        raise ProposalError("UNTRUSTED_GIT_CONFIG", "the worktree git-dir is not under the expected repository")
    return git_dir, common


def _scan_git_config(git_dir: str, common_dir: str) -> None:
    """Refuse repository or worktree config that can run a program or change content (read directly, no git)."""
    seen: set[str] = set()
    for folder in (common_dir, git_dir):
        for name in ("config", "config.worktree"):
            path = os.path.join(folder, name)
            if _norm_root(path) in seen:
                continue
            seen.add(_norm_root(path))
            data = _read_small(path, MAX_CONFIG_BYTES)
            if data is None:
                continue
            text = data.decode("utf-8", "replace")
            for label, pattern in _CONFIG_HAZARDS:
                if pattern.search(text):
                    raise ProposalError("UNTRUSTED_GIT_CONFIG", f"{name} in the repository holds {label}")
    for folder in (common_dir, git_dir):
        data = _read_small(os.path.join(folder, "info", "attributes"), MAX_CONFIG_BYTES)
        if data is not None:
            _scan_attribute_text(data, "info/attributes")


def _attribute_tokens(line: str) -> list[str] | None:
    """The attribute tokens of one .gitattributes line (the pattern is dropped); None when the line is malformed."""
    if line.startswith('"'):
        # git falls back to an unquoted pattern on a bad escape, so any escape is refused instead of parsed.
        end = line.find('"', 1)
        if end < 0 or "\\" in line:
            return None
        rest = line[end + 1:]
    else:
        parts = _ATTRIBUTE_SPLIT.split(line, 1)
        rest = parts[1] if len(parts) > 1 else ""
    return [token for token in _ATTRIBUTE_SPLIT.split(rest) if token]


def _scan_attribute_text(data: bytes, label: str) -> None:
    """Refuse an attribute that can run code or rewrite content; text, eol and their off or auto forms pass."""
    text = data.decode("utf-8", "replace").lstrip("\ufeff")
    if _FOREIGN_SEPARATORS.search(text):
        raise ProposalError("UNTRUSTED_GIT_CONFIG", f"{label} holds a separator character that git and this scan could read differently")
    for line in text.split("\n"):
        stripped = line.strip(_ATTRIBUTE_WHITESPACE)
        if not stripped or stripped.startswith("#"):
            continue
        tokens = _attribute_tokens(stripped)
        if tokens is None:
            raise ProposalError("UNTRUSTED_GIT_CONFIG", f"{label} has a line with an unterminated or escaped quoted pattern")
        for token in tokens:
            if token in _ALLOWED_EOL_TOKENS:
                continue
            name, has_value, _ = token.lstrip("-!").partition("=")
            name = name.lower()
            if name in ("text", "eol"):
                raise ProposalError("UNTRUSTED_GIT_CONFIG", f"{label} sets {name} in a form other than text, -text, text=auto, eol=lf or eol=crlf")
            if name in _BLOCKED_ATTRIBUTES or (name in _DRIVER_ATTRIBUTES and has_value):
                raise ProposalError("UNTRUSTED_GIT_CONFIG", f"{label} sets the {name} attribute, which can run a program or rewrite content")


def _scan_attributes(root: str, paths: Iterable[str]) -> None:
    """Every .gitattributes from the worktree root down to each touched file's directory must be free of attributes that run code or rewrite content (text and eol are allowed)."""
    folders = {""}
    for path in paths:
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            folders.add("/".join(parts[:i]))
    for folder in sorted(folders):
        target = os.path.join(root, *(folder.split("/") if folder else []), ".gitattributes")
        data = _read_small(target, MAX_CONFIG_BYTES)
        if data is not None:
            _scan_attribute_text(data, f"{folder + '/' if folder else ''}.gitattributes")


def _read_worktree_file(root: str, rel: str) -> bytes:
    path = os.path.join(root, *rel.split("/"))
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
            raise ProposalError("DIRTY_WORKTREE", f"{_show(rel)} is not a regular file within the size cap")
        with open(path, "rb") as handle:
            return handle.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise ProposalError("DIRTY_WORKTREE", f"{_show(rel)} cannot be read: {type(exc).__name__}") from exc


def _check_clean(root: str, paths: Iterable[str], base_blobs: Mapping[str, bytes]) -> None:
    """Every touched worktree file must equal its base blob byte for byte."""
    for rel in paths:
        if _read_worktree_file(root, rel) != base_blobs[rel]:
            raise ProposalError("DIRTY_WORKTREE", f"{_show(rel)} differs from the base content")


def _check_representable(rel: str, blob: bytes) -> None:
    """AEVE built its diffs from str.splitlines() of a BOM-stripped decode; other sources cannot match them."""
    if blob.startswith(_BOM):
        raise ProposalError("PATCH_NOT_REPRESENTABLE", f"{_show(rel)} starts with a UTF-8 BOM")
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProposalError("PATCH_NOT_REPRESENTABLE", f"{_show(rel)} is not UTF-8") from exc
    if _SPLITLINES_ONLY & set(text):
        raise ProposalError("PATCH_NOT_REPRESENTABLE", f"{_show(rel)} holds a carriage return or a splitlines-only separator")


def _atomic_write(root: str, rel: str, data: bytes) -> None:
    """Temp file in the same directory, flush, fsync, os.replace (retried: Windows may refuse briefly)."""
    target = os.path.join(root, *rel.split("/"))
    temp = f"{target}.vst-{os.getpid()}.tmp"
    try:
        with open(temp, "xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            shutil.copymode(target, temp)
        except OSError:
            pass
        for attempt in range(6):
            try:
                os.replace(temp, target)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.05)
    finally:
        try:
            os.unlink(temp)
        except OSError:
            pass


def _acquire_lock(git_dir: str) -> int:
    path = os.path.join(git_dir, LOCK_NAME)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ProposalError("WORKTREE_LOCKED", "another apply holds the worktree lock (or a crashed one left it)") from exc
    except OSError as exc:
        raise ProposalError("WORKTREE_LOCKED", f"lock cannot be created: {type(exc).__name__}") from exc
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
    except OSError:
        pass
    return fd


def _release_lock(git_dir: str, fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.unlink(os.path.join(git_dir, LOCK_NAME))
    except OSError:
        pass


def _rollback_files(root: str, attempted: Sequence[str], base_blobs: Mapping[str, bytes], cand_blobs: Mapping[str, bytes]) -> list[str]:
    """Compare-and-restore: a path goes back to the base bytes only if it still holds the candidate bytes."""
    conflicts: list[str] = []
    for rel in attempted:
        try:
            current = _read_worktree_file(root, rel)
            if current == base_blobs[rel]:
                continue
            if current == cand_blobs[rel]:
                _atomic_write(root, rel, base_blobs[rel])
            else:
                conflicts.append(rel)
        except Exception:
            conflicts.append(rel)
    return conflicts


# ---------------------------------------------------------------------------- applying
def apply_proposals(
    *, document: object, manifest_sha256: object, base_head: object, proposal_base_head: object,
    allowed_paths: object, protected_paths: object, isolation: object,
    git_runner: GitRunner = default_git_runner, timeout: float = DEFAULT_GIT_TIMEOUT,
) -> ApplyResult:
    """Apply the patches of one AEVE proposal document in the isolated worktree; never raises (except KeyboardInterrupt).

    ``document`` is the parsed ``g6.patch.v1`` object or its raw bytes. ``proposal_base_head`` is the
    head AEVE analysed when it produced the document (caller-reported, for example the ``head`` of
    the AEVE review response of the same run); ``base_head`` is the pinned base of the worktree.
    The call holds an exclusive per-worktree lock (a file in the git-dir). The worktree is written
    only after the gate accepted the change (stage ``MATERIALIZE``), with a journal, and a failure
    there is rolled back by compare-and-restore.
    """
    scratch: str | None = None
    lock: tuple[str, int] | None = None
    stage = "VALIDATE"
    try:
        if isinstance(document, bytes):
            document = parse_proposal_json(document)
        pset = validate_proposal_document(document)
        common = {"report_sha256": pset.report_sha256, "no_patch_paths": pset.no_patch_paths,
                  "patched_paths": pset.patched_paths, "partial": pset.partial}
        patches = pset.patches
        if not patches:
            return _result(BLOCKED, [("NO_PATCH_IN_PROPOSAL", "the document holds no patch; the model may write these paths")],
                           "VALIDATE", **common)
        for name, value in (("base_head", base_head), ("proposal_base_head", proposal_base_head)):
            if not (isinstance(value, str) and _HEX40.fullmatch(value)):
                raise ProposalError("MALFORMED_INPUT", f"{name} must be a lowercase 40-hex commit id")
        if not isinstance(isolation, IsolationContext):
            raise ProposalError("MALFORMED_INPUT", "isolation context is missing")
        if proposal_base_head != base_head:
            return _result(REFUSED, [("STALE_BASE", "the proposal was made for another head than the worktree base")],
                           "BASE_HEAD", **common)

        # Stage PRESCREEN: scope, protected paths and path hazards on the claimed diff, before any git call.
        stage = "PRESCREEN"
        claimed = b"".join(git_patch_bytes(p) for p in patches)
        synthetic = hashlib.sha1(f"{base_head}:{pset.report_sha256}:prescreen".encode("ascii")).hexdigest()
        screen = wg.gate_worker_change(
            manifest_sha256=manifest_sha256, base_head=base_head, candidate_head=synthetic,
            changed_paths=list(pset.patched_paths), allowed_paths=allowed_paths, protected_paths=protected_paths,
            diff_bytes=claimed, isolation=dataclasses.replace(isolation, worktree_head=synthetic))
        if screen.verdict != ACCEPTED:
            return _result(screen.verdict, screen.reasons, "PRESCREEN", gate=screen, **common)

        # Stage WORKTREE_CHECK: trusted repository, lock, base head, byte-identical clean files.
        stage = "WORKTREE_CHECK"
        root = isolation.worktree_root
        if not (isinstance(root, str) and os.path.isdir(root)):
            raise ProposalError("MALFORMED_INPUT", "worktree_root is not an existing directory")
        scratch = tempfile.mkdtemp(prefix="vst-u5-2-")
        if _inside(scratch, root):
            raise ProposalError("MALFORMED_INPUT", "scratch directory would be inside the worktree")
        git_dir, common_dir = _resolve_git_dirs(root)
        lock = (git_dir, _acquire_lock(git_dir))
        if os.path.lexists(os.path.join(git_dir, JOURNAL_NAME)):
            raise ProposalError("JOURNAL_PRESENT", "an earlier apply left a journal; discard or inspect the worktree")
        _scan_git_config(git_dir, common_dir)
        _scan_attributes(root, pset.patched_paths)
        objects = os.path.join(scratch, "objects")
        os.mkdir(objects)
        env = build_git_env(scratch, objects=objects, alternates=os.path.join(common_dir, "objects"))
        index_env = dict(env, GIT_INDEX_FILE=os.path.join(scratch, "vst-throwaway-index"))

        def git(args: Sequence[str], *, use_index: bool = False, stdin: bytes | None = None,
                ok: Sequence[int] = (0,)) -> GitResult:
            return _git(git_runner, args, cwd=root, env=index_env if use_index else env, timeout=timeout, stdin=stdin, ok=ok)

        top = _git_text(git(["rev-parse", "--show-toplevel"]))
        if _norm_root(top) != _norm_root(root):
            return _result(BLOCKED, [("WORKTREE_ROOT_MISMATCH", "git top level differs from the isolation worktree root")], stage, **common)
        reported = _git_text(git(["rev-parse", "--git-dir", "--git-common-dir"])).splitlines()
        expected = (git_dir, common_dir)
        if len(reported) != 2 or any(
                _norm_root(r if os.path.isabs(r) else os.path.join(root, r)) != _norm_root(e) for r, e in zip(reported, expected)):
            raise ProposalError("UNTRUSTED_GIT_CONFIG", "git reports other git directories than the .git entry names")
        head = _git_object(git(["rev-parse", "--verify", "--quiet", "HEAD^{commit}"]))
        if head != base_head:
            return _result(REFUSED, [("STALE_BASE", "worktree HEAD differs from the pinned base head")], stage, **common)
        paths = list(pset.patched_paths)
        if git(["status", "--porcelain=v1", "-z", "--untracked-files=no", "--", *paths]).stdout:
            raise ProposalError("DIRTY_WORKTREE", "a path to patch already has uncommitted changes")
        flags = git(["ls-files", "-v", "-z", "--", *paths]).stdout.decode("utf-8", "replace").split("\0")
        tagged = {entry[2:]: entry[:1] for entry in flags if len(entry) > 2 and entry[1] == " "}
        if set(tagged) != set(paths) or any(tag != "H" for tag in tagged.values()):
            raise ProposalError("DIRTY_WORKTREE", "a path is untracked, assume-unchanged or skip-worktree")
        base_blobs = {rel: git(["cat-file", "blob", f"{base_head}:{rel}"]).stdout for rel in paths}
        _check_clean(root, paths, base_blobs)
        for rel in paths:
            _check_representable(rel, base_blobs[rel])
        base_tree = _git_object(git(["rev-parse", "--verify", "--quiet", f"{base_head}^{{tree}}"]))

        # Stage BUILD: apply every patch, in document order, to a throw-away index and object directory.
        stage = "BUILD"
        git(["read-tree", base_head], use_index=True)
        for proposal in patches:
            patch = git_patch_bytes(proposal)
            apply_args = ["apply", "--cached", "--whitespace=nowarn", f"--include={proposal.file}", "-"]
            checked = git([apply_args[0], "--check", *apply_args[1:]], use_index=True, stdin=patch, ok=tuple(range(256)))
            if checked.returncode != 0:
                text = checked.stderr.decode("utf-8", "replace")
                if checked.returncode == 1 and _STALE_TEXT.search(text):
                    return _result(REFUSED, [("STALE_BASE", f"patch for {_show(proposal.file)} ({proposal.recipe}) does not apply to the base content")],
                                   stage, **common)
                return _result(BLOCKED, [("PATCH_DOES_NOT_APPLY", f"{_show(proposal.file)}: git exit {checked.returncode}: {ascii(text[-200:])}")],
                               stage, **common)
            git(apply_args, use_index=True, stdin=patch)
        tree = _git_object(git(["write-tree"], use_index=True))
        if tree == base_tree:
            return _result(BLOCKED, [("NO_EFFECT", "the patches leave the base tree unchanged")], stage, **common)
        candidate = _git_object(git(["commit-tree", tree, "-p", base_head, "-m", f"VST U5-2 candidate {pset.report_sha256}"]))
        if candidate == base_head:
            return _result(BLOCKED, [("NO_EFFECT", "candidate equals base")], stage, **common)
        diff = git(["diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames",
                    "--src-prefix=a/", "--dst-prefix=b/", base_head, candidate]).stdout
        names = git(["diff", "--name-only", "-z", "--no-renames", base_head, candidate]).stdout
        changed = sorted(n for n in names.decode("utf-8").split("\0") if n)
        if not diff or not changed:
            return _result(BLOCKED, [("NO_EFFECT", "empty resulting diff")], stage, **common)
        if set(changed) != set(pset.patched_paths):
            return _result(REFUSED, [("DIFF_PATH_MISMATCH", "resulting changed paths differ from the proposed files")], stage, **common)
        cand_blobs = {rel: git(["cat-file", "blob", f"{candidate}:{rel}"]).stdout for rel in changed}
        facts = {**common, "candidate_head": candidate, "candidate_tree": tree, "changed_paths": tuple(changed),
                 "diff_bytes": diff, "diff_sha256": hashlib.sha256(diff).hexdigest(),
                 "file_digests": {rel: {"base_sha256": hashlib.sha256(base_blobs[rel]).hexdigest(),
                                        "candidate_sha256": hashlib.sha256(cand_blobs[rel]).hexdigest()} for rel in changed}}

        # Stage GATE: the real resulting diff goes through worker_gate (diff gate, scope, protected paths, isolation proof).
        # isolation.worktree_head is set to the candidate id: a placeholder, the real HEAD is unchanged (see to_dict).
        stage = "GATE"
        gate_args = dict(
            manifest_sha256=manifest_sha256, base_head=base_head, candidate_head=candidate,
            changed_paths=changed, allowed_paths=allowed_paths, protected_paths=protected_paths,
            diff_bytes=diff, isolation=dataclasses.replace(isolation, worktree_head=candidate))
        verdict = wg.gate_worker_change(**gate_args)
        if verdict.verdict != ACCEPTED:
            return _result(verdict.verdict, verdict.reasons, stage, gate=verdict, **facts)
        facts["attempted_hunks_by_file"] = hunk_counts_from_diff(diff)  # attempted, not applied, until the verified write

        # Stage MATERIALIZE: the only stage that writes the worktree. Re-check, journal, write, verify, roll back on failure.
        stage = "MATERIALIZE"
        try:
            _check_clean(root, changed, base_blobs)
            again = wg.gate_worker_change(**gate_args)  # link and scope checks repeated right before the write
        except ProposalError as exc:
            return _result(BLOCKED, [(exc.code, exc.detail)], stage, gate=verdict, **facts)
        if again.verdict != ACCEPTED:
            return _result(again.verdict, again.reasons, stage, gate=again, **facts)
        journal = os.path.join(git_dir, JOURNAL_NAME)
        entry = {"report_sha256": pset.report_sha256, "candidate_head": candidate,
                 "paths": [{"path": rel, **facts["file_digests"][rel]} for rel in changed]}
        try:
            fd = os.open(journal, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "wb") as handle:
                handle.write(json.dumps(entry, sort_keys=True).encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            return _result(BLOCKED, [("JOURNAL_UNAVAILABLE", type(exc).__name__)], stage, gate=verdict, **facts)
        attempted: list[str] = []
        try:
            for rel in changed:
                attempted.append(rel)
                _atomic_write(root, rel, cand_blobs[rel])
            for rel in changed:
                if _read_worktree_file(root, rel) != cand_blobs[rel]:
                    raise ProposalError("MATERIALIZE_VERIFY_FAILED", f"{_show(rel)} differs from the candidate after writing")
        except BaseException as exc:
            conflicts = _rollback_files(root, attempted, base_blobs, cand_blobs)
            reasons = [(getattr(exc, "code", "MATERIALIZE_FAILED"), str(getattr(exc, "detail", type(exc).__name__)))]
            if conflicts:
                reasons += [("ROLLBACK_CONFLICT", _show(rel)) for rel in conflicts]  # journal stays: the next call is blocked
                outcome = _result(BLOCKED, reasons, stage, "UNKNOWN", gate=verdict, post_materialize_verified=False, **facts)
            else:
                reasons.append(("ROLLED_BACK", "touched files were restored to the base bytes"))
                try:
                    os.unlink(journal)
                except OSError:
                    pass
                outcome = _result(BLOCKED, reasons, stage, "UNCHANGED", gate=verdict, post_materialize_verified=False, **facts)
            if not isinstance(exc, Exception):
                raise
            return outcome
        try:
            os.unlink(journal)
        except OSError:
            pass
        return _result(ACCEPTED, verdict.reasons, stage, "MODIFIED", gate=verdict, post_materialize_verified=True,
                       hunks_by_file=facts["attempted_hunks_by_file"], **facts)
    except ProposalError as exc:
        return _result(BLOCKED, [(exc.code, exc.detail)], stage)
    except _GitFail as exc:
        return _result(BLOCKED, [(exc.code, exc.detail)], stage)
    except Exception as exc:  # fail closed on anything unexpected
        return _result(BLOCKED, [("INTERNAL_ERROR", type(exc).__name__)], "INTERNAL")
    finally:
        if lock is not None:
            _release_lock(*lock)
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)


# ---------------------------------------------------------------------------- origin share
def hunk_counts_from_diff(diff_bytes: bytes) -> dict[str, list[tuple[int, int]]]:
    """Per file, one ``(added, deleted)`` pair per hunk of a git diff; validated by worker_gate first."""
    try:
        parsed = wg.parse_diff_paths(diff_bytes)
    except Exception as exc:
        raise ProposalError("DIFF_UNPARSABLE", str(exc)[:200]) from exc
    if parsed["renames"]:
        raise ProposalError("DIFF_UNPARSABLE", "renames carry no per-hunk origin")
    result: dict[str, list[tuple[int, int]]] = {}
    current: str | None = None
    old_rem = new_rem = added = deleted = 0
    for line in diff_bytes.decode("utf-8").split("\n"):
        if old_rem > 0 or new_rem > 0:
            kind = line[:1]
            if kind == " ":
                old_rem -= 1
                new_rem -= 1
            elif kind == "-":
                old_rem -= 1
                deleted += 1
            elif kind == "+":
                new_rem -= 1
                added += 1
            if old_rem == 0 and new_rem == 0 and current is not None:
                result[current].append((added, deleted))
            continue
        if line.startswith("diff --git a/"):
            rest = line[len("diff --git a/"):]
            half = (len(rest) - len(" b/")) // 2
            current = rest[:half]
            if rest != f"{current} b/{current}":
                raise ProposalError("DIFF_UNPARSABLE", "diff header is not a same-path pair")
            result.setdefault(current, [])
            continue
        match = _HUNK.fullmatch(line.split(" @@", 1)[0] + " @@") if line.startswith("@@ ") else None
        if match and current is not None:
            old_rem = int(match.group(2)) if match.group(2) is not None else 1
            new_rem = int(match.group(4)) if match.group(4) is not None else 1
            added = deleted = 0
            if old_rem == 0 and new_rem == 0:
                result[current].append((0, 0))
    return result


def _clean_hunks(name: str, mapping: object) -> dict[str, list[tuple[int, int]]]:
    if not isinstance(mapping, Mapping):
        raise ValueError(f"{name} must be a mapping path -> hunks")
    clean: dict[str, list[tuple[int, int]]] = {}
    for path, hunks in mapping.items():
        if not isinstance(path, str) or not path:
            raise ValueError(f"{name} has a non-string or empty path")
        if isinstance(hunks, (str, bytes)) or not isinstance(hunks, (list, tuple)):
            raise ValueError(f"{name}[{path!r}] must be a list of (added, deleted) pairs")
        rows = []
        for hunk in hunks:
            if not (isinstance(hunk, (list, tuple)) and len(hunk) == 2 and all(_is_int(v) and v >= 0 for v in hunk)):
                raise ValueError(f"{name}[{path!r}] has an entry that is not a pair of non-negative integers")
            rows.append((hunk[0], hunk[1]))
        clean[path] = rows
    return clean


def change_origin_share(proposal_lines_by_file: object, model_lines_by_file: object) -> dict:
    """Count added plus deleted lines per origin and their fractions of the whole change.

    Each input maps a repo-relative path to a list of hunks, each hunk an ``(added, deleted)``
    pair (see ``hunk_counts_from_diff``). Rule: attribution is by hunk. A hunk belongs to exactly
    one origin, so a file touched by both origins contributes its proposal hunks to the proposal
    and its model hunks to the model; no hunk is counted twice. Hunks must be disjoint (the
    caller passes the proposal hunks of the proposal diff and the model hunks of the model diff).
    Paths are matched case-insensitively (NFKC, casefold) because the target is Windows.
    ``model_only_paths`` are model paths with no proposal; ``files_touched_by_both`` lists
    the shared ones. Fractions are ``None`` when the change is empty. Raises ValueError on bad input.
    """
    proposal = _clean_hunks("proposal_lines_by_file", proposal_lines_by_file)
    model = _clean_hunks("model_lines_by_file", model_lines_by_file)

    def totals(side: dict[str, list[tuple[int, int]]]) -> dict:
        added = sum(a for rows in side.values() for a, _ in rows)
        deleted = sum(d for rows in side.values() for _, d in rows)
        return {"added": added, "deleted": deleted, "lines": added + deleted,
                "hunks": sum(len(rows) for rows in side.values()), "files": sorted(side)}

    p_keys = {_fold(p) for p in proposal}
    m_keys = {_fold(p) for p in model}
    p_total, m_total = totals(proposal), totals(model)
    total = p_total["lines"] + m_total["lines"]
    return {
        "schema": SHARE_SCHEMA,
        "rule": "attribution by hunk; a hunk belongs to exactly one origin; paths matched case-insensitively",
        "proposal": p_total,
        "model": m_total,
        "total_lines": total,
        "proposal_fraction": (p_total["lines"] / total) if total else None,
        "model_fraction": (m_total["lines"] / total) if total else None,
        "files_touched_by_both": sorted(p for p in proposal if _fold(p) in m_keys),
        "proposal_only_paths": sorted(p for p in proposal if _fold(p) not in m_keys),
        "model_only_paths": sorted(p for p in model if _fold(p) not in p_keys),
    }


def build_run_record(apply_result: object, model_hunks_by_file: object, overrides: Iterable[Mapping[str, Any]] | None = None) -> dict:
    """JSON-able per-run record: proposal versus model line counts and fractions, shared files, overrides.

    ``overrides`` is ``ModelChangeVerdict.overrides``. Raises ValueError on bad input. A run whose
    proposal was refused or blocked has no applied hunks: its proposal side is zero and the verdict says why.
    Proposal lines count only when the verdict is ACCEPTED and ``post_materialize_verified`` is True. What was
    built and gate-accepted but not (verifiably) written is listed under ``attempted_proposal_hunks`` and
    ``attempted_proposal_lines``; those never enter the fractions.
    """
    if not isinstance(apply_result, ApplyResult):
        raise ValueError("apply_result must be an ApplyResult")
    applied = apply_result.verdict == ACCEPTED and apply_result.post_materialize_verified is True
    share = change_origin_share(apply_result.hunks_by_file if applied and apply_result.hunks_by_file else {}, model_hunks_by_file)
    attempted = _clean_hunks("attempted_hunks_by_file", apply_result.attempted_hunks_by_file or {})
    recorded = [dict(item) for item in (overrides or [])]
    return {
        "schema": RUN_RECORD_SCHEMA,
        "verdict": apply_result.verdict, "stage": apply_result.stage,
        "worktree_state": apply_result.worktree_state,
        "report_sha256": apply_result.report_sha256, "candidate_head": apply_result.candidate_head,
        "diff_sha256": apply_result.diff_sha256, "partial": apply_result.partial,
        "post_materialize_verified": apply_result.post_materialize_verified,
        "patched_paths": list(apply_result.patched_paths), "no_patch_paths": list(apply_result.no_patch_paths),
        "applied": applied,
        "attempted_proposal_hunks": {path: [list(h) for h in rows] for path, rows in attempted.items()},
        "attempted_proposal_lines": sum(a + d for rows in attempted.values() for a, d in rows),
        "proposal_lines": share["proposal"]["lines"], "model_lines": share["model"]["lines"],
        "total_lines": share["total_lines"],
        "proposal_fraction": share["proposal_fraction"], "model_fraction": share["model_fraction"],
        "files_touched_by_both": share["files_touched_by_both"], "model_only_paths": share["model_only_paths"],
        "overrides": recorded,
    }


# ---------------------------------------------------------------------------- model must not override proposals
@dataclass(frozen=True)
class ModelChangeVerdict:
    verdict: str
    reasons: tuple[tuple[str, str], ...]
    overrides: tuple[dict, ...]        # recorded explicit overrides: {"path", "reason", "authorized_by"}
    model_only_paths: tuple[str, ...]  # model paths with no proposed patch

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "reasons": [{"code": c, "detail": d} for c, d in self.reasons],
                "overrides": [dict(o) for o in self.overrides], "model_only_paths": list(self.model_only_paths)}


def _text_problem(value: object, low: int, high: int, what: str) -> str | None:
    if not isinstance(value, str):
        return f"{what} is not a string"
    text = value.strip()
    if not low <= len(text) <= high:
        return f"{what} must have {low} to {high} characters after trimming"
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in text):
        return f"{what} contains control, format or line-separator characters"
    return None


def check_model_changes(
    *, model_changed_paths: object, apply_result: object = None, proposal_patched_paths: object = None,
    override_reasons: object = None, authorized_by: object = None,
) -> ModelChangeVerdict:
    """The model may write only paths AEVE proposed no patch for; never raises.

    The patched paths come from ``apply_result.patched_paths`` (the validated document of this run);
    ``proposal_patched_paths`` is an unbound alternative and exactly one of the two must be given.
    A model change on a patched path is REFUSED (MODEL_OVERRIDES_PROPOSAL) unless
    ``override_reasons`` maps that exact model path to a stated reason AND ``authorized_by`` names the
    operator who authorised it; then it is ACCEPTED with the override recorded (MODEL_OVERRIDE_RECORDED
    and ``overrides``). Without ``authorized_by`` the path stays refused (OVERRIDE_AUTHORIZATION_MISSING).
    At most MAX_OVERRIDES overrides; an override for a path not in conflict is BLOCKED
    (OVERRIDE_WITHOUT_CONFLICT). Scope of the model change is the business of worker_gate.
    """
    try:
        if (apply_result is None) == (proposal_patched_paths is None):
            raise ProposalError("MALFORMED_INPUT", "give exactly one of apply_result and proposal_patched_paths")
        if apply_result is not None:
            if not isinstance(apply_result, ApplyResult) or apply_result.report_sha256 is None:
                raise ProposalError("MALFORMED_INPUT", "apply_result carries no validated proposal")
            patched = _paths("apply_result.patched_paths", list(apply_result.patched_paths))
        else:
            patched = _paths("proposal_patched_paths", proposal_patched_paths)
        model = _paths("model_changed_paths", model_changed_paths)
        if override_reasons is None:
            override_reasons = {}
        if not isinstance(override_reasons, Mapping) or any(not isinstance(k, str) for k in override_reasons):
            raise ProposalError("MALFORMED_INPUT", "override_reasons must map model paths to reason strings")
        if len(override_reasons) > MAX_OVERRIDES:
            raise ProposalError("OVERRIDE_CAP_EXCEEDED", f"more than {MAX_OVERRIDES} overrides")
        patched_keys = {_fold(p) for p in patched}
        conflicts = sorted({m for m in model if _fold(m) in patched_keys})
        author_problem = _text_problem(authorized_by, 1, MAX_AUTHORIZED_BY, "authorized_by")
        refuse: list[tuple[str, str]] = []
        block: list[tuple[str, str]] = []
        recorded: list[dict] = []
        for path in conflicts:
            if path not in override_reasons:
                refuse.append(("MODEL_OVERRIDES_PROPOSAL", _show(path)))
                continue
            if author_problem:
                refuse.append(("OVERRIDE_AUTHORIZATION_MISSING", f"{_show(path)}: {author_problem}"))
                continue
            problem = _text_problem(override_reasons[path], MIN_OVERRIDE_REASON, MAX_OVERRIDE_REASON, "reason")
            if problem:
                refuse.append(("OVERRIDE_REASON_INVALID", f"{_show(path)}: {problem}"))
                continue
            recorded.append({"path": path, "reason": override_reasons[path].strip(), "authorized_by": authorized_by.strip()})
        for path in sorted(set(override_reasons) - set(conflicts)):
            block.append(("OVERRIDE_WITHOUT_CONFLICT", _show(path)))
        model_only = tuple(sorted(m for m in model if _fold(m) not in patched_keys))
        if refuse:
            return ModelChangeVerdict(REFUSED, tuple(refuse + block), tuple(recorded), model_only)
        if block:
            return ModelChangeVerdict(BLOCKED, tuple(block), tuple(recorded), model_only)
        reasons = [("MODEL_OVERRIDE_RECORDED", _show(o["path"])) for o in recorded] or [("NO_CONFLICT", "model paths avoid every proposed patch")]
        return ModelChangeVerdict(ACCEPTED, tuple(reasons), tuple(recorded), model_only)
    except ProposalError as exc:
        return ModelChangeVerdict(BLOCKED, ((exc.code, exc.detail),), (), ())
    except Exception as exc:
        return ModelChangeVerdict(BLOCKED, (("INTERNAL_ERROR", type(exc).__name__),), (), ())


def _paths(name: str, value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple, set, frozenset)):
        raise ProposalError("MALFORMED_INPUT", f"{name} must be a list of strings")
    items = list(value)
    for item in items:
        if not isinstance(item, str):
            raise ProposalError("MALFORMED_INPUT", f"{name} holds a non-string")
        if wg.path_hazards(item):
            raise ProposalError("MALFORMED_INPUT", f"{name} holds a hazardous path {_show(item)}")
    return items
