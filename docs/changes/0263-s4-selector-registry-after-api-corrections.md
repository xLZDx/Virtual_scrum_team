# 0263 S4 selector registry after API corrections

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / test correction `05f7ba442fb68afdec4fd17cb01f9e025295ae5f`

## What changed

- Regenerated `docs/qa/categories.json` after the schema-migration and fail-closed E4 test corrections in `05f7ba4`.
- Updated current state and S4 backlog with the corrected selector denominator and the exact 3558b14 partial runtime results.

## Why

The selector manifest pins committed source hashes and explicit policy `NOT_RUN` entries. The two test-source corrections changed the registry inventory, so a new exact-head run must consume a manifest bound to the corrected source commit.

## Evidence and verification

- Test correction source commit: `05f7ba442fb68afdec4fd17cb01f9e025295ae5f`.
- Successful generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`; output `wrote docs/qa/categories.json`, exit 0. The manifest `source_head` is the full test source commit above.
- Current committed selector inventory after the correction: functional 58; integration 84 selectors including 36 policy `NOT_RUN`; API 705 including 12 policy `NOT_RUN`; E2E 56 including 1 policy `NOT_RUN`; seeded-failure 3; regression 854 including 49 policy `NOT_RUN`.
- No tests/checks/build/CI/migrations ran during this registry refresh. The last partial runtime evidence remains candidate `3558b14a420a249d34f5d17309944b5c5a0d3f25`: functional 58/58 passed, integration 42/48 passed with 6 platform skips and 36 policy `NOT_RUN`, API 686/693 passed with 2 stale-test failures, 5 skips and 12 policy `NOT_RUN`. Those two stale-test assumptions are corrected in `05f7ba4`; the other categories were not run after the API failure.
- The partial functional/integration/API artifacts are retained in `docs/sdlc/evidence/qa/`; change 0262 records their source/destination SHA-256 values. The separate functional-test-reviewer run at the same source head passed 58/58 with 113 concrete cases; its duplicate artifacts remain in the disposable test candidate only.
- All development remains in `D:\Repo\Virtual_scrum_team`; no sprint worktree was created or used. The existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- VST-032: corrected selector inventory is regenerated from `05f7ba4`; this change records and commits the refreshed manifest.
- VST-033–037: no full run has occurred after the corrections. Preserve all policy `NOT_RUN` entries and platform skips as non-passing.
- Accountable task owner: operator under the delegated continuation. Executor: Codex. Runtime test owner: `e2e-runner`; functional test author/executor: `functional-test-reviewer`.
- Next: commit this manifest refresh and run the complete supported suite at the resulting exact clean head. Stop for code fixes if a real product defect appears; preserve failed evidence and do not weaken acceptance.
