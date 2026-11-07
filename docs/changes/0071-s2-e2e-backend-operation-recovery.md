# 0071 S2 E2E backend operation recovery

## What changed

- Added two E2E regressions to `tests/vst/test_s2_runner_lifecycle.py` for external callback lock release and bounded local Git timeout recovery.
- The callback test proves an independent Store write can complete while the backend callback is running outside the primary Store/anchor transaction.
- The timeout test verifies the backend passes a finite timeout to source-backed local Git, a timeout leaves durable PENDING intent, Store restart permits same-key/same-payload retry, the target ref is created once, and a repeated backend key/payload is idempotent while a changed payload is rejected.
- Added dedicated E2E evidence at `docs/sdlc/evidence/s2-e2e-operation-recovery-0071.md`; the functional owner's change record 0070 separately records its tests and the shared combined suite.

## Why

The S2 reliability change moves push and pull-request effects outside Store locks and represents uncertain external outcomes as durable pending operations. The tests exercise the real local Git backend and SQLite/external-anchor boundary, including restart and the backend's own operation-key binding.

## Scope and compatibility

- No production code or schema was changed by this test/evidence commit.
- The Git remote is a disposable local bare repository. The test never contacts a real remote.
- Timeout is injected at the subprocess boundary; the test confirms a finite timeout was supplied and exercises durable recovery without spawning or intentionally killing a timed-out child.
- Receipt operations, process-kill paths, and kill-table suites are outside this test batch.

## Verification

- Product source HEAD: `c0e7e9ce15958b6c6de7811bcaf1020119ba169d`.
- Command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`.
- Environment: Python 3.14.3, pytest 8.4.2, Windows 11 build 10.0.26300-SP0.
- Result: exit 0; 72 passed, 14 skipped, 1 pytest-asyncio deprecation warning; 86 total cases.
- Skip boundaries: POSIX anchor and worker-identity cases require POSIX; four E4 containment cases remain `NOT_RUN` due platform requirements and the explicit process-kill/kill-table prohibition.
- Initial red runs on earlier source/test states and their product/test-fixture classifications are preserved in the linked E2E evidence. They are not called flakes and do not alter the final exact-head result.

## Ownership

- Accountable task owner: operator, by delegated task.
- Executor and E2E test author: Codex E2E runner (`gpt-6-luna`, medium effort).
- Functional reviewer owns the separate signed manual-override and Store contract tests recorded in change 0070.
- No named technical service owner for the local Store/Git backend is established in the canonical records.

## Next action

The callback and timeout/restart E2E criteria pass on the recorded source HEAD. Keep POSIX and prohibited process-containment scenarios marked `NOT_RUN`; the parent coordinator owns S2 acceptance reconciliation.
