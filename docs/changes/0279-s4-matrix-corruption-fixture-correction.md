# 0279 S4 matrix corruption fixture correction

**Date:** 2026-10-25  
**Executor:** Codex with `functional-test-reviewer` as test author  
**Baseline HEAD:** `3916101c7b38f8aa6182c685dcedbf0f9ad014ed`

## What changed

Changed the corruption fixture in `tests/qa/test_s4_functional_runtime_matrix.py` to replace the
captured bytes `b"PASS selector\n"` with same-length bytes `b"FAIL selector\n"`.

## Why

The focused run at this baseline reported that the tampered stdout was shorter than the recorded
range, so the validator correctly rejected an out-of-bounds range before reaching the intended
digest-mismatch assertion. Using a same-length replacement keeps the range valid and makes the
fixture target the digest-integrity failure path.

## Verification state

- The prior run at exact HEAD `3916101c7b38f8aa6182c685dcedbf0f9ad014ed` collected 29 cases: 25
  passed and 4 failed. The failure in `test_s4_matrix_rejects_stale_candidate_and_corrupt_artifact_range` was only the fixture's
  expected reason mismatch; it asserted a digest mismatch although the shortened bytes caused a
  range-bounds error. The other three failures were `NameError: _HEX64 is not defined` in the root
  proof implementation at `tools/qa/run.py:497` and are recorded separately by the implementation
  owner.
- This fixture correction has **not** been rerun. It does not establish a pass.
- The test-author update changed no implementation source, dependency, WSL state, or execution.
  Companion implementation fix is documented in change 0278; both narrow fixes are grouped in one
  remediation commit.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved.

## Next step

The parent coordinator owns the implementation repair, manifest refresh after this test-source
change is committed, and a later focused rerun at a newly recorded exact HEAD.
