# 0278 S4 root-proof nonce validation

**Date:** 2026-10-25  
**Executor:** Codex  
**Baseline HEAD:** `3916101c7b38f8aa6182c685dcedbf0f9ad014ed`

## What changed

Defined the missing lowercase SHA-256 hex pattern `_HEX64` in `tools/qa/run.py`, which the root
preflight already uses to validate a 64-character run nonce.

## Why

The first focused run at exact HEAD `3916101` exposed a `NameError` before the root proof could be
validated. This was a real runtime defect in the new root-harness branch. The functional-test
reviewer also found one test-oracle issue: the artifact-corruption fixture wrote fewer bytes than
the recorded range, so the validator correctly reported an out-of-bounds range instead of a digest
mismatch. That test-source correction is documented separately in change 0279; the implementation
and fixture are committed together as one focused remediation because the first test run exposed
both defects.

## Verification state

- **Run:** `3916101c7b38f8aa6182c685dcedbf0f9ad014ed`, Windows CPython 3.14.3, pytest 9.0.3,
  locked external dependency target.
- **Command:**
  `C:\Python314\python.exe -c "import sys; sys.path.insert(0, r'D:\Temp\virtual_scrum_team_qa_f4ef8e7'); import pytest; print('pytest=' + pytest.__version__); raise SystemExit(pytest.main(['-v', 'tests/qa/test_s4_functional_runtime_matrix.py']))"`
- **Result:** 29 collected, 25 passed, 4 failed in 9.68 seconds. Three parametrizations failed
  with `NameError: name '_HEX64' is not defined` at `tools/qa/run.py:497`. The fourth failed because
  the test expected a digest-mismatch message after truncating the artifact; actual response was
  the correct `range extends beyond the artifact` rejection.
- No source changes were made by the test agent during that run. It stopped after the failure and
  will correct only the fixture before the next run.
- No broad tests, WSL runner execution, build, CI, migration, push, PR, or merge was run.
- The pre-existing untracked S2 evidence file remains preserved.

## Next step

Regenerate the registry from the corrected committed test source and rerun the focused suite at the
resulting exact HEAD. Do not start the full Windows/WSL matrix until focused contract tests pass.
