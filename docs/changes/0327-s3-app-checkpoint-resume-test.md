# Change 0327 — Record the S3 synthetic app-checkpoint resume selector

## What changed

- Recorded the previously deselected S3 AC-4 app-checkpoint resume selector and its safety review.
- Updated S3 plan/backlog/evidence to distinguish this local idempotent resume result from STOP/crash recovery and sandbox acceptance.

## Why

The earlier safe S3 adapter run deselected this single selector. Inspection showed it exercises Store epoch idempotency using a synthetic returned application checkpoint and isolated pytest temporary fixture; it does not run a process-kill, call an external service, or enter a policy-excluded lifecycle path. Running it closes that bounded test gap without implying crash/STOP or sandbox acceptance.

## Evidence and verification

- Test owner: `e2e-runner`, GPT-6 Luna.
- Command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_adapter.py::test_ac4_resume_accepts_only_returned_named_app_checkpoint_and_is_idempotent`.
- Python 3.14.3; exit 0; 1 passed; one pytest-asyncio deprecation warning.
- Repository HEAD before and after: `42ab7bf90bdf7ab36b41f1df813945ef6a0a6f10`. The test file SHA-256 `625f93f43402aff1a6447c2273ef9773cd8ded38` matches its committed version at `2eec051`. Only the preserved untracked S2 evidence file appeared in status; no edits/staging occurred.
- Full command, inspection notes, and limitation: `docs/sdlc/evidence/s2-s3-current-source-regression-5ae495c.md`.
- No test, check, or build was run by Codex in this documentation update.

## Remaining acceptance and owners

- This selector covers only synthetic idempotent application-checkpoint resume. S3 STOP/crash recovery, cross-process locking, candidate comparison, external egress/replay, and sandbox-boundary evidence remain `NOT_RUN` or gated.
- Operator remains accountable for S3; Codex coordinates authorized work; `e2e-runner` owns required E2E test execution. S3 worker runs remain behind the S2 gate and a fresh run-bound sandbox probe.
- No PR, merge, candidate acquisition, or worker choice is authorized by this record.

Change: 0327  
Executor: Codex
