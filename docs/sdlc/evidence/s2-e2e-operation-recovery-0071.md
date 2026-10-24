# S2 E2E backend operation recovery evidence (0071)

## Scope and ownership

- Accountable task owner: operator, by delegated task.
- Executor/test owner: Codex E2E runner (`gpt-6-luna`, medium effort).
- Code under test: exact source HEAD `c0e7e9ce15958b6c6de7811bcaf1020119ba169d`.
- Test files executed: `tests/vst/test_s2_runner_lifecycle.py` and `tests/vst/test_s2_store_lifecycle.py` only.
- No production source, build, CI, migration, or unrelated test suite was edited or run in this verification.

## Final E2E-owned module run

- Exact command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`
- Environment: Python 3.14.3; pytest 8.4.2; Windows 11 build 10.0.26300-SP0.
- Exact source revision printed immediately before the run: `c0e7e9ce15958b6c6de7811bcaf1020119ba169d`.
- Result: exit 0; 72 passed, 14 skipped, 1 warning; 86 cases total; pytest reported 10.40 seconds (command wall time 13.16 seconds).
- Warning: pytest-asyncio emitted a deprecation warning for `asyncio.get_event_loop_policy`.

## Requested acceptance coverage

| Criterion | State | Evidence |
|---|---|---|
| Backend callback runs outside the Store write/anchor transaction | PASS | `test_external_backend_callback_runs_outside_store_anchor_transaction` starts an independent Store in a separate thread during the callback and requires its write to finish before the callback returns. The per-thread Store connection respects SQLite thread affinity. |
| Local Git timeout records durable PENDING and permits restart retry | PASS with boundary-injection limit | `test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key` injects `subprocess.TimeoutExpired` at the actual bounded `git -C <source_repo> push` invocation boundary, checks that the backend received a 10-second timeout and that Store retained PENDING plus the unresolved event, closes/reopens Store, then retries with the same key and payload. The candidate commit is seeded into a local bare target. |
| Completion and same-key retry are idempotent | PASS | The same regression checks one durable completion event, the target ref, direct backend retry with the same key/payload, and rejection of a different branch payload under the same key. Supervisor replay also returns the completed result. |
| Previously completed internal operation row remains replayable | PASS in same-HEAD combined run before functional test relocation | `test_completed_legacy_idempotent_operation_remains_replayable` passed in the earlier 90-case runner/store run on the same source HEAD. The functional reviewer later moved its four functional-owned cases to `tests/vst/test_s2_operation_recovery.py`; the current E2E-owned runner/store pair now collects 86 cases. The functional combined run also reported 76 passed and 14 skipped on the same HEAD. |
| Completed manual-override ID rejects a different valid signed record | PASS in functional-owned coverage | `tests/vst/test_s2_operation_recovery.py::test_manual_override_same_action_id_with_changed_signed_record_is_rejected_after_restart` is functional-reviewer-owned. It passed in the functional agent's combined 90-case run on the same HEAD; see that agent's 0070 evidence. It was not duplicated in E2E-owned tests. |

The timeout failure is injected before launching the Git child. This proves that the backend supplies a finite subprocess timeout and that the durable retry protocol recovers after a timeout result; real child termination/cleanup after a live OS timeout remains `NOT_RUN` because process-kill scenarios are prohibited. No process was intentionally killed by this run.

## Skips and NOT_RUN boundaries

The 14 pytest skips are deliberate platform/prohibition boundaries, not passing substitutes:

- 9 POSIX external-anchor tests: permissions/locking, restored database, one-event and multi-event suffix recovery, and five invalid-anchor suffix states. Windows does not prove POSIX locking or mode behavior.
- 1 POSIX worker identity test: account separation, key-file denial, and Unix-socket denial require the provisioned POSIX identity boundary.
- 4 E4 platform containment cases: POSIX process-group cleanup, post-exit descendant cleanup, worker key permissions, and nested Windows Job Object acceptance. The process containment cases are explicitly prohibited here; Job Object runtime nesting is unavailable on this host.

No process-kill, kill-table, mutation, CI, build, migration, or tests outside the two owned modules were run.

## Earlier red diagnostics (kept separate from the final pass)

1. On source HEAD `14bd1e85459d97c9caa90a62b117a41020200b9a`, command `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py` reported 2 failed, 71 passed, 14 skipped, 1 warning (pytest 16.50 seconds). The external-operation history verifier rejected a pending external operation on anchored commit/restart. This was a product defect fixed by change 0067. The same early run also had an E2E callback fixture using a SQLite connection across threads; that fixture was corrected and is not classified as product behavior.
2. On source HEAD `cc30917644e762065a6afed3650ad890cf124e22`, an intermediate full-module run reported 3 failed, 74 passed, 14 skipped, 1 warning. The callback failures were test-fixture thread-affinity errors; the timeout setup first lacked the candidate commit in the bare target, then exposed that the backend needed its explicit source repository. The latter product defect was fixed by change 0069.
3. On `cc30917`, after correcting the fixture, the local Git push exceeded a test timeout of one second. The timeout injection was retained, while the bounded retry timeout was set to 10 seconds. A focused diagnostic also exposed an incorrect test expectation that the durable side-table result changes from PENDING; the append-only contract keeps PENDING in that row and records completion as an event. The test now asserts the completion event result instead.

These failures were deterministic product/test-fixture defects across different source/test states, not flakes. The final result is the exact-head pass above; earlier red runs remain visible and are not upgraded to pass.

## Result and next action

E2E acceptance for callback lock release and bounded timeout/restart/same-key backend recovery passes on the recorded Windows source HEAD. The functional-owned signed override and legacy compatibility cases are covered by the functional agent's same-HEAD combined run. Remaining platform and process-containment cases stay `NOT_RUN`; their exact dependencies and prohibition are listed above. No further action is required for this E2E batch; the parent coordinator can reconcile both test-owner evidence records into S2 phase status.
