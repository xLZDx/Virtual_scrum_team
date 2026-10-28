# Change 0536: record S2 M03 cross-generation recovery focused test run

## Why

The 119/119 M03 run recorded at `a34c574` predates the historical replay operation and cannot
verify the recovery code or its new failure boundaries. The mapped selectors needed an exact-head
run after the source and test commits.

## What changed

- Added `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-test-run-20261029.md` with the
  exact committed HEAD, one-invocation WSL mount and test command, Ubuntu/Python/pytest versions,
  four selected test-file hashes, duration, result, coverage mapping, and acceptance limits.
- Updated the recovery implementation/test change records and S2 project state with the observed
  result.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Verification and acceptance

- `e2e-runner` executed the four focused S2 files at
  `c855ca4f2888d7288b006973950e4c6d28023b63`: **130 passed, 0 failed**, exit 0. Pytest reported
  11.23 seconds; wall command duration was 12.42 seconds.
- No source or test files changed during this execution. The e2e-runner did not read or modify the
  protected untracked `docs/sdlc/evidence/s2-functional-test-run.md`.
- This is synthetic source-level evidence only. Production identity/configuration, coordinator,
  installed runtime/E5, prohibited selectors, Windows containment, and full S2 are not accepted.
  Fresh specialist review remains pending; M03 remains MAJOR/OPEN.
