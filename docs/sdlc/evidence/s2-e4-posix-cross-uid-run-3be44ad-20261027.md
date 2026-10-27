# S2 E4.1 POSIX cross-UID runtime evidence — 3be44ad

Date: 2026-10-27  
Repository: `D:\Repo\Virtual_scrum_team`  
Exact archived source/test commit: `3be44ad4ea93bc9e68cee1534d1d4c4e731ac451`  
Runtime correlation: transient systemd units `s2-e4-3be44ad-r2.service`, `r3.service`, and `r4.service`; no S4 report-bound runner was used because this S2 selector is not in its category manifest.

## Functional evidence

The designated `functional-test-reviewer` ran the focused lifecycle set on Windows, Python 3.14.3:

```text
python -m pytest -q tests/vst/test_s2_runner_lifecycle.py -k 'distinct_uid_worker_refuses or distinct_uid_cgroup_gate or distinct_uid_attach_failure or gate_environment_timeout or run_and_sign_stops_after or run_manifest_commands_stops_after or unconfirmed_cgroup_cleanup_latches_later_distinct_uid_launches or concurrent_distinct_uid_launch_waits_for_cleanup_latch_admission'
```

Result: exit 0; **11 passed, 85 deselected**, 3.48 seconds. One unrelated `pytest-asyncio` deprecation warning noted `asyncio.get_event_loop_policy`. Only the protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was present in the worktree; it was not touched.

## WSL runtime evidence

The designated `e2e-runner` copied an exact `git archive` of commit `3be44ad4ea93bc9e68cee1534d1d4c4e731ac451` into the existing Ubuntu-24.04 WSL environment. The archive hashes matched:

- `tools/vst/runner.py`: `f6e0c75c0aca291cde07903617061722e75ce3cd88d7981b89f6d2d8ef762da5`
- `tests/vst/test_e4_runner.py`: `8e2bdf8c7e448544debbffafd339e3a03b55346273b6d8cf25a8d9992c12f8ad`

Environment: Python 3.12.3, pytest 7.4.4, kernel `6.6.114.1-microsoft-standard-WSL2`. The selected test passed in each of three bounded transient units; the detailed r4 command/result follows:

```text
python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-e4-3be44ad-r4 -p no:cacheprovider tests/vst/test_e4_runner.py::test_posix_worker_timeout_kills_descendant_across_uid_boundary
```

Result: exit success; **1 passed in 5.01 seconds**. The bounding unit was configured with `Delegate=yes`, 100% CPU quota, 2 GiB memory, 64 tasks, 45-second runtime, private network, `NoNewPrivileges=yes`, and only `CAP_SETUID`/`CAP_SETGID`. The runner was UID/GID 997:988 with capability mask `0xc0`; worker UID/GID 999:989 had zero effective/permitted capabilities.

The child cgroup was `/sys/fs/cgroup/vst.slice/vst-run.slice/s2-e4-3be44ad-r4.service/vst-command-456-f2226b3cbc934180a766a39d7390c604`; `cgroup.kill` was present. `cgroup.events` showed `populated=0` on creation and `populated=1` after attachment. The final `populated=0` event was too brief to capture before scope removal; the test's `capture_incomplete=False` and stopped-heartbeat assertions passed. No other selector or prohibited policy scenario was run.

Invocation profile:

```text
systemd-run --wait --pipe --collect --unit=s2-e4-3be44ad-r4 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/run/vst-s2-e4-3be44ad-r4 --setenv=PYTHONPATH=/run/vst-s2-e4-3be44ad-r4 --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=Delegate=yes --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property='TemporaryFileSystem=/tmp:size=1G,mode=1777' --property=PrivateNetwork=yes --property='RestrictAddressFamilies=AF_UNIX AF_INET' --property=NoNewPrivileges=yes --property='CapabilityBoundingSet=CAP_SETUID CAP_SETGID' --property='AmbientCapabilities=CAP_SETUID CAP_SETGID' /usr/bin/bash -lc '<prints id/caps/cgroup; exec /usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-e4-3be44ad-r4 -p no:cacheprovider tests/vst/test_e4_runner.py::test_posix_worker_timeout_kills_descendant_across_uid_boundary>'
```

## Scope and limitations

This proves only the selected cross-UID POSIX descendant cleanup behavior on the archived source/test head and that revision's transient WSL unit profile. It does not prove persistent service deployment, end-to-end egress, all resource limits outside the observed unit properties, Windows Job Object nesting, complete S2, or the later deadline correction in change 0458. The last cgroup event was not retained. S2 remains open; S3 has not started.
