# S3 worker pilot E2E exact-head evidence

## Scope and provenance

- Branch: `s3-vendor-neutral-worker-pilot`.
- Repository HEAD before and after the run: `71169f7e004160f9bc0781de2dce1568bbaa8e49`.
- The committed S3 product/test source under test is at `2a8c175`; `71169f7` is a follow-up evidence/documentation commit.
- Test owner/executor: `e2e-runner` (GPT-6 Luna, medium effort); accountable task owner: operator under delegated S3 work.
- Worktree was not clean: before and after the run, its only status entry was the pre-existing unrelated untracked file `docs/sdlc/evidence/s2-functional-test-run.md`. It was not staged, read, modified, or removed. The S3 test module builds its own synthetic candidate repositories under pytest temporary directories.

## Command and result

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_pilot_e2e.py
```

- Result: **8 passed, 0 failed, 0 skipped** in 89.31 seconds.
- One existing `pytest-asyncio` deprecation warning reported that `asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16.
- Exact HEAD was unchanged: `71169f7e004160f9bc0781de2dce1568bbaa8e49` before and after.
- The one unrelated untracked S2 evidence file was present with the same status before and after; no test or source files were modified by this run.

## Coverage and limits

The module exercises the in-repository synthetic pilot through Store and Supervisor boundaries: manifest-scoped edit, out-of-scope rejection, application-checkpoint resume, STOP fencing/idempotency/stale-start rejection, safe STOP cleanup diagnostics, and caller candidate identity rejection. The cleanup cases preserve process cleanup as `NOT_VERIFIED` and do not terminate operating-system processes.

No process-kill/kill-table scenario, external candidate execution, fresh signed sandbox probe, actual WSL boundary, or full candidate comparison was run. Those remain `NOT_RUN` or `NOT_VERIFIED`; this focused module does not satisfy those separate S3 acceptance gates.

## Acceptance mapping

| Criterion | State | Evidence / remaining work |
|---|---|---|
| S3 synthetic pilot E2E module at exact repository HEAD | PASS | Exact command above; 8 passed, 0 failed, 0 skipped at `71169f7`; code/test source is at `2a8c175`. |
| Preserve unrelated S2 evidence artifact | PASS | Same sole untracked path before and after; it was not staged or modified. |
| OS process cleanup after STOP or timeout | NOT_VERIFIED | The module asserts a non-approving message that cleanup remains unverified; no process termination was attempted. |
| Sandbox-bound worker and external candidate comparison | NOT_RUN | Requires fresh signed probe and separately authorized candidate gates; no candidate was acquired or executed. |

## Ownership and next step

The operator is accountable for the delegated S3 work; Codex is the executor. The repository does not establish a technical owner for the platform sandbox. Keep operating-system cleanup, sandbox containment, external candidate behavior and comparison open under their existing gates; do not infer them from the synthetic module pass.
