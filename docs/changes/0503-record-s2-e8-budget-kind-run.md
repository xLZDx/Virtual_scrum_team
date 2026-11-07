# Change 0503 — Record S2 safe synthetic run after budget error-kind fix

Date: 2026-10-28

## What changed and why

Recorded the focused helper tests at the exact revision containing the Store budget error-kind
fix. The prior six-test pass at `d70bbe2` remains historical evidence and is superseded for current
exact-source acceptance because the implementation and assertion now require the expected budget
error kind.

## Affected paths and contracts

- Evidence: `docs/sdlc/evidence/s2-e8-safe-synthetic-run-0c7c31d-20261028.md`.
- Implementation under test: `tools/vst/slice.py::run_lifecycle_scenarios`.
- Tests under test: `tests/vst/test_s2_e8_synthetic_lifecycle.py`.
- Scope: safe synthetic report/candidate/budget behavior and Store cleanup after constructor
  failure; full E8 and system acceptance remain open.

## Verification state

- Exact command: `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`.
- Exact HEAD: `0c7c31dc19181b80b6629d6ba0b13b1112eaf6a4`.
- Result: 6 passed, 0 failed, 0 skipped; one pytest-asyncio deprecation warning.
- Exact selectors, environment, source/test hashes, fixture cleanup boundary, worktree status and
  limitations are in the linked evidence file.
- Restricted process/crash, STOP, resume/restart, out-of-scope mutation, external egress, real
  sandbox and operator candidate scenarios remain `NOT_RUN` or `NOT_ESTABLISHED`.

## Ownership and next step

Codex owns the evidence and repository record. The functional-test-reviewer authored the tests and
the e2e-runner executed this exact committed revision. GPT-PM owns the exact-head gate. The operator
owns the real sandbox, signed current-run E5 and candidate choice needed for actual E8 acceptance.
Next, complete relevant exact-diff reviews and keep S2 open until independent runtime, integration
and approval gates are met.
