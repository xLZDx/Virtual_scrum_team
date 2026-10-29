# Change 0501 — Record S2 safe synthetic helper run after Store cleanup fix

Date: 2026-10-28

## What changed and why

Recorded the focused test result at the exact revision that includes the Store cleanup boundary
and its failure-injection regression. The prior five-test run at `e59c2e9` is linked as historical
evidence because it predates this resource-lifecycle fix; the current file contains six cases.

## Affected paths and contracts

- Evidence: `docs/sdlc/evidence/s2-e8-safe-synthetic-run-d70bbe2-20261028.md`.
- Implementation under test: `tools/vst/slice.py::run_lifecycle_scenarios`.
- Tests under test: `tests/vst/test_s2_e8_synthetic_lifecycle.py`.
- Scope: safe synthetic report/candidate/budget behavior and Store cleanup after constructor
  failure; full E8 and system acceptance remain open.

## Verification state

- Exact command: `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`.
- Exact HEAD: `d70bbe2de787e0a209ba8d1f78072eb70dda32a9`.
- Result: 6 passed, 0 failed, 0 skipped; one pytest-asyncio deprecation warning.
- Exact selector list, environment, source/test hashes, fixture cleanup boundary, worktree status,
  and limitations are in the linked evidence file.
- Restricted process/crash, STOP, resume/restart, out-of-scope mutation, external egress, real
  sandbox, and operator candidate scenarios remain `NOT_RUN` or `NOT_ESTABLISHED`.

## Ownership and next step

Codex owns the evidence and repository record. The functional-test-reviewer authored the tests and
the e2e-runner executed the exact committed revision. GPT-PM owns the exact-head gate. The operator
owns the real sandbox, signed current-run E5, and candidate choice needed for actual E8 acceptance.
Next, complete relevant exact-diff reviews and keep S2 open until its independent runtime,
integration, and approval gates are satisfied.
