# S2 runner restart-fence verification — exact commit `a6ea0dc`

Date: 2026-10-27
Repository: `D:\Repo\Virtual_scrum_team`
Branch: `s4-canonical-continuation`
Exact source/test commit: `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`
Change record: `docs/changes/0464-fence-s2-posix-scopes-across-runner-restart.md`
Complete source/test diff from review baseline `f0bbac8` through this code/test commit: `docs/sdlc/evidence/s2-code-diff-f0bbac8-to-a6ea0dc.patch`, SHA-256 `9243245F7029802183860E17354D029A0C7747A6461FFA629ED19EA04A86AB13` (7 paths; 1,599 insertions, 59 deletions).

This record verifies the restart-fence code at the exact committed source/test revision. It does not close S2. Tests were authored/executed by the designated `functional-test-reviewer` and `e2e-runner`; the coordinator did not execute tests.

## Windows safe functional selections

Environment: Windows, Python 3.14.3 via `C:\Python314\python.exe`, pytest 8.4.2. Repository status before/after the runs: clean tracked tree, with only the protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`. Every invocation reported exact HEAD `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`.

The reviewer repeated the exact selection command blocks in `s2-safe-functional-exact-4c1692d-20261027.md` for E1/E2/D1/D2 contracts, E6 diff gate, E7 operation recovery, synthetic E5/E6 probe, E3/E7 store, E7 lifecycle, synthetic Git, E2 runner/signing, mocked Windows Job Object, bounded storage, timeout/retry, target-lock timeout, and the safe POSIX admission/deadline selection. These are the same node IDs and command arguments as that ledger; the source/test commit was updated to `a6ea0dc`. The 20 previously prohibited or platform-unverified selectors were excluded.

Results by command group:

| Group | Passed | Duration |
|---|---:|---:|
| E1/E2/D1/D2 contract | 43 | 1.10 s |
| E6 diff gate | 22 | 33.26 s |
| E7 operation recovery | 4 | 1.13 s |
| Synthetic E5/E6 probe | 14 | 1.24 s |
| E3/E7 store | 10 | 1.04 s |
| E7 lifecycle/breaker/reconciliation | 8 | 1.27 s |
| Synthetic Git | 6 | 67.04 s |
| E2 runner/signing | 42 | 9.21 s |
| Mocked Windows Job Object | 10 | 1.43 s |
| Bounded target storage | 4 | 23.85 s |
| Timeout/retry | 1 | 15.73 s |
| Target lock timeout | 1 | 5.30 s |
| Safe POSIX admission/deadline mocks | 13 | 2.97 s |
| New lock/stale-scope unit selectors | 10 | 1.07 s |
| **Total** | **188** | — |

The new lock/stale command was:

```text
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py::test_posix_admission_lock_validates_private_runtime_and_lock_file tests/vst/test_s2_runner_lifecycle.py::test_posix_admission_lock_refuses_untrusted_runtime_directory[16895] tests/vst/test_s2_runner_lifecycle.py::test_posix_admission_lock_refuses_untrusted_runtime_directory[16877] tests/vst/test_s2_runner_lifecycle.py::test_posix_admission_lock_refuses_untrusted_runtime_directory[41408] tests/vst/test_s2_runner_lifecycle.py::test_posix_admission_lock_refuses_non_private_lock_file tests/vst/test_s2_runner_lifecycle.py::test_posix_admission_lock_deadline_refuses_contended_flock tests/vst/test_s2_runner_lifecycle.py::test_posix_stale_cgroup_reconciliation_removes_only_owned_scope tests/vst/test_s2_runner_lifecycle.py::test_posix_stale_cgroup_reconciliation_fails_closed_on_malformed_scope tests/vst/test_s2_runner_lifecycle.py::test_posix_stale_cgroup_reconciliation_refuses_unconfirmed_cleanup tests/vst/test_s2_runner_lifecycle.py::test_distinct_uid_launch_refuses_when_process_lock_or_reconciliation_fails
```

Result across all Windows groups: 188 passed, 0 failed. Fourteen pytest_asyncio deprecation warnings reported `asyncio.get_event_loop_policy`; no other warning or skip was reported. One initial diff-gate invocation ran without its session handle being retained; the reviewer waited for it to exit and reran the identical selection with output capture. Only the captured 22/22 result is included above.

The 10 new selectors use synthetic cgroup and mocked `fcntl` fixtures. They verify runtime-directory/lock ownership and permissions, bounded lock wait, strict stale-scope filtering, bounded cleanup result handling, and non-approving refusal. They do not establish real POSIX lock contention or a populated stale-scope recovery.

## Bounded WSL2 runtime evidence

Exact source archive command:

```text
cmd.exe /d /c "git -C D:\Repo\Virtual_scrum_team archive --format=tar HEAD tools/vst tests/vst | wsl.exe -d Ubuntu-24.04 -- tar -x -C /run/vst-s2-restart-lock-a6"
```

Archive SHA-256: `219a1e65f27b067f7062bd4402f1ce312e235bd101c8f369f6cd2654549d7682`. Exact file hashes:

| File | SHA-256 |
|---|---|
| `tools/vst/runner.py` | `f3e6d2f132c70e2cf3baad53506a70faf65221ddbdb4721f0dac96cf0c88dcf3` |
| `tests/vst/test_s2_runner_lifecycle.py` | `3f213dbda0ca933a0a81bba540e5c74d890ec3bac66328fce4b93396aa7e395d` |
| `tests/vst/test_s2_sandbox_probe.py` | `66440069c6a267f8fcbae2ba9fad0c2552d74fd801fffcbebd0e0c4a9c1fbd8c` |
| `tools/vst/lifecycle.py` | `db81de532229cca96855be286ae5565acff31e0910be09afbc39885132e47a34` |
| `tools/vst/store.py` | `eaf70a5f095fc77cdf5e27985fe9f659db087045f8c0c79d015f8d953980b3b6` |
| `tests/vst/test_s2_store_lifecycle.py` | `243ae4105e7e752ce0028c9a5a9edf9ec844fd1de1a69a09151a6c6d8ffcf52e` |
| `tests/vst/e1e4_helpers.py` | `c36dbb1e8f22cbb8ec50925fa130d2673e6216451cab661ca7c357fa2cf14347` |

Environment: Ubuntu 24.04 WSL2, kernel `6.6.114.1-microsoft-standard-WSL2`, Python 3.12.3, pytest 7.4.4, cgroup2fs. Existing runner identity was UID/GID `997:988`, worker `999:989`; signer and reviewer identities were present. The successful transient units were bounded to CPU 100%, 2 GiB memory, 64 tasks, 45 seconds, 1 GiB temporary filesystem, private network, `AF_UNIX` only, and `NoNewPrivileges=yes`. No persistent service or system configuration was installed.

### POSIX identity and capability selectors

Unit `s2-restart-id-a6-r3.service`, root with `CAP_CHOWN CAP_SETGID CAP_SETUID`, ran:

```text
wsl.exe -d Ubuntu-24.04 -- systemd-run --wait --pipe --collect --unit=s2-restart-id-a6-r3 --slice=vst-run.slice --uid=root --gid=root --working-directory=/run/vst-s2-restart-lock-a6 --setenv=PYTHONPATH=/run/vst-s2-restart-lock-a6 --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=RuntimeDirectory=vst-runner --property=RuntimeDirectoryMode=0700 --property=RuntimeDirectoryPreserve=no --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property="TemporaryFileSystem=/tmp:size=1G,mode=1777" --property=PrivateNetwork=yes --property="RestrictAddressFamilies=AF_UNIX" --property=NoNewPrivileges=yes --property="CapabilityBoundingSet=CAP_CHOWN CAP_SETGID CAP_SETUID" --property="AmbientCapabilities=CAP_CHOWN CAP_SETGID CAP_SETUID" /usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-restart-lock-a6 -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture
```

Pytest command inside the unit:

```text
/usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-restart-lock-a6 -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture
```

Result: 2 passed in 1.66 s. Unit exit 0; runtime 2.365 s. These used temporary key/socket and read-only worktree/SQLite fixtures only.

Unit `s2-restart-cap-a6-r1.service`, UID/GID `997:988`, `Delegate=yes`, `CAP_SETGID CAP_SETUID`, ran:

```text
wsl.exe -d Ubuntu-24.04 -- systemd-run --wait --pipe --collect --unit=s2-restart-cap-a6-r1 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/run/vst-s2-restart-lock-a6 --setenv=PYTHONPATH=/run/vst-s2-restart-lock-a6 --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=RuntimeDirectory=vst-runner --property=RuntimeDirectoryMode=0700 --property=RuntimeDirectoryPreserve=no --property=Delegate=yes --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property="TemporaryFileSystem=/tmp:size=1G,mode=1777" --property=PrivateNetwork=yes --property="RestrictAddressFamilies=AF_UNIX" --property=NoNewPrivileges=yes --property="CapabilityBoundingSet=CAP_SETGID CAP_SETUID" --property="AmbientCapabilities=CAP_SETGID CAP_SETUID" /usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-restart-lock-a6 -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_drops_uid_change_capabilities_before_worker_command
```

Pytest command inside the unit:

```text
/usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-restart-lock-a6 -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_drops_uid_change_capabilities_before_worker_command
```

Result: 1 passed in 1.33 s. The test observed worker effective/permitted/inheritable/ambient capabilities all zero and inability to change UID to signer.

For both units, systemd created `/run/vst-runner` with mode `0700`, owner UID/GID `997:988`; unit stop removed the runtime directory.

Harness-attempt history: `s2-restart-id-a6-r1` did not execute tests because WSL idled between calls and cleared `/run/vst-s2-restart-lock-a6` (`status=200/CHDIR`). Attempt `r2` used comma-separated systemd capability values, so both selectors failed at fixture `os.chown` with `EPERM` (2 failed in 0.90 s). The corrected space-separated capability invocation `r3` then passed both selectors 2/2. These failed attempts are harness setup errors, not product test failures; only the corrected run is counted above.

### Cross-process lock and empty stale-scope fixture

Unit `s2-restart-lock-a6-r2.service`, invocation ID `34c1baf6c61b46e7985e5d7ffe6c2a03`, ran `/usr/bin/python3 /run/vst-s2-restart-lock-a6/flock-smoke.py`. It used `Delegate=yes`, UID/GID `997:988`, and the same bounded profile. Harness SHA-256: `fc84cc936566f1e45aaff31f93d545b5a6047bbb87e0ad5ea19dab27e7b46524`. Output:

```text
wsl.exe -d Ubuntu-24.04 -- systemd-run --wait --pipe --collect --unit=s2-restart-lock-a6-r2 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/run/vst-s2-restart-lock-a6 --setenv=PYTHONPATH=/run/vst-s2-restart-lock-a6 --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=RuntimeDirectory=vst-runner --property=RuntimeDirectoryMode=0700 --property=RuntimeDirectoryPreserve=no --property=Delegate=yes --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property="TemporaryFileSystem=/tmp:size=1G,mode=1777" --property=PrivateNetwork=yes --property="RestrictAddressFamilies=AF_UNIX" --property=NoNewPrivileges=yes --property="CapabilityBoundingSet=CAP_SETGID CAP_SETUID" --property="AmbientCapabilities=CAP_SETGID CAP_SETUID" /usr/bin/python3 /run/vst-s2-restart-lock-a6/flock-smoke.py
```

Harness source:

```python
import importlib, os, pwd, shutil, subprocess, sys, tempfile, time, types, uuid
from pathlib import Path
from tools.vst.runner import _DelegatedCgroup, _posix_cgroup_process_lock

runtime_dir = Path("/run/vst-runner")
st = runtime_dir.stat()
assert st.st_uid == os.geteuid() == pwd.getpwnam("vst-runner").pw_uid
assert st.st_mode & 0o777 == 0o700, oct(st.st_mode & 0o777)
print(f"runtime-directory mode={st.st_mode & 0o777:o} owner={st.st_uid}:{st.st_gid}")
print(f"invocation-id={os.environ.get('INVOCATION_ID','not-set')}")
with open("/proc/self/cgroup", encoding="ascii") as stream:
    print("cgroup=" + next(line.strip() for line in stream if line.startswith("0::")))

base = Path(tempfile.mkdtemp(prefix="vst-flock-smoke-"))
child = r"""
import importlib, os, sys, time, types
from pathlib import Path
from tools.vst.runner import _posix_cgroup_process_lock
role, root = sys.argv[1:3]
if role == "b":
    real = importlib.import_module("fcntl").flock
    proxy = types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4)
    def observed(fd, operation):
        try:
            return real(fd, operation)
        except BlockingIOError:
            Path(root + ".blocked").touch()
            raise
    proxy.flock = observed
    sys.modules["fcntl"] = proxy
with _posix_cgroup_process_lock(time.monotonic() + 10):
    if role == "a":
        Path(root + ".held").touch()
        until = time.monotonic() + 10
        while not Path(root + ".release").exists():
            if time.monotonic() >= until:
                raise SystemExit("release event deadline expired")
            time.sleep(0.005)
    else:
        Path(root + ".acquired").touch()
"""
def wait_file(path, seconds=5):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if path.exists():
            return
        time.sleep(0.005)
    raise RuntimeError(f"condition deadline expired waiting for {path.name}")
a = subprocess.Popen([sys.executable, "-c", child, "a", str(base)])
try:
    wait_file(Path(str(base) + ".held"))
    b = subprocess.Popen([sys.executable, "-c", child, "b", str(base)])
    wait_file(Path(str(base) + ".blocked"))
    assert not Path(str(base) + ".acquired").exists(), "second runner process entered held lock"
    Path(str(base) + ".release").touch()
    assert a.wait(timeout=10) == 0
    assert b.wait(timeout=10) == 0
    assert Path(str(base) + ".acquired").exists()
finally:
    if a.poll() is None:
        a.wait(timeout=10)
print("actual flock: second runner process waited until first released")

parent = _DelegatedCgroup._runner_parent()
stale = os.path.join(parent, f"vst-command-{os.getpid()}-{uuid.uuid4().hex}")
os.mkdir(stale, 0o700)
with open(os.path.join(stale, "cgroup.events"), encoding="ascii") as stream:
    events = dict(line.split() for line in stream if line.strip())
with open(os.path.join(stale, "cgroup.procs"), encoding="ascii") as stream:
    pids = stream.read().strip()
assert events.get("populated") == "0" and not pids, (events, pids)
print(f"stale synthetic scope before reconcile: populated={events['populated']} cgroup.procs=empty path={stale}")
with _posix_cgroup_process_lock(time.monotonic() + 10):
    pass
assert not os.path.exists(stale), "empty stale scope was not removed"
print("empty stale scope reconciled; no populated cgroup or process was killed")
shutil.rmtree(base)
```

```text
runtime-directory mode=700 owner=997:988
invocation-id=34c1baf6c61b46e7985e5d7ffe6c2a03
cgroup=0::/vst.slice/vst-run.slice/s2-restart-lock-a6-r2.service
actual flock: second runner process waited until first released
stale synthetic scope before reconcile: populated=0 cgroup.procs=empty path=/sys/fs/cgroup/vst.slice/vst-run.slice/s2-restart-lock-a6-r2.service/vst-command-776-a5152ece9c094491af0b6ea06c7341f4
empty stale scope reconciled; no populated cgroup or process was killed
```

Before reconciliation, the harness read and asserted `cgroup.events populated=0` and empty `cgroup.procs`. It then acquired the same lock helper and confirmed removal. No populated scope existed, no process was killed, and no runner crash was simulated. Unit result: success, runtime 891 ms, CPU 844 ms, memory peak 448 KiB.

### POSIX E3 anchor selectors

Unit `s2-e3-anchor-a6-r1.service`, UID/GID `997:988`, no effective/permitted/bounding/ambient capabilities, ran the 8 temporary Store/anchor selectors listed under “Additional exact-head POSIX E3 anchor fixtures” in `s2-safe-functional-exact-4c1692d-20261027.md`. Result: 8 passed in 0.24 s; unit and outer exit 0, runtime 864 ms. These included synthetic restored-old-database detection and malformed/forked checkpoint fixtures; no interruption/crash-recovery selector ran. The unit invocation ID was not captured.

Exact transient invocation:

```text
wsl.exe -d Ubuntu-24.04 -- systemd-run --wait --pipe --collect --unit=s2-e3-anchor-a6-r1 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/run/vst-s2-restart-lock-a6 --setenv=PYTHONPATH=/run/vst-s2-restart-lock-a6 --setenv=PYTHONDONTWRITEBYTECODE=1 --setenv=TMPDIR=/tmp --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property="TemporaryFileSystem=/tmp:size=1G,mode=1777" --property=PrivateNetwork=yes --property="RestrictAddressFamilies=AF_UNIX" --property=NoNewPrivileges=yes --property="CapabilityBoundingSet=" --property="AmbientCapabilities=" /usr/bin/python3 -m pytest -q -c /dev/null --rootdir=/run/vst-s2-restart-lock-a6 -p no:cacheprovider tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork tests/vst/test_s2_store_lifecycle.py::test_anchor_append_separates_valid_tail_without_final_newline tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes 'tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[external_anchor_ahead_of_database]' 'tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[external_anchor_missing_for_nonempty_database]' 'tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[forked_checkpoint_suffix]' 'tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[malformed_checkpoint_suffix]' 'tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[tampered_checkpoint_suffix]'
```

Exact node IDs:

```text
tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork
tests/vst/test_s2_store_lifecycle.py::test_anchor_append_separates_valid_tail_without_final_newline
tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes
tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[external_anchor_ahead_of_database]
tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[external_anchor_missing_for_nonempty_database]
tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[forked_checkpoint_suffix]
tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[malformed_checkpoint_suffix]
tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed[tampered_checkpoint_suffix]
```

The command line above ends with these eight exact selectors.

## Exact-head selector accounting and limits

The Windows runs passed 188 selected IDs. The WSL runs passed 11 additional selected IDs (3 identity/capability and 8 E3 anchor). Therefore 199 selected test IDs passed at exact source/test commit `a6ea0dc`, with no test failure. The 10 new lock/stale pytest IDs extend the prior 209-ID inventory to 219 expected IDs; a new collect-only command was intentionally not run. The same 20 listed selectors in the prior ledger remain `NOT_RUN`, including prohibited process-kill, runner crash/recovery, mutation, E8, and policy cases. The separate cross-UID descendant-kill E4.1 selector last passed at `4c1692d`; it was not rerun at this head and is not counted as exact-head evidence here.

The runtime directory and delegated cgroup were transient and removed when the bounded units stopped. This evidence does not prove persistent service provisioning, stability across a real runner crash/restart with a populated child scope, Windows ACL behavior, nested Windows Job Object containment, end-to-end host egress, or any prohibited `NOT_RUN` scenario. S2 remains open.

## Fresh specialist review at the exact code/test head

All four reviewers used GPT-6 Luna, medium effort, read-only, and reviewed `4c1692d..a6ea0dc` plus the committed test change and the WSL evidence above. No reviewer executed tests or changed files.

| Role | Finding | Evidence and limits |
|---|---|---|
| Architect | Prior source-level restart-latch MAJOR is resolved for lock-aware runners in the same stable delegated parent; no new code BLOCKER/MAJOR. | `runner.py` obtains the shared lock before reconciliation/launch; strict direct-child name/path checks and bounded cleanup refuse uncertain scopes. Stable parent, same lock inode, and stopping pre-lock instances remain deployment prerequisites. A different replacement cgroup cannot see the previous cgroup. |
| Security reviewer | No actionable code BLOCKER/MAJOR. | Private lock directory/file checks, `O_NOFOLLOW`, strict child cgroup scope, and fail-closed handling limit the new boundary. Persistent service configuration and populated-scope restart evidence remain unproven. |
| Reliability reviewer | **MAJOR — deployment restart fence is not evidenced.** | The replacement scans only its own cgroup parent. Without a stable singleton service parent or verified stop/fence-before-restart, stale scopes in a different prior parent are invisible. Owner: operator for service/runtime provisioning evidence; Codex for collection; GPT-PM for adjudication. |
| Silent-failure reviewer | No actionable silent-failure finding. | Lock timeout returns `EXIT_TIMEOUT`; unsafe lock or unresolved scope returns `EXIT_CAPTURE_INCOMPLETE` with `posix_cgroup_refused`; later commands are stopped. The reviewer confirms the WSL scope was empty, not populated, and no restart/crash was simulated. |

Consensus state: source behavior is fail-closed for compliant runners sharing one lock and one delegated parent. The stable-parent deployment condition is an open acceptance MAJOR; no persistent runner service unit/config is present in the repository. It must not be upgraded to a code pass or waived by the bounded transient-unit result. Exact GPT-PM adjudication has not yet been obtained.
