# 0288 S4 selector registry after traceback-mock correction

**Date:** 2026-10-25  
**Executor:** Codex  
**Test source HEAD:** `24ba10dd341f8bc9a99dd8f303f760f83fb8aef6`

## What changed

- Regenerated `docs/qa/categories.json` from the committed tests after change 0287.
- Updated the S4 backlog/state with the source-bound registry inventory and next focused-run step.

## Verification state

- `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write` exited 0.
- Registry source HEAD: `24ba10dd341f8bc9a99dd8f303f760f83fb8aef6`; regression: 884 runnable plus 51 policy `NOT_RUN` (935 total); functional: 90 selectors.
- The previous focused run at `85f8a9d` ended with pytest `INTERNALERROR` after 93 passed and 2 warnings; the underlying failure remains unknown. The new test mock field has not been verified.
- `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (264 lines). This is documentation-index generation only.

## Next step

Commit this registry refresh, then rerun the three focused S4 modules through `functional-test-reviewer` at the resulting exact HEAD.
