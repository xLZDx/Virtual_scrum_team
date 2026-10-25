# 0285 S4 remaining focused-test fixture corrections

**Date:** 2026-10-25  
**Executor:** Codex coordinating the functional-test reviewer  
**Failed-run HEAD:** `0b28d1f8ec56fe4b4e4e7c870596d781fe149636`

## What changed

- Updated the blocked-run test to assert the current runtime-profile rejection reason.
- Added the candidate root-helper source file to the synthetic repository used by the outer helper test, allowing the intended helper-hash contract to execute.
- Updated the `setpriv` executable expectation to the fixed `/usr/bin/setpriv` path.

Only `test_s4_functional_runner_contracts.py` and `test_s4_functional_root_harness.py` changed. Product code and the pre-existing S2 evidence file remain untouched.

## Why

The second focused run found three stale assertions/fixtures after the earlier test-only repairs. The failures did not demonstrate a product runtime defect; the tests needed to represent the current contract and a complete synthetic candidate.

## Verification state

- At `0b28d1f8ec56fe4b4e4e7c870596d781fe149636`, Python 3.14.3, Windows, command `C:\Python314\python.exe -m pytest tests/qa/test_s4_functional_runner_contracts.py tests/qa/test_s4_functional_runtime_matrix.py tests/qa/test_s4_functional_root_harness.py -q --tb=short` returned 105 passed, 3 failed, 1 warning in 227.11 seconds (exit 1).
- Warning: `pytest_asyncio` reports deprecated `asyncio.get_event_loop_policy` usage in the real committed selector denominator test; slated for removal in Python 3.16.
- The three corrections are unverified. No product code changed, no registry was regenerated, and no helper was installed in this change.
- Documentation registry command: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (261 lines). This is documentation-index generation only.

## Next step

Commit these test corrections, regenerate the category registry from the new exact source HEAD, then rerun all three focused modules through `functional-test-reviewer`. Preserve all policy `NOT_RUN` selectors.
