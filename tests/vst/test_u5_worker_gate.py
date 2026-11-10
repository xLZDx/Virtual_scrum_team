"""U5-1: worker adapter output through the deterministic diff gate (Windows-local, no WSL).

Acceptance text: "The S3 worker adapter output passes through the deterministic diff gate on
Windows-local isolation; an out-of-scope or protected-path change is refused; the isolation
proof states what is and is not verified."

Synthetic data only; no real git repository and no network. The product code is not patched,
except that "diff gate missing" is simulated by removing the module from sys.modules.
"""

from __future__ import annotations

import os
import stat
import sys
import types
from types import SimpleNamespace

import pytest

from tools.vst import worker_gate as wg
from tools.vst.worker_adapter import (
    WorkerError, WorkerErrorCode, WorkerResponse, WorkerState, operation_key_for,
)

MANIFEST = "a" * 64
BASE = "b" * 40
HEAD = "c" * 40
ALLOWED = ("src/app.py",)


def make_isolation(tmp_path, *, links=(), network=False, pinned=BASE, root_ok=True,
                   with_attributes=True, same_root=False, nested=False):
    worktree = str(tmp_path / "worktree")
    main = worktree if same_root else (os.path.join(worktree, "main") if nested else str(tmp_path / "main"))

    def lstat(path):
        if root_ok and os.path.normcase(path) == os.path.normcase(worktree):
            info = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755)
            if with_attributes:
                info.st_file_attributes = 0
            return info
        if os.path.basename(path) in links:
            return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_file_attributes=0x400)
        raise FileNotFoundError(path)

    return wg.IsolationContext(worktree, main, network, pinned, lstat=lstat)


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


# ------------------------------------------------------------------ accepted and out of scope
def test_in_scope_change_is_accepted_with_gate_evidence(tmp_path):
    verdict = run(tmp_path)
    assert verdict.verdict == "ACCEPTED"
    assert codes(verdict) == ["DIFFGATE_PASS"]
    assert verdict.diff_evidence["verdict"] == "PASS"
    assert verdict.diff_evidence["changed_paths"] == ["src/app.py"]
    assert verdict.diff_evidence["candidate_head"] == HEAD
    assert verdict.to_dict()["verdict"] == "ACCEPTED"


def test_out_of_scope_change_is_refused(tmp_path):
    verdict = run(tmp_path, changed=("src/app.py", "src/other.py"))
    assert verdict.verdict == "REFUSED"
    assert ("OUT_OF_SCOPE_PATH", "src/other.py") in verdict.reasons
    assert "DIFFGATE_OUT_OF_SCOPE_PATH" in codes(verdict)


def test_case_variant_of_an_allowed_path_is_refused(tmp_path):
    verdict = run(tmp_path, changed=("SRC/APP.PY",))
    assert verdict.verdict == "REFUSED"
    assert ("CASE_VARIANT_OF_ALLOWED_PATH", "SRC/APP.PY") in verdict.reasons


# ------------------------------------------------------------------ protected paths
@pytest.mark.parametrize("path", [
    ".git/config", ".GIT/config", ".github/workflows/ci.yml", ".Github/x.yml", ".harness/ledger.json",
    ".claude/settings.json", "AGENTS.md", "agents.md", "CLAUDE.md", "sub/.git/hooks/pre-commit",
    "package-lock.json", "hooks/pre-push", "pyproject.toml", ".gitmodules",
])
def test_protected_path_is_refused_even_when_listed_as_allowed(tmp_path, path):
    verdict = run(tmp_path, changed=(path,), allowed=(path,))
    assert verdict.verdict == "REFUSED"
    assert ("PROTECTED_PATH", path) in verdict.reasons


@pytest.mark.parametrize("path", ["tools/vst/gate.py", "TOOLS/VST/gate.py", "core/DECISION_LOG.md"])
def test_caller_protected_entries_are_refused_case_insensitively(tmp_path, path):
    verdict = run(tmp_path, changed=(path,), allowed=(path,), protected=("tools/vst", "core/"))
    assert verdict.verdict == "REFUSED"
    assert ("PROTECTED_PATH", path) in verdict.reasons


def test_rename_into_protected_path_is_refused(tmp_path):
    diff = (b"diff --git a/src/app.py b/.github/ci.yml\nsimilarity index 100%\n"
            b"rename from src/app.py\nrename to .github/ci.yml\n")
    verdict = run(tmp_path, changed=("src/app.py", ".github/ci.yml"), allowed=("src/app.py", ".github/ci.yml"), diff=diff)
    assert verdict.verdict == "REFUSED"
    assert ("PROTECTED_PATH", ".github/ci.yml") in verdict.reasons


def test_symlink_mode_change_is_refused(tmp_path):
    diff = (b"diff --git a/src/app.py b/src/app.py\nnew file mode 120000\nindex 0000000..2222222\n"
            b"--- /dev/null\n+++ b/src/app.py\n@@ -0,0 +1 @@\n+target\n")
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "REFUSED"
    assert "DIFFGATE_SYMLINK_CHANGE" in codes(verdict)


def test_submodule_change_is_refused(tmp_path):
    diff = (b"diff --git a/src/app.py b/src/app.py\nnew file mode 160000\nindex 0000000..2222222\n"
            b"--- /dev/null\n+++ b/src/app.py\n@@ -0,0 +1 @@\n+Subproject commit 1\n")
    assert run(tmp_path, diff=diff).verdict == "REFUSED"


def test_understated_changed_paths_are_refused(tmp_path):
    diff = diff_for("src/app.py", "src/hidden.py")
    verdict = run(tmp_path, diff=diff)
    assert verdict.verdict == "REFUSED"
    assert "DIFF_PATH_MISMATCH" in codes(verdict)


# ------------------------------------------------------------------ Windows path tricks
TRICKS = [
    "../outside.py", "src/../src/app.py", "src/./app.py", "src//app.py",
    "src/app.py::$DATA", "src/app.py:stream", "src/app.py.", "src/app.py ", "src /app.py",
    "src/PROGRA~1/x.py", "src/GIT~1/config", "src/NUL", "src/nul.txt", "src/CON", "src/com1.py", "src/LPT9.py",
    "src/aux.", "//server/share/x.py", "\\\\server\\share\\x.py", "\\\\?\\C:\\x.py", "C:/x.py", "C:src/app.py",
    "src\\app.py", "/etc/passwd", "src/app<1>.py", "src/a*.py", "src/\u00bd.py",
]


@pytest.mark.parametrize("path", TRICKS)
def test_path_trick_is_refused(tmp_path, path):
    verdict = run(tmp_path, changed=(path,), allowed=ALLOWED, diff=diff_for(path))
    assert verdict.verdict == "REFUSED", (path, verdict.reasons)
    assert any(code.startswith("PATH_HAZARD_") or code == "OUT_OF_SCOPE_PATH" for code in codes(verdict))


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
    assert (code, path) in verdict.reasons


def test_junction_on_a_changed_path_is_refused(tmp_path):
    verdict = run(tmp_path, isolation=make_isolation(tmp_path, links={"src"}))
    assert verdict.verdict == "REFUSED"
    assert ("ISOLATION_VIOLATION", "link_and_reparse_point_check_on_changed_paths") in verdict.reasons


# ------------------------------------------------------------------ BLOCKED on bad or missing input
@pytest.mark.parametrize("over", [
    {"changed_paths": None}, {"changed_paths": "src/app.py"}, {"changed_paths": ()}, {"changed_paths": (1,)},
    {"allowed_paths": ()}, {"allowed_paths": ("../x",)}, {"protected_paths": "core"}, {"protected_paths": ("..",)},
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


def test_unparsable_diff_is_blocked(tmp_path):
    quoted = b'diff --git "a/src/\\303\\251.py" "b/src/\\303\\251.py"\n'
    assert run(tmp_path, diff=quoted).verdict == "BLOCKED"
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


# ------------------------------------------------------------------ missing diff gate
def test_diffgate_missing_from_modules_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "tools.vst.diffgate", None)
    verdict = run(tmp_path)
    assert verdict.verdict == "BLOCKED"
    assert codes(verdict) == ["DIFFGATE_UNAVAILABLE"]
    assert verdict.diff_evidence is None


def test_diffgate_without_check_diff_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "tools.vst.diffgate", types.ModuleType("tools.vst.diffgate"))
    assert run(tmp_path).verdict == "BLOCKED"


def test_diffgate_loader_error_is_blocked(tmp_path, monkeypatch):
    def broken():
        raise RuntimeError("boom")
    monkeypatch.setattr(wg, "_load_diffgate", broken)
    assert run(tmp_path).verdict == "BLOCKED"


def test_diffgate_exception_or_junk_result_is_blocked(tmp_path, monkeypatch):
    real = wg._load_diffgate()

    def gate_with(check):
        return SimpleNamespace(check_diff=check, is_blocked_path=real.is_blocked_path, normalize_path=real.normalize_path)

    def raises(**_):
        raise ValueError("x")
    monkeypatch.setattr(wg, "_load_diffgate", lambda: gate_with(raises))
    assert run(tmp_path).verdict == "BLOCKED"
    monkeypatch.setattr(wg, "_load_diffgate", lambda: gate_with(lambda **_: {"verdict": "MAYBE"}))
    assert run(tmp_path).verdict == "BLOCKED"
    monkeypatch.setattr(wg, "_load_diffgate", lambda: gate_with(lambda **_: "PASS"))
    assert run(tmp_path).verdict == "BLOCKED"


def test_diffgate_cannot_be_overridden_to_accept(tmp_path, monkeypatch):
    real = wg._load_diffgate()
    fake = SimpleNamespace(check_diff=lambda **_: {"verdict": "FAIL", "reason": "OUT_OF_SCOPE_PATH"},
                           is_blocked_path=real.is_blocked_path, normalize_path=real.normalize_path)
    monkeypatch.setattr(wg, "_load_diffgate", lambda: fake)
    assert run(tmp_path).verdict == "REFUSED"


# ------------------------------------------------------------------ isolation proof
MUST_STAY_NOT_VERIFIED = {"os_sandbox", "process_containment", "network_enforcement", "worker_identity_separation"}
MAY_BE_VERIFIED = {"worktree_separate_from_main_checkout", "base_commit_pinned", "network_flag_not_requested",
                   "paths_normalized", "link_and_reparse_point_check_on_changed_paths"}


def statuses(proof):
    return {item["property"]: item["status"] for item in proof["properties"]}


def test_proof_lists_not_verified_items_and_verified_ones_only_for_checked_properties(tmp_path):
    verdict = run(tmp_path)
    proof = verdict.isolation_proof
    status = statuses(proof)
    assert proof["isolation_mode"] == "windows-local-no-wsl"
    for name in MUST_STAY_NOT_VERIFIED:
        assert status[name] == "NOT_VERIFIED"
    assert {name for name, value in status.items() if value == "VERIFIED"} == MAY_BE_VERIFIED
    assert all(item["detail"] for item in proof["properties"])
    assert wg.proof_is_honest(proof)


def test_not_verified_items_stay_listed_even_when_the_change_is_refused(tmp_path):
    proof = run(tmp_path, changed=("src/other.py",)).isolation_proof
    for name in MUST_STAY_NOT_VERIFIED:
        assert statuses(proof)[name] == "NOT_VERIFIED"


def test_network_flag_is_described_as_a_flag_not_enforcement(tmp_path):
    items = {i["property"]: i for i in run(tmp_path).isolation_proof["properties"]}
    assert "enforcement is NOT verified" in items["network_flag_not_requested"]["detail"]


def test_a_tampered_proof_is_not_honest(tmp_path):
    proof = run(tmp_path).isolation_proof
    for item in proof["properties"]:
        if item["property"] == "os_sandbox":
            item["status"] = "VERIFIED"
    assert wg.proof_is_honest(proof) is False
    assert wg.proof_is_honest({}) is False


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


@pytest.mark.parametrize("kwargs", [{"root_ok": False}, {"with_attributes": False}])
def test_uninspectable_worktree_blocks_and_link_check_is_not_verified(tmp_path, kwargs):
    verdict = run(tmp_path, isolation=make_isolation(tmp_path, **kwargs))
    assert verdict.verdict == "BLOCKED"
    assert ("ISOLATION_NOT_VERIFIED", "link_and_reparse_point_check_on_changed_paths") in verdict.reasons
    assert statuses(verdict.isolation_proof)["link_and_reparse_point_check_on_changed_paths"] == "NOT_VERIFIED"


def test_non_boolean_network_flag_is_not_verified(tmp_path):
    verdict = run(tmp_path, isolation=make_isolation(tmp_path, network="no"))
    assert verdict.verdict == "BLOCKED"
    assert statuses(verdict.isolation_proof)["network_flag_not_requested"] == "NOT_VERIFIED"
