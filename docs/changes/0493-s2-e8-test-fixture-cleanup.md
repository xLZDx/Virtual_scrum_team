# Change 0493 — Clean up the S2 E8 synthetic test fixture

Date: 2026-10-28

## What changed and why

Changed the focused synthetic lifecycle test fixture to use `tempfile.TemporaryDirectory` as a
context manager. Pytest is configured to retain temporary paths, so its standard `tmp_path_factory`
left failed-run fixtures in the host temp directory. The context manager now removes only the
directory created by this test after the module fixture finishes, including when assertions or
setup raise.

## Affected paths

- `tests/vst/test_s2_e8_synthetic_lifecycle.py` fixture lifecycle only. The six acceptance
  assertions and test scope are unchanged.

## Verification state

- No tests were run for this cleanup change.
- The prior failed-run fixture at `D:\Temp\pytest-of-koros\pytest-3188` was not inspected or
  deleted; it predates this cleanup and remains outside this change.
- The current test revision is pending focused `e2e-runner` execution.

## Ownership and next step

The functional-test-reviewer owns the test fixture implementation, and Codex owns its Git/evidence
coordination. `e2e-runner` owns execution at the next committed exact head. Operator owns any
deletion of the previously retained temporary fixture. Keep restricted crash/process scenarios
`NOT_RUN`.
