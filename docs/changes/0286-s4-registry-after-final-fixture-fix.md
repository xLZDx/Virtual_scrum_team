# 0286 S4 selector registry after final fixture correction

**Date:** 2026-10-25  
**Executor:** Codex  
**Test source HEAD:** `13dd6e1b2fb761e574d98c6658c80b0ac248ecfa`

## What changed

- Regenerated `docs/qa/categories.json` from the committed test sources in change 0285.
- Preserved the policy `NOT_RUN` rows and updated S4 state/backlog records.

## Verification state

- `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write` exited 0 and wrote the selector registry.
- The recorded inventory is 935 regression selectors, 884 assigned runnable and 51 policy `NOT_RUN`; functional contains 90 selectors.
- The latest test run remains 105 passed / 3 failed / 1 warning at `0b28d1f`, before change 0285. Registry generation does not verify the fixture corrections.
- Documentation registry command: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (262 lines). This is documentation-index generation only.

## Next step

Commit the selector registry refresh, then rerun the three focused S4 contract modules through `functional-test-reviewer` at the resulting exact HEAD. Preserve all 51 policy `NOT_RUN` selectors.
