# S2 review regressions at exact source/test HEAD `dc1741b`

## Scope and provenance

- Sprint: S2 only; acceptance mapping: VST-011, VST-012, VST-017.
- Canonical checkout: `D:\Repo\Virtual_scrum_team`, branch `s4-canonical-continuation`.
- Exact source/test commit: `dc1741bda127de5fc7af5544c984dd81cb4927aa`.
- Source corrections under test: `324f901` (ambient capability drop, anchor tail separator, bounded Git cleanup).
- Executor: `e2e-runner`, GPT-6 Luna, medium effort.
- Environment: existing WSL2 `Ubuntu-24.04`; transient systemd unit `s2-focused-regression-dc1741b`, invocation `23d6730f34d94877849cd7bf177708a4`.
- Unit identity and bounds: UID/GID `vst-runner`; `CapabilityBoundingSet=CAP_SETUID CAP_SETGID`; `AmbientCapabilities=CAP_SETUID CAP_SETGID`; `NoNewPrivileges=yes`; private network; 2 GiB memory, 64 tasks, 45-second runtime; `/tmp` bounded to 1 GiB.

## Exact command

```sh
git archive --format=tar dc1741bda127de5fc7af5544c984dd81cb4927aa | wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc 'set -eu; target=/run/vst-s2-regression-dc1741b; mkdir -p "$target"; tar -xf - -C "$target"; cd "$target"; systemd-run --wait --pipe --collect --unit=s2-focused-regression-dc1741b --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory="$target" --setenv=PYTHONPATH="$target" --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property=TemporaryFileSystem=/tmp:size=1G,mode=1777 --property=PrivateNetwork=yes --property="RestrictAddressFamilies=AF_UNIX AF_INET" --property=NoNewPrivileges=yes --property="CapabilityBoundingSet=CAP_SETUID CAP_SETGID" --property="AmbientCapabilities=CAP_SETUID CAP_SETGID" /usr/bin/python3 -m pytest -q tests/vst/test_s2_runner_lifecycle.py::test_runner_drops_uid_change_capabilities_before_worker_command tests/vst/test_s2_store_lifecycle.py::test_anchor_append_separates_valid_tail_without_final_newline tests/vst/test_s2_runner_lifecycle.py::test_bounded_git_reader_start_failure_kills_reaps_and_closes tests/vst/test_s2_runner_lifecycle.py::test_bounded_git_reader_failure_kills_reaps_and_fails_closed'
```

## Results

- Result: **4 passed, 0 skipped**, exit code 0 (`4 passed, 2 warnings in 0.63s`).
- `test_runner_drops_uid_change_capabilities_before_worker_command`: passed under the `vst-runner` profile with ambient `CAP_SETUID` and `CAP_SETGID`; the worker observed zero effective, permitted, inheritable, and ambient capabilities and could not change to the signer UID. It did not read a signing key.
- `test_anchor_append_separates_valid_tail_without_final_newline`: passed; the valid no-final-LF checkpoint remained a readable two-record JSONL history after successor append.
- `test_bounded_git_reader_start_failure_kills_reaps_and_closes`: passed with a fake process; no real subprocess was started or killed.
- `test_bounded_git_reader_failure_kills_reaps_and_fails_closed`: passed with a fake process; no real subprocess was started or killed.
- Both warnings were pytest cache writes denied because the source archive was read-only; they did not skip or fail a selector.
- An initial `cmd.exe /d /c` setup failed with Windows path syntax error before any selector ran. A separate `tar -tf - | head -1` diagnostic closed the archive pipe early before any selector ran. The successful command above consumed the complete archive.
- The temporary archive path `/run/vst-s2-regression-dc1741b` was absent after execution. No worktree/fork was created. No other selector ran.

## Limits

This evidence validates only the three targeted code corrections. It does not close full S2 Phase 8 acceptance: Windows Job Object nesting, complete POSIX descendant containment, full egress enforcement, persistent deployment, and policy-restricted process-kill/crash/resume/mutation/timeout selectors remain open or `NOT_RUN`.
