"""Regenerate the committed QA category registry from statically declared tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .registry import _function_selectors, _latest_path_commit, git_head, git_root, inventory_test_files


TEST_FILE_CATEGORIES = {
    "test_s2_contract_gate.py": "functional",
    "test_s2_diffgate.py": "functional",
    "test_e1_contracts.py": "api",
    "test_e2_gate.py": "api",
    "test_e3_store.py": "api",
    "test_e4_runner.py": "api",
    "test_s2_sandbox_probe.py": "api",
    "test_s3_worker_adapter.py": "api",
    "test_e5_process_death.py": "integration",
    "test_s2_operation_recovery.py": "integration",
    "test_s2_runner_lifecycle.py": "integration",
    "test_s2_store_lifecycle.py": "integration",
    "test_e5_slice.py": "e2e",
    "test_s3_worker_pilot_e2e.py": "e2e",
}
PRIMARY_CATEGORIES = ("functional", "integration", "api", "e2e", "seeded-failure")
POLICY_NOT_RUN = {
    "tests/vst/test_e4_runner.py::test_background_process_holding_the_pipe_gives_exit_minus_four_and_capture_incomplete":
        "NOT_RUN: this scenario invokes process-kill cleanup; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_capture_incomplete_takes_precedence_over_output_truncation":
        "NOT_RUN: this scenario invokes process-kill cleanup; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_s2_runner_lifecycle.py::test_e4_platform_containment_scenarios_not_run":
        "NOT_RUN: process-kill/kill-table containment scenarios are explicitly prohibited for this S4 run.",
    "tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_cli_timeout_is_nonapproving_without_install_or_fallback":
        "NOT_RUN: this scenario invokes process-tree termination; process-kill execution is prohibited for this S4 run.",
}


def _category_for_test_file(source_path: str) -> str:
    """Classify new QA test modules deterministically without changing VST ownership."""
    filename = Path(source_path).name
    explicit = TEST_FILE_CATEGORIES.get(filename)
    if explicit is not None:
        return explicit
    parts = Path(source_path).as_posix().split("/")
    if parts[:2] != ["tests", "qa"]:
        raise ValueError(f"no primary category is assigned to {source_path}")
    if "seeded_failure" in parts[2:-1] or filename.startswith("test_s4_seeded_failure"):
        return "seeded-failure"
    stem = Path(filename).stem
    for category in ("functional", "integration", "api", "e2e"):
        if stem.startswith(f"test_s4_{category}_"):
            return category
    if stem.startswith("test_s4_"):
        return "functional"
    raise ValueError(f"QA test module must use the test_s4_ filename convention: {source_path}")


def build_registry(root_path: str | Path) -> dict:
    root = git_root(root_path)
    source_head = git_head(root)
    inventory: list[dict[str, str]] = []
    tests: list[dict[str, str]] = []
    category_ids: dict[str, list[str]] = {category: [] for category in PRIMARY_CATEGORIES}

    for source_path in inventory_test_files(root):
        category = _category_for_test_file(source_path)
        content = (root / Path(source_path)).read_bytes()
        commit = _latest_path_commit(root, source_path)
        inventory.append(
            {
                "path": source_path,
                "source_commit": commit,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
        selectors = _function_selectors(source_path, content)
        for selector in sorted(selectors):
            tests.append(
                {
                    "test_id": selector,
                    "selector": selector,
                    "source_path": source_path,
                    "source_commit": commit,
                    "primary_category": category,
                }
            )
            category_ids[category].append(selector)

    if not tests:
        raise ValueError("no static pytest selectors were found")
    categories = {
        category: {
            "status": "SUPPORTED",
            "test_ids": sorted(category_ids[category]),
            "not_run_reasons": {
                selector: reason
                for selector, reason in sorted(POLICY_NOT_RUN.items())
                if selector in category_ids[category]
            },
            "reason": None,
        }
        for category in PRIMARY_CATEGORIES
        if category != "seeded-failure"
    }
    seeded_ids = sorted(category_ids["seeded-failure"])
    categories["seeded-failure"] = {
        "status": "SUPPORTED" if seeded_ids else "NOT_RUN",
        "test_ids": seeded_ids,
        "not_run_reasons": {},
        "reason": None if seeded_ids else "The test-author phase has not added committed fixture-consuming tests yet.",
    }
    for selector in category_ids["integration"]:
        if selector.startswith("tests/vst/test_e5_process_death.py::"):
            categories["integration"]["not_run_reasons"][selector] = (
                "NOT_RUN: this selector launches a child that terminates via os._exit;"
                " process-death execution is prohibited for this S4 run."
            )
    runnable_ids = {
        category: sorted(
            selector for selector in category_ids[category]
            if selector not in categories[category]["not_run_reasons"]
        )
        for category in ("functional", "integration", "api", "e2e")
    }
    categories["regression"] = {
        "status": "AGGREGATE",
        "test_ids": sorted(
            selector
            for category in ("functional", "integration", "api", "e2e")
            for selector in runnable_ids[category]
        ),
        "not_run_reasons": {
            selector: categories[category]["not_run_reasons"][selector]
            for category in ("functional", "integration", "api", "e2e")
            for selector in categories[category]["not_run_reasons"]
        },
        "reason": None,
    }
    return {
        "schema_version": 1,
        "registry_version": "1",
        "artifacts": {
            category: {
                "report": f"docs/sdlc/evidence/qa/{category}.report.jsonl",
                "stdout": f"docs/sdlc/evidence/qa/{category}.stdout.txt",
                "stderr": f"docs/sdlc/evidence/qa/{category}.stderr.txt",
            }
            for category in (
                "functional", "integration", "api", "e2e", "regression", "seeded-failure"
            )
        },
        "source_head": source_head,
        "source_inventory": inventory,
        "tests": sorted(tests, key=lambda item: item["test_id"]),
        "categories": categories,
        "aggregates": {"regression_members": ["functional", "integration", "api", "e2e"]},
        "unsupported_apis": {
            "http": {
                "status": "UNSUPPORTED",
                "reason": "The repository exposes Python modules and has no declared HTTP route contract.",
                "evidence_paths": [
                    "docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md",
                    "tools/vst/__init__.py",
                ],
            }
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    registry = build_registry(args.repo_root)
    data = json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    target = git_root(args.repo_root) / "docs" / "qa" / "categories.json"
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding="utf-8", newline="\n")
        print(f"wrote {target.relative_to(git_root(args.repo_root)).as_posix()}")
    else:
        sys.stdout.write(data)
    return 0


if __name__ == "__main__":  # pragma: no cover - code-generation CLI
    raise SystemExit(main())
