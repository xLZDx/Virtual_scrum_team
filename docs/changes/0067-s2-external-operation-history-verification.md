# 0067 S2 external-operation history verification

## What changed

- Extended `_verify_supervisor_records` to recognize legacy completed operation rows and the new external-operation pending-intent format.
- Verifies every external intent's operation key, operation name, payload digest, `PENDING` state, and positive attempt number against its append-only row.
- Verifies completion event binding and canonical result digest, rejects conflicting completed results, validates unknown outcome bindings, and rejects orphaned completion/unknown events.
- Kept prior legacy operation rows compatible and kept the external operation row append-only; no schema migration or receipt version change.

## Why

The designated functional and E2E agents ran focused regressions on source head `14bd1e85459d97c9caa90a62b117a41020200b9a`. They found that when an external anchor was configured, the first new pending operation row failed `_verify_supervisor_records` because the existing invariant required a legacy `SUPERVISOR_OPERATION` completion event for every row. The same integrity failure prevented same-key retry after reopening the store. The test agents recorded 3 passing/1 failing functional regressions and 71 passing/2 failing/14 skipped E2E cases on the initial code head; this initial failed run remains part of the acceptance evidence.

## Ownership

- Accountable task owner: operator.
- Executor: Codex.
- Regression test author/executor: `functional-test-reviewer` and `e2e-runner` only.
- The initial failure was reported by those agents; the source fix is by Codex.

## Verification state

- Initial failing code head: `14bd1e85459d97c9caa90a62b117a41020200b9a`.
- Initial functional result: 3 passed, 1 failed; the anchored external-operation intent failed during consistency verification.
- Initial E2E result: 71 passed, 2 failed, 14 skipped; both failures were the same consistency-invariant defect in callback/anchor-lock and restart-retry paths.
- Exact commands and exception traces are recorded in `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md` after the designated agents complete the final rerun.
- The code fix itself has not yet been rerun. No tests/checks/builds/CI/migrations were run by Codex.
