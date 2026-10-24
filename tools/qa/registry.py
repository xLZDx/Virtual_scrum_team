"""Load the committed QA registry and validate its v2 manifest projection."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.vst.contracts import ContractError, manifest_sha256, validate_task_manifest


PRIMARY_CATEGORIES = ("functional", "integration", "api", "e2e", "seeded-failure")
REGRESSION_CATEGORIES = ("functional", "integration", "api", "e2e")
MAX_REGISTRY_BYTES = 512 * 1024


def _read_repo_json(root: Path, relative_path: str, *, max_bytes: int) -> tuple[dict, bytes]:
    if os.path.isabs(relative_path) or ".." in Path(relative_path).parts:
        raise ContractError("registry and manifest paths must be repository-relative")
    target = root / relative_path
    if target.is_symlink() or not target.is_file():
        raise ContractError(f"repository JSON file is missing or linked: {relative_path}")
    resolved = target.resolve(strict=True)
    if root.resolve() not in resolved.parents:
        raise ContractError("repository JSON file escapes the worktree")
    with resolved.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ContractError(f"repository JSON file exceeds {max_bytes} bytes")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"repository JSON file is malformed: {relative_path}") from exc
    if not isinstance(parsed, dict):
        raise ContractError(f"repository JSON root must be an object: {relative_path}")
    return parsed, raw


def _git_file_is_tracked(root: Path, relative_path: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative_path], cwd=root,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _git_commit_exists(root: Path, revision: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{revision}^{{commit}}"], cwd=root,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def load_registry(root: Path, relative_path: str = "docs/qa/categories.json") -> tuple[dict, str]:
    """Validate committed registry syntax, unique IDs, categories, and source paths."""
    registry, raw = _read_repo_json(root, relative_path, max_bytes=MAX_REGISTRY_BYTES)
    if set(registry) != {"schema_version", "source_head", "categories", "regression"}:
        raise ContractError("QA registry has missing or unexpected top-level fields")
    if registry["schema_version"] != 1:
        raise ContractError("unsupported QA registry schema_version")
    source_head = registry["source_head"]
    if (not isinstance(source_head, str) or len(source_head) != 40 or
            any(char not in "0123456789abcdef" for char in source_head) or
            not _git_commit_exists(root, source_head)):
        raise ContractError("QA registry source_head must be a full lowercase Git SHA")
    categories = registry["categories"]
    if not isinstance(categories, dict) or set(categories) != set(PRIMARY_CATEGORIES):
        raise ContractError("QA registry must account for every primary category")
    seen_ids: set[str] = set()
    for category in PRIMARY_CATEGORIES:
        entry = categories[category]
        if not isinstance(entry, dict) or not isinstance(entry.get("state"), str):
            raise ContractError(f"QA registry category {category!r} is malformed")
        state = entry["state"]
        if state == "NOT_RUN":
            if set(entry) != {"state", "owner_role", "reason", "next_step"}:
                raise ContractError(f"NOT_RUN category {category!r} has unexpected fields")
            if entry.get("test_ids") not in (None, []):
                raise ContractError(f"NOT_RUN category {category!r} cannot declare required IDs")
            if not isinstance(entry.get("reason"), str) or not entry["reason"]:
                raise ContractError(f"NOT_RUN category {category!r} needs a reason")
            if not isinstance(entry.get("next_step"), str) or not entry["next_step"]:
                raise ContractError(f"NOT_RUN category {category!r} needs a next step")
            continue
        if state != "SUPPORTED":
            raise ContractError(f"unknown QA category state {state!r}")
        expected_fields = {
            "state", "coverage_state", "coverage_reason", "owner_role",
            "source_head", "test_ids",
        }
        if category == "api":
            expected_fields.add("network_api")
        if set(entry) != expected_fields:
            raise ContractError(f"QA category {category!r} has missing or unexpected fields")
        if entry.get("coverage_state") not in ("PARTIAL", "COMPLETE"):
            raise ContractError(f"QA category {category!r} needs PARTIAL or COMPLETE coverage state")
        if not isinstance(entry.get("coverage_reason"), str) or not entry["coverage_reason"]:
            raise ContractError(f"QA category {category!r} needs a coverage explanation")
        if entry.get("owner_role") not in ("functional-test-reviewer", "e2e-runner"):
            raise ContractError(f"QA category {category!r} has an invalid test owner role")
        head = entry.get("source_head")
        if (not isinstance(head, str) or len(head) != 40 or
                any(char not in "0123456789abcdef" for char in head) or
                not _git_commit_exists(root, head)):
            raise ContractError(f"QA category {category!r} needs a full source_head")
        test_ids = entry.get("test_ids")
        if not isinstance(test_ids, list) or not test_ids:
            raise ContractError(f"supported QA category {category!r} needs test IDs")
        if any(not isinstance(item, str) for item in test_ids):
            raise ContractError(f"QA category {category!r} test IDs must be strings")
        if len(test_ids) != len(set(test_ids)):
            raise ContractError(f"QA category {category!r} has duplicate test IDs")
        for test_id in test_ids:
            if not isinstance(test_id, str) or "::" not in test_id:
                raise ContractError(f"QA test ID is not a pytest node ID: {test_id!r}")
            path = test_id.split("::", 1)[0].replace("\\", "/")
            if path.startswith("tests/") is False or not _git_file_is_tracked(root, path):
                raise ContractError(f"QA test ID source is not a tracked tests path: {test_id!r}")
            if test_id in seen_ids:
                raise ContractError(f"QA test ID has multiple primary categories: {test_id!r}")
            seen_ids.add(test_id)
    network_api = categories["api"].get("network_api")
    if (not isinstance(network_api, dict) or
            set(network_api) != {"state", "reason"} or
            network_api["state"] != "UNSUPPORTED" or
            not isinstance(network_api["reason"], str) or not network_api["reason"]):
        raise ContractError("network API coverage must be explicitly UNSUPPORTED with a reason")
    regression = registry["regression"]
    if (not isinstance(regression, dict) or
            set(regression) != {"state", "coverage_state", "reason", "primary_categories"} or
            regression["state"] != "SUPPORTED_AGGREGATE" or
            regression["coverage_state"] not in ("PARTIAL", "COMPLETE") or
            not isinstance(regression["reason"], str) or not regression["reason"] or
            regression["primary_categories"] != list(REGRESSION_CATEGORIES)):
        raise ContractError("regression must be the ordered functional/integration/api/e2e aggregate")
    return registry, hashlib.sha256(raw).hexdigest()


def load_manifest(root: Path, relative_path: str) -> tuple[dict, str]:
    if not _git_file_is_tracked(root, relative_path):
        raise ContractError("v2 task manifest must be a tracked repository file")
    raw_manifest, _ = _read_repo_json(root, relative_path, max_bytes=2 * 1024 * 1024)
    manifest = validate_task_manifest(raw_manifest)
    if manifest.get("contract_version") != 2:
        raise ContractError("QA execution requires a v2 VST task manifest")
    return manifest, manifest_sha256(manifest)


def validate_projection(registry: dict, manifest: dict) -> None:
    """Require exact category/test-ID/selector projection into the run manifest."""
    categories: dict[str, dict[str, Any]] = registry["categories"]
    slots = {
        item["slot"]: item["receipt_type"]
        for item in manifest["required_receipts"]
        if item["receipt_type"] == "TestRun"
    }
    expected_slots = {
        category for category, entry in categories.items()
        if entry["state"] == "SUPPORTED"
    }
    if set(slots) != expected_slots:
        raise ContractError("v2 TestRun slots must exactly match supported QA primary categories")
    for category in expected_slots:
        expected = categories[category]["test_ids"]
        actual = sorted(
            item["test_id"] for item in manifest["required_tests"]
            if item["slot"] == category
        )
        if actual != sorted(expected):
            raise ContractError(f"v2 required test IDs differ from registry for {category!r}")
        commands = [
            item["argv"] for item in manifest["mandatory_commands"]
            if item["slot"] == category
        ]
        if len(commands) != 1:
            raise ContractError(f"category {category!r} needs exactly one pinned pytest command")
        expected_argv = [
            sys.executable, "-m", "pytest", "-q", "-p",
            "tools.qa.pytest_pass_plugin", *sorted(expected),
        ]
        if commands[0] != expected_argv:
            raise ContractError(
                f"category {category!r} command must exactly select its committed pytest node IDs"
            )
