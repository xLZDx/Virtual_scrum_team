# 0253 S4 E2E baseline update for policy NOT_RUN fix

**Date:** 2026-10-25  
**Executor:** Codex  
**Test author:** `e2e-runner`, GPT-6 Luna, medium effort  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `f32c6e33b0289438a79f88328975c712b07aa881`

## What changed

- Updated the synthetic E2E source baseline to committed product head `f32c6e3`, which contains the policy `NOT_RUN` execution fix.
- No test behavior was weakened; the existing policy-inventory scenario continues to require the eligible selector to execute and the category to return `INCONCLUSIVE` only because of the explicit policy row.

## Why

The previous E2E baseline `fe256fc` predates the policy fix in `tools/qa/run.py`. Without updating the fixture baseline, E2E would continue testing old behavior and would not verify the product correction.

## Evidence and verification

- Test source change: one `BASELINE_HEAD` constant in `tests/qa/test_s4_e2e_runner_cli.py`, now `f32c6e33b0289438a79f88328975c712b07aa881`.
- The preceding exact-head functional run at `11e231f` passed (54 selectors, 109 concrete cases). Integration/API were blocked before execution due the pre-fix policy handling; their reports are in `docs/sdlc/evidence/qa/`.
- No tests were run after the baseline update. The category registry must be regenerated after this source commit before another run.
- All source development remains in the canonical checkout; no worktree was created. The pre-existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- VST-032: refresh the selector registry after this E2E source change.
- VST-035: E2E fixtures will archive the fixed policy behavior; exact-head category evidence remains pending.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test author/executor: `e2e-runner`.
- Next: commit the baseline update, regenerate and commit the category manifest, then rerun all six categories at the new exact commit.
