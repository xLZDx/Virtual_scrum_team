# Change 0320 — Record S2 cleanup and current S2/S3 regression evidence

## What changed

- Added 12 functional contract cases for mocked false/exception outcomes from `TerminateJobObject` and `CloseHandle`, handle-close retry, fallback invocation, and fail-closed signed receipts.
- Added `docs/sdlc/evidence/s2-s3-current-source-regression-5ae495c.md` with exact commands, Python version, source head, counts, skips/deselections, dirty-state notes, and attempt history.
- Reconciled S2 current-source and gate status in `docs/sdlc/STATE.md`; recorded the remaining S2 and S3 test limitations in `core/BACKLOG.md`.
- Added the latest four-sprint checkpoint to `core/STATE.md` so the project landing state points to the current S2/S3 evidence and accurately summarizes the open S4/S5 gates.
- Added this per-change record and related decision and lesson entries.

## Why

Three exact-head specialist reviews identified a reachable Windows cleanup false-success defect; change 0319 fixed the source. The previous S2 evidence was bound to `dc959`, while later S3 changes modified shared Store/publication paths. Designated test agents ran the focused fail-closed contract cases and safe exact-source S2/S3 subsets to reduce that gap without invoking prohibited process-kill, stop, resume, or sandbox scenarios.

## Evidence and verification

- Source HEAD for all runs: `5ae495c073a7bfb5d26f209f582c00e7c4c954c7`; Python 3.14.3 via `C:\Python314\python.exe`. Detailed commands and results: `docs/sdlc/evidence/s2-s3-current-source-regression-5ae495c.md`.
- Functional-test-reviewer: 12 passed, 290 deselected on mocked Win32 cleanup cases. It corrected an initial test-double omission and four retry-count assertions before the final passing run.
- E2E-runner: S2 Store lifecycle 10 passed / 9 explicit POSIX skips; operation recovery 4 passed; S3 adapter safe subset 8 passed / 1 resume deselected; S3 pilot safe subset 3 passed.
- One `pytest-asyncio` deprecation warning occurred in each agent invocation. No test was run by the primary session.
- All test commands ran with `tests/vst/test_e4_runner.py` modified but uncommitted; the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved. Exact committed-test-head reruns are still required.
- S3 app-resume, STOP/fencing cleanup, and sandbox-boundary scenarios remain `NOT_RUN`; S2 POSIX external-anchor cases remain skipped/`NOT_RUN` as detailed in the evidence file.

## Remaining acceptance and owners

- Codex owns committing the test and evidence record, then coordinating a final exact committed-test-head rerun with `functional-test-reviewer` and `e2e-runner`.
- Operator remains accountable for S2/S3. Operator owns any policy authorization for prohibited scenarios; Codex prepares fixtures and coordinates; the designated test roles execute only after the gate permits.
- Fresh exact-head specialist consensus and GPT-PM approval remain pending after the final committed-test-head rerun. No push/PR is authorized until approval.

Change: 0320
Executor: Codex
