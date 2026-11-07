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

## Current continuation: exact S2 lifecycle regression follow-up

At repository HEAD `c7ad087c9006d07eeafd348cdc3df8cbc73888d1`, the designated `e2e-runner` ran the broad safe lifecycle selection:

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py -k "not test_signer_rejects_malformed_signing_evidence"
```

The first run returned **64 passed, 2 failed, 5 skipped, 4 deselected** (exit 1). The two failures were `test_strict_windows_launch_suspends_assigns_job_then_resumes_before_command` and `test_nonstrict_windows_launch_keeps_unsuspended_compatibility_path`; both received `EXIT_CAPTURE_INCOMPLETE` (-4) instead of 0. Inspection showed the test-only `MockJob.terminate_and_close()` implicitly returned `None`, while the production contract treats only explicit `True` as confirmed cleanup. The implementation was not changed.

`functional-test-reviewer` updated that mock to return `True` on successful and idempotent cleanup while preserving assignment, thread-discovery and resume failure cases. The rerun used:

```powershell
C:\Python314\python.exe -m pytest tests/vst/test_s2_runner_lifecycle.py -k 'not signer_rejects_malformed_signing_evidence' -q
```

It exited 0: **66 passed, 5 skipped, 4 deselected**, with one `pytest-asyncio` deprecation warning. Python 3.14.3; elapsed 47.63 seconds. HEAD remained `c7ad087c9006d07eeafd348cdc3df8cbc73888d1`; the test file was modified in the working tree for this run. The corrected test source must be committed and rerun at its exact committed HEAD before final S2 review.

The designated functional-test reviewer also ran `C:\Python314\python.exe -m pytest tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py -q` at exact HEAD `c7ad087c9006d07eeafd348cdc3df8cbc73888d1`: exit 0, **60 passed**, one pytest-asyncio deprecation warning, Python 3.14.3. HEAD and status were unchanged; only the preserved untracked S2 evidence file was present. These tests cover in-memory contract and diff-gate behavior and are not Windows/POSIX containment runtime evidence.

After change 0322 committed the corrected lifecycle test, the designated functional-test reviewer ran the same broad lifecycle command at exact committed HEAD `9ce27f0d9837e2d302872df0b878ebcaba15b513`: `C:\Python314\python.exe -m pytest tests/vst/test_s2_runner_lifecycle.py -k 'not signer_rejects_malformed_signing_evidence' -q`. Result: exit 0, **66 passed, 5 skipped, 4 deselected**, one pytest-asyncio deprecation warning, Python 3.14.3, 69.49 seconds. HEAD and status were unchanged before/after; only the preserved untracked S2 evidence file was present.

The designated functional-test reviewer also repeated the contract/diffgate modules at exact committed HEAD `9ce27f0d9837e2d302872df0b878ebcaba15b513` using `C:\Python314\python.exe -m pytest tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py -q`. Result: exit 0, **60 passed**, one pytest-asyncio deprecation warning, Python 3.14.3, 0.82 seconds. HEAD was unchanged. The working tree contained only the concurrent documentation updates for change 0323 and the preserved untracked S2 evidence file; the test agent made no edits.

The designated E2E runner also attempted `tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture` in Ubuntu-24.04 WSL. The distro was available, but `/mnt/d/Repo/Virtual_scrum_team` did not exist because `/mnt/d` was an empty mount placeholder. The selector is **NOT_RUN**; no mount or provisioning change was attempted.

## POSIX reviewer-boundary selector from a disposable WSL source snapshot

To avoid mounting the canonical Windows checkout, the designated `e2e-runner` created a one-time archive snapshot of committed HEAD `dfb99cbf611f42a89e27277dbe4a2818518bb311` at `/tmp/vst-s2-boundary-dfb99cb` inside Ubuntu-24.04 WSL. The snapshot contained no `.git` directory and was not a worktree. The selector file was byte-for-byte unchanged from source/test HEAD `9ce27f0d9837e2d302872df0b878ebcaba15b513` (`git diff 9ce27f0..dfb99cb -- tests/vst/test_s2_sandbox_probe.py` was empty). No canonical checkout files were modified.

Environment: Ubuntu-24.04 WSL, Python 3.12.3, pytest 7.4.4. The parent invocation ran as root; the selector launched the child under the provisioned `vst-reviewer` identity and verified denied writes to the disposable worktree/Store fixture. Exact command:

```powershell
wsl.exe -d Ubuntu-24.04 --cd /tmp/vst-s2-boundary-dfb99cb python3 -m pytest -q tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture
```

Result: exit 0; **1 passed in 0.54 seconds**. The test fixture and archive snapshot were removed; a follow-up search found no `/tmp/vst-reviewer-boundary-*` fixture. No packages/downloads, mount changes, worktrees, process-kill, mutation, E8, or real sandbox-inventory steps were performed.

This closes only the named reviewer write-denial selector for the disposable fixture. Full POSIX containment, canonical Windows-path binding, signed run-bound sandbox inventory/default-deny egress, and other S2 platform criteria remain `NOT_RUN` or `NOT_VERIFIED` as listed above.

## S3 AC-4 app-checkpoint resume selector

The designated `e2e-runner` inspected and ran the previously deselected S3 adapter resume selector. It uses a `SliceFixture` under pytest `tmp_path`, stores a synthetic returned `INCONCLUSIVE`/`INTERRUPTED` application checkpoint, calls `resume_epoch_idempotent` twice, and asserts the same epoch is returned. Inspection found no subprocess, OS process-kill, external service, mutation testing, or policy-excluded lifecycle behavior.

Command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_adapter.py::test_ac4_resume_accepts_only_returned_named_app_checkpoint_and_is_idempotent`

At repository HEAD `42ab7bf90bdf7ab36b41f1df813945ef6a0a6f10`, Python 3.14.3, result was exit 0, **1 passed**, one `pytest-asyncio` deprecation warning. HEAD and status were unchanged before/after except the preserved untracked S2 evidence file. The test file SHA-256 `625f93f43402aff1a6447c2273ef9773cd8ded38` matched the exact committed file at `2eec051`; no edits were made.

Together with the prior safe adapter subset at `2eec051` (8 passed, 1 deselected), the adapter selectors now have successful outcomes for all nine cases. This does not prove STOP/crash recovery, cross-process locking, sandbox boundaries, external candidate execution, or the complete S3 scenario denominator; those remain `NOT_RUN` or gated.
