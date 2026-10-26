# S2 Job Object attach cleanup focused tests

Date: 2026-10-26  
Repository: `D:\Repo\Virtual_scrum_team`  
Source HEAD during both runs: `d9b2a5c1ffced7930c6a5dfc82c04b7c6d9f88ce` (working tree dirty)  
Test owner: designated `e2e-runner`, GPT-6 Luna

## Source change under test

The working-tree change to `tools/vst/runner.py` addresses the earlier reliability advisory about `_JobObject.attach()` ignoring failed `CloseHandle` results after Job Object setup failure. It retries once, writes an error log if both attempts fail, and still returns `None`; strict callers therefore continue to refuse the requested command. The exact source diff is in change 0331 and was not yet committed during these runs.

## Runs

| Command | Result |
|---|---|
| `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py -k "job_object_attach_setup_failure or strict_windows_launch_stays_fail_closed_after_job_setup_cleanup_failure"` | Python 3.14.3; exit 0; 5 passed, 75 deselected; one `pytest-asyncio` deprecation warning; 0.33 s |
| `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py::test_strict_windows_launch_suspends_assigns_job_then_resumes_before_command tests/vst/test_s2_runner_lifecycle.py::test_nonstrict_windows_launch_keeps_unsuspended_compatibility_path` | Python 3.14.3; exit 0; 2 passed; one `pytest-asyncio` deprecation warning; 0.26 s |

An initial run of the five focused cases returned 4 passed / 1 failed because the new strict test treated process creation as proof the synthetic command resumed. The designated test author changed the assertion to observe the resume call; the resulting focused rerun passed 5/5. This was a test assertion defect, not a source failure.

## Excluded behavior and provenance

The agent did not run process-kill/kill-table, POSIX process-group, sandbox identity, mutation, or explicit E4 platform-containment selectors. All cleanup effects were mocked. Before testing, status contained only the implementer's `tools/vst/runner.py` edit and the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; afterward the test file was additionally modified by the designated agent. No commit was created by that agent. Exact committed-head rerun and specialist review are still required.
