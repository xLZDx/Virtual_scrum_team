"""Functional acceptance for S4 registry, selector, and event accounting contracts."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.qa import build_registry, fixtures, pytest_plugin, registry, run


ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, check=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        shell=False,
    )


def _git_output(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, shell=False,
    )
    return result.stdout.strip()


def _build_candidate_repo(tmp_path: Path, *, include_seeded: bool = True) -> tuple[Path, dict]:
    """Build a tiny committed QA repository so registry checks use real Git provenance."""
    root = tmp_path / "candidate"
    (root / "tests" / "qa").mkdir(parents=True)
    (root / "docs" / "qa").mkdir(parents=True)
    (root / "docs").mkdir(exist_ok=True)
    (root / "tools" / "vst").mkdir(parents=True)

    categories = ("functional", "integration", "api", "e2e")
    if include_seeded:
        categories += ("seeded_failure",)
    for category in categories:
        filename = f"test_s4_{category}_fixture.py"
        (root / "tests" / "qa" / filename).write_bytes(
            "def test_fixture_node():\n    return None\n".encode("utf-8")
        )
    (root / "docs" / "S4_QA_AUTOMATION_PLAN_2026-10-24.md").write_text(
        "# Python API scope\n", encoding="utf-8"
    )
    (root / "tools" / "vst" / "__init__.py").write_text(
        '"""Synthetic VST package marker."""\n', encoding="utf-8"
    )

    _git(root, "init")
    _git(root, "config", "user.name", "S4 functional test")
    _git(root, "config", "user.email", "s4-functional@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "add", "tests", "docs", "tools")
    _git(root, "commit", "-m", "synthetic registry fixture")
    manifest = build_registry.build_registry(root)
    manifest_path = root / "docs" / "qa" / "categories.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return root, manifest


@pytest.fixture
def candidate_repo(tmp_path: Path) -> tuple[Path, dict]:
    return _build_candidate_repo(tmp_path)


def _rewrite_manifest(root: Path, manifest: dict) -> None:
    (root / "docs" / "qa" / "categories.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def test_s4_registry_accepts_real_committed_selector_denominator(candidate_repo):
    root, manifest = candidate_repo

    loaded = registry.validate_registry(root)

    assert loaded.sha256 == hashlib.sha256(
        (root / "docs" / "qa" / "categories.json").read_bytes()
    ).hexdigest()
    assert loaded.candidate_head == manifest["source_head"]
    assert set(loaded.category_inventory_ids) >= {
        "functional", "integration", "api", "e2e", "seeded-failure", "regression"
    }
    assert loaded.category_test_ids["regression"] == sorted(
        test_id
        for category in ("functional", "integration", "api", "e2e")
        for test_id in loaded.category_test_ids[category]
    )


@pytest.mark.parametrize(
    "bad_path",
    [
        "../test_s4_functional_fixture.py",
        "tests/../test_s4_functional_fixture.py",
        "tests\\test_s4_functional_fixture.py",
        "/test_s4_functional_fixture.py",
    ],
)
def test_s4_registry_rejects_noncanonical_source_path(candidate_repo, bad_path):
    root, manifest = candidate_repo
    changed = copy.deepcopy(manifest)
    changed["source_inventory"][0]["path"] = bad_path
    _rewrite_manifest(root, changed)

    with pytest.raises(registry.RegistryError, match="non-canonical repository path|not a test module"):
        registry.validate_registry(root)


def test_s4_registry_rejects_linked_source_path_escape(candidate_repo, tmp_path: Path):
    root, manifest = candidate_repo
    qa_dir = root / "tests" / "qa"
    outside = tmp_path / "outside_qa"
    qa_dir.rename(outside)

    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(qa_dir), str(outside)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )
        if result.returncode != 0:
            pytest.skip(
                "directory junction creation unavailable: "
                f"exit={result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}"
            )
    else:
        try:
            qa_dir.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(
                "directory symlink creation unavailable: "
                f"{type(exc).__name__}: {exc}"
            )

    with pytest.raises(registry.RegistryError, match="source path escapes the repository"):
        registry.validate_registry(root)


def test_s4_registry_rejects_source_changed_after_manifest_digest(candidate_repo):
    root, _ = candidate_repo
    source = root / "tests" / "qa" / "test_s4_functional_fixture.py"
    source.write_text("def test_changed_node():\n    return None\n", encoding="utf-8")

    with pytest.raises(registry.RegistryError, match="test source changed after registry generation"):
        registry.validate_registry(root)


def test_s4_registry_source_digest_is_stable_across_checkout_line_endings(candidate_repo):
    root, manifest = candidate_repo
    source = root / "tests" / "qa" / "test_s4_functional_fixture.py"
    lf_bytes = source.read_bytes()
    assert b"\n" in lf_bytes
    assert b"\r\n" not in lf_bytes

    source.write_bytes(lf_bytes.replace(b"\n", b"\r\n"))

    loaded = registry.validate_registry(root)

    assert loaded.data["source_inventory"] == manifest["source_inventory"]


def test_s4_registry_rejects_source_head_outside_candidate_history(candidate_repo):
    root, manifest = candidate_repo
    tree = _git_output(root, "rev-parse", "HEAD^{tree}")
    unreachable_commit = _git_output(
        root, "commit-tree", tree, "-m", "valid commit outside candidate history"
    )
    changed = copy.deepcopy(manifest)
    changed["source_head"] = unreachable_commit
    _rewrite_manifest(root, changed)

    with pytest.raises(registry.RegistryError, match="source_head is not an ancestor"):
        registry.validate_registry(root)


def test_s4_registry_rejects_duplicate_selector_before_acceptance(candidate_repo):
    root, manifest = candidate_repo
    changed = copy.deepcopy(manifest)
    changed["tests"].append(copy.deepcopy(changed["tests"][0]))
    _rewrite_manifest(root, changed)

    with pytest.raises(registry.RegistryError, match="duplicate selector/test id"):
        registry.validate_registry(root)


def test_s4_registry_rejects_test_assigned_to_wrong_primary_category(candidate_repo):
    root, manifest = candidate_repo
    changed = copy.deepcopy(manifest)
    changed["tests"][0]["primary_category"] = "not-a-primary-category"
    _rewrite_manifest(root, changed)

    with pytest.raises(registry.RegistryError, match="primary category is invalid"):
        registry.validate_registry(root)


def test_s4_registry_rejects_missing_or_unknown_static_selector(candidate_repo):
    root, manifest = candidate_repo
    changed = copy.deepcopy(manifest)
    selector = changed["tests"][0]
    original = selector["test_id"]
    replacement = original.removesuffix("test_fixture_node") + "test_missing_node"
    selector["test_id"] = replacement
    selector["selector"] = replacement
    category = selector["primary_category"]
    changed["categories"][category]["test_ids"].remove(original)
    changed["categories"][category]["test_ids"].append(replacement)
    if category in {"functional", "integration", "api", "e2e"}:
        changed["categories"]["regression"]["test_ids"].remove(original)
        changed["categories"]["regression"]["test_ids"].append(replacement)
        changed["categories"]["regression"]["test_ids"].sort()
    _rewrite_manifest(root, changed)

    with pytest.raises(registry.RegistryError, match="selector inventory differs from source"):
        registry.validate_registry(root)


def test_s4_source_parser_maps_functions_unittest_classes_and_inherited_methods():
    source = b"""
import unittest
import pytest

@pytest.mark.parametrize('value', ['red', 'blue'])
def test_parameterized(value):
    pass

class BaseTests(unittest.TestCase):
    def test_base_case(self):
        pass

class TestChild(BaseTests):
    def test_child_case(self):
        pass
"""

    selectors = registry._function_selectors("tests/qa/test_s4_functional_nodes.py", source)

    assert selectors == {
        "tests/qa/test_s4_functional_nodes.py::test_parameterized",
        "tests/qa/test_s4_functional_nodes.py::BaseTests::test_base_case",
        "tests/qa/test_s4_functional_nodes.py::TestChild::test_base_case",
        "tests/qa/test_s4_functional_nodes.py::TestChild::test_child_case",
    }


def test_s4_plugin_maps_parameter_instances_to_one_registered_function_selector(tmp_path: Path):
    test_path = tmp_path / "tests" / "qa" / "test_parameterized.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("def test_color(value):\n    pass\n", encoding="utf-8")
    selector = "tests/qa/test_parameterized.py::test_color"
    plugin = object.__new__(pytest_plugin._QAPlugin)
    plugin.repo_root = tmp_path.resolve()
    plugin.selector_map = {selector: selector}
    plugin.collected = {}
    plugin.outcomes = {}
    plugin.duplicates = []

    red = SimpleNamespace(
        path=test_path, originalname="test_color", name="test_color[red]",
        cls=None, nodeid="tests/qa/test_parameterized.py::test_color[red]",
    )
    blue = SimpleNamespace(
        path=test_path, originalname="test_color", name="test_color[blue]",
        cls=None, nodeid="tests/qa/test_parameterized.py::test_color[blue]",
    )
    plugin.collect(SimpleNamespace(items=[red, blue]))

    assert plugin.collected[red.nodeid]["selector"] == selector
    assert plugin.collected[blue.nodeid]["selector"] == selector
    assert set(plugin.collected) == {red.nodeid, blue.nodeid}


def test_s4_plugin_maps_unittest_concrete_method_to_class_selector(tmp_path: Path):
    test_path = tmp_path / "tests" / "qa" / "test_unittest_cases.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("class TestSuite:\n    def test_method(self):\n        pass\n", encoding="utf-8")
    selector = "tests/qa/test_unittest_cases.py::TestSuite::test_method"
    plugin = object.__new__(pytest_plugin._QAPlugin)
    plugin.repo_root = tmp_path.resolve()
    plugin.selector_map = {selector: selector}
    plugin.collected = {}
    plugin.outcomes = {}
    plugin.duplicates = []
    item = SimpleNamespace(
        path=test_path, originalname="test_method", name="test_method",
        cls=type("TestSuite", (), {}), nodeid="tests/qa/test_unittest_cases.py::TestSuite::test_method",
    )

    plugin.collect(SimpleNamespace(items=[item]))

    assert plugin.collected[item.nodeid]["selector"] == selector


def test_s4_pytest_command_bounds_argv_for_hundreds_of_selectors(tmp_path: Path):
    scratch_run = tmp_path / "scratch"
    scratch_run.mkdir()
    dependency_target = tmp_path / "dependencies"
    dependency_target.mkdir()
    expected_ids = []
    selectors = {}
    for file_index in range(24):
        source_path = f"tests/qa/test_large_{file_index:02d}.py"
        for test_index in range(20):
            test_id = f"{source_path}::test_case_{test_index:02d}"
            expected_ids.append(test_id)
            selectors[test_id] = {"selector": test_id}
    known_only = "tests/qa/test_policy.py::test_not_run"
    selectors[known_only] = {"selector": known_only}

    argv, _ = run._pytest_command(
        expected_ids=expected_ids,
        selectors=selectors,
        scratch_run=scratch_run,
        repo_root=tmp_path,
        dependency_target=dependency_target,
    )

    selection = json.loads((scratch_run / "selection.json").read_text(encoding="utf-8"))
    source_paths = sorted({test_id.split("::", 1)[0] for test_id in expected_ids})
    assert len(expected_ids) == 480
    assert selection == {
        "schema_version": 2,
        "expected_selectors": {test_id: test_id for test_id in expected_ids},
        "known_selectors": {test_id: row["selector"] for test_id, row in selectors.items()},
    }
    assert argv[-len(source_paths):] == source_paths
    assert len(argv) <= 80
    assert not set(expected_ids).intersection(argv)


def test_s4_plugin_filters_known_other_category_and_policy_but_keeps_unknown(tmp_path: Path):
    repo_root = tmp_path / "repo"
    expected_path = repo_root / "tests" / "qa" / "test_expected.py"
    other_path = repo_root / "tests" / "qa" / "test_other.py"
    policy_path = repo_root / "tests" / "vst" / "test_e4_runner.py"
    unknown_path = repo_root / "tests" / "qa" / "test_unknown.py"
    for path in (expected_path, other_path, policy_path, unknown_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"# synthetic test source\n")

    expected = "tests/qa/test_expected.py::test_expected"
    other_category = "tests/qa/test_other.py::test_other"
    policy_not_run = "tests/vst/test_e4_runner.py::test_timeout_kills_the_whole_process_tree"
    selection_path = tmp_path / "selection.json"
    selection_path.write_text(
        json.dumps({
            "schema_version": 2,
            "expected_selectors": {expected: expected},
            "known_selectors": {
                expected: expected,
                other_category: other_category,
                policy_not_run: policy_not_run,
            },
        }),
        encoding="utf-8",
    )
    options = {
        "--qa-selection-file": str(selection_path),
        "--qa-events-file": str(tmp_path / "events.json"),
        "--qa-repo-root": str(repo_root),
    }
    plugin = pytest_plugin._QAPlugin(SimpleNamespace(getoption=options.__getitem__))

    def item(path: Path, name: str) -> SimpleNamespace:
        return SimpleNamespace(
            path=path, originalname=name, name=name, cls=None,
            nodeid=f"{path.relative_to(repo_root).as_posix()}::{name}",
        )

    expected_item = item(expected_path, "test_expected")
    other_item = item(other_path, "test_other")
    policy_item = item(policy_path, "test_timeout_kills_the_whole_process_tree")
    unknown_item = item(unknown_path, "test_unregistered")

    selected, deselected = plugin.select_items(
        [expected_item, other_item, policy_item, unknown_item]
    )

    assert selected == [expected_item, unknown_item]
    assert deselected == [other_item, policy_item]


def test_s4_resolve_cases_classifies_skipped_xfail_xpass_missing_and_unexpected():
    selectors = {
        "tests/qa/test_runner.py::test_pass": {},
        "tests/qa/test_runner.py::test_skip": {},
        "tests/qa/test_runner.py::test_xfail": {},
        "tests/qa/test_runner.py::test_xpass": {},
        "tests/qa/test_runner.py::test_not_run": {},
    }
    expected = list(selectors)
    rows = [
        {"node_id": "test_runner.py::test_pass[param]", "selector": expected[0], "outcome": "passed"},
        {"node_id": "test_runner.py::test_skip", "selector": expected[1], "outcome": "skipped"},
        {"node_id": "test_runner.py::test_xfail", "selector": expected[2], "outcome": "xfailed"},
        {"node_id": "test_runner.py::test_xpass", "selector": expected[3], "outcome": "xpassed"},
        {"node_id": "test_runner.py::test_not_run", "selector": expected[4], "outcome": "not_run"},
        {"node_id": "test_runner.py::test_unregistered", "selector": "unknown", "outcome": "passed"},
    ]

    accounted = run._resolve_cases(
        {"collected": rows, "duplicates": [], "collection_errors": []}, expected, selectors
    )

    assert accounted["passed_test_ids"] == [expected[0]]
    assert accounted["skipped_test_ids"] == [expected[1]]
    assert accounted["xfail_test_ids"] == [expected[2]]
    assert set(accounted["failed_test_ids"]) == {expected[3], expected[4]}
    assert accounted["unexpected_node_ids"] == ["test_runner.py::test_unregistered"]
    assert accounted["uncollected_test_ids"] == []


def test_s4_resolve_cases_reports_uncollected_required_selector_and_plugin_diagnostics():
    expected = ["tests/qa/test_runner.py::test_required"]

    accounted = run._resolve_cases(
        {
            "collected": [],
            "duplicates": ["duplicate-node"],
            "collection_errors": ["tests/qa/broken.py"],
        },
        expected,
        {expected[0]: {}},
    )

    assert accounted["uncollected_test_ids"] == expected
    assert accounted["duplicates"] == ["duplicate-node"]
    assert accounted["collection_errors"] == ["tests/qa/broken.py"]


def test_s4_resolve_cases_rejects_duplicate_concrete_node_ids():
    row = {"node_id": "node", "selector": "registered", "outcome": "passed"}

    with pytest.raises(run.QARunError, match="invalid or duplicate concrete node IDs"):
        run._resolve_cases({"collected": [row, dict(row)]}, ["registered"], {"registered": {}})


def test_s4_fixture_catalog_requires_hash_and_registered_seed_selector(candidate_repo):
    root, manifest = candidate_repo
    validated = registry.validate_registry(root)
    test_id = validated.category_inventory_ids["seeded-failure"][0]
    input_record = {"contract_version": 2}
    fixture = {
        "fixture_id": "QA-SEED-SYNTHETIC",
        "source_interface": "tools.vst.contracts.validate_task_manifest",
        "input": input_record,
        "input_sha256": fixtures.input_sha256(input_record),
        "expected_rejection": "FAIL",
        "test_id": test_id,
    }
    catalog_path = root / "docs" / "qa" / "fixtures.json"
    catalog = {"schema_version": 1, "status": "SUPPORTED", "reason": None, "fixtures": [fixture]}
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    loaded, digest = fixtures.load_fixture_catalog(root, validated)
    assert loaded == catalog
    assert digest == hashlib.sha256(catalog_path.read_bytes()).hexdigest()

    catalog["fixtures"][0]["input_sha256"] = "0" * 64
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(fixtures.FixtureCatalogError, match="input_sha256 does not match"):
        fixtures.load_fixture_catalog(root, validated)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("unknown-field", "expected exact fields"),
        ("approving-result", "expected_rejection is approving or invalid"),
        ("unregistered-test", "test_id is not a seeded-failure selector"),
    ],
)
def test_s4_fixture_catalog_rejects_malformed_or_approving_rows(candidate_repo, mutation, message):
    root, _ = candidate_repo
    validated = registry.validate_registry(root)
    test_id = validated.category_inventory_ids["seeded-failure"][0]
    input_record = {"contract_version": 2}
    fixture = {
        "fixture_id": "QA-SEED-SYNTHETIC",
        "source_interface": "tools.vst.contracts.validate_task_manifest",
        "input": input_record,
        "input_sha256": fixtures.input_sha256(input_record),
        "expected_rejection": "FAIL",
        "test_id": test_id,
    }
    if mutation == "unknown-field":
        fixture["extra"] = "not allowed"
    elif mutation == "approving-result":
        fixture["expected_rejection"] = "PASS"
    else:
        fixture["test_id"] = "tests/qa/test_s4_seeded_failure_contracts.py::test_unregistered"
    catalog = {"schema_version": 1, "status": "SUPPORTED", "reason": None, "fixtures": [fixture]}
    (root / "docs" / "qa" / "fixtures.json").write_text(json.dumps(catalog), encoding="utf-8")

    error_type = registry.RegistryError if mutation == "unknown-field" else fixtures.FixtureCatalogError
    with pytest.raises(error_type, match=message):
        fixtures.load_fixture_catalog(root, validated)


def test_s4_fixture_observation_is_bound_to_exact_seed_test_node():
    fixture_id = "QA-SEED-SYNTHETIC"
    test_id = "tests/qa/test_s4_seeded_failure_contracts.py::test_fixture"
    node_id = test_id
    catalog = {
        "fixtures": [{
            "fixture_id": fixture_id,
            "input_sha256": "a" * 64,
            "test_id": test_id,
            "expected_rejection": "FAIL",
        }]
    }
    validated = registry.ValidatedRegistry(
        data={}, sha256="b" * 64, candidate_head="c" * 40,
        selectors_by_id={test_id: {"selector": test_id, "primary_category": "seeded-failure"}},
        category_test_ids={"seeded-failure": [test_id]},
        category_inventory_ids={"seeded-failure": [test_id]},
        category_not_run={"seeded-failure": {}},
    )
    events = {
        "collected": [{"node_id": node_id, "selector": test_id, "outcome": "passed"}],
        "fixture_observations": [{
            "fixture_id": fixture_id,
            "test_node_id": node_id,
            "observed_rejection": "FAIL",
        }],
    }

    results, errors = run._fixture_results(catalog, validated, events)

    assert errors == []
    assert results == [{
        "fixture_id": fixture_id,
        "input_sha256": "a" * 64,
        "test_id": test_id,
        "test_node_id": node_id,
        "expected_rejection": "FAIL",
        "observed_rejection": "FAIL",
        "result": "PASS",
    }]


def test_s4_fixture_observation_rejects_wrong_node_binding():
    fixture_id = "QA-SEED-SYNTHETIC"
    test_id = "tests/qa/test_s4_seeded_failure_contracts.py::test_fixture"
    validated = registry.ValidatedRegistry(
        data={}, sha256="b" * 64, candidate_head="c" * 40,
        selectors_by_id={test_id: {"selector": test_id, "primary_category": "seeded-failure"}},
        category_test_ids={"seeded-failure": [test_id]},
        category_inventory_ids={"seeded-failure": [test_id]},
        category_not_run={"seeded-failure": {}},
    )
    catalog = {"fixtures": [{
        "fixture_id": fixture_id, "input_sha256": "a" * 64,
        "test_id": test_id, "expected_rejection": "FAIL",
    }]}
    bad_observation = {
        "fixture_id": fixture_id, "test_node_id": "tests/qa/other.py::test_wrong",
        "observed_rejection": "FAIL",
    }
    events = {
        "collected": [{"node_id": "tests/qa/other.py::test_wrong", "selector": "other", "outcome": "passed"}],
        "fixture_observations": [bad_observation],
    }

    results, errors = run._fixture_results(catalog, validated, events)

    assert results == []
    assert any("observation came from the wrong test" in error for error in errors)


def test_s4_fixture_observation_rejects_duplicate_observation():
    fixture_id = "QA-SEED-SYNTHETIC"
    test_id = "tests/qa/test_s4_seeded_failure_contracts.py::test_fixture"
    node_id = test_id
    validated = registry.ValidatedRegistry(
        data={}, sha256="b" * 64, candidate_head="c" * 40,
        selectors_by_id={test_id: {"selector": test_id, "primary_category": "seeded-failure"}},
        category_test_ids={"seeded-failure": [test_id]},
        category_inventory_ids={"seeded-failure": [test_id]},
        category_not_run={"seeded-failure": {}},
    )
    catalog = {"fixtures": [{
        "fixture_id": fixture_id, "input_sha256": "a" * 64,
        "test_id": test_id, "expected_rejection": "FAIL",
    }]}
    observation = {
        "fixture_id": fixture_id, "test_node_id": node_id, "observed_rejection": "FAIL",
    }
    events = {
        "collected": [{"node_id": node_id, "selector": test_id, "outcome": "passed"}],
        "fixture_observations": [observation, dict(observation)],
    }

    results, errors = run._fixture_results(catalog, validated, events)

    assert results == []
    assert any("observation count is 2" in error for error in errors)


def test_s4_fixture_observation_rejects_a_different_nonapproving_outcome():
    fixture_id = "QA-SEED-SYNTHETIC"
    test_id = "tests/qa/test_s4_seeded_failure_contracts.py::test_fixture"
    validated = registry.ValidatedRegistry(
        data={}, sha256="b" * 64, candidate_head="c" * 40,
        selectors_by_id={test_id: {"selector": test_id, "primary_category": "seeded-failure"}},
        category_test_ids={"seeded-failure": [test_id]},
        category_inventory_ids={"seeded-failure": [test_id]},
        category_not_run={"seeded-failure": {}},
    )
    catalog = {"fixtures": [{
        "fixture_id": fixture_id, "input_sha256": "a" * 64,
        "test_id": test_id, "expected_rejection": "FAIL",
    }]}
    events = {
        "collected": [{"node_id": test_id, "selector": test_id, "outcome": "passed"}],
        "fixture_observations": [{
            "fixture_id": fixture_id,
            "test_node_id": test_id,
            "observed_rejection": "BLOCKED",
        }],
    }

    results, errors = run._fixture_results(catalog, validated, events)

    assert results[0]["result"] == "FAIL"
    assert any("did not observe its expected rejection" in error for error in errors)


@pytest.mark.parametrize(
    "events",
    [
        {},
        {"collected": None},
        {"collected": [{"node_id": "n", "selector": "id", "outcome": "mystery"}]},
        {"collected": [{"selector": "id", "outcome": "passed"}]},
    ],
)
def test_s4_resolve_cases_fails_closed_on_malformed_events(events):
    with pytest.raises(run.QARunError):
        run._resolve_cases(events, ["id"], {"id": {}})


def test_s4_process_death_selectors_are_declared_not_run_by_policy():
    from tools.qa.build_registry import POLICY_NOT_RUN

    death_source = ROOT / "tests" / "vst" / "test_e5_process_death.py"
    death_selectors = registry._function_selectors(
        "tests/vst/test_e5_process_death.py", death_source.read_bytes()
    )
    generated = build_registry.build_registry(ROOT)
    declared_not_run = {
        selector: reason
        for category in generated["categories"].values()
        for selector, reason in category["not_run_reasons"].items()
    }
    e2e_timeout_selector = (
        "tests/qa/test_s4_e2e_runner_cli.py::"
        "test_s4_e2e_cli_timeout_is_nonapproving_without_install_or_fallback"
    )

    assert death_selectors
    assert death_selectors <= declared_not_run.keys()
    assert e2e_timeout_selector in POLICY_NOT_RUN
    assert e2e_timeout_selector in declared_not_run
    assert declared_not_run[e2e_timeout_selector].startswith("NOT_RUN:")
    assert set(POLICY_NOT_RUN) <= declared_not_run.keys()
    assert all(declared_not_run[selector].startswith("NOT_RUN:") for selector in death_selectors | set(POLICY_NOT_RUN))


def test_s4_audited_e4_terminating_selectors_remain_not_run():
    from tools.qa.build_registry import POLICY_NOT_RUN

    audited_terminating_selectors = {
        "tests/vst/test_e4_runner.py::test_timeout_records_exit_minus_one_and_fails",
        "tests/vst/test_e4_runner.py::test_timeout_kills_the_whole_process_tree",
        "tests/vst/test_e4_runner.py::test_overall_deadline_stops_later_commands_without_running_them",
        "tests/vst/test_e4_runner.py::test_deadline_limits_a_command_below_its_own_timeout",
        "tests/vst/test_e4_runner.py::test_timeout_does_not_prevent_following_commands_within_the_deadline",
        "tests/vst/test_e4_runner.py::test_report_capture_incomplete_is_false_for_every_normal_outcome",
        "tests/vst/test_e4_runner.py::test_stray_descendant_is_killed_after_the_root_command_exited_normally",
        "tests/vst/test_e4_runner.py::test_thread_start_failure_kills_the_child_and_cleans_up",
        "tests/vst/test_e4_runner.py::test_thread_start_failure_for_the_first_reader_also_cleans_up",
        "tests/vst/test_e4_runner.py::test_job_is_closed_when_thread_start_fails",
        "tests/vst/test_e4_runner.py::test_background_process_holding_the_pipe_gives_exit_minus_four_and_capture_incomplete",
        "tests/vst/test_e4_runner.py::test_capture_incomplete_takes_precedence_over_output_truncation",
    }
    generated = build_registry.build_registry(ROOT)
    api_not_run = generated["categories"]["api"]["not_run_reasons"]

    assert audited_terminating_selectors <= POLICY_NOT_RUN.keys()
    assert audited_terminating_selectors <= api_not_run.keys()
    assert all(
        api_not_run[selector].startswith("NOT_RUN:")
        for selector in audited_terminating_selectors
    )


@pytest.mark.parametrize(
    "bad_path",
    ["", "../escape", "tests/../escape", "tests//file.py", "tests\\file.py", "/absolute"],
)
def test_s4_runner_rejects_noncanonical_artifact_paths(bad_path: str):
    with pytest.raises(run.QARunError, match="canonical relative path"):
        run._canonical_relative(bad_path, "artifact path")


def test_s4_runner_reports_missing_dependency_lock_as_typed_failure(tmp_path: Path):
    with pytest.raises(run.QARunError, match="QA dependency lock is missing"):
        run._lock_versions(tmp_path)


def test_s4_runner_identifies_missing_locked_distribution(tmp_path: Path):
    actual, missing = run._installed_versions({"pytest": "999.0"}, tmp_path)

    assert actual == {}
    assert missing == ["pytest"]


def test_s4_runner_refuses_an_unapproved_interpreter(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(run.sys, "executable", str(tmp_path / "python.exe"))

    assert run._canonical_interpreter_matches() is False


def test_s4_runner_rejects_artifacts_outside_fixed_category_paths(tmp_path: Path):
    args = SimpleNamespace(
        repo_root=str(ROOT),
        scratch_root=str(tmp_path),
        run_id="functional-run",
        timeout_seconds=30,
        output_cap_bytes=4096,
        category="functional",
        report_path="docs/sdlc/evidence/qa/regression.report.jsonl",
        stdout_path="docs/sdlc/evidence/qa/functional.stdout.txt",
        stderr_path="docs/sdlc/evidence/qa/functional.stderr.txt",
        dependency_target=str(tmp_path / "target"),
    )

    with pytest.raises(run.QARunError, match="fixed append-only category paths"):
        run._repo_paths(args)


def test_s4_main_reports_wrong_interpreter_as_blocked_without_spawning_pytest(
    tmp_path: Path, monkeypatch, capsys
):
    root, _ = _build_candidate_repo(tmp_path / "not-run-candidate", include_seeded=False)
    fixtures_catalog = {
        "schema_version": 1,
        "status": "NOT_RUN",
        "reason": "This candidate intentionally has no seeded-failure tests.",
        "fixtures": [],
    }
    (root / "docs" / "qa" / "fixtures.json").write_text(
        json.dumps(fixtures_catalog), encoding="utf-8"
    )
    lock_path = root / "tools" / "qa" / "requirements.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        "# Wheel-only, exact hashes for a synthetic runner test.\n"
        "pytest==9.0.3 \\\n"
        f"    --hash=sha256:{'0' * 64}\n",
        encoding="utf-8",
    )
    _git(root, "add", "docs/qa/categories.json", "docs/qa/fixtures.json", "tools/qa/requirements.lock")
    _git(root, "commit", "-m", "synthetic NOT_RUN fixture and lock")

    dependency_target = tmp_path / "empty-dependency-target"
    dependency_target.mkdir()
    args = Namespace(
        category="functional",
        repo_root=str(root),
        manifest="docs/qa/categories.json",
        fixtures="docs/qa/fixtures.json",
        dependency_target=str(dependency_target),
        scratch_root=str(tmp_path / "scratch"),
        run_id="wrong-interpreter",
        expected_head=None,
        timeout_seconds=30,
        output_cap_bytes=4096,
        report_path="docs/sdlc/evidence/qa/functional.report.jsonl",
        stdout_path="docs/sdlc/evidence/qa/functional.stdout.txt",
        stderr_path="docs/sdlc/evidence/qa/functional.stderr.txt",
    )
    spawn_attempts = []

    def fail_if_pytest_is_spawned(*_args, **_kwargs):
        spawn_attempts.append(True)
        raise AssertionError("wrong interpreter must block before pytest spawn")

    monkeypatch.setattr(run, "_args", lambda: args)
    monkeypatch.setattr(run.sys, "executable", str(tmp_path / "unapproved-python.exe"))
    monkeypatch.setattr(run.sys, "path", list(run.sys.path))
    monkeypatch.setattr(run, "_pytest_command", fail_if_pytest_is_spawned)
    monkeypatch.setattr(run, "_run_bounded", fail_if_pytest_is_spawned)

    exit_code = run.main()
    stdout = capsys.readouterr().out
    report_path = root / args.report_path
    report = json.loads(report_path.read_text(encoding="utf-8").splitlines()[0])

    assert exit_code == 2
    assert "QA_RESULT BLOCKED" in stdout
    assert report["result"] == "BLOCKED"
    assert report["exit_code"] is None
    assert any("runner executable is not the approved" in reason for reason in report["reasons"])
    assert any("locked QA dependencies are missing or mismatched" in reason for reason in report["reasons"])
    assert report["command"] == []
    assert spawn_attempts == []
