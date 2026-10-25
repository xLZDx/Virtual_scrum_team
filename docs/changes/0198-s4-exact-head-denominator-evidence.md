# 0198 — Exact-head S4 ancestry, API, local, and E2E test evidence

## Source and environment identity

- Exact tested source/test HEAD: `20fa7bb5759d8c35159a942043a78ec93f3c79a1`.
- QA registry source_head: `173a7f25966fdbd92a36e0705be6fa2b2537aae7`.
- QA registry SHA-256: `37ec1a8009bae72f7fab7c933385cfaafe1395ea667b7d387a27faad4ad765db`.
- Worktree before runs: clean except pre-existing untracked `.codex-s4-final-review.patch`; it was not inspected, modified, staged, or removed. The same file remained the only untracked path after runs.
- Platform: Microsoft Windows NT 10.0.26300.0, Windows PowerShell.
- Python: `Python 3.14.3`; pytest: `pytest 8.4.2`.
- Each full run used `-p no:cacheprovider -p tools.qa.pytest_pass_plugin`.

## API denominator

Exact command:

```powershell
$manifest = Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json
$ids = @($manifest.categories.api.test_ids)
Write-Output "HEAD=$(git rev-parse HEAD)"
Write-Output "PYTHON=$(python --version 2>&1)"
Write-Output "SELECTOR_COUNT=$($ids.Count)"
python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin @ids
```

The category has **73 mapped selector IDs**; pytest expanded parametrized selectors to 93 executed cases. Result: **92 passed, 1 skipped, 0 failed** in 16.02 seconds. One pytest-asyncio deprecation warning was emitted: `asyncio.get_event_loop_policy` is deprecated and slated for removal in Python 3.16.

The sole skip was `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_symlinked_source_components_before_ast_acceptance`. On the same exact HEAD, its reason was confirmed with:

```powershell
python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_symlinked_source_components_before_ast_acceptance
```

It skipped because symlink creation raised `OSError: [WinError 1314] A required privilege is not held by the client` while creating the temporary link. The diagnostic took 0.28 seconds and emitted the same deprecation warning. This does not establish symlink behavior on POSIX or a Windows account with the required privilege.

Per-selector outcomes for all 73 API IDs:

- `tests/qa/test_s4_registry_contracts.py::test_s4_committed_registry_loads_with_resolved_nodes` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_accepts_single_primary_category_per_test_id` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_loader_rejects_noncanonical_path_even_when_ast_target_exists` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_manifest_projection_requires_exact_ids_and_commands` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_duplicate_primary_category_assignment` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_noncanonical_source_paths_before_ast_acceptance` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_provenance_outside_candidate_history` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_supported_category_without_required_ids` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_symlinked_source_components_before_ast_acceptance` — SKIPPED (Windows symlink creation unavailable; details below)
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_test_source_over_one_mib_before_ast_parse` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_unknown_pytest_node_id` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_registry_treats_recursion_error_during_ast_parse_as_unresolved` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_seeded_failure_catalog_rejects_hash_mismatch` — PASSED
- `tests/vst/test_e1_contracts.py::test_canonical_bytes_exact_form` — PASSED
- `tests/vst/test_e1_contracts.py::test_canonical_bytes_unserialisable_raises_contract_error` — PASSED
- `tests/vst/test_e1_contracts.py::test_derive_testrun_pass_when_everything_matches` — PASSED
- `tests/vst/test_e1_contracts.py::test_gate_decision_valid_and_deep_copy` — PASSED
- `tests/vst/test_e1_contracts.py::test_manifest_sha256_matches_independent_computation_and_is_stable` — PASSED
- `tests/vst/test_e1_contracts.py::test_manifest_valid_returns_equal_deep_copy` — PASSED
- `tests/vst/test_e1_contracts.py::test_normalize_principal` — PASSED
- `tests/vst/test_e1_contracts.py::test_receipt_sha256_matches_independent_computation_and_is_stable` — PASSED
- `tests/vst/test_e1_contracts.py::test_receipt_valid_each_type_returns_deep_copy` — PASSED
- `tests/vst/test_e2_gate.py::test_forged_unsigned_receipt_rejected` — PASSED
- `tests/vst/test_e2_gate.py::test_stale_head_one_receipt_is_a_hard_reason_and_the_slot_is_unmet` — PASSED
- `tests/vst/test_e3_store.py::test_acquire_after_ttl_fences_live_lease_and_old_epoch_writes` — PASSED
- `tests/vst/test_e3_store.py::test_acquire_epoch_exhausted_counter_is_refused` — PASSED
- `tests/vst/test_e3_store.py::test_busy_database_raises_store_busy_error_and_writes_nothing` — PASSED
- `tests/vst/test_e3_store.py::test_expired_lease_is_reaped_on_next_acquire_and_slot_reused` — PASSED
- `tests/vst/test_e3_store.py::test_lease_attempts_are_consecutive_from_one` — PASSED
- `tests/vst/test_e3_store.py::test_lease_statuses_follow_the_closed_enum` — PASSED
- `tests/vst/test_e3_store.py::test_lost_attempt_must_be_marked_before_retry` — PASSED
- `tests/vst/test_e3_store.py::test_lost_attempts_count_toward_retry_cap_and_the_next_lease_commits_a_signed_marker` — PASSED
- `tests/vst/test_e3_store.py::test_mark_budget_exceeded_writes_signed_blocked_receipt_and_event` — PASSED
- `tests/vst/test_e3_store.py::test_no_dangling_transaction_after_success_and_after_error` — PASSED
- `tests/vst/test_e3_store.py::test_register_task_returns_manifest_hash_and_get_manifest_roundtrips` — PASSED
- `tests/vst/test_e3_store.py::test_render_state_md_shows_the_phase` — PASSED
- `tests/vst/test_e3_store.py::test_renew_epoch_extends_liveness_without_changing_epoch` — PASSED
- `tests/vst/test_e3_store.py::test_reopen_of_a_version_three_database_keeps_data` — PASSED
- `tests/vst/test_e3_store.py::test_set_phase_by_live_owner_changes_phase_and_records_event` — PASSED
- `tests/vst/test_e3_store.py::test_supervisor_path_rejects_worker_slot_receipts` — PASSED
- `tests/vst/test_e4_runner.py::test_artifact_digests_maps_each_path` — PASSED
- `tests/vst/test_e4_runner.py::test_artifact_through_a_symlink_or_junction_to_outside_is_refused` — PASSED
- `tests/vst/test_e4_runner.py::test_build_environment_unit` — PASSED
- `tests/vst/test_e4_runner.py::test_failing_command_nonzero_exit_gives_fail` — PASSED
- `tests/vst/test_e4_runner.py::test_file_sha256_known_vectors` — PASSED
- `tests/vst/test_e4_runner.py::test_receipt_is_bound_to_the_manifest_not_to_caller_supplied_ids` — PASSED
- `tests/vst/test_e4_runner.py::test_signature_is_scoped_to_the_receipt_label` — PASSED
- `tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation` — PASSED
- `tests/vst/test_s2_operation_recovery.py::test_completed_override_action_id_with_changed_valid_signed_record_rejected_after_restart` — PASSED
- `tests/vst/test_s2_operation_recovery.py::test_external_operation_intent_and_completion_are_committed_around_callback` — PASSED
- `tests/vst/test_s2_operation_recovery.py::test_external_operation_timeout_stays_pending_and_same_key_payload_recovers` — PASSED
- `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` — PASSED
- `tests/vst/test_s2_runner_lifecycle.py::test_failed_start_side_effect_blocks_restart_until_verified_reconciliation` — PASSED
- `tests/vst/test_s2_runner_lifecycle.py::test_idempotent_push_and_pull_request_use_local_bare_remote` — PASSED
- `tests/vst/test_s2_runner_lifecycle.py::test_lifecycle_transition_table_rejects_unlisted_pairs` — PASSED
- `tests/vst/test_s2_runner_lifecycle.py::test_restart_resumes_the_correct_cleanup_phase_after_reconciliation` — PASSED
- `tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides` — PASSED
- `tests/vst/test_s2_store_lifecycle.py::test_coordinator_oserror_is_normalized_and_store_connection_is_closed` — PASSED
- `tests/vst/test_s2_store_lifecycle.py::test_gate_and_anchor_readers_racing_writer_do_not_permanently_lock_store` — PASSED
- `tests/vst/test_s2_store_lifecycle.py::test_store_and_supervisor_refuse_lease_start_or_decision_before_reconciliation` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_acquire_epoch_idempotent_replay_keeps_one_new_epoch` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_append_manual_override_rejects_unsigned_record_without_control_write` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_append_receipt_idempotent_replays_one_receipt` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_begin_action_rejects_mismatched_transaction_id_without_write` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_charge_idempotent_replay_updates_budget_once` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_consume_preflight_is_one_time_and_records_probe` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_lookup_idempotent_operation_returns_bound_completed_result` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_prepare_run_binds_fresh_run_and_probe_nonce` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_resume_epoch_idempotent_rejects_unrecorded_outcome_without_mutation` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_startup_reconcile_verifies_current_store_history` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_stop_attempt_fenced_advances_epoch_and_fences_live_lease` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_supervisor_resume_runs_only_from_stopped_lifecycle` — PASSED
- `tests/vst/test_s4_python_api_entrypoints.py::test_api_validate_task_manifest_v2_rejects_missing_contract_fields` — PASSED

## Functional, integration, and seeded-failure denominator

Exact command:

```powershell
$manifest = Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json
$ids = @($manifest.categories.functional.test_ids) + @($manifest.categories.integration.test_ids) + @($manifest.categories.'seeded-failure'.test_ids)
Write-Output "HEAD=$(git rev-parse HEAD)"
Write-Output "PYTHON=$(python --version 2>&1)"
Write-Output "PYTEST=$(python -m pytest --version 2>&1)"
Write-Output "SELECTOR_COUNT=$($ids.Count)"
python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin @ids
```

The category counts are functional **19**, integration **6**, seeded-failure **7** (32 selector IDs). Result: **32 passed, 0 skipped, 0 failed** in 38.22 seconds. One pytest-asyncio deprecation warning as above. The five new ancestry falsifiers each passed: return code 0 -> true; return code 1 -> false; another exit code -> typed `ContractError`; second timeout after one retry -> typed `ContractError`; `OSError` -> typed invocation `ContractError`.

Per-selector outcomes for all 32 IDs:

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
- `tests/qa/test_s4_registry_contracts.py::test_s4_git_ancestry_returncode_zero_is_true` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_git_ancestry_returncode_one_is_false` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_git_ancestry_other_returncode_is_contract_error` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_git_ancestry_second_timeout_is_contract_error` — PASSED
- `tests/qa/test_s4_registry_contracts.py::test_s4_git_ancestry_oserror_is_contract_error` — PASSED
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

## E2E denominator

The E2E runner executed the existing **12 mapped selector IDs** on the same exact source/test HEAD. Exact PowerShell command:

```powershell
$manifest = Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json; $ids = @($manifest.categories.e2e.test_ids); Write-Output "HEAD=$(git rev-parse HEAD)"; Write-Output "PYTHON=$(python --version 2>&1)"; Write-Output "SELECTOR_COUNT=$($ids.Count)"; python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin @ids
```

Environment: Windows PowerShell, Python 3.14.3, pytest 8.4.2. Result: **12 passed, 0 skipped, 0 failed** in 19.68 seconds. One pytest-asyncio deprecation warning as above. The E2E agent reported that HEAD remained unchanged and worktree remained clean except the same pre-existing untracked patch.

Per-selector outcomes for all 12 E2E IDs:

- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_commits_only_the_manifest_scoped_synthetic_change` — PASSED
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_rejects_out_of_scope_edit_before_worker_invocation` — PASSED
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_app_checkpoint_can_resume_same_effect_under_new_store_epoch` — PASSED
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_stop_fences_interrupted_attempt_idempotently_and_rejects_stale_start` — PASSED
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_candidate_identity_cannot_be_self_selected` — PASSED
- `tests/qa/test_s4_qa_e2e.py::test_s4_e5_synthetic_slice_cli_journey_preserves_gate_and_restart_evidence` — PASSED
- `tests/qa/test_s4_qa_e2e.py::test_s4_e6_qa_snapshot_cli_refuses_an_unapproved_distribution` — PASSED
- `tests/qa/test_s4_report_bound_e2e.py::test_s4_native_pytest_discovery_accounts_exact_required_ids` — PASSED
- `tests/qa/test_s4_report_bound_e2e.py::test_s4_signed_runner_receipt_and_artifact_gate_approve_at_exact_head` — PASSED
- `tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_stale_signed_runner_receipt` — PASSED
- `tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_missing_signed_artifact` — PASSED
- `tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_corrupt_signed_artifact` — PASSED

## Scope and decision

All requested local test denominators pass on exact source/test HEAD `20fa7bb5759d8c35159a942043a78ec93f3c79a1`, with one explicit Windows symlink-privilege skip in API coverage. E2E denominator remains `PARTIAL` as mapped; these 12 selectors passing does not clear external v2 signer, trusted report-bound runtime, or sandbox gates, which remain `NOT_RUN`. No source, test, category mapping, or S4 report files changed after test/mapping HEAD `20fa7bb`. This record and governance metadata are evidence-only.

Executor: Codex
