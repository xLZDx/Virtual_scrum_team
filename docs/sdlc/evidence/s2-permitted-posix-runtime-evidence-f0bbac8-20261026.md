# S2 permitted POSIX runtime evidence at code/test HEAD `f0bbac8`

## Result

Four selected S2 runtime acceptance cases passed in the existing `Ubuntu-24.04`
WSL2 distribution. This evidence covers two identity-boundary cases and two
external-anchor cases only. It is not full E4 containment or general sandbox
acceptance.

## Source and execution identity

- Exact archived code/test commit: `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2`.
- Canonical repository HEAD during execution: `f9ba9ddd857095548d0694ade44f8e6d874abd90`.
- At execution time, `git diff --name-only f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2..HEAD -- tests/vst tools/vst` produced no paths. The working-tree diff for `tests/vst` and `tools/vst` was also empty. The runtime snapshot therefore used the exact source and test files from `f0bbac8`.
- Runtime: WSL2 `Ubuntu-24.04`, effective UID 0 (`root`), Python `3.12.3`, pytest `7.4.4`.
- The distro reported the `vst-worker`, `vst-runner`, `vst-signer`, and `vst-reviewer` accounts; the `vst-worker`, `vst-runner`, and `vst-signer` groups were also present. This identifies the test host setup; it is not a claim that these checks ran as a provisioned production unit.

## Exact commands and results

1. Identity-boundary selectors:

   ```text
   wsl.exe -d Ubuntu-24.04 --cd /tmp/vst-s2-runtime-f0bbac8-20261026 python3 -m pytest -q tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture
   ```

   Result: **2 passed** in `0.73s`, no warnings.

2. External-anchor selectors:

   ```text
   wsl.exe -d Ubuntu-24.04 --cd /tmp/vst-s2-anchor-f0bbac8-20261026 python3 -m pytest -q tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes
   ```

   Result: **2 passed** in `0.42s`, no warnings.

The pytest durations above are the exact durations printed by the respective
test runs.

## Selector-specific limits

- `test_posix_worker_cannot_read_signer_or_key_file` requires the test process
  to run as root, creates synthetic key files and a synthetic Unix socket under
  `/tmp`, and starts a child with the configured worker UID/GID. It checks that
  this child cannot read those fixture keys or connect to the fixture socket.
  It does not establish production signer isolation or broader sandbox
  containment.
- `test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture` also
  requires a root harness and drops its child to the configured reviewer
  identity. The tested worktree and SQLite database are disposable temporary
  fixtures; the test checks denied writes to those fixtures only.
- `test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork` uses
  a temporary anchor file to check signed append idempotency and same-count fork
  rejection.
- `test_external_anchor_detects_restored_older_database_and_locks_writes`
  copies an earlier temporary SQLite database, opens that copy against the
  newer temporary external anchor, and checks that writes remain locked. This
  is not a process-crash or interrupted-transaction test.

## Additional full Store lifecycle run

The complete Store lifecycle module was subsequently run from another temporary
archive of the same code/test commit:

- Canonical repository HEAD during this run: `bc1f015b39ead97f30444fc6fc72a8bc35febd0c`.
- `tests/vst` and `tools/vst` remained unchanged from `f0bbac8`; the diff from
  that code/test commit listed no paths.
- Runtime: the same WSL2 `Ubuntu-24.04` distro as above, UID 0 (`root`), Python
  `3.12.3`, pytest `7.4.4`.
- Temporary archive: `/tmp/vst-s2-store-lifecycle-f0bbac8-20261026`, created
  from `git archive` at the exact code/test commit and removed after the run.

Exact command:

```text
wsl.exe -d Ubuntu-24.04 --cd /tmp/vst-s2-store-lifecycle-f0bbac8-20261026 python3 -m pytest -q tests/vst/test_s2_store_lifecycle.py
```

Result: exit code `0`; **19 passed, 0 skipped** in `1.85s`, no warnings.

This module includes synthetic interruption/recovery cases using temporary
anchor and SQLite files (`test_exactly_one_event_ahead_is_recovered_before_mutation`
and `test_multi_event_transaction_recovers_suffix_after_one_checkpoint_append`).
The first truncates a temporary anchor suffix; the second injects an exception
after a temporary checkpoint append and reopens the temporary store. Neither
case kills or terminates a process, and neither is full E8 process-crash/resume
acceptance. The module inspection found no subprocess, process-kill, kill-table,
or mutation-testing runner.

## Snapshot handling and exclusions

Each run used a temporary source snapshot created with `git archive` from the
exact commit above. The extracted snapshots had no `.git` directory and were
removed after execution; cleanup was checked. No Git checkout, worktree, or
fork directory was created. The tests created their own temporary fixtures and
cleaned them in their normal teardown paths. No source or test file was changed
for these runs, and no package was installed.

The results do **not** establish:

- full E4 POSIX or Windows process containment;
- real egress, sandbox inventory, CPU/memory/storage quota, or resource gates;
- POSIX process-group cleanup or Windows Job Object descendant cleanup;
- real process-crash or process-kill recovery beyond the synthetic temporary
  anchor interruption cases described above.

Policy-excluded process-kill, kill-table, mutation, process-group cleanup, and
full crash/resume cases were not run. Real sandbox inventory and egress probes
were also not run; these results must not be reported as their acceptance.

## Final safe S2 module remainder at code/test HEAD `f0bbac8`

### Inventory and selection method

The S2 plan's acceptance epics E1-E8 were cross-checked against the committed
QA registry (`docs/qa/categories.json`), the six S2-specific module paths it
assigns, test names, skip markers, and the relevant test bodies. The registry
contains 79 S2 test IDs across these six modules (parameterized pytest cases
expand to additional node IDs). The source/test snapshot remained exactly
`f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2`; the canonical repository HEAD
during this remainder run was `bc1f015b39ead97f30444fc6fc72a8bc35febd0c`.
No `tests/vst` or `tools/vst` paths differ between those commits, and their
working-tree diff was empty.

The already-recorded complete `test_s2_diffgate.py` run (22 passed), complete
`test_s2_store_lifecycle.py` run (19 passed), and four prior POSIX runtime
selectors were not repeated. The five previously passed `diff_gate` cases in
`test_s2_contract_gate.py` were deselected from its remaining-module run.
Previously completed runner identity/provenance and Job Object selectors were
also excluded from the runner remainder command.

### Newly executed safe remainder

All commands below ran from temporary `git archive` snapshots of
`f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2` in WSL2 `Ubuntu-24.04`, effective
UID 0 (`root`), Python `3.12.3`, pytest `7.4.4`. The snapshot had no `.git`
directory and was deleted after the run. No Git checkout, worktree, or fork
directory was created. Each command exited `0`; no warnings were emitted.

1. Remaining contract-gate coverage (the five prior `diff_gate` cases are
   deselected):

   ```text
   wsl.exe -d Ubuntu-24.04 --cd /tmp/vst-s2-acceptance-f0bbac8-20261026 python3 -m pytest -q tests/vst/test_s2_contract_gate.py -k "not diff_gate"
   ```

   Result: **38 passed, 5 deselected** in `0.31s`.

2. Store-backed operation-recovery module:

   ```text
   wsl.exe -d Ubuntu-24.04 --cd /tmp/vst-s2-acceptance-f0bbac8-20261026 python3 -m pytest -q tests/vst/test_s2_operation_recovery.py
   ```

   Result: **4 passed** in `0.26s`. The timeout case injects a synthetic
   backend `TimeoutError`; it does not start or terminate an OS process.

3. Synthetic sandbox-probe contracts. The prior reviewer identity selector,
   real inventory, and E8 placeholders were excluded:

   ```text
   wsl.exe -d Ubuntu-24.04 --cd /tmp/vst-s2-acceptance-f0bbac8-20261026 python3 -m pytest -q tests/vst/test_s2_sandbox_probe.py -k "not test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture and not test_real_sandbox_inventory_has_all_required_properties and not test_e8_sandbox_bakeoff_scenarios_not_run"
   ```

   Result: **14 passed, 8 deselected** in `0.27s`.

4. Safe runner-lifecycle remainder. This excludes E4 process containment,
   local-Git timeout recovery, POSIX process-group cleanup, the prior worker
   identity and provenance selectors, the process-cleanup failure cases, and
   previously completed Job Object/launch selectors:

   ```text
   wsl.exe -d Ubuntu-24.04 --cd /tmp/vst-s2-acceptance-f0bbac8-20261026 python3 -m pytest -q tests/vst/test_s2_runner_lifecycle.py -k "not test_e4_platform_containment_scenarios_not_run and not test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key and not test_posix_launch_keeps_session_based_compatibility_path and not test_posix_worker_cannot_read_signer_or_key_file and not test_strict_windows_launch_failure_cleans_up_without_running_command and not test_strict_windows_launch_stays_fail_closed_after_job_setup_cleanup_failure and not test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides and not test_runner_rejects_caller_supplied_head_parser_key_or_commands and not test_job_object_attach_setup_failure_retries_close_and_logs_only_if_cleanup_fails and not test_strict_windows_launch_suspends_assigns_job_then_resumes_before_command and not test_nonstrict_windows_launch_keeps_unsuspended_compatibility_path"
   ```

   Result: **56 passed, 24 deselected** in `5.51s`. The retained signer
   malformed-evidence cases alter disposable request inputs to exercise
   validation; they do not run mutation-testing tooling.

The first attempt at command 4 collected no tests because its temporary archive
directory was no longer present (`chdir(/tmp/vst-s2-acceptance-f0bbac8-20261026)
failed 2`). The archive was recreated from the same exact commit and the command
above then completed successfully. This was an invocation/setup error, not a
test failure; no selector ran in the failed attempt.

### Acceptance coverage matrix and remaining gates

| Plan item | Evidence at this code/test head | State and limit |
|---|---|---|
| E1 / VST-009 — authenticated reviewer authority | Contract-gate remainder (38 pass), prior five diff-gate contract cases, and runner receipt-authority cases in the safe lifecycle remainder | Local contract acceptance passed; this does not prove a production reviewer environment. |
| E2 / VST-010/011 — runner-derived evidence and signing-key isolation | Safe runner lifecycle remainder; prior runner provenance selectors; worker key/socket identity boundary (1 pass) | Local checks passed; child identity result applies only to the configured WSL test identities and synthetic fixture. |
| E3 / VST-012 — external anchor and rollback detection | Full Store lifecycle module (19 pass), including anchor append, stale-copy detection, suffix reconciliation and fail-closed states | Temporary SQLite/anchor fixtures passed; real crash interruption was not performed. |
| E4 / VST-013 — POSIX process containment and Windows Job Object nesting | No real process-group, descendant-kill, kill-table, or nested Job Object runtime selector was run | **NOT_RUN** under the active process-kill restriction; mocked selector outcomes are not platform proof. |
| E5 / VST-014 — sandbox probe | Synthetic probe contract subset (14 pass) | **Partial**: real run-bound inventory, egress, and resource enforcement were not exercised. |
| E6 / VST-015 — diff gate and read-only reviewer | Full DiffGate module (22 pass), plus one POSIX reviewer identity fixture pass | Local path/digest and fixture permission checks passed; this is not full sandbox containment or canonical-path binding. |
| E7 / VST-016..019 — STOP, idempotency, breaker and reconciliation | Safe runner lifecycle remainder (56 pass), operation recovery (4 pass), and Store lifecycle (19 pass) | Local Store/Supervisor state transitions passed; real process cleanup and full crash/resume remain unverified. |
| E8 / VST-020 — isolated worker bake-off | No candidate/sandbox run | **NOT_RUN**: no external candidate was run and no real probe/egress gate was claimed. |

The following selectors were excluded from this exact archive inventory run:

- `test_e4_platform_containment_scenarios_not_run[posix_process_group_cleanup]`
- `test_e4_platform_containment_scenarios_not_run[post_exit_descendant_cleanup]`
- `test_e4_platform_containment_scenarios_not_run[key_file_permissions_for_worker_identity]`
- `test_e4_platform_containment_scenarios_not_run[windows_parent_job_nesting]`
- `test_posix_launch_keeps_session_based_compatibility_path`
- `test_strict_windows_launch_failure_cleans_up_without_running_command[assignment]`
- `test_strict_windows_launch_failure_cleans_up_without_running_command[thread_discovery]`
- `test_strict_windows_launch_failure_cleans_up_without_running_command[resume]`
- `test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key`
  (the QA registry marks this selector `NOT_RUN` under its timeout policy)
- `test_real_sandbox_inventory_has_all_required_properties`
- `test_e8_sandbox_bakeoff_scenarios_not_run[worker_crash_mid_edit]`
- `test_e8_sandbox_bakeoff_scenarios_not_run[STOP_injection_and_cleanup]`
- `test_e8_sandbox_bakeoff_scenarios_not_run[budget_exhaustion]`
- `test_e8_sandbox_bakeoff_scenarios_not_run[resume_with_fresh_epoch_and_receipt]`
- `test_e8_sandbox_bakeoff_scenarios_not_run[unauthorized_write_outside_scope]`
- `test_e8_sandbox_bakeoff_scenarios_not_run[blocked_egress_attempt]`

The already-passed worker identity and reviewer boundary selectors, the four
anchor selectors and complete Store module, prior DiffGate and contract
`diff_gate` cases, and prior runner provenance/Job Object setup selectors were
not repeated. No process-kill, kill-table, mutation-testing, or full E8
crash/resume scenario was executed by this inventory.

### Fresh permitted POSIX subset at repository HEAD `022fd6b` (2026-10-26)

The designated `e2e-runner` ran six individually selected POSIX identity and
external-anchor cases from a temporary archive of the canonical checkout at
`022fd6bc5d68e94edde6d281e7e5bec4030b2908`. The checkout contained only the
pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; no source
or test changes were made. The final HEAD was unchanged, and that untracked file
was preserved with SHA-256
`1273679AC992268BB6FAAC4AC002EDCEDE5D884A7470325314D181E67F6B6B08`.

Environment: selected `Ubuntu-24.04` WSL2, Python 3.12.3, pytest 7.4.4. The
distro was stopped before the run and started by the WSL invocation; it remained
running afterward. `automount.enabled=false` and `interop.enabled=false`. The
real `vst-runner`, `vst-worker`, `vst-signer`, and `vst-reviewer` identities were
present. No helper, package, or compiler was installed.

Exact command:

```text
git archive --format=tar HEAD | wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc 'set -eu; target=/tmp/vst-s2-runtime-022fd6-20261026; mkdir -p "$target"; tar -xf - -C "$target"; test ! -e "$target/.git"; cd "$target"; python3 -m pytest -q tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes tests/vst/test_s2_store_lifecycle.py::test_exactly_one_event_ahead_is_recovered_before_mutation tests/vst/test_s2_store_lifecycle.py::test_multi_event_transaction_recovers_suffix_after_one_checkpoint_append; rc=$?; rm -rf "$target"; exit $rc'
```

Result: **6 passed, 0 failed, 0 skipped**, exit code 0, in 0.63 seconds.
Coverage is limited to fixture-scoped worker key/socket denial, reviewer
write-denial, and temporary external-anchor append/restore/reconciliation. The
recovery cases changed only disposable SQLite/anchor fixtures and injected a
Python exception; no OS process was terminated. The archive snapshot was
removed after the run. No process-kill, kill-table, mutation-testing, Windows
Job Object, real POSIX process-group cleanup, full crash/resume, or real
egress/sandbox-inventory selector was run. This run does not close S2 Phase 8.
