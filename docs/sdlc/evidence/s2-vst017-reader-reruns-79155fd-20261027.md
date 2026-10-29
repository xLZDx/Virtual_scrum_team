# S2 VST-017 reader cleanup reruns at source/test HEAD 79155fd

## Scope

The designated `e2e-runner` reran exactly two selectors after source correction `f95ceb1` moved all post-spawn reader setup under bounded-Git cleanup protection:

- `tests/vst/test_s2_runner_lifecycle.py::test_bounded_git_reader_start_failure_kills_reaps_and_closes`
- `tests/vst/test_s2_runner_lifecycle.py::test_bounded_git_reader_failure_kills_reaps_and_fails_closed`

Both use `_FakeBoundedGitProcess`; neither launches or kills an OS process.

## Exact source and test identity

- Repository: `D:\Repo\Virtual_scrum_team`; branch `s4-canonical-continuation`.
- Source/test HEAD: `79155fdf9f1f4a7ba71358592ccd54c669a76291`.
- Source blob `tools/vst/slice.py`: `fe2acfeb7052d3f16136d7661bf5b553fbf6463d`.
- Test blob `tests/vst/test_s2_runner_lifecycle.py`: `424c7424ac9b08701678eb1d6eb17cd724c9390f`.
- Successful invocation ID: `609f49b815db436bb1b2c73c9551432d`.
- Successful transient unit: `s2-reader-rerun-aabbccddee11`.

## Environment and command

Ubuntu-24.04 WSL; Python 3.12.3 / pytest 7.4.4; runner UID/GID 997:988. The successful run streamed `git archive --format=tar 79155fdf9f1f4a7ba71358592ccd54c669a76291` into a fresh transient extraction `/run/vst-s2-reader-rerun-aabbccddee11`, then used:

```text
systemd-run --wait --pipe --collect --unit=s2-reader-rerun-aabbccddee11 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/run/vst-s2-reader-rerun-aabbccddee11 --setenv=PYTHONPATH=/run/vst-s2-reader-rerun-aabbccddee11 --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property=TemporaryFileSystem=/tmp:size=1G,mode=1777 --property=PrivateNetwork=yes --property='RestrictAddressFamilies=AF_UNIX AF_INET' --property=NoNewPrivileges=yes --property='CapabilityBoundingSet=CAP_SETUID CAP_SETGID' --property='AmbientCapabilities=CAP_SETUID CAP_SETGID' /usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-reader-rerun-aabbccddee11 -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_bounded_git_reader_start_failure_kills_reaps_and_closes tests/vst/test_s2_runner_lifecycle.py::test_bounded_git_reader_failure_kills_reaps_and_fails_closed
```

A first setup attempt failed with `CHDIR` permission denied before any selector started. The role created a fresh archive, corrected its ownership to UID/GID 997:988, and retried. The successful run had no warnings; both selectors passed, pytest duration 0.48 seconds, exit 0. The archive was removed and absence verified. No repository files were changed by the test run.

## Result and limits

- 2 passed, 0 failed, 0 skipped at exact source/test HEAD `79155fd`.
- Together with the constructor-failure regression at this same head, all three targeted bounded-Git setup/reader failure regressions passed on the corrected cleanup source. Four other source regressions remain tied to `dc1741b` and are not upgraded to `79155fd`.
- This does not establish real process termination, descendants, crash recovery, timeout/restart behavior, Windows Job Objects, or complete system containment.
- Restricted process-kill, crash/resume, mutation, timeout/restart, and policy selectors remain `NOT_RUN`.

## Attribution

Executor: `e2e-runner`, GPT-6 Luna, medium effort. Successful invocation: `609f49b815db436bb1b2c73c9551432d`.
