# Change 0447: defer initial-anchor directory sync as nonblocking

## What changed

- Resolved the database-review MINOR against the S2 anchor contract and marked parent-directory fsync after first anchor creation as a nonblocking availability improvement.
- Clarified that a missing anchor for nonempty data remains fail-closed, preserving integrity; S2 does not promise uninterrupted availability after host power loss.

## Why

The database review conditioned its recommendation on power-loss availability being required. S2 section 10.3 requires missing-anchor data to remain locked and fail-closed pending operator recovery; it does not promise uninterrupted availability after a host power loss. The MINOR therefore belongs in the backlog and does not block code closure.

## Affected paths

- `core/BACKLOG.md`
- `docs/sdlc/STATE.md`
- `docs/changes/0447-defer-anchor-directory-sync-minor.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and verification

- Database-review evidence: `docs/sdlc/evidence/s2-final-specialist-review-79155fd-20261027.md`, exact source/test HEAD `79155fdf9f1f4a7ba71358592ccd54c669a76291`.
- Contract basis: `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`, section 10 item 3: missing anchor for nonempty data remains write-locked and fail-closed pending operator recovery.
- This disposition is an inference from the accepted contract; it does not claim directory-entry durability after power loss.
- No tests/checks/build/CI/migrations were run.

## Ordered next steps and owners

1. Codex: leave the optional parent-directory fsync improvement in the nonblocking backlog.
2. Operator: owns any decision to require uninterrupted service after host power loss or change the environment/policy gates.
3. Codex: continue only required S2 acceptance work; this MINOR is not a sprint gate.

## Attribution

Change: 0447
Executor: Codex
