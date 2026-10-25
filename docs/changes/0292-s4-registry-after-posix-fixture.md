# 0292 S4 selector registry after POSIX path fixture

**Date:** 2026-10-25  
**Executor:** Codex  
**Test source HEAD:** `d1416dc271143d926075cc39467869257bcd9f51`

## What changed

- Regenerated `docs/qa/categories.json` from committed test source change 0291.
- Updated S4 state and backlog with the exact source head and follow-up test step.

## Verification state

- `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write` exited 0.
- Inventory: 935 regression selectors, 884 assigned runnable, 51 policy `NOT_RUN`, and 90 functional selectors.
- The latest focused run at `211b823` returned 107 passed, 1 failed, 1 warning due a Windows path separator mismatch; the test-only correction is in `d1416dc` and has not been rerun.
- The installed WSL helper hash/permissions are documented in change 0291; no helper execution occurred.
- `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (268 lines). This is documentation-index generation only.

## Next step

Commit this registry refresh, then rerun the focused modules through `functional-test-reviewer` at the exact resulting HEAD. Preserve policy `NOT_RUN` selectors.
