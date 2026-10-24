# 0090 S3 focused worker adapter tests

## What changed

- Added functional contract and Store recovery tests for bounded request/response values, STOP/resume fencing, idempotency, budget edges, named application checkpoints, and the rule that worker state cannot create acceptance receipts.
- Added synthetic pilot journeys for scoped edits, trusted candidate identity, app-checkpoint resume, and durable STOP fencing.
- Kept fresh signed sandbox-probe and actual WSL-boundary scenarios explicitly `NOT_RUN`; synthetic fixtures cannot prove those boundaries.

## Why

S3's in-repository implementation needs focused acceptance evidence that exercises the committed adapter and Store/Supervisor boundary without executing external candidates or prohibited OS process-kill paths.

## Affected contracts and paths

- `tests/vst/test_s3_worker_adapter.py`
- `tests/vst/test_s3_worker_pilot_e2e.py`
- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`, `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, and `governance/DOCUMENT_REGISTRY.md`

## Decisions and ownership

- Accountable task owner: operator under delegated continuation. Test authors/executors: `functional-test-reviewer` and `e2e-runner` (GPT-6 Luna, medium); coordinator: Codex.
- Worker OS cleanup and process-kill/kill-table remain outside this run and are not inferred from Store fencing.

## Verification state

- The functional agent reported 8 passed on source commit `bf7c34b8f2369da6c2bbc64b10678e616f97053b` using `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_adapter.py` (one pytest-asyncio deprecation warning).
- The E2E agent reported 5 passed using `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_pilot_e2e.py`; source code matched `bf7c34b8f2369da6c2bbc64b10678e616f97053b`, but exact checkout HEAD at corrected rerun start was not captured. These results are provisional until both focused files are rerun against the committed head.
- No full suite, build, CI, migration, external candidate, actual sandbox probe, WSL-boundary, or process-kill test was run for this record.
