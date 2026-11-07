# Change 0489 — Design bounded S2 E8 synthetic harness work

Date: 2026-10-28

## What and why

Recorded the bounded implementation scope for the existing but uncalled E8 synthetic lifecycle
helper. The S2 plan requires real E5/E6/S1 sandbox execution and an operator worker choice, which
are unavailable; this design covers only locally reproducible synthetic scenario evidence and
explicitly prevents it from being called E8 acceptance.

## Affected contracts and paths

- Design: `docs/S2_E8_SYNTHETIC_HARNESS_DESIGN_2026-10-28.md`.
- Existing helper: `tools/vst/slice.py::run_lifecycle_scenarios`.
- Existing real-sandbox placeholders remain in `tests/vst/test_s2_sandbox_probe.py` and stay
  `NOT_RUN`.

## Decision

Extend the existing helper with explicit synthetic results for its local crash/STOP/resume/budget
flow and an out-of-scope-write rejection. Label the report as synthetic; do not simulate or claim
real egress, real E5, external-candidate comparison, production isolation or operator choice.

## Verification state

- Read the S2 E8 acceptance plan, the helper and the placeholder tests.
- `code-architect` completed a read-only review and found no architecture blocker for this narrow
  synthetic-only scope; it specifically warned that child self-exit is not real process-kill
  containment and that `supervisor.stop` must not be called a distinct STOP-injection scenario.
- No source or test files changed; no tests/checks were run for this design note.
- S2 remains NOT APPROVED and S3 remains unstarted.

## Ownership and next step

Codex owns implementation. `functional-test-reviewer` authors coverage and `e2e-runner` executes it
after coding. GPT-PM retains exact-head adjudication; the operator retains the real E5/sandbox and
candidate decisions.
