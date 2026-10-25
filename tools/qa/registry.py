"""Validate the committed QA registry and bind it to source files and Git HEAD."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PRIMARY_CATEGORIES = frozenset(
    {"functional", "integration", "api", "e2e", "seeded-failure"}
)
ALL_CATEGORIES = PRIMARY_CATEGORIES | {"regression"}
WINDOWS_PROFILE = "windows-cpython-3.14.3"
WSL_PROFILE = "wsl-ubuntu-24.04-cpython-3.12.3"
WSL_ROOT_PROFILE = "wsl-ubuntu-24.04-root-harness"
RUNTIME_PROFILES = (WINDOWS_PROFILE, WSL_PROFILE, WSL_ROOT_PROFILE)
POSIX_ONLY_SELECTORS = frozenset({
    "tests/vst/test_e3_store.py::test_database_file_is_owner_only_on_posix",
    "tests/vst/test_e4_runner.py::test_link_created_by_the_command_itself_gets_a_zero_digest",
    "tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork",
    "tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes",
    "tests/vst/test_s2_store_lifecycle.py::test_exactly_one_event_ahead_is_recovered_before_mutation",
    "tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed",
    "tests/vst/test_s2_store_lifecycle.py::test_multi_event_transaction_recovers_suffix_after_one_checkpoint_append",
})
WSL_ROOT_ONLY_SELECTORS = frozenset({
    "tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file",
    "tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture",
})
WINDOWS_ONLY_SELECTORS = frozenset({
    "tests/vst/test_e4_runner.py::test_job_is_closed_when_thread_start_fails",
})
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SELECTOR = re.compile(
    r"(?P<path>tests/[A-Za-z0-9_./-]+\.py)::"
    r"(?:(?P<class>[A-Za-z_][A-Za-z0-9_]*)::)?(?P<function>test_[A-Za-z0-9_]+)\Z"
)
_TEST_FILE = re.compile(r"test_[A-Za-z0-9_]+\.py\Z")


def required_runtime_profiles(selector: str) -> list[str]:
    """Return the committed S4 profile assignment contract for one selector."""
    if selector in WSL_ROOT_ONLY_SELECTORS:
        return [WSL_ROOT_PROFILE]
    if selector in POSIX_ONLY_SELECTORS:
        return [WSL_PROFILE]
    if selector in WINDOWS_ONLY_SELECTORS:
        return [WINDOWS_PROFILE]
    return [WINDOWS_PROFILE, WSL_PROFILE]


class RegistryError(ValueError):
    """Raised when the committed registry cannot prove its exact denominator."""


@dataclass(frozen=True)
class ValidatedRegistry:
    data: dict[str, Any]
    sha256: str
    candidate_head: str
    selectors_by_id: dict[str, dict[str, Any]]
    category_test_ids: dict[str, list[str]]
    category_inventory_ids: dict[str, list[str]]
    category_not_run: dict[str, dict[str, str]]
    category_profile_test_ids: dict[str, dict[str, list[str]]]
    category_profile_not_run: dict[str, dict[str, dict[str, str]]]
    category_profile_unassigned_ids: dict[str, dict[str, list[str]]]


def _exact_keys(value: object, keys: set[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RegistryError(f"{context}: expected exact fields {sorted(keys)}")
    if any(not isinstance(key, str) for key in value):
        raise RegistryError(f"{context}: keys must be strings")
    return value


def _safe_git(root: Path, *args: str) -> bytes:
    command = [
        "git",
        "-c",
        "safe.directory=",
        "-c",
        f"safe.directory={os.fspath(root)}",
        *args,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RegistryError(f"Git provenance query failed ({type(exc).__name__})") from None
    if result.returncode != 0:
        raise RegistryError("Git provenance query failed")
    return result.stdout


def git_root(path: str | os.PathLike[str]) -> Path:
    candidate = Path(path).resolve(strict=True)
    if not candidate.is_dir():
        raise RegistryError("candidate root must be a directory")
    root_bytes = _safe_git(candidate, "rev-parse", "--show-toplevel")
    try:
        root = Path(os.fsdecode(root_bytes).strip()).resolve(strict=True)
    except OSError:
        raise RegistryError("Git returned an invalid repository root") from None
    return root


def git_head(root: Path) -> str:
    head = os.fsdecode(_safe_git(root, "rev-parse", "--verify", "HEAD")).strip()
    if _HEX40.fullmatch(head) is None:
        raise RegistryError("candidate HEAD is not a canonical commit id")
    return head


def _latest_path_commit(root: Path, relative: str) -> str:
    output = os.fsdecode(
        _safe_git(root, "log", "-1", "--format=%H", "--", relative)
    ).strip()
    if _HEX40.fullmatch(output) is None:
        raise RegistryError(f"source path has no committed provenance: {relative}")
    return output


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    command = [
        "git",
        "-c",
        "safe.directory=",
        "-c",
        f"safe.directory={os.fspath(root)}",
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RegistryError(f"Git ancestry query failed ({type(exc).__name__})") from None
    if result.returncode not in (0, 1):
        raise RegistryError("Git ancestry query failed")
    return result.returncode == 0


def _read_repo_file(root: Path, relative: str) -> bytes:
    if relative.startswith("/") or "\\" in relative or ".." in relative.split("/"):
        raise RegistryError(f"non-canonical repository path: {relative!r}")
    path = root.joinpath(*relative.split("/"))
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        raise RegistryError(f"required source file is missing: {relative}") from None
    if not resolved.is_relative_to(root) or path.is_symlink():
        raise RegistryError(f"source path escapes the repository: {relative}")
    try:
        return resolved.read_bytes()
    except OSError as exc:
        raise RegistryError(f"cannot read source file: {relative} ({type(exc).__name__})") from None


def _function_selectors(source_path: str, content: bytes) -> set[str]:
    try:
        source = content.decode("utf-8")
        tree = ast.parse(source, filename=source_path)
    except (UnicodeError, SyntaxError) as exc:
        raise RegistryError(
            f"test source cannot be statically parsed: {source_path} ({type(exc).__name__})"
        ) from None

    found: set[str] = set()
    classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }
    test_class_names = {
        name
        for name in classes
        if name.startswith("Test") or name.endswith("Tests")
    }

    def collect_methods(class_name: str, seen: set[str] | None = None) -> set[str]:
        visited = set() if seen is None else set(seen)
        if class_name in visited:
            return set()
        visited.add(class_name)
        node = classes[class_name]
        methods = {
            member.name
            for member in node.body
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            and member.name.startswith("test_")
        }
        for base in node.bases:
            base_name = base.id if isinstance(base, ast.Name) else None
            if base_name in classes:
                methods.update(collect_methods(base_name, visited))
        return methods

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            found.add(f"{source_path}::{node.name}")
    for class_name in sorted(test_class_names):
        for method_name in sorted(collect_methods(class_name)):
            found.add(f"{source_path}::{class_name}::{method_name}")
    return found


def inventory_test_files(root: Path) -> list[str]:
    tests_root = root / "tests"
    if not tests_root.is_dir():
        raise RegistryError("tests directory is missing")
    files = sorted(
        path.relative_to(root).as_posix()
        for path in tests_root.rglob("*.py")
        if _TEST_FILE.fullmatch(path.name)
    )
    if not files:
        raise RegistryError("no committed test modules were found")
    return files


def validate_registry(
    root_path: str | os.PathLike[str],
    manifest_path: str = "docs/qa/categories.json",
) -> ValidatedRegistry:
    root = git_root(root_path)
    manifest_bytes = _read_repo_file(root, manifest_path)
    try:
        data = json.loads(manifest_bytes)
    except (UnicodeError, json.JSONDecodeError):
        raise RegistryError("category manifest is not valid UTF-8 JSON") from None

    data = _exact_keys(
        data,
        {
            "schema_version",
            "registry_version",
            "runtime_profiles",
            "artifacts",
            "source_head",
            "source_inventory",
            "tests",
            "categories",
            "aggregates",
            "unsupported_apis",
        },
        "manifest",
    )
    if data["schema_version"] != 2 or data["registry_version"] != "2":
        raise RegistryError("manifest schema or registry version is unsupported")
    profiles = data["runtime_profiles"]
    if profiles != list(RUNTIME_PROFILES):
        raise RegistryError("manifest runtime profiles do not match the supported profile matrix")
    artifacts = data["artifacts"]
    expected_artifacts = {
        category: {
            "report": f"docs/sdlc/evidence/qa/{category}.report.jsonl",
            "stdout": f"docs/sdlc/evidence/qa/{category}.stdout.txt",
            "stderr": f"docs/sdlc/evidence/qa/{category}.stderr.txt",
        }
        for category in ALL_CATEGORIES | {"seeded-failure"}
    }
    if artifacts != expected_artifacts:
        raise RegistryError("manifest artifact paths do not match the fixed append-only category paths")
    source_head = data["source_head"]
    if not isinstance(source_head, str) or _HEX40.fullmatch(source_head) is None:
        raise RegistryError("source_head must be a canonical commit id")
    head = git_head(root)
    if not _is_ancestor(root, source_head, head):
        raise RegistryError("registry source_head is not an ancestor of candidate HEAD")

    inventory = data["source_inventory"]
    if not isinstance(inventory, list):
        raise RegistryError("source_inventory must be a list")
    inventory_by_path: dict[str, dict[str, Any]] = {}
    actual_selectors: set[str] = set()
    for index, raw_item in enumerate(inventory):
        item = _exact_keys(raw_item, {"path", "source_commit", "sha256"}, f"source_inventory[{index}]")
        path = item["path"]
        commit = item["source_commit"]
        digest = item["sha256"]
        if not isinstance(path, str) or not _TEST_FILE.fullmatch(Path(path).name):
            raise RegistryError(f"source_inventory[{index}].path is not a test module")
        if path in inventory_by_path:
            raise RegistryError(f"duplicate source inventory path: {path}")
        if not isinstance(commit, str) or _HEX40.fullmatch(commit) is None:
            raise RegistryError(f"source_inventory[{index}].source_commit is invalid")
        if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
            raise RegistryError(f"source_inventory[{index}].sha256 is invalid")
        content = _read_repo_file(root, path)
        normalized_content = content.replace(b"\r\n", b"\n")
        if hashlib.sha256(normalized_content).hexdigest() != digest:
            raise RegistryError(f"test source changed after registry generation: {path}")
        if _latest_path_commit(root, path) != commit:
            raise RegistryError(f"test source provenance is stale: {path}")
        actual_selectors.update(_function_selectors(path, content))
        inventory_by_path[path] = item

    expected_files = set(inventory_test_files(root))
    if set(inventory_by_path) != expected_files:
        raise RegistryError("source_inventory does not cover every committed test module")

    categories = data["categories"]
    if not isinstance(categories, dict) or set(categories) != ALL_CATEGORIES:
        raise RegistryError("categories must declare all five primary categories and regression")
    tests = data["tests"]
    if not isinstance(tests, list):
        raise RegistryError("tests must be a list")
    selectors_by_id: dict[str, dict[str, Any]] = {}
    selectors: set[str] = set()
    categorized_ids: dict[str, list[str]] = {name: [] for name in PRIMARY_CATEGORIES}
    categorized_profiles: dict[str, dict[str, list[str]]] = {
        category: {profile: [] for profile in RUNTIME_PROFILES}
        for category in PRIMARY_CATEGORIES
    }
    for index, raw_test in enumerate(tests):
        item = _exact_keys(
            raw_test,
            {
                "test_id", "selector", "source_path", "source_commit",
                "primary_category", "runtime_profiles",
            },
            f"tests[{index}]",
        )
        test_id = item["test_id"]
        selector = item["selector"]
        source_path = item["source_path"]
        source_commit = item["source_commit"]
        category = item["primary_category"]
        runtime_profiles = item["runtime_profiles"]
        match = _SELECTOR.fullmatch(selector) if isinstance(selector, str) else None
        if match is None or test_id != selector:
            raise RegistryError(f"tests[{index}] selector or test_id is not canonical")
        if selector in selectors or test_id in selectors_by_id:
            raise RegistryError(f"duplicate selector/test id: {selector}")
        if source_path != match.group("path") or source_path not in inventory_by_path:
            raise RegistryError(f"tests[{index}] source_path does not match its selector")
        if source_commit != inventory_by_path[source_path]["source_commit"]:
            raise RegistryError(f"tests[{index}] source_commit is stale")
        if category not in PRIMARY_CATEGORIES:
            raise RegistryError(f"tests[{index}] primary category is invalid")
        if (
            not isinstance(runtime_profiles, list)
            or runtime_profiles != sorted(set(runtime_profiles))
            or any(profile not in RUNTIME_PROFILES for profile in runtime_profiles)
        ):
            raise RegistryError(f"tests[{index}] runtime_profiles is invalid")
        if runtime_profiles and runtime_profiles != sorted(required_runtime_profiles(selector)):
            raise RegistryError(f"tests[{index}] runtime_profiles violates the selector platform contract")
        selectors.add(selector)
        selectors_by_id[test_id] = {
            "selector": selector,
            "primary_category": category,
            "runtime_profiles": runtime_profiles,
        }
        categorized_ids[category].append(test_id)
        for profile in runtime_profiles:
            categorized_profiles[category][profile].append(test_id)

    if selectors != actual_selectors:
        missing = sorted(actual_selectors - selectors)
        extra = sorted(selectors - actual_selectors)
        raise RegistryError(
            f"registry selector inventory differs from source (missing={len(missing)}, extra={len(extra)})"
        )

    category_test_ids: dict[str, list[str]] = {}
    category_inventory_ids: dict[str, list[str]] = {}
    category_not_run: dict[str, dict[str, str]] = {}
    category_profile_test_ids: dict[str, dict[str, list[str]]] = {}
    category_profile_not_run: dict[str, dict[str, dict[str, str]]] = {}
    category_profile_unassigned_ids: dict[str, dict[str, list[str]]] = {}
    for category in sorted(PRIMARY_CATEGORIES):
        entry = _exact_keys(
            categories[category],
            {"status", "test_ids", "not_run_reasons", "reason"},
            f"categories.{category}",
        )
        status, ids, reason = entry["status"], entry["test_ids"], entry["reason"]
        if status not in {"SUPPORTED", "NOT_RUN", "UNSUPPORTED"}:
            raise RegistryError(f"categories.{category}.status is invalid")
        if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
            raise RegistryError(f"categories.{category}.test_ids must be a string list")
        if len(ids) != len(set(ids)) or sorted(ids) != sorted(categorized_ids[category]):
            raise RegistryError(f"categories.{category}.test_ids disagree with test assignments")
        not_run_reasons = entry["not_run_reasons"]
        if (
            not isinstance(not_run_reasons, dict)
            or any(test_id not in ids for test_id in not_run_reasons)
            or any(not isinstance(value, str) or not value.strip() for value in not_run_reasons.values())
        ):
            raise RegistryError(f"categories.{category}.not_run_reasons is invalid")
        if status == "SUPPORTED" and not ids:
            raise RegistryError(f"categories.{category} cannot be SUPPORTED without tests")
        if status != "SUPPORTED" and (not isinstance(reason, str) or not reason.strip()):
            raise RegistryError(f"categories.{category} requires an exact non-approving reason")
        category_inventory_ids[category] = list(ids)
        category_not_run[category] = dict(not_run_reasons)
        category_test_ids[category] = sorted(set(ids) - set(not_run_reasons))
        category_profile_test_ids[category] = {}
        category_profile_not_run[category] = {}
        category_profile_unassigned_ids[category] = {}
        for profile in RUNTIME_PROFILES:
            profile_inventory = sorted(categorized_profiles[category][profile])
            profile_not_run = {
                test_id: not_run_reasons[test_id]
                for test_id in profile_inventory
                if test_id in not_run_reasons
            }
            category_profile_test_ids[category][profile] = sorted(
                set(profile_inventory) - set(profile_not_run)
            )
            category_profile_not_run[category][profile] = profile_not_run
            category_profile_unassigned_ids[category][profile] = sorted(
                set(ids) - set(profile_inventory)
            )

    for test_id, selector in selectors_by_id.items():
        category = selector["primary_category"]
        unassigned = not selector["runtime_profiles"]
        policy_not_run = test_id in category_not_run[category]
        if unassigned != policy_not_run:
            raise RegistryError(
                f"selector assignment and category NOT_RUN policy disagree: {test_id}"
            )

    regression = _exact_keys(
        categories["regression"],
        {"status", "test_ids", "not_run_reasons", "reason"},
        "categories.regression",
    )
    expected_regression = sorted(
        test_id
        for category in ("functional", "integration", "api", "e2e")
        for test_id in category_test_ids[category]
    )
    expected_regression_not_run = {
        selector: reason
        for category in ("functional", "integration", "api", "e2e")
        for selector, reason in category_not_run[category].items()
    }
    if (
        regression["status"] != "AGGREGATE"
        or regression["test_ids"] != expected_regression
        or regression["reason"] is not None
        or regression["not_run_reasons"] != expected_regression_not_run
    ):
        raise RegistryError("regression must exactly aggregate functional/integration/api/e2e IDs")
    category_test_ids["regression"] = expected_regression
    category_inventory_ids["regression"] = sorted(
        test_id
        for category in ("functional", "integration", "api", "e2e")
        for test_id in category_inventory_ids[category]
    )
    category_not_run["regression"] = expected_regression_not_run
    category_profile_test_ids["regression"] = {
        profile: sorted(
            test_id
            for category in ("functional", "integration", "api", "e2e")
            for test_id in category_profile_test_ids[category][profile]
        )
        for profile in RUNTIME_PROFILES
    }
    category_profile_not_run["regression"] = {
        profile: {
            test_id: reason
            for category in ("functional", "integration", "api", "e2e")
            for test_id, reason in category_profile_not_run[category][profile].items()
        }
        for profile in RUNTIME_PROFILES
    }
    category_profile_unassigned_ids["regression"] = {
        profile: sorted(
            test_id
            for category in ("functional", "integration", "api", "e2e")
            for test_id in category_profile_unassigned_ids[category][profile]
        )
        for profile in RUNTIME_PROFILES
    }

    aggregates = _exact_keys(data["aggregates"], {"regression_members"}, "aggregates")
    if aggregates["regression_members"] != ["functional", "integration", "api", "e2e"]:
        raise RegistryError("regression_members has an unsupported ordering or membership")
    unsupported = _exact_keys(data["unsupported_apis"], {"http"}, "unsupported_apis")
    http = _exact_keys(unsupported["http"], {"status", "reason", "evidence_paths"}, "unsupported_apis.http")
    if http["status"] != "UNSUPPORTED" or not isinstance(http["reason"], str) or not http["reason"].strip():
        raise RegistryError("HTTP API must remain explicitly UNSUPPORTED with a reason")
    evidence_paths = http["evidence_paths"]
    if not isinstance(evidence_paths, list) or not evidence_paths or any(not isinstance(path, str) for path in evidence_paths):
        raise RegistryError("HTTP API requires repository evidence paths")
    for path in evidence_paths:
        if not _read_repo_file(root, path):
            raise RegistryError(f"HTTP API evidence path is empty: {path}")

    return ValidatedRegistry(
        data=data,
        sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        candidate_head=head,
        selectors_by_id=selectors_by_id,
        category_test_ids=category_test_ids,
        category_inventory_ids=category_inventory_ids,
        category_not_run=category_not_run,
        category_profile_test_ids=category_profile_test_ids,
        category_profile_not_run=category_profile_not_run,
        category_profile_unassigned_ids=category_profile_unassigned_ids,
    )
