# 0048 S2 atomic lifecycle intent admission

## What changed

- `tools/vst/store.py`: added `begin_action`, which verifies the event chain and external checkpoint, derives lifecycle state and unresolved actions from the control NOTE stream, checks the expected predecessor state, and appends lifecycle intent inside the same serialized write transaction.
- `tools/vst/supervisor.py`: routes start, stop, rollback, cleanup, and resume intents through the Store atomic admission path. A stale Supervisor cache cannot authorize an action after another instance has advanced or locked lifecycle state.
- `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`: adds cross-instance concurrent lifecycle admission to the E7 test denominator and rejection criteria.
- Decision/lesson logs and document registry record the MAJOR finding and fix.

## Why

Independent Supervisor instances can cache the same lifecycle state. Appending distinct intents in separate transactions without deriving state under the writer lock allowed both instances to invoke their callbacks. The Store now makes admission and intent append one transaction; the next instance sees the first unresolved intent or the resulting durable state and is rejected before its callback.

## Affected contracts and paths

S2 E7 / VST-016 to VST-019; `tools/vst/store.py`, `tools/vst/supervisor.py`, S2 worker plan. No migration or schema change.

## Verification state

No tests, checks, builds, CI, migrations, or runtime probes were run. The two-instance concurrent-start regression case is assigned to the E2E test agent. The earlier accidental `git diff --cached --check` is documented only in change record 0047.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation engineer (`gpt-6-luna`).
- Test owner: designated E2E test agent.
- Next: prove with two Store/Supervisor instances that only one start callback runs; then run the lifecycle regression set and request independent reliability review on the exact head.

Agent-Attribution: implementation-engineer (`gpt-6-luna`); Codex executor
