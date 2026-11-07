# S2 safe synthetic helper run — 2026-10-28

## Result and scope

At exact repository HEAD `d70bbe2de787e0a209ba8d1f78072eb70dda32a9`, the focused file passed:
**6 passed, 0 failed, 0 skipped**, with one pytest-asyncio deprecation warning. The sixth test
injects a Python exception during `Supervisor` construction and verifies the temporary Store
connection is closed. It does not kill or crash a child process, invoke STOP/resume/restart,
perform out-of-scope mutation, attempt egress, or touch a real system boundary.

This is local functional evidence for safe synthetic report/candidate/budget behavior and Store
resource cleanup only. It does **not** establish S2 E8 acceptance, real E5/E6/S1 qualification,
sandbox isolation, blocked egress, process/crash containment, STOP, resume/restart, out-of-scope
mutation behavior, external-candidate comparison, or operator choice.

The earlier exact run at `e59c2e9c69f999bbf17e71e4472abf8298e34a07` is retained separately in
`docs/sdlc/evidence/s2-e8-safe-synthetic-run-e59c2e9-20261028.md`. That five-test result is
historical and superseded for current exact-source evidence by the Store cleanup regression and
try-boundary fix. The test suite at the current head contains one additional setup-failure case.

## Exact run

- Command: `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`
- HEAD before and after: `d70bbe2de787e0a209ba8d1f78072eb70dda32a9`
- Python: CPython 3.14.3
- pytest: 8.4.2
- Source SHA-256, `tools/vst/slice.py`:
  `48820FB70B94D7A189F0C2A20F0684FE9232435F744A1B578957FC779F617F04`
- Test SHA-256, `tests/vst/test_s2_e8_synthetic_lifecycle.py`:
  `80D69EA3511DC05CE74E759A30D8D2509645C56A71059886150DCDFFE684BA15`
- Collected and executed selectors (6):
  - `test_report_explicitly_does_not_claim_real_e8_acceptance`
  - `test_restricted_process_stop_resume_and_mutation_scenarios_remain_unrun`
  - `test_report_marks_budget_overflow_as_rejected`
  - `test_bounded_synthetic_candidate_report_has_no_worker_remote`
  - `test_caller_probe_values_are_not_upgraded_to_environment_egress_evidence`
  - `test_store_is_closed_when_supervisor_setup_fails`
- Output summary: `6 passed, 1 warning in 20.80s`; process exit code 0.
- Warning: pytest-asyncio deprecated `asyncio.get_event_loop_policy`; it did not fail the run.

## Fixture and cleanup boundary

The module-scoped safe-flow fixture creates a parent with `tempfile.TemporaryDirectory`, then
passes a new `work` child beneath it to the helper. The failure-injection test uses its own
`TemporaryDirectory` parent and new child. The helper's `os.mkdir(workdir)` refuses a pre-existing
child. Both context managers exited normally through pytest teardown, invoking cleanup for their
synthetic roots. No filesystem scan or operation was performed on earlier pytest temporary roots.

The test asserts the restricted child self-exit, process-kill, STOP, resume/restart, out-of-scope
write, and external-egress scenarios remain `NOT_RUN`. The only injected failure is a Python
exception raised by a monkeypatched `Supervisor` constructor before any worker start; the test then
checks that the created Store connection is closed.

## Worktree

Before and after the run, the only status entry was the protected pre-existing untracked
`docs/sdlc/evidence/s2-functional-test-run.md`. It was not opened, modified, staged, or removed. The
test command did not change source or test files. No other tests, real system probes, service
actions, credential provisioning, or E5 attestation were part of this run.
