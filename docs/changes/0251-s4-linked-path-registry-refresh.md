# 0251 S4 linked-path selector registry refresh

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `d4464792633b5552cfa3c5bb2f4b6cb45ef03625`

## What changed

- Regenerated `docs/qa/categories.json` after the cross-platform linked-path test and selector rename were committed in `d446479`.
- Updated the backlog and S4 plan to show that the source fix is committed while runtime evidence remains pending.

## Why

The category manifest binds every selector to committed source hashes. The test selector changed from a file-symlink-only name to a cross-platform linked-path escape name; the registry must reflect that exact committed source before another run.

## Evidence and verification

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`.
- The prior Windows functional run at exact candidate HEAD `8eb8dbd38d196b1434b3fcb8d3f1a27eb7c54944` remains `FAIL` (108 passed, 1 required selector skipped); it is preserved in `docs/sdlc/evidence/qa/functional.report.jsonl`.
- The cross-platform junction/symlink correction is committed at `d446479`; **no tests were run after it**, and the refreshed manifest alone does not establish runtime acceptance.
- No worktree or development clone was created. The pre-existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- VST-032: selector registry refreshed to include the linked-path selector and committed provenance.
- VST-034: Windows junction/POSIX symlink contract test is committed; exact-head functional rerun is pending.
- VST-033, VST-035–037: category/runtime, seeded-observation, and VST gate evidence remain pending.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test executor: `e2e-runner`.
- Next: run all six supported categories through the bounded QA runner at the post-refresh exact head. A required skip must remain non-approving.
