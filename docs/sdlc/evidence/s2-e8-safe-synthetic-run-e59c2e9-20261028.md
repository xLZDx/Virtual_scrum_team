# S2 safe synthetic helper run — 2026-10-28

## Result and acceptance boundary

At exact repository HEAD `e59c2e9c69f999bbf17e71e4472abf8298e34a07`, the one focused test file
passed: **5 passed, 0 failed, 0 skipped**, with one pytest-asyncio deprecation warning. This proves
only the safe synthetic report/candidate/budget contract in this test file. It does not establish
S2 E8 acceptance, real E5/E6/S1 qualification, sandbox isolation, blocked egress, process/crash
containment, STOP, resume/restart, out-of-scope mutation, external-candidate comparison, or operator
choice.

The previous exact run at `05a443c76b6453c48a103aa136576ba487c80b44` is retained separately in
`docs/sdlc/evidence/s2-e8-safe-synthetic-run-05a443c-20261028.md`. That successful run is superseded
for current exact-source evidence by change 0498, which added a fail-closed work-directory guard and
made the test's temporary parent/new child layout explicit. The prior result remains historical.

Earlier setup failures at heads `83ffe604bcba9293407741510f14420fed580b68`,
`99368ebbb2110706f108a75bfeae224b96026d92`, and `43c5d3d327f529674ca96a93669e5116147e1219` are
recorded with their exact limits in the 05a evidence file; each stopped before a test body ran.

## Exact run

- Command: `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`
- HEAD before and after: `e59c2e9c69f999bbf17e71e4472abf8298e34a07`
- Python: CPython 3.14.3
- pytest: 8.4.2
- Source SHA-256, `tools/vst/slice.py`:
  `91D1EC3ABF3A880B4AC71BBDA8DCBD5ECDE1846CDFBADA4206F50C6DA41FE328`
- Test SHA-256, `tests/vst/test_s2_e8_synthetic_lifecycle.py`:
  `A63687B75D58348C2BAD50D96FB864E978A34544DD42E7B5F8EBDA2EC709CDC5`
- Collected and executed selectors (5):
  - `test_report_explicitly_does_not_claim_real_e8_acceptance`
  - `test_restricted_process_stop_resume_and_mutation_scenarios_remain_unrun`
  - `test_report_marks_budget_overflow_as_rejected`
  - `test_bounded_synthetic_candidate_report_has_no_worker_remote`
  - `test_caller_probe_values_are_not_upgraded_to_environment_egress_evidence`
- Output summary: `5 passed, 1 warning in 17.30s`; process exit code 0.
- Warning: pytest-asyncio deprecated `asyncio.get_event_loop_policy`; it did not fail the run.

## Fixture safety and restricted scenarios

The test creates `temp_root` with `tempfile.TemporaryDirectory`, passes a new `work` child beneath
that root to `run_lifecycle_scenarios`, and the helper creates the child with `os.mkdir`, which
refuses an existing target. The fixture context manager removes the whole parent tree at teardown,
including if helper setup raises. The run used only this disposable repository/SQLite/bare-Git
fixture.

The test and helper leave child self-exit, process kill, STOP, resume/restart, out-of-scope write,
and external-egress scenarios uninvoked and assert their statuses are `NOT_RUN`. No real sandbox,
service, credential, E5, candidate-comparison, or production integration activity occurred.

## Worktree

Before and after the run, the only worktree status entry was the protected pre-existing untracked
`docs/sdlc/evidence/s2-functional-test-run.md`. It was not opened, modified, staged, or removed.
No source/test files were changed by the run. Prior temporary roots were not inspected or deleted.
