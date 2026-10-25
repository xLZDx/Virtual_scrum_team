# 0290 S4 selector registry after Linux flag fixture

**Date:** 2026-10-25  
**Executor:** Codex  
**Test source HEAD:** `c4f9cb9a10f2a1ed4404c5b9277fb26c27a77209`

## What changed

- Regenerated `docs/qa/categories.json` from committed test source change 0289.
- Updated S4 inventory and next-run records while preserving the policy `NOT_RUN` rows.

## Verification state

- `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write` exited 0 and wrote the selector registry.
- Inventory: 935 regression selectors, 884 assigned runnable, 51 policy `NOT_RUN`, and 90 functional selectors.
- The latest focused run at `17096c7` returned 107 passed, 1 failed, 1 warning; test fixture change 0289 has not been executed.
- `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (266 lines). This is documentation-index generation only.

## Next step

Commit this selector-registry refresh, then rerun all three focused S4 modules through `functional-test-reviewer` at exact HEAD. Preserve all policy `NOT_RUN` selectors.
