# 0307 S4 selector registry after NOT_RUN fixture fix

**Date:** 2026-10-25  
**Executor:** Codex  
**Source HEAD:** `26b959f53e8398b7b4b736b66e4c5a406369705b`

## What changed

Regenerated `docs/qa/categories.json` after change 0306 committed the synthetic E2E fixture baseline update.

## Why

The selector registry records test-source identities and must follow every committed test-source change before exact-head execution. The refresh now includes the fixture that pins the category-wide `NOT_RUN` contract test to a runner containing the correction.

## Evidence and verification state

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`
- Result: exit code `0`; registry source HEAD `26b959f53e8398b7b4b736b66e4c5a406369705b`.
- Inventory: 935 primary regression selectors, 883 runnable and 52 policy `NOT_RUN`, plus 3 separate seeded-failure selectors. Category runnable counts are functional 90, integration 84, API 705 and E2E 56.
- This is registry generation, not runtime verification. The corrected safe focused WSL contract and focused Windows suite remain to be run by designated test agents.
- Preserve every policy exclusion. Do not run the underlying sandbox-dependent selector, timeout, process-kill/death or mutation scenarios.

## Next

This registry refresh and its decision/lessons entries were committed at `05b1845`. Designated agents reran focused Windows and WSL contracts and all assigned Windows/WSL/root categories at that exact candidate; change 0308 records the valid 15-reference matrix, which remains non-approving because of 52 policy `NOT_RUN` selectors.
