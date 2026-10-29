# Change 0494 — Limit the S2 E8 helper to safe synthetic outcomes

Date: 2026-10-28

## What changed and why

The focused helper was reduced to a safe local candidate, receipt and budget flow. It no longer
executes child self-exit, process kill, STOP, crash/restart/resume, out-of-scope write, or egress
scenarios; every such outcome is reported as `NOT_RUN`. The worker only edits its declared path
inside the disposable repository. This preserves the active S2 restriction on process/crash and
mutation evidence while still exercising candidate hashing, receipt idempotency, and budget
rejection in local fixtures.

The helper always constructs its synthetic supervisor with the distinct operator key. A previous
focused attempt also found missing trusted context on a restarted supervisor, but the restart path
is now deliberately absent rather than repaired or executed.

## Affected paths and contracts

- `tools/vst/slice.py::run_lifecycle_scenarios` now runs only the safe synthetic flow and records
  restricted scenario statuses as `NOT_RUN`.
- `tests/vst/test_s2_e8_synthetic_lifecycle.py` asserts safe candidate/report fields and verifies
  restricted statuses remain unrun. Its temporary root is cleaned by `TemporaryDirectory`.
- `docs/S2_E8_SYNTHETIC_HARNESS_DESIGN_2026-10-28.md` defines the revised safe scope.
- Real sandbox placeholder selectors remain unchanged.

## Verification state

- Attempt at exact source HEAD `43c5d3d327f529674ca96a93669e5116147e1219` used
  `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`: 6 setup errors, 0 test bodies.
  The restarted synthetic `Supervisor` lacked required trusted run/probe context. The test source
  changed concurrently before execution, so this was not exact code-and-test-head evidence.
- Earlier setup failures are recorded in changes 0490–0492. All attempts stopped before test
  assertions and before restricted process/crash scenarios.
- No test has run against this revision. A focused exact-head `e2e-runner` execution is pending.

## Ownership and next step

Codex owns implementation and Git/evidence coordination. The functional-test-reviewer owns the
focused assertions; e2e-runner owns their exact-head execution. GPT-PM owns exact-head adjudication.
The operator owns actual sandbox/E5 evidence, worker choice, and any deletion of retained temporary
fixtures. A passing synthetic run does not close E8 or S2; keep S2 and production dispatch open
until their separate acceptance gates are satisfied.
