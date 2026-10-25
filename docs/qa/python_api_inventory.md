# S4 Python API callable inventory

Scope: source-defined non-underscore top-level functions/classes and public instance/class methods in the five modules named by S4.3.2. `supervisor.py` also explicitly exports `Supervisor` and `STOP_TRANSITIONS` through `__all__`. The other modules do not define `__all__`; this inventory uses the Python non-underscore convention. Underscore-prefixed helpers and nested implementation classes are excluded. No HTTP route contract is present; `network_api` remains `UNSUPPORTED`.

Each row maps the source-defined name to one API-primary pytest node ID whose test body references that callable. Tests already primary-assigned to functional/integration/E2E were not duplicated; distinct API falsifiers were added for cross-category entrypoints. The test IDs are required by `docs/qa/categories.json` and are executed as one bounded API lane. Some selectors falsify more than one entrypoint; IDs remain unique across primary categories.

| Module | Source-defined public name | API-primary falsifying test ID |
|---|---|---|
| `contracts.py` | `ContractError` | `tests/vst/test_e1_contracts.py::test_canonical_bytes_unserialisable_raises_contract_error` |
| `contracts.py` | `canonical_bytes` | `tests/vst/test_e1_contracts.py::test_canonical_bytes_exact_form` |
| `contracts.py` | `receipt_sha256` | `tests/vst/test_e1_contracts.py::test_receipt_sha256_matches_independent_computation_and_is_stable` |
| `contracts.py` | `manifest_sha256` | `tests/vst/test_e1_contracts.py::test_manifest_sha256_matches_independent_computation_and_is_stable` |
| `contracts.py` | `normalize_principal` | `tests/vst/test_e1_contracts.py::test_normalize_principal` |
| `contracts.py` | `validate_task_manifest` | `tests/vst/test_e1_contracts.py::test_manifest_valid_returns_equal_deep_copy` |
| `contracts.py` | `validate_task_manifest_v2` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_validate_task_manifest_v2_rejects_missing_contract_fields` |
| `contracts.py` | `validate_receipt` | `tests/vst/test_e1_contracts.py::test_receipt_valid_each_type_returns_deep_copy` |
| `contracts.py` | `derive_result` | `tests/vst/test_e1_contracts.py::test_derive_testrun_pass_when_everything_matches` |
| `contracts.py` | `validate_gate_decision` | `tests/vst/test_e1_contracts.py::test_gate_decision_valid_and_deep_copy` |
| `gate.py` | `evaluate` | `tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation` |
| `store.py` | `StoreError` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` |
| `store.py` | `StoreBusyError` | `tests/vst/test_e3_store.py::test_busy_database_raises_store_busy_error_and_writes_nothing` |
| `store.py` | `Store` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` |
| `store.py` | `Store.close` | `tests/vst/test_s2_store_lifecycle.py::test_coordinator_oserror_is_normalized_and_store_connection_is_closed` |
| `store.py` | `Store.init_slots` | `tests/vst/test_e3_store.py::test_expired_lease_is_reaped_on_next_acquire_and_slot_reused` |
| `store.py` | `Store.open_story` | `tests/vst/test_e3_store.py::test_reopen_of_a_version_three_database_keeps_data` |
| `store.py` | `Store.current_epoch` | `tests/vst/test_e3_store.py::test_reopen_of_a_version_three_database_keeps_data` |
| `store.py` | `Store.acquire_epoch` | `tests/vst/test_e3_store.py::test_no_dangling_transaction_after_success_and_after_error` |
| `store.py` | `Store.acquire_epoch_idempotent` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_acquire_epoch_idempotent_replay_keeps_one_new_epoch` |
| `store.py` | `Store.resume_epoch_idempotent` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_resume_epoch_idempotent_rejects_unrecorded_outcome_without_mutation` |
| `store.py` | `Store.renew_epoch` | `tests/vst/test_e3_store.py::test_renew_epoch_extends_liveness_without_changing_epoch` |
| `store.py` | `Store.release_epoch` | `tests/vst/test_e3_store.py::test_acquire_epoch_exhausted_counter_is_refused` |
| `store.py` | `Store.set_phase` | `tests/vst/test_e3_store.py::test_set_phase_by_live_owner_changes_phase_and_records_event` |
| `store.py` | `Store.get_phase` | `tests/vst/test_e3_store.py::test_reopen_of_a_version_three_database_keeps_data` |
| `store.py` | `Store.register_task` | `tests/vst/test_e3_store.py::test_register_task_returns_manifest_hash_and_get_manifest_roundtrips` |
| `store.py` | `Store.get_manifest` | `tests/vst/test_e3_store.py::test_register_task_returns_manifest_hash_and_get_manifest_roundtrips` |
| `store.py` | `Store.acquire_lease` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_stop_attempt_fenced_advances_epoch_and_fences_live_lease` |
| `store.py` | `Store.failed_attempts` | `tests/vst/test_e3_store.py::test_lost_attempts_count_toward_retry_cap_and_the_next_lease_commits_a_signed_marker` |
| `store.py` | `Store.heartbeat` | `tests/vst/test_e3_store.py::test_acquire_after_ttl_fences_live_lease_and_old_epoch_writes` |
| `store.py` | `Store.release_lease` | `tests/vst/test_e3_store.py::test_lease_attempts_are_consecutive_from_one` |
| `store.py` | `Store.reap_expired` | `tests/vst/test_e3_store.py::test_lease_statuses_follow_the_closed_enum` |
| `store.py` | `Store.append_receipt` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_stop_attempt_fenced_advances_epoch_and_fences_live_lease` |
| `store.py` | `Store.append_supervisor_receipt` | `tests/vst/test_e3_store.py::test_supervisor_path_rejects_worker_slot_receipts` |
| `store.py` | `Store.receipts_for_task` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_stop_attempt_fenced_advances_epoch_and_fences_live_lease` |
| `store.py` | `Store.evaluate_gate` | `tests/vst/test_s2_store_lifecycle.py::test_gate_and_anchor_readers_racing_writer_do_not_permanently_lock_store` |
| `store.py` | `Store.record_event` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_startup_reconcile_verifies_current_store_history` |
| `store.py` | `Store.append_manual_override` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_append_manual_override_rejects_unsigned_record_without_control_write` |
| `store.py` | `Store.begin_action` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_begin_action_rejects_mismatched_transaction_id_without_write` |
| `store.py` | `Store.reconcile_action` | `tests/vst/test_s2_runner_lifecycle.py::test_failed_start_side_effect_blocks_restart_until_verified_reconciliation` |
| `store.py` | `Store.control_events` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` |
| `store.py` | `Store.verify_event_chain` | `tests/vst/test_e3_store.py::test_reopen_of_a_version_three_database_keeps_data` |
| `store.py` | `Store.event_anchor` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_consume_preflight_is_one_time_and_records_probe` |
| `store.py` | `Store.reconciliation_complete` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_startup_reconcile_verifies_current_store_history` |
| `store.py` | `Store.startup_reconcile` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_startup_reconcile_verifies_current_store_history` |
| `store.py` | `Store.execute_idempotent` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_lookup_idempotent_operation_returns_bound_completed_result` |
| `store.py` | `Store.lookup_idempotent_operation` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_lookup_idempotent_operation_returns_bound_completed_result` |
| `store.py` | `Store.charge_idempotent` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_charge_idempotent_replay_updates_budget_once` |
| `store.py` | `Store.stop_attempt_fenced` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_stop_attempt_fenced_advances_epoch_and_fences_live_lease` |
| `store.py` | `Store.execute_external_idempotent` | `tests/vst/test_s2_operation_recovery.py::test_external_operation_intent_and_completion_are_committed_around_callback` |
| `store.py` | `Store.append_receipt_idempotent` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_append_receipt_idempotent_replays_one_receipt` |
| `store.py` | `Store.consume_preflight` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_consume_preflight_is_one_time_and_records_probe` |
| `store.py` | `Store.set_budget` | `tests/vst/test_e3_store.py::test_mark_budget_exceeded_writes_signed_blocked_receipt_and_event` |
| `store.py` | `Store.charge` | `tests/vst/test_e3_store.py::test_no_dangling_transaction_after_success_and_after_error` |
| `store.py` | `Store.supervisor_reap_and_mark` | `tests/vst/test_e3_store.py::test_lost_attempt_must_be_marked_before_retry` |
| `store.py` | `Store.mark_budget_exceeded` | `tests/vst/test_e3_store.py::test_mark_budget_exceeded_writes_signed_blocked_receipt_and_event` |
| `store.py` | `Store.render_state_md` | `tests/vst/test_e3_store.py::test_render_state_md_shows_the_phase` |
| `runner.py` | `file_sha256` | `tests/vst/test_e4_runner.py::test_file_sha256_known_vectors` |
| `runner.py` | `artifact_digests` | `tests/vst/test_e4_runner.py::test_artifact_digests_maps_each_path` |
| `runner.py` | `receipt_without_signature` | `tests/vst/test_e4_runner.py::test_signature_is_scoped_to_the_receipt_label` |
| `runner.py` | `build_environment` | `tests/vst/test_e4_runner.py::test_build_environment_unit` |
| `runner.py` | `contained_artifact_path` | `tests/vst/test_e4_runner.py::test_artifact_through_a_symlink_or_junction_to_outside_is_refused` |
| `runner.py` | `run_and_sign` | `tests/vst/test_e4_runner.py::test_receipt_is_bound_to_the_manifest_not_to_caller_supplied_ids` |
| `runner.py` | `run_manifest_commands` | `tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides` |
| `supervisor.py` | `Supervisor` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` |
| `supervisor.py` | `Supervisor.reconcile_action` | `tests/vst/test_s2_runner_lifecycle.py::test_failed_start_side_effect_blocks_restart_until_verified_reconciliation` |
| `supervisor.py` | `Supervisor.start_worker` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` |
| `supervisor.py` | `Supervisor.prepare_run` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_prepare_run_binds_fresh_run_and_probe_nonce` |
| `supervisor.py` | `Supervisor.evaluate_gate` | `tests/vst/test_s2_store_lifecycle.py::test_gate_and_anchor_readers_racing_writer_do_not_permanently_lock_store` |
| `supervisor.py` | `Supervisor.provider_succeeded` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` |
| `supervisor.py` | `Supervisor.provider_failed` | `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it` |
| `supervisor.py` | `Supervisor.manual_override` | `tests/vst/test_s2_operation_recovery.py::test_completed_override_action_id_with_changed_valid_signed_record_rejected_after_restart` |
| `supervisor.py` | `Supervisor.stop` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_supervisor_resume_runs_only_from_stopped_lifecycle` |
| `supervisor.py` | `Supervisor.rollback` | `tests/vst/test_s2_runner_lifecycle.py::test_restart_resumes_the_correct_cleanup_phase_after_reconciliation` |
| `supervisor.py` | `Supervisor.resume` | `tests/vst/test_s4_python_api_entrypoints.py::test_api_supervisor_resume_runs_only_from_stopped_lifecycle` |
| `supervisor.py` | `Supervisor.simulate_push` | `tests/vst/test_s2_operation_recovery.py::test_external_operation_timeout_stays_pending_and_same_key_payload_recovers` |
| `supervisor.py` | `Supervisor.simulate_pull_request` | `tests/vst/test_s2_runner_lifecycle.py::test_idempotent_push_and_pull_request_use_local_bare_remote` |
| `supervisor.py` | `Supervisor.create_receipt` | `tests/vst/test_s2_store_lifecycle.py::test_store_and_supervisor_refuse_lease_start_or_decision_before_reconciliation` |
| `supervisor.py` | `STOP_TRANSITIONS` | `tests/vst/test_s2_runner_lifecycle.py::test_lifecycle_transition_table_rejects_unlisted_pairs` |

Inventory count: **79** entrypoints mapped to **57** distinct API-primary selectors. The full API category has **73** selectors, including the existing QA registry and seeded-catalog contract selectors.

## Scope boundaries

Underscore-prefixed functions/classes are private implementation helpers and are not separate supported callables in this denominator. The absent HTTP surface remains `UNSUPPORTED`. Runtime skips/failures are reported separately from this static denominator: complete mapping does not imply every platform-specific selector ran successfully. Report-bound signing, receipts, and authoritative gate acceptance are separate S4 runtime gates.

Source evidence: `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` §S4.3.2 and AC-2/AC-8; `tools/vst/contracts.py`, `gate.py`, `store.py`, `runner.py`, and `supervisor.py`; each candidate test body listed above.
