# S4 Python API callable inventory

Scope: source-defined non-underscore top-level functions/classes and public instance/class methods in the five modules named by S4.3.2. `supervisor.py` also has an explicit `__all__` exporting `Supervisor` and `STOP_TRANSITIONS`. The other modules do not define `__all__`; inventory uses the Python non-underscore convention. Underscore-prefixed helpers and nested implementation classes are excluded. No HTTP route contract is present; `network_api` remains `UNSUPPORTED`.

For each name, the candidate ID is the first test function whose parsed body references that exact callable name, preferring an API-mapped ID and then the focused S4 API test file. This is a source-derived test mapping aid; the exact assertion is reviewed in the test body, and mere test existence is not execution evidence. Any candidate in another primary category remains there; the registry forbids cross-category duplicate IDs.

| Module | Source-defined public name | Existing candidate test ID | Current category status |
|---|---|---|---|
| `contracts.py` | `ContractError` | `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_duplicate_primary_category_assignment` | MAPPED `api` |
| `contracts.py` | `canonical_bytes` | `tests/vst/test_e1_contracts.py::test_canonical_bytes_exact_form` | EXISTS, NOT YET IN API CATEGORY |
| `contracts.py` | `receipt_sha256` | `tests/vst/test_e1_contracts.py::test_receipt_sha256_matches_independent_computation_and_is_stable` | EXISTS, NOT YET IN API CATEGORY |
| `contracts.py` | `manifest_sha256` | `tests/vst/test_e1_contracts.py::test_manifest_sha256_matches_independent_computation_and_is_stable` | EXISTS, NOT YET IN API CATEGORY |
| `contracts.py` | `normalize_principal` | `tests/vst/test_e1_contracts.py::test_normalize_principal` | EXISTS, NOT YET IN API CATEGORY |
| `contracts.py` | `validate_task_manifest` | `tests/vst/test_e1_contracts.py::test_manifest_valid_returns_equal_deep_copy` | MAPPED `api` |
| `contracts.py` | `validate_task_manifest_v2` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_validate_task_manifest_v2_rejects_missing_contract_fields` | EXISTS, NOT YET IN API CATEGORY |
| `contracts.py` | `validate_receipt` | `tests/vst/test_e1_contracts.py::test_receipt_valid_each_type_returns_deep_copy` | EXISTS, NOT YET IN API CATEGORY |
| `contracts.py` | `derive_result` | `tests/vst/test_e1_contracts.py::test_derive_testrun_pass_when_everything_matches` | EXISTS, NOT YET IN API CATEGORY |
| `contracts.py` | `validate_gate_decision` | `tests/vst/test_e1_contracts.py::test_gate_decision_valid_and_deep_copy` | EXISTS, NOT YET IN API CATEGORY |
| `gate.py` | `evaluate` | `tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation` | MAPPED `api` |
| `store.py` | `StoreError` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` | MAPPED `api` |
| `store.py` | `StoreBusyError` | `tests/vst/test_e3_store.py::test_busy_database_raises_store_busy_error_and_writes_nothing` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` | MAPPED `api` |
| `store.py` | `Store.close` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` | MAPPED `api` |
| `store.py` | `Store.init_slots` | `tests/vst/test_e3_store.py::test_expired_lease_is_reaped_on_next_acquire_and_slot_reused` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.open_story` | `tests/vst/test_e3_store.py::test_reopen_of_a_version_three_database_keeps_data` | MAPPED `api` |
| `store.py` | `Store.current_epoch` | `tests/vst/test_e3_store.py::test_reopen_of_a_version_three_database_keeps_data` | MAPPED `api` |
| `store.py` | `Store.acquire_epoch` | `tests/vst/test_e3_store.py::test_no_dangling_transaction_after_success_and_after_error` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.acquire_epoch_idempotent` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_acquire_epoch_idempotent_replay_keeps_one_new_epoch` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.resume_epoch_idempotent` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_resume_epoch_idempotent_rejects_unrecorded_outcome_without_mutation` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.renew_epoch` | `tests/vst/test_e3_store.py::test_renew_epoch_extends_liveness_without_changing_epoch` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.release_epoch` | `tests/vst/test_e3_store.py::test_acquire_epoch_exhausted_counter_is_refused` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.set_phase` | `tests/vst/test_e3_store.py::test_set_phase_by_live_owner_changes_phase_and_records_event` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.get_phase` | `tests/vst/test_e3_store.py::test_reopen_of_a_version_three_database_keeps_data` | MAPPED `api` |
| `store.py` | `Store.register_task` | `tests/vst/test_e3_store.py::test_register_task_returns_manifest_hash_and_get_manifest_roundtrips` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.get_manifest` | `tests/vst/test_e3_store.py::test_register_task_returns_manifest_hash_and_get_manifest_roundtrips` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.acquire_lease` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_stop_attempt_fenced_advances_epoch_and_fences_live_lease` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.failed_attempts` | `tests/vst/test_e3_store.py::test_lost_attempts_count_toward_retry_cap_and_the_next_lease_commits_a_signed_marker` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.heartbeat` | `tests/vst/test_e3_store.py::test_acquire_after_ttl_fences_live_lease_and_old_epoch_writes` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.release_lease` | `tests/vst/test_e3_store.py::test_lease_attempts_are_consecutive_from_one` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.reap_expired` | `tests/vst/test_e3_store.py::test_lease_statuses_follow_the_closed_enum` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.append_receipt` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_stop_attempt_fenced_advances_epoch_and_fences_live_lease` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.append_supervisor_receipt` | `tests/vst/test_e3_store.py::test_supervisor_path_rejects_worker_slot_receipts` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.receipts_for_task` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_stop_attempt_fenced_advances_epoch_and_fences_live_lease` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.evaluate_gate` | `tests/vst/test_s2_store_lifecycle.py::test_gate_and_anchor_readers_racing_writer_do_not_permanently_lock_store` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.record_event` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_startup_reconcile_verifies_current_store_history` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.append_manual_override` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_append_manual_override_rejects_unsigned_record_without_control_write` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.begin_action` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_begin_action_rejects_mismatched_transaction_id_without_write` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.reconcile_action` | `tests/vst/test_s2_runner_lifecycle.py::test_failed_start_side_effect_blocks_restart_until_verified_reconciliation` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.control_events` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` | MAPPED `api` |
| `store.py` | `Store.verify_event_chain` | `tests/vst/test_e3_store.py::test_reopen_of_a_version_three_database_keeps_data` | MAPPED `api` |
| `store.py` | `Store.event_anchor` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_consume_preflight_is_one_time_and_records_probe` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.reconciliation_complete` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_startup_reconcile_verifies_current_store_history` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.startup_reconcile` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_startup_reconcile_verifies_current_store_history` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.execute_idempotent` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_lookup_idempotent_operation_returns_bound_completed_result` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.lookup_idempotent_operation` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_lookup_idempotent_operation_returns_bound_completed_result` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.charge_idempotent` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_charge_idempotent_replay_updates_budget_once` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.stop_attempt_fenced` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_stop_attempt_fenced_advances_epoch_and_fences_live_lease` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.execute_external_idempotent` | `tests/vst/test_s2_operation_recovery.py::test_external_operation_intent_and_completion_are_committed_around_callback` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.append_receipt_idempotent` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_append_receipt_idempotent_replays_one_receipt` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.consume_preflight` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_consume_preflight_is_one_time_and_records_probe` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.set_budget` | `tests/vst/test_e3_store.py::test_mark_budget_exceeded_writes_signed_blocked_receipt_and_event` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.charge` | `tests/vst/test_e3_store.py::test_no_dangling_transaction_after_success_and_after_error` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.supervisor_reap_and_mark` | `tests/vst/test_e3_store.py::test_lost_attempt_must_be_marked_before_retry` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.mark_budget_exceeded` | `tests/vst/test_e3_store.py::test_mark_budget_exceeded_writes_signed_blocked_receipt_and_event` | EXISTS, NOT YET IN API CATEGORY |
| `store.py` | `Store.render_state_md` | `tests/vst/test_e3_store.py::test_render_state_md_shows_the_phase` | EXISTS, NOT YET IN API CATEGORY |
| `runner.py` | `file_sha256` | `tests/vst/test_e4_runner.py::test_file_sha256_known_vectors` | EXISTS, NOT YET IN API CATEGORY |
| `runner.py` | `artifact_digests` | `tests/vst/test_e4_runner.py::test_artifact_digests_maps_each_path` | EXISTS, NOT YET IN API CATEGORY |
| `runner.py` | `receipt_without_signature` | `tests/vst/test_e4_runner.py::test_signature_is_scoped_to_the_receipt_label` | EXISTS, NOT YET IN API CATEGORY |
| `runner.py` | `build_environment` | `tests/vst/test_e4_runner.py::test_build_environment_unit` | EXISTS, NOT YET IN API CATEGORY |
| `runner.py` | `contained_artifact_path` | `tests/vst/test_e4_runner.py::test_artifact_through_a_symlink_or_junction_to_outside_is_refused` | EXISTS, NOT YET IN API CATEGORY |
| `runner.py` | `run_and_sign` | `tests/vst/test_e4_runner.py::test_receipt_is_bound_to_the_manifest_not_to_caller_supplied_ids` | EXISTS, NOT YET IN API CATEGORY |
| `runner.py` | `run_manifest_commands` | `tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `Supervisor` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` | MAPPED `api` |
| `supervisor.py` | `Supervisor.reconcile_action` | `tests/vst/test_s2_runner_lifecycle.py::test_failed_start_side_effect_blocks_restart_until_verified_reconciliation` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `Supervisor.start_worker` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` | MAPPED `api` |
| `supervisor.py` | `Supervisor.prepare_run` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_prepare_run_binds_fresh_run_and_probe_nonce` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `Supervisor.evaluate_gate` | `tests/vst/test_s2_store_lifecycle.py::test_gate_and_anchor_readers_racing_writer_do_not_permanently_lock_store` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `Supervisor.provider_succeeded` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` | MAPPED `api` |
| `supervisor.py` | `Supervisor.provider_failed` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` | MAPPED `api` |
| `supervisor.py` | `Supervisor.manual_override` | `tests/vst/test_s2_operation_recovery.py::test_completed_override_action_id_with_changed_valid_signed_record_rejected_after_restart` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `Supervisor.stop` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_supervisor_resume_runs_only_from_stopped_lifecycle` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `Supervisor.rollback` | `tests/vst/test_s2_runner_lifecycle.py::test_restart_resumes_the_correct_cleanup_phase_after_reconciliation` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `Supervisor.resume` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_supervisor_resume_runs_only_from_stopped_lifecycle` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `Supervisor.simulate_push` | `tests/vst/test_s2_operation_recovery.py::test_external_operation_timeout_stays_pending_and_same_key_payload_recovers` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `Supervisor.simulate_pull_request` | `tests/vst/test_s2_runner_lifecycle.py::test_idempotent_push_and_pull_request_use_local_bare_remote` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `Supervisor.create_receipt` | `tests/vst/test_s2_store_lifecycle.py::test_store_and_supervisor_refuse_lease_start_or_decision_before_reconciliation` | EXISTS, NOT YET IN API CATEGORY |
| `supervisor.py` | `STOP_TRANSITIONS` | `tests/vst/test_s2_runner_lifecycle.py::test_lifecycle_transition_table_rejects_unlisted_pairs` | EXISTS, NOT YET IN API CATEGORY |

Inventory count: **79** names. Exact-name references after adding the focused API falsifiers: **79/79**.

## Mapping gaps

Every source-defined callable must have a unique API-category selector for the API denominator to be `COMPLETE`. The candidate rows still marked as belonging to another primary category, or “EXISTS, NOT YET IN API CATEGORY,” need a distinct API selector if their existing selector is already assigned elsewhere. The focused S4 API test file adds one selector per previously unmapped/cross-category entrypoint (13 total). The category manifest still needs to include those IDs and the existing unassigned candidates before the denominator can be called complete.

Exact names with no candidate test reference:

- None after the 13 focused API tests were added.

Source evidence: `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` §S4.3.2 and AC-2/AC-8; the five listed `tools/vst` source modules; candidate tests per row.
