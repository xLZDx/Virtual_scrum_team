# 0257 S4 selector registry refresh

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `c80357e`

## What changed

- Regenerated `docs/qa/categories.json` after the committed selector contract tests in `c80357e`.
- Bound the E2E and functional test source hashes to their committed provenance and included the expanded E4 timeout/termination `NOT_RUN` policy rows.
- Updated current-state and backlog records to show test authorship and registry refresh complete while exact-head runtime evidence remains pending.

## Why

The S4 category manifest binds selector IDs and source hashes to committed test content. It must be regenerated after test-source edits and policy changes before the runner can validate and execute an exact candidate.

## Evidence and verification

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`.
- Source test commit: `c80357e`; product implementation commit: `7a0c8d4e33e8db3ddb141e66fb93becf2fb0a5e1`.
- No tests or checks were run for this registry refresh. All newly authored coverage remains unexecuted until the exact-head QA run.
- The pre-existing untracked S2 evidence file remains untouched. Development stayed in `D:\Repo\Virtual_scrum_team`; no worktree was created or used.

## Acceptance and next steps

- VST-032: committed manifest now contains the refreshed selector inventory and policy denominator.
- VST-033–036: exact-head functional, integration, API, E2E, regression, and seeded-failure evidence remains pending; platform skips and process-termination `NOT_RUN` remain non-passing.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Required QA execution owner: `e2e-runner`.
- Next: run the complete supported QA categories against a clean candidate at the resulting exact commit. Keep the six POSIX-dependent integration selectors and all process-termination selectors non-passing unless their actual supported environments permit them safely.
