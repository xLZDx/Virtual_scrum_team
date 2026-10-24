# Change record 0029: S2 plan, backlog and state refresh

## What changed
- Added `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`: sprint plan for S2 (trust roots and isolated worker sandbox) with goal, scope, entry criteria, eight epics (E1 reviewer key, E2 runner head and signing-key isolation, E3 external anchor, E4 POSIX and Job Object verification, E5 sandbox spec and probe, E6 diff gate and read-only reviewer, E7 STOP/idempotency/breaker/reconciliation, E8 worker bake-off), acceptance mechanism class per epic, Definition of Done, risks and out-of-scope.
- `core/BACKLOG.md`: VST-007 marked closed in effect and VST-008 partly done (exact-head rule enforced in `tools/vst/gate.py`; wording in the `sdlc-orchestrator` skill remains a small open sub-item), both dated 2026-10-24; added VST-009 to VST-020 (S2 items, planned) and VST-021 to VST-024 (operator-owned alignment items, open).
- `core/STATE.md`: the S1 section now states the current truth (code complete, four review rounds closed, focused test counts, zero-cost-cap fix committed, remaining gates, `origin/main` still `9b5b597`). The state-authority wording is unchanged.

## Why
Process rule v4 item 7 asks for next-sprint documentation to be prepared while the current sprint is tested; it was not done before. The backlog and state lines were reported stale in change record 0027.

## Affected paths
`docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`, `core/BACKLOG.md`, `core/STATE.md`, `docs/changes/0029-s2-plan-backlog-state-refresh.md`.

## Known staleness not changed
The blueprint roadmap table (section 10) names S2 "Planning router"; the baseline plan re-scoped S2 to the sandbox worker. The S2 plan notes this; the blueprint is left as is until S2 closes. `core/DECISION_LOG.md` and `core/LESSONS_LOG.md` entries and the document registry are handled by the coordinator.

## Verification state
Documentation only. No code and no tests changed or run. Test counts in `core/STATE.md` are copied from the decision log and the coordinator's instruction, not re-run.
