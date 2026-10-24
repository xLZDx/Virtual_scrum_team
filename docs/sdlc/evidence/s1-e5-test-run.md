# S1 E5 vertical-slice test run

- Head: c7867550669a340588d1016ccdbf238ce9124221 (branch s1-control-plane-core; `git rev-parse HEAD`)
- Python: 3.14.3 (`C:\Python314\python.exe`), pytest, run from repo root `D:\Repo\Virtual_scrum_team`
- Scope: Python API of tools/vst (store, gate, signing, contracts, slice). No browser or UI. No source under tools/vst was edited.

## Commands

1. `C:\Python314\python.exe -m pytest tests/vst/test_e5_slice.py -q -p no:cacheprovider -W ignore` -> 13 passed
2. `C:\Python314\python.exe -m pytest tests/vst/test_e5_process_death.py -q -p no:cacheprovider -W ignore` -> 5 passed
3. `C:\Python314\python.exe -m pytest tests/vst/test_e5_slice.py tests/vst/test_e5_process_death.py -q -p no:cacheprovider -W ignore -rA` -> 18 passed in 11.88s

Note: the first run of file 1 had 1 failure (test over-specification: zombie heartbeat expected kind 'epoch', actual 'lease' because acquire_epoch fences the old lease first; zombie is still rejected; the assertion was corrected to accept 'lease' or 'epoch' and additionally assert the lease is fenced, released=2). Not a product defect. The recorded final runs are the ones above.

## Counts (final whole-set run)

| File | Collected | Passed | Failed | Skipped | Xfailed |
|---|---|---|---|---|---|
| tests/vst/test_e5_slice.py | 13 | 13 | 0 | 0 | 0 |
| tests/vst/test_e5_process_death.py | 5 | 5 | 0 | 0 | 0 |
| Total | 18 | 18 | 0 | 0 | 0 |

## Expected vs executed test ids (all executed, all PASSED)

test_e5_slice.py: SliceScenarioTests::{test_scenario_names_are_exactly_the_ten_expected, test_happy_path_approves, test_worker_death_before_receipt_is_not_approved_and_attempt_retained, test_zombie_late_write_rejected_with_epoch_error, test_stale_head_is_not_approved, test_retry_after_fail_approves_and_keeps_earlier_failure, test_forged_receipt_is_not_approved, test_partial_static_coverage_is_not_approved, test_missing_required_receipt_is_not_approved, test_not_run_with_waiver_matrix, test_budget_exceeded_blocks}; SliceCliTests::{test_cli_exits_zero_and_prints_deterministic_sorted_json, test_cli_without_directory_exits_two}

test_e5_process_death.py: ProcessDeathTests::{test_dead_worker_state_survives_in_the_file, test_reap_expired_frees_the_slot_of_the_dead_worker, test_supervisor_marks_worker_lost_and_gate_refuses, test_dead_workers_old_epoch_cannot_write_after_new_owner}; ConcurrentEpochTests::test_two_store_instances_exactly_one_wins_each_round (25 barrier-synchronised rounds, two Store instances in two threads)

## Not run / not covered

- NOT_RUN: nothing mandatory.
- Not covered: runner.py is not used by the slice (receipts are built directly), so no real command execution; multi-process (not thread) epoch contention; the second real-clock path (default time.time) of Store.
- Gate verdict observed for worker death: the synthetic manifest has no Documentation slot, so the supervisor receipt lands in the first slot (`tests`) with type Documentation and the gate reports a type mismatch (non-approval, as documented in store.py supervisor_reap_and_mark).
- Mutation checks were not run (forbidden by operator decision).
