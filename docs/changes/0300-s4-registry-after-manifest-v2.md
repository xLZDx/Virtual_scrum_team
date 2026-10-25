# 0300 S4 selector registry after synthetic manifest v2

**Date:** 2026-10-25  
**Executor:** Codex  
**Test source HEAD:** `2295bf4c19fb496eb12f8978946a620056b256b2`

## What changed

Regenerated `docs/qa/categories.json` after change 0299 updated the synthetic E2E manifest fixture to the current schema v2 contract.

## Verification state

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`
- Exit code: 0; generator wrote the category registry and bound it to exact source HEAD `2295bf4c19fb496eb12f8978946a620056b256b2`.
- Inventory: 935 regression selectors total, 883 assigned runnable and 52 policy `NOT_RUN`; functional has 90 selectors and E2E has 56. Three seeded-failure selectors remain separate from the regression aggregate.
- This is registry generation only. No tests or runtime categories ran during this refresh. The prohibited timeout recovery selector remains `NOT_RUN`.

## Next

Have `functional-test-reviewer` rerun focused Windows contracts, including only the safe E2E fixture selectors, at the exact committed head with this registry. Then have `e2e-runner` run the complete assigned Windows/WSL/restricted-root matrix at the same exact head. Preserve all 52 policy exclusions as non-approving.

The document index was regenerated after this record was added: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and indexed 256 Markdown documents. This is documentation inventory generation only.
