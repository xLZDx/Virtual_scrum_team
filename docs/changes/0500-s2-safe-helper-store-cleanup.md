# Change 0500 — Close the synthetic Store if supervisor setup fails

Date: 2026-10-28

## What changed and why

Python review of the fresh-workdir version found that `SliceFixture` opened its SQLite Store before
the helper's `try/finally`, while the helper constructed `Supervisor` before entering that block.
If supervisor construction raised, the Store could remain open during temporary-directory
cleanup. The existing `try/finally` now begins before `Supervisor` construction so `fixture.close()`
runs for that setup failure as well as later failures.

## Affected paths and contracts

- `tools/vst/slice.py::run_lifecycle_scenarios` moves trusted `Supervisor` setup inside the Store
  cleanup boundary.
- `tests/vst/test_s2_e8_synthetic_lifecycle.py` adds a failure-injection test that verifies the
  original setup error propagates and the captured SQLite connection is closed.
- The failure injection does not execute process/crash, STOP, resume/restart, mutation, egress, or
  real sandbox scenarios.

## Verification state

- The previous exact run at `e59c2e9c69f999bbf17e71e4472abf8298e34a07` passed 5 tests; its evidence
  is in `docs/sdlc/evidence/s2-e8-safe-synthetic-run-e59c2e9-20261028.md`. This source change
  invalidates it as current-head evidence.
- Python reviewer at that exact head raised the Store cleanup finding; security reviewer found no
  security findings. Both were read-only and ran no checks.
- The cleanup fix and added regression test have not yet been tested; focused `e2e-runner` execution
  and exact-head Python re-review are pending.

## Ownership and next step

Codex owns implementation, local Git and evidence coordination. The functional-test-reviewer owns
the cleanup regression assertion, e2e-runner owns its exact-head execution, and Python reviewer
owns the targeted recheck. GPT-PM owns exact-head adjudication. The operator owns actual sandbox/E5
evidence and any deletion of old retained pytest roots. Keep S2 and E8 open until their separate
system and integration gates are met.
