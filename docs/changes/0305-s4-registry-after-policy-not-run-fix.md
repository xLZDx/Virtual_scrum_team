# 0305 S4 selector registry refresh after policy NOT_RUN correction

**Date:** 2026-10-25  
**Executor:** Codex  
**Source HEAD:** `fc20c9e31e1d4bb9bd9356921add66e14e5e230a`

## What changed

Regenerated `docs/qa/categories.json` after change 0304 committed the category-wide policy `NOT_RUN` handling in the runner and matrix validator, along with the restricted-root IPC fixture correction. The registry now binds its source inventory to the exact committed source HEAD.

## Why

The registry is derived from selector metadata and test source. Refreshing it after the source commit keeps its source identity and selector inventory consistent before new exact-head test evidence is collected.

## Evidence and verification state

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`
- Result: exit code `0`; output: `wrote docs/qa/categories.json`.
- Registry: schema version `2`; source HEAD `fc20c9e31e1d4bb9bd9356921add66e14e5e230a`; 935 primary regression selectors, 883 assigned runnable and 52 policy `NOT_RUN`; 3 seeded-failure selectors remain separate.
- Registry generation is inventory maintenance, not runtime verification. No tests or checks were run for this refresh.
- Do not run policy-excluded timeout, process-kill/death, mutation, or underlying sandbox-dependent selectors. The safe outer `NOT_RUN` contract is eligible for the designated test agent.

## Next

Commit this registry refresh with its decision and lessons entries. Then designated functional/E2E agents should run focused, policy-compliant exact-head scenarios before the complete assigned S4 matrix. Keep the matrix non-approving while policy exclusions remain.
