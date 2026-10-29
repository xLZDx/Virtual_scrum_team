# Change 0497 — Record current S2 safe synthetic helper run

Date: 2026-10-28

## What changed and why

Recorded the exact focused run after change 0496 clarified the synthetic verdict field name. The
new run binds the test output to the full current HEAD and preserves the earlier exact-head setup
failures as failed attempts, separate from acceptance evidence.

## Affected paths and contracts

- Evidence: `docs/sdlc/evidence/s2-e8-safe-synthetic-run-05a443c-20261028.md`.
- Implementation under test: `tools/vst/slice.py::run_lifecycle_scenarios`.
- Tests under test: `tests/vst/test_s2_e8_synthetic_lifecycle.py`.
- Scope: synthetic report labels and safe synthetic budget/candidate behavior only; full E8 and
  system acceptance remain open.

## Verification state

- Exact command: `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`.
- Exact HEAD: `05a443c76b6453c48a103aa136576ba487c80b44`.
- Result: 5 passed, 0 failed, 0 skipped; one pytest-asyncio deprecation warning.
- Exact selector list, Python/pytest versions, source/test SHA-256, earlier setup failures, worktree
  scope and limits are in the linked evidence file.
- Restricted process/crash, STOP, resume/restart, out-of-scope mutation, external egress, real
  sandbox and operator candidate scenarios remain `NOT_RUN` or `NOT_ESTABLISHED`.

## Ownership and next step

Codex owns the evidence and repository record. The functional-test-reviewer authored the focused
tests and e2e-runner executed the exact committed revision. GPT-PM owns the exact-head gate. The
operator owns the actual sandbox, signed current-run E5 and candidate choice needed for real E8.
Next, complete relevant exact-diff review while keeping S2 open until its independent runtime,
integration and approval gates are satisfied.
