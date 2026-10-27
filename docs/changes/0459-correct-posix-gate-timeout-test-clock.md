# Change 0459: Correct the POSIX gate-timeout test clock

## What changed

- Update the fake monotonic clock in `test_distinct_uid_gate_environment_timeout_cleans_scope_and_refuses_exec` to keep admission and the initial deadline guard within budget, then expire specifically at the gate handoff boundary.
- Assert the expected number of monotonic reads so future deadline checks cannot silently shift the test to a different branch.

## Why

After change 0458 added admission and initial deadline checks, the previous two-value fake clock expired before `_write_pipe_before_deadline` was reached. The production result correctly reported a timeout without setting the gate-specific diagnostic, so the stale fixture failed with `KeyError: posix_gate_timeout`. The fixture now models the intended gate-handoff timeout contract deterministically.

## Affected paths

- `tests/vst/test_s2_runner_lifecycle.py`
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, and the generated document registry.

## Verification state

- Exact-head run on `aa965c030396001fce82583d17fc6dca9a50cdf7` exposed the stale fake-clock fixture: the selected set had 10 passed and 2 gate-timeout failures (85 deselected). The source did not change during that run.
- The test fixture correction is committed separately. A complete exact-head rerun of the focused set is pending; do not treat the failed run as a product failure or as a passing verification.
- POSIX E4.1 cross-UID E2E passed 1/1 at source/test commit `aa965c030396001fce82583d17fc6dca9a50cdf7` in a bounded delegated Ubuntu-24.04 WSL unit; see `docs/sdlc/evidence/s2-e4-posix-cross-uid-run-3be44ad-20261027.md` for earlier-head evidence and the next exact-head evidence addendum.

## Decision and ownership

- Decision: keep the assertion strict and move the test's fake expiry point to the actual gate-handoff boundary rather than weakening the production deadline behavior.
- Test correction authored by `functional-test-reviewer`; coordination and local Git by Codex.
- No production source change, policy selector, push, PR, merge, or external configuration is included.
