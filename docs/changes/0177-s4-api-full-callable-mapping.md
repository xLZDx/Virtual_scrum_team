# 0177 — Map all source-defined Python API entrypoints

## What changed

`docs/qa/python_api_inventory.md` now maps all 79 source-defined non-private names across S4.3.2's five accepted modules to 57 distinct API-primary pytest selectors. `docs/qa/categories.json` adds every selector needed for that mapping, retains the existing QA registry/provenance/path/seeded-catalog selectors, and marks API `coverage_state` as `COMPLETE`. The API category now contains 73 unique selectors; seeded-failure remains its separate primary category with one fixture selector. The API and seeded IDs are checked against other categories for conflicts before this commit; no cross-category duplicate was found. API provenance points to the committed test-source HEAD `1a8d61aa3455b4e202a2d18b753063f362d85b24`.

Thirteen focused tests from change 0176 provide distinct API-primary falsifiers for the ten previously unreferenced entries and three whose existing selectors were already functional/E2E primary. Existing free selectors provide falsifying cases for the remaining inventory rows. The prior integration happy-path runner ID remains integration-primary; a distinct runner failure ID is API-primary. No product source changed.

## Why

AC-1 requires one primary category per test ID, while S4.3.2 and AC-2/AC-8 require a truthful native Python API lane for `contracts`, `gate`, `store`, `runner`, and `supervisor`. A complete source-derived inventory and disjoint selector projection make the API denominator auditable without relabeling functional/E2E work or claiming an absent HTTP route.

## Verification state

The complete 73-selector API category plus the one seeded-failure selector is not yet runtime-verified on this manifest commit. The next focused invocation must use the committed category IDs and report exact Python/pytest versions, HEAD, collected/pass/skip/fail counts, and the known Windows symlink privilege limitation. `COMPLETE` here means every inventoried callable has a mapped API-primary falsifier; it does not by itself mean the Windows run or report-bound S4 gate is approved.

## Remaining scope

API runtime evidence will be limited by any platform-specific skip (the registry symlink case previously returned WinError 1314 on Windows). Full regression aggregation, report-bound runner, signer socket, receipt and authoritative-gate acceptance remain separate S4 criteria. `network_api` remains explicitly `UNSUPPORTED`.
