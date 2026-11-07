# Change 0318 — Assign S2 containment evidence closure

## What changed

- Added accountable ownership and a conditional next action for the unrun Windows Job Object, full POSIX containment, and E8 crash/resume scenarios in `docs/sdlc/STATE.md`.
- Reconciled VST-013 with the same owner/executor split while preserving all three areas as `NOT_RUN` and preserving the unknown technical platform owner.

## Why

The S2 state identified a missing technical platform owner but did not name the accountable owner for the remaining evidence. The project operating rule assigns accountability to the operator, evidence preparation/coordination to Codex, and execution to the designated E2E role only after the applicable policy gate permits the scenario. This makes the closure path explicit without treating assignment as authorization or evidence.

## Evidence and scope

- Prior canonical change: `b5861fad792bfa31256007b47001302e19ff5e06` (`docs(s2): reconcile state and backlog`); S2 source/test evidence remains bound to the revisions listed in `docs/sdlc/STATE.md`.
- Existing S2 records identify Windows Job Object nesting and full E8 crash/resume as unrun; this change does not execute or authorize them.
- Documentation-only. No tests, checks, builds, runtime scenarios, or gate actions were run.

## Remaining acceptance and owners

- The operator owns any policy authorization needed to execute prohibited or platform-sensitive scenarios. Codex owns preparing the exact fixture and coordinating evidence. `e2e-runner` owns execution only after the gate permits it. The technical platform owner remains unknown in canonical records.

Change: 0318
Executor: Codex
