# Change 0472: Correct S2 runner gate and reconciliation authority

Date: 2026-10-28  
Sprint: S2  
Branch: `s4-canonical-continuation`  
Base HEAD: `2da827be982d3f2d6f2adf152668af6ff8007f21`  
State: source and focused tests implemented; fresh specialist review and exact-head GPT-PM approval pending.

## Why

Fresh database and silent-failure reviews found three defects in the persistent runner path. Gate evaluation could use an older passing receipt while a later execution claim remained unresolved. One `AUTHORITY_CHANGED_BEFORE_COMPLETION` event did not record its actual `EXECUTION_RESERVED` predecessor, so the signed reconciliation did not fully bind the state being resolved. Finally, an exception thrown by the post-reservation daemon-boundary callback could escape before the execution authority marked the reservation confirmed, allowing the service to treat the failure as an ordinary refusal instead of fail-stopping that generation.

## Changes

- `tools/vst/store.py`: `evaluate_gate()` now checks the append-only runner-claim lifecycle in the same SQLite read snapshot as the receipt chain. Unresolved states fail closed even when an earlier receipt is `PASS`; only a complete claim, a justified predecessor-generation pre-spawn `PENDING`, or a valid signed safe reconciliation can proceed to ordinary gate evaluation.
- `tools/vst/store.py`: authority-changed completion records `predecessor_state=EXECUTION_RESERVED`. The reconciliation verifier enforces the closed predecessor/outcome matrix: `NO_EXECUTION_PROVEN` only for `PENDING`, `EFFECTS_RESOLVED` only for `EXECUTION_RESERVED`, and non-continuing outcomes only for a recognized predecessor state. The signed record and event must match that exact state.
- `tools/vst/execution_grant.py`: after the exact durable `EXECUTION_RESERVED` response is validated, reservation confirmation is recorded before the post-reservation boundary callback. Any exception from that callback now enters the existing reserved-but-not-complete fail-stop behavior.
- No scheduler, CLI, spool, new assignment authority, IPC operation, database migration, or runtime installation was added.

## Verification

The assigned `functional-test-reviewer` added direct regressions and ran four approved groups against the working source/test diff based on base HEAD `2da827be...`:

- Persistent runner: 46 passed.
- E1 contract: 32 passed.
- E2 runner authority: 38 passed.
- E6 DiffGate: 22 passed.
- Total: 138 passed, 0 failed, 0 skipped. One installed `pytest_asyncio` deprecation warning was emitted per group.

Exact commands, SHA-256 fingerprints, acceptance mapping, and run limitations are recorded in `docs/sdlc/evidence/s2-final-gate-authority-regressions-20261028.md`. The test run used in-memory Store instances and fake authority callbacks. It does not prove live service framing, daemon/systemd generation restart, Windows/WSL containment, or production coordinator integration. The full suite, restricted selectors, checks, build, CI, migrations, provisioning, and runtime were not run.

## Remaining S2 acceptance

`S2-DISPATCH-M01` remains MAJOR/OPEN: this repository has no production coordinator callsite and no approved new assignment path. The existing reconciliation method is in-process only; the deployed service dispatch and role allowlist do not expose a reconciliation operation. Fresh specialist reviews and a new exact-head GPT-PM sweep are pending. E5 still needs the required operator-root-signed inventory/attestation; it must not be fabricated. Keep prohibited process, crash/recovery, mutation, E8, and policy selectors `NOT_RUN`. S2 is not approved; do not start S3, push, or open a PR before the remaining authorized acceptance and exact-head gate.

## Ownership

- Codex: bounded source correction, evidence reconciliation, and discovery of an existing in-scope production integration.
- `functional-test-reviewer`: focused functional test authorship and execution.
- Specialist reviewer agents: fresh exact-diff review after the source and test commit is frozen.
- GPT-PM: architecture and exact-head approval.
- Operator: any required signed attestation or host action that requires operator authority.