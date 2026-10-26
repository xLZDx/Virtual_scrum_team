# S2/S3 focused regression evidence at source HEAD `5ae495c`

Date: 2026-10-26  
Repository: `D:\Repo\Virtual_scrum_team`  
Source HEAD before and after all runs: `5ae495c073a7bfb5d26f209f582c00e7c4c954c7`  
Interpreter: `C:\Python314\python.exe`, Python 3.14.3  
Working tree during runs: `tests/vst/test_e4_runner.py` was modified by the functional test agent; pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved. Test edits were later committed in change 0320. These results are source-HEAD evidence, not yet a committed-test-head rerun.

## S2 Windows Job Object cleanup regression

Owner: `functional-test-reviewer`  
Command:

```powershell
C:\Python314\python.exe -m pytest tests/vst/test_e4_runner.py -k 'job_cleanup_failure_is_never_confirmed_and_fallback_runs or failed_job_handle_close_is_retried or run_receipt_fails_closed_when_job_cleanup_is_unconfirmed' -q
```

Result: exit 0; **12 passed, 290 deselected**, one `pytest-asyncio` deprecation warning. The selected cases mock Win32 API results and assert that false/exception outcomes trigger fallback and produce exit code `-4`, `capture_incomplete=true`, and a signed receipt result of `FAIL`; a failed handle close is retried. No real process-kill scenario was run.

Attempt history: an early test-double run failed because the fake process did not implement `kill`; after correction, the first runner-to-receipt integration run had four assertion failures because cleanup retries in `finally` caused repeated calls. The assertions were corrected and the full selected set passed. Counts and exit codes for the first test-double attempt were not retained; neither failed attempt is acceptance evidence.

## S2 Store lifecycle and operation recovery

Owner: `e2e-runner`  
Command:

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_store_lifecycle.py
```

Result: exit 0; **10 passed, 9 skipped**, one pytest-asyncio deprecation warning. All nine skips are explicit POSIX-only external-anchor permission/locking, restore-detection, interrupted-recovery, or invalid-anchor-suffix cases. They remain `NOT_RUN`; no skip was forced.

Command:

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_operation_recovery.py
```

Result: exit 0; **4 passed, 0 skipped**, one pytest-asyncio deprecation warning. The test agent inspected this Store/Supervisor-only module and found no process-kill, mutation-test, or crash/resume scenario.

## S3 safe regression subset

Owner: `e2e-runner`  
Command:

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_adapter.py -k "not ac4_resume_accepts_only_returned_named_app_checkpoint_and_is_idempotent"
```

Result: exit 0; **8 passed, 1 deselected**, one pytest-asyncio deprecation warning. The deselected case is `test_ac4_resume_accepts_only_returned_named_app_checkpoint_and_is_idempotent`.

Command:

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_commits_only_the_manifest_scoped_synthetic_change tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_rejects_out_of_scope_edit_before_worker_invocation tests/vst/test_s3_worker_pilot_e2e.py::test_s3_candidate_identity_cannot_be_self_selected
```

Result: exit 0; **3 passed**, one pytest-asyncio deprecation warning. The test agent inspected the module and confirmed it does not invoke OS process termination. It deliberately did not run the app-resume case, four `test_s3_stop_*` functions (five cases after parameterization), or sandbox boundary AC-5/AC-6; these remain `NOT_RUN` pending their policy/trusted-probe conditions.

## Limitations and next step

## Exact committed-test-head rerun

After change 0320 committed the functional test source and evidence, the designated agents repeated the same applicable selectors without edits at repository HEAD `2eec05101abe38b7ec50aefcb3ec04788dc26195`. Before/after status contained only the preserved untracked `docs/sdlc/evidence/s2-functional-test-run.md`.

| Test set | Exact command / selectors | Result |
|---|---|---|
| S2 Job Object cleanup | `C:\Python314\python.exe -m pytest tests/vst/test_e4_runner.py -k 'job_cleanup_failure_is_never_confirmed_and_fallback_runs or failed_job_handle_close_is_retried or run_receipt_fails_closed_when_job_cleanup_is_unconfirmed' -q` | 12 passed, 290 deselected; exit 0 |
| S2 Store lifecycle | `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_store_lifecycle.py` | 10 passed, 9 POSIX-only skipped; exit 0 |
| S2 operation recovery | `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_operation_recovery.py` | 4 passed; exit 0 |
| S3 worker adapter safe subset | `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_adapter.py -k "not ac4_resume_accepts_only_returned_named_app_checkpoint_and_is_idempotent"` | 8 passed, 1 resume case deselected; exit 0 |
| S3 pilot safe subset | Three selectors listed in the prior section | 3 passed; exit 0 |

Python: 3.14.3. Every invocation emitted one `pytest-asyncio` deprecation warning about `asyncio.get_event_loop_policy`; no failures occurred. The explicit POSIX skips, resume deselection, S3 stop/fencing cases and sandbox boundary cases remain `NOT_RUN`, not passes. These results are bound to the exact committed source/test HEAD `2eec051`; this evidence document and subsequent status records do not change source or test files.
