# 0302 S4 selector registry after runtime-profile-aware assertions

**Date:** 2026-10-25  
**Executor:** Codex  
**Source HEAD:** `5cb61b2ba11192241f6c01465895daf22fdd5ef8`

## What changed

Regenerated `docs/qa/categories.json` after change 0301 modified the S4 E2E test source. The schema-v2 registry records source HEAD `5cb61b2ba11192241f6c01465895daf22fdd5ef8`.

## Verification state

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`
- Exit code: 0; the generator wrote the category registry.
- Inventory: 935 primary regression selectors, 883 assigned runnable and 52 policy `NOT_RUN`; categories contain 90 functional, 84 integration, 705 API and 56 E2E selectors. Three seeded-failure selectors remain a separate category.
- The timeout-recovery selector remains in the integration `not_run_reasons` map. It was not executed. Registry generation is not test evidence; no tests or runtime categories ran during this refresh.

## Next

Have `functional-test-reviewer` run the focused safe Windows E2E selectors and capture any blocked report's exact reasons while its temporary candidate still exists. Have the designated test role run the same safe selectors under WSL at an exact candidate. Start the complete assigned matrix only after the focused contracts pass, preserving all 52 policy exclusions as non-approving.
