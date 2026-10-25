# 0261 S4 selector registry after contract corrections

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `b0beca3580b1e307d2ddc8c80fa9c4ad1d40c552`

## What changed

- Regenerated `docs/qa/categories.json` from committed test sources at `b0beca3` after the S4 first-run contract corrections.
- Updated S4 backlog and state to distinguish committed test corrections and regenerated selector inventory from runtime evidence, which remains pending.
- Recorded the exact generator invocation and the initial unsupported direct-script invocation.

## Why

The QA manifest pins selector IDs, category membership, and each test source's commit and SHA-256. It must match the corrected, committed test sources before another exact-head run can begin.

## Evidence and verification

- Test-contract correction commit: `b0beca3580b1e307d2ddc8c80fa9c4ad1d40c552` (`test: align S4 contracts with exact-head findings`).
- Successful registry generation: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`; output: `wrote docs/qa/categories.json`, exit code 0.
- An initial direct invocation, `C:\Python314\python.exe tools/qa/build_registry.py`, exited 1 with `ImportError: attempted relative import with no known parent package`; no manifest was written by that invocation. The module invocation above is the supported form, matching change 0257.
- No tests, checks, builds, CI, or migrations were run for this registry refresh. This step records source inventory only and does not establish behavioral acceptance.
- All development remains in `D:\Repo\Virtual_scrum_team`; no sprint worktree was created or used. The pre-existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- VST-032: corrected selectors and source hashes are regenerated in the manifest; this record and manifest still need their commit.
- VST-033–037: corrected tests and the updated registry still require the complete supported six-category exact-head run; the previous d1bd results remain the latest runtime evidence.
- Accountable task owner: operator under the delegated continuation. Executor: Codex. Required test author/executor roles: `functional-test-reviewer` and `e2e-runner`.
- Next: commit this registry refresh, then have `e2e-runner` run the complete supported six-category suite on the resulting exact clean head while preserving all policy `NOT_RUN` selectors and platform skips.
