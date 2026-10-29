# S2 safe functional evidence — exact source/test HEAD 4c1692d

Date: 2026-10-27
Repository: `D:\Repo\Virtual_scrum_team`
Branch: `s4-canonical-continuation`
Exact source/test HEAD for every execution below: `4c1692d61ee04e945fc0ccdd44db71869ccd5468`
Test author/executor: designated `functional-test-reviewer`, model `gpt-6-luna`, medium effort.
Environment: Windows, Python 3.14.3, pytest 8.4.2.
Collection inventory: 209 test IDs across the six S2 modules listed below. No test bodies ran during collection.

## Result

Across the Windows functional selections below, 178 selected tests passed. The designated E2E role then ran 8 additional POSIX E3 temporary-fixture IDs, the collected VST-011 capability-drop ID and two POSIX identity-boundary IDs in WSL; all passed. Thus 189 of 209 collected IDs passed and 20 remain `NOT_RUN`. A further E4.1 runtime selector outside these six modules passed separately. There were no test failures or skipped selected tests. Every child execution exited 0. The common Windows `pytest_asyncio` deprecation warning reported use of `asyncio.get_event_loop_policy`; no source/test changes were made by the executions. The parent-session 13-selector lifecycle run is included once in the 178 Windows results and is disjoint from the 12 child runs.

Provenance note: the 178 Windows selections and the original E4.1/VST-011 WSL results were already available in the active task record at turn start; this evidence update reconciles them without claiming the coordinator reran them. The 8 E3 anchor selectors and 2 identity-boundary selectors were newly executed by the designated `e2e-runner` during this continuation.

The protected pre-existing untracked file `docs/sdlc/evidence/s2-functional-test-run.md` was not edited or staged.

## Collection command

```text
python -m pytest --collect-only -q tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py tests/vst/test_s2_operation_recovery.py tests/vst/test_s2_sandbox_probe.py tests/vst/test_s2_store_lifecycle.py tests/vst/test_s2_runner_lifecycle.py
```

Result: 209 IDs collected in 0.81 seconds. This is an inventory, not a test pass.

## Executed functional commands

All commands ran at the exact HEAD above. Counts and durations are included in each heading.

### E1/E2 and S2 D1/D2 contracts — 43 passed, 1.05 seconds

```text
python -m pytest -q tests/vst/test_s2_contract_gate.py::test_v2_manifest_rejects_missing_or_untrusted_mandatory_parser_pin tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping tests/vst/test_s2_contract_gate.py::test_v2_contract_accepts_each_receipt_type_with_its_required_fields tests/vst/test_s2_contract_gate.py::test_v2_trust_root_keys_are_pairwise_distinct tests/vst/test_s2_contract_gate.py::test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review tests/vst/test_s2_contract_gate.py::test_v2_waiver_scope_never_includes_failure_or_review_rejection tests/vst/test_s2_contract_gate.py::test_v2_waiver_allows_only_named_non_execution_results tests/vst/test_s2_contract_gate.py::test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence
```

### E6 diff gate — 22 passed, 14.22 seconds

```text
python -m pytest -q tests/vst/test_s2_diffgate.py::test_runner_untracked_out_of_scope_file_is_in_signed_fail_evidence tests/vst/test_s2_diffgate.py::test_runner_untracked_blocked_file_is_in_signed_fail_evidence tests/vst/test_s2_diffgate.py::test_runner_allowed_untracked_file_content_is_bound_to_signed_digest tests/vst/test_s2_diffgate.py::test_runner_includes_ignored_and_ordinary_untracked_files_in_scope_evidence tests/vst/test_s2_diffgate.py::test_runner_ignored_untracked_file_still_counts_against_manifest_scope tests/vst/test_s2_diffgate.py::test_allowed_change_passes_with_stable_digest_and_normalized_order tests/vst/test_s2_diffgate.py::test_blocked_file_classes_fail_when_manifest_does_not_list_them tests/vst/test_s2_diffgate.py::test_explicitly_scoped_blocked_class_is_permitted_by_manifest tests/vst/test_s2_diffgate.py::test_escaping_or_ambiguous_paths_are_rejected tests/vst/test_s2_diffgate.py::test_path_outside_manifest_scope_fails tests/vst/test_s2_diffgate.py::test_rename_from_allowed_file_into_blocked_hook_fails tests/vst/test_s2_diffgate.py::test_symlink_change_fails_even_when_target_path_is_allowed tests/vst/test_s2_diffgate.py::test_diff_evidence_is_bound_to_manifest_and_candidate_head
```

### E7 external-operation intent, timeout, and idempotency — 4 passed, 0.39 seconds

```text
python -m pytest -q tests/vst/test_s2_operation_recovery.py::test_completed_override_action_id_with_changed_valid_signed_record_rejected_after_restart tests/vst/test_s2_operation_recovery.py::test_external_operation_intent_and_completion_are_committed_around_callback tests/vst/test_s2_operation_recovery.py::test_external_operation_timeout_stays_pending_and_same_key_payload_recovers tests/vst/test_s2_operation_recovery.py::test_completed_legacy_idempotent_operation_remains_replayable
```

### E5/E6 synthetic probe and attestation — 14 passed, 1.15 seconds

```text
python -m pytest -q tests/vst/test_s2_sandbox_probe.py::test_six_sandbox_trust_roots_are_pairwise_distinct tests/vst/test_s2_sandbox_probe.py::test_probe_and_operator_attestation_bind_run_spec_nonce_and_every_check tests/vst/test_s2_sandbox_probe.py::test_sign_inventory_rejects_incomplete_or_extra_contract_fields tests/vst/test_s2_sandbox_probe.py::test_supervisor_accepts_a_valid_synthetic_operator_attestation tests/vst/test_s2_sandbox_probe.py::test_supervisor_refuses_untrusted_operator_attestation_before_worker_start tests/vst/test_s2_sandbox_probe.py::test_collect_inventory_cannot_claim_empty_allowlist_without_operator_attestation tests/vst/test_s2_sandbox_probe.py::test_collect_inventory_fails_closed_when_socket_enumeration_is_incomplete tests/vst/test_s2_sandbox_probe.py::test_mount_classification_only_rejects_windows_drive_mounts tests/vst/test_s2_sandbox_probe.py::test_socket_inventory_discovers_runtime_socket_under_non_1000_uid
```

These are synthetic contract tests; they do not prove a real sandbox inventory, persistent deployment, or host-egress boundary.

### E3/E7 safe store, reconciliation, and concurrency — 10 passed, 0.73 seconds

```text
python -m pytest -q tests/vst/test_s2_store_lifecycle.py::test_sandbox_mode_requires_anchor_and_supervisor_reconciliation_key tests/vst/test_s2_store_lifecycle.py::test_coordinator_oserror_is_normalized_and_store_connection_is_closed tests/vst/test_s2_store_lifecycle.py::test_coordinator_unlock_oserror_is_typed_and_releases_path_mutex tests/vst/test_s2_store_lifecycle.py::test_two_store_instances_serialize_concurrent_write_and_anchor_sync tests/vst/test_s2_store_lifecycle.py::test_gate_and_anchor_readers_racing_writer_do_not_permanently_lock_store tests/vst/test_s2_store_lifecycle.py::test_store_and_supervisor_refuse_lease_start_or_decision_before_reconciliation tests/vst/test_s2_store_lifecycle.py::test_record_event_rejects_caller_forged_reserved_control_note tests/vst/test_s2_store_lifecycle.py::test_supervisor_consumes_a_synthetic_probe_once_for_one_run tests/vst/test_s2_store_lifecycle.py::test_supervisor_receipt_replay_is_idempotent_and_payload_conflict_fails
```

### E7 lifecycle table, breaker, and reconciliation — 8 passed, 1.55 seconds

```text
python -m pytest -q -x tests/vst/test_s2_runner_lifecycle.py::test_lifecycle_transition_table_rejects_unlisted_pairs tests/vst/test_s2_runner_lifecycle.py::test_breaker_requires_operator_signed_override_bound_to_active_episode tests/vst/test_s2_runner_lifecycle.py::test_manual_override_replay_is_stale_after_a_later_breaker_episode tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it tests/vst/test_s2_runner_lifecycle.py::test_stale_second_supervisor_cannot_start_after_peer_opens_persisted_breaker tests/vst/test_s2_runner_lifecycle.py::test_failed_start_side_effect_blocks_restart_until_verified_reconciliation tests/vst/test_s2_runner_lifecycle.py::test_reconciliation_rejects_unsigned_false_and_accepts_signed_operator_resolution tests/vst/test_s2_runner_lifecycle.py::test_replay_keeps_invalid_legacy_reconciliation_unresolved
```

### E7 supervisor concurrency and synthetic Git — 6 passed, 32.84 seconds

```text
python -m pytest -q -x tests/vst/test_s2_runner_lifecycle.py::test_two_cached_ready_supervisors_allow_only_one_concurrent_start_callback tests/vst/test_s2_runner_lifecycle.py::test_idempotent_push_and_pull_request_use_local_bare_remote tests/vst/test_s2_runner_lifecycle.py::test_external_backend_callback_runs_outside_store_anchor_transaction tests/vst/test_s2_runner_lifecycle.py::test_hook_free_publication_transfers_source_only_commit_without_running_pre_push tests/vst/test_s2_runner_lifecycle.py::test_source_object_alternates_are_rejected_before_pack_or_index_writer tests/vst/test_s2_runner_lifecycle.py::test_synthetic_backend_fast_forward_and_conflicting_branch_and_pr_refs
```

### E2 runner-derived heads, signing protocol, and gate routes — 42 passed, 5.15 seconds

```text
python -m pytest -q -x tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands tests/vst/test_s2_runner_lifecycle.py::test_signing_request_exact_schema_and_replay_protocol_without_os_claim tests/vst/test_s2_runner_lifecycle.py::test_signer_rejects_malformed_signing_evidence tests/vst/test_s2_runner_lifecycle.py::test_gate_routes_each_v2_receipt_to_its_designated_authority
```

### Mocked Windows Job Object control flow — 10 passed, 0.60 seconds

```text
python -m pytest -q -x tests/vst/test_s2_runner_lifecycle.py::test_job_object_attach_setup_failure_retries_close_and_logs_only_if_cleanup_fails tests/vst/test_s2_runner_lifecycle.py::test_strict_windows_launch_stays_fail_closed_after_job_setup_cleanup_failure tests/vst/test_s2_runner_lifecycle.py::test_strict_windows_launch_suspends_assigns_job_then_resumes_before_command tests/vst/test_s2_runner_lifecycle.py::test_strict_windows_launch_failure_cleans_up_without_running_command tests/vst/test_s2_runner_lifecycle.py::test_nonstrict_windows_launch_keeps_unsuspended_compatibility_path
```

These mocked unit cases do not prove nested Job Object behavior on the Windows host.

### E7 bounded Git/source storage preflight — 4 passed, 18.28 seconds

```text
python -m pytest -q -x tests/vst/test_s2_runner_lifecycle.py::test_bounded_source_preflight_rejects_before_pack_or_index_writer tests/vst/test_s2_runner_lifecycle.py::test_poisoned_or_interrupted_target_refuses_before_object_writer tests/vst/test_s2_runner_lifecycle.py::test_cumulative_target_storage_cap_rejects_before_pack_process_starts
```

### E7 timeout and same-key retry after Store reopen — 1 passed, 14.86 seconds

```text
python -m pytest -q -x tests/vst/test_s2_runner_lifecycle.py::test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key
```

The test monkeypatches `Popen` to raise `TimeoutExpired` for `git pack-objects` before creating a child. It exercises the persisted pending result and same-key retry after reopening the synthetic store. No worker process is killed and this is not a crash/resume simulation.

### E7 synthetic cross-process target-lock timeout — 1 passed, 4.16 seconds

```text
python -m pytest -q -x tests/vst/test_s2_runner_lifecycle.py::test_target_storage_lock_times_out_on_another_process_then_releases_normally
```

The helper process releases the synthetic lock and exits normally. This does not test process termination, crash recovery, or a worker kill path.

### E4.1 POSIX admission/deadline focused run — 13 passed, 3.12 seconds

Designated functional reviewer, exact command:

```text
python -m pytest -q tests/vst/test_s2_runner_lifecycle.py -k 'distinct_uid_worker_refuses or distinct_uid_cgroup_gate or distinct_uid_attach_failure or gate_environment_timeout or run_and_sign_stops_after or run_manifest_commands_stops_after or unconfirmed_cgroup_cleanup_latches_later_distinct_uid_launches or concurrent_distinct_uid_launch_waits_for_cleanup_latch_admission or distinct_uid_launch_skips_after_lock_wait_exhausts_command_budget or distinct_uid_launch_preserves_expired_absolute_deadline_at_admission'
```

Result: 98 lifecycle IDs collected, 13 selected and passed, 85 deselected, 0 skipped; exit 0 in 3.12 seconds. This was separate and disjoint from the 12 child runs above. It covers the serialized distinct-UID admission and absolute-deadline correction, not host-level Windows containment.

## Additional exact-head POSIX E3 anchor fixtures — 8 passed, 0.23 seconds

The designated `e2e-runner` executed these eight selectors from an exact archive of the same source/test HEAD. Environment: Ubuntu 24.04 WSL2, kernel `6.6.114.1-microsoft-standard-WSL2`, Python 3.12.3, pytest 7.4.4. Transient unit `s2-e3-4c1692d-r1.service`, invocation ID `f019c088e1a048558f110bb9e1be029c`.

```text
/usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-e3-4c1692d-r1 -p no:cacheprovider tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork tests/vst/test_s2_store_lifecycle.py::test_anchor_append_separates_valid_tail_without_final_newline tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes 'tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[external_anchor_ahead_of_database]' 'tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[external_anchor_missing_for_nonempty_database]' 'tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[forked_checkpoint_suffix]' 'tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[malformed_checkpoint_suffix]' 'tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[tampered_checkpoint_suffix]'
```

Result: 8 passed in 0.23 seconds, unit and outer exit 0. Archive hashes: `tools/vst/lifecycle.py` `db81de532229cca96855be286ae5565acff31e0910be09afbc39885132e47a34`; `tools/vst/store.py` `eaf70a5f095fc77cdf5e27985fe9f659db087045f8c0c79d015f8d953980b3b6`; `tests/vst/test_s2_store_lifecycle.py` `243ae4105e7e752ce0028c9a5a9edf9ec844fd1de1a69a09151a6c6d8ffcf52e`; `tests/vst/e1e4_helpers.py` `c36dbb1e8f22cbb8ec50925fa130d2673e6216451cab661ca7c357fa2cf14347`.

The unit ran as `vst-runner` UID/GID `997:988`, with no effective/permitted/bounding/ambient capabilities; 100% CPU, 2 GiB memory, 64 tasks, 45-second runtime, private network, `AF_UNIX` only, and a 1 GiB temporary `/tmp`. These cases use only temporary database/anchor fixtures. The five corrupted-suffix cases are synthetic invalid-input fixtures, not mutation-testing runs. No real system anchor was changed; crash/interruption tests were not selected.

Unit invocation:

```text
systemd-run --wait --pipe --collect --unit=s2-e3-4c1692d-r1 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/run/vst-s2-e3-4c1692d-r1 --setenv=PYTHONPATH=/run/vst-s2-e3-4c1692d-r1 --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property='TemporaryFileSystem=/tmp:size=1G,mode=1777' --property=PrivateNetwork=yes --property='RestrictAddressFamilies=AF_UNIX' --property=NoNewPrivileges=yes --property='CapabilityBoundingSet=' --property='AmbientCapabilities=' /usr/bin/bash -lc '<id/caps/cgroup; exec pytest command>'
```

## Additional exact-head POSIX identity boundary selectors — 2 passed, 1.28 seconds

The designated `e2e-runner` verified these existing WSL identities without changing accounts: `vst-worker` UID/GID `999:989`, `vst-runner` `997:988`, `vst-signer` `995:987`, `vst-reviewer` `993:985`. Two exact-head selectors passed in Ubuntu 24.04 WSL2, Python 3.12.3 / pytest 7.4.4, bounded transient unit `s2-identity-4c1692d-r1.service`.

```text
/usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-identity-4c1692d-r1 -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture
```

Result: 2 passed in 1.28 seconds, unit and outer exit 0. Archive hashes: `tools/vst/sandbox.py` `b5946426d9749a00c76bfc666a0a6f2edb30e74e9985bf0b796caba08fe3b803`; `tests/vst/test_s2_runner_lifecycle.py` `0d818498cea953ef71254d667e64b5aa3b5f77ba9865f6140fe385fdfa6917b9`; `tests/vst/test_s2_sandbox_probe.py` `66440069c6a267f8fcbae2ba9fad0c2552d74fd801fffcbebd0e0c4a9c1fbd8c`; `tests/vst/e1e4_helpers.py` `c36dbb1e8f22cbb8ec50925fa130d2673e6216451cab661ca7c357fa2cf14347`.

The unit ran as root with `Delegate=no`, 100% CPU, 2 GiB, 64 tasks, 45 seconds, 1 GiB `/tmp`, private network, `AF_UNIX` only, `NoNewPrivileges=yes`, and capability bounding/ambient sets limited to `CAP_CHOWN CAP_SETGID CAP_SETUID` (`0xc1`). One selector used synthetic key bytes and a temporary Unix socket; the other used a temporary read-only worktree/SQLite fixture. Neither accessed real keys or signer IPC, changed system accounts, or altered configuration.

Exact transient unit invocation:

```text
systemd-run --wait --pipe --collect --unit=s2-identity-4c1692d-r1 --slice=vst-run.slice --uid=root --gid=root --working-directory=/run/vst-s2-identity-4c1692d-r1 --setenv=PYTHONPATH=/run/vst-s2-identity-4c1692d-r1 --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property='TemporaryFileSystem=/tmp:size=1G,mode=1777' --property=PrivateNetwork=yes --property=RestrictAddressFamilies=AF_UNIX --property=NoNewPrivileges=yes --property='CapabilityBoundingSet=CAP_CHOWN CAP_SETGID CAP_SETUID' --property='AmbientCapabilities=CAP_CHOWN CAP_SETGID CAP_SETUID' /usr/bin/bash -lc "id; grep -E '^(CapEff|CapPrm|CapBnd|CapAmb|NoNewPrivs):' /proc/self/status; cat /proc/self/cgroup; exec /usr/bin/python3 -m pytest -q -c /dev/null --rootdir='/run/vst-s2-identity-4c1692d-r1' -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture"
```

## Collected IDs left `NOT_RUN`

These 20 collected IDs were not executed:

- **E5/E6/E8 probe and environment selectors (7):** `test_real_sandbox_inventory_has_all_required_properties`; `test_e8_sandbox_bakeoff_scenarios_not_run[worker_crash_mid_edit]`; `[STOP_injection_and_cleanup]`; `[budget_exhaustion]`; `[resume_with_fresh_epoch_and_receipt]`; `[unauthorized_write_outside_scope]`; `[blocked_egress_attempt]`.
- **E3 interrupted-anchor recovery (2):** `test_exactly_one_event_ahead_is_recovered_before_mutation`; `test_multi_event_transaction_recovers_suffix_after_one_checkpoint_append`.
- **E2/E4/E7 runner platform/process/restart selectors (11):** `test_restart_resumes_the_correct_cleanup_phase_after_reconciliation[stop]`; `[rollback]`; `test_bounded_git_reader_start_failure_kills_reaps_and_closes`; `test_bounded_git_thread_constructor_failure_kills_reaps_and_fails_closed`; `test_bounded_git_reader_failure_kills_reaps_and_fails_closed`; `test_posix_launch_keeps_session_based_compatibility_path`; `test_distinct_uid_cgroup_cleanup_failure_is_non_approving`; `test_e4_platform_containment_scenarios_not_run[posix_process_group_cleanup]`; `[post_exit_descendant_cleanup]`; `[key_file_permissions_for_worker_identity]`; `[windows_parent_job_nesting]`.

Reasons: prohibited process/kill/cleanup, crash/resume or mutation scenarios, and unavailable real platform-boundary acceptance. Mocked Windows Job Object tests above are unit evidence only. The designated WSL E4.1 and VST-011 runtime results are recorded separately and do not turn the other collected platform selectors into passes.

## Acceptance limits

These focused results do not close S2. A fresh signed sandbox inventory and full egress evidence, persistent deployment/restart fencing, Windows ACL behavior and nested Job Object runtime, E8 crash/resume, and the listed prohibited scenarios remain unproven or `NOT_RUN`. POSIX key-file/socket isolation was tested only with synthetic temporary fixtures; no real key material was accessed. Keep S2 open until its outstanding acceptance gates are resolved. Do not start S3 before S2 closes.

## Separately executed POSIX runtime selectors

The designated `e2e-runner` executed only the following two authorized WSL selectors from an exact archive of the same source/test HEAD. These are additional to, not part of, the 178 functional results above.

Archive file hashes:

- `tools/vst/runner.py`: `dc3f71deafc51ce321e37e4a86cb9c10233189b29ddf8e475968ef624044559d`
- `tests/vst/test_e4_runner.py`: `8e2bdf8c7e448544debbffafd339e3a03b55346273b6d8cf25a8d9992c12f8ad`
- `tests/vst/test_s2_runner_lifecycle.py`: `0d818498cea953ef71254d667e64b5aa3b5f77ba9865f6140fe385fdfa6917b9`

### E4.1 delegated cgroup cleanup across UIDs — 1 passed, 4.30 seconds

Environment: Ubuntu 24.04 WSL2, kernel `6.6.114.1-microsoft-standard-WSL2`, Python 3.12.3, pytest 7.4.4. Transient unit: `s2-e4-4c1692d-r1.service`.

```text
/usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-e4-4c1692d-r1 -p no:cacheprovider tests/vst/test_e4_runner.py::test_posix_worker_timeout_kills_descendant_across_uid_boundary
```

Result: 1 passed, unit success, outer exit 0. Unit profile: `Delegate=yes`, 100% CPU quota, 2 GiB memory, 64 tasks, 45-second runtime, private network, `AF_UNIX AF_INET`, `NoNewPrivileges=yes`, capability bounding/ambient sets limited to `CAP_SETUID CAP_SETGID`. Runner UID/GID `997:988`, permitted/effective/bounding mask `0xc0`; worker UID/GID `999:989`, zero permitted/effective capabilities. The child cgroup was `/sys/fs/cgroup/vst.slice/vst-run.slice/s2-e4-4c1692d-r1.service/vst-command-459-8d3492cddc5c461c8469dfe32ee16a20`; `cgroup.kill` existed. `cgroup.events` was sampled as `populated=0` at creation and `populated=1` after attach. The final child `populated=0` sample was not retained before immediate scope removal; assertions for complete capture and stopped heartbeat passed.

The transient unit was invoked with `systemd-run --wait --pipe --collect --unit=s2-e4-4c1692d-r1 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/run/vst-s2-e4-4c1692d-r1 --setenv=PYTHONPATH=/run/vst-s2-e4-4c1692d-r1 --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=Delegate=yes --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property='TemporaryFileSystem=/tmp:size=1G,mode=1777' --property=PrivateNetwork=yes --property='RestrictAddressFamilies=AF_UNIX AF_INET' --property=NoNewPrivileges=yes --property='CapabilityBoundingSet=CAP_SETUID CAP_SETGID' --property='AmbientCapabilities=CAP_SETUID CAP_SETGID' /usr/bin/bash -lc '<prints id/caps/cgroup; exec /usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-e4-4c1692d-r1 -p no:cacheprovider tests/vst/test_e4_runner.py::test_posix_worker_timeout_kills_descendant_across_uid_boundary>'`.

### VST-011 worker capability drop — 1 passed, 0.63 seconds

Same OS/runtime profile and exact archive. Transient unit: `s2-e2-cap-4c1692d-r1.service`.

```text
/usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-e2-cap-4c1692d-r1 -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_drops_uid_change_capabilities_before_worker_command
```

Result: 1 passed, unit success, outer exit 0. Runner UID/GID `997:988`, capability mask `0xc0`, `NoNewPrivileges=1`; the test asserted worker effective/permitted/inheritable/ambient capabilities were zero and that it could not change UID to the signer. Scope: `/sys/fs/cgroup/vst.slice/vst-run.slice/s2-e2-cap-4c1692d-r1.service/vst-command-441-43d91f5f4e7f4cf6b8d4d1130d292158`; `cgroup.kill` existed. The short-lived worker's final cgroup event was not observed separately; only the empty `populated=0` state was sampled.

The VST-011 transient unit used the same systemd properties as E4.1, with unit/root paths changed to `s2-e2-cap-4c1692d-r1` and `/run/vst-s2-e2-cap-4c1692d-r1`.

Neither transient run proves persistent service/restart fencing, full host egress or sandbox acceptance, Windows nested Job Object behavior, or the prohibited process/kill-table, crash/resume, mutation, or policy cases. No operator key/signature was used or fabricated.
