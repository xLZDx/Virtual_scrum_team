# Change 0495 — Record safe S2 E8 synthetic helper test result

Date: 2026-10-28

## What changed and why

Recorded the exact focused test run for the safe synthetic helper and retained the three earlier
fixture-setup failures without presenting them as acceptance evidence. The final run passed after
the harness supplied required trusted context, emitted only the candidate hash, and left restricted
process/STOP/resume/mutation scenarios unrun.

## Affected paths and contracts

- Evidence: `docs/sdlc/evidence/s2-e8-safe-synthetic-run-23c4a67-20261028.md`.
- Implementation under test: `tools/vst/slice.py::run_lifecycle_scenarios`.
- Tests under test: `tests/vst/test_s2_e8_synthetic_lifecycle.py`.
- Scope: synthetic report labels and safe fixture behavior only; full E8 and system acceptance are
  still open.

## Verification state

- Exact command: `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`.
- Exact HEAD: `23c4a678358728fb7b65ceb84e2fe70a636f97ca`.
- Result: 5 passed, 0 failed, 0 skipped; one pytest-asyncio deprecation warning.
- Test and source SHA-256, environment, selector list, prior failed attempts, worktree scope and
  limitations are in the linked evidence file.
- Restricted process/crash, STOP, resume/restart, out-of-scope mutation, external egress, real
  sandbox, and operator candidate scenarios remain `NOT_RUN` or `NOT_ESTABLISHED`.

## Ownership and next step

Codex owns the evidence and repository record. The functional-test-reviewer authored the focused
tests and e2e-runner executed the exact committed revision. GPT-PM owns the exact-head gate. The
operator owns the actual sandbox, signed current-run E5, and candidate choice needed for real E8.
Next, perform relevant exact-diff reviews and keep S2 open until its independent runtime,
integration, and approval gates are satisfied.
