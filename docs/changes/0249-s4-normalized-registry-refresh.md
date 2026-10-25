# 0249 S4 normalized registry refresh

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `0d55c086930680994d99da06576fde025b96fa28`

## What changed

- Regenerated `docs/qa/categories.json` after the line-ending normalization and its new functional test were committed in `0d55c08`.
- Updated S4 backlog and current-state documentation to distinguish committed implementation/coverage from still-unverified runtime acceptance.

## Why

The previous manifest was generated before the line-ending contract test was committed. Registry generation must follow every test-source commit; the new normalized hash contract also needs to be represented in the exact candidate manifest.

## Evidence and verification

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`.
- The prior six-category attempt at exact HEAD `0122f063d173678e8285a9b0b956998ed7a44851` is preserved in `docs/sdlc/evidence/qa/`; each report is `BLOCKED` before pytest collection because the raw Windows working-copy digest differed from the committed LF source bytes. Expected/executed test counts are zero.
- The line-ending normalization code and functional test are committed at `0d55c08`; **no tests were run after this fix**. This registry commit does not claim runtime acceptance.
- The pre-existing untracked S2 evidence file remains untouched. All development remains in the canonical checkout; no worktree was created.

## Acceptance and next steps

- VST-032: normalized committed selector manifest is refreshed; exact-head category runtime remains pending.
- VST-033–037: runtime reports and seeded observations remain unverified until the next test-agent run.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test executor: `e2e-runner`.
- Next: execute all six supported QA categories on one clean test-only candidate at the resulting exact commit; preserve policy-prohibited selectors as `NOT_RUN`.
