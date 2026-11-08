"""U1-6 / U1-7 end-to-end tests: the single entry command `tools/uc/router.py review`.

Real AEVE is invoked at most FIVE times in this module (session fixtures below):
  A  mixed roles on a seeded-defect repository      (fresh state dir S_A)
  B  hostile repository (json.py, aeve/ package)    (fresh state dir S_B)
  C  same request_id, different content, state S_A  (probe only, refused before any review)
  D  fake base_revision of 40 zeros                 (fresh state dir S_D)
  E  identical resubmission of A, state S_A         (retryability)
All other tests are refusals that return before AEVE is touched; they point --aeve-root at a
directory that does not exist, so a test that reached AEVE would fail with a different reason.
"""

from __future__ import annotations

import json
import os
import pathlib
import re

import pytest

from tests.uc_e2e import helpers as h
from tools.uc import contracts

pytestmark = pytest.mark.skipif(not (h.AEVE_ROOT / "src" / "aeve" / "__main__.py").is_file(),
                                reason="AEVE checkout not present")

ROLES_A = ["silent-failure-hunter", "python-reviewer", "code-architect", "functional-test-reviewer",
           "business-analyst", "planner", "zz-unknown-role"]
NO_AEVE = pathlib.Path("D:/nonexistent-aeve-root-for-uc-e2e")


# --------------------------------------------------------------------------- real-call fixtures

class Run:
    def __init__(self, done, doc, state, repo, head, request_doc):
        self.done, self.doc, self.state, self.repo, self.head, self.request_doc = done, doc, state, repo, head, request_doc


def _parsed(done):
    try:
        return json.loads(done.stdout) if done.stdout.strip() else None
    except ValueError:
        return None


@pytest.fixture(scope="session")
def base(tmp_path_factory):
    return tmp_path_factory.mktemp("uc_e2e")


@pytest.fixture(scope="session")
def repo_a(base):
    root = base / "repo_a"
    head = h.make_repo(root, {h.APP_PATH: h.APP_SOURCE})
    return root, head


@pytest.fixture(scope="session")
def run_a(base, repo_a):
    root, head = repo_a
    state = base / "state_a"
    req = h.request(root, head, "uc-e2e-a", ROLES_A, [h.APP_PATH])
    done = h.run_router(req, base / "work_a", state_dir=state, allowed_roots=[str(root)])
    return Run(done, _parsed(done), state, root, head, req)


@pytest.fixture(scope="session")
def sentinel_dir(base):
    path = base / "sentinels"
    path.mkdir()
    return path


@pytest.fixture(scope="session")
def run_b(base, sentinel_dir):
    root = base / "repo_hostile"
    files = h.hostile_files(sentinel_dir)
    head = h.make_repo(root, files)
    state = base / "state_b"
    req = h.request(root, head, "uc-e2e-b", ["silent-failure-hunter"], sorted(files))
    # The orchestrator is started with the hostile repository as its working directory.
    done = h.run_router(req, base / "work_b", state_dir=state, allowed_roots=[str(root)], cwd=root)
    return Run(done, _parsed(done), state, root, head, req)


@pytest.fixture(scope="session")
def run_c(base, run_a):
    """Same request_id as A, different content (different role set); reuses A's state dir."""
    sha_file = run_a.state / "uc-requests" / "uc-e2e-a.sha256"
    before = sha_file.read_text(encoding="utf-8") if sha_file.is_file() else None
    req = h.request(run_a.repo, run_a.head, "uc-e2e-a", ["planner"], [h.APP_PATH])
    done = h.run_router(req, base / "work_c", state_dir=run_a.state, allowed_roots=[str(run_a.repo)])
    after = sha_file.read_text(encoding="utf-8") if sha_file.is_file() else None
    run = Run(done, _parsed(done), run_a.state, run_a.repo, run_a.head, req)
    run.sha_before, run.sha_after = before, after
    return run


@pytest.fixture(scope="session")
def run_d(base, repo_a):
    root, _ = repo_a
    state = base / "state_d"
    req = h.request(root, "0" * 40, "uc-e2e-d", ["silent-failure-hunter"], [h.APP_PATH])
    done = h.run_router(req, base / "work_d", state_dir=state, allowed_roots=[str(root)])
    return Run(done, _parsed(done), state, root, "0" * 40, req)


@pytest.fixture(scope="session")
def run_e(base, run_a):
    """Identical resubmission of A (same id, same content) into A's state dir."""
    done = h.run_router(run_a.request_doc, base / "work_e", state_dir=run_a.state,
                        allowed_roots=[str(run_a.repo)])
    return Run(done, _parsed(done), run_a.state, run_a.repo, run_a.head, run_a.request_doc)


def assert_blocked(run: Run, reason: str | None = None) -> dict:
    assert run.done.returncode == 2, (run.done.returncode, run.done.stdout[-800:], run.done.stderr[-800:])
    assert run.doc is not None, run.done.stderr[-800:]
    contracts.validate_blocked(run.doc)
    assert run.doc["schema_version"] == "uc.blocked.v1" and run.doc["status"] == "BLOCKED"
    if reason is not None:
        assert run.doc["reason"] == reason, run.doc
    return run.doc


def assert_repo_untouched(repo: pathlib.Path, head: str) -> None:
    assert h.git(repo, "rev-parse", "HEAD") == head
    assert h.git(repo, "status", "--porcelain", "--ignored") == "", "review modified or polluted the reviewed repository"


# ------------------------------------------------------------------ scenario 1: mixed roles, real call

class TestMixedRolesRealCall:
    def test_exit_code_three_and_single_json_document(self, run_a):
        assert run_a.done.returncode == 3, (run_a.done.stdout[-1500:], run_a.done.stderr[-1500:])
        assert run_a.doc is not None
        assert "Traceback" not in run_a.done.stderr

    def test_result_validates_against_contract(self, run_a):
        assert run_a.doc is not None, run_a.done.stderr[-1500:]
        doc = contracts.validate_result(run_a.doc)
        assert doc["schema_version"] == "uc.role-result.v1"
        assert doc["exit_code"] == 3
        assert doc["request_id"] == "uc-e2e-a"
        assert doc["base_revision"] == run_a.head
        assert re.fullmatch(r"[0-9a-f]{64}", doc["snapshot_hash"]) and doc["snapshot_hash"] != "0" * 64
        assert [r["role"] for r in doc["roles"]] == ROLES_A

    @pytest.mark.parametrize("name", ["silent-failure-hunter", "python-reviewer"])
    def test_seeded_silent_failure_is_reported_with_path_and_line(self, run_a, name):
        entry = h.role(run_a.doc, name)
        assert entry["status"] == "FINDINGS", entry
        assert entry["class"] == "LOCAL_PLUS_MODEL"
        assert entry["model_residual"] == ["model-judgment"]
        assert [e["id"] for e in entry["executors"]] == ["g2.python-rules"]
        assert entry["executors"][0]["status"] == "COMPLETE"
        assert entry["executors"][0]["snapshot_hash"] == run_a.doc["snapshot_hash"]
        seeded = [f for f in entry["findings"] if f["rule_id"] == "py-silent-except-swallow"]
        assert len(seeded) == 1, entry["findings"]
        finding = seeded[0]
        assert finding["path"] == h.APP_PATH
        assert finding["line"] == h.APP_EXCEPT_LINE
        assert finding["severity"] == "MAJOR"
        assert re.fullmatch(r"[0-9a-f]{64}", finding["evidence_hash"])

    def test_findings_are_deduplicated_per_role(self, run_a):
        for entry in run_a.doc["roles"]:
            keys = [(f["rule_id"], f["path"], f["line"], f["column"]) for f in entry["findings"]]
            assert len(keys) == len(set(keys)), entry["role"]

    def test_code_architect_is_never_clean_and_keeps_model_residual(self, run_a):
        entry = h.role(run_a.doc, "code-architect")
        assert entry["class"] == "LOCAL_PLUS_MODEL"
        assert entry["status"] in ("PARTIAL", "FINDINGS"), entry
        assert entry["model_residual"] == ["model-judgment"]
        assert {e["id"] for e in entry["executors"]} == {
            "g1.python-graph", "g1.python-import-cycles", "g5.dependency-boundary", "g5.layering-shapes"}

    def test_test_role_reports_test_execution_not_available(self, run_a):
        entry = h.role(run_a.doc, "functional-test-reviewer")
        assert "test-execution-not-available" in entry["uncovered"], entry
        assert entry["status"] != "CLEAN"

    def test_test_role_carries_token_never_clean_and_may_report_static_findings_until_u3(self, run_a):
        """U1-6 (reworded): a test role must carry test-execution-not-available, must never be CLEAN,
        and may report FINDINGS from its static part; NOT_COVERED is not required."""
        entry = h.role(run_a.doc, "functional-test-reviewer")
        assert "test-execution-not-available" in entry["uncovered"], entry
        assert entry["status"] != "CLEAN", entry
        assert entry["status"] in ("FINDINGS", "PARTIAL", "NOT_COVERED"), entry
        if entry["status"] == "FINDINGS":
            assert entry["findings"], entry
        assert entry["executors"], "static executors of a covered test role must be listed"

    @pytest.mark.parametrize("name", ["business-analyst", "planner"])
    def test_model_only_roles_are_not_covered_and_never_clean(self, run_a, name):
        entry = h.role(run_a.doc, name)
        assert entry["status"] == "NOT_COVERED"
        assert entry["class"] == "MODEL_ONLY"
        assert entry["executors"] == [] and entry["findings"] == []
        assert entry["uncovered"] == ["model-only"]
        assert entry["model_residual"] == ["authoring"]

    def test_unknown_role_is_not_covered(self, run_a):
        entry = h.role(run_a.doc, "zz-unknown-role")
        assert entry["status"] == "NOT_COVERED"
        assert entry["class"] == "UNKNOWN"
        assert entry["canonical_role"] == "zz-unknown-role"
        assert entry["uncovered"] == ["unknown-role"]
        assert entry["executors"] == [] and entry["findings"] == []

    def test_fake_secret_absent_from_stdout_stderr_and_state(self, run_a):
        assert h.FAKE_SECRET not in run_a.done.stdout
        assert h.FAKE_SECRET not in run_a.done.stderr
        assert "SEEDSECRET" not in run_a.done.stdout + run_a.done.stderr
        assert h.tree_contains(run_a.state, h.FAKE_SECRET) == []

    def test_lock_released_and_request_fingerprint_retained(self, run_a):
        directory = run_a.state / "uc-requests"
        assert (directory / "uc-e2e-a.sha256").is_file()
        assert not (directory / "uc-e2e-a.lock").exists(), "request lock leaked after the run"

    def test_reviewed_repository_is_untouched(self, run_a):
        assert_repo_untouched(run_a.repo, run_a.head)

    def test_aeve_ledger_goes_to_state_dir_not_user_profile(self, run_a):
        written = [p for p in run_a.state.rglob("*") if p.is_file() and "uc-requests" not in p.parts]
        assert written, "AEVE wrote nothing under --state-dir (ledger escaped to the real LOCALAPPDATA?)"


# --------------------------------------------------------------------- scenario 2: hostile repository

class TestHostileRepository:
    def test_review_completes_with_findings(self, run_b):
        assert run_b.done.returncode == 3, (run_b.done.stdout[-1500:], run_b.done.stderr[-1500:])
        doc = contracts.validate_result(run_b.doc)
        entry = h.role(doc, "silent-failure-hunter")
        assert entry["status"] == "FINDINGS"
        assert any(f["path"] == h.APP_PATH and f["line"] == h.APP_EXCEPT_LINE
                   and f["rule_id"] == "py-silent-except-swallow" for f in entry["findings"]), entry["findings"]

    def test_planted_modules_were_not_executed(self, run_b, sentinel_dir):
        assert run_b.done.returncode in (0, 3)  # guard: the sentinel check is meaningless if nothing ran
        assert sorted(p.name for p in sentinel_dir.iterdir()) == []

    def test_reviewed_repository_is_untouched(self, run_b):
        assert_repo_untouched(run_b.repo, run_b.head)

    def test_fake_secret_absent(self, run_b):
        assert h.FAKE_SECRET not in run_b.done.stdout + run_b.done.stderr
        assert h.tree_contains(run_b.state, h.FAKE_SECRET) == []


# ------------------------------------------------------------ scenario 3: refusals needing a real probe

class TestRequestIdAndHead:
    def test_same_request_id_with_different_content_is_refused(self, run_c):
        doc = assert_blocked(run_c, "REQUEST_ID_CONFLICT")
        assert doc["request_id"] == "uc-e2e-a"

    def test_conflict_does_not_overwrite_the_original_fingerprint(self, run_c):
        assert run_c.sha_before is not None and run_c.sha_before == run_c.sha_after

    def test_conflict_leaves_no_lock(self, run_c):
        assert not (run_c.state / "uc-requests" / "uc-e2e-a.lock").exists()

    def test_moved_head_is_blocked_not_a_result(self, run_d):
        doc = assert_blocked(run_d)
        assert doc["request_id"] == "uc-e2e-d"
        assert doc["reason"] in ("HEAD_MOVED", "AEVE_REFUSED"), doc
        assert "roles" not in doc

    def test_moved_head_leaves_no_lock(self, run_d):
        assert not (run_d.state / "uc-requests" / "uc-e2e-d.lock").exists()

    def test_identical_resubmission_is_retryable(self, run_e):
        """PROJECT_PLAN U1-6: 'request_id is retryable'. A second identical run must not be BLOCKED."""
        assert run_e.done.returncode == 3, (run_e.done.returncode, run_e.done.stdout[-1200:], run_e.done.stderr[-600:])
        doc = contracts.validate_result(run_e.doc)
        assert doc["request_id"] == "uc-e2e-a"
        entry = h.role(doc, "silent-failure-hunter")
        assert entry["status"] == "FINDINGS"

    def test_retry_result_matches_first_run_snapshot(self, run_a, run_e):
        assert run_e.doc is not None and run_e.doc.get("schema_version") == "uc.role-result.v1", run_e.doc
        assert run_e.doc["snapshot_hash"] == run_a.doc["snapshot_hash"]


# ------------------------------------------------- scenario 3b: cheap refusals (AEVE never reached)

@pytest.fixture()
def cheap(repo_a, tmp_path):
    root, head = repo_a

    def go(doc, *, roots=None, **kw):
        done = h.run_router(doc, tmp_path, state_dir=tmp_path / "state", allowed_roots=roots or [str(root)],
                            aeve_root=NO_AEVE, **kw)
        return Run(done, _parsed(done), tmp_path / "state", root, head, doc)
    go.root, go.head, go.tmp = root, head, tmp_path
    return go


def good(cheap_fn, **overrides):
    doc = h.request(cheap_fn.root, cheap_fn.head, "uc-cheap", ["silent-failure-hunter"], [h.APP_PATH])
    doc.update(overrides)
    return doc


class TestInvalidRequestsRefusedBeforeAeve:
    def test_root_outside_allowlist(self, cheap, tmp_path_factory):
        other = tmp_path_factory.mktemp("other_root")
        doc = assert_blocked(cheap(good(cheap, root=str(other))), "INVALID_REQUEST")
        assert doc["detail"].startswith("ROOT_NOT_ALLOWED")

    def test_root_that_only_shares_a_prefix_with_the_allowed_root(self, cheap):
        sibling = pathlib.Path(str(cheap.root) + "-evil")
        sibling.mkdir(exist_ok=True)
        doc = assert_blocked(cheap(good(cheap, root=str(sibling))), "INVALID_REQUEST")
        assert doc["detail"].startswith("ROOT_NOT_ALLOWED")

    def test_subdirectory_of_allowed_root_is_not_allowed(self, cheap):
        doc = assert_blocked(cheap(good(cheap, root=str(cheap.root / "src"))), "INVALID_REQUEST")
        assert doc["detail"].startswith("ROOT_NOT_ALLOWED")

    def test_root_with_dotdot_that_escapes_the_allowlist(self, cheap):
        escaping = str(cheap.root / "src" / ".." / "..")
        doc = assert_blocked(cheap(good(cheap, root=escaping)), "INVALID_REQUEST")
        assert doc["detail"].startswith("ROOT_NOT_ALLOWED")

    def test_relative_root(self, cheap):
        doc = assert_blocked(cheap(good(cheap, root="repo")), "INVALID_REQUEST")
        assert doc["detail"].startswith("ROOT_NOT_ABSOLUTE")

    @pytest.mark.parametrize("bad", ["../outside.py", "src/../../outside.py", "/etc/passwd", "C:/Windows/win.ini",
                                     "src\\app.py", "src//app.py", "./src/app.py", "src/app.py ", "src/app.py."])
    def test_path_traversal_and_malformed_paths(self, cheap, bad):
        doc = assert_blocked(cheap(good(cheap, changed_paths=[bad])), "INVALID_REQUEST")
        assert doc["detail"].startswith("BAD_PATH"), doc

    def test_duplicate_changed_path(self, cheap):
        doc = assert_blocked(cheap(good(cheap, changed_paths=[h.APP_PATH, h.APP_PATH])), "INVALID_REQUEST")
        assert doc["detail"].startswith("DUPLICATE_PATH")

    def test_unknown_request_field(self, cheap):
        doc = assert_blocked(cheap(good(cheap, surprise=1)), "INVALID_REQUEST")
        assert doc["detail"].startswith("UNKNOWN_FIELD")

    def test_unknown_field_name_does_not_echo_a_secret(self, cheap):
        """The blocked envelope must not carry caller-supplied text (U1-6: a seeded secret never appears)."""
        run = cheap(good(cheap, **{h.FAKE_SECRET: 1}))
        doc = assert_blocked(run, "INVALID_REQUEST")
        assert h.FAKE_SECRET not in run.done.stdout + run.done.stderr
        assert "SEEDSECRET" not in run.done.stdout + run.done.stderr
        assert doc["detail"] == "UNKNOWN_FIELD at request.[unknown field]"

    def test_missing_required_field(self, cheap):
        doc = good(cheap)
        del doc["purpose"]
        assert assert_blocked(cheap(doc), "INVALID_REQUEST")["detail"].startswith("MISSING_FIELD")

    @pytest.mark.parametrize("overrides,code", [
        ({"purpose": "deploy"}, "NOT_ALLOWED_VALUE"),
        ({"base_revision": "HEAD"}, "BAD_FORMAT"),
        ({"base_revision": "A" * 40}, "BAD_FORMAT"),
        ({"roles": []}, "EMPTY_LIST"),
        ({"roles": ["planner", "planner"]}, "DUPLICATE_ROLE"),
        ({"roles": ["Bad_Role"]}, "BAD_FORMAT"),
        ({"schema_version": "uc.role-request.v2"}, "WRONG_SCHEMA"),
        ({"request_id": "bad id/../x"}, "BAD_FORMAT"),
        ({"iteration_of": "bad id"}, "BAD_FORMAT"),
        ({"criteria": "not-a-list"}, "NOT_A_LIST"),
    ])
    def test_field_level_violations(self, cheap, overrides, code):
        doc = assert_blocked(cheap(good(cheap, **overrides)), "INVALID_REQUEST")
        assert doc["detail"].startswith(code), doc

    def test_invalid_request_id_is_not_echoed(self, cheap):
        doc = assert_blocked(cheap(good(cheap, request_id="bad id/../x")))
        assert doc["request_id"] == "invalid"

    def test_request_that_is_not_an_object(self, cheap, tmp_path):
        path = tmp_path / "list.json"
        path.write_text("[1, 2]", encoding="utf-8")
        run = cheap(None, request_file=path)
        assert assert_blocked(run, "INVALID_REQUEST")["detail"].startswith("NOT_AN_OBJECT")

    def test_symlink_component_in_changed_path(self, cheap, tmp_path_factory):
        root = tmp_path_factory.mktemp("symroot")
        outside = tmp_path_factory.mktemp("symtarget")
        try:
            os.symlink(str(outside), str(root / "link"), target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"cannot create a symlink on this host: {exc}")
        doc = h.request(root, "a" * 40, "uc-sym", ["silent-failure-hunter"], ["link/x.py"])
        run = cheap(doc, roots=[str(root)])
        assert assert_blocked(run, "INVALID_REQUEST")["detail"].startswith("SYMLINK_COMPONENT")


class TestUnreadableRequestAndUsage:
    def test_missing_request_file(self, cheap, tmp_path):
        run = cheap(None, request_file=tmp_path / "does-not-exist.json")
        doc = assert_blocked(run, "UNREADABLE_REQUEST")
        assert doc["request_id"] == "invalid"

    def test_request_file_is_not_json(self, cheap, tmp_path):
        path = tmp_path / "garbage.json"
        path.write_bytes(b"\xff\xfe not json {")
        assert_blocked(cheap(None, request_file=path), "UNREADABLE_REQUEST")

    def test_request_path_is_a_directory(self, cheap, tmp_path):
        assert_blocked(cheap(None, request_file=tmp_path), "UNREADABLE_REQUEST")

    def test_missing_state_dir_is_a_usage_error_with_no_stdout_result(self, cheap):
        doc = good(cheap)
        done = h.run_router(doc, cheap.tmp, state_dir=None, allowed_roots=[str(cheap.root)], aeve_root=NO_AEVE,
                            omit_state_dir=True)
        assert done.returncode == 2
        assert done.stdout.strip() == ""
        assert "--state-dir" in done.stderr and "required" in done.stderr

    def test_missing_allowed_root_is_a_usage_error(self, cheap):
        done = h.run_router(good(cheap), cheap.tmp, state_dir=cheap.tmp / "s", allowed_roots=[], aeve_root=NO_AEVE)
        assert done.returncode == 2 and done.stdout.strip() == ""
        assert "--allowed-root" in done.stderr

    def test_no_state_is_created_for_refused_requests(self, cheap):
        run = cheap(good(cheap, purpose="deploy"))
        assert_blocked(run, "INVALID_REQUEST")
        assert not (run.state / "uc-requests").exists()
