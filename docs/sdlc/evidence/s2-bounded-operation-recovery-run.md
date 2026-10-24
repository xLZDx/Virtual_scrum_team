# S2 bounded idempotent backend operation regressions

## Initial focused run on source HEAD `14bd1e8`

- Full source revision: `14bd1e85459d97c9caa90a62b117a41020200b9a` (`fix(s2): persist bounded idempotent backend operations`).
- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_manual_override_same_action_id_with_changed_signed_record_is_rejected_after_restart tests/vst/test_s2_runner_lifecycle.py::test_external_operation_intent_commits_before_backend_and_releases_anchor_lock tests/vst/test_s2_runner_lifecycle.py::test_external_operation_timeout_stays_pending_and_same_key_payload_recovers tests/vst/test_s2_runner_lifecycle.py::test_completed_legacy_idempotent_operation_remains_replayable`
- Environment: Python 3.14.3, pytest 8.4.2, Windows NT 10.0.26300.0, PowerShell 7.6.7.
- Result: exit 1; 3 passed, 1 failed, 1 pytest-asyncio deprecation warning in 1.42 seconds.
- Passed IDs: `test_manual_override_same_action_id_with_changed_signed_record_is_rejected_after_restart`, `test_external_operation_timeout_stays_pending_and_same_key_payload_recovers`, `test_completed_legacy_idempotent_operation_remains_replayable`.
- Failed ID: `test_external_operation_intent_commits_before_backend_and_releases_anchor_lock` (the functional test was later narrowed to the Store transaction boundary; E2E owns cross-Store backend locking).
- Failure evidence: the first pending-intent transaction committed, then `_tx_locked()` called `_sync_external_anchor()`; `_verify_supervisor_records()` raised `StoreError("supervisor records differ from their append-only events")` because it only matched operation rows against the legacy `SUPERVISOR_OPERATION` marker. The external operation's valid `PENDING` row is instead represented by new intent/completion/unknown events. The backend callback did not run.
- Product fix was identified by the functional test and implemented in change 0067; this initial failure is retained as regression evidence, not a passing result.

## Post-fix focused regressions on source HEAD `cc30917`

- Full source revision: `cc30917644e762065a6afed3650ad890cf124e22` (`fix(s2): verify external operation intents`).
- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_manual_override_same_action_id_with_changed_signed_record_is_rejected_after_restart tests/vst/test_s2_runner_lifecycle.py::test_external_operation_intent_and_completion_are_committed_around_callback tests/vst/test_s2_runner_lifecycle.py::test_external_operation_timeout_stays_pending_and_same_key_payload_recovers tests/vst/test_s2_runner_lifecycle.py::test_completed_legacy_idempotent_operation_remains_replayable`
- Result: exit 0; 4 passed, 0 skipped, 1 pytest-asyncio deprecation warning in 0.97 seconds.
- Covered IDs: `test_manual_override_same_action_id_with_changed_signed_record_is_rejected_after_restart`, `test_external_operation_intent_and_completion_are_committed_around_callback`, `test_external_operation_timeout_stays_pending_and_same_key_payload_recovers`, `test_completed_legacy_idempotent_operation_remains_replayable`.

## Relevant module run on source HEAD `cc30917`

- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`.
- Result: exit 1; 75 passed, 14 skipped, 2 failed, 1 pytest-asyncio deprecation warning in 16.98 seconds.
- Both failing tests were concurrent E2E additions in `test_s2_runner_lifecycle.py`: `test_external_backend_callback_runs_outside_store_anchor_transaction` shared a SQLite connection with a different thread, and `test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key` attempted to push a candidate commit from a bare remote that did not contain that object. The first is an E2E fixture defect; the second exposes a product E8 backend source-repository binding defect, confirmed by the coordinator. The coordinator is fixing the source API; the E2E owner is correcting its callback fixture.
- This run is not a final pass. The coordinator directed that the relevant modules be rerun only after the next source commit and E2E-owned test corrections.

## Final combined relevant-module run on source HEAD `c0e7e9c`

- Full source revision: `c0e7e9ce15958b6c6de7811bcaf1020119ba169d` (the synthetic publishing source-repository fix).
- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_operation_recovery.py tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`
- Result: exit 0; **76 passed, 14 skipped, 1 warning** in 11.84 seconds. Total denominator: 90 collected cases (76 executed and passed, 14 explicitly skipped).
- Environment: Python 3.14.3, pytest 8.4.2, Windows NT 10.0.26300.0, PowerShell 7.6.7.
- Warning: pytest-asyncio deprecation for `asyncio.get_event_loop_policy`; no test failed due to it.
- The combined command includes the four functional regressions, the E2E-owned backend callback and real local-Git timeout/restart cases, and the Store lifecycle module. It replaces earlier partial runs for acceptance.
- Functional IDs passed: `test_completed_override_action_id_with_changed_valid_signed_record_rejected_after_restart`, `test_external_operation_intent_and_completion_are_committed_around_callback`, `test_external_operation_timeout_stays_pending_and_same_key_payload_recovers`, and `test_completed_legacy_idempotent_operation_remains_replayable`.
- E2E IDs passed in the same command: `test_external_backend_callback_runs_outside_store_anchor_transaction` and `test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key`.

### Skipped cases

- 1 POSIX account and Unix-socket permissions scenario: unavailable on Windows.
- 4 E4 process-containment scenarios: not run because process-kill/kill-table execution is prohibited; the alternative authorized nested Windows Job Object host was unavailable.
- 9 Store external-anchor cases: POSIX permissions, restore detection, interrupted recovery and failure-state scenarios require the provisioned POSIX sandbox.

These are `NOT_RUN`, not passes; they remain dependencies for the complete S2 runtime acceptance. The combined test/evidence working tree also contained the parent-owned S3 plan edit and a pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; neither was staged by this test task.

## E2E-owned full-module rerun on source HEAD `c0e7e9ce15958b6c6de7811bcaf1020119ba169d`

- Exact command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`.
- Environment observed in the same session: Python 3.14.3, pytest 8.4.2, Windows 11 build 10.0.26300-SP0.
- Result: exit 0; 76 passed, 14 skipped, 1 warning in 26.67 seconds (pytest-reported; command wall time 29.95 seconds). The warning was pytest-asyncio's `get_event_loop_policy` deprecation.
- The command collected/executed 90 cases at run time. After this run, the functional reviewer moved four functionally owned cases from `test_s2_runner_lifecycle.py` to `test_s2_operation_recovery.py`; current collect-only for the two E2E-owned modules is 86. The four moved tests had passed during this run; the functional owner is running them in the new module. Do not compare those denominators as an unchanged file set.
- E2E regression IDs passed: `test_external_backend_callback_runs_outside_store_anchor_transaction`; `test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key`; `test_idempotent_push_and_pull_request_use_local_bare_remote`. Also passed within the same module run: `test_external_operation_intent_commits_before_backend_and_releases_anchor_lock`, `test_external_operation_timeout_stays_pending_and_same_key_payload_recovers`, `test_completed_legacy_idempotent_operation_remains_replayable`, and the functional-owned `test_manual_override_same_action_id_with_changed_signed_record_is_rejected_after_restart` before it was moved.
- The timeout regression injects `subprocess.TimeoutExpired` at the bounded `git -C <source_repo> push` boundary, verifies a durable `PENDING` row and unknown event, closes/reopens Store, then retries with the same key and payload. It checks the source-backed bare remote ref and one completion event. It does not launch a process that is intentionally killed.
- The callback regression checks that an independent Store write can finish while the backend callback is active. Its independent Store is created and closed in the writer thread to respect SQLite thread affinity.
- Skips (all explicitly platform/prohibition gated): 9 POSIX-only anchor permission/recovery/failure-state cases; 1 POSIX worker-account and Unix-socket access case; 4 E4 process-containment cases (POSIX process group, post-exit descendants, worker key permissions, Windows parent Job Object nesting). The E4 cases remain `NOT_RUN`; no process-kill or kill-table test was run.
- Historical red runs above remain diagnostic records. They are not reclassified as flakes and are not part of the final green result.

## Functional-owned follow-up on hook-free object-transfer source HEAD `202e068`

- Full source revision: `202e0680e8e1b4fb30dcbe9659bf550d06443d90` (`fix(s2): import candidate before ancestry check`).
- E2E test author confirmed code authoring was complete before this run. The E2E-owned runner test file was not executed by this focused command.
- Exact command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_operation_recovery.py`.
- Result: exit 0; 4 passed, 0 skipped, 1 pytest-asyncio deprecation warning in 0.52 seconds.
- Environment: Python 3.14.3, pytest 8.4.2, Windows NT 10.0.26300.0, PowerShell 7.6.7.
- Passed IDs: `test_completed_override_action_id_with_changed_valid_signed_record_rejected_after_restart`, `test_external_operation_intent_and_completion_are_committed_around_callback`, `test_external_operation_timeout_stays_pending_and_same_key_payload_recovers`, `test_completed_legacy_idempotent_operation_remains_replayable`.
- This verifies the four Store-level recovery and override cases against the new source head. The new hook-free pack-transfer, source-only object, ref-conflict and timeout-process boundary behavior is owned by the E2E module and is not covered by this command; retain its separate exact-head evidence.

## Functional-owned follow-up on bounded pack-resource source HEAD `1ef3fee`

- Full source revision: `1ef3fee07d5743dc8e42c632e1dc3100601116a7` (`fix(s2): cap cumulative synthetic object storage`).
- The E2E agent confirmed test authoring was complete for this source revision before the run.
- Exact command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_operation_recovery.py`.
- Result: exit 0; 4 passed, 0 skipped, 1 pytest-asyncio deprecation warning in 1.35 seconds.
- Environment: Python 3.14.3, pytest 8.4.2, Windows NT 10.0.26300.0, PowerShell 7.6.7.
- Passed IDs: `test_completed_override_action_id_with_changed_valid_signed_record_rejected_after_restart`, `test_external_operation_intent_and_completion_are_committed_around_callback`, `test_external_operation_timeout_stays_pending_and_same_key_payload_recovers`, `test_completed_legacy_idempotent_operation_remains_replayable`.
- This command verifies the four Store-level recovery and override contracts on the newer source head. It does not execute the E2E-owned pack transfer, hook-denial, storage-cap, concurrency, ref-conflict or timeout-boundary cases; record those only from the separate E2E exact-head run.
