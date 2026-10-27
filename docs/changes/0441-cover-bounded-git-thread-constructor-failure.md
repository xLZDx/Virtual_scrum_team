# Change 0441: cover bounded Git thread-constructor failure

## What changed

- Added one VST-017 regression that injects `MemoryError` while constructing the first pipe-reader thread after the bounded Git child has been spawned.
- The test verifies the child is killed and reaped and both captured pipes are closed.
- The test uses `_FakeBoundedGitProcess`; it does not spawn or kill an operating-system process.

## Why

Change 0440 moved all post-spawn setup inside cleanup protection after a reliability review found that `Thread` construction could still fail before the cleanup guard. This regression binds that specific failure path to the source correction.

## Affected paths

- `tests/vst/test_s2_runner_lifecycle.py`
- `docs/changes/0441-cover-bounded-git-thread-constructor-failure.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and verification

- Source correction: `f95ceb1324967629de2feb475b0deb4bf34c3963`.
- Test authored by `functional-test-reviewer`, GPT-6 Luna, medium effort; the coordinator reviewed the focused diff. No tests/checks were run during authoring or review.
- The new selector remains pending execution by `e2e-runner` against the exact committed source/test head. A pass can establish this synthetic cleanup path only; it cannot establish real process termination or the restricted S2 process-kill, crash/resume, mutation, or timeout/restart scenarios.
- No policy-excluded selector was added or run.

## Ordered next steps and owners

1. Codex: commit this test with its linked change record and generated registry.
2. `e2e-runner`: execute only `test_bounded_git_thread_constructor_failure_kills_reaps_and_closes` at the exact source/test head in the existing Ubuntu 24.04 WSL environment; preserve `NOT_RUN` if setup fails.
3. Reliability, silent-failure, architecture, security, and database reviewers: review the applicable S2 changes on the final post-test head.
4. Codex: reconcile exact results and remaining permitted S2 evidence; retain prohibited scenarios as `NOT_RUN`.
5. GPT-PM: review the exact final S2 head only after S2 evidence is complete; no push/PR before fresh approval.

## Attribution

Change: 0441
Executor: Codex (test authored by functional-test-reviewer)
