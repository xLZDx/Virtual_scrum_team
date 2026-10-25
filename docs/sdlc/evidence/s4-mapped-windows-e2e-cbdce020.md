# S4 mapped Windows E2E at exact HEAD cbdce020

## Scope and provenance

- Branch: `s4-native-qa-runner`.
- Repository HEAD before and after the run: `cbdce020fbd8030e7518285526831c2932f879a2`.
- Worktree status was empty before and after the run.
- Test owner/executor: `e2e-runner` (GPT-6 Luna, medium effort); accountable task owner: operator under delegated S4 work.
- This is a Windows-host run. It does not update the older WSL evidence or prove POSIX behavior.

## Command and result

The seven registered selectors were run with the pinned Windows interpreter and repository pytest pass plugin:

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

- Result: **7 passed, 0 failed, 0 skipped** in 66.94 seconds.
- One existing `pytest-asyncio` deprecation warning reported that `asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16.
- Exact full HEAD remained `cbdce020fbd8030e7518285526831c2932f879a2`; worktree remained clean.

## Acceptance mapping and limits

| Criterion | State | Evidence / remaining work |
|---|---|---|
| Seven mapped selectors on Windows at current exact HEAD | PASS | 7 passed, 0 failed, 0 skipped at `cbdce020`; exact command and before/after status above. |
| Seven mapped selectors on identified WSL snapshot | NOT_RUN | No WSL command was run in this task. The earlier transfer result remains `RESULT_NOT_CAPTURED`; no retry or destination inspection occurred. |
| POSIX symlink path regression | NOT_RUN | Windows run does not exercise POSIX symlink creation/handling. |
| Signer socket, report-bound runner, receipt and authoritative gate | NOT_RUN | Not invoked by these selectors. |

The focused registry functional rerun is separate evidence: 15 passed, 1 Windows symlink-privilege skip, 0 failed at `56a58a7` (change 0149). The current seven-selector E2E result does not replace or widen that module's coverage.

## Ownership and next step

The operator is accountable for the delegated S4 task; Codex is the executor. The repository does not establish a technical service owner for the private WSL runner. Keep WSL/POSIX, signer, report and gate criteria open; do not infer them from this Windows run.
