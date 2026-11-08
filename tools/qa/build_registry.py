"""Regenerate the committed QA category registry from statically declared tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .registry import (
    RUNTIME_PROFILES,
    RegistryError,
    _function_selectors,
    _read_head_blob,
    _latest_path_commit,
    git_head,
    check_worktree_clean,
    git_root,
    inventory_test_files,
    required_runtime_profiles,
)


TEST_FILE_CATEGORIES = {
    "test_s2_contract_gate.py": "functional",
    "test_s2_diffgate.py": "functional",
    "test_s4_functional_worker_identity.py": "identity",
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
# Modules that exist on main but were not classified on the S4 branch. Keyed by
# full repository path; an unlisted module fails closed in _category_for_test_file.
MAIN_TEST_FILE_CATEGORIES = {
    "tests/qa/test_s4a_registry.py": "functional",
    "tests/qa/test_s4b_runner.py": "functional",
    "tests/af/test_s2_review_source_fidelity.py": "functional",
    "tests/uc/test_adapter.py": "functional",
    "tests/uc/test_aeve_probe.py": "functional",
    "tests/uc/test_cli_measure.py": "functional",
    "tests/uc/test_cli_token_baseline.py": "functional",
    "tests/uc/test_contracts.py": "functional",
    "tests/uc/test_measure.py": "functional",
    "tests/uc/test_role_table.py": "functional",
    "tests/uc/test_router.py": "functional",
    "tests/uc/test_token_baseline.py": "functional",
    "tests/uc_e2e/test_u1_router_e2e.py": "e2e",
    "tests/vst/test_s2_4e_store_windows_preflight_contract.py": "api",
    "tests/vst/test_s2_assignment_basis.py": "functional",
    "tests/vst/test_s2_assignment_bootstrap.py": "functional",
    "tests/vst/test_s2_bootstrap_runtime.py": "integration",
    "tests/vst/test_s2_dispatch_intent_client_schema.py": "api",
    "tests/vst/test_s2_dispatch_issuance_contract.py": "api",
    "tests/vst/test_s2_dispatch_owner_latch.py": "functional",
    "tests/vst/test_s2_dispatch_owner_service.py": "integration",
    "tests/vst/test_s2_dispatch_owner_transport.py": "integration",
    "tests/vst/test_s2_e8_synthetic_lifecycle.py": "integration",
    "tests/vst/test_s2_machine_authorization_v2.py": "functional",
    "tests/vst/test_s2_machine_source_contracts.py": "api",
    "tests/vst/test_s2_owner_completed_receipt_contract.py": "api",
    "tests/vst/test_s2_owner_runner_functional.py": "functional",
    "tests/vst/test_s2_owner_runner_windows_e2e.py": "e2e",
    "tests/vst/test_s2_peer_pidfd.py": "integration",
    "tests/vst/test_s2_persistent_runner_service.py": "integration",
    "tests/vst/test_s2_preflight_capture.py": "functional",
    "tests/vst/test_s2_preflight_host_capture.py": "functional",
    "tests/vst/test_s2_root_dispatch_integration.py": "integration",
    "tests/vst/test_s2_runtime_bootstrap_transaction.py": "integration",
    "tests/vst/test_s2_runtime_bundle.py": "functional",
    "tests/vst/test_s2_runtime_config_bundle.py": "functional",
    "tests/vst/test_s2_runtime_stage_policy.py": "functional",
    "tests/vst/test_s2_signed_dispatch_instruction.py": "api",
    "tests/vst/test_s2_source_staging_plan.py": "functional",
    "tests/vst/test_s2_stage_only_install.py": "integration",
    "tests/vst/test_s2_store_backed_pubsub.py": "integration",
    "tests/vst/test_s2_wsl_bundle_verifiers.py": "functional",
}
PRIMARY_CATEGORIES = ("functional", "integration", "api", "e2e", "identity", "seeded-failure")
POLICY_NOT_RUN = {
    "tests/vst/test_e4_runner.py::test_timeout_records_exit_minus_one_and_fails":
        "NOT_RUN: this scenario invokes timeout process-tree cleanup; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_timeout_kills_the_whole_process_tree":
        "NOT_RUN: this scenario invokes process-tree termination; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_overall_deadline_stops_later_commands_without_running_them":
        "NOT_RUN: this scenario invokes timeout process-tree cleanup; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_deadline_limits_a_command_below_its_own_timeout":
        "NOT_RUN: this scenario invokes timeout process-tree cleanup; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_timeout_does_not_prevent_following_commands_within_the_deadline":
        "NOT_RUN: this scenario invokes timeout process-tree cleanup; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_report_capture_incomplete_is_false_for_every_normal_outcome":
        "NOT_RUN: a parameterized case invokes timeout process-tree cleanup; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_stray_descendant_is_killed_after_the_root_command_exited_normally":
        "NOT_RUN: this scenario invokes process-tree termination; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_thread_start_failure_kills_the_child_and_cleans_up":
        "NOT_RUN: this scenario invokes child process termination; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_thread_start_failure_for_the_first_reader_also_cleans_up":
        "NOT_RUN: this scenario invokes child process termination; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_job_is_closed_when_thread_start_fails":
        "NOT_RUN: this Windows-only scenario invokes child process termination; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_background_process_holding_the_pipe_gives_exit_minus_four_and_capture_incomplete":
        "NOT_RUN: this scenario invokes process-kill cleanup; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_root_that_survives_the_kill_gives_exit_minus_four":
        "NOT_RUN: this scenario deliberately exercises timeout and post-timeout cleanup behavior; timeout/process cleanup execution is prohibited for this S4 run.",
    "tests/vst/test_e4_runner.py::test_capture_incomplete_takes_precedence_over_output_truncation":
        "NOT_RUN: this scenario invokes process-kill cleanup; process-kill execution is prohibited for this S4 run.",
    "tests/vst/test_s2_runner_lifecycle.py::test_e4_platform_containment_scenarios_not_run":
        "NOT_RUN: process-kill/kill-table containment scenarios are explicitly prohibited for this S4 run.",
    "tests/vst/test_s2_sandbox_probe.py::test_real_sandbox_inventory_has_all_required_properties":
        "NOT_RUN: the test placeholder is unconditionally skipped and requires run-bound sandbox attestation.",
    "tests/vst/test_s2_sandbox_probe.py::test_e8_sandbox_bakeoff_scenarios_not_run":
        "NOT_RUN: full E8 acceptance requires process-death/STOP execution and a run-bound sandbox; prohibited for this S4 run.",
    "tests/vst/test_s2_runner_lifecycle.py::test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key":
        "NOT_RUN: this selector exercises timeout recovery; timeout scenarios are prohibited for this S4 run.",
}
def _runtime_profiles_for_selector(selector: str) -> list[str]:
    if selector in POLICY_NOT_RUN or selector.startswith("tests/vst/test_e5_process_death.py::"):
        return []
    return required_runtime_profiles(selector)


def _category_for_test_file(source_path: str) -> str:
    """Classify new QA test modules deterministically without changing VST ownership."""
    filename = Path(source_path).name
    mapped = MAIN_TEST_FILE_CATEGORIES.get(source_path)
    if mapped is not None:
        return mapped
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
    check_worktree_clean(root)
    source_head = git_head(root)
    inventory: list[dict[str, str]] = []
    tests: list[dict[str, Any]] = []
    category_ids: dict[str, list[str]] = {category: [] for category in PRIMARY_CATEGORIES}

    for source_path in inventory_test_files(root):
        category = _category_for_test_file(source_path)
        content = _read_head_blob(root, source_path)
        normalized_content = content.replace(b"\r\n", b"\n")
        commit = _latest_path_commit(root, source_path)
        inventory.append(
            {
                "path": source_path,
                "source_commit": commit,
                "sha256": hashlib.sha256(normalized_content).hexdigest(),
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
                    "runtime_profiles": _runtime_profiles_for_selector(selector),
                }
            )
            category_ids[category].append(selector)

    if not tests:
        raise ValueError("no static pytest selectors were found")
    stale_policy = sorted(
        selector for selector in POLICY_NOT_RUN
        if selector.split("::", 1)[0] in {item["path"] for item in inventory}
        and selector not in {test["selector"] for test in tests}
    )
    if stale_policy:
        raise ValueError(f"POLICY_NOT_RUN names selectors absent from source: {stale_policy}")
    categories = {
        category: {
            "status": "SUPPORTED" if category_ids[category] else "NOT_RUN",
            "test_ids": sorted(category_ids[category]),
            "not_run_reasons": {
                selector: reason
                for selector, reason in sorted(POLICY_NOT_RUN.items())
                if selector in category_ids[category]
            },
            "reason": None if category_ids[category] else "No committed test module is assigned to this category yet.",
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
    for category in ("functional", "integration", "api", "e2e", "identity", "seeded-failure"):
        # A category that holds tests must keep at least one runnable selector; a
        # NOT_RUN/UNSUPPORTED category must hold none (registry validator contract).
        if category_ids[category] and not (
            set(category_ids[category]) - set(categories[category]["not_run_reasons"])
        ):
            raise RegistryError(f"category {category} holds only NOT_RUN selectors; cannot be SUPPORTED")
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
        "schema_version": 2,
        "registry_version": "2",
        "runtime_profiles": list(RUNTIME_PROFILES),
        "artifacts": {
            category: {
                "report": f"docs/sdlc/evidence/qa/{category}.report.jsonl",
                "stdout": f"docs/sdlc/evidence/qa/{category}.stdout.txt",
                "stderr": f"docs/sdlc/evidence/qa/{category}.stderr.txt",
            }
            for category in (
                "functional", "integration", "api", "e2e", "identity", "regression", "seeded-failure"
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
