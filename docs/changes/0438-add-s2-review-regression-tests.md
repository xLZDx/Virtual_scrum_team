# Change 0438: add focused S2 review-regression tests

## What changed

- Added a POSIX runner-boundary test that checks the worker command starts with empty effective, permitted, inheritable, and ambient capability sets and cannot switch to the signer UID.
- Added an external-anchor test for a valid final JSON checkpoint without a terminating LF.
- Added two synthetic bounded-Git tests for pipe-reader startup and read failures; both use a fake process and do not start or kill a real subprocess.

## Why

Change 0436 fixed three S2 source findings. These tests bind the corrections to VST-011, VST-012, and VST-017 without selecting the policy-excluded timeout/restart, process-kill, crash/resume, or mutation scenarios.

## Affected paths

- `tests/vst/test_s2_runner_lifecycle.py`
- `tests/vst/test_s2_store_lifecycle.py`
- `docs/changes/0438-add-s2-review-regression-tests.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Test ownership and evidence

- Authored by `functional-test-reviewer`, GPT-6 Luna, medium effort; tests were not run during authoring.
- Current source correction commit: `324f901`. These tests must be run against the exact committed test/source head in the provisioned WSL environment. The capability test skips unless it sees the `vst-runner` identity and expected ambient capability profile; a skip is `NOT_RUN`, not PASS.
- Exact new test ids: `test_runner_drops_uid_change_capabilities_before_worker_command`; `test_anchor_append_separates_valid_tail_without_final_newline`; `test_bounded_git_reader_start_failure_kills_reaps_and_closes`; `test_bounded_git_reader_failure_kills_reaps_and_fails_closed`.
- No restricted policy selector was added. No test, check, build, CI, migration, or runtime scenario was executed in this change.

## Ordered next steps and owners

1. Codex: review the new tests' mapping to the three accepted S2 corrections.
2. `e2e-runner`: execute only the four named selectors on the exact source/test head under the provisioned WSL runner profile; record `NOT_RUN` if the required identity/capability profile is unavailable.
3. Relevant security, database, reliability, silent-failure, and architecture reviewers: re-review the corrected exact source head after the test results.
4. GPT-PM: adjudicate the exact final S2 head only after all required evidence and remaining system acceptance are reconciled.

## Attribution

Change: 0438
Executor: Codex
