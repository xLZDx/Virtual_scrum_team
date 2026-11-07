# S2 VST-017 constructor-failure regression run

## Scope

Executed only `tests/vst/test_s2_runner_lifecycle.py::test_bounded_git_thread_constructor_failure_kills_reaps_and_closes` for VST-017. The selector injects `MemoryError` from `threading.Thread` construction after a fake bounded-Git process is returned by the patched `Popen`; it is not an operating-system process termination test.

## Exact source and test identity

- Repository: `D:\Repo\Virtual_scrum_team`, branch `s4-canonical-continuation`.
- Source/test HEAD: `79155fdf9f1f4a7ba71358592ccd54c669a76291`.
- Source blob `tools/vst/slice.py`: `fe2acfeb7052d3f16136d7661bf5b553fbf6463d`.
- Test blob `tests/vst/test_s2_runner_lifecycle.py`: `424c7424ac9b08701678eb1d6eb17cd724c9390f`.
- Invocation ID: `4360e5aed857492f933bb5ab4e8b5cf5`.

## Environment and command

The `e2e-runner` streamed `git archive --format=tar 79155fdf9f1f4a7ba71358592ccd54c669a76291` into the existing Ubuntu-24.04 WSL distribution and extracted it temporarily to `/run/vst-s2-regression-79155fd`. The command was:

```text
systemd-run --wait --pipe --collect --unit=s2-ctor-regression-79155fd --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/run/vst-s2-regression-79155fd --setenv=PYTHONPATH=/run/vst-s2-regression-79155fd --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property=TemporaryFileSystem=/tmp:size=1G,mode=1777 --property=PrivateNetwork=yes --property='RestrictAddressFamilies=AF_UNIX AF_INET' --property=NoNewPrivileges=yes --property='CapabilityBoundingSet=CAP_SETUID CAP_SETGID' --property='AmbientCapabilities=CAP_SETUID CAP_SETGID' /usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-regression-79155fd -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_bounded_git_thread_constructor_failure_kills_reaps_and_closes
```

Runtime: Python 3.12.3, pytest 7.4.4; runner UID/GID 997:988, worker UID/GID 999:989. The transient systemd unit reported success, exit code 0, runtime 672 ms, and peak memory 1.5 MiB.

## Result

- 1 passed, 0 failed, 0 skipped; pytest duration 0.26 seconds; command exit 0.
- The fake-process assertions observed kill/reap and stdout/stderr closure after injected constructor failure.
- The temporary archive was removed after the run. No repository files were changed by test execution.
- No other selector was executed in this invocation.

## Limits and policy exclusions

This result establishes only the injected Python setup-failure path with a fake process. It does not establish real child termination, OS process-group or Windows Job Object containment, crash recovery, or timeout behavior. Restricted process-kill, crash/resume, mutation, timeout/restart, and policy selectors remain `NOT_RUN`. Full S2 acceptance remains open pending fresh specialist review and permitted system evidence.

## Attribution

Executor: `e2e-runner`, GPT-6 Luna, medium effort. Evidence was returned by the role and correlated to invocation `4360e5aed857492f933bb5ab4e8b5cf5`.
