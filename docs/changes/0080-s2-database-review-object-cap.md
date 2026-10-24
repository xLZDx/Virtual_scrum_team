# 0080 S2 database review of synthetic object-store accounting

## What changed

- Added the read-only database review at `docs/sdlc/s2-database-review-1ef3fee.md` for S2 source `1ef3fee07d5743dc8e42c632e1dc3100601116a7`.
- Recorded one MAJOR: failed or incomplete Git child termination/reaping can allow `index-pack` to outlive `_target_storage_lock`, so another writer could race the byte accounting and exceed the cumulative storage cap.
- Reconciled the finding against the E2E evidence: normal Windows lock and WSL `flock` contention/release passed; live termination and post-start overflow cleanup remain `NOT_RUN` under the process-kill restriction.
- Recorded the external boundary: direct writers outside `SyntheticOperationBackend` and filesystem metadata are not covered by the logical 512 MiB cap; canonical technical ownership for such writers is not established.

## Why

S2's cumulative target object cap depends on every writer using the same advisory lock and on no previous object writer continuing after the lock is released. The review found that cleanup currently swallows kill and wait failures, which leaves that invariant unproven and potentially false.

## Ownership and next action

- Accountable task owner: operator, by delegated S2 task.
- Executor: Codex.
- Required next action: update the pack-import lifecycle so uncertainty about child termination poisons the target and prevents future writes, or otherwise guarantee all writers are reaped before releasing the lock. Then request a fresh exact-source review. Tests that force process termination remain prohibited and must stay `NOT_RUN` unless the applicable restriction changes.
- Technical owner for an external direct writer or filesystem quota service: not identified in canonical project records. The code-level assumption is that the target remains supervisor-owned and all writers use this backend.

## Verification state

- Reviewed source: `1ef3fee07d5743dc8e42c632e1dc3100601116a7`.
- Reviewed repository head: `eab4ea5d6363e3f8efa99533a996a5388ffaa48c`.
- Reviewer: `database-reviewer`, GPT-6 Luna, medium effort.
- No tests, checks, builds, CI, migrations, or runtime operations were run for this review.
- E2E evidence is recorded in change 0079 and `docs/sdlc/evidence/s2-e2e-hook-free-pack-1ef3fee.md`; it does not cover failed child termination/reaping.
