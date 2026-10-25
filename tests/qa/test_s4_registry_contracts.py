"""Focused S4 category-registry and seeded-failure contract coverage."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

pytest_plugins = ("tools.qa.pytest_pass_plugin",)

from tools.qa import registry
from tools.qa.pytest_pass_plugin import record_seeded_failure_observation
from tools.vst.contracts import ContractError, validate_task_manifest


ROOT = Path(__file__).resolve().parents[2]
HERE = "tests/qa/test_s4_registry_contracts.py"


def _registry_fixture() -> dict:
    value = json.loads((ROOT / "docs/qa/categories.json").read_text(encoding="utf-8"))
    value["categories"]["seeded-failure"] = {
        "state": "SUPPORTED",
        "coverage_state": "PARTIAL",
        "coverage_reason": "synthetic registry validator fixture",
        "owner_role": "functional-test-reviewer",
        "source_head": value["source_head"],
        "test_ids": [f"{HERE}::test_s4_seeded_failure_rejects_invalid_manifest_and_records_observation"],
    }
    return value


def _load_registry_with(monkeypatch, payload: dict):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    monkeypatch.setattr(registry, "_read_repo_json", lambda *args, **kwargs: (payload, raw))
    monkeypatch.setattr(registry, "_git_commit_exists", lambda *args: True)
    monkeypatch.setattr(registry, "_current_candidate_head", lambda *args: "a" * 40)
    monkeypatch.setattr(registry, "_git_commit_is_ancestor", lambda *args: True)
    monkeypatch.setattr(registry, "_git_file_is_tracked", lambda *args: True)
    return registry.load_registry(ROOT)


def test_s4_registry_accepts_single_primary_category_per_test_id(monkeypatch):
    candidate = _registry_fixture()
    loaded, digest = _load_registry_with(monkeypatch, candidate)

    all_ids = [test_id for item in loaded["categories"].values()
               if item["state"] == "SUPPORTED" for test_id in item["test_ids"]]
    assert len(all_ids) == len(set(all_ids))
    assert digest == hashlib.sha256(json.dumps(candidate, separators=(",", ":")).encode()).hexdigest()


def test_s4_committed_registry_loads_with_resolved_nodes():
    loaded, digest = registry.load_registry(ROOT)
    registry_bytes = (ROOT / "docs/qa/categories.json").read_bytes()
    test_ids = [
        test_id for entry in loaded["categories"].values()
        if entry["state"] == "SUPPORTED" for test_id in entry["test_ids"]
    ]

    assert digest == hashlib.sha256(registry_bytes).hexdigest()
    assert len(test_ids) == len(set(test_ids))


def test_s4_registry_rejects_duplicate_primary_category_assignment(monkeypatch):
    candidate = _registry_fixture()
    candidate["categories"]["integration"]["test_ids"] = list(
        candidate["categories"]["functional"]["test_ids"]
    )

    with pytest.raises(ContractError, match="multiple primary categories"):
        _load_registry_with(monkeypatch, candidate)


def test_s4_registry_rejects_provenance_outside_candidate_history(monkeypatch):
    candidate = _registry_fixture()
    monkeypatch.setattr(registry, "_read_repo_json", lambda *args, **kwargs: (candidate, b"{}"))
    monkeypatch.setattr(registry, "_git_commit_exists", lambda *args: True)
    monkeypatch.setattr(registry, "_current_candidate_head", lambda *args: "a" * 40)
    monkeypatch.setattr(registry, "_git_commit_is_ancestor", lambda *args: False)

    with pytest.raises(ContractError, match="stale or outside"):
        registry.load_registry(ROOT)


def test_s4_registry_rejects_unknown_pytest_node_id(monkeypatch):
    candidate = _registry_fixture()
    candidate["categories"]["api"]["test_ids"].append(f"{HERE}::test_node_that_does_not_exist")

    with pytest.raises(ContractError, match="does not resolve"):
        _load_registry_with(monkeypatch, candidate)


@pytest.mark.parametrize("test_path", [
    "tests/../outside.py",
    "tests//valid.py",
    r"tests\valid.py",
])
def test_s4_registry_rejects_noncanonical_source_paths_before_ast_acceptance(tmp_path, test_path):
    """A valid test function outside canonical spelling cannot pass source resolution."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "valid.py").write_text("def test_contract():\n    pass\n", encoding="utf-8")
    (tmp_path / "outside.py").write_text("def test_contract():\n    pass\n", encoding="utf-8")

    assert not registry._pytest_node_id_exists(tmp_path, f"{test_path}::test_contract")


def test_s4_registry_rejects_symlinked_source_components_before_ast_acceptance(tmp_path):
    """Valid AST reachable through a symlink must not count as a repository tests node."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "valid.py").write_text("def test_contract():\n    pass\n", encoding="utf-8")
    try:
        (tests_dir / "linked.py").symlink_to(outside_dir / "valid.py")
        (tests_dir / "linked_dir").symlink_to(outside_dir, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {type(exc).__name__}: {exc}")

    assert not registry._pytest_node_id_exists(tmp_path, "tests/linked.py::test_contract")
    assert not registry._pytest_node_id_exists(tmp_path, "tests/linked_dir/valid.py::test_contract")


def test_s4_registry_loader_rejects_noncanonical_path_even_when_ast_target_exists(monkeypatch, tmp_path):
    candidate = _registry_fixture()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tmp_path / "outside.py").write_text("def test_contract():\n    pass\n", encoding="utf-8")
    candidate["categories"]["api"]["test_ids"] = ["tests/../outside.py::test_contract"]
    raw = json.dumps(candidate, separators=(",", ":")).encode()
    monkeypatch.setattr(registry, "_read_repo_json", lambda *args, **kwargs: (candidate, raw))
    monkeypatch.setattr(registry, "_git_commit_exists", lambda *args: True)
    monkeypatch.setattr(registry, "_current_candidate_head", lambda *args: "a" * 40)
    monkeypatch.setattr(registry, "_git_commit_is_ancestor", lambda *args: True)
    monkeypatch.setattr(registry, "_git_file_is_tracked", lambda *args: True)

    with pytest.raises(ContractError, match="does not resolve"):
        registry.load_registry(tmp_path)


def test_s4_registry_rejects_supported_category_without_required_ids(monkeypatch):
    candidate = _registry_fixture()
    candidate["categories"]["functional"]["test_ids"] = []

    with pytest.raises(ContractError, match="needs test IDs"):
        _load_registry_with(monkeypatch, candidate)


def test_s4_registry_manifest_projection_requires_exact_ids_and_commands(monkeypatch):
    candidate = _registry_fixture()
    _load_registry_with(monkeypatch, candidate)
    required_categories = {
        name: entry for name, entry in candidate["categories"].items()
        if entry["state"] == "SUPPORTED"
    }
    manifest = {
        "required_receipts": [
            {"slot": category, "receipt_type": "TestRun"}
            for category in required_categories
        ],
        "required_tests": [
            {"slot": category, "test_id": test_id}
            for category, entry in required_categories.items()
            for test_id in entry["test_ids"]
        ],
        "mandatory_commands": [
            {
                "slot": category,
                "argv": [
                    sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "-p", "tools.qa.pytest_pass_plugin", *sorted(entry["test_ids"]),
                ],
            }
            for category, entry in required_categories.items()
        ],
    }
    registry.validate_projection(candidate, manifest)

    manifest["required_tests"][0]["test_id"] += "::stale"
    with pytest.raises(ContractError, match="differ from registry"):
        registry.validate_projection(candidate, manifest)


def test_s4_seeded_failure_catalog_rejects_hash_mismatch(monkeypatch):
    candidate = _registry_fixture()
    fixture_id = "invalid-task-manifest"
    test_id = f"{HERE}::test_s4_seeded_failure_rejects_invalid_manifest_and_records_observation"
    candidate["categories"]["seeded-failure"]["test_ids"] = [test_id]
    invalid_input = {"contract_version": 2}
    catalog = {
        "schema_version": 1,
        "state": "SUPPORTED",
        "fixtures": [{
            "fixture_id": fixture_id,
            "input": invalid_input,
            "input_sha256": "0" * 64,
            "expected_rejection": "INVALID_TASK_MANIFEST",
            "test_id": test_id,
        }],
        "reason": None,
        "next_step": None,
    }
    monkeypatch.setattr(registry, "_git_file_is_tracked", lambda *args: True)
    monkeypatch.setattr(registry, "_read_repo_json", lambda *args, **kwargs: (catalog, b"{}"))

    with pytest.raises(ContractError, match="input hash is invalid"):
        registry.load_seeded_failure_catalog(ROOT, candidate)


def test_s4_seeded_failure_rejects_invalid_manifest_and_records_observation(monkeypatch):
    invalid_input = {"contract_version": 2}
    digest = hashlib.sha256(
        json.dumps(invalid_input, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    fixture_id = "invalid-task-manifest"
    test_id = f"{HERE}::test_s4_seeded_failure_rejects_invalid_manifest_and_records_observation"
    candidate = _registry_fixture()
    candidate["categories"]["seeded-failure"]["test_ids"] = [test_id]
    # The committed fixture catalog is the real input boundary for this lane.
    loaded_catalog, _ = registry.load_seeded_failure_catalog(ROOT, candidate)
    assert loaded_catalog["fixtures"][0]["test_id"] == test_id

    with pytest.raises(ContractError, match=r"task_manifest_v2: missing field\(s\):"):
        validate_task_manifest(invalid_input)

    record_seeded_failure_observation(
        fixture_id=fixture_id,
        input_sha256=digest,
        expected_rejection="INVALID_TASK_MANIFEST",
        observed_rejection="INVALID_TASK_MANIFEST",
        test_id=test_id,
    )

