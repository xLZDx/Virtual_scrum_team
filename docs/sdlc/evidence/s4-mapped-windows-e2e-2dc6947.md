# S4 mapped Windows E2E evidence

## Scope and provenance

- Story/gate: S4 QA automation mapped E2E selectors (VST-032–037).
- Repository branch: `s4-native-qa-runner`.
- Exact code/test HEAD before and after: `2dc6947e416b61103548285ec279d787c1027d8b`.
- Worktree status was clean before and after execution.
- Test owner/executor: `e2e-runner` (GPT-6 Luna, low effort); accountable task owner: operator under delegated S4 work.
- Environment: Windows, CPython 3.14.3, pytest 8.4.2.
- This run covers Windows mapped selectors only. It does not replace WSL/POSIX evidence.

## Command and result

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin `
  tests/qa/test_s4_qa_e2e.py::test_s4_e5_synthetic_slice_cli_journey_preserves_gate_and_restart_evidence `
  tests/qa/test_s4_qa_e2e.py::test_s4_e6_qa_snapshot_cli_refuses_an_unapproved_distribution `
  tests/vst/test_s3_worker_pilot_e2e.py::test_s3_app_checkpoint_can_resume_same_effect_under_new_store_epoch `
  tests/vst/test_s3_worker_pilot_e2e.py::test_s3_candidate_identity_cannot_be_self_selected `
  tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_commits_only_the_manifest_scoped_synthetic_change `
  tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_rejects_out_of_scope_edit_before_worker_invocation `
  tests/vst/test_s3_worker_pilot_e2e.py::test_s3_stop_fences_interrupted_attempt_idempotently_and_rejects_stale_start
```

Result: exit 0; **7 passed, 0 failed, 0 skipped** in 25.47 seconds. One existing `pytest-asyncio` deprecation warning states that `asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16.

## Acceptance mapping and remaining work

| Criterion | State | Evidence / remaining work |
|---|---|---|
| Seven mapped selectors on Windows at exact HEAD | PASS | The exact command above passed all seven selectors; HEAD and worktree status were unchanged. |
| Current S4 committed-registry functional module | PASS with skip | Separate record 0156: 19 passed, 1 Windows symlink-privilege skip, 0 failed at source HEAD `6903b7bf3e3dd4fc1281412c173fb82db9924d11`. |
| Current WSL transfer and POSIX behavior | NOT_RUN / RESULT_NOT_CAPTURED | The prior transfer result remains uncorrelated; this task did not inspect or retry it. POSIX symlink behavior remains unverified on Windows. |
| Signer socket, report-bound runner, receipt and authoritative gate | NOT_RUN | These paths were not invoked by the seven selectors. |

No full category coverage or complete sandbox acceptance is implied by this Windows run.

## Ownership and next step

The operator is accountable for the delegated S4 task; Codex is the executor. The repository does not establish a technical service owner for the private WSL runner. Continue with the independent WSL/POSIX and signer/report/gate criteria using fresh correlated evidence; retain the prior uncorrelated result as `RESULT_NOT_CAPTURED`.
