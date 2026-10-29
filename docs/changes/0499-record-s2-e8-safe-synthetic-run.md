# Change 0499 — Record S2 safe synthetic helper run after workdir guard

Date: 2026-10-28

## What changed and why

Recorded the focused safe synthetic helper run at the exact revision that added the fail-closed
work-directory guard and explicit temporary parent/new-child fixture layout. The earlier successful
run at `05a443c` is linked as historical evidence and marked superseded for current exact-source
acceptance.

## Affected paths and contracts

- Evidence: `docs/sdlc/evidence/s2-e8-safe-synthetic-run-e59c2e9-20261028.md`.
- Implementation under test: `tools/vst/slice.py::run_lifecycle_scenarios`.
- Tests under test: `tests/vst/test_s2_e8_synthetic_lifecycle.py`.
- Scope: safe synthetic report/candidate/budget behavior only; real E8 and system acceptance remain
  open.

## Verification state

- Exact command: `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`.
- Exact HEAD: `e59c2e9c69f999bbf17e71e4472abf8298e34a07`.
- Result: 5 passed, 0 failed, 0 skipped; one pytest-asyncio deprecation warning.
- Exact selectors, environment, source/test hashes, fixture cleanup boundary, worktree status, and
  limitations are in the linked evidence file.
- Child process/crash, process-kill, STOP, resume/restart, out-of-scope mutation, external egress,
  real sandbox, and operator candidate scenarios remain `NOT_RUN` or `NOT_ESTABLISHED`.

## Ownership and next step

Codex owns the evidence and repository record. The functional-test-reviewer authored the tests and
the e2e-runner executed this exact revision. GPT-PM owns the exact-head gate. The operator owns the
real sandbox, signed current-run E5, and candidate choice needed for actual E8 acceptance. Next,
complete relevant exact-diff reviews and keep S2 open until its independent runtime, integration,
and approval gates are met.
