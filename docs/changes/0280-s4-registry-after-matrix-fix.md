# 0280 S4 registry refresh after matrix test correction

**Date:** 2026-10-25  
**Executor:** Codex  
**Baseline HEAD:** `ce9624c`

## What changed

Regenerated `docs/qa/categories.json` after test-source commit `ce9624c` so the source inventory and
selector hashes include the equal-length artifact-corruption fixture correction. The schema-v2
registry continues to contain 919 regression selectors, 868 assigned runnable selectors, and 51
policy `NOT_RUN` selectors.

## Why

The prior manifest referenced the older test-source bytes from `1727776`. The corrected source must
be committed and bound by the manifest before the next exact-head run.

## Verification state

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`.
- Result: exit code 0; wrote `docs/qa/categories.json`.
- This is registry generation, not a product test or runtime proof.
- The focused suite at `3916101` remains 25 passed / 4 failed; no rerun at `ce9624c` has occurred.
- No broader suite, WSL runner, matrix, build, CI, migration, push, PR, or merge was run.
- The pre-existing untracked S2 evidence file remains preserved.

## Next step

Commit this registry refresh and its records, then rerun the focused module through the functional
test reviewer at the exact resulting HEAD.
