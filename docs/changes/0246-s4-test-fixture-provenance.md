# 0246 S4 test fixture provenance corrections

**Date:** 2026-10-25  
**Executor:** Codex  
**Test authors:** `functional-test-reviewer` and `e2e-runner`, GPT-6 Luna, medium effort  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `fe256fcceb6a9e1d02c8bee84db0561e1960e3d0`

## What changed

- Changed the registry functional test to create an existing but unreachable Git commit object for the non-ancestor case. The product code can now distinguish a normal non-ancestor result from Git failing to resolve an unknown object.
- Updated the E2E fixture source baseline to the committed CPython preflight fix `fe256fc`, so synthetic candidates include the current product correction.
- Kept seeded-fixture observation calls unconditional. Their acceptance evidence requires the S4 QA plugin; absence of the required observations must remain a non-approving runner result.

## Why

The first combined direct-pytest run at `0b73000` exposed a malformed non-ancestor fixture: forty zeroes were not an object in the synthetic repository, so Git correctly returned a query error. The E2E fixtures also archived a product baseline from before the CPython preflight fix. These test-source corrections align the fixtures with the contracts being tested without weakening product checks.

## Evidence and verification

- Test-agent run at `0b73000bb7eb2a0d25caa8364b066c64299abd85`: 11 failed, 51 passed, 2 skipped, 1 warning in 232.34 seconds. Seven E2E cases were preflight-blocked before pytest child execution; the CPython rejection was fixed in 0245 and synthetic Python cache hygiene in 0244.
- The source-head test failure was due to a nonexistent Git object; the updated fixture uses `git commit-tree` to make a valid, unreachable commit object.
- Three seeded tests failed when invoked by direct pytest because they deliberately require an active QA plugin. Their observation calls remain unconditional. The seeded category must be executed through `tools.qa.run`; a direct pytest run is not seeded-failure acceptance evidence.
- No tests were run after these test-source corrections. The process-tree timeout selector remains policy-skipped. No worktree/clone was created; the pre-existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- Registry ancestry test: now represents a valid non-ancestor Git object; rerun pending.
- E2E CLI: now packages the CPython preflight fix and ignores generated Python bytecode; exact-head rerun pending.
- Seeded-failure category: test assertions remain sound, but execution must include the QA plugin and full fixture-observation accounting.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test authors/executors: `functional-test-reviewer` and `e2e-runner`.
- Next: rerun focused functional/report tests directly, E2E tests through their synthetic candidates, and seeded-failure through the bounded QA runner on a clean exact-commit test candidate. Preserve the prohibited timeout row as `NOT_RUN`.
