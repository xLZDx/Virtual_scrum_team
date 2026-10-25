# S4 current-head mapped E2E evidence at c5289ca

## Scope and provenance

- Source branch: `s4-native-qa-runner`.
- Exact source HEAD before and after the captured local run: `c5289cae2255b51e165ec8e65a322c752be0e99a`.
- Worktree was clean before and after the captured run.
- Test owner/executor: `e2e-runner` (GPT-6 Luna, medium effort); accountable task owner: operator under delegated S4 continuation.
- This evidence separates the Windows-host run from the prior WSL run at `452c8ea`. It does not upgrade the older WSL evidence to the current source HEAD.

## Captured Windows-host run

- Environment: Windows PowerShell, Python 3.14.3, pytest 8.4.2.
- The exact seven selectors from `s4-native-e2e-452c8ea.md` were executed on the current clean source HEAD:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; C:\Python314\python.exe -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin `
  tests/qa/test_s4_qa_e2e.py::test_s4_e5_synthetic_slice_cli_journey_preserves_gate_and_restart_evidence `
  tests/qa/test_s4_qa_e2e.py::test_s4_e6_qa_snapshot_cli_refuses_an_unapproved_distribution `
  tests/vst/test_s3_worker_pilot_e2e.py::test_s3_app_checkpoint_can_resume_same_effect_under_new_store_epoch `
  tests/vst/test_s3_worker_pilot_e2e.py::test_s3_candidate_identity_cannot_be_self_selected `
  tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_commits_only_the_manifest_scoped_synthetic_change `
  tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_rejects_out_of_scope_edit_before_worker_invocation `
  tests/vst/test_s3_worker_pilot_e2e.py::test_s3_stop_fences_interrupted_attempt_idempotently_and_rejects_stale_start
```

- Result: **7 passed, 0 failed, 0 skipped** in 35.06 seconds; one existing `pytest-asyncio` deprecation warning concerning `asyncio.get_event_loop_policy`.
- A first local invocation's nested process session handle was not retained by the coordinator wrapper. Its output could not be recovered; a later process observation established only that it had exited. That invocation is `RESULT_NOT_CAPTURED` and is not counted as evidence. The captured rerun above is the acceptance evidence for these seven selectors on Windows.

## WSL transfer and POSIX status

- A bounded exact-head transfer was invoked using the already provisioned `Ubuntu-24.04` environment and the project-specific private S4 destination. The PowerShell wrapper's nested execution session handle was not retained; no transfer response or run metadata is available to this agent.
- Transfer state: `RESULT_NOT_CAPTURED`; candidate clone identity, bundle digest/size, ownership/modes and read-only worker boundary are **NOT_VERIFIED** for `c5289ca`.
- No destination was inspected, cleaned, deleted or retried because no correlated run metadata was available.
- The seven selectors have not been run in WSL at this source HEAD. The newly added POSIX symlink-component regression is also `NOT_RUN`; the earlier Windows run skipped it because Windows denied symlink creation (WinError 1314).
- The prior successful WSL transfer and native E2E evidence at `452c8ea` remains valid only for that earlier source HEAD (change 0134).

## Acceptance mapping

| Criterion | State at `c5289ca` | Evidence / remaining work |
|---|---|---|
| Seven mapped selectors on Windows | PASS | Captured focused run: 7 passed, 0 failed, 0 skipped. This does not prove POSIX behavior. |
| Seven mapped selectors on identified WSL snapshot | NOT_RUN | Transfer result and run ID were not captured; do not infer snapshot identity from the older `452c8ea` run. |
| Transfer identity, hash, size, owner/group/modes and worker read-only boundary | NOT_VERIFIED | No correlated transfer metadata is available. |
| Registry rejection of symlinked source components | NOT_RUN | Windows cannot create the required symlinks; POSIX/WSL run needs an identified exact-head snapshot. |
| Signer socket, report-bound runner, receipt and authoritative gate | NOT_RUN | Not invoked by these runs; remains separate S4 acceptance work. |

## Next step and ownership

The operator remains accountable for the delegated S4 task; Codex is the executor. The repository does not establish a technical service owner for the private WSL runner. The current transfer record cannot support inspection or retry under the no-metadata rule. Keep POSIX, signer, report and gate criteria open and use only a future separately authorized, correlated run if the governing task permits it.
