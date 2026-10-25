# 0282 S4 test-selector registry refresh

**Date:** 2026-10-25  
**Executor:** Codex  
**Test source HEAD:** `d77d7ccce1f98bffb07642d4619dcd2b96d5a3aa`

## What changed

- Regenerated `docs/qa/categories.json` from the committed S4 functional-test sources, including the 16 new contract selectors in change 0281.
- Updated S4 state and backlog records with the refreshed test denominator and exact source HEAD.
- Preserved the 51 policy `NOT_RUN` rows without changing their reasons or approval state.

## Why

The test-selector registry must describe exact committed sources before any test agent executes them. Change 0281 added test selectors, so the previously committed registry was stale.

## Verification state

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`.
- The generator completed and wrote the registry with source HEAD `d77d7cc`.
- Inventory: 935 regression selectors; 884 assigned runnable; 51 policy `NOT_RUN`; functional category contains 90 selectors, including 16 new contracts.
- This is registry generation evidence only. No product test or check was run.
- Documentation registry command: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (258 lines). This is documentation-index generation only.

## Next step

Commit the registry refresh and record, then have `functional-test-reviewer` run the focused S4 contract modules at the exact resulting HEAD. Preserve all policy `NOT_RUN` selectors.
