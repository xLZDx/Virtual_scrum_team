# S2 safe synthetic helper run — 2026-10-28

## Result and scope

At exact repository HEAD `0c7c31dc19181b80b6629d6ba0b13b1112eaf6a4`, the focused file passed:
**6 passed, 0 failed, 0 skipped**, with one pytest-asyncio deprecation warning. The suite checks
safe synthetic report/candidate/budget behavior and Store cleanup when Supervisor construction
fails. It does not establish S2 E8 acceptance, real E5/E6/S1 qualification, sandbox isolation,
blocked egress, process/crash containment, STOP, resume/restart, out-of-scope mutation,
external-candidate comparison, or operator choice.

The previous six-test pass at
`d70bbe2de787e0a209ba8d1f78072eb70dda32a9` is recorded separately in
`docs/sdlc/evidence/s2-e8-safe-synthetic-run-d70bbe2-20261028.md`. It is historical and superseded
for current exact-source evidence by the budget error-kind fix, which requires the helper to report
lease rejection only for a `StoreError` whose kind is `budget`.

## Exact run

- Command: `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`
- HEAD before and after: `0c7c31dc19181b80b6629d6ba0b13b1112eaf6a4`
- Python: CPython 3.14.3
- pytest: 8.4.2
- Source SHA-256, `tools/vst/slice.py`:
  `8E81E0ECBBD301FABEFCBDA3299D4F8B1415AA86C9B0A90795428DAFCFF3EB2F`
- Test SHA-256, `tests/vst/test_s2_e8_synthetic_lifecycle.py`:
  `C9878A7152A4B5CF3A4D0F59452C19705086204BF9874C8CA172B013D58DC732`
- Collected and executed selectors (6):
  - `test_report_explicitly_does_not_claim_real_e8_acceptance`
  - `test_restricted_process_stop_resume_and_mutation_scenarios_remain_unrun`
  - `test_report_marks_budget_overflow_as_rejected`
  - `test_bounded_synthetic_candidate_report_has_no_worker_remote`
  - `test_caller_probe_values_are_not_upgraded_to_environment_egress_evidence`
  - `test_store_is_closed_when_supervisor_setup_fails`
- Output summary: `6 passed, 1 warning in 18.40s`; process exit code 0.
- Warning: pytest-asyncio deprecated `asyncio.get_event_loop_policy`; it did not fail the run.

## Fixture cleanup and restricted scenarios

The module-scoped safe-flow fixture creates a `TemporaryDirectory` parent and a new `work` child.
The Store-cleanup regression uses a separate `TemporaryDirectory` parent and child. The helper
creates each child with `os.mkdir`, which refuses a pre-existing target. Both context managers
exited through normal pytest teardown, invoking cleanup for their synthetic roots. No prior pytest
temporary path was inspected or deleted.

The suite asserts child self-exit, process kill, STOP, resume/restart, out-of-scope write, and
external-egress scenarios remain `NOT_RUN`; none were invoked. The injected exception is raised by a
monkeypatched `Supervisor` constructor before worker start. That test verifies the helper closes
its SQLite Store connection on setup failure.

## Worktree

Before and after the run, the only status entry was the protected pre-existing untracked
`docs/sdlc/evidence/s2-functional-test-run.md`. It was not opened, modified, staged, or removed.
The test command did not change source or test files. No other tests, system probes, service
actions, credential provisioning, or E5 attestation were part of this run.
