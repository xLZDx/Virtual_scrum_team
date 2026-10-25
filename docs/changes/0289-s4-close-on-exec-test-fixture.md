# 0289 S4 close-on-exec test fixture

**Date:** 2026-10-25  
**Executor:** Codex coordinating the functional-test reviewer  
**Failed-run HEAD:** `17096c74d0b9a71ca26298aa47d785949b51f4ce`

## What changed

- Added a test-local Linux-compatible `O_CLOEXEC` constant to the Windows-host root-helper test.
- Captured the mocked namespace open and asserted the exact `/proc/self/ns/net` path and `O_RDONLY | O_CLOEXEC` flags.

Only `tests/qa/test_s4_functional_root_harness.py` changed. Product code and the pre-existing S2 evidence file remain untouched.

## Why

The helper's outer launch path is Linux-specific and correctly uses `os.O_CLOEXEC`; the Windows host does not define that constant. The test double must model Linux's flag while preserving the assertion on production behavior.

## Verification state

- At exact HEAD `17096c74d0b9a71ca26298aa47d785949b51f4ce`, Python 3.14.3, the focused run returned 107 passed, 1 failed, 1 warning in 316.51 seconds (exit 1).
- Failure: `test_s4_root_harness_outer_preflights_candidate_then_reexecs_fixed_installed_helper` raised `AttributeError` because Windows Python lacks `os.O_CLOEXEC`.
- The fixture correction is unverified. No tests reran and no selector registry was regenerated for this test-source change.
- Documentation registry command: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (265 lines). This is documentation-index generation only.

## Next step

Commit the test-only correction, regenerate the selector registry for the exact source commit, then rerun the three focused modules through `functional-test-reviewer`.
