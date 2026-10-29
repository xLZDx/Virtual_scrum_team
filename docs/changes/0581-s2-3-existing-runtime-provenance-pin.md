# S2-3: preserve target inventory identity in existing-runtime verification

## Task and review finding

- Sprint task: S2-3, continuation of the immutable non-secret runtime bundle and bounded WSL
  qualification preparation.
- Repository: `D:\Repo\Virtual_scrum_team`.
- Prior implementation commit: `f34cefd0827f631466e66b39a03b1d999c770388`.
- GPT-PM exact-head review request: `d4577012-d47b-4b43-b598-bfcbb8d064c9`; verdict `MODIFY`.
- Review summary: `docs/sdlc/evidence/s2-3-review-m-s2-3-03-d4577012.md`.
- GPT-PM confirmed the two earlier source-map and fresh-stage MAJOR findings were resolved, then
  identified M-S2-3-03: the existing-runtime branch referenced `inventory_sha` but the shell
  invocation did not pass/unpack it. Reusing an already-present matching runtime would therefore
  raise `NameError` before the intended schema-3 marker comparison.

## Correction

- `tools/qa/install_wsl_runner_runtime.sh` now passes the inventory digest between the plan digest
  and bundle root to the embedded Python verifier and unpacks it in that same order.
- `tests/vst/test_s2_stage_only_install.py` extracts and executes the actual existing-runtime
  validation block with disposable POSIX fixtures. It checks that a matching schema-3 marker is
  accepted and that mismatched inventory and source-head values are rejected. A separate assertion
  binds the shell invocation and Python tuple unpacking to the same argument order.
- No live WSL artifact, systemd unit, runtime selector, Store, key, E5, or dispatch path was used.

## Verification

- The product fix and initial regression are committed at `eb649d7a4b83549076b9076389315c3b34e31813`.
  The first exact-commit direct test attempt failed before the assertions because the test helper
  selected the wrong embedded shell heredoc; this test-extractor defect is corrected and tracked in
  `docs/changes/0582-s2-3-existing-runtime-test-extractor.md`. After that correction was committed,
  the designated `e2e-runner` executed the direct selection on HEAD
  `043980f64b4cc2ac7c42719251f2fb8258660377`: **4 passed, 8 deselected, 0 skipped** in Ubuntu
  24.04 WSL, Python 3.12.3, pytest 7.4.4. Inputs came from `git show` and pre/post SHA-256 checks
  matched. The exact run/hash record is
  `docs/sdlc/evidence/s2-3-existing-runtime-regression-043980f.md`. No result is inferred from the
  previous 54-case run, which was bound to the pre-f34 overlay and did not cover this branch.
- Static review by `code-reviewer` verified that both the marker-writer and existing-runtime
  verifier invocations pass and unpack `inventory_sha` in matching positions. This is not a test
  result or GPT-PM approval.
- GPT-PM's `MODIFY` disposition remains open until a focused exact-head re-review closes
  M-S2-3-03.

## Next actions

1. Submit a new GPT-PM review of committed HEAD `043980f`, focused only on M-S2-3-03 and the direct
   regression.
2. If approved, generate the exact source plan and fresh source-head-bound target inventory for
   the intended stage-only source revision.
3. Continue only after the exact package review; do not reopen the two resolved findings without
   contradictory evidence. Do not stage, select, activate services, or proceed to S2-4 until the exact package gates and
   fresh source-bound target inventory are satisfied.
