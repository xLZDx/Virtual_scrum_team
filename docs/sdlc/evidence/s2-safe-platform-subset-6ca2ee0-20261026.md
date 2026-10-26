# S2 safe platform evidence at committed HEAD `6ca2ee00ef31ac621e7ff3231ac175646bbd3bb2`

## Scope and provenance

This run was limited to safe S2 contract and external-anchor selectors. It did not modify source or tests, create a worktree, or touch the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`.

- Canonical repository: `D:\Repo\Virtual_scrum_team`
- HEAD before and after execution: `6ca2ee00ef31ac621e7ff3231ac175646bbd3bb2`
- Initial and final status: `?? docs/sdlc/evidence/s2-functional-test-run.md`; `?? docs/sdlc/evidence/s4-specialist-reviews-3885d8a-20261026.md`
- Protected file SHA-256 before execution: `1273679AC992268BB6FAAC4AC002EDCEDE5D884A7470325314D181E67F6B6B08`
- Windows interpreter: `python` (Python 3.14; pytest; pytest-asyncio emitted one deprecation warning)
- POSIX interpreter: Python 3 via existing `Ubuntu-24.04` WSL2, root harness
- No package installation or external network access was performed.

## Windows run

Command:

```text
python -m pytest -q tests/vst/test_s2_contract_gate.py::test_v2_manifest_rejects_missing_or_untrusted_mandatory_parser_pin tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping tests/vst/test_s2_contract_gate.py::test_v2_trust_root_keys_are_pairwise_distinct tests/vst/test_s2_contract_gate.py::test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review tests/vst/test_s2_contract_gate.py::test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence tests/vst/test_s2_diffgate.py::test_allowed_change_passes_with_stable_digest_and_normalized_order
```

Result: **32 passed, 0 failed, 0 skipped**, exit 0, 1.70 seconds; one pytest-asyncio deprecation warning. The parameterized selectors contribute 31 expanded cases plus the standalone diff-gate case. Coverage is reviewer identity/registry, trusted parser manifest pins, pairwise key distinctness, signed diff-gate evidence rejection, and normalized safe diff paths. No runner lifecycle, child-process, kill, timeout-cleanup, crash/resume, or dependency-target case was selected.

## POSIX / WSL2 run

The source snapshot was streamed from committed HEAD using `git archive` into `/tmp/vst-safe-s2-6ca2ee0` in the existing `Ubuntu-24.04` WSL2 distribution. No worktree or per-sprint directory was created. The temporary archive directory was removed by the command after pytest completed.

Command:

```text
git archive --format=tar HEAD | wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc 'set -eu; target=/tmp/vst-safe-s2-6ca2ee0; mkdir -p "$target"; tar -xf - -C "$target"; cd "$target"; python3 -m pytest -q tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed; rc=$?; rm -rf "$target"; exit $rc'
```

Result: **7 passed, 0 failed, 0 skipped**, exit 0, 0.84 seconds. The three selectors expand to seven parameterized cases. They use temporary database and anchor fixtures only; no OS process was created or terminated by the selected cases, and no crash/resume or external resource target was exercised.

## Acceptance matrix

| S2 item | State | Evidence / limitation | Remaining acceptance and owner | Next action |
|---|---|---|---|---|
| E1 reviewer identity and trust roots | Partial runtime evidence | Windows contract selectors passed; local fixtures only | Full S2 acceptance remains broader; Codex to reconcile with the plan evidence | Keep this subset linked to E1; do not infer sandbox identity proof |
| E3 external anchor rollback integrity | Partial POSIX runtime evidence | Three selected selectors, seven cases passed on WSL2 with disposable fixtures | Process interruption and complete lifecycle acceptance remain outside this run; Codex owns any future authorized safe subset | Record the bounded evidence; leave process-death scenarios NOT_RUN |
| E6 deterministic diff gate | Partial Windows contract evidence | Gate evidence rejection and stable normalized path behavior passed | Full diff fixture denominator and read-only reviewer runtime not covered here; Codex owns follow-up inventory | Keep uncovered selectors NOT_RUN |
| E4 process containment / Job Object nesting | NOT_RUN | No child identity, POSIX permission-denial, process-group, descendant cleanup, or Job Object behavior was selected | Operator policy governs process and child-boundary execution; operator owns any scope change | Keep these selectors NOT_RUN |
| E5 real sandbox probe / egress | NOT_RUN | No real inventory or network probe was selected | Requires separately authorized bounded environment action; operator owns authorization | No action in this run |
| E7 lifecycle / recovery | Partial contract evidence | Windows temporary-store and contract cases cover selected transition-table, breaker, reconciliation, receipt-authority and serialization invariants. No timeout-cleanup, child cleanup, process-death, crash or resume selector was run | Codex owns any additional safe selector review; operator owns policy expansion | Keep prohibited runtime effects NOT_RUN; distinguish contract cases from full runtime acceptance |
| E8 isolated worker bake-off | NOT_RUN | No worker execution or crash/resume scenario was selected | Out of this run's authorization; operator owns any scope expansion | No action in this run |

This evidence is a bounded subset and does not establish full S2 acceptance or close Phase 8.

## Continuation: remaining permitted cases and denominator

The committed QA registry `docs/qa/categories.json` contains 86 S2 test IDs across the six `test_s2_*.py` modules. Review of those IDs against the S2 plan and selector bodies found no additional real Windows identity/permission or POSIX credential-boundary selector that complies with the instruction not to create child processes: `test_posix_worker_cannot_read_signer_or_key_file` and `test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture` both create a child and drop its identity. The permitted real POSIX anchor behavior was exercised above (including forked/tampered/missing/ahead suffix states); system concurrency and lifecycle contracts were then run below.

Additional Windows run (Python 3.14 / pytest):

```text
python -m pytest -q tests/vst/test_s2_store_lifecycle.py::test_sandbox_mode_requires_anchor_and_supervisor_reconciliation_key tests/vst/test_s2_store_lifecycle.py::test_coordinator_oserror_is_normalized_and_store_connection_is_closed tests/vst/test_s2_store_lifecycle.py::test_coordinator_unlock_oserror_is_typed_and_releases_path_mutex tests/vst/test_s2_store_lifecycle.py::test_two_store_instances_serialize_concurrent_write_and_anchor_sync tests/vst/test_s2_store_lifecycle.py::test_gate_and_anchor_readers_racing_writer_do_not_permanently_lock_store tests/vst/test_s2_store_lifecycle.py::test_store_and_supervisor_refuse_lease_start_or_decision_before_reconciliation tests/vst/test_s2_store_lifecycle.py::test_record_event_rejects_caller_forged_reserved_control_note tests/vst/test_s2_store_lifecycle.py::test_supervisor_consumes_a_synthetic_probe_once_for_one_run tests/vst/test_s2_store_lifecycle.py::test_supervisor_receipt_replay_is_idempotent_and_payload_conflict_fails
```

Result: **10 passed, 0 failed, 0 skipped**, exit 0, 0.77 seconds; one pytest-asyncio deprecation warning. The two parameterized OSError cases expand the eight named selectors to ten cases. The suite uses temporary SQLite/anchor files and Python threads; the synthetic probe case explicitly does not assert host isolation.

Additional Windows contract run:

```text
python -m pytest -q tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_v2_contract_accepts_each_receipt_type_with_its_required_fields tests/vst/test_s2_contract_gate.py::test_v2_waiver_scope_never_includes_failure_or_review_rejection tests/vst/test_s2_contract_gate.py::test_v2_waiver_allows_only_named_non_execution_results tests/vst/test_s2_diffgate.py::test_diff_evidence_is_bound_to_manifest_and_candidate_head tests/vst/test_s2_diffgate.py::test_escaping_or_ambiguous_paths_are_rejected tests/vst/test_s2_diffgate.py::test_explicitly_scoped_blocked_class_is_permitted_by_manifest tests/vst/test_s2_diffgate.py::test_path_outside_manifest_scope_fails tests/vst/test_s2_diffgate.py::test_rename_from_allowed_file_into_blocked_hook_fails tests/vst/test_s2_diffgate.py::test_symlink_change_fails_even_when_target_path_is_allowed tests/vst/test_s2_runner_lifecycle.py::test_lifecycle_transition_table_rejects_unlisted_pairs tests/vst/test_s2_runner_lifecycle.py::test_breaker_requires_operator_signed_override_bound_to_active_episode tests/vst/test_s2_runner_lifecycle.py::test_manual_override_replay_is_stale_after_a_later_breaker_episode tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it tests/vst/test_s2_runner_lifecycle.py::test_stale_second_supervisor_cannot_start_after_peer_opens_persisted_breaker tests/vst/test_s2_runner_lifecycle.py::test_failed_start_side_effect_blocks_restart_until_verified_reconciliation tests/vst/test_s2_runner_lifecycle.py::test_reconciliation_rejects_unsigned_false_and_accepts_signed_operator_resolution tests/vst/test_s2_runner_lifecycle.py::test_replay_keeps_invalid_legacy_reconciliation_unresolved tests/vst/test_s2_runner_lifecycle.py::test_restart_resumes_the_correct_cleanup_phase_after_reconciliation tests/vst/test_s2_runner_lifecycle.py::test_two_cached_ready_supervisors_allow_only_one_concurrent_start_callback
```

Result: **32 passed, 0 failed, 0 skipped**, exit 0, 1.24 seconds; one pytest-asyncio deprecation warning. These contract/temporary-store selectors do not invoke external network targets, subprocess cleanup, or process death. Across all four safe runs in this continuation (three Windows invocations and one WSL2 invocation): **74 Windows cases + 7 WSL2 cases = 81 passed, 0 failed, 0 skipped**. This does not imply that the 86-ID registry denominator was exhausted.

### Denominator disposition

The permitted denominator is **not exhausted** across all 86 registry IDs. This continuation exhausted the additional safe contract and real temporary-store selectors chosen for the authorized platform/system subset. Remaining IDs include tests which are either duplicates of existing current-turn evidence, synthetic-only tests that do not add platform evidence, or selectors requiring a prohibited effect. The actual platform evidence still has a hard gap for child-identity checks and process containment because the authorization explicitly forbids child creation/termination. Do not describe the complete 86-ID registry denominator as run.

Explicitly excluded S2 selectors and rationale:

- `tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file` and `tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture`: launch a child under a different UID/GID; child-process creation is prohibited.
- `tests/vst/test_s2_runner_lifecycle.py::test_e4_platform_containment_scenarios_not_run[posix_process_group_cleanup]`, `[post_exit_descendant_cleanup]`, `[key_file_permissions_for_worker_identity]`, `[windows_parent_job_nesting]`: process-group/descendant kill, identity child, or Job Object behavior; process containment/kill execution is prohibited. These placeholders are deliberately not evidence.
- `tests/vst/test_s2_runner_lifecycle.py::test_posix_launch_keeps_session_based_compatibility_path`, `::test_strict_windows_launch_suspends_assigns_job_then_resumes_before_command`, `::test_strict_windows_launch_failure_cleans_up_without_running_command[assignment|thread_discovery|resume]`, `::test_strict_windows_launch_stays_fail_closed_after_job_setup_cleanup_failure`, `::test_job_object_attach_setup_failure_retries_close_and_logs_only_if_cleanup_fails[...]`, `::test_nonstrict_windows_launch_keeps_unsuspended_compatibility_path`: test bodies invoke mocked kill/cleanup, Job Object terminate/close, or launch/process handling; explicitly barred even when mocked.
- `tests/vst/test_s2_runner_lifecycle.py::test_target_storage_lock_times_out_on_another_process_then_releases_normally`, `::test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key`, and `tests/vst/test_s2_operation_recovery.py::test_external_operation_timeout_stays_pending_and_same_key_payload_recovers`: inter-process locking or timeout-recovery semantics are expressly excluded by the instruction; no timeout selector was run.
- `tests/vst/test_s2_sandbox_probe.py::test_real_sandbox_inventory_has_all_required_properties` and all `::test_e8_sandbox_bakeoff_scenarios_not_run[...]`: actual egress/network probe, worker execution, STOP, budget exhaustion, resume, or unauthorized-write scenario; external network and crash/resume/process effects are excluded. The placeholders remain NOT_RUN.
- Every ID in `tests/vst/test_e5_process_death.py` and `tests/vst/test_e4_runner.py` was excluded: these are not safe contract-only cases; the process-death tests terminate a child, and runner containment/timeout cases launch and/or kill process trees. No selector in either module ran.
- Runner/source-backend cases in `tests/vst/test_s2_diffgate.py` that call `_init_git_candidate` / `runner._diff_paths`, and `tests/vst/test_s2_runner_lifecycle.py` operation-publication/backend cases, were not selected because their bodies start subprocesses (Git) or perform synthetic publication side effects; this continuation does not claim those integration behaviors.

Final state during this continuation: HEAD remained `6ca2ee00ef31ac621e7ff3231ac175646bbd3bb2`; protected `s2-functional-test-run.md` SHA-256 remained `1273679AC992268BB6FAAC4AC002EDCEDE5D884A7470325314D181E67F6B6B08`. `core/BACKLOG.md` was observed modified during this continuation; origin is not verified and this agent did not edit it. No source/test code was changed.
