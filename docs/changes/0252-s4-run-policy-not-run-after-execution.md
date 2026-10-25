# 0252 S4 execute eligible selectors with policy NOT_RUN inventory

**Date:** 2026-10-25  
**Executor:** Codex  
**Implementation agent:** `implementation-engineer`, GPT-6 Luna, medium effort  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `11e231ffde78fda18f107d52c7964f6f23499ee3`

## What changed

- Removed the policy `NOT_RUN` reason from native-runner preflight so eligible selectors in a supported category can execute.
- Added the same reason after execution, preserving the category inventory and reporting `INCONCLUSIVE` only when policy `NOT_RUN` is the sole remaining limitation and all eligible tests pass cleanly.
- Preserved fail-closed behavior for dependency, dirty-source, collection, test, skip, xfail, output and artifact errors.

## Why

The S4 design keeps process-kill, process-death and incomplete sandbox selectors in the denominator as explicit `NOT_RUN`, while allowing available tests to run. The prior runner added a policy reason before launching pytest, causing `BLOCKED` with zero executed selectors for any category containing a policy row. Its post-run classification already intended `INCONCLUSIVE` when policy `NOT_RUN` was the only limitation, but could not be reached.

## Evidence and verification

- Exact candidate HEAD `11e231ffde78fda18f107d52c7964f6f23499ee3`: functional category `PASS`, Python 3.14.3 / pytest 9.0.3, 54 expected and passed selectors, 109 concrete nodes executed, 0 failed, 0 skipped, 0 policy `NOT_RUN`.
- At the same head, integration and API categories returned `BLOCKED` before child execution: integration had 48 eligible selectors and 36 policy `NOT_RUN` inventory rows; API had 703 eligible selectors and 2 policy `NOT_RUN` rows. Both reports show zero collected/executed tests. Evidence is preserved in `docs/sdlc/evidence/qa/`.
- The runner correction is limited to moving one policy reason from preflight to post-execution classification. **No tests were run after this change.**
- No prohibited selector, process kill, network call, CI/build, or worktree action occurred. The pre-existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- VST-033: policy `NOT_RUN` no longer preflight-blocks eligible tests; exact runtime confirmation is pending.
- VST-035: integration/API/E2E/regression categories must execute permitted selectors and remain `INCONCLUSIVE` only when the prohibited inventory rows are the sole limitation.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Implementation executor: `implementation-engineer`; test executor: `e2e-runner`.
- Next: update the E2E fixture baseline to this committed runner code, refresh the selector registry after that test-source edit, then run all six categories on the resulting exact head.
