# 0186 — S4 mapped functional, integration, and seeded selectors pass

## Run identity

- Candidate HEAD: `97c39000331c96b0184b1fb18d9ac2ba65c5658d`
- Worktree: `D:\Repo\Virtual_scrum_team-s4`, branch `s4-native-qa-runner`; worktree was clean before execution.
- Shell: Windows PowerShell
- Python: `Python 3.14.3`
- Pytest plugin: `tools.qa.pytest_pass_plugin`; cache provider disabled.

## Focused ancestry regressions

Command: `python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_seeded_failures.py::test_seeded_out_of_scope_diff_fails tests/qa/test_s4_registry_contracts.py::test_s4_committed_registry_loads_with_resolved_nodes`

Result: **2 passed, 0 failed**, 17.13 seconds. One pytest-asyncio deprecation warning was emitted. Both checks that had gated the full denominator passed at the exact candidate HEAD.

## Full mapped denominator

Exact PowerShell command:

```powershell
$manifest = Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json
$ids = @($manifest.categories.functional.test_ids) + @($manifest.categories.integration.test_ids) + @($manifest.categories.'seeded-failure'.test_ids)
Write-Output "HEAD=$(git rev-parse HEAD)"
Write-Output "PYTHON=$(python --version 2>&1)"
Write-Output "SELECTOR_COUNT=$($ids.Count)"
python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin @ids
```

Observed identity: HEAD `97c39000331c96b0184b1fb18d9ac2ba65c5658d`; Python 3.14.3; 27 selectors. Result: **27 passed, 0 failed, 0 skipped**, 91.87 seconds. One pytest-asyncio deprecation warning was emitted; the process exited 0.

The category breakdown was functional 14/14, integration 6/6, seeded-failure 7/7. The exact selector outcomes are:

- `tests/vst/test_s3_worker_adapter.py::test_ac1_request_contract_enforces_identity_fence_and_payload_bounds` — PASSED
- `tests/vst/test_s3_worker_adapter.py::test_ac1_response_contract_rejects_untyped_or_oversized_worker_claims` — PASSED
- `tests/vst/test_s3_worker_adapter.py::test_ac2_resume_and_stop_requests_require_new_fence_and_bound_keys` — PASSED
- `tests/vst/test_s3_worker_adapter.py::test_ac3_idempotency_replay_returns_original_and_rejects_changed_payload` — PASSED
- `tests/vst/test_s3_worker_adapter.py::test_ac3_budget_exact_cap_replay_over_cap_and_stale_snapshot` — PASSED
- `tests/vst/test_s3_worker_adapter.py::test_ac3_zero_budget_allows_zero_charge_but_blocks_positive_charge` — PASSED
- `tests/vst/test_s3_worker_adapter.py::test_ac4_resume_accepts_only_returned_named_app_checkpoint_and_is_idempotent` — PASSED
- `tests/vst/test_s3_worker_adapter.py::test_ac4_worker_state_alone_never_creates_verification_receipts` — PASSED
- `tests/vst/test_e2_gate.py::test_approve_independent_of_receipt_order` — PASSED
- `tests/vst/test_e2_gate.py::test_no_receipts_gives_modify_with_everything_unmet` — PASSED
- `tests/vst/test_e1_contracts.py::test_manifest_unknown_field_rejected` — PASSED
- `tests/vst/test_e2_gate.py::test_signature_by_wrong_key_rejected` — PASSED
- `tests/vst/test_e4_runner.py::test_replay_against_another_head_is_rejected` — PASSED
- `tests/vst/test_e4_runner.py::test_skipped_or_xfail_ids_prevent_pass` — PASSED
- `tests/vst/test_e4_runner.py::test_harmless_command_produces_signed_passing_testrun` — PASSED
- `tests/vst/test_e3_store.py::test_store_output_is_approved_by_the_gate` — PASSED
- `tests/vst/test_e4_runner.py::test_runner_receipt_is_approved_by_gate_at_its_head_and_epoch` — PASSED
- `tests/vst/test_s2_runner_lifecycle.py::test_signing_request_exact_schema_and_replay_protocol_without_os_claim` — PASSED
- `tests/vst/test_s2_runner_lifecycle.py::test_hook_free_publication_transfers_source_only_commit_without_running_pre_push` — PASSED
- `tests/vst/test_s2_store_lifecycle.py::test_supervisor_receipt_replay_is_idempotent_and_payload_conflict_fails` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_seeded_failure_rejects_invalid_manifest_and_records_observation` — PASSED
- `tests/qa/test_s4_seeded_failures.py::test_seeded_stale_head_rejects_current_gate_decision` — PASSED
- `tests/qa/test_s4_seeded_failures.py::test_seeded_missing_receipt_is_non_approving` — PASSED
- `tests/qa/test_s4_seeded_failures.py::test_seeded_invalid_signature_is_rejected` — PASSED
- `tests/qa/test_s4_seeded_failures.py::test_seeded_out_of_scope_diff_fails` — PASSED
- `tests/qa/test_s4_seeded_failures.py::test_seeded_skipped_required_id_derives_failure` — PASSED
- `tests/qa/test_s4_seeded_failures.py::test_seeded_artifact_digest_mismatch_is_non_approving` — PASSED

## Scope and limits

This run covers only the committed functional, integration, and seeded-failure selector arrays. API and E2E selectors were not run here. The mapped run establishes local test execution at this Windows/Python environment; it does not establish the separate trusted signer OS identity, report-bound runner, sandbox, or POSIX acceptance paths. No product source or S4 report was modified.

## Decision

The previous ancestry mismatch did not recur in either focused regression or the complete 27-selector run. Record the functional, integration, and seeded-failure execution evidence as PASS for this exact HEAD and environment. Keep separate runtime and platform gates in their existing evidence state.

Executor: Codex
