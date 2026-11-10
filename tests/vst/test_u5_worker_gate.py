"""U5-1: worker adapter output through the deterministic diff gate (Windows-local, no WSL).

Acceptance text: "The S3 worker adapter output passes through the deterministic diff gate on
Windows-local isolation; an out-of-scope or protected-path change is refused; the isolation
proof states what is and is not verified."

Synthetic data only; no real git repository and no network. The product code is not patched,
except that "diff gate missing" is simulated by removing the module from sys.modules and
the gate result by replacing the loader. Reason details hold ascii(path), see `shown`.
"""

from __future__ import annotations

import os
import stat
import sys
import types
from types import SimpleNamespace

import pytest

from tools.vst import diffgate as real_diffgate
from tools.vst import worker_gate as wg
from tools.vst.worker_adapter import (
    WorkerError, WorkerErrorCode, WorkerResponse, WorkerState, operation_key_for,
)

MANIFEST = "a" * 64
BASE = "b" * 40
HEAD = "c" * 40
ALLOWED = ("src/app.py",)
MIB = 1024 * 1024


def shown(path):
    return ascii(path)


def make_isolation(tmp_path, *, links=(), network=False, pinned=BASE, head=HEAD, root_ok=True,
                   with_attributes=True, same_root=False, nested=False, missing=(), realpath=None):
    worktree = str(tmp_path / "worktree")
    main = worktree if same_root else (os.path.join(worktree, "main") if nested else str(tmp_path / "main"))
    roots = {os.path.normcase(worktree), os.path.normcase(main)}

    def lstat(path):
        norm = os.path.normcase(path)
        if norm == os.path.normcase(worktree) and not root_ok:
            raise FileNotFoundError(path)
        info = SimpleNamespace(st_mode=(stat.S_IFDIR if norm in roots else stat.S_IFREG) | 0o755)
        name = os.path.basename(path)
        if norm not in roots and name in missing:
            raise FileNotFoundError(path)
        if with_attributes:
            info.st_file_attributes = 0x400 if (norm not in roots and name in links) else 0
        return info

    kwargs = {"realpath": realpath} if realpath else {}
    return wg.IsolationContext(worktree, main, network, pinned, head, lstat=lstat, **kwargs)


def diff_for(*paths):
    return "".join(
        f"diff --git a/{p} b/{p}\nindex 1111111..2222222 100644\n--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-a\n+b\n"
        for p in paths).encode("utf-8")


def run(tmp_path, *, changed=("src/app.py",), allowed=ALLOWED, protected=(), diff=None, isolation=None, **over):
    args = dict(
        manifest_sha256=MANIFEST, base_head=BASE, candidate_head=HEAD, changed_paths=changed,
        allowed_paths=allowed, protected_paths=protected,
        diff_bytes=diff_for(*changed) if diff is None else diff,
        isolation=make_isolation(tmp_path) if isolation is None else isolation,
    )
    args.update(over)
    return wg.gate_worker_change(**args)


def codes(verdict):
    return [code for code, _ in verdict.reasons]


def statuses(proof):
    return {item["property"]: item["status"] for item in proof["properties"]}


# ------------------------------------------------------------------ accepted and out of scope
def test_in_scope_change_is_accepted_with_gate_evidence(tmp_path):
    verdict = run(tmp_path)
    assert verdict.verdict == "ACCEPTED"
    assert codes(verdict) == ["DIFFGATE_PASS"]
    assert verdict.diff_evidence["verdict"] == "PASS"
    assert verdict.diff_evidence["changed_paths"] == ["src/app.py"]
    assert verdict.diff_evidence["candidate_head"] == HEAD
    assert verdict.to_dict()["verdict"] == "ACCEPTED"


def test_duplicate_changed_paths_are_accepted_once(tmp_path):
    verdict = run(tmp_path, changed=("src/app.py", "src/app.py"), diff=diff_for("src/app.py"))
    assert verdict.verdict == "ACCEPTED"
    assert verdict.diff_evidence["changed_paths"] == ["src/app.py"]


def test_deleted_file_missing_from_the_worktree_is_accepted(tmp_path):
    diff = (b"diff --git a/src/app.py b/src/app.py\ndeleted file mode 100644\nindex 2222222..0000000\n"
            b"--- a/src/app.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-a\n")
    verdict = run(tmp_path, diff=diff, isolation=make_isolation(tmp_path, missing={"app.py"}))
    assert verdict.verdict == "ACCEPTED"


def test_out_of_scope_change_is_refused(tmp_path):
    verdict = run(tmp_path, changed=("src/app.py", "src/other.py"))
    assert verdict.verdict == "REFUSED"
    assert ("OUT_OF_SCOPE_PATH", shown("src/other.py")) in verdict.reasons
    assert "DIFFGATE_OUT_OF_SCOPE_PATH" in codes(verdict)


def test_case_variant_of_an_allowed_path_is_refused(tmp_path):
    verdict = run(tmp_path, changed=("SRC/APP.PY",))
    assert verdict.verdict == "REFUSED"
    assert ("CASE_VARIANT_OF_ALLOWED_PATH", shown("SRC/APP.PY")) in verdict.reasons


def test_non_ascii_path_is_echoed_as_ascii(tmp_path):
    path = "src/\u00e9.py"
    verdict = run(tmp_path, changed=(path,))
    assert ("OUT_OF_SCOPE_PATH", "'src/\\xe9.py'") in verdict.reasons


# ------------------------------------------------------------------ protected paths
@pytest.mark.parametrize("path", [".git/config", ".GIT/config", "sub/.git/hooks/x"])
def test_dot_git_path_is_refused_outside_scope_and_when_listed_as_allowed(tmp_path, path):
    outside = run(tmp_path, changed=(path,), allowed=ALLOWED)
    assert outside.verdict == "REFUSED"
    assert ("PROTECTED_PATH", shown(path)) in outside.reasons
    assert ("OUT_OF_SCOPE_PATH", shown(path)) in outside.reasons
    listed = run(tmp_path, changed=(path,), allowed=(path,))
    assert listed.verdict == "REFUSED"
    assert codes(listed) == ["PROTECTED_PATH"]
    assert "MALFORMED_INPUT" not in codes(listed) + codes(outside)


@pytest.mark.parametrize("path", [
    ".github/workflows/ci.yml", ".Github/x.yml", ".harness/ledger.json", ".claude/settings.json",
    "AGENTS.md", "agents.md", "CLAUDE.md", "package-lock.json", "hooks/pre-push", "pyproject.toml", ".gitmodules",
    "sub/CLAUDE.md", "pkg/.claude/x", "sub/.gitattributes", "deep/sub/AGENTS.md", "x/.husky/pre-commit",
    "x/.harness/state.json", "tools/vst/gate.py", "TOOLS/VST/gate.py", ".harness-tools/ledger.py",
])
def test_protected_path_is_refused_even_when_listed_as_allowed(tmp_path, path):
    verdict = run(tmp_path, changed=(path,), allowed=(path,))
    assert verdict.verdict == "REFUSED"
    assert ("PROTECTED_PATH", shown(path)) in verdict.reasons


@pytest.mark.parametrize("path", ["core/DECISION_LOG.md", "CORE/x.md", "docs/private/a.md"])
def test_caller_protected_entries_are_refused_case_insensitively(tmp_path, path):
    verdict = run(tmp_path, changed=(path,), allowed=(path,), protected=("core/", "docs/private"))
    assert verdict.verdict == "REFUSED"
    assert codes(verdict) == ["PROTECTED_PATH"]


def test_unrelated_path_next_to_a_protected_prefix_is_not_protected(tmp_path):
    verdict = run(tmp_path, changed=("tools/vstx/a.py",), allowed=("tools/vstx/a.py",))
    assert verdict.verdict == "ACCEPTED"


@pytest.mark.parametrize("path", ["AGENTS.md.", "CLAUDE.md:stream", ".github /x.yml", ".git./config"])
def test_protected_name_alias_is_refused_as_hazard_and_as_protected(tmp_path, path):
    verdict = run(tmp_path, changed=(path,), allowed=(path,))
    assert verdict.verdict == "REFUSED"
    assert ("PROTECTED_PATH", shown(path)) in verdict.reasons
    assert any(code.startswith("PATH_HAZARD_") for code in codes(verdict))


def test_rename_into_protected_path_is_refused(tmp_path):
    diff = (b"diff --git a/src/app.py b/.github/ci.yml\nsimilarity index 100%\n"
            b"rename from src/app.py\nrename to .github/ci.yml\n")
    verdict = run(tmp_path, changed=("src/app.py", ".github/ci.yml"), allowed=("src/app.py", ".github/ci.yml"), diff=diff)
    assert verdict.verdict == "REFUSED"
    assert ("PROTECTED_PATH", shown(".github/ci.yml")) in verdict.reasons


def test_rename_out_of_a_protected_path_is_refused_on_the_source(tmp_path):
    diff = (b"diff --git a/.github/ci.yml b/src/app.py\nsimilarity index 100%\n"
            b"rename from .github/ci.yml\nrename to src/app.py\n")
    verdict = run(tmp_path, changed=(".github/ci.yml", "src/app.py"), allowed=(".github/ci.yml", "src/app.py"), diff=diff,
                  isolation=make_isolation(tmp_path, missing={"ci.yml"}))
    assert verdict.verdict == "REFUSED"
    assert ("PROTECTED_PATH", shown(".github/ci.yml")) in verdict.reasons


def test_symlink_mode_change_is_refused(tmp_path):
    diff = (b"diff --git a/src/app.py b/src/app.py\nnew file mode 120000\nindex 0000000..2222222\n"
            b"--- /dev/null\n+++ b/src/app.py\n@@ -0,0 +1 @@\n+target\n")
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "REFUSED"
    assert codes(verdict) == ["DIFFGATE_SYMLINK_CHANGE"]


def test_submodule_change_is_refused(tmp_path):
    diff = (b"diff --git a/src/app.py b/src/app.py\nnew file mode 160000\nindex 0000000..2222222\n"
            b"--- /dev/null\n+++ b/src/app.py\n@@ -0,0 +1 @@\n+Subproject commit 1\n")
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "REFUSED"
    assert ("SUBMODULE_CHANGE", shown(["src/app.py"])) in verdict.reasons


def test_nonstandard_file_mode_is_refused(tmp_path):
    diff = b"diff --git a/src/app.py b/src/app.py\nold mode 100644\nnew mode 100664\n"
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "REFUSED"
    assert ("NONSTANDARD_MODE", shown(["src/app.py"])) in verdict.reasons


# ------------------------------------------------------------------ diff text versus declared paths
def test_understated_changed_paths_are_refused(tmp_path):
    verdict = run(tmp_path, diff=diff_for("src/app.py", "src/hidden.py"))
    assert verdict.verdict == "REFUSED"
    assert codes(verdict) == ["DIFF_PATH_MISMATCH"]


def test_declared_path_absent_from_the_diff_is_refused(tmp_path):
    verdict = run(tmp_path, changed=("src/app.py", "src/b.py"), allowed=("src/app.py", "src/b.py"),
                  diff=diff_for("src/app.py"))
    assert verdict.verdict == "REFUSED"
    assert codes(verdict) == ["DIFF_PATH_MISMATCH"]


def test_rename_source_omitted_from_declared_paths_is_refused(tmp_path):
    diff = (b"diff --git a/src/old.py b/src/app.py\nsimilarity index 100%\n"
            b"rename from src/old.py\nrename to src/app.py\n")
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "REFUSED"
    assert "DIFF_PATH_MISMATCH" in codes(verdict)


@pytest.mark.parametrize("junk", [
    b"--- a/src/evil.py\n+++ b/src/evil.py\n@@ -1 +1 @@\n-a\n+b\n",
    b"diff --cc src/evil.py\n", b"diff --combined src/evil.py\n", b"GIT binary patch\nliteral 1\n",
    b"hello preamble\n",
])
def test_text_outside_the_git_block_grammar_is_not_accepted(tmp_path, junk):
    before = run(tmp_path, diff=junk + diff_for("src/app.py"))
    after = run(tmp_path, diff=diff_for("src/app.py") + junk)
    for verdict in (before, after):
        assert verdict.verdict == "BLOCKED"
        assert codes(verdict) == ["DIFF_UNPARSABLE"]


@pytest.mark.parametrize("diff", [
    b"diff --git a/src/app.py b/src/app.py\nindex 1111111..2222222 100644\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1,2 +1 @@\n-a\n",
    b"diff --git a/src/app.py b/src/app.py\nindex 1111111..2222222 100644\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-a\n+b\n+c\n",
    b"diff --git a/src/app.py b/src/app.py\nindex 1111111..2222222 100644\n--- a/src/app.py\n",
    b"diff --git a/src/app.py b/src/app.py\nunknown header\n",
    b"",
])
def test_truncated_or_inconsistent_hunks_are_not_accepted(tmp_path, diff):
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "BLOCKED"


def test_oversized_diff_is_blocked(tmp_path):
    verdict = run(tmp_path, diff=diff_for("src/app.py") + b"x" * (8 * MIB + 1))
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["MALFORMED_INPUT"]


def test_over_long_header_line_is_blocked(tmp_path):
    diff = b"diff --git a/src/app.py b/src/app.py\nindex 1111111..2222222 100644\n" + b"a" * 5000 + b"\n"
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "BLOCKED"
    assert verdict.reasons == (("DIFF_UNPARSABLE", "header line exceeds the size cap"),)


def test_more_than_128_paths_is_blocked(tmp_path):
    paths = tuple(f"src/f{i}.py" for i in range(129))
    verdict = run(tmp_path, changed=paths, allowed=paths)
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["MALFORMED_INPUT"]


HEADER = b"diff --git a/src/app.py b/src/app.py\n"
INDEX = b"index 1111111..2222222 100644\n"


@pytest.mark.parametrize("diff", [
    HEADER,
    HEADER + INDEX,
    diff_for("src/app.py") + HEADER,
    diff_for("src/app.py") + HEADER + INDEX,
    HEADER + b"similarity index 100%\n",
    HEADER + b"old mode 100644\n",
    HEADER + b"--- a/src/app.py\n",
])
def test_incomplete_blocks_are_blocked_with_the_header_only_reason(tmp_path, diff):
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict)[0] == "DIFF_UNPARSABLE"
    assert verdict.reasons[0][1] in ("diff block carries no complete change (header-only block)",
                                     "diff is empty, truncated or has no diff header")


def test_header_only_first_block_before_a_good_block_is_blocked(tmp_path):
    verdict = run(tmp_path, diff=HEADER + diff_for("src/app.py"))
    assert verdict.verdict == "BLOCKED"
    assert verdict.reasons == (("DIFF_UNPARSABLE", "diff block carries no complete change (header-only block)"),)


@pytest.mark.parametrize("diff", [
    HEADER + INDEX + b"GIT binary patch\n",
    HEADER + INDEX + b"GIT binary patch\nliteral 3\nzcmZQz\n",
    HEADER + INDEX + b"GIT binary patch\nliteral 3\nzcmZQz\n\ngarbage after the payload\n",
    HEADER + INDEX + b"GIT binary patch\nliteral 0\nHcmV?d00001\n\ndiff --git a/src/app.py b/src/app.py\n",
])
def test_git_binary_patch_is_unsupported_and_blocked(tmp_path, diff):
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "BLOCKED"
    assert verdict.reasons == (("DIFF_UNPARSABLE", "GIT binary patch payloads are unsupported"),)


def test_mode_only_block_is_accepted(tmp_path):
    diff = HEADER + b"old mode 100644\nnew mode 100755\n"
    assert run(tmp_path, diff=diff).verdict == "ACCEPTED"


def test_rename_only_block_is_accepted(tmp_path):
    diff = (b"diff --git a/src/old.py b/src/app.py\nsimilarity index 100%\n"
            b"rename from src/old.py\nrename to src/app.py\n")
    verdict = run(tmp_path, changed=("src/old.py", "src/app.py"), allowed=("src/old.py", "src/app.py"), diff=diff,
                  isolation=make_isolation(tmp_path, missing={"old.py"}))
    assert verdict.verdict == "ACCEPTED"


def test_binary_files_differ_marker_is_accepted_as_a_path_touch(tmp_path):
    diff = HEADER + INDEX + b"Binary files a/src/app.py and b/src/app.py differ\n"
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "ACCEPTED"
    assert verdict.diff_evidence["changed_paths"] == ["src/app.py"]


def test_binary_marker_for_an_out_of_scope_path_is_still_refused(tmp_path):
    diff = (b"diff --git a/src/other.py b/src/other.py\nindex 1111111..2222222 100644\n"
            b"Binary files a/src/other.py and b/src/other.py differ\n")
    verdict = run(tmp_path, changed=("src/other.py",), diff=diff)
    assert verdict.verdict == "REFUSED"
    assert ("OUT_OF_SCOPE_PATH", shown("src/other.py")) in verdict.reasons


# ------------------------------------------------------------------ REFUSED outranks BLOCKED
def test_refusal_outranks_a_blocking_isolation_reason(tmp_path):
    verdict = run(tmp_path, changed=("src/other.py",), isolation=make_isolation(tmp_path, network="no"))
    assert verdict.verdict == "REFUSED"
    assert ("OUT_OF_SCOPE_PATH", shown("src/other.py")) in verdict.reasons
    assert ("ISOLATION_NOT_VERIFIED", "network_flag_not_requested") in verdict.reasons


def test_refusal_outranks_an_unparsable_diff(tmp_path):
    quoted = b'diff --git "a/src/other.py" "b/src/other.py"\n'
    verdict = run(tmp_path, changed=("src/other.py",), diff=quoted)
    assert verdict.verdict == "REFUSED"
    assert "OUT_OF_SCOPE_PATH" in codes(verdict) and "DIFF_UNPARSABLE" in codes(verdict)


# ------------------------------------------------------------------ Windows path tricks
TRICKS = [
    "../outside.py", "src/../src/app.py", "src/./app.py", "src//app.py",
    "src/app.py::$DATA", "src/app.py:stream", "src/app.py.", "src/app.py ", "src /app.py",
    "src/PROGRA~1/x.py", "src/GIT~1/config", "src/NUL", "src/nul.txt", "src/CON", "src/com1.py", "src/LPT9.py",
    "src/aux.", "//server/share/x.py", "\\\\server\\share\\x.py", "\\\\?\\C:\\x.py", "C:/x.py", "C:src/app.py",
    "src\\app.py", "/etc/passwd", "src/app<1>.py", "src/a*.py", "src/\u00bd.py",
    "AGENTS.md.", "CLAUDE.md:stream", ".github /x.yml", ".git./config",
]


@pytest.mark.parametrize("path", TRICKS)
def test_path_trick_is_refused(tmp_path, path):
    verdict = run(tmp_path, changed=(path,), allowed=ALLOWED, diff=diff_for(path))
    assert verdict.verdict == "REFUSED", (path, verdict.reasons)
    assert any(code.startswith("PATH_HAZARD_") for code in codes(verdict))


@pytest.mark.parametrize("path", TRICKS)
def test_path_trick_listed_as_allowed_is_refused_not_blocked(tmp_path, path):
    verdict = run(tmp_path, changed=(path,), allowed=(path,), diff=diff_for(path))
    assert verdict.verdict == "REFUSED", (path, verdict.reasons)
    assert "MALFORMED_INPUT" not in codes(verdict)


@pytest.mark.parametrize("path,code", [
    ("src/app.py::$DATA", "PATH_HAZARD_ALTERNATE_DATA_STREAM_OR_DRIVE"),
    ("src/app.py.", "PATH_HAZARD_TRAILING_DOT_OR_SPACE"),
    ("src/PROGRA~1/x.py", "PATH_HAZARD_SHORT_NAME_ALIAS"),
    ("src/NUL", "PATH_HAZARD_RESERVED_DEVICE_NAME"),
    ("//server/share/x.py", "PATH_HAZARD_UNC_PATH"),
    ("../outside.py", "PATH_HAZARD_TRAVERSAL_OR_EMPTY_COMPONENT"),
    ("C:/x.py", "PATH_HAZARD_DRIVE_LETTER"),
    ("src\\app.py", "PATH_HAZARD_BACKSLASH"),
])
def test_path_trick_reports_its_named_hazard(tmp_path, path, code):
    verdict = run(tmp_path, changed=(path,), diff=diff_for(path))
    assert (code, shown(path)) in verdict.reasons


def test_hazardous_allowed_entry_never_matches_and_does_not_block(tmp_path):
    verdict = run(tmp_path, allowed=("../x", "src/app.py::$DATA"))
    assert verdict.verdict == "REFUSED"
    assert codes(verdict) == ["OUT_OF_SCOPE_PATH", "DIFFGATE_OUT_OF_SCOPE_PATH"]


def test_junction_on_a_changed_path_is_refused(tmp_path):
    verdict = run(tmp_path, isolation=make_isolation(tmp_path, links={"src"}))
    assert verdict.verdict == "REFUSED"
    assert codes(verdict) == ["ISOLATION_VIOLATION"]
    assert ("ISOLATION_VIOLATION", "link_and_reparse_point_check_on_changed_paths") in verdict.reasons


# ------------------------------------------------------------------ BLOCKED on bad or missing input
@pytest.mark.parametrize("over", [
    {"changed_paths": None}, {"changed_paths": "src/app.py"}, {"changed_paths": ()}, {"changed_paths": (1,)},
    {"allowed_paths": ()}, {"allowed_paths": ("src/app.py", 3)}, {"protected_paths": "core"}, {"protected_paths": ("..",)},
    {"protected_paths": ("a\\b",)}, {"protected_paths": ("/abs",)}, {"protected_paths": ("",)},
    {"diff_bytes": "text"}, {"diff_bytes": b""}, {"diff_bytes": None},
    {"manifest_sha256": "A" * 64}, {"manifest_sha256": None}, {"base_head": "b" * 39},
    {"candidate_head": "C" * 40}, {"candidate_head": BASE}, {"isolation": "yes"},
])
def test_malformed_input_is_blocked_never_accepted(tmp_path, over):
    args = dict(manifest_sha256=MANIFEST, base_head=BASE, candidate_head=HEAD, changed_paths=("src/app.py",),
                allowed_paths=ALLOWED, protected_paths=(), diff_bytes=diff_for("src/app.py"),
                isolation=make_isolation(tmp_path))
    args.update(over)
    verdict = wg.gate_worker_change(**args)
    assert verdict.verdict == "BLOCKED"
    assert "MALFORMED_INPUT" in codes(verdict)


def test_a_bad_protected_entry_does_not_hide_a_refusal(tmp_path):
    verdict = run(tmp_path, changed=("src/other.py",), protected=("..",))
    assert verdict.verdict == "REFUSED"
    assert "MALFORMED_INPUT" in codes(verdict) and "OUT_OF_SCOPE_PATH" in codes(verdict)


def test_dot_git_is_a_valid_caller_protected_entry(tmp_path):
    assert run(tmp_path, protected=(".git", "x/")).verdict == "ACCEPTED"


def test_unparsable_diff_is_blocked(tmp_path):
    quoted = b'diff --git "a/src/\\303\\251.py" "b/src/\\303\\251.py"\n'
    verdict = run(tmp_path, diff=quoted)
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["DIFF_UNPARSABLE"]
    assert run(tmp_path, diff=b"\xff\xfe not utf8").verdict == "BLOCKED"


def make_response(**over):
    base = dict(
        run_id="run-1", attempt_id="attempt-1", operation_key=operation_key_for("attempt", "run-1", "attempt-1"),
        effect_key="s3-effect-0001", candidate_id="cand-1", candidate_revision="d" * 40,
        manifest_sha256=MANIFEST, epoch=1, fence=1, invocation_id="inv-1", sandbox_run_id="sbx-1",
        state=WorkerState.SUCCEEDED, candidate_head=HEAD, changed_paths=("src/app.py",),
    )
    base.update(over)
    return WorkerResponse(**base)


def run_response(tmp_path, response, **over):
    args = dict(manifest_sha256=MANIFEST, base_head=BASE, allowed_paths=ALLOWED, protected_paths=(),
                diff_bytes=diff_for("src/app.py"), isolation=make_isolation(tmp_path))
    args.update(over)
    return wg.gate_worker_response(response, **args)


def test_worker_response_in_scope_is_accepted(tmp_path):
    assert run_response(tmp_path, make_response()).verdict == "ACCEPTED"


def test_worker_response_out_of_scope_is_refused(tmp_path):
    response = make_response(changed_paths=("src/other.py",))
    verdict = run_response(tmp_path, response, diff_bytes=diff_for("src/other.py"))
    assert verdict.verdict == "REFUSED"
    assert ("OUT_OF_SCOPE_PATH", shown("src/other.py")) in verdict.reasons


@pytest.mark.parametrize("bad", [None, {}, {"changed_paths": ["src/app.py"]}, "SUCCEEDED", 7, object()])
def test_malformed_worker_output_is_blocked(tmp_path, bad):
    verdict = run_response(tmp_path, bad)
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["MALFORMED_WORKER_OUTPUT"]


def test_worker_that_did_not_succeed_is_blocked(tmp_path):
    response = make_response(state=WorkerState.INCONCLUSIVE, candidate_head=None, changed_paths=(),
                             error=WorkerError(WorkerErrorCode.UNAVAILABLE, "pending"))
    verdict = run_response(tmp_path, response)
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["WORKER_NOT_SUCCEEDED"]


def test_response_bound_to_another_manifest_is_blocked(tmp_path):
    verdict = run_response(tmp_path, make_response(manifest_sha256="e" * 64))
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["MANIFEST_MISMATCH"]


# ------------------------------------------------------------------ missing or lying diff gate
def test_diffgate_missing_from_modules_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "tools.vst.diffgate", None)
    verdict = run(tmp_path)
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["DIFFGATE_UNAVAILABLE"]
    assert verdict.diff_evidence is None


def test_diffgate_without_check_diff_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "tools.vst.diffgate", types.ModuleType("tools.vst.diffgate"))
    verdict = run(tmp_path)
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["DIFFGATE_UNAVAILABLE"]


def test_diffgate_loader_error_is_blocked(tmp_path, monkeypatch):
    def broken():
        raise RuntimeError("boom")
    monkeypatch.setattr(wg, "_load_diffgate", broken)
    assert codes(run(tmp_path)) == ["DIFFGATE_UNAVAILABLE"]


def gate_with(check):
    return SimpleNamespace(check_diff=check, is_blocked_path=real_diffgate.is_blocked_path,
                           normalize_path=real_diffgate.normalize_path)


def test_diffgate_exception_or_junk_result_is_blocked(tmp_path, monkeypatch):
    def raises(**_):
        raise ValueError("x")
    monkeypatch.setattr(wg, "_load_diffgate", lambda: gate_with(raises))
    assert codes(run(tmp_path)) == ["DIFFGATE_ERROR"]
    monkeypatch.setattr(wg, "_load_diffgate", lambda: gate_with(lambda **_: {"verdict": "MAYBE"}))
    assert codes(run(tmp_path)) == ["DIFFGATE_EVIDENCE_MALFORMED"]
    monkeypatch.setattr(wg, "_load_diffgate", lambda: gate_with(lambda **_: "PASS"))
    assert run(tmp_path).verdict == "BLOCKED"


def test_pass_evidence_for_another_candidate_head_is_blocked(tmp_path, monkeypatch):
    lying = {"verdict": "PASS", "candidate_head": "d" * 40, "changed_paths": ["src/app.py"], "reason": "PASS"}
    monkeypatch.setattr(wg, "_load_diffgate", lambda: gate_with(lambda **_: lying))
    verdict = run(tmp_path)
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["DIFFGATE_EVIDENCE_MISMATCH"]


def test_pass_evidence_for_other_paths_is_blocked(tmp_path, monkeypatch):
    lying = {"verdict": "PASS", "candidate_head": HEAD, "changed_paths": ["src/other.py"], "reason": "PASS"}
    monkeypatch.setattr(wg, "_load_diffgate", lambda: gate_with(lambda **_: lying))
    assert codes(run(tmp_path)) == ["DIFFGATE_EVIDENCE_MISMATCH"]


def test_a_gate_fail_result_is_refused_with_its_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(wg, "_load_diffgate", lambda: gate_with(
        lambda **_: {"verdict": "FAIL", "reason": "OUT_OF_SCOPE_PATH"}))
    verdict = run(tmp_path)
    assert verdict.verdict == "REFUSED"
    assert codes(verdict) == ["DIFFGATE_OUT_OF_SCOPE_PATH"]


# ------------------------------------------------------------------ isolation proof
MUST_STAY_NOT_VERIFIED = {"os_sandbox", "process_containment", "network_enforcement", "worker_identity_separation",
                          "writes_outside_worktree", "resource_limits", "short_name_aliases_on_disk",
                          "check_time_vs_use_time", "rename_and_symlink_evidence_completeness"}
COMPUTED_HERE = {"worktree_separate_from_main_checkout", "paths_normalized",
                 "link_and_reparse_point_check_on_changed_paths"}
CALLER_ONLY = {"base_commit_pinned", "worktree_head_matches_candidate", "network_flag_not_requested"}


def test_proof_separates_verified_caller_asserted_and_not_verified(tmp_path):
    proof = run(tmp_path).isolation_proof
    status = statuses(proof)
    assert proof["isolation_mode"] == "windows-local-no-wsl"
    assert {n for n, v in status.items() if v == "VERIFIED"} == COMPUTED_HERE
    assert {n for n, v in status.items() if v == "CALLER_ASSERTED"} == CALLER_ONLY
    assert {n for n, v in status.items() if v == "NOT_VERIFIED"} == MUST_STAY_NOT_VERIFIED
    assert all(item["detail"] for item in proof["properties"])
    assert proof["candidate_head"] == shown(HEAD)
    assert proof["worktree_head_reported"] == shown(HEAD)
    assert wg.proof_is_honest(proof)


def test_not_verified_items_stay_listed_even_when_the_change_is_refused(tmp_path):
    status = statuses(run(tmp_path, changed=("src/other.py",)).isolation_proof)
    assert {n for n, v in status.items() if v == "NOT_VERIFIED"} == MUST_STAY_NOT_VERIFIED


def test_network_flag_is_described_as_a_flag_not_enforcement(tmp_path):
    items = {i["property"]: i for i in run(tmp_path).isolation_proof["properties"]}
    assert "enforcement is NOT verified" in items["network_flag_not_requested"]["detail"]
    assert "git was not read" in items["base_commit_pinned"]["detail"]


def test_link_check_counts_inspected_components(tmp_path):
    items = {i["property"]: i for i in run(tmp_path).isolation_proof["properties"]}
    assert items["link_and_reparse_point_check_on_changed_paths"]["detail"].startswith("2 path component(s) of 1 path(s)")


def test_promoting_a_proof_entry_is_detected(tmp_path):
    for target in ("os_sandbox", "base_commit_pinned", "network_flag_not_requested", "worktree_head_matches_candidate"):
        proof = run(tmp_path).isolation_proof
        for item in proof["properties"]:
            if item["property"] == target:
                item["status"] = "VERIFIED"
        assert wg.proof_is_honest(proof) is False, target
    assert wg.proof_is_honest({}) is False
    assert wg.proof_is_honest(None) is False


@pytest.mark.parametrize("kwargs,prop", [
    ({"network": True}, "network_flag_not_requested"),
    ({"same_root": True}, "worktree_separate_from_main_checkout"),
    ({"nested": True}, "worktree_separate_from_main_checkout"),
    ({"pinned": "f" * 40}, "base_commit_pinned"),
])
def test_failed_isolation_property_is_refused_and_not_listed_as_verified(tmp_path, kwargs, prop):
    verdict = run(tmp_path, isolation=make_isolation(tmp_path, **kwargs))
    assert verdict.verdict == "REFUSED"
    assert ("ISOLATION_VIOLATION", prop) in verdict.reasons
    assert statuses(verdict.isolation_proof)[prop] == "FAILED"


@pytest.mark.parametrize("head", [None, "f" * 40, "short"])
def test_missing_or_different_worktree_head_is_not_verified_and_blocks(tmp_path, head):
    verdict = run(tmp_path, isolation=make_isolation(tmp_path, head=head))
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["ISOLATION_NOT_VERIFIED"]
    assert statuses(verdict.isolation_proof)["worktree_head_matches_candidate"] == "NOT_VERIFIED"


@pytest.mark.parametrize("kwargs", [{"root_ok": False}, {"with_attributes": False}])
def test_uninspectable_worktree_blocks_and_link_check_is_not_verified(tmp_path, kwargs):
    verdict = run(tmp_path, isolation=make_isolation(tmp_path, **kwargs))
    assert verdict.verdict == "BLOCKED"
    assert ("ISOLATION_NOT_VERIFIED", "link_and_reparse_point_check_on_changed_paths") in verdict.reasons
    assert statuses(verdict.isolation_proof)["link_and_reparse_point_check_on_changed_paths"] == "NOT_VERIFIED"


def test_changed_path_missing_from_the_worktree_leaves_the_link_check_unproven(tmp_path):
    verdict = run(tmp_path, isolation=make_isolation(tmp_path, missing={"app.py"}))
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["ISOLATION_NOT_VERIFIED"]
    assert statuses(verdict.isolation_proof)["link_and_reparse_point_check_on_changed_paths"] == "NOT_VERIFIED"


def test_resolved_path_leaving_the_worktree_is_refused(tmp_path):
    outside = str(tmp_path / "elsewhere" / "app.py")

    def realpath(path):
        return outside if path.endswith("app.py") else os.path.realpath(path)

    verdict = run(tmp_path, isolation=make_isolation(tmp_path, realpath=realpath))
    assert verdict.verdict == "REFUSED"
    assert ("ISOLATION_VIOLATION", "link_and_reparse_point_check_on_changed_paths") in verdict.reasons


@pytest.mark.skipif(os.name != "nt", reason="drive letters exist only on Windows")
def test_roots_on_different_drives_are_disjoint(tmp_path):
    def realpath(path):
        return "C:\\wt" if path.endswith("worktree") else ("D:\\main" if path.endswith("main") else os.path.realpath(path))

    proof = run(tmp_path, isolation=make_isolation(tmp_path, realpath=realpath)).isolation_proof
    assert statuses(proof)["worktree_separate_from_main_checkout"] == "VERIFIED"


def test_non_boolean_network_flag_is_not_verified(tmp_path):
    verdict = run(tmp_path, isolation=make_isolation(tmp_path, network="no"))
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["ISOLATION_NOT_VERIFIED"]
    assert statuses(verdict.isolation_proof)["network_flag_not_requested"] == "NOT_VERIFIED"
