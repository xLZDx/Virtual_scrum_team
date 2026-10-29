# S2 E4 POSIX admission deadline exact-head evidence — 2a71cf4

Date: 2026-10-27  
Repository: `D:\Repo\Virtual_scrum_team`  
Branch: `s4-canonical-continuation`  
Exact source/test commit: `2a71cf4fc32715a1f9f502ab5e7e7788aeff45e8`  
Production source SHA-256: `tools/vst/runner.py` = `39a3e37d9ec51d52587276f6d17bed695361d5017c23aa0cba5b7be54d1125fc`  
Functional test SHA-256: `tests/vst/test_s2_runner_lifecycle.py` = `a09c25ecdae05efbe14dd17e27aa8965b98c6e973ea693c1509d28965a061cc7`  
POSIX E2E test SHA-256: `tests/vst/test_e4_runner.py` = `8e2bdf8c7e448544debbffafd339e3a03b55346273b6d8cf25a8d9992c12f8ad`

## Focused functional regression

The designated `functional-test-reviewer` ran the exact committed lifecycle suite selection on Windows with Python 3.14.3:

```text
python -m pytest -q tests/vst/test_s2_runner_lifecycle.py -k 'distinct_uid_worker_refuses or distinct_uid_cgroup_gate or distinct_uid_attach_failure or gate_environment_timeout or run_and_sign_stops_after or run_manifest_commands_stops_after or unconfirmed_cgroup_cleanup_latches_later_distinct_uid_launches or concurrent_distinct_uid_launch_waits_for_cleanup_latch_admission or distinct_uid_launch_skips_after_lock_wait_exhausts_command_budget'
```

Result: 97 collected, 12 selected, **12 passed**, 85 deselected, 0 skipped, exit 0 in 3.23 seconds. One unrelated `pytest-asyncio` deprecation warning reported `asyncio.get_event_loop_policy`. Git HEAD and status were unchanged; the protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was left untouched.

## Real POSIX cross-UID E4.1 selector

The designated `e2e-runner` transferred an exact archive of this source/test commit to the existing Ubuntu-24.04 WSL environment and ran only the selected test under a bounded transient systemd unit.

Command:

```text
/usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-e4-2a71cf4-r1 -p no:cacheprovider tests/vst/test_e4_runner.py::test_posix_worker_timeout_kills_descendant_across_uid_boundary
```

Result: **1 passed in 4.30 seconds**, unit success, outer exit 0. Runtime: WSL2 kernel `6.6.114.1-microsoft-standard-WSL2`, Python 3.12.3, pytest 7.4.4. Correlation: transient unit `s2-e4-2a71cf4-r1.service`.

Live outer unit properties: `Delegate=yes`, 100% CPU quota, `MemoryMax=2G`, `TasksMax=64`, 45-second runtime, private network, address families `AF_UNIX AF_INET`, `NoNewPrivileges=yes`, and capability bounding/ambient sets limited to `CAP_SETUID CAP_SETGID`. Runner identity UID/GID `997:988`, `CapPrm/Eff/Bnd=0xc0`, `NoNewPrivs=1`. Worker identity UID/GID `999:989`, zero permitted/effective capabilities.

Observed child cgroup: `/sys/fs/cgroup/vst.slice/vst-run.slice/s2-e4-2a71cf4-r1.service/vst-command-472-36bb0f678662481eb007ae1b163a4c4d`; `cgroup.kill` existed. Its `cgroup.events` showed `populated=0` at creation and `populated=1` after attach. The final child `populated=0` event was not separately sampled before immediate child-scope removal; the test's cleanup and stopped-heartbeat assertions passed.

## Exact transient-unit invocation profile

```text
systemd-run --wait --pipe --collect --unit=s2-e4-2a71cf4-r1 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/run/vst-s2-e4-2a71cf4-r1 --setenv=PYTHONPATH=/run/vst-s2-e4-2a71cf4-r1 --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=Delegate=yes --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property='TemporaryFileSystem=/tmp:size=1G,mode=1777' --property=PrivateNetwork=yes --property='RestrictAddressFamilies=AF_UNIX AF_INET' --property=NoNewPrivileges=yes --property='CapabilityBoundingSet=CAP_SETUID CAP_SETGID' --property='AmbientCapabilities=CAP_SETUID CAP_SETGID' /usr/bin/bash -lc '<prints id/caps/cgroup; exec /usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-e4-2a71cf4-r1 -p no:cacheprovider tests/vst/test_e4_runner.py::test_posix_worker_timeout_kills_descendant_across_uid_boundary>'
```

## Scope and limitations

This proves the exact-head, selected POSIX UID 997→999 descendant timeout-cleanup path and the focused serialized-admission/latch/deadline unit regressions. It does not establish Windows nested Job Object runtime behavior, every E4 platform-conditional scenario, persistent systemd deployment, end-to-end host egress, full sandbox workspace binding, or overall S2 acceptance. Prohibited process/kill-table, crash/resume, and mutation scenarios remain `NOT_RUN`. No S3 work started.
