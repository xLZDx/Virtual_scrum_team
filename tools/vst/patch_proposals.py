"""U5-2: apply AEVE patch proposals through the deterministic diff gate (Windows-local).

Operator decision OD-8 (2026-11-08): AEVE's repair lab proposes bounded patches and never applies
one; VST applies them in the isolated worktree and the diff gate checks them; the model writes code
only for what AEVE proposed no patch for. Everything here fails closed. Verdicts as in U5-1:

* ACCEPTED - the proposal was valid, the base matched, the patch applied, the resulting diff
  passed ``worker_gate.gate_worker_change`` and the worktree now holds exactly that change.
* REFUSED  - a definite policy violation: stale base, out-of-scope or protected path, path trick,
  a gate refusal, or a model change on a path AEVE proposed a patch for.
* BLOCKED  - the decision cannot be made: malformed or oversized proposal, git failure, dirty
  worktree, timeout, unexpected exception. BLOCKED is never an acceptance.

The real AEVE proposal format (``g6.patch.v1``, AEVE origin/main src/aeve/repair/patch.py) carries
no base identity and no machine-readable bounds: each proposal is ``{file, recipe, detail, diff,
changed}`` with a per-file unified diff that has ``--- file`` / ``+++ file`` headers (no ``a/``,
``b/`` prefix, no ``diff --git`` line). The only integrity field is ``report_sha256``. AEVE has no
CLI command that emits the document; ``aeve review`` runs only diagnosis and dead-code executors.
So this module takes the JSON document as input and validates it strictly. Base identity is
therefore enforced by VST: the caller states the head AEVE analysed (``proposal_base_head``), the
worktree HEAD must equal the pinned base, and every hunk must apply to the base content
(``git apply`` context and removed lines are compared with the real file bytes).

Nothing touches the worktree until the whole change was built in a throw-away index, turned into
a candidate commit object and accepted by the gate. See docs/sdlc/u5/PATCH_PROPOSALS.md.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import worker_gate as wg
from .worker_gate import ACCEPTED, BLOCKED, REFUSED, IsolationContext, WorkerGateVerdict

PROPOSAL_SCHEMA = "g6.patch.v1"
SHARE_SCHEMA = "vst-change-origin-share-v1"

MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_PROPOSALS = 256
MAX_DIFF_BYTES_PER_PROPOSAL = 512 * 1024
MAX_TOTAL_DIFF_BYTES = 4 * 1024 * 1024
MAX_FIELD_CHARS = 2000
MAX_HUNK_LINES = 100000
MAX_GIT_OUTPUT = 16 * 1024 * 1024
DEFAULT_GIT_TIMEOUT = 30.0
MIN_OVERRIDE_REASON = 10
MAX_OVERRIDE_REASON = 500

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

# Prefix of every git call: literal pathspecs, no fsmonitor hook, no signing.
_GIT_PREFIX = ("--literal-pathspecs", "-c", "core.fsmonitor=false", "-c", "commit.gpgsign=false")


class ProposalError(Exception):
    """The proposal document or an input is malformed; the result is BLOCKED."""

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
    # Same canonical form as AEVE patch.py:245-248.
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


def _check_diff(file: str, diff: object) -> tuple[str, int, int]:
    """Validate one AEVE per-file unified diff; return (text, added, deleted)."""
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
    index, added, deleted, hunks = 2, 0, 0, 0
    while index < len(lines):
        match = _HUNK.fullmatch(lines[index])
        if not match:
            raise ProposalError("PROPOSAL_MALFORMED", "line outside any hunk")
        old_len = int(match.group(2)) if match.group(2) is not None else 1
        new_len = int(match.group(4)) if match.group(4) is not None else 1
        if old_len > MAX_HUNK_LINES or new_len > MAX_HUNK_LINES:
            raise ProposalError("PROPOSAL_TOO_LARGE", "hunk length exceeds the cap")
        index += 1
        hunks += 1
        old_seen = new_seen = 0
        body_started = False
        while old_seen < old_len or new_seen < new_len or (index < len(lines) and lines[index] == _NO_NEWLINE and body_started):
            if index >= len(lines):
                raise ProposalError("PROPOSAL_MALFORMED", "hunk is shorter than its header says")
            line = lines[index]
            if line == _NO_NEWLINE:
                if not body_started:
                    raise ProposalError("PROPOSAL_MALFORMED", "no-newline marker before any hunk line")
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
            body_started = True
            index += 1
    if hunks == 0 or added + deleted == 0:
        raise ProposalError("PROPOSAL_MALFORMED", f"diff for {_show(file)} changes nothing")
    return diff[:-1] if diff.endswith("\n") else diff, added, deleted


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
    for key in ("note",):
        if key in doc and (not isinstance(doc[key], str) or len(doc[key]) > MAX_FIELD_CHARS):
            raise ProposalError("PROPOSAL_MALFORMED", f"{key} is not a short string")
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
            text, added, deleted = _check_diff(file, item["diff"])
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
    if len({_fold(f) for f in patched}) != len(patched):
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


def build_git_env(scratch: str, *, index_file: str | None = None) -> dict[str, str]:
    """Fixed minimal environment for every git call; nothing is inherited except system paths."""
    git_path = shutil.which("git")
    env = {
        "PATH": os.path.dirname(git_path) if git_path else "",
        "HOME": scratch, "USERPROFILE": scratch, "TEMP": scratch, "TMP": scratch,
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
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
    return env


def default_git_runner(args: Sequence[str], *, cwd: str, env: Mapping[str, str],
                       stdin: bytes | None = None, timeout: float = DEFAULT_GIT_TIMEOUT) -> GitResult:
    """Run git with shell=False, an explicit environment, cwd and timeout; never raises on git errors."""
    exe = shutil.which("git", path=env.get("PATH") or None)
    if exe is None:
        return GitResult(-1, b"", b"git executable not found")
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
    result = runner([*_GIT_PREFIX, *args], cwd=cwd, env=env, stdin=stdin, timeout=timeout)
    if not isinstance(result, GitResult):
        raise _GitFail("GIT_RUNNER_MALFORMED", "runner did not return a GitResult")
    if result.timed_out:
        raise _GitFail("GIT_TIMEOUT", f"git {args[0]} exceeded {timeout}s")
    if len(result.stdout) > MAX_GIT_OUTPUT:
        raise _GitFail("GIT_OUTPUT_TOO_LARGE", f"git {args[0]} output exceeds the cap")
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
    candidate_head: str | None = None
    changed_paths: tuple[str, ...] = ()
    diff_bytes: bytes | None = None
    diff_sha256: str | None = None
    report_sha256: str | None = None
    hunks_by_file: dict | None = None           # input for change_origin_share (proposal side)
    no_patch_paths: tuple[str, ...] = ()
    gate: WorkerGateVerdict | None = None

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict, "stage": self.stage, "worktree_state": self.worktree_state,
            "reasons": [{"code": c, "detail": d} for c, d in self.reasons],
            "candidate_head": self.candidate_head, "changed_paths": list(self.changed_paths),
            "diff_sha256": self.diff_sha256, "report_sha256": self.report_sha256,
            "hunks_by_file": self.hunks_by_file, "no_patch_paths": list(self.no_patch_paths),
            "gate": self.gate.to_dict() if self.gate else None,
        }


def _result(verdict: str, reasons: Iterable[tuple[str, str]], stage: str, state: str = "UNCHANGED", **extra: Any) -> ApplyResult:
    return ApplyResult(verdict, tuple(reasons), stage, state, **extra)


# ---------------------------------------------------------------------------- applying
def _norm_root(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.realpath(path)))


def apply_proposals(
    *, document: object, manifest_sha256: object, base_head: object, proposal_base_head: object,
    allowed_paths: object, protected_paths: object, isolation: object,
    git_runner: GitRunner = default_git_runner, timeout: float = DEFAULT_GIT_TIMEOUT,
) -> ApplyResult:
    """Apply the patches of one AEVE proposal document in the isolated worktree; never raises.

    ``document`` is the parsed ``g6.patch.v1`` object or its raw bytes. ``proposal_base_head`` is the
    head AEVE analysed when it produced the document (caller-reported, for example the ``head`` of
    the AEVE review response of the same run); ``base_head`` is the pinned base of the worktree.
    The worktree is written only after the gate accepted the change (stage ``MATERIALIZE``);
    a failure in that last stage is rolled back and, if the rollback fails, reported as UNKNOWN.
    """
    scratch: str | None = None
    try:
        if isinstance(document, bytes):
            document = parse_proposal_json(document)
        pset = validate_proposal_document(document)
        patches = pset.patches
        if not patches:
            return _result(BLOCKED, [("NO_PATCH_IN_PROPOSAL", "the document holds no patch; the model may write these paths")],
                           "VALIDATE", report_sha256=pset.report_sha256, no_patch_paths=pset.no_patch_paths)
        for name, value in (("base_head", base_head), ("proposal_base_head", proposal_base_head)):
            if not (isinstance(value, str) and _HEX40.fullmatch(value)):
                raise ProposalError("MALFORMED_INPUT", f"{name} must be a lowercase 40-hex commit id")
        if not isinstance(isolation, IsolationContext):
            raise ProposalError("MALFORMED_INPUT", "isolation context is missing")
        common = {"report_sha256": pset.report_sha256, "no_patch_paths": pset.no_patch_paths}
        if proposal_base_head != base_head:
            return _result(REFUSED, [("STALE_BASE", "the proposal was made for another head than the worktree base")],
                           "BASE_HEAD", **common)

        # Stage PRESCREEN: scope, protected paths and path hazards on the claimed diff, before any git call.
        claimed = b"".join(git_patch_bytes(p) for p in patches)
        synthetic = hashlib.sha1(f"{base_head}:{pset.report_sha256}:prescreen".encode("ascii")).hexdigest()
        screen = wg.gate_worker_change(
            manifest_sha256=manifest_sha256, base_head=base_head, candidate_head=synthetic,
            changed_paths=list(pset.patched_paths), allowed_paths=allowed_paths, protected_paths=protected_paths,
            diff_bytes=claimed, isolation=dataclasses.replace(isolation, worktree_head=synthetic))
        if screen.verdict != ACCEPTED:
            return _result(screen.verdict, screen.reasons, "PRESCREEN", gate=screen, **common)

        root = isolation.worktree_root
        if not (isinstance(root, str) and os.path.isdir(root)):
            raise ProposalError("MALFORMED_INPUT", "worktree_root is not an existing directory")
        scratch = tempfile.mkdtemp(prefix="vst-u5-2-")
        try:
            inside = os.path.commonpath([_norm_root(scratch), _norm_root(root)]) == _norm_root(root)
        except ValueError:  # different drives: disjoint
            inside = False
        if inside:
            raise ProposalError("MALFORMED_INPUT", "scratch directory would be inside the worktree")
        env = build_git_env(scratch)
        index_env = build_git_env(scratch, index_file=os.path.join(scratch, "vst-throwaway-index"))

        def git(args: Sequence[str], *, use_index: bool = False, stdin: bytes | None = None, ok: Sequence[int] = (0,)) -> GitResult:
            return _git(git_runner, args, cwd=root, env=index_env if use_index else env, timeout=timeout, stdin=stdin, ok=ok)

        # Stage WORKTREE_CHECK: the cwd is the worktree top level, HEAD is the pinned base, touched paths are clean.
        top = _git_text(git(["rev-parse", "--show-toplevel"]))
        if _norm_root(top) != _norm_root(root):
            return _result(BLOCKED, [("WORKTREE_ROOT_MISMATCH", "git top level differs from the isolation worktree root")], "WORKTREE_CHECK", **common)
        head = _git_object(git(["rev-parse", "--verify", "--quiet", "HEAD^{commit}"]))
        if head != base_head:
            return _result(REFUSED, [("STALE_BASE", "worktree HEAD differs from the pinned base head")], "WORKTREE_CHECK", **common)
        status = git(["status", "--porcelain=v1", "-z", "--untracked-files=no", "--", *pset.patched_paths])
        if status.stdout:
            return _result(BLOCKED, [("DIRTY_WORKTREE", "a path to patch already has uncommitted changes")], "WORKTREE_CHECK", **common)
        base_tree = _git_object(git(["rev-parse", "--verify", "--quiet", f"{base_head}^{{tree}}"]))

        # Stage BUILD: apply every patch, in document order, to a throw-away index. The worktree is not touched.
        git(["read-tree", base_head], use_index=True)
        for proposal in patches:
            patch = git_patch_bytes(proposal)
            apply_args = ["apply", "--cached", "--whitespace=nowarn", f"--include={proposal.file}", "-"]
            checked = git([apply_args[0], "--check", *apply_args[1:]], use_index=True, stdin=patch, ok=(0, 1))
            if checked.returncode == 1:
                text = checked.stderr.decode("utf-8", "replace")
                if "corrupt patch" in text or "malformed patch" in text:
                    return _result(BLOCKED, [("PROPOSAL_MALFORMED", f"git rejected the patch for {_show(proposal.file)} as corrupt")], "BUILD", **common)
                return _result(REFUSED, [("STALE_BASE", f"patch for {_show(proposal.file)} ({proposal.recipe}) does not apply to the base content")],
                               "BUILD", **common)
            git(apply_args, use_index=True, stdin=patch)
        tree = _git_object(git(["write-tree"], use_index=True))
        if tree == base_tree:
            return _result(BLOCKED, [("NO_EFFECT", "the patches leave the base tree unchanged")], "BUILD", **common)
        candidate = _git_object(git(["commit-tree", tree, "-p", base_head, "-m", f"VST U5-2 candidate {pset.report_sha256}"]))
        if candidate == base_head:
            return _result(BLOCKED, [("NO_EFFECT", "candidate equals base")], "BUILD", **common)
        diff = git(["diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames",
                    "--src-prefix=a/", "--dst-prefix=b/", base_head, candidate]).stdout
        names = git(["diff", "--name-only", "-z", "--no-renames", base_head, candidate]).stdout
        changed = sorted(n for n in names.decode("utf-8").split("\0") if n)
        if not diff or not changed:
            return _result(BLOCKED, [("NO_EFFECT", "empty resulting diff")], "BUILD", **common)
        if set(changed) != set(pset.patched_paths):
            return _result(REFUSED, [("DIFF_PATH_MISMATCH", "resulting changed paths differ from the proposed files")], "BUILD", **common)
        facts = {**common, "candidate_head": candidate, "changed_paths": tuple(changed), "diff_bytes": diff,
                 "diff_sha256": hashlib.sha256(diff).hexdigest()}

        # Stage GATE: the real resulting diff goes through worker_gate (diff gate, scope, protected paths, isolation proof).
        verdict = wg.gate_worker_change(
            manifest_sha256=manifest_sha256, base_head=base_head, candidate_head=candidate,
            changed_paths=changed, allowed_paths=allowed_paths, protected_paths=protected_paths,
            diff_bytes=diff, isolation=dataclasses.replace(isolation, worktree_head=candidate))
        if verdict.verdict != ACCEPTED:
            return _result(verdict.verdict, verdict.reasons, "GATE", gate=verdict, **facts)
        hunks = hunk_counts_from_diff(diff)
        facts["hunks_by_file"] = hunks

        # Stage MATERIALIZE: the only stage that writes the worktree (working files only, index and HEAD stay).
        paths_nul = b"".join(p.encode("utf-8") + b"\0" for p in changed)
        restore = ["restore", "--worktree", "--pathspec-from-file=-", "--pathspec-file-nul"]
        try:
            git([restore[0], f"--source={candidate}", *restore[1:]], stdin=paths_nul)
            same = git(["diff", "--quiet", "--no-ext-diff", "--no-textconv", candidate, "--", *changed], ok=(0, 1))
        except Exception as exc:  # any failure after the first write attempt must roll back
            detail = getattr(exc, "detail", type(exc).__name__)
            return _rollback(git, restore, base_head, paths_nul,
                             [(getattr(exc, "code", "MATERIALIZE_FAILED"), str(detail))], verdict, facts)
        if same.returncode != 0:
            return _rollback(git, restore, base_head, paths_nul,
                             [("MATERIALIZE_VERIFY_FAILED", "worktree files differ from the candidate after writing")], verdict, facts)
        return _result(ACCEPTED, verdict.reasons, "MATERIALIZE", "MODIFIED", gate=verdict, **facts)
    except ProposalError as exc:
        return _result(BLOCKED, [(exc.code, exc.detail)], "VALIDATE")
    except _GitFail as exc:
        return _result(BLOCKED, [(exc.code, exc.detail)], "GIT")
    except Exception as exc:  # fail closed on anything unexpected
        return _result(BLOCKED, [("INTERNAL_ERROR", type(exc).__name__)], "INTERNAL")
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)


def _rollback(git: Callable[..., GitResult], restore: list[str], base_head: str, paths_nul: bytes,
              reasons: list[tuple[str, str]], gate: WorkerGateVerdict, facts: dict) -> ApplyResult:
    """Restore the touched files from the pinned base; UNKNOWN when even that fails."""
    try:
        git([restore[0], f"--source={base_head}", *restore[1:]], stdin=paths_nul)
    except Exception as exc:
        return _result(BLOCKED, reasons + [("ROLLBACK_FAILED", type(exc).__name__)], "MATERIALIZE", "UNKNOWN", gate=gate, **facts)
    return _result(BLOCKED, reasons + [("ROLLED_BACK", "touched files were restored from the base head")], "MATERIALIZE", "UNCHANGED", gate=gate, **facts)


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


# ---------------------------------------------------------------------------- model must not override proposals
@dataclass(frozen=True)
class ModelChangeVerdict:
    verdict: str
    reasons: tuple[tuple[str, str], ...]
    overrides: tuple[dict, ...]        # recorded explicit overrides: {"path", "reason"}
    model_only_paths: tuple[str, ...]  # model paths with no proposed patch

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "reasons": [{"code": c, "detail": d} for c, d in self.reasons],
                "overrides": [dict(o) for o in self.overrides], "model_only_paths": list(self.model_only_paths)}


def _reason_problem(reason: object) -> str | None:
    if not isinstance(reason, str):
        return "reason is not a string"
    text = reason.strip()
    if not MIN_OVERRIDE_REASON <= len(text) <= MAX_OVERRIDE_REASON:
        return f"reason must have {MIN_OVERRIDE_REASON} to {MAX_OVERRIDE_REASON} characters after trimming"
    if any(ord(ch) < 32 or ord(ch) == 0x7F for ch in text):
        return "reason contains control characters"
    return None


def check_model_changes(
    *, proposal_patched_paths: object, model_changed_paths: object, override_reasons: object = None,
) -> ModelChangeVerdict:
    """The model may write only paths AEVE proposed no patch for; never raises.

    A model change on a patched path is REFUSED (MODEL_OVERRIDES_PROPOSAL) unless
    ``override_reasons`` maps that exact model path to a stated reason; then it is ACCEPTED with the
    override recorded (MODEL_OVERRIDE_RECORDED and ``overrides``). An override for a path
    that is not in conflict is BLOCKED (OVERRIDE_WITHOUT_CONFLICT). Whether the model change is also
    in scope is the business of worker_gate, not of this function.
    """
    try:
        patched = _paths("proposal_patched_paths", proposal_patched_paths)
        model = _paths("model_changed_paths", model_changed_paths)
        if override_reasons is None:
            override_reasons = {}
        if not isinstance(override_reasons, Mapping) or any(not isinstance(k, str) for k in override_reasons):
            raise ProposalError("MALFORMED_INPUT", "override_reasons must map model paths to reason strings")
        patched_keys = {_fold(p) for p in patched}
        conflicts = sorted({m for m in model if _fold(m) in patched_keys})
        refuse: list[tuple[str, str]] = []
        block: list[tuple[str, str]] = []
        recorded: list[dict] = []
        for path in conflicts:
            if path not in override_reasons:
                refuse.append(("MODEL_OVERRIDES_PROPOSAL", _show(path)))
                continue
            problem = _reason_problem(override_reasons[path])
            if problem:
                refuse.append(("OVERRIDE_REASON_INVALID", f"{_show(path)}: {problem}"))
                continue
            recorded.append({"path": path, "reason": override_reasons[path].strip()})
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
