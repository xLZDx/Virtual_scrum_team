# 0265 S4 selector registry after E2E fixture fixes

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / test fix `363a4f42d7ff9a5e3418b5b107dd47bfd046c639`

## What changed

- Regenerated `docs/qa/categories.json` after the E2E fixture corrections committed in `363a4f4`.
- Updated current S4 state and backlog to show the manifest source binding and that the pre-correction exact-head E2E results are diagnostic, not final acceptance.

## Why

The E2E test source changed, so the hash-bound selector manifest must be regenerated before another exact-head suite can run.

## Evidence and verification

- Source commit: `363a4f42d7ff9a5e3418b5b107dd47bfd046c639`.
- Generator: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`; output `wrote docs/qa/categories.json`, exit 0. Manifest `source_head` equals the full source commit above.
- Inventory after the test-only correction: functional 58 (0 policy `NOT_RUN`); integration 84 (36 policy `NOT_RUN`); API 705 (12 policy `NOT_RUN`); E2E 56 (1 policy `NOT_RUN`); seeded-failure 3; regression 854 (49 policy `NOT_RUN`).
- No tests/checks/build/CI/migrations ran during this registry refresh. The latest prior partial exact run was at `e020823`; its E2E failures were isolated to test fixture/assertion assumptions in change 0264. Functional passed; integration and API remain non-approving due skips and `NOT_RUN`; regression and seeded-failure were not run.
- All development remains in `D:\Repo\Virtual_scrum_team`; no sprint worktree was created or used. The existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- VST-032: selector inventory is refreshed against `363a4f4`; this change commits the manifest and record.
- VST-033–037: exact-head behavioral acceptance after changes 0262 and 0264 remains open.
- Accountable task owner: operator under the delegated continuation. Executor: Codex. Test roles: `functional-test-reviewer` and `e2e-runner`.
- Next: run the complete supported six-category set at the exact commit containing this refresh. Preserve platform skips and policy `NOT_RUN` rows as non-passing and stop for any confirmed product defect.
