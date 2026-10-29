# S2 versioned worker-helper focused test execution — attempt 3

## Provenance

- Repository: canonical `Virtual_scrum_team` checkout.
- Git HEAD: `9a5c41de5ce2878558402665eafaa0a80c09d177`.
- Worktree: dirty; source and test changes were uncommitted at execution time.
- Interpreter: CPython 3.14.3 (`C:\Python314\python.exe`).
- Protected pre-existing `s2-functional-test-run.md` remained untracked and
  untouched.
- Attempt 1 and attempt 2 evidence are retained in the adjacent uniquely named
  files.

## Exact execution

```text
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_persistent_runner_service.py tests/vst/test_s2_runner_lifecycle.py
```

Result: **178 passed, 1 failed, 6 skipped**, 1 pytest-asyncio deprecation
warning, exit code 1, elapsed 75.67 seconds. Total collected: 185 cases.

SHA-256 at execution:

- `tests/vst/test_s2_persistent_runner_service.py`:
  `efcfce624c6e4e45d8dfb8addad2215707a06ed2662109f3d756ad4b8ace5ee3`
- `tests/vst/test_s2_runner_lifecycle.py`:
  `2a4cee1bd2165a74ea879d97a7145695d698bdc3bebfc61252b7e42a0f1b4c16`
- `tools/vst/runner.py`:
  `02c60162ed1bbda61e1341d055aa893ce1cf52c3bbecb545e7e67eb902a07ee`
- `tools/vst/runner_service.py`:
  `729e62edbc5e011f3d7294d754b6b34adfc0256802879ba263604c36150b76c4`

## Remaining failure

`test_run_manifest_commands_stops_after_incomplete_cleanup_and_records_later_command_not_run`
fails with:

```text
ContractError: no command reached its launch path before the deadline; refusing an unreserved receipt
```

The test replaces `_run_one` with a mock that returns
`EXIT_CAPTURE_INCOMPLETE` without invoking the `_before_spawn` callback passed
by `run_manifest_commands`. As a result, the mock skips the real launch-boundary
reservation, and the production guard correctly refuses to mint a receipt
without a reserved execution. Classification: **test mock defect**. The test
owner should have the mock invoke `_before_spawn` before returning the simulated
post-launch capture failure, then retain its assertions that later commands do
not run and the receipt is inconclusive.

The prior attempt-2 cgroup fixture failures are fixed and now pass. Six
platform-conditional skips remain skips, not passes. No production source was
edited by the execution role.

## Next action

Owner: functional-test-reviewer. Correct the mock to traverse the launch-boundary
callback without weakening assertions, then rerun this exact two-module command.
This Windows run is neither real cgroup-kill evidence nor WSL helper installation
or runtime proof.
