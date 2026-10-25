# 0242 S4 category registry refresh

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `298b9a6d21a82520508688ad0bfd3ef29b97df72`

## What changed

- Regenerated `docs/qa/categories.json` from committed test sources using `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`.
- Added the E2E timeout selector to the generator's policy `NOT_RUN` inventory, with the explicit process-tree termination prohibition reason.
- Updated S4 plan and backlog state to identify committed test sources and the regenerated manifest while retaining runtime evidence as pending.

## Why

The selector registry records source commit and content identity. Test sources therefore had to be committed in 0241 before regeneration. The timeout scenario remains in the denominator with an explicit non-executable reason; it must never be invoked or counted as a pass.

## Evidence and verification

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`.
- Read-only manifest inspection reports primary inventory statuses/counts: functional 53 selectors; integration 84 with 36 `NOT_RUN`; API 705 with 2 `NOT_RUN`; E2E 55 with 1 `NOT_RUN`; seeded-failure 3; regression is an aggregate of 858 selectors with 39 `NOT_RUN` references.
- The timeout selector is present in the E2E inventory and has the reason `NOT_RUN: this scenario invokes process-tree termination; process-kill execution is prohibited for this S4 run.`
- No tests, checks, build, CI, process termination, or external call ran. This commit does not claim runtime acceptance.
- All development remains in `D:\Repo\Virtual_scrum_team`; no sprint worktree was created. The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.

## Acceptance mapping and next steps

- VST-032: regenerated committed registry is now bound to committed test sources; runtime coverage evidence remains pending.
- VST-034–036: focused functional/API, E2E, and seeded-failure tests and fixtures are registered; execution and observed outcomes remain pending.
- VST-037: final exact-head QA reports and VST gate receipt remain pending.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test execution owners: `functional-test-reviewer` for functional/API/seeded-failure scenarios and `e2e-runner` for E2E/CLI scenarios.
- Next: commit the registry refresh, then have the designated test agents execute permitted scenarios through the bounded runner against exact committed HEAD. Preserve explicit `NOT_RUN` for prohibited process-kill and incomplete S2/S3 acceptance cases.
