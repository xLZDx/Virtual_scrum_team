"""Focused S4 category-registry and seeded-failure contract coverage."""

from __future__ import annotations

import hashlib
import json
import subprocess
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


def test_s4_registry_parses_shared_test_source_once_per_load(monkeypatch, tmp_path):
    """Distinct registered nodes in one source reuse one parsed AST per load."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    source_path = tests_dir / "shared.py"
    source_path.write_text(
        "def test_first():\n    pass\n\ndef test_second():\n    pass\n\n"
        "class TestShared:\n    def test_method(self):\n        pass\n",
        encoding="utf-8",
    )
    first_id = "tests/shared.py::test_first"
    second_id = "tests/shared.py::test_second"
    class_method_id = "tests/shared.py::TestShared::test_method"
    candidate = _registry_fixture()
    candidate["categories"]["functional"].update(
        source_head="a" * 40, test_ids=[first_id]
    )
    candidate["categories"]["integration"] = {
        "state": "SUPPORTED", "coverage_state": "PARTIAL",
        "coverage_reason": "synthetic shared-source index fixture",
        "owner_role": "functional-test-reviewer", "source_head": "a" * 40,
        "test_ids": [class_method_id],
    }
    candidate["categories"]["api"].update(
        source_head="a" * 40, test_ids=[second_id]
    )
    candidate["categories"]["e2e"] = {
        "state": "NOT_RUN", "owner_role": "e2e-runner",
        "reason": "not needed for this source-cache contract fixture",
        "next_step": "none",
    }
    candidate["categories"]["seeded-failure"] = {
        "state": "NOT_RUN", "owner_role": "functional-test-reviewer",
        "reason": "not needed for this source-cache contract fixture",
        "next_step": "none",
    }
    raw = json.dumps(candidate, separators=(",", ":")).encode()
    monkeypatch.setattr(registry, "_read_repo_json", lambda *args, **kwargs: (candidate, raw))
    monkeypatch.setattr(registry, "_current_candidate_head", lambda *args: "a" * 40)
    monkeypatch.setattr(registry, "_git_commit_is_ancestor", lambda *args: True)
    monkeypatch.setattr(registry, "_git_file_is_tracked", lambda *args: True)

    parse_calls = 0
    original_parse = registry.ast.parse

    def count_parse(*args, **kwargs):
        nonlocal parse_calls
        parse_calls += 1
        return original_parse(*args, **kwargs)

    source_reads = 0
    original_open = Path.open

    def count_source_open(path, *args, **kwargs):
        nonlocal source_reads
        if path == source_path:
            source_reads += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(registry.ast, "parse", count_parse)
    monkeypatch.setattr(Path, "open", count_source_open)

    loaded, _ = registry.load_registry(tmp_path)

    assert loaded["categories"]["functional"]["test_ids"] == [first_id]
    assert loaded["categories"]["api"]["test_ids"] == [second_id]
    assert loaded["categories"]["integration"]["test_ids"] == [class_method_id]
    assert parse_calls == 1
    assert source_reads == 1


def test_s4_registry_rejects_aggregate_test_source_budget_overflow(monkeypatch, tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    candidate = _registry_fixture()
    source_paths = []
    for index, category in enumerate(registry.PRIMARY_CATEGORIES):
        source_path = tests_dir / f"budget_{index}.py"
        prefix = f"def test_budget_{index}():\n    pass\n".encode()
        target_size = 900 * 1024
        source_path.write_bytes(prefix + b"#" + b"x" * (target_size - len(prefix) - 1))
        source_paths.append(source_path)
        test_id = f"tests/budget_{index}.py::test_budget_{index}"
        if category == "api":
            candidate["categories"][category].update(
                source_head="a" * 40, test_ids=[test_id]
            )
        else:
            candidate["categories"][category] = {
                "state": "SUPPORTED", "coverage_state": "PARTIAL",
                "coverage_reason": "synthetic aggregate-source-budget fixture",
                "owner_role": "functional-test-reviewer", "source_head": "a" * 40,
                "test_ids": [test_id],
            }
    raw = json.dumps(candidate, separators=(",", ":")).encode()
    monkeypatch.setattr(registry, "_read_repo_json", lambda *args, **kwargs: (candidate, raw))
    monkeypatch.setattr(registry, "_current_candidate_head", lambda *args: "a" * 40)
    monkeypatch.setattr(registry, "_git_commit_is_ancestor", lambda *args: True)
    monkeypatch.setattr(registry, "_git_file_is_tracked", lambda *args: True)

    parse_calls = 0
    original_parse = registry.ast.parse

    def count_parse(*args, **kwargs):
        nonlocal parse_calls
        parse_calls += 1
        return original_parse(*args, **kwargs)

    source_reads = 0
    original_open = Path.open

    def count_source_open(path, *args, **kwargs):
        nonlocal source_reads
        if path in source_paths:
            source_reads += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(registry.ast, "parse", count_parse)
    monkeypatch.setattr(Path, "open", count_source_open)

    with pytest.raises(ContractError, match="exceeds the 4194304-byte aggregate limit"):
        registry.load_registry(tmp_path)

    assert source_reads == 5
    assert parse_calls == 4


def test_s4_registry_rejects_more_than_2048_ids_before_node_resolution(monkeypatch):
    candidate = _registry_fixture()
    candidate["categories"]["functional"]["test_ids"] = [
        f"tests/bulk.py::test_case_{index}"
        for index in range(registry.MAX_REGISTRY_TEST_IDS + 1)
    ]
    raw = json.dumps(candidate, separators=(",", ":")).encode()
    monkeypatch.setattr(registry, "_read_repo_json", lambda *args, **kwargs: (candidate, raw))
    monkeypatch.setattr(registry, "_current_candidate_head", lambda *args: "a" * 40)
    monkeypatch.setattr(registry, "_git_commit_is_ancestor", lambda *args: True)
    monkeypatch.setattr(registry, "_git_file_is_tracked", lambda *args: True)

    def unexpected_node_resolution(*args, **kwargs):
        raise AssertionError("ID limit must reject before any per-ID resolution")

    monkeypatch.setattr(registry, "_pytest_node_id_exists", unexpected_node_resolution)

    with pytest.raises(ContractError, match="exceeds the 2048 test-ID limit"):
        registry.load_registry(ROOT)


def test_s4_registry_caches_oversized_source_as_fail_closed(tmp_path, monkeypatch):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    source_path = tests_dir / "oversized.py"
    source_path.write_bytes(b"#" + b"x" * registry.MAX_TEST_SOURCE_BYTES)
    source_cache = {}
    source_reads = 0
    original_open = Path.open

    def count_source_open(path, *args, **kwargs):
        nonlocal source_reads
        if path == source_path:
            source_reads += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", count_source_open)

    assert not registry._pytest_node_id_exists(
        tmp_path, "tests/oversized.py::test_too_large", source_cache=source_cache
    )
    assert not registry._pytest_node_id_exists(
        tmp_path, "tests/oversized.py::test_also_too_large", source_cache=source_cache
    )

    assert source_reads == 1


def test_s4_committed_registry_loads_with_resolved_nodes():
    loaded, digest = registry.load_registry(ROOT)
    registry_bytes = (ROOT / "docs/qa/categories.json").read_bytes()
    test_ids = [
        test_id for entry in loaded["categories"].values()
        if entry["state"] == "SUPPORTED" for test_id in entry["test_ids"]
    ]

    assert digest == hashlib.sha256(registry_bytes).hexdigest()
    assert len(test_ids) == len(set(test_ids))


def _stub_merge_base(monkeypatch, responses):
    calls = []
    remaining = list(responses)

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        response = remaining.pop(0)
        if isinstance(response, BaseException):
            raise response
        return subprocess.CompletedProcess(command, returncode=response)

    monkeypatch.setattr(registry.subprocess, "run", fake_run)
    return calls


def _assert_merge_base_calls(calls, root, expected_count):
    expected_command = ["git", "merge-base", "--is-ancestor", "a" * 40, "b" * 40]
    assert len(calls) == expected_count
    assert [command for command, _ in calls] == [expected_command] * expected_count
    for _, kwargs in calls:
        assert kwargs["cwd"] == root
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["check"] is False


def test_s4_git_ancestry_returncode_zero_is_true(monkeypatch, tmp_path):
    calls = _stub_merge_base(monkeypatch, [0])

    result = registry._git_commit_is_ancestor(tmp_path, "a" * 40, "b" * 40)

    assert result is True
    _assert_merge_base_calls(calls, tmp_path, expected_count=1)


def test_s4_git_ancestry_returncode_one_is_false(monkeypatch, tmp_path):
    calls = _stub_merge_base(monkeypatch, [1])

    result = registry._git_commit_is_ancestor(tmp_path, "a" * 40, "b" * 40)

    assert result is False
    _assert_merge_base_calls(calls, tmp_path, expected_count=1)


def test_s4_git_ancestry_other_returncode_is_contract_error(monkeypatch, tmp_path):
    calls = _stub_merge_base(monkeypatch, [2])

    with pytest.raises(ContractError, match="git merge-base exited with status 2"):
        registry._git_commit_is_ancestor(tmp_path, "a" * 40, "b" * 40)

    _assert_merge_base_calls(calls, tmp_path, expected_count=1)


def test_s4_git_ancestry_second_timeout_is_contract_error(monkeypatch, tmp_path):
    timeout = subprocess.TimeoutExpired("git merge-base", timeout=registry.GIT_COMMAND_TIMEOUT_SECONDS)
    calls = _stub_merge_base(monkeypatch, [timeout, timeout])

    with pytest.raises(
        ContractError,
        match="git merge-base timed out after 2 attempts of 5 seconds",
    ) as raised:
        registry._git_commit_is_ancestor(tmp_path, "a" * 40, "b" * 40)

    assert isinstance(raised.value.__cause__, subprocess.TimeoutExpired)
    _assert_merge_base_calls(calls, tmp_path, expected_count=2)
    assert all(kwargs["timeout"] == 5 for _, kwargs in calls)


def test_s4_git_ancestry_oserror_is_contract_error(monkeypatch, tmp_path):
    invocation_error = OSError("git executable unavailable")
    calls = _stub_merge_base(monkeypatch, [invocation_error])

    with pytest.raises(ContractError, match="cannot invoke git to verify QA registry ancestry") as raised:
        registry._git_commit_is_ancestor(tmp_path, "a" * 40, "b" * 40)

    assert raised.value.__cause__ is invocation_error
    _assert_merge_base_calls(calls, tmp_path, expected_count=1)


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

    with pytest.raises(ContractError, match="missing, stale, or outside"):
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


def test_s4_registry_rejects_test_source_over_one_mib_before_ast_parse(tmp_path, monkeypatch):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    source = (
        b"#" + b"x" * registry.MAX_TEST_SOURCE_BYTES
        + b"\ndef test_large_source():\n    pass\n"
    )
    (tests_dir / "large.py").write_bytes(source)
    ast_called = False

    def unexpected_parse(*args, **kwargs):
        nonlocal ast_called
        ast_called = True
        raise AssertionError("oversized source must be rejected before AST parsing")

    monkeypatch.setattr(registry.ast, "parse", unexpected_parse)

    assert not registry._pytest_node_id_exists(tmp_path, "tests/large.py::test_large_source")
    assert not ast_called


def test_s4_registry_treats_recursion_error_during_ast_parse_as_unresolved(tmp_path, monkeypatch):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "recursive.py").write_text(
        "def test_recursive_source():\n    pass\n", encoding="utf-8"
    )

    def recursive_parse(*args, **kwargs):
        raise RecursionError("synthetic parser recursion exhaustion")

    monkeypatch.setattr(registry.ast, "parse", recursive_parse)

    assert not registry._pytest_node_id_exists(
        tmp_path, "tests/recursive.py::test_recursive_source"
    )


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
    # The committed category and fixture catalog jointly define the real lane.
    loaded_registry, _ = registry.load_registry(ROOT)
    loaded_catalog, _ = registry.load_seeded_failure_catalog(ROOT, loaded_registry)
    fixture = next(row for row in loaded_catalog["fixtures"] if row["fixture_id"] == fixture_id)
    assert fixture["test_id"] == test_id

    with pytest.raises(ContractError, match=r"task_manifest_v2: missing field\(s\):"):
        validate_task_manifest(invalid_input)

    record_seeded_failure_observation(
        fixture_id=fixture_id,
        input_sha256=digest,
        expected_rejection="INVALID_TASK_MANIFEST",
        observed_rejection="INVALID_TASK_MANIFEST",
        test_id=test_id,
    )

