# Change 0502 — Report only the expected budget-blocked lease

Date: 2026-10-28

## What changed and why

Python review at the exact `d70bbe2` head found that the helper marked a new lease as blocked for
any `StoreError`. That could hide a different storage/lease failure behind a positive-looking
report. The handler now accepts only `StoreError.kind == "budget"` and re-raises all other errors.
The report field is named `new_lease_budget_rejected`, and the focused functional test asserts that
the expected budget reason was observed.

## Affected paths and contracts

- `tools/vst/slice.py::run_lifecycle_scenarios` narrows the exception boundary and clarifies the
  report field.
- `tests/vst/test_s2_e8_synthetic_lifecycle.py` asserts the expected blocked-lease result.
- No restricted process/crash, STOP, resume/restart, out-of-scope mutation, egress or real sandbox
  scenario is invoked.

## Verification state

- The prior exact run at `d70bbe2de787e0a209ba8d1f78072eb70dda32a9` passed 6/6, with one
  pytest-asyncio deprecation warning. Evidence: `docs/sdlc/evidence/s2-e8-safe-synthetic-run-d70bbe2-20261028.md`.
- Python review on that head raised this MINOR; security review found no findings. This source/test
  change invalidates `d70bbe2` as current-head evidence.
- The corrected revision has not yet been run or reviewed. A focused `e2e-runner` run and exact-head
  Python review are required.

## Ownership and next step

Codex owns implementation and evidence reconciliation. The functional-test-reviewer owns the
assertion, e2e-runner owns exact-head execution, Python reviewer owns the recheck, and GPT-PM owns
exact-head adjudication. The operator owns the real sandbox/E5 and worker choice required for E8.
Keep S2 and E8 open pending their independent system/integration gates.
