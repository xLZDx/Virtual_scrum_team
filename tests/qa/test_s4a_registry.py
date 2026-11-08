"""Functional tests for tools/qa/registry.py and tools/qa/build_registry.py (S4-A).

Tamper, HEAD and builder cases run against throw-away git repositories created
under pytest's tmp_path, so the real repository is never modified. One test
validates the real committed manifest at HEAD.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.qa import registry as reg  # noqa: E402
from tools.qa.build_registry import (  # noqa: E402
    POLICY_NOT_RUN,
    build_registry,
)
from tools.qa.registry import (  # noqa: E402
    RegistryError,
    check_artifact_stage,
    count_passed,
    denominator,
    validate_registry,
)

MANIFEST = "docs/qa/categories.json"
E4 = "tests/vst/test_e4_runner.py"
E5 = "tests/vst/test_e5_process_death.py"
OPREC = "tests/vst/test_s2_operation_recovery.py"
OPREC_SELECTOR = f"{OPREC}::test_recover"
QA_A = "tests/qa/test_s4_functional_a.py"
ADAPTER = "tests/uc/test_adapter.py"
IDENTITY_FILE = "tests/qa/test_s4_functional_worker_identity.py"
LINK_SEL = "tests/vst/test_e4_runner.py::test_link_created_by_the_command_itself_gets_a_zero_digest"
E4_POLICY = sorted(s for s in POLICY_NOT_RUN if s.startswith(E4 + "::"))
E4_NORMAL = f"{E4}::test_normal_run"
QA_A_SELECTORS = {
    f"{QA_A}::test_top",
    f"{QA_A}::TestThing::test_method",
    f"{QA_A}::TestChild::test_inherited",
    f"{QA_A}::TestChild::test_own",
}
ADAPTER_SELECTOR = f"{ADAPTER}::test_one"
E5_SELECTOR = f"{E5}::test_dies"


# ----------------------------------------------------------------- helpers

def git(root: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    done = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
        cwd=root, check=True, capture_output=True, env=env,
    )
    return done.stdout.decode().strip()


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def commit_all(root: Path, message: str = "c") -> str:
    git(root, "add", "-A")
    git(root, "commit", "--allow-empty", "-m", message)
    return git(root, "rev-parse", "HEAD")


def e4_text(omit: str | None = None) -> str:
    names = [s.split("::")[1] for s in E4_POLICY]
    names += [LINK_SEL.split("::")[1], "test_normal_run"]
    return "\n".join(f"def {n}():\n    pass\n" for n in names if n != omit)


QA_A_TEXT = """\
def test_top():
    pass


class TestThing:
    def test_method(self):
        pass

    def helper(self):
        pass


class Base:
    def test_inherited(self):
        pass


class TestChild(Base):
    def test_own(self):
        pass


class NotCollected:
    def test_hidden(self):
        pass


def helper_test():
    pass
"""

IDENTITY_TEXT = (
    "def test_s4_worker_helper_drops_runner_identity_and_denies_runner_sentinels():\n    pass\n"
)


def init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    write(root, QA_A, QA_A_TEXT)
    write(root, ADAPTER, "def test_one():\n    pass\n")
    write(root, E4, e4_text())
    write(root, E5, "def test_dies():\n    pass\n")
    write(root, OPREC, "def test_recover():\n    pass\n")
    write(root, "docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md", "plan\n")
    write(root, "tools/vst/__init__.py", "# evidence\n")
    commit_all(root, "base")


def generate(root: Path) -> dict:
    data = build_registry(root)
    write(root, MANIFEST, json.dumps(data, indent=2) + "\n")
    commit_all(root, "manifest")
    return data


def load(root: Path) -> dict:
    return json.loads((root / MANIFEST).read_text("utf-8"))


def save(root: Path, data: object) -> None:
    write(root, MANIFEST, json.dumps(data, indent=2) + "\n")
    commit_all(root, "tampered manifest")


def put_raw(root: Path, raw: bytes) -> None:
    (root / MANIFEST).write_bytes(raw)
    commit_all(root, "raw manifest")


def tamper(root: Path, fn) -> None:
    data = load(root)
    fn(data)
    save(root, data)


def git_blob(root: Path, rel: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{rel}"], cwd=root, check=True, capture_output=True
    ).stdout


def find_entry(data: dict, selector: str) -> dict:
    return next(t for t in data["tests"] if t["selector"] == selector)


@pytest.fixture(scope="module")
def base_repo(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("base") / "repo"
    init_repo(root)
    generate(root)
    return root


@pytest.fixture
def repo(base_repo: Path, tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    shutil.copytree(base_repo, target)
    return target


@pytest.fixture
def validated(repo: Path):
    return validate_registry(repo)


# ------------------------------------------- happy path: ids and categories

def test_valid_registry_has_one_primary_category_and_stable_id_per_selector(repo: Path):
    registry = validate_registry(repo)
    expected = QA_A_SELECTORS | {ADAPTER_SELECTOR, E5_SELECTOR, OPREC_SELECTOR, LINK_SEL, E4_NORMAL} | set(E4_POLICY)
    assert set(registry.selectors_by_id) == expected
    for test_id, item in registry.selectors_by_id.items():
        assert item["selector"] == test_id  # stable id == canonical selector
        assert item["primary_category"] in reg.PRIMARY_CATEGORIES
    per_category = [i for c in reg.PRIMARY_CATEGORIES for i in registry.category_inventory_ids[c]]
    assert sorted(per_category) == sorted(expected)  # partition: exactly once
    assert len(per_category) == len(set(per_category))
    assert registry.selectors_by_id[ADAPTER_SELECTOR]["primary_category"] == "functional"
    assert registry.selectors_by_id[LINK_SEL]["primary_category"] == "api"
    assert registry.selectors_by_id[E5_SELECTOR]["primary_category"] == "integration"
    # class collection: Test* classes only, inherited methods included, helpers excluded
    assert f"{QA_A}::NotCollected::test_hidden" not in registry.selectors_by_id
    assert f"{QA_A}::Base::test_inherited" not in registry.selectors_by_id


def test_ids_are_deterministic_across_regeneration(repo: Path):
    first = load(repo)
    rebuilt = build_registry(repo)
    assert rebuilt["tests"] == first["tests"]
    assert rebuilt["categories"] == first["categories"]
    assert rebuilt["source_inventory"] == first["source_inventory"]


def test_runtime_profiles_follow_platform_contract_and_policy_not_run(validated):
    profiles = {k: v["runtime_profiles"] for k, v in validated.selectors_by_id.items()}
    assert profiles[LINK_SEL] == [reg.WSL_PROFILE]
    assert profiles[E4_NORMAL] == sorted([reg.WINDOWS_PROFILE, reg.WSL_PROFILE])
    assert profiles[E5_SELECTOR] == []
    assert profiles[OPREC_SELECTOR] == sorted([reg.WINDOWS_PROFILE, reg.WSL_PROFILE])
    for selector in E4_POLICY:
        assert profiles[selector] == []
        assert selector in validated.category_not_run["api"]
    assert validated.category_profile_unassigned_ids["api"][reg.WINDOWS_PROFILE] == sorted(E4_POLICY + [LINK_SEL])


# --------------------------------------------------- HEAD / source binding

def test_registry_binds_to_head_and_source_head_is_ancestor(repo: Path):
    data = load(repo)
    registry = validate_registry(repo)
    assert registry.candidate_head == git(repo, "rev-parse", "HEAD")
    assert data["source_head"] != registry.candidate_head  # manifest commit came after
    git(repo, "merge-base", "--is-ancestor", data["source_head"], registry.candidate_head)
    commit_all(repo, "later unrelated commit")
    later = validate_registry(repo)
    assert later.candidate_head != registry.candidate_head
    assert later.sha256 == registry.sha256  # manifest bytes unchanged


def test_builder_records_current_head_and_per_file_sha256(repo: Path):
    head = git(repo, "rev-parse", "HEAD")
    data = build_registry(repo)
    assert data["source_head"] == head
    by_path = {i["path"]: i for i in data["source_inventory"]}
    assert set(by_path) == {QA_A, ADAPTER, E4, E5, OPREC}
    for path, item in by_path.items():
        assert item["sha256"] == hashlib.sha256((repo / path).read_bytes()).hexdigest()
        assert item["source_commit"] == git(repo, "log", "-1", "--format=%H", "--", path)


def test_non_ancestor_source_head_is_refused(repo: Path):
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    orphan = git(repo, "commit-tree", tree, "-m", "orphan")
    tamper(repo, lambda d: d.__setitem__("source_head", orphan))
    with pytest.raises(RegistryError, match="not an ancestor"):
        validate_registry(repo)


def test_source_head_ahead_of_head_is_refused(repo: Path):
    head = git(repo, "rev-parse", "HEAD")
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    child = git(repo, "commit-tree", tree, "-p", head, "-m", "future")
    tamper(repo, lambda d: d.__setitem__("source_head", child))
    with pytest.raises(RegistryError, match="not an ancestor"):
        validate_registry(repo)


@pytest.mark.parametrize("value", ["0" * 40, "abc", "A" * 40, 123, None])
def test_unresolvable_or_non_canonical_source_head_is_refused(repo: Path, value):
    tamper(repo, lambda d: d.__setitem__("source_head", value))
    with pytest.raises(RegistryError):
        validate_registry(repo)


def test_uncommitted_edit_to_source_file_is_refused(repo: Path):
    (repo / QA_A).write_bytes((repo / QA_A).read_bytes() + b"\ndef test_new():\n    pass\n")
    with pytest.raises(RegistryError, match="uncommitted or untracked"):
        validate_registry(repo)
    git(repo, "add", "-A")  # staged but uncommitted is equally refused
    with pytest.raises(RegistryError, match="uncommitted or untracked"):
        validate_registry(repo)


def test_committed_edit_to_source_file_is_refused(repo: Path):
    write(repo, ADAPTER, "def test_one():\n    assert True\n")
    commit_all(repo, "edit")
    with pytest.raises(RegistryError, match="changed after registry generation"):
        validate_registry(repo)


def test_crlf_committed_source_hashes_like_lf_and_validates(tmp_path: Path):
    lf = tmp_path / "lf"
    crlf = tmp_path / "crlf"
    init_repo(lf)
    init_repo(crlf)
    path = crlf / QA_A
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    commit_all(crlf, "crlf")
    assert b"\r\n" in git_blob(crlf, QA_A)
    data_lf = build_registry(lf)
    data_crlf = build_registry(crlf)
    sha = lambda d: {i["path"]: i["sha256"] for i in d["source_inventory"]}  # noqa: E731
    assert sha(data_lf) == sha(data_crlf)  # line-ending normalization is intended
    generate(crlf)
    assert validate_registry(crlf).selectors_by_id


def test_edit_then_revert_with_same_bytes_is_stale_provenance(repo: Path):
    original = (repo / ADAPTER).read_bytes()
    write(repo, ADAPTER, "def test_one():\n    pass\n# x\n")
    commit_all(repo, "edit")
    (repo / ADAPTER).write_bytes(original)
    commit_all(repo, "revert")
    with pytest.raises(RegistryError, match="provenance is stale"):
        validate_registry(repo)


def test_deleted_source_file_is_refused(repo: Path):
    (repo / ADAPTER).unlink()
    with pytest.raises(RegistryError, match="uncommitted or untracked"):
        validate_registry(repo)
    commit_all(repo, "delete")
    with pytest.raises(RegistryError, match="Git provenance query failed"):
        validate_registry(repo)


def test_new_unregistered_test_module_is_refused(repo: Path):
    write(repo, "tests/qa/test_s4_functional_b.py", "def test_b():\n    pass\n")
    commit_all(repo, "new module")
    with pytest.raises(RegistryError, match="does not cover every committed test module"):
        validate_registry(repo)


def test_unparseable_source_is_refused(repo: Path):
    broken = b"def test_one(:\n"
    (repo / ADAPTER).write_bytes(broken)
    new_commit = commit_all(repo, "break source")

    def fix(d):
        digest = hashlib.sha256(broken).hexdigest()
        item = next(i for i in d["source_inventory"] if i["path"] == ADAPTER)
        item["sha256"], item["source_commit"] = digest, new_commit
        for t in d["tests"]:
            if t["source_path"] == ADAPTER:
                t["source_commit"] = new_commit

    tamper(repo, fix)
    with pytest.raises(RegistryError, match="cannot be statically parsed"):
        validate_registry(repo)


def test_selector_added_to_source_but_not_registry_is_refused(repo: Path):
    # registry carries a fully consistent source hash but one selector too few
    tamper(repo, lambda d: d["tests"].remove(find_entry(d, ADAPTER_SELECTOR)))
    with pytest.raises(RegistryError, match="differs from source"):
        validate_registry(repo)


def test_extra_selector_not_in_source_is_refused(repo: Path):
    def add(d):
        extra = copy.deepcopy(find_entry(d, ADAPTER_SELECTOR))
        extra["selector"] = extra["test_id"] = f"{ADAPTER}::test_ghost"
        d["tests"].append(extra)

    tamper(repo, add)
    with pytest.raises(RegistryError, match="differs from source"):
        validate_registry(repo)


# ------------------------------------------------ manifest structure tamper

def _set(key, value):
    return lambda d: d.__setitem__(key, value)


def _del(key):
    return lambda d: d.pop(key)


TOP_LEVEL_TAMPER = [
    ("schema_version_1", _set("schema_version", 1), "unsupported"),
    ("schema_version_3", _set("schema_version", 3), "unsupported"),
    ("registry_version_1", _set("registry_version", "1"), "unsupported"),
    ("registry_version_int", _set("registry_version", 2), "unsupported"),
    ("registry_version_list", _set("registry_version", ["2"]), "unsupported"),
    ("schema_version_bool", _set("schema_version", True), "unsupported"),
    ("schema_version_float", _set("schema_version", 2.0), "unsupported"),
    ("schema_version_string", _set("schema_version", "2"), "unsupported"),
    ("schema_version_list", _set("schema_version", [2]), "unsupported"),
    ("source_head_list", _set("source_head", ["a" * 40]), "canonical"),
    ("category_status_list", lambda d: d["categories"]["api"].__setitem__("status", []), "status is invalid"),
    ("category_status_dict", lambda d: d["categories"]["api"].__setitem__("status", {}), "status is invalid"),
    ("non_supported_with_ids", lambda d: d["categories"]["functional"].update(status="NOT_RUN", reason="x"), "must have empty test_ids"),
    ("unsupported_with_ids", lambda d: d["categories"]["functional"].update(status="UNSUPPORTED", reason="x"), "must have empty test_ids"),
    ("supported_with_only_not_run_ids", lambda d: d["categories"]["api"]["not_run_reasons"].update({i: "NOT_RUN: x" for i in d["categories"]["api"]["test_ids"]}), "without a runnable selector"),
    ("artifacts_not_object", _set("artifacts", []), "artifact paths"),
    ("profiles_reordered", lambda d: d["runtime_profiles"].reverse(), "runtime profiles"),
    ("profiles_missing", lambda d: d["runtime_profiles"].pop(), "runtime profiles"),
    ("profiles_extra", lambda d: d["runtime_profiles"].append("macos"), "runtime profiles"),
    ("profiles_renamed", lambda d: d["runtime_profiles"].__setitem__(0, "windows-cpython-3.13"), "runtime profiles"),
    ("unknown_top_key", _set("surprise", 1), "expected exact fields"),
    ("missing_aggregates", _del("aggregates"), "expected exact fields"),
    ("missing_tests", _del("tests"), "expected exact fields"),
    ("missing_source_head", _del("source_head"), "expected exact fields"),
    ("artifact_path_changed", lambda d: d["artifacts"]["api"].__setitem__("report", "x.jsonl"), "artifact paths"),
    ("artifact_category_removed", lambda d: d["artifacts"].pop("e2e"), "artifact paths"),
    ("inventory_not_list", _set("source_inventory", {}), "must be a list"),
    ("tests_not_list", _set("tests", {}), "must be a list"),
    ("categories_missing_regression", lambda d: d["categories"].pop("regression"), "categories must declare"),
    ("categories_unknown", lambda d: d["categories"].__setitem__("smoke", {}), "categories must declare"),
    ("category_unknown_field", lambda d: d["categories"]["api"].__setitem__("x", 1), "expected exact fields"),
    ("category_bad_status", lambda d: d["categories"]["api"].__setitem__("status", "GREEN"), "status is invalid"),
    ("supported_without_tests", lambda d: d["categories"]["e2e"].__setitem__("status", "SUPPORTED"), "cannot be SUPPORTED"),
    ("not_run_without_reason", lambda d: d["categories"]["e2e"].__setitem__("reason", " "), "non-approving reason"),
    ("aggregates_order", lambda d: d["aggregates"]["regression_members"].reverse(), "regression_members"),
    ("aggregates_extra_key", lambda d: d["aggregates"].__setitem__("x", 1), "expected exact fields"),
    ("http_supported", lambda d: d["unsupported_apis"]["http"].__setitem__("status", "SUPPORTED"), "UNSUPPORTED"),
    ("http_blank_reason", lambda d: d["unsupported_apis"]["http"].__setitem__("reason", ""), "UNSUPPORTED"),
    ("http_no_evidence", lambda d: d["unsupported_apis"]["http"].__setitem__("evidence_paths", []), "evidence paths"),
    ("http_missing_evidence_file", lambda d: d["unsupported_apis"]["http"]["evidence_paths"].append("docs/nope.md"), "missing"),
    ("http_traversal_evidence", lambda d: d["unsupported_apis"]["http"]["evidence_paths"].append("../x"), "non-canonical"),
    ("http_unknown_key", lambda d: d["unsupported_apis"].__setitem__("grpc", {}), "expected exact fields"),
]


@pytest.mark.parametrize("fn,match", [(f, m) for _, f, m in TOP_LEVEL_TAMPER], ids=[n for n, _, _ in TOP_LEVEL_TAMPER])
def test_tampered_manifest_top_level_is_refused(repo: Path, fn, match):
    tamper(repo, fn)
    with pytest.raises(RegistryError, match=match):
        validate_registry(repo)


def _inv(d, idx=0):
    return d["source_inventory"][idx]


INVENTORY_TAMPER = [
    ("inventory_entry_dropped", lambda d: d["source_inventory"].pop(), "does not cover every"),
    ("inventory_duplicate", lambda d: d["source_inventory"].append(copy.deepcopy(_inv(d))), "duplicate source inventory path"),
    ("inventory_bad_sha_format", lambda d: _inv(d).__setitem__("sha256", "xyz"), "sha256 is invalid"),
    ("inventory_wrong_sha", lambda d: _inv(d).__setitem__("sha256", "0" * 64), "changed after registry generation"),
    ("inventory_upper_sha", lambda d: _inv(d).__setitem__("sha256", _inv(d)["sha256"].upper()), "sha256 is invalid"),
    ("inventory_bad_commit_format", lambda d: _inv(d).__setitem__("source_commit", "abc"), "source_commit is invalid"),
    ("inventory_wrong_commit", lambda d: _inv(d).__setitem__("source_commit", "0" * 40), "provenance is stale"),
    ("inventory_non_test_path", lambda d: _inv(d).__setitem__("path", "tools/vst/__init__.py"), "not a test module"),
    ("inventory_unknown_key", lambda d: _inv(d).__setitem__("extra", 1), "expected exact fields"),
    ("inventory_missing_key", lambda d: _inv(d).pop("sha256"), "expected exact fields"),
    ("inventory_path_int", lambda d: _inv(d).__setitem__("path", 5), "not a test module"),
    ("inventory_item_not_object", lambda d: d["source_inventory"].__setitem__(0, "x"), "expected exact fields"),
    ("inventory_traversal_path", lambda d: _inv(d).__setitem__("path", "tests/../tests/test_x.py"), "non-canonical"),
]


@pytest.mark.parametrize("fn,match", [(f, m) for _, f, m in INVENTORY_TAMPER], ids=[n for n, _, _ in INVENTORY_TAMPER])
def test_tampered_source_inventory_is_refused(repo: Path, fn, match):
    tamper(repo, fn)
    with pytest.raises(RegistryError, match=match):
        validate_registry(repo)


def _t(d, selector=ADAPTER_SELECTOR):
    return find_entry(d, selector)


def _dup_other_category(d):
    other = copy.deepcopy(_t(d))
    other["primary_category"] = "api"
    d["tests"].append(other)


def _move_category_only(d):
    _t(d)["primary_category"] = "api"


def _id_in_two_lists(d):
    d["categories"]["api"]["test_ids"].append(ADAPTER_SELECTOR)


TEST_TAMPER = [
    ("test_unknown_key", lambda d: _t(d).__setitem__("extra", 1), "expected exact fields"),
    ("test_missing_key", lambda d: _t(d).pop("primary_category"), "expected exact fields"),
    ("test_id_differs", lambda d: _t(d).__setitem__("test_id", "other"), "not canonical"),
    ("selector_not_canonical", lambda d: _t(d).update(selector="tests/uc/test_adapter.py::one", test_id="tests/uc/test_adapter.py::one"), "not canonical"),
    ("selector_not_str", lambda d: _t(d).__setitem__("selector", 5), "not canonical"),
    ("duplicate_selector", lambda d: d["tests"].append(copy.deepcopy(_t(d))), "duplicate selector"),
    ("selector_in_two_categories_entries", _dup_other_category, "duplicate selector"),
    ("category_reassigned_without_lists", _move_category_only, "disagree with test assignments"),
    ("id_listed_in_two_categories", _id_in_two_lists, "disagree with test assignments"),
    ("category_list_duplicate_id", lambda d: d["categories"]["functional"]["test_ids"].append(ADAPTER_SELECTOR), "disagree with test assignments"),
    ("primary_category_list", lambda d: _t(d).__setitem__("primary_category", []), "primary category is invalid"),
    ("primary_category_dict", lambda d: _t(d).__setitem__("primary_category", {}), "primary category is invalid"),
    ("primary_category_none", lambda d: _t(d).__setitem__("primary_category", None), "primary category is invalid"),
    ("profiles_contains_int", lambda d: _t(d).__setitem__("runtime_profiles", [1]), "runtime_profiles is invalid"),
    ("profiles_contains_list", lambda d: _t(d).__setitem__("runtime_profiles", [[]]), "runtime_profiles is invalid"),
    ("test_item_not_object", lambda d: d["tests"].__setitem__(0, "x"), "expected exact fields"),
    ("category_ids_non_str", lambda d: d["categories"]["api"]["test_ids"].append(5), "must be a string list"),
    ("invalid_primary_category", lambda d: _t(d).__setitem__("primary_category", "regression"), "primary category is invalid"),
    ("source_path_mismatch", lambda d: _t(d).__setitem__("source_path", E4), "source_path does not match"),
    ("source_commit_stale", lambda d: _t(d).__setitem__("source_commit", "1" * 40), "source_commit is stale"),
    ("profiles_unsorted", lambda d: _t(d).__setitem__("runtime_profiles", [reg.WSL_PROFILE, reg.WINDOWS_PROFILE]), "runtime_profiles is invalid"),
    ("profiles_unknown_name", lambda d: _t(d).__setitem__("runtime_profiles", ["beos"]), "runtime_profiles is invalid"),
    ("profiles_not_list", lambda d: _t(d).__setitem__("runtime_profiles", "all"), "runtime_profiles is invalid"),
    ("profiles_duplicate_entries", lambda d: _t(d).__setitem__("runtime_profiles", [reg.WSL_PROFILE, reg.WSL_PROFILE]), "runtime_profiles is invalid"),
    ("profiles_drop_wsl", lambda d: _t(d).__setitem__("runtime_profiles", [reg.WINDOWS_PROFILE]), "platform contract"),
    ("posix_only_given_windows", lambda d: _t(d, LINK_SEL).__setitem__("runtime_profiles", sorted([reg.WINDOWS_PROFILE, reg.WSL_PROFILE])), "platform contract"),
    ("runnable_with_empty_profiles", lambda d: _t(d).__setitem__("runtime_profiles", []), "policy disagree"),
    ("policy_not_run_given_profiles", lambda d: _t(d, E4_POLICY[0]).__setitem__("runtime_profiles", [reg.WSL_PROFILE]), "platform contract|policy disagree"),
    ("policy_not_run_reason_removed", lambda d: d["categories"]["api"]["not_run_reasons"].pop(E4_POLICY[0]), "policy disagree"),
    ("blank_not_run_reason", lambda d: d["categories"]["api"]["not_run_reasons"].__setitem__(E4_POLICY[0], "  "), "not_run_reasons is invalid"),
    ("not_run_reason_for_foreign_id", lambda d: d["categories"]["api"]["not_run_reasons"].__setitem__(ADAPTER_SELECTOR, "x"), "not_run_reasons is invalid"),
    ("not_run_reason_non_str", lambda d: d["categories"]["api"]["not_run_reasons"].__setitem__(E4_POLICY[0], None), "not_run_reasons is invalid"),
    ("runnable_marked_not_run", lambda d: d["categories"]["functional"]["not_run_reasons"].__setitem__(ADAPTER_SELECTOR, "NOT_RUN: x"), "policy disagree"),
    ("regression_id_dropped", lambda d: d["categories"]["regression"]["test_ids"].pop(), "must exactly aggregate"),
    ("regression_wrong_status", lambda d: d["categories"]["regression"].__setitem__("status", "SUPPORTED"), "must exactly aggregate"),
    ("regression_reason_set", lambda d: d["categories"]["regression"].__setitem__("reason", "x"), "must exactly aggregate"),
    ("regression_not_run_dropped", lambda d: d["categories"]["regression"]["not_run_reasons"].clear(), "must exactly aggregate"),
    ("regression_includes_not_run_id", lambda d: d["categories"]["regression"]["test_ids"].append(E4_POLICY[0]), "must exactly aggregate"),
]


@pytest.mark.parametrize("fn,match", [(f, m) for _, f, m in TEST_TAMPER], ids=[n for n, _, _ in TEST_TAMPER])
def test_tampered_test_assignments_are_refused(repo: Path, fn, match):
    tamper(repo, fn)
    with pytest.raises(RegistryError, match=match):
        validate_registry(repo)


@pytest.mark.parametrize("raw", ["not json", "\xef\xbb\xbf{", "[]", "null", '"s"'])
def test_garbage_manifest_is_refused(repo: Path, raw: str):
    put_raw(repo, raw.encode("utf-8"))
    with pytest.raises(RegistryError):
        validate_registry(repo)


def test_non_utf8_manifest_is_refused(repo: Path):
    put_raw(repo, b"\xff\xfe{}")
    with pytest.raises(RegistryError, match="not valid UTF-8 JSON"):
        validate_registry(repo)


def test_missing_manifest_and_path_escape_are_refused(repo: Path):
    git(repo, "rm", "-q", MANIFEST)
    commit_all(repo, "rm manifest")
    with pytest.raises(RegistryError, match="missing"):
        validate_registry(repo)
    with pytest.raises(RegistryError, match="non-canonical"):
        validate_registry(repo, "../outside.json")
    with pytest.raises(RegistryError, match="non-canonical"):
        validate_registry(repo, "docs\\qa\\categories.json")


def test_directory_outside_a_git_repository_is_refused(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(RegistryError):
        validate_registry(plain)


def test_repository_without_commits_is_refused(tmp_path: Path):
    root = tmp_path / "empty"
    root.mkdir()
    git(root, "init", "-q")
    write(root, MANIFEST, "{}")
    with pytest.raises(RegistryError):
        validate_registry(root)


# ------------------------------------------------------ platform contract

def test_platform_contract_selector_missing_from_present_module_is_refused(tmp_path: Path):
    root = tmp_path / "r"
    init_repo(root)
    # the module is present but lacks the POSIX-only selector named by the contract
    write(root, E4, e4_text(omit=LINK_SEL.split("::")[1]))
    commit_all(root, "drop link test")
    generate(root)
    with pytest.raises(RegistryError, match="platform contract names a selector absent"):
        validate_registry(root)


def test_platform_contract_ignores_modules_not_in_the_tree(tmp_path: Path):
    root = tmp_path / "r"
    init_repo(root)
    (root / E4).unlink()
    commit_all(root, "no e4")
    generate(root)
    registry = validate_registry(root)
    assert LINK_SEL not in registry.selectors_by_id


def test_platform_constants_are_well_formed_and_disjoint():
    groups = [reg.POSIX_ONLY_SELECTORS, reg.WSL_ROOT_ONLY_SELECTORS, reg.WINDOWS_ONLY_SELECTORS]
    for group in groups:
        assert group, "an empty platform constant would silently grant every profile"
        for selector in group:
            assert reg._SELECTOR.fullmatch(selector), selector
    assert not (groups[0] & groups[1]) and not (groups[0] & groups[2]) and not (groups[1] & groups[2])
    assert reg.IDENTITY_SELECTOR in reg.POSIX_ONLY_SELECTORS


def test_required_runtime_profiles_per_constant_group():
    for s in reg.WSL_ROOT_ONLY_SELECTORS:
        assert reg.required_runtime_profiles(s) == [reg.WSL_ROOT_PROFILE]
    for s in reg.POSIX_ONLY_SELECTORS:
        assert reg.required_runtime_profiles(s) == [reg.WSL_PROFILE]
    for s in reg.WINDOWS_ONLY_SELECTORS:
        assert reg.required_runtime_profiles(s) == [reg.WINDOWS_PROFILE]
    assert reg.required_runtime_profiles("tests/x/test_a.py::test_b") == [reg.WINDOWS_PROFILE, reg.WSL_PROFILE]
    assert reg.RUNTIME_PROFILES == (reg.WINDOWS_PROFILE, reg.WSL_PROFILE, reg.WSL_ROOT_PROFILE)


def test_platform_constants_are_registered_as_not_windows_runnable():
    # fail-closed: a POSIX/root only selector must never be assigned to the Windows profile
    for s in reg.POSIX_ONLY_SELECTORS | reg.WSL_ROOT_ONLY_SELECTORS:
        assert reg.WINDOWS_PROFILE not in reg.required_runtime_profiles(s)
    for s in reg.WINDOWS_ONLY_SELECTORS:
        assert reg.WSL_PROFILE not in reg.required_runtime_profiles(s)


# ---------------------------------------------------------------- identity

def test_identity_module_with_exact_selector_is_categorized_identity(tmp_path: Path):
    root = tmp_path / "r"
    init_repo(root)
    write(root, IDENTITY_FILE, IDENTITY_TEXT)
    commit_all(root, "identity")
    generate(root)
    registry = validate_registry(root)
    assert registry.category_inventory_ids["identity"] == [reg.IDENTITY_SELECTOR]
    assert registry.selectors_by_id[reg.IDENTITY_SELECTOR]["runtime_profiles"] == [reg.WSL_PROFILE]


def test_identity_module_with_extra_selector_is_refused(tmp_path: Path):
    root = tmp_path / "r"
    init_repo(root)
    write(root, IDENTITY_FILE, IDENTITY_TEXT + "\ndef test_extra():\n    pass\n")
    commit_all(root, "identity+extra")
    generate(root)
    with pytest.raises(RegistryError, match="identity test module must contain exactly"):
        validate_registry(root)


def test_identity_selector_recategorized_is_refused(tmp_path: Path):
    root = tmp_path / "r"
    init_repo(root)
    write(root, IDENTITY_FILE, IDENTITY_TEXT)
    commit_all(root, "identity")
    generate(root)

    def move(d):
        d["categories"]["identity"]["test_ids"].remove(reg.IDENTITY_SELECTOR)
        d["categories"]["functional"]["test_ids"].append(reg.IDENTITY_SELECTOR)
        d["categories"]["regression"]["test_ids"].append(reg.IDENTITY_SELECTOR)
        find_entry(d, reg.IDENTITY_SELECTOR)["primary_category"] = "functional"

    tamper(root, move)
    with pytest.raises(RegistryError, match="identity category must contain exactly"):
        validate_registry(root)


# ------------------------------------------------------------ qa-tooling

QA_TOOLING_FILE = "tests/qa/test_s4a_registry.py"
QA_TOOLING_SELECTOR = f"{QA_TOOLING_FILE}::test_tool"


@pytest.fixture(scope="module")
def qa_tooling_repo(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("qat") / "repo"
    init_repo(root)
    write(root, QA_TOOLING_FILE, "def test_tool():\n    pass\n")
    commit_all(root, "qa tooling module")
    generate(root)
    return root


def test_qa_tooling_is_outside_regression_and_functional_and_other_categories_are_rejected(
    qa_tooling_repo: Path, tmp_path: Path
):
    registry = validate_registry(qa_tooling_repo)
    assert registry.selectors_by_id[QA_TOOLING_SELECTOR]["primary_category"] == "qa-tooling"
    assert registry.category_inventory_ids["qa-tooling"] == [QA_TOOLING_SELECTOR]
    assert QA_TOOLING_SELECTOR not in registry.category_inventory_ids["functional"]
    data = load(qa_tooling_repo)
    assert data["aggregates"]["regression_members"] == ["functional", "integration", "api", "e2e"]
    assert "qa-tooling" not in data["aggregates"]["regression_members"]
    assert QA_TOOLING_SELECTOR not in data["categories"]["regression"]["test_ids"]
    assert QA_TOOLING_SELECTOR not in data["categories"]["regression"]["not_run_reasons"]
    assert QA_TOOLING_SELECTOR not in data["categories"]["functional"]["test_ids"]
    assert denominator(registry)["regression"] == {"expected": 22, "runnable": 8, "not_run": 14, "complete": False}
    assert denominator(registry)["qa-tooling"] == {"expected": 1, "runnable": 1, "not_run": 0, "complete": True}

    for target in ("functional", "integration", "api", "e2e", "identity", "seeded-failure"):
        root = tmp_path / target
        shutil.copytree(qa_tooling_repo, root)

        def move(d, target=target):
            d["categories"]["qa-tooling"]["test_ids"].remove(QA_TOOLING_SELECTOR)
            d["categories"][target]["test_ids"].append(QA_TOOLING_SELECTOR)
            if target in d["aggregates"]["regression_members"]:
                d["categories"]["regression"]["test_ids"].append(QA_TOOLING_SELECTOR)
            find_entry(d, QA_TOOLING_SELECTOR)["primary_category"] = target

        tamper(root, move)
        with pytest.raises(RegistryError):
            validate_registry(root)


# ------------------------------------------------------------ denominator

def test_denominator_per_category_and_regression_aggregate(validated):
    assert len(E4_POLICY) == 13
    assert denominator(validated) == {
        "api": {"expected": 15, "runnable": 2, "not_run": 13, "complete": False},
        "e2e": {"expected": 0, "runnable": 0, "not_run": 0, "complete": False},
        "functional": {"expected": 5, "runnable": 5, "not_run": 0, "complete": True},
        "identity": {"expected": 0, "runnable": 0, "not_run": 0, "complete": False},
        "integration": {"expected": 2, "runnable": 1, "not_run": 1, "complete": False},
        "qa-tooling": {"expected": 0, "runnable": 0, "not_run": 0, "complete": False},
        "regression": {"expected": 22, "runnable": 8, "not_run": 14, "complete": False},
        "seeded-failure": {"expected": 0, "runnable": 0, "not_run": 0, "complete": False},
    }


def test_denominator_invariant_expected_equals_runnable_plus_not_run(validated):
    for name, row in denominator(validated).items():
        assert row["expected"] == row["runnable"] + row["not_run"], name
        assert row["complete"] == (row["expected"] > 0 and row["not_run"] == 0), name


def test_denominator_empty_category_is_never_complete_and_full_category_is(tmp_path: Path):
    root = tmp_path / "r"
    init_repo(root)
    (root / E4).unlink()
    (root / E5).unlink()
    commit_all(root, "only functional and one integration module")
    generate(root)
    rows = denominator(validate_registry(root))
    assert rows["functional"]["complete"] is True
    assert rows["integration"] == {"expected": 1, "runnable": 1, "not_run": 0, "complete": True}
    assert rows["regression"]["complete"] is True  # every aggregated selector runnable
    assert rows["api"] == {"expected": 0, "runnable": 0, "not_run": 0, "complete": False}
    assert rows["e2e"]["complete"] is False


# ------------------------------------------------------------ count_passed

WIN, WSL, ROOT = reg.WINDOWS_PROFILE, reg.WSL_PROFILE, reg.WSL_ROOT_PROFILE


def _all_passed(registry) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for category in reg.PRIMARY_CATEGORIES:
        for selector in registry.category_test_ids[category]:
            for profile in reg.required_runtime_profiles(selector):
                out.setdefault(profile, {})[selector] = "passed"
    return out


def test_count_passed_all_runnable_passed_keeps_not_run_in_denominator(validated):
    result = count_passed(validated, _all_passed(validated))
    assert result["functional"] == {"expected": 5, "passed": 5, "not_passed": 0, "complete": True}
    assert result["api"] == {"expected": 15, "passed": 2, "not_passed": 13, "complete": False}
    assert result["integration"] == {"expected": 2, "passed": 1, "not_passed": 1, "complete": False}
    assert result["regression"] == {"expected": 22, "passed": 8, "not_passed": 14, "complete": False}
    assert result["e2e"] == {"expected": 0, "passed": 0, "not_passed": 0, "complete": False}


@pytest.mark.parametrize("outcomes", [{}, {WIN: {}}, {WIN: {}, WSL: {}, ROOT: {}}])
def test_count_passed_empty_outcomes_counts_nothing(validated, outcomes):
    result = count_passed(validated, outcomes)
    assert all(row["passed"] == 0 and row["complete"] is False for row in result.values())
    assert result["functional"]["not_passed"] == 5
    assert result["regression"]["not_passed"] == 22


@pytest.mark.parametrize("outcome", ["failed", "skipped", "xfailed", "xpassed", "error", "NOT_RUN", "PASSED", "passed ", "pass", "", "ok"])
@pytest.mark.parametrize("bad_profile", [WIN, WSL])
def test_count_passed_only_exact_passed_in_every_required_profile_counts(validated, outcome: str, bad_profile: str):
    outcomes = {WIN: {ADAPTER_SELECTOR: "passed"}, WSL: {ADAPTER_SELECTOR: "passed"}}
    outcomes[bad_profile][ADAPTER_SELECTOR] = outcome
    result = count_passed(validated, outcomes)
    assert result["functional"] == {"expected": 5, "passed": 0, "not_passed": 5, "complete": False}
    assert result["regression"]["passed"] == 0


@pytest.mark.parametrize("present", [WIN, WSL])
def test_count_passed_selector_needing_two_profiles_is_not_passed_with_one(validated, present: str):
    result = count_passed(validated, {present: {ADAPTER_SELECTOR: "passed"}})
    assert result["functional"]["passed"] == 0
    assert result["regression"]["passed"] == 0


def test_count_passed_both_required_profiles_counts_once(validated):
    result = count_passed(validated, {WIN: {ADAPTER_SELECTOR: "passed"}, WSL: {ADAPTER_SELECTOR: "passed"}})
    assert result["functional"] == {"expected": 5, "passed": 1, "not_passed": 4, "complete": False}
    assert result["api"]["passed"] == 0
    assert result["regression"]["passed"] == 1


def test_count_passed_posix_only_selector_needs_only_wsl_and_ignores_other_profiles(validated):
    assert count_passed(validated, {WSL: {LINK_SEL: "passed"}})["api"]["passed"] == 1
    assert count_passed(validated, {WIN: {LINK_SEL: "passed"}})["api"]["passed"] == 0
    assert count_passed(validated, {WIN: {LINK_SEL: "passed"}, WSL: {LINK_SEL: "failed"}})["api"]["passed"] == 0
    both = {WIN: {LINK_SEL: "failed"}, WSL: {LINK_SEL: "passed"}}  # non-required profile outcome is ignored
    assert count_passed(validated, both)["api"]["passed"] == 1


def test_count_passed_outcomes_under_non_required_profile_cannot_help_or_hurt(validated):
    base = {WIN: {ADAPTER_SELECTOR: "passed"}, WSL: {ADAPTER_SELECTOR: "passed"}}
    assert count_passed(validated, {**base, ROOT: {ADAPTER_SELECTOR: "failed"}})["functional"]["passed"] == 1
    assert count_passed(validated, {ROOT: {ADAPTER_SELECTOR: "passed"}})["functional"]["passed"] == 0


def test_count_passed_policy_not_run_selector_never_counts_even_if_reported_passed(validated):
    outcomes = {p: {E4_POLICY[0]: "passed", E5_SELECTOR: "passed"} for p in (WIN, WSL)}
    result = count_passed(validated, outcomes)
    assert result["api"]["passed"] == 0
    assert result["integration"]["passed"] == 0
    assert result["regression"]["passed"] == 0
    assert result["api"]["not_passed"] == 15


def test_count_passed_complete_is_false_when_partial_even_if_nonempty(validated):
    outcomes = _all_passed(validated)
    del outcomes[WSL][ADAPTER_SELECTOR]
    result = count_passed(validated, outcomes)
    assert result["functional"]["passed"] == 4 and result["functional"]["complete"] is False


def test_count_passed_unknown_selector_raises_in_any_profile(validated):
    ghost = "tests/uc/test_adapter.py::test_ghost"
    for profile in (WIN, WSL, ROOT):
        with pytest.raises(RegistryError, match="absent from the registry"):
            count_passed(validated, {**_all_passed(validated), profile: {ghost: "passed"}})


def test_count_passed_unknown_profile_raises(validated):
    with pytest.raises(RegistryError, match="unknown runtime profile"):
        count_passed(validated, {"macos-arm64": {ADAPTER_SELECTOR: "passed"}})


def test_count_passed_old_flat_shape_raises_instead_of_counting_nothing(validated):
    with pytest.raises(RegistryError):
        count_passed(validated, {ADAPTER_SELECTOR: "passed"})


@pytest.mark.parametrize("bad", [None, True, 1, ["passed"], {"x": "passed"}, b"passed"])
def test_count_passed_non_string_outcome_raises(validated, bad):
    with pytest.raises(RegistryError, match="outcome values must be strings"):
        count_passed(validated, {WIN: {ADAPTER_SELECTOR: bad}})


@pytest.mark.parametrize("bad", [None, [], "x", [(WIN, {})]])
def test_count_passed_malformed_outer_shape_raises(validated, bad):
    with pytest.raises(RegistryError):
        count_passed(validated, bad)


def test_count_passed_malformed_profile_value_raises(validated):
    for bad in (None, [], ["passed"], "passed"):
        with pytest.raises(RegistryError, match="must map selectors to outcomes"):
            count_passed(validated, {WIN: bad})


# ---------------------------------------------------------- artifact stage

def _artifact_paths(data: dict) -> list[str]:
    return [p for c in sorted(data["artifacts"]) for p in data["artifacts"][c].values()]


def test_artifact_stage_skipped_when_no_evidence_exists(repo: Path, validated):
    stage = validated.artifact_stage
    assert stage["status"] == "SKIPPED"
    assert stage["present"] == 0 and stage["expected"] == 24
    assert "not evidence of a passing run" in stage["reason"]


def test_artifact_stage_present_when_all_evidence_exists_is_existence_only(repo: Path):
    for rel in _artifact_paths(load(repo)):
        write(repo, rel, "x\n")
    registry = validate_registry(repo)
    assert registry.artifact_stage == {
        "status": "PRESENT", "scope": "existence-only", "reason": None, "expected": 24, "present": 24,
    }


def test_artifact_stage_all_eight_categories_present_is_present_24_of_24(repo: Path):
    artifacts = load(repo)["artifacts"]
    assert len(artifacts) == 8
    for rel in _artifact_paths(load(repo)):
        write(repo, rel, "x\n")
    stage = check_artifact_stage(repo.resolve(), artifacts)
    assert stage["status"] == "PRESENT"
    assert stage["expected"] == stage["present"] == 24
    assert "categories_absent" not in stage


def test_artifact_stage_one_full_category_with_others_absent_is_partial_not_success(repo: Path):
    artifacts = load(repo)["artifacts"]
    for rel in artifacts["api"].values():
        write(repo, rel, "x\n")
    stage = check_artifact_stage(repo.resolve(), artifacts)
    assert stage["status"] == "PARTIAL" and stage["status"] not in ("PRESENT", "SKIPPED")
    assert stage["categories_present"] == ["api"]
    assert stage["categories_absent"] == sorted(c for c in artifacts if c != "api")
    assert len(stage["categories_absent"]) == 7
    assert stage["present"] == 3 and stage["expected"] == 24
    assert "not evidence of a passing run" in stage["reason"]
    assert validate_registry(repo).artifact_stage["status"] == "PARTIAL"


def test_artifact_stage_category_with_two_of_three_files_is_refused(repo: Path):
    artifacts = load(repo)["artifacts"]
    write(repo, artifacts["api"]["report"], "x\n")
    write(repo, artifacts["api"]["stdout"], "x\n")
    with pytest.raises(RegistryError, match="evidence artifacts of category api are partially present"):
        check_artifact_stage(repo.resolve(), artifacts)


def test_artifact_stage_partial_set_is_refused(repo: Path):
    paths = _artifact_paths(load(repo))
    for rel in paths[:-1]:
        write(repo, rel, "x\n")
    with pytest.raises(RegistryError, match="partially present"):
        validate_registry(repo)
    with pytest.raises(RegistryError, match="partially present"):
        check_artifact_stage(repo.resolve(), load(repo)["artifacts"])


def test_artifact_stage_single_file_is_partial_not_present(repo: Path):
    artifacts = load(repo)["artifacts"]
    write(repo, artifacts["api"]["stderr"], "x\n")
    with pytest.raises(RegistryError, match="partially present"):
        check_artifact_stage(repo.resolve(), artifacts)


def test_artifact_stage_empty_file_is_refused_not_present_and_not_skipped(repo: Path):
    artifacts = load(repo)["artifacts"]
    for rel in _artifact_paths(load(repo)):
        write(repo, rel, "x\n")
    write(repo, artifacts["e2e"]["report"], "")
    with pytest.raises(RegistryError, match="empty"):
        check_artifact_stage(repo.resolve(), artifacts)
    only_empty = {"api": {"report": "only_empty.jsonl", "stdout": "n1", "stderr": "n2"}}
    write(repo, "only_empty.jsonl", "")
    with pytest.raises(RegistryError):  # an empty file must not degrade to "partially absent => SKIPPED"
        check_artifact_stage(repo.resolve(), only_empty)


def test_artifact_stage_unreadable_path_is_an_error_not_absence(repo: Path):
    artifacts = load(repo)["artifacts"]
    (repo / artifacts["api"]["report"]).mkdir(parents=True)  # a directory where a file belongs
    with pytest.raises(RegistryError):
        check_artifact_stage(repo.resolve(), artifacts)


def test_artifact_stage_direct_skipped_and_present(tmp_path: Path):
    root = tmp_path.resolve()
    artifacts = {"api": {"report": "r.jsonl", "stdout": "o.txt", "stderr": "e.txt"}}
    assert check_artifact_stage(root, artifacts)["status"] == "SKIPPED"
    for name in ("r.jsonl", "o.txt", "e.txt"):
        (root / name).write_bytes(b"x")
    assert check_artifact_stage(root, artifacts) == {
        "status": "PRESENT", "scope": "existence-only", "reason": None, "expected": 3, "present": 3,
    }


@pytest.mark.parametrize("artifacts", [
    [],
    "x",
    {"api": "r.jsonl"},
    {"api": {"report": "r", "stdout": "o"}},
    {"api": {"report": 1, "stdout": "o", "stderr": "e"}},
    {"api": {"report": "../r", "stdout": "o", "stderr": "e"}},
    {"api": {"report": "", "stdout": "o", "stderr": "e"}},
    {1: {"report": "r", "stdout": "o", "stderr": "e"}},
])
def test_artifact_stage_malformed_artifacts_raise_registry_error(tmp_path: Path, artifacts):
    with pytest.raises(RegistryError):
        check_artifact_stage(tmp_path.resolve(), artifacts)


# --------------------------------------------------------------- builder

def test_builder_unmapped_test_module_raises(repo: Path):
    write(repo, "tests/vst/test_brand_new_unmapped.py", "def test_a():\n    pass\n")
    commit_all(repo, "unmapped")
    with pytest.raises(ValueError, match="no primary category"):
        build_registry(repo)


def test_builder_qa_module_without_s4_convention_raises(repo: Path):
    write(repo, "tests/qa/test_s4a_misnamed.py", "def test_a():\n    pass\n")
    commit_all(repo, "misnamed")
    with pytest.raises(ValueError, match="test_s4_"):
        build_registry(repo)


def test_builder_categorizes_qa_modules_by_convention(repo: Path):
    for rel in (
        "tests/qa/test_s4_e2e_x.py",
        "tests/qa/test_s4_api_y.py",
        "tests/qa/test_s4_integration_z.py",
        "tests/qa/test_s4_plain.py",
        "tests/qa/test_s4_seeded_failure_q.py",
        "tests/qa/seeded_failure/test_s4_anything.py",
    ):
        write(repo, rel, "def test_a():\n    pass\n")
    commit_all(repo, "qa modules")
    data = build_registry(repo)
    got = {t["source_path"]: t["primary_category"] for t in data["tests"]}
    assert got["tests/qa/test_s4_e2e_x.py"] == "e2e"
    assert got["tests/qa/test_s4_api_y.py"] == "api"
    assert got["tests/qa/test_s4_integration_z.py"] == "integration"
    assert got["tests/qa/test_s4_plain.py"] == "functional"
    assert got["tests/qa/test_s4_seeded_failure_q.py"] == "seeded-failure"
    assert got["tests/qa/seeded_failure/test_s4_anything.py"] == "seeded-failure"
    assert data["categories"]["seeded-failure"]["status"] == "SUPPORTED"
    assert data["categories"]["seeded-failure"]["not_run_reasons"] == {}


def test_builder_stale_policy_not_run_selector_raises(repo: Path):
    missing = E4_POLICY[0].split("::")[1]
    write(repo, E4, e4_text(omit=missing))
    commit_all(repo, "e4 without a policy selector")
    with pytest.raises(ValueError, match="POLICY_NOT_RUN names selectors absent from source") as info:
        build_registry(repo)
    assert E4_POLICY[0] in str(info.value)


def test_builder_policy_for_module_absent_from_tree_is_ignored(repo: Path):
    (repo / E4).unlink()
    commit_all(repo, "no e4")
    data = build_registry(repo)
    assert not any(t["source_path"] == E4 for t in data["tests"])
    assert data["categories"]["api"]["not_run_reasons"] == {}
    assert data["categories"]["api"]["status"] == "NOT_RUN"


def test_builder_refuses_uncommitted_test_module(repo: Path):
    write(repo, "tests/qa/test_s4_functional_c.py", "def test_c():\n    pass\n")
    with pytest.raises(RegistryError, match="uncommitted or untracked"):
        build_registry(repo)


def test_builder_syntax_error_module_raises_registry_error(repo: Path):
    write(repo, "tests/qa/test_s4_functional_bad.py", "def test_x(:\n")
    commit_all(repo, "bad")
    with pytest.raises(RegistryError, match="cannot be statically parsed"):
        build_registry(repo)


def test_builder_policy_and_process_death_selectors_are_not_run_with_empty_profiles(repo: Path):
    data = build_registry(repo)
    api = data["categories"]["api"]
    assert sorted(api["not_run_reasons"]) == E4_POLICY
    assert all(r.startswith("NOT_RUN:") for r in api["not_run_reasons"].values())
    assert find_entry(data, E5_SELECTOR)["runtime_profiles"] == []
    assert E5_SELECTOR in data["categories"]["integration"]["not_run_reasons"]
    assert find_entry(data, E4_NORMAL)["runtime_profiles"] == [reg.WINDOWS_PROFILE, reg.WSL_PROFILE]
    reg_cat = data["categories"]["regression"]
    assert E4_POLICY[0] not in reg_cat["test_ids"] and E4_POLICY[0] in reg_cat["not_run_reasons"]


def test_builder_empty_categories_are_not_run_with_reason_never_supported(repo: Path):
    data = build_registry(repo)
    for name in ("e2e", "identity", "qa-tooling", "seeded-failure"):
        entry = data["categories"][name]
        assert entry["status"] == "NOT_RUN" and entry["test_ids"] == [] and entry["reason"]


def test_builder_output_round_trips_through_validator_even_with_new_module(tmp_path: Path):
    root = tmp_path / "r"
    init_repo(root)
    write(root, "tests/qa/test_s4_e2e_x.py", "class TestX:\n    def test_y(self):\n        pass\n")
    commit_all(root, "e2e module")
    generate(root)
    registry = validate_registry(root)
    assert registry.category_inventory_ids["e2e"] == ["tests/qa/test_s4_e2e_x.py::TestX::test_y"]
    assert denominator(registry)["e2e"] == {"expected": 1, "runnable": 1, "not_run": 0, "complete": True}


# ------------------------------------------------- clean-worktree binding

DIRTY_CASES = [
    ("untracked_in_tests", "tests/qa/notes.txt"),
    ("untracked_in_nested_tests", "tests/vst/sub/deep/new_helper.py"),
    ("untracked_in_docs_qa", "docs/qa/extra.json"),
    ("untracked_in_tools_qa", "tools/qa/new_tool.py"),
]


@pytest.mark.parametrize("fn", [validate_registry, build_registry], ids=["validate", "build"])
@pytest.mark.parametrize("rel", [r for _, r in DIRTY_CASES], ids=[n for n, _ in DIRTY_CASES])
def test_untracked_file_in_guarded_paths_is_refused(repo: Path, fn, rel: str):
    write(repo, rel, "x\n")
    with pytest.raises(RegistryError, match="uncommitted or untracked"):
        fn(repo)


@pytest.mark.parametrize("fn", [validate_registry, build_registry], ids=["validate", "build"])
def test_modified_tracked_file_in_guarded_paths_is_refused(repo: Path, fn):
    (repo / ADAPTER).write_bytes((repo / ADAPTER).read_bytes() + b"# edit\n")
    with pytest.raises(RegistryError, match="uncommitted or untracked"):
        fn(repo)


@pytest.mark.parametrize("rel", ["tests/uc/ignored_fixture.txt", "docs/qa/ignored_note.txt", "tools/qa/ignored_tool.py"])
def test_ignored_file_in_guarded_paths_is_refused(repo: Path, rel: str):
    write(repo, ".gitignore", "ignored_*\n")
    commit_all(repo, "ignore rule")
    write(repo, rel, "x\n")
    assert git(repo, "status", "--porcelain", "--", "tests", "docs/qa", "tools/qa") == ""  # invisible to status
    with pytest.raises(RegistryError, match="ignored"):
        validate_registry(repo)
    with pytest.raises(RegistryError, match="ignored"):
        build_registry(repo)


def test_ignored_bytecode_cache_is_tolerated(repo: Path):
    write(repo, ".gitignore", "__pycache__/\n")
    commit_all(repo, "ignore caches")
    write(repo, "tests/uc/__pycache__/test_adapter.cpython-314.pyc", "x")
    assert validate_registry(repo).selectors_by_id


def test_modified_manifest_in_worktree_is_refused(repo: Path):
    (repo / MANIFEST).write_bytes((repo / MANIFEST).read_bytes() + b" ")
    with pytest.raises(RegistryError, match="uncommitted or untracked"):
        validate_registry(repo)


@pytest.mark.parametrize("fn", [validate_registry, build_registry], ids=["validate", "build"])
def test_dirty_paths_outside_guarded_directories_are_ignored(repo: Path, fn):
    write(repo, "docs/other.md", "x\n")
    write(repo, "src/app.py", "x = 1\n")
    assert fn(repo) is not None


def test_untracked_file_in_a_directory_with_spaces_is_refused(repo: Path):
    write(repo, "tests/qa/dir with space/new file.txt", "x\n")
    with pytest.raises(RegistryError, match="uncommitted or untracked"):
        validate_registry(repo)


@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_index_flags_that_hide_worktree_edits_are_refused(repo: Path, flag: str):
    # these flags hide a working-tree edit from `git status`; the binding must fail closed
    git(repo, "update-index", flag, ADAPTER)
    (repo / ADAPTER).write_bytes(b"def test_one(:\n   garbage that would break hash and parse\n")
    assert git(repo, "status", "--porcelain", "--", "tests") == ""  # the edit really is invisible
    with pytest.raises(RegistryError, match="ignored or hidden paths"):
        validate_registry(repo)
    with pytest.raises(RegistryError, match="ignored or hidden paths"):
        build_registry(repo)


def test_head_blob_that_differs_from_manifest_is_refused_even_if_worktree_matches(repo: Path):
    original = (repo / ADAPTER).read_bytes()
    write(repo, ADAPTER, "def test_one():\n    assert True\n")
    commit_all(repo, "change committed bytes")
    git(repo, "update-index", "--skip-worktree", ADAPTER)
    (repo / ADAPTER).write_bytes(original)  # worktree looks like the manifest's source; HEAD does not
    with pytest.raises(RegistryError):  # hidden flag or changed HEAD blob: never accepted
        validate_registry(repo)
    git(repo, "update-index", "--no-skip-worktree", ADAPTER)
    (repo / ADAPTER).write_bytes(original)
    with pytest.raises(RegistryError):  # without the flag the dirty worktree is refused
        validate_registry(repo)
    git(repo, "checkout", "--", ADAPTER)
    with pytest.raises(RegistryError, match="changed after registry generation"):
        validate_registry(repo)


# --------------------------------------------------- git environment binding

def test_foreign_git_environment_variables_are_ignored(repo: Path, tmp_path: Path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-q")
    write(other, "README", "other\n")
    commit_all(other, "other history")
    expected_head = git(repo, "rev-parse", "HEAD")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git" / "index"))
    registry = validate_registry(repo)
    assert registry.candidate_head == expected_head
    assert build_registry(repo)["source_head"] == expected_head


def test_replace_refs_do_not_change_what_is_hashed(repo: Path):
    blob = git(repo, "rev-parse", f"HEAD:{ADAPTER}")
    fake = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"], cwd=repo, input=b"def test_one():\n    assert False\n",
        check=True, capture_output=True,
    ).stdout.decode().strip()
    git(repo, "replace", blob, fake)
    assert git(repo, "cat-file", "blob", f"HEAD:{ADAPTER}") != ""  # default git would now see the replacement
    assert b"assert False" in subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{ADAPTER}"], cwd=repo, check=True, capture_output=True
    ).stdout
    registry = validate_registry(repo)  # still validates against the original bytes
    assert ADAPTER_SELECTOR in registry.selectors_by_id


# ------------------------------------------------------ strict JSON / types

def test_duplicate_top_level_json_key_is_refused(repo: Path):
    text = (repo / MANIFEST).read_text("utf-8")
    assert text.count('"schema_version": 2') == 1
    put_raw(repo, text.replace('"schema_version": 2', '"schema_version": 2,\n  "schema_version": 2').encode("utf-8"))
    with pytest.raises(RegistryError, match="duplicate JSON key"):
        validate_registry(repo)


def test_duplicate_nested_json_key_hiding_a_value_is_refused(repo: Path):
    text = (repo / MANIFEST).read_text("utf-8")
    needle = '"status": "SUPPORTED",'
    assert needle in text
    put_raw(repo, text.replace(needle, '"status": "NOT_RUN", ' + needle, 1).encode("utf-8"))
    with pytest.raises(RegistryError, match="duplicate JSON key"):
        validate_registry(repo)


def test_deeply_nested_json_is_refused_as_registry_error(repo: Path):
    put_raw(repo, b"[" * 100000 + b"]" * 100000)
    with pytest.raises(RegistryError):
        validate_registry(repo)


# ---------------------------------------------- tests changed after source_head

def test_tests_file_added_after_source_head_without_entry_is_refused(repo: Path):
    write(repo, "tests/vst/helper_data.py", "X = 1\n")  # not a test module, so inventory cannot cover it
    commit_all(repo, "late helper")
    with pytest.raises(RegistryError, match="without a manifest entry"):
        validate_registry(repo)


def test_non_test_helper_that_existed_at_source_head_is_accepted(tmp_path: Path):
    root = tmp_path / "r"
    init_repo(root)
    write(root, "tests/vst/helper_data.py", "X = 1\n")
    commit_all(root, "helper before generation")
    generate(root)
    commit_all(root, "unrelated")
    assert validate_registry(root).selectors_by_id


def test_check_tests_unchanged_since_direct(repo: Path):
    first = git(repo, "rev-parse", "HEAD")
    write(repo, "tests/vst/helper_data.py", "X = 1\n")
    write(repo, ADAPTER, "def test_one():\n    pass\n# x\n")
    head = commit_all(repo, "late")
    root = reg.git_root(repo)
    with pytest.raises(RegistryError, match="without a manifest entry"):
        reg.check_tests_unchanged_since(root, first, head, {ADAPTER})
    reg.check_tests_unchanged_since(root, first, head, {ADAPTER, "tests/vst/helper_data.py"})
    reg.check_tests_unchanged_since(root, head, head, set())


# ------------------------------------------------------- builder category rule

def test_builder_refuses_category_holding_only_not_run_selectors(repo: Path):
    write(repo, E4, "\n".join(f"def {s.split('::')[1]}():\n    pass\n" for s in E4_POLICY))
    commit_all(repo, "e4 with policy selectors only")
    with pytest.raises(RegistryError, match="holds only NOT_RUN selectors"):
        build_registry(repo)


def test_builder_refuses_integration_with_only_process_death_selectors(repo: Path):
    git(repo, "rm", "-q", OPREC)
    commit_all(repo, "drop the only runnable integration module")
    with pytest.raises(RegistryError, match="integration holds only NOT_RUN"):
        build_registry(repo)


def test_validator_accepts_non_supported_category_with_no_ids(validated):
    assert validated.data["categories"]["e2e"]["status"] == "NOT_RUN"
    assert validated.data["categories"]["e2e"]["test_ids"] == []


# ----------------------------------------------------------------- collector

def sel(source: str, path: str = "tests/x/test_m.py") -> set[str]:
    return reg._function_selectors(path, source.encode("utf-8"))


def names(selectors: set[str]) -> set[str]:
    return {s.split("::", 1)[1] for s in selectors}


def test_collector_basic_functions_and_prefixed_classes():
    got = names(sel("def test_a(): pass\nasync def test_b(): pass\ndef helper(): pass\nclass TestC:\n    def test_d(self): pass\n    def e(self): pass\n"))
    assert got == {"test_a", "test_b", "TestC::test_d"}


@pytest.mark.parametrize("header,base", [
    ("import unittest", "unittest.TestCase"),
    ("import unittest as ut", "ut.TestCase"),
    ("from unittest import TestCase", "TestCase"),
    ("from unittest import TestCase as TC", "TC"),
    ("from unittest import IsolatedAsyncioTestCase", "IsolatedAsyncioTestCase"),
    ("import unittest.case", "unittest.case.TestCase"),
    ("import unittest.async_case as ac", "ac.IsolatedAsyncioTestCase"),
    ("from unittest.case import TestCase", "TestCase"),
])
def test_collector_collects_unittest_testcase_subclasses_with_any_name(header: str, base: str):
    got = names(sel(f"{header}\nclass Anything({base}):\n    def test_x(self): pass\n    def helper(self): pass\n"))
    assert got == {"Anything::test_x"}


def test_collector_follows_local_base_chains_and_inherited_methods():
    got = names(sel(
        "import unittest\n"
        "class Mixin:\n    def test_from_mixin(self): pass\n"
        "class Root(unittest.TestCase):\n    def test_root(self): pass\n"
        "class Mid(Root):\n    def test_mid(self): pass\n"
        "class Leaf(Mid, Mixin):\n    def test_leaf(self): pass\n"
    ))
    assert got == {
        "Root::test_root",
        "Mid::test_root", "Mid::test_mid",
        "Leaf::test_root", "Leaf::test_mid", "Leaf::test_leaf", "Leaf::test_from_mixin",
    }


def test_collector_plain_class_without_testcase_or_test_prefix_is_not_collected():
    assert sel("class Helper:\n    def test_x(self): pass\n") == set()
    assert sel("class Helper(object):\n    def test_x(self): pass\n") == set()
    assert sel("class Helper(Exception):\n    def test_x(self): pass\n") == set()


def test_collector_cyclic_local_bases_do_not_hang_or_collect():
    assert names(sel("class A(B):\n    pass\nclass B(A):\n    pass\n")) == set()


@pytest.mark.parametrize("source,why", [
    ("class T(UnknownBase):\n    def test_x(self): pass\n", "unknown base name"),
    ("import foo\nclass T(foo.Base):\n    def test_x(self): pass\n", "attribute base outside unittest"),
    ("from foo import Base\nclass T(Base):\n    def test_x(self): pass\n", "imported base"),
    ("class T(make_base()):\n    def test_x(self): pass\n", "call base"),
    ("class Helper(UnknownBase):\n    pass\n", "unresolved base on a non-test class"),
    ("class TestA:\n    class Inner:\n        def test_x(self): pass\n", "nested class with tests"),
    ("import sys\nif sys.platform == 'win32':\n    def test_x(): pass\n", "if at module level"),
    ("try:\n    import foo\nexcept ImportError:\n    def test_x(): pass\n", "try at module level"),
    ("with open('f') as f:\n    def test_x(): pass\n", "with at module level"),
    ("for i in range(3):\n    def test_x(): pass\n", "for at module level"),
    ("if True:\n    class TestA:\n        def test_x(self): pass\n", "class under module if"),
    ("class TestA:\n    if True:\n        def test_x(self): pass\n", "def under class-level if"),
    ("class TestA:\n    try:\n        def test_x(self): pass\n    except Exception:\n        pass\n", "def under class-level try"),
])
def test_collector_unresolvable_constructs_raise_instead_of_being_skipped(source: str, why: str):
    with pytest.raises(RegistryError, match="cannot be proven statically"):
        sel(source)


def test_collector_harmless_compound_statements_and_nested_helpers_are_allowed():
    got = names(sel(
        "import sys\n"
        "if sys.platform == 'win32':\n    X = 1\n"
        "def test_a():\n    def test_inner(): pass\n"
        "class TestB:\n    class Config:\n        value = 1\n    def test_c(self): pass\n"
    ))
    assert got == {"test_a", "TestB::test_c"}


@pytest.mark.parametrize("raw", [b"def test_x(:\n", b"\xff\xfe", b"x = '\x00'\n"])
def test_collector_unparseable_source_raises_registry_error(raw: bytes):
    with pytest.raises(RegistryError, match="cannot be statically parsed"):
        reg._function_selectors("tests/x/test_m.py", raw)


# --- oracle: the static collector must agree with pytest's own collection

ORACLE_MODULES = {
    "functions": "def test_a():\n    pass\n\n\nasync def test_b():\n    pass\n\n\ndef helper():\n    pass\n",
    "prefixed_class_with_plain_base": (
        "class Base:\n    def test_inh(self):\n        pass\n\n\n"
        "class TestChild(Base):\n    def test_own(self):\n        pass\n\n\n"
        "class NotCollected:\n    def test_hidden(self):\n        pass\n"
    ),
    "unittest_forms": (
        "import unittest\nimport unittest as ut\n"
        "from unittest import TestCase as TC, IsolatedAsyncioTestCase\n\n\n"
        "class One(unittest.TestCase):\n    def test_one(self):\n        pass\n\n\n"
        "class Two(ut.TestCase):\n    def test_two(self):\n        pass\n\n\n"
        "class Three(TC):\n    def test_three(self):\n        pass\n\n\n"
        "class Four(IsolatedAsyncioTestCase):\n    async def test_four(self):\n        pass\n"
    ),
    "local_chains": (
        "import unittest\n\n\n"
        "class Mixin:\n    def test_mix(self):\n        pass\n\n\n"
        "class Root(unittest.TestCase):\n    def test_root(self):\n        pass\n\n\n"
        "class Leaf(Root, Mixin):\n    def test_leaf(self):\n        pass\n\n\n"
        "class TestDeep(Leaf):\n    def test_deep(self):\n        pass\n"
    ),
    "no_test_members": "import unittest\n\n\nclass Empty(unittest.TestCase):\n    def helper(self):\n        pass\n\n\nclass TestNone:\n    x = 1\n",
    "decorated_and_nested_helper": (
        "import functools\n\n\n@functools.lru_cache\ndef test_cached():\n    pass\n\n\n"
        "class TestK:\n    class Config:\n        pass\n\n    @staticmethod\n    def test_static():\n        pass\n"
    ),
}

# Constructs on which the static rules and pytest's default collection disagree.
ORACLE_DIVERGENCES = {
    "plain_class_with_Tests_suffix": "class WidgetTests:\n    def test_w(self):\n        pass\n",
    "test_prefix_without_underscore_function": "def testlower():\n    pass\n",
    "unittest_camel_case_method": "import unittest\n\n\nclass UC(unittest.TestCase):\n    def testCamel(self):\n        pass\n",
    "test_class_with_init_is_not_collected": "class TestInit:\n    def __init__(self):\n        pass\n\n    def test_x(self):\n        pass\n",
}


@pytest.fixture(scope="module")
def pytest_collected(tmp_path_factory) -> dict[str, set[str]]:
    root = tmp_path_factory.mktemp("oracle")
    (root / "tests").mkdir()
    sources = {**ORACLE_MODULES, **ORACLE_DIVERGENCES}
    for name, text in sources.items():
        (root / "tests" / f"test_oracle_{name}.py").write_text(text, encoding="utf-8", newline="\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "--rootdir", str(root), "tests"],
        cwd=root, capture_output=True, env=env, timeout=120,
    )
    assert done.returncode == 0, done.stdout.decode(errors="replace")
    collected: dict[str, set[str]] = {}
    for line in done.stdout.decode().splitlines():
        if line.startswith("tests/") and "::" in line:
            collected.setdefault(line.split("::", 1)[0], set()).add(line.split("[", 1)[0])
    collected["_sources"] = sources  # type: ignore[assignment]
    return collected


def _oracle_pair(collected, name: str) -> tuple[set[str], set[str]]:
    path = f"tests/test_oracle_{name}.py"
    source = collected["_sources"][name]  # type: ignore[index]
    return sel(source, path), collected.get(path, set())


@pytest.mark.parametrize("name", sorted(ORACLE_MODULES))
def test_collector_agrees_with_pytest_collect_only(pytest_collected, name: str):
    static, dynamic = _oracle_pair(pytest_collected, name)
    assert static == dynamic
    assert static or name == "no_test_members"  # the oracle modules are not vacuous


@pytest.mark.parametrize("name", sorted(ORACLE_DIVERGENCES))
def test_collector_agrees_with_pytest_on_edge_constructs(pytest_collected, name: str):
    static, dynamic = _oracle_pair(pytest_collected, name)
    assert static == dynamic


# --------------------------------------------------------- real repository

def test_real_manifest_at_head_validates():
    registry = validate_registry(REPO_ROOT)
    assert registry.candidate_head == git(REPO_ROOT, "rev-parse", "HEAD")
    assert registry.selectors_by_id
    assert "tests/qa/test_s4a_registry.py" in {
        i["path"] for i in registry.data["source_inventory"]
    }, "this test module must be registered (MAIN_TEST_FILE_CATEGORIES) and the manifest regenerated"


def test_real_manifest_contains_selectors_the_old_collector_missed():
    data = json.loads((REPO_ROOT / MANIFEST).read_text("utf-8"))
    ids = {t["test_id"] for t in data["tests"]}
    fidelity = "tests/af/test_s2_review_source_fidelity.py::FixtureGit::"
    assert {i for i in ids if i.startswith(fidelity)} == {
        fidelity + "test_attachment_size_mismatch_fails_closed",
        fidelity + "test_crlf_and_embedded_markdown_fence_map_to_head_blob",
        fidelity + "test_unredacted_mismatch_fails_closed",
    }
    e2e = (
        "tests/vst/test_s2_owner_runner_windows_e2e.py::S2OwnerRunnerWindowsProcessE2E::"
        "test_signed_owner_instruction_completes_in_real_windows_worker_job"
    )
    assert e2e in ids
    assert next(t for t in data["tests"] if t["test_id"] == e2e)["primary_category"] == "e2e"
