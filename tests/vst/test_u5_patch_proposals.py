"""U5-2: apply AEVE patch proposals through the diff gate.

Acceptance text: "AEVE's repair lab (diagnosis, dead-code candidates, bounded patch proposals; it
never applies a patch itself) supplies the patch; VST applies it in the isolated worktree and the
deterministic diff gate checks it; the model writes code only for what AEVE proposed no patch for;
a patch outside scope, on a protected path, or with a stale base is refused; the share of a change
produced by proposals versus the model is recorded per run."

Two kinds of tests. Most use a scripted git runner (`FakeGit`) injected through `git_runner`, with
real files under tmp_path for the worktree. The block at the end uses a real tiny git repository
and the default runner; it is skipped when no git is found. The proposal document follows the real
AEVE `g6.patch.v1` shape (AEVE src/aeve/repair/patch.py); diffs for the real-git tests are built with
`difflib.unified_diff(lineterm="")` exactly as AEVE does. Expected bytes, counts and fractions are
hand-computed from the data written in this file, never taken from the code under test.
"""

from __future__ import annotations

import copy
import difflib
import hashlib
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from tools.vst import patch_proposals as pp
from tools.vst import worker_gate as wg

MANIFEST = "a" * 64
BASE = "b" * 40
OTHER_HEAD = "d" * 40
CAND = "c" * 40
TREE_BASE = "1" * 40
TREE_NEW = "2" * 40
ALLOWED = ("src/app.py",)
REASON = "AEVE patch removes a trailing space inside a string the task needs"
AUTHOR = "operator-1"
BASE_TEXT = "a\nb  \nc\n"
CAND_TEXT = "a\nb\nc\n"
PL = len(pp.GIT_PREFIX)
_UNSET = object()


def shown(value):
    return ascii(value)


# ---------------------------------------------------------------------------- document builders
def aeve_diff(path="src/app.py"):
    """One AEVE per-file diff: headers without a/ b/ prefix, one hunk, one changed line."""
    return "\n".join([f"--- {path}", f"+++ {path}", "@@ -1,3 +1,3 @@", " a", "-b  ", "+b", " c"])


def difflib_diff(path, old, new):
    """The way AEVE patch.py builds a diff: splitlines + unified_diff(lineterm="")."""
    return "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=path, tofile=path, lineterm=""))


def eof_marker_diff(path, last_line, line_number):
    """AEVE's special form for a file whose only change is the final newline (patch.py _diff)."""
    return "\n".join([f"--- {path}", f"+++ {path}", f"@@ -{line_number},1 +{line_number},1 @@", f"-{last_line}",
                      "\\ No newline at end of file", f"+{last_line}"])


def git_diff(path="src/app.py"):
    return (f"diff --git a/{path} b/{path}\nindex 1111111..2222222 100644\n--- a/{path}\n+++ b/{path}\n"
            "@@ -1,3 +1,3 @@\n a\n-b  \n+b\n c\n").encode()


def proposal(file="src/app.py", recipe="trailing-whitespace", changed=True, diff=None, detail="Strip trailing spaces/tabs"):
    text = (aeve_diff(file) if diff is None else diff) if changed else ""
    return {"file": file, "recipe": recipe, "detail": detail, "diff": text, "changed": changed}


def report_hash(doc):
    # Independent restatement of AEVE patch.py: sha256 of the canonical JSON without report_sha256.
    body = {k: v for k, v in doc.items() if k != "report_sha256"}
    return hashlib.sha256(json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def make_doc(*proposals, **over):
    doc = {"schema_version": "g6.patch.v1", "proposals": list(proposals), "proposal_count": len(proposals),
           "llm_calls": 0, "executed_project_code": False,
           "note": "Proposals only; patches are never auto-applied and require a re-test."}
    doc.update({k: v for k, v in over.items() if k != "report_sha256"})
    doc["report_sha256"] = over.get("report_sha256", report_hash(doc))
    return doc


def rehash(doc):
    doc = dict(doc)
    doc["report_sha256"] = report_hash(doc)
    return doc


# ---------------------------------------------------------------------------- isolation and git fakes
def make_isolation(tmp_path, head=BASE):
    worktree = tmp_path / "worktree"
    main = tmp_path / "main"
    (worktree / ".git").mkdir(parents=True, exist_ok=True)
    (worktree / ".git" / "config").write_bytes(b"[core]\n\trepositoryformatversion = 0\n")
    (worktree / "src").mkdir(exist_ok=True)
    (worktree / "src" / "app.py").write_bytes(BASE_TEXT.encode())
    main.mkdir(exist_ok=True)

    def lstat(path):
        info = os.lstat(path)
        return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=getattr(info, "st_file_attributes", 0))

    return wg.IsolationContext(str(worktree), str(main), False, head, None, lstat=lstat)


class FakeGit:
    """Scripted git: answers by subcommand (args[PL]; the first PL items are the fixed prefix) and records calls."""

    def __init__(self, root, *, head=BASE, toplevel=None, dirty=False, check_rc=0, check_err=None, apply_rc=0,
                 tree=TREE_NEW, diff=None, names=b"src/app.py\0", timeout_on=None, flags=b"H src/app.py\0",
                 base_blobs=None, cand_blobs=None, git_dirs=b".git\n.git\n", status_out=None):
        self.root, self.head, self.dirty = root, head, dirty
        self.check_rc, self.check_err, self.apply_rc, self.tree = check_rc, check_err, apply_rc, tree
        self.toplevel = (toplevel or root).replace("\\", "/")
        self.diff = git_diff() if diff is None else diff
        self.names, self.timeout_on, self.flags, self.git_dirs = names, timeout_on, flags, git_dirs
        self.base_blobs = {"src/app.py": BASE_TEXT.encode()} if base_blobs is None else base_blobs
        self.cand_blobs = {"src/app.py": CAND_TEXT.encode()} if cand_blobs is None else cand_blobs
        self.status_out = status_out
        self.calls = []

    def subs(self):
        return [c["sub"] for c in self.calls]

    def __call__(self, args, *, cwd, env, stdin=None, timeout):
        sub, rest = args[PL], list(args[PL + 1:])
        self.calls.append({"sub": sub, "rest": rest, "cwd": cwd, "env": dict(env), "stdin": stdin,
                           "timeout": timeout, "prefix": list(args[:PL])})
        if sub == self.timeout_on:
            return pp.GitResult(-1, b"", b"", True)
        if sub == "rev-parse":
            if "--show-toplevel" in rest:
                return pp.GitResult(0, self.toplevel.encode() + b"\n")
            if "--git-dir" in rest:
                return pp.GitResult(0, self.git_dirs)
            if rest[-1].endswith("^{tree}"):
                return pp.GitResult(0, TREE_BASE.encode() + b"\n")
            return pp.GitResult(0, self.head.encode() + b"\n")
        if sub == "status":
            out = self.status_out if self.status_out is not None else (b" M src/app.py\0" if self.dirty else b"")
            return pp.GitResult(0, out)
        if sub == "ls-files":
            return pp.GitResult(0, self.flags)
        if sub == "cat-file":
            rev, path = rest[-1].split(":", 1)
            return pp.GitResult(0, (self.base_blobs if rev == BASE else self.cand_blobs)[path])
        if sub == "read-tree":
            return pp.GitResult(0)
        if sub == "apply":
            if "--check" in rest:
                err = self.check_err
                if err is None and self.check_rc == 1:
                    err = b"error: patch failed: src/app.py:1\nerror: src/app.py: patch does not apply\n"
                return pp.GitResult(self.check_rc, b"", err or b"")
            return pp.GitResult(self.apply_rc, b"", b"error: boom\n" if self.apply_rc else b"")
        if sub == "write-tree":
            return pp.GitResult(0, self.tree.encode() + b"\n")
        if sub == "commit-tree":
            return pp.GitResult(0, CAND.encode() + b"\n")
        if sub == "diff":
            if "--name-only" in rest:
                return pp.GitResult(0, self.names)
            return pp.GitResult(0, self.diff)
        return pp.GitResult(128, b"", b"unexpected")


def run(tmp_path, *, fake_kw=None, doc=_UNSET, prepare=None, **over):
    isolation = make_isolation(tmp_path)
    if prepare:
        prepare(isolation.worktree_root)
    fake = FakeGit(isolation.worktree_root, **(fake_kw or {}))
    kwargs = dict(document=make_doc(proposal()) if doc is _UNSET else doc, manifest_sha256=MANIFEST,
                  base_head=BASE, proposal_base_head=BASE, allowed_paths=ALLOWED, protected_paths=(),
                  isolation=isolation, git_runner=fake)
    kwargs.update(over)
    return pp.apply_proposals(**kwargs), fake


def app_bytes(fake):
    with open(os.path.join(fake.root, "src", "app.py"), "rb") as handle:
        return handle.read()


def codes(result):
    return [c for c, _ in result.reasons]


def git_dir_files(fake):
    return sorted(os.listdir(os.path.join(fake.root, ".git")))


# ---------------------------------------------------------------------------- valid proposal
def test_valid_proposal_is_applied_and_accepted(tmp_path):
    result, fake = run(tmp_path)
    assert result.verdict == "ACCEPTED"
    assert result.stage == "MATERIALIZE"
    assert result.worktree_state == "MODIFIED"
    assert result.post_materialize_verified is True
    assert result.candidate_head == CAND and result.candidate_tree == TREE_NEW
    assert result.changed_paths == ("src/app.py",)
    assert result.patched_paths == ("src/app.py",) and result.partial is False
    assert result.gate.verdict == "ACCEPTED"
    assert result.diff_sha256 == hashlib.sha256(git_diff()).hexdigest()
    assert result.hunks_by_file == {"src/app.py": [(1, 1)]}  # one hunk: one line added, one deleted
    assert app_bytes(fake) == CAND_TEXT.encode()
    assert result.file_digests == {"src/app.py": {"base_sha256": hashlib.sha256(BASE_TEXT.encode()).hexdigest(),
                                                  "candidate_sha256": hashlib.sha256(CAND_TEXT.encode()).hexdigest()}}
    assert "restore" not in fake.subs() and "checkout" not in fake.subs()  # the write is not done by git


def test_lock_and_journal_are_gone_after_a_run(tmp_path):
    result, fake = run(tmp_path)
    assert result.verdict == "ACCEPTED"
    assert git_dir_files(fake) == ["config"]


def test_result_dict_is_json_able_and_marks_the_isolation_stage(tmp_path):
    result, _ = run(tmp_path)
    data = json.loads(json.dumps(result.to_dict()))
    assert data["isolation_stage"] == "pre_materialize"
    assert data["post_materialize_verified"] is True
    assert data["hunks_by_file"] == {"src/app.py": [[1, 1]]}
    proof = data["gate"]["isolation_proof"]
    assert proof["isolation_stage"] == "pre_materialize"
    assert "placeholder" in proof["worktree_head_note"] and "unchanged" in proof["worktree_head_note"]


def test_document_may_be_given_as_json_bytes(tmp_path):
    result, _ = run(tmp_path, doc=json.dumps(make_doc(proposal())).encode())
    assert result.verdict == "ACCEPTED"


def test_patch_is_checked_then_applied_to_a_throwaway_index_and_object_directory(tmp_path):
    result, fake = run(tmp_path)
    assert result.verdict == "ACCEPTED"
    applies = [c for c in fake.calls if c["sub"] == "apply"]
    assert ["--check" in c["rest"] for c in applies] == [True, False]
    assert all("--cached" in c["rest"] for c in applies)
    expected = (b"diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n"
                b"@@ -1,3 +1,3 @@\n a\n-b  \n+b\n c\n")
    assert all(c["stdin"] == expected for c in applies)
    for call in applies + [c for c in fake.calls if c["sub"] in ("read-tree", "write-tree")]:
        assert "GIT_INDEX_FILE" in call["env"]
    for call in fake.calls:  # a scratch object directory, so no object lands in the repository
        assert "GIT_OBJECT_DIRECTORY" in call["env"]
        assert call["env"]["GIT_OBJECT_DIRECTORY"].startswith(call["env"]["TEMP"])
        assert call["env"]["GIT_ALTERNATE_OBJECT_DIRECTORIES"] == os.path.join(fake.root, ".git", "objects")


def test_gate_runs_before_any_write_and_again_right_before_it(tmp_path, monkeypatch):
    events = []
    real_gate, real_write = pp.wg.gate_worker_change, pp._atomic_write

    def gate(**kw):
        events.append("gate")
        return real_gate(**kw)

    def write(*a):
        events.append("write")
        return real_write(*a)

    monkeypatch.setattr(pp.wg, "gate_worker_change", gate)
    monkeypatch.setattr(pp, "_atomic_write", write)
    result, _ = run(tmp_path)
    assert result.verdict == "ACCEPTED"
    assert events == ["gate", "gate", "gate", "write"]  # prescreen, real diff, re-check, then the single write


def test_status_is_scoped_to_the_patched_paths(tmp_path):
    result, fake = run(tmp_path)
    status = [c for c in fake.calls if c["sub"] == "status"]
    assert len(status) == 1 and status[0]["rest"][-2:] == ["--", "src/app.py"]
    assert [c["rest"][-2:] for c in fake.calls if c["sub"] == "ls-files"] == [["--", "src/app.py"]]


def test_every_git_call_uses_the_worktree_cwd_fixed_prefix_timeout_and_minimal_env(tmp_path, monkeypatch):
    monkeypatch.setenv("VST_SENTINEL_SECRET", "leak")
    result, fake = run(tmp_path, timeout=7.5)
    assert result.verdict == "ACCEPTED"
    root = make_isolation(tmp_path).worktree_root
    for call in fake.calls:
        assert call["cwd"] == root
        assert call["timeout"] == 7.5
        assert call["prefix"] == list(pp.GIT_PREFIX)
        assert "VST_SENTINEL_SECRET" not in call["env"]
        assert call["env"]["GIT_TERMINAL_PROMPT"] == "0" and call["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
    prefix = " ".join(pp.GIT_PREFIX)
    for needed in (f"core.attributesFile={os.devnull}", f"core.hooksPath={os.devnull}", "core.autocrlf=false",
                   "core.safecrlf=false", "core.quotepath=false", "core.fsmonitor=false", "--literal-pathspecs"):
        assert needed in prefix
    index_calls = [c for c in fake.calls if "GIT_INDEX_FILE" in c["env"]]
    assert {c["sub"] for c in index_calls} == {"read-tree", "apply", "write-tree"}
    assert not os.path.normcase(index_calls[0]["env"]["GIT_INDEX_FILE"]).startswith(os.path.normcase(root))


def test_scratch_directory_is_removed_after_the_run(tmp_path):
    result, fake = run(tmp_path)
    assert result.verdict == "ACCEPTED"
    assert not os.path.exists(fake.calls[0]["env"]["TEMP"])


def test_two_recipes_for_one_file_are_applied_in_document_order(tmp_path):
    second = proposal(recipe="final-newline", detail="Ensure a single trailing newline", diff=eof_marker_diff("src/app.py", "c", 3))
    result, fake = run(tmp_path, doc=make_doc(proposal(), second))
    assert result.verdict == "ACCEPTED"
    applies = [c for c in fake.calls if c["sub"] == "apply" and "--check" not in c["rest"]]
    assert len(applies) == 2
    assert applies[0]["stdin"].startswith(b"diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1,3 +1,3 @@")
    assert applies[1]["stdin"].endswith(b"@@ -3,1 +3,1 @@\n-c\n\\ No newline at end of file\n+c\n")


def test_flagged_only_paths_are_reported_and_need_no_patch(tmp_path):
    doc = make_doc(proposal(), proposal(file="src/other.py", recipe="unused-import", changed=False, detail="Remove unused import 'os'"),
                   proposal(file="src/other.py", recipe="unused-import", changed=False, detail="Remove unused import 'sys'"))
    result, _ = run(tmp_path, doc=doc)
    assert result.verdict == "ACCEPTED"
    assert result.no_patch_paths == ("src/other.py",)


def test_partial_report_with_uncovered_list_is_valid_and_exposed(tmp_path):
    doc = make_doc(proposal(), status="PARTIAL", uncovered=["LANGUAGE_NOT_INDEXED: web/app.js"])
    result, _ = run(tmp_path, doc=doc)
    assert result.verdict == "ACCEPTED" and result.partial is True


def test_document_without_a_patch_is_blocked_and_touches_nothing(tmp_path):
    doc = make_doc(proposal(recipe="unused-import", changed=False, detail="Remove unused import 'os'"))
    result, fake = run(tmp_path, doc=doc)
    assert result.verdict == "BLOCKED" and codes(result) == ["NO_PATCH_IN_PROPOSAL"]
    assert fake.calls == []


def test_partial_document_without_any_patch_is_blocked(tmp_path):
    doc = make_doc(proposal(file="web/a.js", recipe="unsupported-language", changed=False, detail="Repair proposals do not cover JavaScript sources"),
                   status="PARTIAL", uncovered=["LANGUAGE_NOT_INDEXED: web/a.js"])
    result, fake = run(tmp_path, doc=doc)
    assert codes(result) == ["NO_PATCH_IN_PROPOSAL"] and result.partial is True
    assert fake.calls == []


# ---------------------------------------------------------------------------- stale base
def test_proposal_made_for_another_head_is_refused_stale_base(tmp_path):
    result, fake = run(tmp_path, proposal_base_head=OTHER_HEAD)
    assert result.verdict == "REFUSED" and codes(result) == ["STALE_BASE"]
    assert result.worktree_state == "UNCHANGED" and fake.calls == []


def test_worktree_head_that_moved_is_refused_stale_base_before_any_write(tmp_path):
    result, fake = run(tmp_path, fake_kw={"head": OTHER_HEAD})
    assert result.verdict == "REFUSED" and codes(result) == ["STALE_BASE"]
    assert "apply" not in fake.subs() and app_bytes(fake) == BASE_TEXT.encode()


@pytest.mark.parametrize("err", [
    b"error: patch failed: src/app.py:1\nerror: src/app.py: patch does not apply\n",
    b"error: src/app.py: does not match index\n",
])
def test_patch_that_does_not_apply_to_the_base_content_is_refused_stale_base(tmp_path, err):
    result, fake = run(tmp_path, fake_kw={"check_rc": 1, "check_err": err})
    assert result.verdict == "REFUSED" and codes(result) == ["STALE_BASE"]
    assert result.stage == "BUILD" and result.worktree_state == "UNCHANGED"
    assert sum(1 for c in fake.calls if c["sub"] == "apply") == 1  # stopped at the first failing check
    assert app_bytes(fake) == BASE_TEXT.encode()


@pytest.mark.parametrize("rc, err", [
    (1, b"error: src/app.py: does not exist in index\n"),
    (1, b"error: no valid patches in input (allow with \"--allow-empty\")\n"),
    (1, b"error: patch fragment without header at line 3\n"),
    (1, b"error: corrupt patch at line 9\n"),
    (1, b"error: src/app.py: is a symbolic link\n"),
    (128, b"fatal: not a git repository\n"),
])
def test_other_apply_failures_are_blocked_not_stale(tmp_path, rc, err):
    result, fake = run(tmp_path, fake_kw={"check_rc": rc, "check_err": err})
    assert result.verdict == "BLOCKED" and codes(result) == ["PATCH_DOES_NOT_APPLY"]
    detail = result.reasons[0][1]
    assert f"git exit {rc}" in detail and ascii(err.decode()[-200:]) in detail
    assert app_bytes(fake) == BASE_TEXT.encode()


def test_dubious_ownership_is_reported_as_unsafe_directory(tmp_path):
    result, _ = run(tmp_path, fake_kw={"check_rc": 128, "check_err": b"fatal: detected dubious ownership in repository at 'x'\n"})
    assert result.verdict == "BLOCKED" and codes(result) == ["GIT_UNSAFE_DIRECTORY"]


def test_missing_or_malformed_base_heads_are_blocked(tmp_path):
    for bad in (None, "", "b" * 39, "B" * 40, 5):
        result, fake = run(tmp_path, proposal_base_head=bad)
        assert result.verdict == "BLOCKED" and fake.calls == []
        result, fake = run(tmp_path, base_head=bad)
        assert result.verdict == "BLOCKED" and fake.calls == []


# ---------------------------------------------------------------------------- base bytes AEVE cannot represent
@pytest.mark.parametrize("blob", [
    b"a\r\nb  \r\nc\r\n", b"a\rb  \rc\r", b"\xef\xbb\xbfa\nb  \nc\n", b"a\nb  \x0bx\nc\n", b"a\nb  \x0c\nc\n",
    b"a\nb  \x1c\nc\n", b"a\nb  \x1d\nc\n", b"a\nb  \x1e\nc\n", "a\nb  \u0085\nc\n".encode(),
    "a\nb  \u2028\nc\n".encode(), "a\nb  \u2029\nc\n".encode(), b"a\nb  \xff\nc\n",
])
def test_base_file_aeve_cannot_have_diffed_is_blocked_not_stale(tmp_path, blob):
    def prepare(root):
        with open(os.path.join(root, "src", "app.py"), "wb") as handle:
            handle.write(blob)
    result, fake = run(tmp_path, prepare=prepare, fake_kw={"base_blobs": {"src/app.py": blob}})
    assert result.verdict == "BLOCKED" and codes(result) == ["PATCH_NOT_REPRESENTABLE"]
    assert "apply" not in fake.subs() and app_bytes(fake) == blob


# ---------------------------------------------------------------------------- scope and protected paths
def test_out_of_scope_patch_is_refused_before_any_git_call(tmp_path):
    result, fake = run(tmp_path, doc=make_doc(proposal(file="src/other.py")))
    assert result.verdict == "REFUSED"
    assert ("OUT_OF_SCOPE_PATH", shown("src/other.py")) in result.reasons
    assert result.stage == "PRESCREEN" and result.worktree_state == "UNCHANGED" and fake.calls == []


@pytest.mark.parametrize("path", [
    "CLAUDE.md", "docs/CLAUDE.md", "pkg/sub/AGENTS.md", ".github/workflows/ci.py", ".harness/x.py",
    "tools/vst/patch_proposals.py", ".claude/settings.py", "a/.git/hooks/pre-commit", ".git/config",
])
def test_protected_path_is_refused_even_when_listed_as_allowed(tmp_path, path):
    result, fake = run(tmp_path, doc=make_doc(proposal(file=path)), allowed_paths=(path,))
    assert result.verdict == "REFUSED"
    assert ("PROTECTED_PATH", shown(path)) in result.reasons
    assert fake.calls == [] and result.worktree_state == "UNCHANGED"


def test_caller_protected_path_is_refused(tmp_path):
    result, fake = run(tmp_path, protected_paths=("src",))
    assert result.verdict == "REFUSED" and ("PROTECTED_PATH", shown("src/app.py")) in result.reasons
    assert fake.calls == []


def test_second_proposed_file_outside_scope_refuses_the_whole_document(tmp_path):
    result, fake = run(tmp_path, doc=make_doc(proposal(), proposal(file="src/two.py")), allowed_paths=ALLOWED)
    assert result.verdict == "REFUSED" and result.stage == "PRESCREEN"
    assert fake.calls == [] and app_bytes(fake) == BASE_TEXT.encode()


# ---------------------------------------------------------------------------- the GATE stage
SUBMODULE_DIFF = (b"diff --git a/src/app.py b/src/app.py\nnew file mode 160000\nindex 0000000..2222222\n"
                  b"--- /dev/null\n+++ b/src/app.py\n@@ -0,0 +1 @@\n+Subproject commit " + b"1" * 40 + b"\n")


def test_gate_refusal_on_the_built_diff_stops_before_any_write(tmp_path):
    result, fake = run(tmp_path, fake_kw={"diff": SUBMODULE_DIFF})
    assert result.verdict == "REFUSED" and result.stage == "GATE"
    assert result.gate.verdict == "REFUSED"
    assert "SUBMODULE_CHANGE" in codes(result)
    assert result.worktree_state == "UNCHANGED" and result.post_materialize_verified is None
    assert app_bytes(fake) == BASE_TEXT.encode()
    assert git_dir_files(fake) == ["config"]


def test_gate_block_on_an_unparsable_built_diff_stops_before_any_write(tmp_path):
    result, fake = run(tmp_path, fake_kw={"diff": b"garbage, not a diff\n"})
    assert result.verdict == "BLOCKED" and result.stage == "GATE"
    assert result.gate.verdict == "BLOCKED" and "DIFF_UNPARSABLE" in codes(result)
    assert app_bytes(fake) == BASE_TEXT.encode() and result.worktree_state == "UNCHANGED"


def test_changed_set_that_differs_from_the_proposed_files_is_refused(tmp_path):
    result, fake = run(tmp_path, fake_kw={"names": b"src/app.py\0src/extra.py\0"})
    assert result.verdict == "REFUSED" and codes(result) == ["DIFF_PATH_MISMATCH"]
    assert app_bytes(fake) == BASE_TEXT.encode()


# ---------------------------------------------------------------------------- malformed proposals
def bad_schema(d): d["schema_version"] = "g6.patch.v2"; return rehash(d)
def extra_key(d): d["extra"] = 1; return rehash(d)
def llm_used(d): d["llm_calls"] = 1; return rehash(d)
def code_executed(d): d["executed_project_code"] = True; return rehash(d)
def count_wrong(d): d["proposal_count"] = 2; return rehash(d)
def hash_wrong(d): d["report_sha256"] = "0" * 64; return d
def hash_missing(d): del d["report_sha256"]; return d
def not_a_list(d): d["proposals"] = {}; return rehash(d)
def traversal(d): d["proposals"][0]["file"] = "../x.py"; d["proposals"][0]["diff"] = aeve_diff("../x.py"); return rehash(d)
def absolute(d): d["proposals"][0]["file"] = "/etc/x.py"; return rehash(d)
def backslash(d): d["proposals"][0]["file"] = "src\\app.py"; return rehash(d)
def glob_name(d): d["proposals"][0]["file"] = "src/*.py"; d["proposals"][0]["diff"] = aeve_diff("src/*.py"); return rehash(d)
def bracket_name(d): d["proposals"][0]["file"] = "[x"; d["proposals"][0]["diff"] = aeve_diff("[x"); return rehash(d)
def dash_name(d): d["proposals"][0]["file"] = "-x"; d["proposals"][0]["diff"] = aeve_diff("-x"); return rehash(d)
def header_other_file(d): d["proposals"][0]["diff"] = aeve_diff("src/zzz.py"); return rehash(d)
def hunk_too_short(d): d["proposals"][0]["diff"] = aeve_diff().rsplit("\n", 1)[0]; return rehash(d)
def hunk_too_long(d): d["proposals"][0]["diff"] = aeve_diff() + "\n+extra"; return rehash(d)
def empty_diff(d): d["proposals"][0]["diff"] = ""; return rehash(d)
def context_only(d): d["proposals"][0]["diff"] = "\n".join(["--- src/app.py", "+++ src/app.py", "@@ -1,2 +1,2 @@", " a", " c"]); return rehash(d)
def diff_on_note(d): d["proposals"][0].update(changed=False); return rehash(d)
def unknown_recipe(d): d["proposals"][0]["recipe"] = "rewrite-everything"; return rehash(d)
def note_recipe_with_patch(d): d["proposals"][0]["recipe"] = "unused-import"; return rehash(d)
def changed_not_bool(d): d["proposals"][0]["changed"] = 1; return rehash(d)
def missing_field(d): del d["proposals"][0]["detail"]; return rehash(d)
def extra_item_key(d): d["proposals"][0]["extra"] = 1; return rehash(d)
def redacted(d): d["proposals"][0]["diff"] = aeve_diff().replace("+b", "+[REDACTED]"); return rehash(d)
def duplicate_recipe(d): d["proposals"].append(copy.deepcopy(d["proposals"][0])); d["proposal_count"] = 2; return rehash(d)
def case_only_duplicate(d): d["proposals"].append(proposal(file="SRC/APP.PY")); d["proposal_count"] = 2; return rehash(d)
def nul_in_diff(d): d["proposals"][0]["diff"] = aeve_diff().replace("+b", "+b\x00"); return rehash(d)
def status_not_partial(d): d["status"] = "COMPLETE"; return rehash(d)
def note_not_string(d): d["note"] = 5; return rehash(d)
def uncovered_not_list(d): d["uncovered"] = "x"; return rehash(d)
def uncovered_bad_item(d): d["uncovered"] = [1]; return rehash(d)
def too_many(d): d["proposals"] = [proposal(file=f"f{i}.py") for i in range(pp.MAX_PROPOSALS + 1)]; d["proposal_count"] = len(d["proposals"]); return rehash(d)
def not_a_dict(d): return ["x"]

MALFORMED = [bad_schema, extra_key, llm_used, code_executed, count_wrong, hash_wrong, hash_missing, not_a_list,
             traversal, absolute, backslash, glob_name, bracket_name, dash_name, header_other_file, hunk_too_short,
             hunk_too_long, empty_diff, context_only, diff_on_note, unknown_recipe, note_recipe_with_patch, changed_not_bool,
             missing_field, extra_item_key, redacted, duplicate_recipe, case_only_duplicate, nul_in_diff,
             status_not_partial, note_not_string, uncovered_not_list, uncovered_bad_item, too_many, not_a_dict]


@pytest.mark.parametrize("mutate", MALFORMED, ids=lambda f: f.__name__)
def test_malformed_proposal_is_blocked_and_touches_nothing(tmp_path, mutate):
    result, fake = run(tmp_path, doc=mutate(make_doc(proposal())))
    assert result.verdict == "BLOCKED" and result.stage == "VALIDATE"
    assert fake.calls == [] and result.worktree_state == "UNCHANGED"


def test_hash_mismatch_has_its_own_code():
    with pytest.raises(pp.ProposalError) as info:
        pp.validate_proposal_document(hash_wrong(make_doc(proposal())))
    assert info.value.code == "PROPOSAL_HASH_MISMATCH"


def test_oversized_document_bytes_are_blocked(tmp_path):
    result, fake = run(tmp_path, doc=b"{" + b" " * (pp.MAX_DOCUMENT_BYTES + 1) + b"}")
    assert result.verdict == "BLOCKED" and codes(result) == ["PROPOSAL_TOO_LARGE"] and fake.calls == []


def test_oversized_single_diff_is_blocked(tmp_path):
    big = "\n".join(["--- src/app.py", "+++ src/app.py", "@@ -0,0 +1,40000 @@"] + ["+" + "x" * 20] * 40000)
    assert len(big.encode()) > pp.MAX_DIFF_BYTES_PER_PROPOSAL
    result, fake = run(tmp_path, doc=make_doc(proposal(diff=big)))
    assert result.verdict == "BLOCKED" and codes(result) == ["PROPOSAL_TOO_LARGE"] and fake.calls == []


@pytest.mark.parametrize("raw", [b"", b"not json", b"[1]", b'{"a": 1, "a": 2}', b'{"llm_calls": NaN}', b"\xff\xfe", b'{"a": "\x00"}'])
def test_unparsable_document_bytes_are_blocked(tmp_path, raw):
    result, fake = run(tmp_path, doc=raw)
    assert result.verdict == "BLOCKED" and fake.calls == []


@pytest.mark.parametrize("bad", [None, 5, "text", [], object()], ids=["none", "int", "text", "list", "object"])
def test_non_document_types_are_blocked(tmp_path, bad):
    result, fake = run(tmp_path, doc=bad)  # the sentinel lets None reach apply_proposals
    assert result.verdict == "BLOCKED" and result.stage == "VALIDATE" and fake.calls == []


def test_missing_isolation_context_is_blocked(tmp_path):
    result, fake = run(tmp_path, isolation=None)
    assert result.verdict == "BLOCKED" and fake.calls == []


# ---------------------------------------------------------------------------- the recipe label must describe the diff
def test_difflib_built_whitespace_and_newline_diffs_are_valid_recipes():
    ws = difflib_diff("pkg/m.py", "x = 1  \ny = 2\t\n\nz = 3\n", "x = 1\ny = 2\n\nz = 3\n")
    nl = difflib_diff("pkg/m.py", "x = 1\ny = 2\n\n\n", "x = 1\ny = 2\n")
    marker = eof_marker_diff("pkg/m.py", "y = 2", 2)
    for recipe, text in (("trailing-whitespace", ws), ("final-newline", nl), ("final-newline", marker)):
        doc = make_doc(proposal(file="pkg/m.py", recipe=recipe, diff=text))
        assert pp.validate_proposal_document(doc).patched_paths == ("pkg/m.py",)


def test_unpaired_difflib_shape_for_repeated_lines_is_valid():
    # SequenceMatcher aligns the second "x" with the first on the new side: removal, context, addition.
    text = difflib_diff("pkg/m.py", "x \nx\n", "x\nx\n")
    assert pp.validate_proposal_document(make_doc(proposal(file="pkg/m.py", diff=text))).patched_paths == ("pkg/m.py",)


def code_change(d):  # a "whitespace" patch that changes code
    d["proposals"][0]["diff"] = "\n".join(["--- src/app.py", "+++ src/app.py", "@@ -1,3 +1,3 @@", "-if check(x):", "+if True:", " a", " c"])
    return rehash(d)
def code_change_with_whitespace(d):
    d["proposals"][0]["diff"] = "\n".join(["--- src/app.py", "+++ src/app.py", "@@ -1,3 +1,3 @@", " a", "-if check(x):  ", "+if True:", " c"])
    return rehash(d)
def whitespace_added(d):
    d["proposals"][0]["diff"] = "\n".join(["--- src/app.py", "+++ src/app.py", "@@ -1,3 +1,3 @@", " a", "-b", "+b  ", " c"])
    return rehash(d)
def whitespace_lines_inserted(d):
    d["proposals"][0]["diff"] = "\n".join(["--- src/app.py", "+++ src/app.py", "@@ -1,3 +1,4 @@", " a", "-b  ", "+b", "+extra", " c"])
    return rehash(d)
def whitespace_with_marker(d):
    d["proposals"][0]["diff"] = eof_marker_diff("src/app.py", "c", 3)
    return rehash(d)
def newline_recipe_changes_code(d):
    d["proposals"][0].update(recipe="final-newline", diff="\n".join(["--- src/app.py", "+++ src/app.py", "@@ -3,1 +3,1 @@", "-c", "\\ No newline at end of file", "+d"]))
    return rehash(d)
def newline_recipe_removes_text(d):
    d["proposals"][0].update(recipe="final-newline", diff="\n".join(["--- src/app.py", "+++ src/app.py", "@@ -1,3 +1,2 @@", " a", "-b", " c"]))
    return rehash(d)
def newline_recipe_whitespace_diff(d):
    d["proposals"][0]["recipe"] = "final-newline"
    return rehash(d)
def newline_recipe_two_hunks(d):
    d["proposals"][0].update(recipe="final-newline", diff="\n".join(["--- src/app.py", "+++ src/app.py", "@@ -1,1 +1,1 @@", "-a", "\\ No newline at end of file", "+a", "@@ -9,1 +9,1 @@", "-c", "\\ No newline at end of file", "+c"]))
    return rehash(d)
def newline_recipe_removal_not_at_end(d):
    d["proposals"][0].update(recipe="final-newline", diff="\n".join(["--- src/app.py", "+++ src/app.py", "@@ -1,3 +1,2 @@", "-", " a", " c"]))
    return rehash(d)
def newline_before_whitespace(d):
    nl = proposal(recipe="final-newline", diff=eof_marker_diff("src/app.py", "c", 3))
    d["proposals"] = [nl, proposal()]
    d["proposal_count"] = 2
    return rehash(d)

RECIPE_MISMATCHES = [code_change, code_change_with_whitespace, whitespace_added, whitespace_lines_inserted,
                     whitespace_with_marker, newline_recipe_changes_code,
                     newline_recipe_removes_text, newline_recipe_whitespace_diff, newline_recipe_two_hunks,
                     newline_recipe_removal_not_at_end, newline_before_whitespace]


@pytest.mark.parametrize("mutate", RECIPE_MISMATCHES, ids=lambda f: f.__name__)
def test_recipe_label_that_does_not_match_the_diff_is_blocked_before_any_git_call(tmp_path, mutate):
    result, fake = run(tmp_path, doc=mutate(make_doc(proposal())))
    assert result.verdict == "BLOCKED" and codes(result) == ["RECIPE_MISMATCH"] and result.stage == "VALIDATE"
    assert fake.calls == [] and app_bytes(fake) == BASE_TEXT.encode()


# ---------------------------------------------------------------------------- apply failure leaves the worktree unchanged
def test_dirty_touched_path_is_blocked_before_building(tmp_path):
    result, fake = run(tmp_path, fake_kw={"dirty": True})
    assert result.verdict == "BLOCKED" and codes(result) == ["DIRTY_WORKTREE"]
    assert "apply" not in fake.subs() and app_bytes(fake) == BASE_TEXT.encode()


def test_file_whose_bytes_differ_from_the_base_blob_is_blocked_even_if_git_says_clean(tmp_path):
    def prepare(root):
        with open(os.path.join(root, "src", "app.py"), "wb") as handle:
            handle.write(b"a\nb  \nc\n# local edit\n")
    result, fake = run(tmp_path, prepare=prepare)
    assert result.verdict == "BLOCKED" and codes(result) == ["DIRTY_WORKTREE"]
    assert "apply" not in fake.subs() and app_bytes(fake) == b"a\nb  \nc\n# local edit\n"


@pytest.mark.parametrize("flag", [b"h src/app.py\0", b"S src/app.py\0", b"s src/app.py\0", b"? src/app.py\0", b""])
def test_assume_unchanged_skip_worktree_and_untracked_paths_are_blocked(tmp_path, flag):
    result, fake = run(tmp_path, fake_kw={"flags": flag})
    assert result.verdict == "BLOCKED" and codes(result) == ["DIRTY_WORKTREE"]
    assert "apply" not in fake.subs()


def test_git_toplevel_that_is_not_the_worktree_is_blocked(tmp_path):
    result, fake = run(tmp_path, fake_kw={"toplevel": str(tmp_path / "elsewhere")})
    assert result.verdict == "BLOCKED" and codes(result) == ["WORKTREE_ROOT_MISMATCH"]
    assert fake.subs() == ["rev-parse"]


def test_git_that_reports_other_git_directories_is_untrusted(tmp_path):
    result, fake = run(tmp_path, fake_kw={"git_dirs": b"../elsewhere/.git\n../elsewhere/.git\n"})
    assert result.verdict == "BLOCKED" and codes(result) == ["UNTRUSTED_GIT_CONFIG"]
    assert "apply" not in fake.subs()


def test_failing_apply_after_a_good_check_is_blocked_and_the_worktree_is_untouched(tmp_path):
    result, fake = run(tmp_path, fake_kw={"apply_rc": 1})
    assert result.verdict == "BLOCKED" and codes(result) == ["GIT_FAILED"] and result.worktree_state == "UNCHANGED"
    assert app_bytes(fake) == BASE_TEXT.encode()


@pytest.mark.parametrize("sub", ["rev-parse", "status", "ls-files", "cat-file", "read-tree", "apply", "write-tree", "commit-tree", "diff"])
def test_git_timeout_is_blocked_and_the_worktree_is_untouched(tmp_path, sub):
    result, fake = run(tmp_path, fake_kw={"timeout_on": sub})
    assert result.verdict == "BLOCKED" and codes(result) == ["GIT_TIMEOUT"] and result.worktree_state == "UNCHANGED"
    assert app_bytes(fake) == BASE_TEXT.encode()
    assert git_dir_files(fake) == ["config"]  # lock released on every path


def test_patches_that_change_nothing_are_blocked(tmp_path):
    result, fake = run(tmp_path, fake_kw={"tree": TREE_BASE})
    assert result.verdict == "BLOCKED" and codes(result) == ["NO_EFFECT"] and app_bytes(fake) == BASE_TEXT.encode()


def test_runner_that_raises_is_blocked_not_propagated(tmp_path):
    def boom(args, **kw):
        raise RuntimeError("x")
    result, _ = run(tmp_path, git_runner=boom)
    assert result.verdict == "BLOCKED" and codes(result) == ["INTERNAL_ERROR"]


def test_runner_returning_garbage_is_blocked(tmp_path):
    result, _ = run(tmp_path, git_runner=lambda args, **kw: (0, b""))
    assert result.verdict == "BLOCKED" and codes(result) == ["GIT_RUNNER_MALFORMED"]


def test_git_object_ids_that_are_not_hex_are_blocked(tmp_path):
    result, _ = run(tmp_path, fake_kw={"head": "not-a-sha"})
    assert result.verdict == "BLOCKED" and codes(result) == ["GIT_OUTPUT_MALFORMED"]


# ---------------------------------------------------------------------------- write failure, rollback, journal
def failing_writer(monkeypatch, *, then, calls_ok=0):
    """Replace _atomic_write: after `calls_ok` good calls the next call writes the candidate, runs `then`, and raises."""
    real = pp._atomic_write
    state = {"n": 0}

    def write(root, rel, data):
        state["n"] += 1
        if state["n"] <= calls_ok or data == BASE_TEXT.encode():
            return real(root, rel, data)
        real(root, rel, data)
        then(root, rel)
        raise OSError("disk went away")

    monkeypatch.setattr(pp, "_atomic_write", write)


def test_write_failure_is_rolled_back_to_the_base_bytes(tmp_path, monkeypatch):
    failing_writer(monkeypatch, then=lambda root, rel: None)
    result, fake = run(tmp_path)
    assert result.verdict == "BLOCKED" and result.worktree_state == "UNCHANGED"
    assert codes(result) == ["MATERIALIZE_FAILED", "ROLLED_BACK"]
    assert result.post_materialize_verified is False
    assert app_bytes(fake) == BASE_TEXT.encode()
    assert git_dir_files(fake) == ["config"]  # journal removed after a clean rollback


def test_rollback_conflict_leaves_a_foreign_change_and_keeps_the_journal(tmp_path, monkeypatch):
    def tamper(root, rel):
        with open(os.path.join(root, rel), "wb") as handle:
            handle.write(b"somebody else wrote this\n")
    failing_writer(monkeypatch, then=tamper)
    result, fake = run(tmp_path)
    assert result.verdict == "BLOCKED" and result.worktree_state == "UNKNOWN"
    assert ("ROLLBACK_CONFLICT", shown("src/app.py")) in result.reasons
    assert app_bytes(fake) == b"somebody else wrote this\n"  # never overwritten
    assert "vst-u5-2.journal" in git_dir_files(fake) and "vst-u5-2.lock" not in git_dir_files(fake)


def test_journal_left_behind_blocks_the_next_call(tmp_path, monkeypatch):
    def tamper(root, rel):
        with open(os.path.join(root, rel), "wb") as handle:
            handle.write(b"x")
    failing_writer(monkeypatch, then=tamper)
    run(tmp_path)
    monkeypatch.undo()
    result, fake = run(tmp_path)  # make_isolation rewrites the files but keeps .git, so the journal is still there
    assert result.verdict == "BLOCKED" and codes(result) == ["JOURNAL_PRESENT"]


def test_keyboard_interrupt_during_the_write_rolls_back_and_is_re_raised(tmp_path, monkeypatch):
    real = pp._atomic_write
    state = {"n": 0}

    def write(root, rel, data):
        state["n"] += 1
        real(root, rel, data)
        if data != BASE_TEXT.encode():
            raise KeyboardInterrupt

    monkeypatch.setattr(pp, "_atomic_write", write)
    isolation = make_isolation(tmp_path)
    fake = FakeGit(isolation.worktree_root)
    with pytest.raises(KeyboardInterrupt):
        pp.apply_proposals(document=make_doc(proposal()), manifest_sha256=MANIFEST, base_head=BASE, proposal_base_head=BASE,
                           allowed_paths=ALLOWED, protected_paths=(), isolation=isolation, git_runner=fake)
    assert app_bytes(fake) == BASE_TEXT.encode()
    assert git_dir_files(fake) == ["config"]  # rolled back, journal and lock gone


def test_worktree_that_is_edited_between_the_gate_and_the_write_is_blocked_and_the_edit_survives(tmp_path, monkeypatch):
    real_gate = pp.wg.gate_worker_change
    state = {"n": 0}

    def gate(**kw):
        state["n"] += 1
        result = real_gate(**kw)
        if state["n"] == 2:  # after the real-diff gate, before the re-check and the write
            with open(os.path.join(kw["isolation"].worktree_root, "src", "app.py"), "wb") as handle:
                handle.write(b"edited meanwhile\n")
        return result

    monkeypatch.setattr(pp.wg, "gate_worker_change", gate)
    result, fake = run(tmp_path)
    assert result.verdict == "BLOCKED" and codes(result) == ["DIRTY_WORKTREE"] and result.stage == "MATERIALIZE"
    assert app_bytes(fake) == b"edited meanwhile\n"  # not overwritten
    assert git_dir_files(fake) == ["config"]


def test_second_call_after_success_is_blocked_dirty_and_changes_nothing(tmp_path):
    result, fake = run(tmp_path)
    assert result.verdict == "ACCEPTED"
    again = pp.apply_proposals(document=make_doc(proposal()), manifest_sha256=MANIFEST, base_head=BASE, proposal_base_head=BASE,
                               allowed_paths=ALLOWED, protected_paths=(), isolation=make_isolation_nowrite(fake.root),
                               git_runner=FakeGit(fake.root, base_blobs={"src/app.py": BASE_TEXT.encode()}))
    assert again.verdict == "BLOCKED" and codes(again) == ["DIRTY_WORKTREE"]
    assert app_bytes(fake) == CAND_TEXT.encode()


def make_isolation_nowrite(root):
    """An isolation context for an existing fake worktree, without rewriting its files."""
    def lstat(path):
        info = os.lstat(path)
        return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=getattr(info, "st_file_attributes", 0))
    return wg.IsolationContext(root, os.path.join(os.path.dirname(root), "main"), False, BASE, None, lstat=lstat)


# ---------------------------------------------------------------------------- lock and untrusted repository
def test_lock_that_is_present_blocks_and_is_left_alone(tmp_path):
    def prepare(root):
        with open(os.path.join(root, ".git", "vst-u5-2.lock"), "wb") as handle:
            handle.write(b"123")
    result, fake = run(tmp_path, prepare=prepare)
    assert result.verdict == "BLOCKED" and codes(result) == ["WORKTREE_LOCKED"]
    assert "vst-u5-2.lock" in git_dir_files(fake) and fake.calls == []
    assert app_bytes(fake) == BASE_TEXT.encode()


@pytest.mark.parametrize("config", [
    b'[filter "lfs"]\n\tclean = evil\n', b"[include]\n\tpath = ../x\n", b'[includeIf "gitdir:/"]\n\tpath = x\n',
    b"[core]\n\tattributesFile = x\n", b"[core]\n\thooksPath = x\n", b"[core]\n\tfsmonitor = evil\n",
    b"[core]\n\tworktree = ..\n", b"[extensions]\n\tworktreeConfig = true\n", b'[diff "x"]\n\ttextconv = evil\n',
    b"[core]\n\tTextConv = evil\n", b"[attr]\n\ttree = HEAD\n",
])
def test_hostile_repository_config_is_untrusted(tmp_path, config):
    def prepare(root):
        with open(os.path.join(root, ".git", "config"), "ab") as handle:
            handle.write(config)
    result, fake = run(tmp_path, prepare=prepare)
    assert result.verdict == "BLOCKED" and codes(result) == ["UNTRUSTED_GIT_CONFIG"]
    assert fake.calls == [] and app_bytes(fake) == BASE_TEXT.encode()


def _worktree_config(root):
    with open(os.path.join(root, ".git", "config.worktree"), "wb") as handle:
        handle.write(b'[filter "x"]\n\tsmudge = evil\n')


def _info_attributes(root):
    os.makedirs(os.path.join(root, ".git", "info"), exist_ok=True)
    with open(os.path.join(root, ".git", "info", "attributes"), "wb") as handle:
        handle.write(b"*.py filter=evil\n")


@pytest.mark.parametrize("prepare", [_worktree_config, _info_attributes], ids=["config.worktree", "info/attributes"])
def test_worktree_level_config_and_info_attributes_are_scanned(tmp_path, prepare):
    result, fake = run(tmp_path, prepare=prepare)
    assert result.verdict == "BLOCKED" and codes(result) == ["UNTRUSTED_GIT_CONFIG"] and fake.calls == []


@pytest.mark.parametrize("attributes", [
    b"*.py filter=lfs\n", b"*.py -filter\n", b"*.py ident\n", b"*.py working-tree-encoding=UTF-16\n", b"*.py crlf\n",
    b"*.py -crlf\n", b"*.py export-subst\n", b"*.py diff=evil\n", b"*.py merge=union\n", b"*.py merge=evil\n",
    b"*.py text eol=lf filter=lfs\n", b"*.py FILTER=lfs\n", b"[attr]x filter=lfs\n", b"[attr]x ident\n",
    b'"a b.py" ident\n', b"*.py\tident\n", b"*.py text=yes\n", b"*.py text=input\n", b"*.py eol\n", b"*.py eol=cr\n",
    b"*.py eol=LF\n", b'"a b.py ident\n', b"\xef\xbb\xbf*.py filter=lfs\n",
    b"*.py -text=auto\n", b"*.py !text=auto\n", b"*.py -eol=lf\n", b"*.py !filter\n", b"*.py -ident\n",
    b"*.py -working-tree-encoding\n", b"*.py -export-subst\n", b"*.py !crlf\n",
    b"*.py text\r\n*.py filter=lfs\r\n", b"* text=auto\n*.md text eol=lf\n*.py ident\n",
    b"*.py\rfilter=lfs\n", b"*.py\x0b ident\n", b"*.py\xc2\x85 filter=lfs\n", b"\x0b# filter=lfs\n",
    b"*.py\xe2\x80\xa8ident\n", b'"*\\q" ident\n', b'"x\\q filter=a" text\n', b'"a\\"b.py" text\n',
    b'"a\\"b.py" ident\n', b'"a\\\\" ident\n', b"# note\n\n  \n*.py text\n*.py diff=evil\n",
])
def test_gitattributes_that_run_code_or_rewrite_content_are_untrusted(tmp_path, attributes):
    def prepare(root):
        with open(os.path.join(root, "src", ".gitattributes"), "wb") as handle:
            handle.write(attributes)
    result, fake = run(tmp_path, prepare=prepare)
    assert result.verdict == "BLOCKED" and codes(result) == ["UNTRUSTED_GIT_CONFIG"]
    assert fake.calls == []


@pytest.mark.parametrize("attributes", [
    b"*.py text\n", b"* text=auto\n", b"*.py eol=crlf\n", b"*.py eol=lf\n", b"*.py -text\n", b"*.py !text\n",
    b"*.py -eol\n", b"*.py !eol\n", b"*.md text eol=lf\n", b"[attr]x text\n", b'"a b.py" text eol=lf\n',
    b"* text=auto\n*.md text eol=lf\n*.py text eol=lf\n", b"*.py -diff -merge\n",
    b"*.py diff merge\n", b"*.py binary\n", b"ident text\n", b"filter text eol=lf\n", b"*.py text\r\n*.md eol=lf\r\n",
    b"# filter=lfs\n\n  \n*.py text\n", b"\xef\xbb\xbf*.py text eol=lf\n",
])
def test_gitattributes_with_only_line_ending_attributes_are_accepted(tmp_path, attributes):
    def prepare(root):
        with open(os.path.join(root, "src", ".gitattributes"), "wb") as handle:
            handle.write(attributes)
    result, _ = run(tmp_path, prepare=prepare)
    assert result.verdict == "ACCEPTED"


def _root_eol_attributes(root):
    with open(os.path.join(root, ".gitattributes"), "wb") as handle:
        handle.write(b"* text=auto\n*.py text eol=lf\n")


def _info_eol_attributes(root):
    os.makedirs(os.path.join(root, ".git", "info"), exist_ok=True)
    with open(os.path.join(root, ".git", "info", "attributes"), "wb") as handle:
        handle.write(b"*.py text eol=crlf\n")


def _root_eol_nested_filter(root):
    _root_eol_attributes(root)
    with open(os.path.join(root, "src", ".gitattributes"), "wb") as handle:
        handle.write(b"*.py filter=lfs\n")


def _root_filter_nested_eol(root):
    with open(os.path.join(root, ".gitattributes"), "wb") as handle:
        handle.write(b"*.py filter=lfs\n")
    with open(os.path.join(root, "src", ".gitattributes"), "wb") as handle:
        handle.write(b"*.py text\n")


@pytest.mark.parametrize("prepare", [_root_eol_attributes, _info_eol_attributes], ids=["root", "info/attributes"])
def test_line_ending_attributes_are_accepted_in_every_scanned_location(tmp_path, prepare):
    result, _ = run(tmp_path, prepare=prepare)
    assert result.verdict == "ACCEPTED"


@pytest.mark.parametrize("prepare", [_root_eol_nested_filter, _root_filter_nested_eol], ids=["nested-filter", "root-filter"])
def test_a_hostile_attribute_in_any_level_blocks_even_beside_accepted_eol_attributes(tmp_path, prepare):
    result, fake = run(tmp_path, prepare=prepare)
    assert result.verdict == "BLOCKED" and codes(result) == ["UNTRUSTED_GIT_CONFIG"] and fake.calls == []


def test_harmless_gitattributes_and_comments_are_accepted(tmp_path):
    def prepare(root):
        with open(os.path.join(root, ".gitattributes"), "wb") as handle:
            handle.write(b"# text files are fine here\n*.png binary\n")
    result, _ = run(tmp_path, prepare=prepare)
    assert result.verdict == "ACCEPTED"


def test_git_entry_that_is_not_a_directory_or_pointer_is_untrusted(tmp_path):
    def prepare(root):
        import shutil
        shutil.rmtree(os.path.join(root, ".git"))
        with open(os.path.join(root, ".git"), "wb") as handle:
            handle.write(b"not a pointer\n")
    result, fake = run(tmp_path, prepare=prepare)
    assert result.verdict == "BLOCKED" and codes(result) == ["UNTRUSTED_GIT_CONFIG"] and fake.calls == []


def test_pointer_file_outside_the_expected_repository_is_untrusted(tmp_path):
    other = tmp_path / "other-repo-gitdir"
    other.mkdir()
    (tmp_path / "unrelated").mkdir()
    (other / "commondir").write_bytes(b"../unrelated\n")

    def prepare(root):
        import shutil
        shutil.rmtree(os.path.join(root, ".git"))
        with open(os.path.join(root, ".git"), "wb") as handle:
            handle.write(f"gitdir: {other}\n".encode())
    result, fake = run(tmp_path, prepare=prepare)
    assert result.verdict == "BLOCKED" and codes(result) == ["UNTRUSTED_GIT_CONFIG"] and fake.calls == []


# ---------------------------------------------------------------------------- default runner and git lookup
def test_default_runner_uses_shell_false_absolute_git_cwd_env_timeout_and_reports_timeout(tmp_path, monkeypatch):
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"], seen["kw"] = argv, kw
        return SimpleNamespace(returncode=0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(pp, "find_git", lambda exclude=None: "C:/git/git.exe")
    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    env = {"PATH": "C:/git", "X": "1"}
    result = pp.default_git_runner(["status"], cwd=str(tmp_path), env=env, stdin=b"in", timeout=3.0)
    assert result == pp.GitResult(0, b"ok", b"")
    assert seen["argv"] == ["C:/git/git.exe", "status"]
    assert seen["kw"]["shell"] is False and seen["kw"]["cwd"] == str(tmp_path)
    assert seen["kw"]["env"] == env and seen["kw"]["timeout"] == 3.0 and seen["kw"]["input"] == b"in"

    def timed_out(argv, **kw):
        raise pp.subprocess.TimeoutExpired(argv, 3.0)

    monkeypatch.setattr(pp.subprocess, "run", timed_out)
    assert pp.default_git_runner(["status"], cwd=str(tmp_path), env=env).timed_out is True
    monkeypatch.setattr(pp, "find_git", lambda exclude=None: None)
    assert pp.default_git_runner(["status"], cwd=str(tmp_path), env=env).returncode == -1


def test_find_git_ignores_relative_path_entries_and_folders_inside_the_exclusion(tmp_path, monkeypatch):
    inside = tmp_path / "wt" / "bin"
    inside.mkdir(parents=True)
    (inside / "git.exe").write_bytes(b"x")
    (inside / "git").write_bytes(b"x")
    outside = tmp_path / "tools"
    outside.mkdir()
    (outside / "git.exe").write_bytes(b"x")
    (outside / "git").write_bytes(b"x")
    monkeypatch.setenv("PATH", os.pathsep.join(["bin", ".", "", str(inside), str(outside)]))
    assert pp.find_git(exclude=str(tmp_path / "wt")) in (str(outside / "git.exe"), str(outside / "git"))
    monkeypatch.setenv("PATH", os.pathsep.join(["bin", ".", ""]))
    assert pp.find_git() is None


def test_build_git_env_is_fixed_and_minimal(monkeypatch, tmp_path):
    monkeypatch.setenv("SOME_TOKEN", "secret")
    env = pp.build_git_env(str(tmp_path), index_file="idx", objects="obj", alternates="alt")
    assert "SOME_TOKEN" not in env
    assert (env["GIT_INDEX_FILE"], env["GIT_OBJECT_DIRECTORY"], env["GIT_ALTERNATE_OBJECT_DIRECTORIES"]) == ("idx", "obj", "alt")
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull and env["HOME"] == str(tmp_path)
    plain = pp.build_git_env(str(tmp_path))
    assert not {"GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"} & set(plain)


# ---------------------------------------------------------------------------- share of proposal versus model
def test_share_counts_added_plus_deleted_lines_per_origin_with_exact_fractions():
    # proposal: (2+1) + (1+0) = 4 lines; model: (5+3) + (4+0) = 12 lines; total 16
    share = pp.change_origin_share({"src/a.py": [(2, 1), (1, 0)]}, {"src/a.py": [(5, 3)], "src/b.py": [(4, 0)]})
    assert share["proposal"] == {"added": 3, "deleted": 1, "lines": 4, "hunks": 2, "files": ["src/a.py"]}
    assert share["model"] == {"added": 9, "deleted": 3, "lines": 12, "hunks": 2, "files": ["src/a.py", "src/b.py"]}
    assert share["total_lines"] == 16
    assert share["proposal_fraction"] == 0.25 and share["model_fraction"] == 0.75
    assert share["files_touched_by_both"] == ["src/a.py"]
    assert share["model_only_paths"] == ["src/b.py"] and share["proposal_only_paths"] == []
    assert share["schema"] == "vst-change-origin-share-v1"


def test_share_with_a_pure_proposal_change_and_a_pure_model_change():
    only_proposal = pp.change_origin_share({"x.py": [(3, 1)]}, {})
    assert (only_proposal["proposal_fraction"], only_proposal["model_fraction"]) == (1.0, 0.0)
    assert only_proposal["model_only_paths"] == [] and only_proposal["proposal_only_paths"] == ["x.py"]
    only_model = pp.change_origin_share({}, {"y.py": [(2, 0)]})
    assert (only_model["proposal_fraction"], only_model["model_fraction"]) == (0.0, 1.0)
    assert only_model["model_only_paths"] == ["y.py"]


def test_share_of_an_empty_change_has_no_fractions():
    share = pp.change_origin_share({}, {})
    assert share["total_lines"] == 0 and share["proposal_fraction"] is None and share["model_fraction"] is None


def test_share_matches_paths_case_insensitively_so_a_case_variant_is_not_model_only():
    share = pp.change_origin_share({"src/a.py": [(1, 0)]}, {"SRC/A.PY": [(1, 0)]})
    assert share["files_touched_by_both"] == ["src/a.py"] and share["model_only_paths"] == []


def test_share_does_not_double_count_a_shared_file():
    share = pp.change_origin_share({"a.py": [(1, 1)]}, {"a.py": [(1, 1)]})
    assert share["total_lines"] == 4 and share["proposal_fraction"] == 0.5


@pytest.mark.parametrize("proposal_side, model_side", [
    ({"a.py": [(-1, 0)]}, {}), ({"a.py": [(True, 0)]}, {}), ({"a.py": [(1.5, 0)]}, {}), ({"a.py": [(1,)]}, {}),
    ({"a.py": "text"}, {}), ({"": [(1, 0)]}, {}), ({1: [(1, 0)]}, {}), ([("a.py", [(1, 0)])], {}), ({}, None),
])
def test_share_rejects_invalid_input(proposal_side, model_side):
    with pytest.raises(ValueError):
        pp.change_origin_share(proposal_side, model_side)


def test_hunk_counts_come_from_the_real_diff_per_hunk():
    diff = ("diff --git a/src/a.py b/src/a.py\nindex 1111111..2222222 100644\n--- a/src/a.py\n+++ b/src/a.py\n"
            "@@ -1,4 +1,3 @@ def f():\n keep\n-x\n-y\n+z\n end\n"
            "@@ -10,2 +11,4 @@\n m\n+n\n+o\n p\n"
            "diff --git a/src/b.py b/src/b.py\nindex 3333333..4444444 100644\n--- a/src/b.py\n+++ b/src/b.py\n"
            "@@ -1 +1 @@\n-q\n+r\n").encode()
    assert pp.hunk_counts_from_diff(diff) == {"src/a.py": [(1, 2), (2, 0)], "src/b.py": [(1, 1)]}


def test_hunk_counts_reject_unparsable_diffs_and_renames():
    with pytest.raises(pp.ProposalError):
        pp.hunk_counts_from_diff(b"not a diff")
    with pytest.raises(pp.ProposalError):
        pp.hunk_counts_from_diff(b"diff --git a/a.py b/b.py\nsimilarity index 100%\nrename from a.py\nrename to b.py\n")


def test_applied_proposal_hunks_feed_the_share_record(tmp_path):
    result, _ = run(tmp_path)
    share = pp.change_origin_share(result.hunks_by_file, {"src/model_only.py": [(7, 1)]})
    # proposal 1+1 = 2 lines, model 7+1 = 8 lines, total 10
    assert share["proposal"]["lines"] == 2 and share["model"]["lines"] == 8
    assert share["proposal_fraction"] == 0.2 and share["model_only_paths"] == ["src/model_only.py"]


def test_run_record_for_a_proposal_plus_a_model_change_on_another_path(tmp_path):
    result, _ = run(tmp_path, doc=make_doc(proposal(), status="PARTIAL", uncovered=["LANGUAGE_NOT_INDEXED: web/a.js"]))
    overrides = [{"path": "src/x.py", "reason": REASON, "authorized_by": AUTHOR}]
    record = pp.build_run_record(result, {"src/model.py": [(6, 2)]}, overrides)
    json.dumps(record)  # JSON-able
    # proposal: 1 added + 1 deleted = 2 lines; model: 6 + 2 = 8 lines; total 10
    assert (record["proposal_lines"], record["model_lines"], record["total_lines"]) == (2, 8, 10)
    assert (record["proposal_fraction"], record["model_fraction"]) == (0.2, 0.8)
    assert record["files_touched_by_both"] == [] and record["model_only_paths"] == ["src/model.py"]
    assert record["verdict"] == "ACCEPTED" and record["partial"] is True and record["post_materialize_verified"] is True
    assert record["patched_paths"] == ["src/app.py"] and record["overrides"] == overrides
    assert record["report_sha256"] == result.report_sha256 and record["candidate_head"] == CAND
    assert record["schema"] == "vst-patch-run-record-v1"
    assert record["applied"] is True and record["attempted_proposal_lines"] == 2
    assert record["attempted_proposal_hunks"] == {"src/app.py": [[1, 1]]}


MODEL_ONLY = {"src/model.py": [(3, 0)]}  # 3 model lines


def assert_nothing_applied(result, record):
    # attempted: one hunk, 1 added + 1 deleted = 2 lines; applied: none; model 3 lines, so total 3
    assert result.hunks_by_file is None
    assert result.attempted_hunks_by_file == {"src/app.py": [(1, 1)]}
    assert record["applied"] is False
    assert (record["proposal_lines"], record["model_lines"], record["total_lines"]) == (0, 3, 3)
    assert (record["proposal_fraction"], record["model_fraction"]) == (0.0, 1.0)
    assert record["attempted_proposal_lines"] == 2 and record["attempted_proposal_hunks"] == {"src/app.py": [[1, 1]]}
    assert record["files_touched_by_both"] == []
    assert result.to_dict()["hunks_by_file"] is None and result.to_dict()["attempted_hunks_by_file"] == {"src/app.py": [[1, 1]]}


def test_run_record_counts_no_applied_lines_when_blocked_after_the_gate_but_before_the_write(tmp_path, monkeypatch):
    real_gate = pp.wg.gate_worker_change
    state = {"n": 0}

    def gate(**kw):
        state["n"] += 1
        outcome = real_gate(**kw)
        if state["n"] == 2:  # gate accepted the real diff; the file is edited before the re-check
            with open(os.path.join(kw["isolation"].worktree_root, "src", "app.py"), "wb") as handle:
                handle.write(b"edited meanwhile\n")
        return outcome

    monkeypatch.setattr(pp.wg, "gate_worker_change", gate)
    result, _ = run(tmp_path)
    assert result.verdict == "BLOCKED" and codes(result) == ["DIRTY_WORKTREE"] and result.post_materialize_verified is None
    assert_nothing_applied(result, pp.build_run_record(result, MODEL_ONLY))


def test_run_record_counts_no_applied_lines_after_a_failed_write_that_was_rolled_back(tmp_path, monkeypatch):
    failing_writer(monkeypatch, then=lambda root, rel: None)
    result, fake = run(tmp_path)
    assert result.verdict == "BLOCKED" and codes(result) == ["MATERIALIZE_FAILED", "ROLLED_BACK"]
    assert result.worktree_state == "UNCHANGED" and app_bytes(fake) == BASE_TEXT.encode()
    assert_nothing_applied(result, pp.build_run_record(result, MODEL_ONLY))


def test_run_record_counts_no_applied_lines_after_a_rollback_conflict(tmp_path, monkeypatch):
    def tamper(root, rel):
        with open(os.path.join(root, rel), "wb") as handle:
            handle.write(b"somebody else wrote this\n")
    failing_writer(monkeypatch, then=tamper)
    result, _ = run(tmp_path)
    assert result.verdict == "BLOCKED" and result.worktree_state == "UNKNOWN"
    assert ("ROLLBACK_CONFLICT", shown("src/app.py")) in result.reasons
    assert_nothing_applied(result, pp.build_run_record(result, MODEL_ONLY))


def test_run_record_counts_no_applied_lines_when_the_journal_cannot_be_created(tmp_path, monkeypatch):
    real_open = os.open

    def deny_journal(path, flags, *a, **kw):
        if str(path).endswith("vst-u5-2.journal"):
            raise PermissionError("journal denied")
        return real_open(path, flags, *a, **kw)

    monkeypatch.setattr(pp.os, "open", deny_journal)
    result, fake = run(tmp_path)
    assert result.verdict == "BLOCKED" and codes(result) == ["JOURNAL_UNAVAILABLE"]
    assert app_bytes(fake) == BASE_TEXT.encode()
    assert_nothing_applied(result, pp.build_run_record(result, MODEL_ONLY))


def test_run_record_of_an_accepted_run_still_attributes_the_applied_lines(tmp_path):
    result, _ = run(tmp_path)
    record = pp.build_run_record(result, {"src/b.py": [(4, 0)]})
    # applied 1 + 1 = 2 proposal lines, model 4 lines, total 6
    assert (record["proposal_lines"], record["model_lines"], record["total_lines"]) == (2, 4, 6)
    assert record["proposal_fraction"] == 2 / 6 and record["model_fraction"] == 4 / 6
    assert result.hunks_by_file == result.attempted_hunks_by_file == {"src/app.py": [(1, 1)]}


def test_run_record_ignores_hunks_of_a_result_that_is_not_verified_accepted():
    import dataclasses
    forged = pp.ApplyResult("BLOCKED", (), "MATERIALIZE", "UNKNOWN", hunks_by_file={"a.py": [(5, 5)]},
                            attempted_hunks_by_file={"a.py": [(5, 5)]})
    assert pp.build_run_record(forged, {})["proposal_lines"] == 0
    unverified = dataclasses.replace(forged, verdict="ACCEPTED", post_materialize_verified=None)
    record = pp.build_run_record(unverified, {})
    assert record["proposal_lines"] == 0 and record["attempted_proposal_lines"] == 10


def test_run_record_of_a_refused_proposal_has_no_proposal_lines(tmp_path):
    result, _ = run(tmp_path, proposal_base_head=OTHER_HEAD)
    record = pp.build_run_record(result, {"src/model.py": [(3, 0)]})
    assert record["verdict"] == "REFUSED" and record["proposal_lines"] == 0 and record["proposal_fraction"] == 0.0
    with pytest.raises(ValueError):
        pp.build_run_record("not a result", {})


# ---------------------------------------------------------------------------- model may not override a proposal
def applied(tmp_path, *paths):
    """A real ApplyResult whose validated document patches `paths` (stage VALIDATE data only)."""
    result, _ = run(tmp_path, doc=make_doc(proposal()), proposal_base_head=OTHER_HEAD)  # REFUSED, but carries the document facts
    import dataclasses
    return dataclasses.replace(result, patched_paths=tuple(paths))


def test_model_change_on_a_path_with_a_proposed_patch_is_refused(tmp_path):
    verdict = pp.check_model_changes(apply_result=applied(tmp_path, "src/app.py"), model_changed_paths=["src/app.py", "src/new.py"])
    assert verdict.verdict == "REFUSED"
    assert verdict.reasons == (("MODEL_OVERRIDES_PROPOSAL", shown("src/app.py")),)
    assert verdict.overrides == () and verdict.model_only_paths == ("src/new.py",)


def test_patched_paths_are_taken_from_the_apply_result_not_from_the_caller(tmp_path):
    result, _ = run(tmp_path, proposal_base_head=OTHER_HEAD)
    verdict = pp.check_model_changes(apply_result=result, model_changed_paths=["src/app.py"])
    assert verdict.verdict == "REFUSED"  # the document patches src/app.py even though the apply was refused


def test_apply_result_without_a_validated_document_and_double_binding_are_blocked(tmp_path):
    bad, _ = run(tmp_path, doc=make_doc(proposal(), schema_version="g6.patch.v2"))
    assert pp.check_model_changes(apply_result=bad, model_changed_paths=["a.py"]).verdict == "BLOCKED"
    assert pp.check_model_changes(apply_result="x", model_changed_paths=["a.py"]).verdict == "BLOCKED"
    assert pp.check_model_changes(model_changed_paths=["a.py"]).verdict == "BLOCKED"
    both = pp.check_model_changes(apply_result=applied(tmp_path, "a.py"), proposal_patched_paths=["a.py"], model_changed_paths=["a.py"])
    assert both.verdict == "BLOCKED"


def test_model_change_on_a_case_variant_of_a_patched_path_is_refused():
    verdict = pp.check_model_changes(proposal_patched_paths=["src/app.py"], model_changed_paths=["SRC/App.py"])
    assert verdict.verdict == "REFUSED" and verdict.reasons[0][0] == "MODEL_OVERRIDES_PROPOSAL"


def test_model_may_write_paths_with_no_proposed_patch():
    verdict = pp.check_model_changes(proposal_patched_paths=["src/app.py"], model_changed_paths=["src/other.py", "docs/x.md"])
    assert verdict.verdict == "ACCEPTED"
    assert verdict.reasons == (("NO_CONFLICT", "model paths avoid every proposed patch"),)
    assert verdict.model_only_paths == ("docs/x.md", "src/other.py")


def test_flagged_only_path_from_the_proposal_is_not_a_patched_path(tmp_path):
    doc = make_doc(proposal(), proposal(file="src/other.py", recipe="unused-import", changed=False, detail="Remove unused import 'os'"))
    result, _ = run(tmp_path, doc=doc)
    verdict = pp.check_model_changes(apply_result=result, model_changed_paths=["src/other.py"])
    assert verdict.verdict == "ACCEPTED"


def test_explicit_override_with_reason_and_author_is_recorded_and_not_silent():
    verdict = pp.check_model_changes(
        proposal_patched_paths=["src/app.py"], model_changed_paths=["src/app.py"],
        override_reasons={"src/app.py": "  " + REASON + "  "}, authorized_by="  " + AUTHOR + " ")
    assert verdict.verdict == "ACCEPTED"
    expected = {"path": "src/app.py", "reason": REASON, "authorized_by": AUTHOR}
    assert verdict.overrides == (expected,)
    assert verdict.reasons == (("MODEL_OVERRIDE_RECORDED", shown("src/app.py")),)
    assert verdict.to_dict()["overrides"] == [expected]


@pytest.mark.parametrize("author", [None, "", "   ", 5, "x" * 101, "bad\x00name", "zero\u200bwidth", "line\u2028sep", "tab\tin"])
def test_override_without_a_valid_authorizer_does_not_unlock_the_path(author):
    verdict = pp.check_model_changes(proposal_patched_paths=["src/app.py"], model_changed_paths=["src/app.py"],
                                     override_reasons={"src/app.py": REASON}, authorized_by=author)
    assert verdict.verdict == "REFUSED" and verdict.reasons[0][0] == "OVERRIDE_AUTHORIZATION_MISSING"
    assert verdict.overrides == ()


@pytest.mark.parametrize("reason", ["", "   ", "short", "123456789", None, 5, "x" * 501, "bad\x00reason here", "line\nbreak in reason",
                                    "zero\u200bwidth reason", "para\u2029graph reason", "ctrl\x1breason here"])
def test_invalid_override_reason_does_not_unlock_the_path(reason):
    verdict = pp.check_model_changes(proposal_patched_paths=["src/app.py"], model_changed_paths=["src/app.py"],
                                     override_reasons={"src/app.py": reason}, authorized_by=AUTHOR)
    assert verdict.verdict == "REFUSED" and verdict.reasons[0][0] == "OVERRIDE_REASON_INVALID" and verdict.overrides == ()


@pytest.mark.parametrize("length, ok", [(9, False), (10, True), (500, True), (501, False)])
def test_override_reason_length_bounds_are_inclusive(length, ok):
    verdict = pp.check_model_changes(proposal_patched_paths=["src/app.py"], model_changed_paths=["src/app.py"],
                                     override_reasons={"src/app.py": "r" * length}, authorized_by=AUTHOR)
    assert (verdict.verdict == "ACCEPTED") is ok


def test_number_of_overrides_is_capped():
    paths = [f"src/f{i}.py" for i in range(pp.MAX_OVERRIDES + 1)]
    verdict = pp.check_model_changes(proposal_patched_paths=paths, model_changed_paths=paths,
                                     override_reasons={p: REASON for p in paths}, authorized_by=AUTHOR)
    assert verdict.verdict == "BLOCKED" and verdict.reasons[0][0] == "OVERRIDE_CAP_EXCEEDED"
    ok = paths[:pp.MAX_OVERRIDES]
    assert pp.check_model_changes(proposal_patched_paths=ok, model_changed_paths=ok,
                                  override_reasons={p: REASON for p in ok}, authorized_by=AUTHOR).verdict == "ACCEPTED"


def test_override_covers_only_the_named_path():
    verdict = pp.check_model_changes(proposal_patched_paths=["src/a.py", "src/b.py"], model_changed_paths=["src/a.py", "src/b.py"],
                                     override_reasons={"src/a.py": REASON}, authorized_by=AUTHOR)
    assert verdict.verdict == "REFUSED"
    assert verdict.reasons == (("MODEL_OVERRIDES_PROPOSAL", shown("src/b.py")),)
    assert verdict.overrides == ({"path": "src/a.py", "reason": REASON, "authorized_by": AUTHOR},)


def test_override_for_a_path_without_conflict_is_blocked():
    verdict = pp.check_model_changes(proposal_patched_paths=["src/a.py"], model_changed_paths=["src/c.py"],
                                     override_reasons={"src/c.py": REASON}, authorized_by=AUTHOR)
    assert verdict.verdict == "BLOCKED" and verdict.reasons == (("OVERRIDE_WITHOUT_CONFLICT", shown("src/c.py")),)


@pytest.mark.parametrize("patched, model, overrides", [
    ("src/a.py", ["x.py"], None), (["a.py"], "a.py", None), (["a.py"], [1], None), (["a.py"], ["../a.py"], None),
    (["a.py"], ["a.py"], ["a.py"]), (None, ["a.py"], None),
])
def test_malformed_model_check_input_is_blocked(patched, model, overrides):
    verdict = pp.check_model_changes(proposal_patched_paths=patched, model_changed_paths=model, override_reasons=overrides)
    assert verdict.verdict == "BLOCKED"


# ---------------------------------------------------------------------------- real git (skipped without git)
GIT = pp.find_git()
needs_git = pytest.mark.skipif(GIT is None, reason="no git executable on an absolute PATH entry")


def git_env(home):
    env = {"PATH": os.path.dirname(GIT), "HOME": str(home), "USERPROFILE": str(home), "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}
    if os.environ.get("SystemRoot"):
        env["SystemRoot"] = os.environ["SystemRoot"]
    return env


def sh(root, home, *args):
    done = subprocess.run([GIT, *args], cwd=str(root), env=git_env(home), capture_output=True, check=True)
    return done.stdout.decode().strip()


def make_repo(tmp_path, files):
    root = tmp_path / "worktree"
    root.mkdir()
    (tmp_path / "main").mkdir()
    sh(root, tmp_path, "init", "-q")
    sh(root, tmp_path, "config", "user.name", "t")
    sh(root, tmp_path, "config", "user.email", "t@example.invalid")
    sh(root, tmp_path, "config", "core.autocrlf", "false")
    for rel, data in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    sh(root, tmp_path, "add", "-A")
    sh(root, tmp_path, "commit", "-q", "-m", "base")
    head = sh(root, tmp_path, "rev-parse", "HEAD")

    def lstat(path):
        info = os.lstat(path)
        return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=getattr(info, "st_file_attributes", 0))

    return root, head, wg.IsolationContext(str(root), str(tmp_path / "main"), False, head, None, lstat=lstat)


def real_apply(root, head, isolation, doc, *, base_head=None, allowed=("pkg/m.py",)):
    return pp.apply_proposals(document=doc, manifest_sha256=MANIFEST, base_head=base_head or head, proposal_base_head=head,
                              allowed_paths=allowed, protected_paths=(), isolation=isolation)


def expected_strip(text):
    return "".join(line.rstrip(" \t") + "\n" for line in text.splitlines())


OLD = "def f():\n    return 1  \n\nx = 2\t\n"


@needs_git
def test_real_git_valid_proposal_is_applied_with_exactly_the_expected_bytes(tmp_path):
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": OLD.encode()})
    doc = make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", OLD, expected_strip(OLD))))
    result = real_apply(root, head, iso, doc)
    assert result.verdict == "ACCEPTED", result.reasons
    assert (root / "pkg" / "m.py").read_bytes() == b"def f():\n    return 1\n\nx = 2\n"
    assert sh(root, tmp_path, "rev-parse", "HEAD") == head  # HEAD not moved
    assert sh(root, tmp_path, "status", "--porcelain") == "M pkg/m.py"  # unstaged working-file change only
    assert "vst-u5-2.lock" not in os.listdir(root / ".git") and "vst-u5-2.journal" not in os.listdir(root / ".git")


@needs_git
def test_real_git_candidate_objects_do_not_land_in_the_repository(tmp_path):
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": OLD.encode()})
    result = real_apply(root, head, iso, make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", OLD, expected_strip(OLD)))))
    assert result.verdict == "ACCEPTED", result.reasons
    done = subprocess.run([GIT, "cat-file", "-e", result.candidate_head], cwd=str(root), env=git_env(tmp_path), capture_output=True)
    assert done.returncode != 0  # the dangling candidate commit was written to the scratch object directory only


@needs_git
def test_real_git_stale_head_leaves_bytes_unchanged(tmp_path):
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": OLD.encode()})
    (root / "pkg" / "m.py").write_bytes(b"def f():\n    return 9\n")
    sh(root, tmp_path, "commit", "-q", "-a", "-m", "second")
    newer = sh(root, tmp_path, "rev-parse", "HEAD")
    doc = make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", OLD, expected_strip(OLD))))
    result = pp.apply_proposals(document=doc, manifest_sha256=MANIFEST, base_head=newer, proposal_base_head=head,
                                allowed_paths=("pkg/m.py",), protected_paths=(), isolation=iso)
    assert result.verdict == "REFUSED" and codes(result) == ["STALE_BASE"]
    assert (root / "pkg" / "m.py").read_bytes() == b"def f():\n    return 9\n"


@needs_git
def test_real_git_patch_for_other_content_is_refused_stale_and_leaves_bytes_unchanged(tmp_path):
    other = "def f():\n    return 1 \n\nx = 2\t\n"  # one trailing space where the file has two
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": OLD.encode()})
    doc = make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", other, expected_strip(other))))
    result = real_apply(root, head, iso, doc)
    assert result.verdict == "REFUSED" and codes(result) == ["STALE_BASE"] and result.stage == "BUILD"
    assert (root / "pkg" / "m.py").read_bytes() == OLD.encode()


@needs_git
def test_real_git_two_recipes_for_one_file_apply_in_sequence(tmp_path):
    old = "x = 1  \ny = 2\n\n\n"
    stripped = "x = 1\ny = 2\n\n\n"
    final = "x = 1\ny = 2\n"
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": old.encode()})
    doc = make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", old, stripped)),
                   proposal(file="pkg/m.py", recipe="final-newline", detail="Ensure a single trailing newline",
                            diff=difflib_diff("pkg/m.py", stripped, final)))
    result = real_apply(root, head, iso, doc)
    assert result.verdict == "ACCEPTED", result.reasons
    assert (root / "pkg" / "m.py").read_bytes() == b"x = 1\ny = 2\n"


@needs_git
def test_real_git_final_newline_marker_diff_adds_the_newline(tmp_path):
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": b"x = 1"})
    doc = make_doc(proposal(file="pkg/m.py", recipe="final-newline", detail="Ensure a single trailing newline",
                            diff=eof_marker_diff("pkg/m.py", "x = 1", 1)))
    result = real_apply(root, head, iso, doc)
    assert result.verdict == "ACCEPTED", result.reasons
    assert (root / "pkg" / "m.py").read_bytes() == b"x = 1\n"


@needs_git
def test_real_git_crlf_file_is_blocked_not_representable_and_unchanged(tmp_path):
    crlf = OLD.replace("\n", "\r\n").encode()
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": crlf})
    doc = make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", OLD, expected_strip(OLD))))
    result = real_apply(root, head, iso, doc)
    assert result.verdict == "BLOCKED" and codes(result) == ["PATCH_NOT_REPRESENTABLE"]
    assert (root / "pkg" / "m.py").read_bytes() == crlf


@needs_git
def test_real_git_second_apply_after_success_is_blocked_dirty_and_the_file_is_unchanged(tmp_path):
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": OLD.encode()})
    doc = make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", OLD, expected_strip(OLD))))
    assert real_apply(root, head, iso, doc).verdict == "ACCEPTED"
    after = (root / "pkg" / "m.py").read_bytes()
    again = real_apply(root, head, iso, doc)
    assert again.verdict == "BLOCKED" and codes(again) == ["DIRTY_WORKTREE"]
    assert (root / "pkg" / "m.py").read_bytes() == after == b"def f():\n    return 1\n\nx = 2\n"


@needs_git
def test_real_git_lock_present_blocks_and_changes_nothing(tmp_path):
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": OLD.encode()})
    (root / ".git" / "vst-u5-2.lock").write_bytes(b"1")
    doc = make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", OLD, expected_strip(OLD))))
    result = real_apply(root, head, iso, doc)
    assert result.verdict == "BLOCKED" and codes(result) == ["WORKTREE_LOCKED"]
    assert (root / "pkg" / "m.py").read_bytes() == OLD.encode()
    assert (root / ".git" / "vst-u5-2.lock").exists()


@needs_git
def test_real_git_hostile_repository_config_is_untrusted(tmp_path):
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": OLD.encode()})
    with open(root / ".git" / "config", "ab") as handle:
        handle.write(b'\n[filter "evil"]\n\tclean = evil-program\n\tsmudge = evil-program\n')
    doc = make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", OLD, expected_strip(OLD))))
    result = real_apply(root, head, iso, doc)
    assert result.verdict == "BLOCKED" and codes(result) == ["UNTRUSTED_GIT_CONFIG"]
    assert (root / "pkg" / "m.py").read_bytes() == OLD.encode()


@needs_git
def test_real_git_committed_gitattributes_with_eol_is_accepted(tmp_path):
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": OLD.encode(), ".gitattributes": b"* text=auto\n*.py text eol=lf\n"})
    doc = make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", OLD, expected_strip(OLD))))
    result = real_apply(root, head, iso, doc)
    assert result.verdict == "ACCEPTED"
    assert (root / "pkg" / "m.py").read_bytes() == b"def f():\n    return 1\n\nx = 2\n"


@needs_git
def test_real_git_committed_gitattributes_with_filter_is_untrusted(tmp_path):
    root, head, iso = make_repo(tmp_path, {"pkg/m.py": OLD.encode(), ".gitattributes": b"*.py filter=evil\n"})
    doc = make_doc(proposal(file="pkg/m.py", diff=difflib_diff("pkg/m.py", OLD, expected_strip(OLD))))
    result = real_apply(root, head, iso, doc)
    assert result.verdict == "BLOCKED" and codes(result) == ["UNTRUSTED_GIT_CONFIG"]
    assert (root / "pkg" / "m.py").read_bytes() == OLD.encode()
