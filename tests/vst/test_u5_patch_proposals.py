"""U5-2: apply AEVE patch proposals through the diff gate.

Acceptance text: "AEVE's repair lab (diagnosis, dead-code candidates, bounded patch proposals; it
never applies a patch itself) supplies the patch; VST applies it in the isolated worktree and the
deterministic diff gate checks it; the model writes code only for what AEVE proposed no patch for;
a patch outside scope, on a protected path, or with a stale base is refused; the share of a change
produced by proposals versus the model is recorded per run."

Synthetic data only. There is no real git repository: git is replaced by a scripted runner
(`FakeGit`) injected through the `git_runner` parameter, as the module allows. The proposal document
follows the real AEVE `g6.patch.v1` shape (AEVE src/aeve/repair/patch.py). Expected counts and
fractions are hand-computed from the hunks written in this file.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
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


def shown(value):
    return ascii(value)


# ---------------------------------------------------------------------------- document builders
def aeve_diff(path="src/app.py"):
    """One AEVE per-file diff: headers without a/ b/ prefix, one hunk, one changed line."""
    return "\n".join([f"--- {path}", f"+++ {path}", "@@ -1,3 +1,3 @@", " a", "-b  ", "+b", " c"])


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
def make_isolation(tmp_path):
    worktree = tmp_path / "worktree"
    main = tmp_path / "main"
    worktree.mkdir(exist_ok=True)
    main.mkdir(exist_ok=True)
    roots = {os.path.normcase(str(worktree)), os.path.normcase(str(main))}

    def lstat(path):
        mode = stat.S_IFDIR if os.path.normcase(path) in roots else stat.S_IFREG
        return SimpleNamespace(st_mode=mode | 0o755, st_file_attributes=0)

    return wg.IsolationContext(str(worktree), str(main), False, BASE, None, lstat=lstat)


class FakeGit:
    """Scripted git: answers by subcommand (args[5]; the first five are the fixed prefix) and records calls."""

    def __init__(self, root, *, head=BASE, toplevel=None, dirty=False, check_rc=0, apply_rc=0, tree=TREE_NEW,
                 diff=None, names=b"src/app.py\0", verify_rc=0, restore_rcs=(0, 0), timeout_on=None):
        self.root = root
        self.head, self.dirty, self.check_rc, self.apply_rc, self.tree = head, dirty, check_rc, apply_rc, tree
        self.toplevel = (toplevel or root).replace("\\", "/")
        self.diff = git_diff() if diff is None else diff
        self.names, self.verify_rc = names, verify_rc
        self.restore_rcs = list(restore_rcs)
        self.timeout_on = timeout_on
        self.calls = []

    def subs(self):
        return [c["sub"] for c in self.calls]

    def __call__(self, args, *, cwd, env, stdin=None, timeout):
        sub, rest = args[5], list(args[6:])
        self.calls.append({"sub": sub, "rest": rest, "cwd": cwd, "env": dict(env), "stdin": stdin,
                           "timeout": timeout, "prefix": list(args[:5])})
        if sub == self.timeout_on:
            return pp.GitResult(-1, b"", b"", True)
        if sub == "rev-parse":
            if "--show-toplevel" in rest:
                return pp.GitResult(0, self.toplevel.encode() + b"\n")
            if rest[-1].endswith("^{tree}"):
                return pp.GitResult(0, TREE_BASE.encode() + b"\n")
            return pp.GitResult(0, self.head.encode() + b"\n")
        if sub == "status":
            return pp.GitResult(0, b" M src/app.py\0" if self.dirty else b"")
        if sub == "read-tree":
            return pp.GitResult(0)
        if sub == "apply":
            if "--check" in rest:
                return pp.GitResult(self.check_rc, b"", b"error: patch failed: src/app.py:1\n" if self.check_rc else b"")
            return pp.GitResult(self.apply_rc, b"", b"error: boom\n" if self.apply_rc else b"")
        if sub == "write-tree":
            return pp.GitResult(0, self.tree.encode() + b"\n")
        if sub == "commit-tree":
            return pp.GitResult(0, CAND.encode() + b"\n")
        if sub == "diff":
            if "--quiet" in rest:
                return pp.GitResult(self.verify_rc)
            if "--name-only" in rest:
                return pp.GitResult(0, self.names)
            return pp.GitResult(0, self.diff)
        if sub == "restore":
            rc = self.restore_rcs.pop(0) if self.restore_rcs else 0
            return pp.GitResult(rc, b"", b"error: restore\n" if rc else b"")
        return pp.GitResult(128, b"", b"unexpected")


def run(tmp_path, *, fake=None, doc=None, **over):
    isolation = make_isolation(tmp_path)
    fake = fake or FakeGit(isolation.worktree_root)
    kwargs = dict(document=make_doc(proposal()) if doc is None else doc, manifest_sha256=MANIFEST,
                  base_head=BASE, proposal_base_head=BASE, allowed_paths=ALLOWED, protected_paths=(),
                  isolation=isolation, git_runner=fake)
    kwargs.update(over)
    return pp.apply_proposals(**kwargs), fake


def codes(result):
    return [c for c, _ in result.reasons]


# ---------------------------------------------------------------------------- valid proposal
def test_valid_proposal_is_applied_and_accepted(tmp_path):
    result, fake = run(tmp_path)
    assert result.verdict == "ACCEPTED"
    assert result.stage == "MATERIALIZE"
    assert result.worktree_state == "MODIFIED"
    assert result.candidate_head == CAND
    assert result.changed_paths == ("src/app.py",)
    assert result.gate.verdict == "ACCEPTED"
    assert result.diff_sha256 == hashlib.sha256(git_diff()).hexdigest()
    # one hunk: one line added, one line deleted
    assert result.hunks_by_file == {"src/app.py": [(1, 1)]}
    restore = [c for c in fake.calls if c["sub"] == "restore"]
    assert len(restore) == 1
    assert f"--source={CAND}" in restore[0]["rest"]
    assert restore[0]["stdin"] == b"src/app.py\0"


def test_document_may_be_given_as_json_bytes(tmp_path):
    raw = json.dumps(make_doc(proposal())).encode()
    result, _ = run(tmp_path, doc=raw)
    assert result.verdict == "ACCEPTED"


def test_patch_is_checked_then_applied_to_a_throwaway_index_and_worktree_written_last(tmp_path):
    result, fake = run(tmp_path)
    assert result.verdict == "ACCEPTED"
    applies = [c for c in fake.calls if c["sub"] == "apply"]
    assert ["--check" in c["rest"] for c in applies] == [True, False]
    assert all("--cached" in c["rest"] for c in applies)
    expected = (b"diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n"
                b"@@ -1,3 +1,3 @@\n a\n-b  \n+b\n c\n")
    assert all(c["stdin"] == expected for c in applies)
    subs = fake.subs()
    # nothing writes the working files before the gate: restore is the very last mutating call
    assert subs.index("restore") > subs.index("commit-tree")
    assert subs.count("restore") == 1


def test_every_git_call_uses_the_worktree_cwd_fixed_prefix_timeout_and_minimal_env(tmp_path, monkeypatch):
    monkeypatch.setenv("VST_SENTINEL_SECRET", "leak")
    result, fake = run(tmp_path, timeout=7.5)
    assert result.verdict == "ACCEPTED"
    root = make_isolation(tmp_path).worktree_root
    for call in fake.calls:
        assert call["cwd"] == root
        assert call["timeout"] == 7.5
        assert call["prefix"] == ["--literal-pathspecs", "-c", "core.fsmonitor=false", "-c", "commit.gpgsign=false"]
        assert "VST_SENTINEL_SECRET" not in call["env"]
        assert call["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert call["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
    index_calls = [c for c in fake.calls if "GIT_INDEX_FILE" in c["env"]]
    assert {c["sub"] for c in index_calls} == {"read-tree", "apply", "write-tree"}
    index_path = index_calls[0]["env"]["GIT_INDEX_FILE"]
    assert not os.path.normcase(index_path).startswith(os.path.normcase(root))


def test_scratch_directory_is_removed_after_the_run(tmp_path):
    result, fake = run(tmp_path)
    scratch = fake.calls[0]["env"]["TEMP"]
    assert result.verdict == "ACCEPTED"
    assert not os.path.exists(scratch)


def test_two_recipes_for_one_file_are_applied_in_document_order(tmp_path):
    second = proposal(recipe="final-newline", detail="Ensure a single trailing newline",
                      diff="\n".join(["--- src/app.py", "+++ src/app.py", "@@ -3 +3 @@", "-c", "\\ No newline at end of file", "+c"]))
    result, fake = run(tmp_path, doc=make_doc(proposal(), second))
    assert result.verdict == "ACCEPTED"
    applies = [c for c in fake.calls if c["sub"] == "apply" and "--check" not in c["rest"]]
    assert len(applies) == 2
    assert applies[0]["stdin"].startswith(b"diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1,3 +1,3 @@")
    assert applies[1]["stdin"].endswith(b"@@ -3 +3 @@\n-c\n\\ No newline at end of file\n+c\n")


def test_flagged_only_paths_are_reported_and_need_no_patch(tmp_path):
    doc = make_doc(proposal(), proposal(file="src/other.py", recipe="unused-import", changed=False, detail="Remove unused import 'os'"),
                   proposal(file="src/other.py", recipe="unused-import", changed=False, detail="Remove unused import 'sys'"))
    result, _ = run(tmp_path, doc=doc)
    assert result.verdict == "ACCEPTED"
    assert result.no_patch_paths == ("src/other.py",)


def test_document_without_a_patch_is_blocked_and_touches_nothing(tmp_path):
    doc = make_doc(proposal(recipe="unused-import", changed=False, detail="Remove unused import 'os'"))
    result, fake = run(tmp_path, doc=doc)
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["NO_PATCH_IN_PROPOSAL"]
    assert fake.calls == []


# ---------------------------------------------------------------------------- stale base
def test_proposal_made_for_another_head_is_refused_stale_base(tmp_path):
    result, fake = run(tmp_path, proposal_base_head=OTHER_HEAD)
    assert result.verdict == "REFUSED"
    assert codes(result) == ["STALE_BASE"]
    assert result.worktree_state == "UNCHANGED"
    assert fake.calls == []


def test_worktree_head_that_moved_is_refused_stale_base_before_any_write(tmp_path):
    result, fake = run(tmp_path, fake=FakeGit(make_isolation(tmp_path).worktree_root, head=OTHER_HEAD))
    assert result.verdict == "REFUSED"
    assert codes(result) == ["STALE_BASE"]
    assert "apply" not in fake.subs() and "restore" not in fake.subs()


def test_patch_that_does_not_apply_to_the_base_content_is_refused_stale_base(tmp_path):
    result, fake = run(tmp_path, fake=FakeGit(make_isolation(tmp_path).worktree_root, check_rc=1))
    assert result.verdict == "REFUSED"
    assert codes(result) == ["STALE_BASE"]
    assert result.stage == "BUILD"
    assert result.worktree_state == "UNCHANGED"
    assert "restore" not in fake.subs()
    assert sum(1 for c in fake.calls if c["sub"] == "apply") == 1  # stopped at the first failing check


def test_patch_that_git_calls_corrupt_is_blocked_not_stale(tmp_path):
    class Corrupt(FakeGit):
        def __call__(self, args, **kw):
            res = super().__call__(args, **kw)
            if args[5] == "apply" and "--check" in args:
                return pp.GitResult(1, b"", b"error: corrupt patch at line 9\n")
            return res
    result, _ = run(tmp_path, fake=Corrupt(make_isolation(tmp_path).worktree_root))
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["PROPOSAL_MALFORMED"]


def test_missing_or_malformed_base_heads_are_blocked(tmp_path):
    for bad in (None, "", "b" * 39, "B" * 40, 5):
        result, fake = run(tmp_path, proposal_base_head=bad)
        assert result.verdict == "BLOCKED" and fake.calls == []
        result, fake = run(tmp_path, base_head=bad)
        assert result.verdict == "BLOCKED" and fake.calls == []


# ---------------------------------------------------------------------------- scope and protected paths
def test_out_of_scope_patch_is_refused_before_any_git_call(tmp_path):
    doc = make_doc(proposal(file="src/other.py"))
    result, fake = run(tmp_path, doc=doc)
    assert result.verdict == "REFUSED"
    assert ("OUT_OF_SCOPE_PATH", shown("src/other.py")) in result.reasons
    assert result.stage == "PRESCREEN"
    assert result.worktree_state == "UNCHANGED"
    assert fake.calls == []


@pytest.mark.parametrize("path", [
    "CLAUDE.md", "docs/CLAUDE.md", "pkg/sub/AGENTS.md", ".github/workflows/ci.py", ".harness/x.py",
    "tools/vst/patch_proposals.py", ".claude/settings.py", "a/.git/hooks/pre-commit",
])
def test_protected_path_is_refused_even_when_listed_as_allowed(tmp_path, path):
    doc = make_doc(proposal(file=path))
    result, fake = run(tmp_path, doc=doc, allowed_paths=(path,))
    assert result.verdict == "REFUSED"
    assert ("PROTECTED_PATH", shown(path)) in result.reasons
    assert fake.calls == []
    assert result.worktree_state == "UNCHANGED"


def test_caller_protected_path_is_refused(tmp_path):
    result, fake = run(tmp_path, protected_paths=("src",))
    assert result.verdict == "REFUSED"
    assert ("PROTECTED_PATH", shown("src/app.py")) in result.reasons
    assert fake.calls == []


def test_gate_refusal_after_the_build_never_writes_the_worktree(tmp_path):
    # git reports a different changed set than the proposed files: refused, restore never called
    fake = FakeGit(make_isolation(tmp_path).worktree_root, names=b"src/app.py\0src/extra.py\0")
    result, _ = run(tmp_path, fake=fake)
    assert result.verdict == "REFUSED"
    assert codes(result) == ["DIFF_PATH_MISMATCH"]
    assert "restore" not in fake.subs()
    assert result.worktree_state == "UNCHANGED"


def test_second_proposed_file_outside_scope_refuses_the_whole_document(tmp_path):
    # One in-scope and one out-of-scope patch: the document is refused as a whole, nothing is written.
    doc = make_doc(proposal(), proposal(file="src/two.py"))
    two = git_diff("src/two.py")
    fake = FakeGit(make_isolation(tmp_path).worktree_root, diff=git_diff() + two, names=b"src/app.py\0src/two.py\0")
    result, _ = run(tmp_path, doc=doc, fake=fake, allowed_paths=ALLOWED)
    assert result.verdict == "REFUSED"
    assert result.stage == "PRESCREEN"  # caught already on the claimed diff
    assert "restore" not in fake.subs()


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
def header_other_file(d): d["proposals"][0]["diff"] = aeve_diff("src/zzz.py"); return rehash(d)
def hunk_too_short(d): d["proposals"][0]["diff"] = aeve_diff().rsplit("\n", 1)[0]; return rehash(d)
def hunk_too_long(d): d["proposals"][0]["diff"] = aeve_diff() + "\n+extra"; return rehash(d)
def empty_diff(d): d["proposals"][0]["diff"] = ""; return rehash(d)
def diff_on_note(d): d["proposals"][0].update(changed=False); return rehash(d)
def unknown_recipe(d): d["proposals"][0]["recipe"] = "rewrite-everything"; return rehash(d)
def note_recipe_with_patch(d): d["proposals"][0]["recipe"] = "unused-import"; return rehash(d)
def changed_not_bool(d): d["proposals"][0]["changed"] = 1; return rehash(d)
def missing_field(d): del d["proposals"][0]["detail"]; return rehash(d)
def redacted(d): d["proposals"][0]["diff"] = aeve_diff().replace("+b", "+[REDACTED]"); return rehash(d)
def duplicate_recipe(d): d["proposals"].append(copy.deepcopy(d["proposals"][0])); d["proposal_count"] = 2; return rehash(d)
def nul_in_diff(d): d["proposals"][0]["diff"] = aeve_diff().replace("+b", "+b\x00"); return rehash(d)
def status_not_partial(d): d["status"] = "COMPLETE"; return rehash(d)
def too_many(d): d["proposals"] = [proposal(file=f"f{i}.py") for i in range(pp.MAX_PROPOSALS + 1)]; d["proposal_count"] = len(d["proposals"]); return rehash(d)
def not_a_dict(d): return ["x"]

MALFORMED = [bad_schema, extra_key, llm_used, code_executed, count_wrong, hash_wrong, hash_missing, not_a_list,
             traversal, absolute, backslash, glob_name, header_other_file, hunk_too_short, hunk_too_long,
             empty_diff, diff_on_note, unknown_recipe, note_recipe_with_patch, changed_not_bool, missing_field,
             redacted, duplicate_recipe, nul_in_diff, status_not_partial, too_many, not_a_dict]


@pytest.mark.parametrize("mutate", MALFORMED, ids=lambda f: f.__name__)
def test_malformed_proposal_is_blocked_and_touches_nothing(tmp_path, mutate):
    result, fake = run(tmp_path, doc=mutate(make_doc(proposal())))
    assert result.verdict == "BLOCKED"
    assert fake.calls == []
    assert result.worktree_state == "UNCHANGED"
    assert result.stage == "VALIDATE"


def test_partial_report_with_uncovered_list_is_valid(tmp_path):
    doc = make_doc(proposal(), status="PARTIAL", uncovered=["LANGUAGE_NOT_INDEXED: web/app.js"])
    result, _ = run(tmp_path, doc=doc)
    assert result.verdict == "ACCEPTED"


def test_oversized_document_bytes_are_blocked(tmp_path):
    result, fake = run(tmp_path, doc=b"{" + b" " * (pp.MAX_DOCUMENT_BYTES + 1) + b"}")
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["PROPOSAL_TOO_LARGE"]
    assert fake.calls == []


def test_oversized_single_diff_is_blocked(tmp_path):
    big = "\n".join(["--- src/app.py", "+++ src/app.py", f"@@ -0,0 +1,{40000} @@"] + ["+" + "x" * 20] * 40000)
    assert len(big.encode()) > pp.MAX_DIFF_BYTES_PER_PROPOSAL
    result, fake = run(tmp_path, doc=make_doc(proposal(diff=big)))
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["PROPOSAL_TOO_LARGE"]
    assert fake.calls == []


@pytest.mark.parametrize("raw", [
    b"", b"not json", b"[1]", b'{"a": 1, "a": 2}', b'{"llm_calls": NaN}', b"\xff\xfe", b'{"a": "\x00"}',
])
def test_unparsable_document_bytes_are_blocked(tmp_path, raw):
    result, fake = run(tmp_path, doc=raw)
    assert result.verdict == "BLOCKED"
    assert fake.calls == []


def test_non_document_types_are_blocked(tmp_path):
    for bad in (None, 5, "text", [], object()):
        result, fake = run(tmp_path, doc=bad)
        assert result.verdict == "BLOCKED" and fake.calls == []


def test_missing_isolation_context_is_blocked(tmp_path):
    result, fake = run(tmp_path, isolation=None)
    assert result.verdict == "BLOCKED"
    assert fake.calls == []


# ---------------------------------------------------------------------------- apply failure leaves the worktree unchanged
def test_dirty_touched_path_is_blocked_before_building(tmp_path):
    fake = FakeGit(make_isolation(tmp_path).worktree_root, dirty=True)
    result, _ = run(tmp_path, fake=fake)
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["DIRTY_WORKTREE"]
    assert "apply" not in fake.subs() and "restore" not in fake.subs()


def test_git_toplevel_that_is_not_the_worktree_is_blocked(tmp_path):
    fake = FakeGit(make_isolation(tmp_path).worktree_root, toplevel=str(tmp_path / "elsewhere"))
    result, _ = run(tmp_path, fake=fake)
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["WORKTREE_ROOT_MISMATCH"]
    assert fake.subs() == ["rev-parse"]


def test_failing_apply_after_a_good_check_is_blocked_and_the_worktree_is_untouched(tmp_path):
    fake = FakeGit(make_isolation(tmp_path).worktree_root, apply_rc=1)
    result, _ = run(tmp_path, fake=fake)
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["GIT_FAILED"]
    assert result.worktree_state == "UNCHANGED"
    assert "restore" not in fake.subs()


@pytest.mark.parametrize("sub", ["rev-parse", "status", "read-tree", "apply", "write-tree", "commit-tree", "diff"])
def test_git_timeout_is_blocked_and_the_worktree_is_untouched(tmp_path, sub):
    fake = FakeGit(make_isolation(tmp_path).worktree_root, timeout_on=sub)
    result, _ = run(tmp_path, fake=fake)
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["GIT_TIMEOUT"]
    assert result.worktree_state == "UNCHANGED"
    assert "restore" not in fake.subs()


def test_patches_that_change_nothing_are_blocked(tmp_path):
    fake = FakeGit(make_isolation(tmp_path).worktree_root, tree=TREE_BASE)
    result, _ = run(tmp_path, fake=fake)
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["NO_EFFECT"]
    assert "restore" not in fake.subs()


def test_write_failure_is_rolled_back_from_the_base_head(tmp_path):
    fake = FakeGit(make_isolation(tmp_path).worktree_root, restore_rcs=(1, 0))
    result, _ = run(tmp_path, fake=fake)
    assert result.verdict == "BLOCKED"
    assert result.worktree_state == "UNCHANGED"
    assert codes(result) == ["GIT_FAILED", "ROLLED_BACK"]
    restores = [c for c in fake.calls if c["sub"] == "restore"]
    assert [f"--source={CAND}" in c["rest"] for c in restores] == [True, False]
    assert f"--source={BASE}" in restores[1]["rest"]


def test_write_failure_and_failed_rollback_report_unknown_state(tmp_path):
    fake = FakeGit(make_isolation(tmp_path).worktree_root, restore_rcs=(1, 1))
    result, _ = run(tmp_path, fake=fake)
    assert result.verdict == "BLOCKED"
    assert result.worktree_state == "UNKNOWN"
    assert "ROLLBACK_FAILED" in codes(result)


def test_worktree_that_differs_from_the_candidate_after_writing_is_rolled_back(tmp_path):
    fake = FakeGit(make_isolation(tmp_path).worktree_root, verify_rc=1)
    result, _ = run(tmp_path, fake=fake)
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["MATERIALIZE_VERIFY_FAILED", "ROLLED_BACK"]
    assert result.worktree_state == "UNCHANGED"
    assert [c["rest"] for c in fake.calls if c["sub"] == "restore"][-1].count(f"--source={BASE}") == 1


def test_runner_that_raises_is_blocked_not_propagated(tmp_path):
    def boom(args, **kw):
        raise RuntimeError("x")
    result, _ = run(tmp_path, git_runner=boom)
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["INTERNAL_ERROR"]


def test_runner_returning_garbage_is_blocked(tmp_path):
    result, _ = run(tmp_path, git_runner=lambda args, **kw: (0, b""))
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["GIT_RUNNER_MALFORMED"]


def test_git_object_ids_that_are_not_hex_are_blocked(tmp_path):
    fake = FakeGit(make_isolation(tmp_path).worktree_root, head="not-a-sha")
    result, _ = run(tmp_path, fake=fake)
    assert result.verdict == "BLOCKED"
    assert codes(result) == ["GIT_OUTPUT_MALFORMED"]


def test_default_runner_uses_shell_false_cwd_env_timeout_and_reports_timeout(tmp_path, monkeypatch):
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"], seen["kw"] = argv, kw
        return SimpleNamespace(returncode=0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(pp.shutil, "which", lambda name, path=None: "C:/git/git.exe")
    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    env = {"PATH": "C:/git", "X": "1"}
    result = pp.default_git_runner(["status"], cwd=str(tmp_path), env=env, stdin=b"in", timeout=3.0)
    assert result == pp.GitResult(0, b"ok", b"")
    assert seen["argv"] == ["C:/git/git.exe", "status"]
    assert seen["kw"]["shell"] is False
    assert seen["kw"]["cwd"] == str(tmp_path)
    assert seen["kw"]["env"] == env
    assert seen["kw"]["timeout"] == 3.0
    assert seen["kw"]["input"] == b"in"

    def timed_out(argv, **kw):
        raise pp.subprocess.TimeoutExpired(argv, 3.0)

    monkeypatch.setattr(pp.subprocess, "run", timed_out)
    assert pp.default_git_runner(["status"], cwd=str(tmp_path), env=env).timed_out is True
    monkeypatch.setattr(pp.shutil, "which", lambda name, path=None: None)
    assert pp.default_git_runner(["status"], cwd=str(tmp_path), env=env).returncode == -1


def test_build_git_env_is_fixed_and_minimal(monkeypatch, tmp_path):
    monkeypatch.setenv("SOME_TOKEN", "secret")
    env = pp.build_git_env(str(tmp_path), index_file="idx")
    assert "SOME_TOKEN" not in env
    assert env["GIT_INDEX_FILE"] == "idx"
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert env["HOME"] == str(tmp_path)
    assert "GIT_INDEX_FILE" not in pp.build_git_env(str(tmp_path))


# ---------------------------------------------------------------------------- share of proposal versus model
def test_share_counts_added_plus_deleted_lines_per_origin_with_exact_fractions():
    # proposal: (2+1) + (1+0) = 4 lines; model: (5+3) + (4+0) = 12 lines; total 16
    share = pp.change_origin_share(
        {"src/a.py": [(2, 1), (1, 0)]},
        {"src/a.py": [(5, 3)], "src/b.py": [(4, 0)]})
    assert share["proposal"] == {"added": 3, "deleted": 1, "lines": 4, "hunks": 2, "files": ["src/a.py"]}
    assert share["model"] == {"added": 9, "deleted": 3, "lines": 12, "hunks": 2, "files": ["src/a.py", "src/b.py"]}
    assert share["total_lines"] == 16
    assert share["proposal_fraction"] == 0.25
    assert share["model_fraction"] == 0.75
    assert share["files_touched_by_both"] == ["src/a.py"]
    assert share["model_only_paths"] == ["src/b.py"]
    assert share["proposal_only_paths"] == []
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
    assert share["total_lines"] == 0
    assert share["proposal_fraction"] is None and share["model_fraction"] is None


def test_share_matches_paths_case_insensitively_so_a_case_variant_is_not_model_only():
    share = pp.change_origin_share({"src/a.py": [(1, 0)]}, {"SRC/A.PY": [(1, 0)]})
    assert share["files_touched_by_both"] == ["src/a.py"]
    assert share["model_only_paths"] == []


def test_share_does_not_double_count_a_shared_file():
    share = pp.change_origin_share({"a.py": [(1, 1)]}, {"a.py": [(1, 1)]})
    assert share["total_lines"] == 4
    assert share["proposal_fraction"] == 0.5


@pytest.mark.parametrize("proposal_side, model_side", [
    ({"a.py": [(-1, 0)]}, {}),
    ({"a.py": [(True, 0)]}, {}),
    ({"a.py": [(1.5, 0)]}, {}),
    ({"a.py": [(1,)]}, {}),
    ({"a.py": "text"}, {}),
    ({"": [(1, 0)]}, {}),
    ({1: [(1, 0)]}, {}),
    ([("a.py", [(1, 0)])], {}),
    ({}, None),
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
    rename = b"diff --git a/a.py b/b.py\nsimilarity index 100%\nrename from a.py\nrename to b.py\n"
    with pytest.raises(pp.ProposalError):
        pp.hunk_counts_from_diff(rename)


def test_applied_proposal_hunks_feed_the_share_record(tmp_path):
    result, _ = run(tmp_path)
    share = pp.change_origin_share(result.hunks_by_file, {"src/model_only.py": [(7, 1)]})
    # proposal 1+1 = 2 lines, model 7+1 = 8 lines, total 10
    assert share["proposal"]["lines"] == 2
    assert share["model"]["lines"] == 8
    assert share["proposal_fraction"] == 0.2
    assert share["model_only_paths"] == ["src/model_only.py"]


# ---------------------------------------------------------------------------- model may not override a proposal
def test_model_change_on_a_path_with_a_proposed_patch_is_refused():
    verdict = pp.check_model_changes(proposal_patched_paths=["src/app.py"], model_changed_paths=["src/app.py", "src/new.py"])
    assert verdict.verdict == "REFUSED"
    assert verdict.reasons == (("MODEL_OVERRIDES_PROPOSAL", shown("src/app.py")),)
    assert verdict.overrides == ()
    assert verdict.model_only_paths == ("src/new.py",)


def test_model_change_on_a_case_variant_of_a_patched_path_is_refused():
    verdict = pp.check_model_changes(proposal_patched_paths=["src/app.py"], model_changed_paths=["SRC/App.py"])
    assert verdict.verdict == "REFUSED"
    assert verdict.reasons[0][0] == "MODEL_OVERRIDES_PROPOSAL"


def test_model_may_write_paths_with_no_proposed_patch():
    verdict = pp.check_model_changes(proposal_patched_paths=["src/app.py"], model_changed_paths=["src/other.py", "docs/x.md"])
    assert verdict.verdict == "ACCEPTED"
    assert verdict.reasons == (("NO_CONFLICT", "model paths avoid every proposed patch"),)
    assert verdict.model_only_paths == ("docs/x.md", "src/other.py")


def test_flagged_only_path_from_the_proposal_is_not_a_patched_path(tmp_path):
    result, _ = run(tmp_path, doc=make_doc(proposal(), proposal(file="src/other.py", recipe="unused-import", changed=False,
                                                                  detail="Remove unused import 'os'")))
    verdict = pp.check_model_changes(proposal_patched_paths=result.changed_paths, model_changed_paths=["src/other.py"])
    assert verdict.verdict == "ACCEPTED"


def test_explicit_override_reason_is_recorded_and_not_silent():
    verdict = pp.check_model_changes(
        proposal_patched_paths=["src/app.py"], model_changed_paths=["src/app.py"],
        override_reasons={"src/app.py": "  " + REASON + "  "})
    assert verdict.verdict == "ACCEPTED"
    assert verdict.overrides == ({"path": "src/app.py", "reason": REASON},)
    assert verdict.reasons == (("MODEL_OVERRIDE_RECORDED", shown("src/app.py")),)
    assert verdict.to_dict()["overrides"] == [{"path": "src/app.py", "reason": REASON}]


@pytest.mark.parametrize("reason", ["", "   ", "short", None, 5, "x" * 501, "bad\x00reason here", "line\nbreak in reason"])
def test_invalid_override_reason_does_not_unlock_the_path(reason):
    verdict = pp.check_model_changes(
        proposal_patched_paths=["src/app.py"], model_changed_paths=["src/app.py"], override_reasons={"src/app.py": reason})
    assert verdict.verdict == "REFUSED"
    assert verdict.reasons[0][0] == "OVERRIDE_REASON_INVALID"
    assert verdict.overrides == ()


def test_override_covers_only_the_named_path():
    verdict = pp.check_model_changes(
        proposal_patched_paths=["src/a.py", "src/b.py"], model_changed_paths=["src/a.py", "src/b.py"],
        override_reasons={"src/a.py": REASON})
    assert verdict.verdict == "REFUSED"
    assert verdict.reasons == (("MODEL_OVERRIDES_PROPOSAL", shown("src/b.py")),)
    assert verdict.overrides == ({"path": "src/a.py", "reason": REASON},)


def test_override_for_a_path_without_conflict_is_blocked():
    verdict = pp.check_model_changes(
        proposal_patched_paths=["src/a.py"], model_changed_paths=["src/c.py"], override_reasons={"src/c.py": REASON})
    assert verdict.verdict == "BLOCKED"
    assert verdict.reasons == (("OVERRIDE_WITHOUT_CONFLICT", shown("src/c.py")),)


@pytest.mark.parametrize("patched, model, overrides", [
    ("src/a.py", ["x.py"], None),
    (["a.py"], "a.py", None),
    (["a.py"], [1], None),
    (["a.py"], ["../a.py"], None),
    (["a.py"], ["a.py"], ["a.py"]),
    (None, ["a.py"], None),
])
def test_malformed_model_check_input_is_blocked(patched, model, overrides):
    verdict = pp.check_model_changes(proposal_patched_paths=patched, model_changed_paths=model, override_reasons=overrides)
    assert verdict.verdict == "BLOCKED"
