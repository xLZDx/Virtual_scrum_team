# 0254 S4 E2E source registry refresh

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `653d10c862198fe946eb362ff78cba2fedcae925`

## What changed

- Regenerated `docs/qa/categories.json` after the E2E fixture baseline source change in `653d10c`.
- Updated the backlog, S4 plan and current state to record that the manifest now includes committed test-source provenance while runtime confirmation of the policy fix remains pending.

## Why

The category registry binds test selectors to committed content. The E2E test source now points synthetic candidates at product runner commit `f32c6e3`; this source change must be committed and included in the manifest before exact-head testing.

## Evidence and verification

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`.
- Prior exact-head evidence at `11e231f`: functional `PASS` (54 selectors, 109 concrete cases); integration and API `BLOCKED` before execution by policy `NOT_RUN` preflight. Those reports are preserved under `docs/sdlc/evidence/qa/`.
- The policy execution fix is committed in `f32c6e3`, and the E2E test source baseline is committed in `653d10c`. **No tests were run after these changes.**
- The pre-existing untracked S2 evidence file remains untouched; no worktree or development clone was created.

## Acceptance and next steps

- VST-032: committed registry now covers the E2E baseline source change.
- VST-033–037: full exact-head runtime results, seeded observations, reviews and gate receipt remain pending.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test executor: `e2e-runner`.
- Next: run all six supported categories via `tools.qa.run` against the post-refresh exact commit. Keep policy-prohibited test IDs in the report as `NOT_RUN` and confirm eligible tests execute.
