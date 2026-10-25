# 0283 S4 focused test fixture corrections

**Date:** 2026-10-25  
**Executor:** Codex coordinating the functional-test reviewer  
**Failed-run HEAD:** `7cc903b17bb651710ee1a91c5c1fb61949353eb3`

## What changed

- Updated four `ValidatedRegistry` test fixtures with the current profile-partition fields.
- Passed the required runtime profile into the interpreter-selection test and supplied explicit absent proof/nonce values in unprivileged runner fixtures.
- Added the parent network-namespace inode to the schema-v4 root-proof matrix fixture.
- Made root-helper test doubles portable on Windows Python while retaining their POSIX-path and mount-boundary assertions.

Only the three assigned test modules changed: `test_s4_functional_runner_contracts.py`, `test_s4_functional_runtime_matrix.py`, and `test_s4_functional_root_harness.py`. Product code and the pre-existing S2 evidence file were not changed.

## Why

The focused exact-head run exposed stale fixture shapes and host assumptions rather than a demonstrated product defect. Keeping the contract assertions while making the doubles host-portable allows the designated Windows focused run to exercise the intended checks.

## Verification state

- At `7cc903b17bb651710ee1a91c5c1fb61949353eb3`, command `C:\Python314\python.exe -m pytest tests/qa/test_s4_functional_runner_contracts.py tests/qa/test_s4_functional_runtime_matrix.py tests/qa/test_s4_functional_root_harness.py -q --tb=short` returned 87 passed, 21 failed, 1 warning (exit 1).
- Failure groups: four missing `ValidatedRegistry` profile maps; one outdated interpreter-profile call; two runner `Namespace` fixtures missing explicit proof/nonce values; one schema-v4 root matrix proof fixture; six missing Unix `geteuid` mocks; three Python 3.14 argparse flag mocks; one Windows path expectation; three empty mountinfo fixtures. These are test fixture failures; no product source was changed in response.
- The test-only corrections are unverified. No tests were rerun, no registry was regenerated, and no root helper was installed in this change.
- Documentation registry command: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (259 lines). This is documentation-index generation only.

## Next step

Commit the corrected test sources, refresh the selector registry for their new exact source commit, then rerun these three modules through `functional-test-reviewer` at the resulting exact HEAD. Preserve all policy `NOT_RUN` rows.
