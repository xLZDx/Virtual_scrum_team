# 0043 S2 external-anchor concurrency and recovery

## What

- Added a cross-process coordinator lock beside the external anchor and hold it across anchored SQLite transactions plus checkpoint synchronization, and across anchored reads plus checkpoint comparison.
- Changed synchronization and startup recovery to verify the complete event HMAC chain, confirm that the stored checkpoint is the exact event prefix, then compare-and-append each missing checkpoint in order. Multi-event committed suffixes can recover after a crash.
- Require the external checkpoint log to start at the signed genesis checkpoint.
- Updated the S2 E3 contract and sandbox spec with serialization and suffix-recovery behavior.
- Corrected the `Store` module docstring's schema version from 3 to 4 to match `SCHEMA_VERSION`.

## Why

The database reviewer reported that normal transactions can append multiple events but startup recovered only exactly one event ahead. It also found that independent store processes could commit before synchronizing, allowing one writer to try anchoring directly across a gap. Separately, gate and anchor reads could compare an older SQLite snapshot to a newer valid external checkpoint and permanently integrity-lock the store. I verified those paths in `store.py` and `lifecycle.py` on baseline code HEAD `d779d55ea0cbb5f391a1f028cbab0345cab7e155`.

## Affected contracts and paths

- `tools/vst/lifecycle.py`: sidecar lock file `.coord.lock`, reentrant within the current thread/path and OS-locked across processes; anchor checkpoint history must begin at count zero/genesis.
- `tools/vst/store.py`: `_tx`/`_read_tx` coordination, serialized startup reconciliation, verified event-prefix history, ordered suffix synchronization/recovery, gate and event-anchor comparison under the same lock.
- `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`: E3 denominator includes multi-event transactions, concurrent writers, and read/write snapshot overlap.
- `docs/SANDBOX_SPEC.md`: lock location and fail-closed recovery contract.
- No database schema migration was added; event and receipt bytes remain unchanged.

## Decisions

- All store processes sharing an external anchor must use the same sidecar coordinator lock. The lock file resides next to the external anchor and must remain outside the worker mount.
- Recovery may append more than one event only after verifying the complete current DB HMAC chain and proving the latest signed checkpoint matches the exact chain prefix at its recorded count. Each checkpoint is then compare-and-appended sequentially.
- A missing anchor for a non-empty DB, anchor ahead of DB, invalid/forked chain, malformed checkpoint history, mismatching prefix, or append failure remains fail-closed. The store never reconstructs a missing anchor from DB state.
- Gate, `verify_event_chain`, and `event_anchor` hold the coordinator lock through their DB snapshot and external-anchor comparison, preventing a valid concurrent advance from being classified as tampering.

## Verification state

- This change was implemented against exact baseline `d779d55ea0cbb5f391a1f028cbab0345cab7e155`, after source review of `store.py` and `lifecycle.py`.
- No tests, checks, builds, CI, migrations, or runtime commands were run by the implementation agent. The test-agent suite at the baseline predates this change and is not evidence for it.
- Required test-agent scenarios: multi-event suffix recovery after commit-before-sync interruption; malformed/forked/anchor-ahead cases remain locked; two processes sharing an anchor serialize commits/checkpoints; and authoritative read snapshots do not false-lock while a writer advances.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation-engineer on `gpt-6-luna`. Required runtime evidence owner: E2E/functional test-agent roles under the repository's test ownership rule. No named technical storage service owner is established in canonical records.
- Next: have the authorized test agents add/run the named scenarios on the new committed HEAD; then complete fresh reliability/database/security review of the resulting code.

Agent-Attribution: implementation-engineer (gpt-6-luna); Codex executor
