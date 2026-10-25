# 0247 S4 registry refresh after authored test corrections

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `d99be2478a85b8acf9ac09e775c12d763512d69a`

## What changed

- Regenerated `docs/qa/categories.json` after test-source corrections in `d99be24`, binding updated test selectors and source digests to committed provenance.
- Updated the S4 backlog rows to show authored tests and fixtures as committed while preserving runtime evidence as pending.
- Added the first exact-head QA runner attempt report under `docs/sdlc/evidence/qa/`.

## Why

The first native-category attempt correctly failed closed before test collection because the manifest's source digest did not match the corrected committed E2E source. Regeneration is required after every committed test-source edit so the registry cannot accept stale selectors.

## Evidence and verification

- Attempted command used the bounded QA runner at exact source HEAD `d99be2478a85b8acf9ac09e775c12d763512d69a`, category `functional`, approved Python 3.14.3, pytest target 9.0.3, isolated dependency target and a temporary exact-head test candidate.
- Result: `BLOCKED` before pytest launch; report `docs/sdlc/evidence/qa/functional.report.jsonl` records `RegistryError: test source changed after registry generation: tests/qa/test_s4_e2e_runner_cli.py`, `expected_test_ids=[]`, `command=[]`, `pytest_version=null`, and no test outcomes. No tests ran.
- Only the functional category was attempted. Other categories were not run because the same stale manifest check would block them before collection.
- The temporary candidate was created only for test execution, not development; no Git worktree was created. The canonical checkout retains the pre-existing untracked S2 evidence file untouched.

## Acceptance and next steps

- VST-032: manifest regeneration is committed; a clean exact-head run is still required.
- VST-034–037: test sources/fixtures are committed; runtime and seeded-observation evidence remain pending.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test executor: `e2e-runner`.
- Next: create a clean test-only candidate from the post-refresh exact commit and run all permitted QA categories through `tools.qa.run`. Preserve all policy-prohibited selectors as explicit `NOT_RUN`.
