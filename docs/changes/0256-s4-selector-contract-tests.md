# 0256 S4 selector contract tests

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `7a0c8d4e33e8db3ddb141e66fb93becf2fb0a5e1`

## What changed

- Added functional contract coverage for a 480-selector invocation across 24 source modules. It checks that pytest argv contains distinct source paths, remains bounded, and uses the schema-v2 expected/known selector file.
- Added plugin filtering coverage: expected selectors and unknown selectors remain selected; known other-category and policy `NOT_RUN` selectors are deselected.
- Added coverage that all 12 audited E4 timeout/termination selectors stay in API policy `NOT_RUN` inventory and its generated category inventory.
- Updated the E2E policy fixture to require module-path invocation, exact expected and `NOT_RUN` inventory, and execution/collection of only the eligible node.
- Added a regression that compares argv sizes for one and 1,000 registered selectors sharing one source module.
- Pinned the E2E fixture to the exact bounded-selector product commit `7a0c8d4e33e8db3ddb141e66fb93becf2fb0a5e1`.

## Why

The product fix changes the pytest selection boundary from per-selector command arguments to source modules plus a selector file. Tests must prove the argument size no longer scales with selector count and that category filtering preserves exact acceptance accounting, including prohibited selectors and unexpected items.

## Evidence and verification

- The test-source edits were authored by the designated `functional-test-reviewer` and `e2e-runner` agents in their assigned files. Both agents reported that they did not execute tests or checks.
- The E2E baseline commit was verified with `git rev-parse HEAD`: `7a0c8d4e33e8db3ddb141e66fb93becf2fb0a5e1`. An initial mistyped hash was corrected before commit; no test run used the typo.
- The category registry must be regenerated after these committed test sources so source hashes and selectors match.
- The pre-existing untracked S2 evidence file remains untouched. Development stayed in `D:\Repo\Virtual_scrum_team`; no worktree was created or used.

## Acceptance and next steps

- VST-032: new selector coverage is authored; manifest refresh remains pending.
- VST-033: argv/filter contracts are authored; execution remains pending.
- VST-034–036: test source is authored; full functional, API, E2E, regression, integration and seeded-failure runtime evidence remains pending.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test authors: `functional-test-reviewer` and `e2e-runner`; required execution owner: `e2e-runner`.
- Next: commit these test sources, regenerate the category registry on that exact source head, then run only the permitted QA selectors. Preserve all process-termination and unavailable-platform scenarios as non-passing `NOT_RUN` or skipped evidence.
