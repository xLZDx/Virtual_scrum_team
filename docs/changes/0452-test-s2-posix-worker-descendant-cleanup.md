# Change 0452: test POSIX descendant cleanup across worker identity

## What changed

- Added `test_posix_worker_timeout_kills_descendant_across_uid_boundary` to `tests/vst/test_e4_runner.py`.
- The test runs the real POSIX runner under the provisioned `vst-runner` identity, switches its command to `vst-worker`, and requires the worker descendant's heartbeat to stop after timeout cleanup.
- The test skips with a precise reason when the expected identities, helper, sandbox `/tmp`, or runner capability profile is unavailable; the descendant is bounded to self-exit within six seconds if cleanup fails.

## Why

S2 E4.1 requires POSIX process-group/descendant cleanup inside the sandbox. Existing process-tree tests ran with one UID, while S2 launches the command under a distinct worker UID. This targeted case exercises that actual boundary.

## Affected paths

- `tests/vst/test_e4_runner.py`
- `docs/changes/0452-test-s2-posix-worker-descendant-cleanup.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Test ownership and verification

- Test authored by `functional-test-reviewer`, GPT-6 Luna, medium effort; the coordinator reviewed the diff.
- Exact selector: `tests/vst/test_e4_runner.py::test_posix_worker_timeout_kills_descendant_across_uid_boundary`.
- No tests/checks were run during authorship or review. Execution is pending by `e2e-runner` at the committed source/test head.
- This is a controlled temp-only process test. The descendant has a six-second self-exit bound; all files are under a unique sandbox `/tmp` directory removed in `finally`.

## Ordered next steps and owners

1. `e2e-runner`: execute only the new selector in the existing Ubuntu-24.04 WSL sandbox profile; record exact identity/capabilities, command, result, and cleanup.
2. Codex: if the real UID boundary fails, fix the least-privilege process-supervision path before further E4/E8 acceptance.
3. Relevant security/reliability reviewers: review any source change before acceptance.
4. GPT-PM: review exact final S2 head after all remaining system acceptance is complete.

## Attribution

Change: 0452
Executor: Codex (test authored by functional-test-reviewer)
