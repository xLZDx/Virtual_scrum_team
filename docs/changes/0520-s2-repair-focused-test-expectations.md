# Change 0520: repair focused S2 test expectations and fixtures

## Why

The first focused run at HEAD `a1fa0b022eeafaf0973e58d3f8dd564cb2362453` collected and executed
tests, then returned **100 passed, 5 failed**, exit code 1. The designated e2e-runner classified all
five failures as test-source defects; no product-source defect was confirmed. The complete fifth
traceback was not retained because the initial tool output was truncated, so this record preserves
the exact available classification and does not invent the missing traceback.

## What changed

The functional-test-reviewer corrected only test source:

- The expired-envelope assertion now matches the implementation's exact noncanonical-expiry error.
- The fixed Supervisor registry-path test now supplies a complete valid peer/config shape so it
  reaches the intended fixed-path validation.
- The public-key non-regular-file fixture now reports a directory from `fstat` for the file
  descriptor under test.
- The admission-latch loader test patches `os.path.lexists`, the path lookup actually used by source.
- The legacy unsigned event test now distinguishes hash-chain integrity from semantic replay:
  `verify_event_chain()` succeeds for the correctly chained bytes, then reopening and calling
  `startup_reconcile()` must reject the old event schema and integrity-lock the Store.

Product source, runtime configuration and test scope were not changed. These corrections preserve
the original acceptance intent and do not remove, skip, or weaken a test.

## Verification state

- The 100/5 run above is an unsuccessful attempt and is not a passing gate.
- The corrected test source has not been re-executed. `e2e-runner` owns the next focused run on the
  committed corrected test source.
- No code, check, build, CI, migration, installation, systemd activation, root configuration, key,
  or real dispatch action occurred.
- The protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched.

## Acceptance and ownership

This change closes five test-source defects only; it does not close S2-PROV-M03 or establish a test
pass. The functional-test-reviewer owns test-source corrections, e2e-runner owns the rerun, and
Codex owns evidence/coordination. S2 remains NOT APPROVED and S3 remains unstarted.
