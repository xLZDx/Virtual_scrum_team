# 0267 S4 selector registry after duplicate-event assertion correction

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / test correction `28e7c50c11fccd2acd7e2e59ea15ddeed0078ec6`

## What changed

- Regenerated `docs/qa/categories.json` after the duplicate-event expected-outcome correction in `28e7c50`.
- Updated S4 state and backlog to tie partial `6fd26c6` results to their correct acceptance status and identify the remaining exact-head rerun.

## Why

The test source hash changed in the duplicate-event assertion correction; the selector manifest must be regenerated before behavioral reruns.

## Evidence and verification

- Test correction source commit: `28e7c50c11fccd2acd7e2e59ea15ddeed0078ec6`.
- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`; output `wrote docs/qa/categories.json`, exit 0. The manifest `source_head` is the same full commit ID.
- Selector inventory: functional 58; integration 84 including 36 policy `NOT_RUN`; API 705 including 12 policy `NOT_RUN`; E2E 56 including 1 policy `NOT_RUN`; seeded-failure 3; regression 854 including 49 policy `NOT_RUN`.
- No tests/checks/build/CI/migrations ran during the registry refresh. The latest partial run was at `6fd26c6`: functional passed 58/58; integration had 84 pass, 0 fail, 6 skips; API had 1,492 pass, 0 fail, 5 skips; E2E had 58 pass and one duplicate-event test assertion failure. Policy `NOT_RUN` rows remain in integration/API/E2E; regression and seeded-failure were not run.
- The sole E2E failure was the test's expected outcome list; inner candidate evidence shows the runner failed closed on duplicate node IDs. The assertion correction is committed at `28e7c50` but not yet rerun.
- All development remains in `D:\Repo\Virtual_scrum_team`; no sprint worktree was created or used. The existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- VST-032: the regenerated selector manifest binds to source commit `28e7c50`; this change records and commits it.
- VST-033–037: exact-head behavioral acceptance after the correction remains pending; platform skips and policy `NOT_RUN` rows are not passes.
- Accountable task owner: operator under the delegated continuation. Executor: Codex. Test roles: `functional-test-reviewer` and `e2e-runner`.
- Next: run the full supported six-category set at the exact commit containing this manifest. If all assertions pass, retain the category results and proceed to specialist review; keep prohibited timeout/process-kill scenarios `NOT_RUN`.
