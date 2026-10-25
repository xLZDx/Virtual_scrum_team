# 0184 — Correct S4 seeded tests after mapped exact-head execution

## What changed

Updated the pre-existing invalid-task-manifest seeded test to load the committed primary category and complete seeded catalog, then select its fixture by ID. It no longer narrows the category's test IDs to itself, which conflicted with the seven-fixture catalog. Corrected the stale-head fixture's current epoch to 2, matching the epoch on its valid signed receipts so the test reaches the intended stale-head rejection. Recomputed the canonical input hash. Updated category provenance for the seeded test source to the exact parent source head `126b67f3a969a067ac1643bebab2ac669a821eaa`. No product code changed.

## Why

The initial mapped run executed 27 selectors and reported 24 passed, 3 failed. One was an outdated synthetic catalog assumption; one seeded a receipt epoch mismatch before the expected stale-head condition; one attempted registry load reported an E2E source-head ancestry failure even though a direct `git merge-base --is-ancestor 452c8ea8da5545bdce0f584a6b51662b93a33abf HEAD` check at the same HEAD returned success. The latter is not treated as product defect and requires reproduction on rerun.

## Verification state

Exact command: PowerShell loaded the `functional`, `integration`, and `seeded-failure` `test_ids` arrays from `docs/qa/categories.json`, concatenated them, and invoked `python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin @ids`. Environment: Windows PowerShell, Python 3.14.3, repository HEAD `126b67f3a969a067ac1643bebab2ac669a821eaa`. Result: 24 passed, 3 failed in 82.62 seconds. Failures were the two corrected test mismatches and the unreproduced registry ancestry discrepancy. Affected selector set must be rerun after this correction commit.

## Decision and remaining scope

Keep product source unchanged. Preserve the integration and seeded selector denominators; do not edit E2E IDs. If registry provenance failure recurs, capture its exact environment and candidate-head calculation before considering any category change.

Executor: Codex
