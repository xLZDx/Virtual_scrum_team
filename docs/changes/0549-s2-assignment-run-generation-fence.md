# Change 0549: Fence S2 assignment handoffs to the active run and generation

## State

Implemented as a bounded source correction. Tests and checks remain NOT_RUN; the designated
functional-test reviewer owns adapting the red source fixture and validating the stale-run and
stale-generation cases.

## Why

The assignment-basis response reports the currently observed service generation. Without a
generation recorded in the durable handoff, an old assignment/probe could be observed again by a
new service generation and appear current. The Supervisor's trusted run identity must also match
the run bound into the handoff.

## Change

- Added required service_generation to the exact authenticated handoff schema and validate it as
  a canonical identifier. No legacy handoff shape is upgraded.
- Supervisor.assignment_basis() now requires its configured run identity and passes both that
  identity and the currently resolved service generation to the Store.
- Store.authenticated_assignment_basis() compares the handoff run ID and recorded generation to
  those trusted current values inside the same read transaction that verifies the handoff, event
  chain, external anchor, consumed probe, live lease, and owner epoch.
- A mismatch fails closed; the response can no longer stamp a previous-generation handoff with the
  current generation.

## Verification

- Tests/checks: NOT_RUN; code is handed to the designated functional-test reviewer.
- Runtime acceptance: NOT_RUN.
- No assignment mutation, key, migration, or commit was added.
