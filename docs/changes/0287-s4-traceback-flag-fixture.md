# 0287 S4 Python 3.14 traceback flag fixture

**Date:** 2026-10-25  
**Executor:** Codex coordinating the functional-test reviewer  
**Failed-run HEAD:** `85f8a9d9fbef8f6377500bfcd8aec5b7594039a0`

## What changed

- Added the Python 3.14 `sys.flags.verbose` field to the root-helper tests' isolated-mode mock so pytest can render tracebacks from failures without raising a secondary exception.

Only `tests/qa/test_s4_functional_root_harness.py` changed. Product code and the pre-existing S2 evidence file remain untouched.

## Why

The previous run reached 93 passed cases, then failed inside pytest's failure-reporting path because the test double did not model a field used by `traceback._compute_suggestion_error`. The internal error masked the original assertion failure.

## Verification state

- At exact HEAD `85f8a9d9fbef8f6377500bfcd8aec5b7594039a0`, Python 3.14.3, the three focused modules printed 93 passed and 2 warnings before pytest raised `INTERNALERROR`; exit code 1, elapsed 209.76 seconds. This is not a clean test total and does not identify the underlying failed assertion.
- The `verbose=0` mock correction is unverified. No tests were rerun and no selector registry was regenerated for this source change.
- Documentation registry command: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (263 lines). This is documentation-index generation only.

## Next step

Commit this test-only correction, regenerate the selector registry for the exact test source commit, then rerun all three focused modules through `functional-test-reviewer`. Record the underlying assertion failure if one remains.
