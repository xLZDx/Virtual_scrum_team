# 0270 S4 selector registry after final-status fix

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/source head:** `s4-reproducible-qa-automation` / `1012a5e15715777ea70fc63ef0c132e625eb7975`

## What changed

- Regenerated `docs/qa/categories.json` after committing the final-status runner fix and its targeted functional regression in `1012a5e`.
- Updated the S4 backlog, current state, decision history, and lessons to identify the new denominator and exact-head test requirement.
- Corrected a local documentation-script path-variable mistake before commit by restoring `core/BACKLOG.md` from HEAD and reapplying its intended S4 rows; no committed data was lost.

## Why

The functional regression adds a registered selector. The selector manifest must bind to the committed test source before the six-category exact-head run; the earlier `ac17bde` results remain baseline evidence and do not verify the fix.

## Evidence and verification

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`; exit 0, output `wrote docs/qa/categories.json`.
- Manifest `source_head`: `1012a5e15715777ea70fc63ef0c132e625eb7975`.
- Selector inventory: functional 59; integration 84 including 36 policy `NOT_RUN`; API 705 including 12 policy `NOT_RUN`; E2E 56 including 1 policy `NOT_RUN`; seeded-failure 3; regression 855 including 49 policy `NOT_RUN`.
- No product tests, checks, builds, CI, or migrations were run during this registry refresh. The focused regression result is recorded in change 0269; the full six-category post-fix run is pending a commit containing this refreshed registry.
- All development source and tests remain in `D:\Repo\Virtual_scrum_team`; no Git worktree was created or used.

## Acceptance and next steps

- VST-032: registry now includes the added functional and aggregate regression selector and binds it to `1012a5e`.
- VST-033–037: code fix and focused test exist, but the six-category exact-head results must be rerun after this manifest is committed. Platform skips and policy `NOT_RUN` remain non-passing.
- Accountable owner: operator under the delegated continuation. Executor: Codex. Full suite owner: e2e-runner; functional regression owner: functional-test-reviewer.
- Next: commit this registry refresh, run all six categories against that exact commit, review current evidence, then request the fresh GPT-PM gate. No push or merge until approval.
