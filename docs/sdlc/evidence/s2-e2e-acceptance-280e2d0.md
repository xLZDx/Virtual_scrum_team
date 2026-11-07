# S2 E2E lifecycle and WSL diagnostic evidence

## Run identity and environment

- Product source HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1` (`Authenticate and episode-bind breaker overrides`).
- Repository: `D:\Repo\Virtual_scrum_team`.
- Test ownership: E2E runner owns `tests/vst/test_s2_runner_lifecycle.py`, `tests/vst/test_s2_store_lifecycle.py`, and `tests/vst/test_s2_sandbox_probe.py`.
- Product code was at the exact committed HEAD above. The owned test files were dirty and included the current test-author changes; they were not part of that source commit. No product source was edited in this run.
- Windows: Windows 11 build `10.0.26300`, PowerShell 7.6.7, `C:\Python314\python.exe`, Python 3.14.3, pytest 8.4.2.
- WSL: Ubuntu 24.04.5, systemd 255, Python 3.12.3, pytest 7.4.4, `vst-run.slice` with CPU quota 100%, memory max 2 GiB and task max 64.
- WSL test and diagnostic commands used transient systemd units in `vst-run.slice`; Store tests ran as `vst-runner`, and the runner/sandbox identity tests ran in a root harness that dropped child processes to `vst-worker` and `vst-reviewer`.
- Per-run systemd `InaccessiblePaths` were set for `/mnt/wsl`, `/mnt/wslg`, `/tmp/.X11-unix`, and `/usr/lib/wsl`. A separate in-scope check confirmed `scandir` was denied on each path and each presented mode `000` in the unit namespace. `stat` of the mountpoint itself remained possible, so stat success alone is not treated as evidence that the path is exposed.
- No operator key was read or accessed. No final probe was signed. No process-kill, kill-table, mutation, CI, build, or migration suite ran.

## Windows focused run

Command:

```powershell
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py tests/vst/test_s2_sandbox_probe.py
```

Final result after the last test edit: exit 0; **84 passed, 22 skipped, 1 warning** in 6.15 seconds. This is 106 collected tests. The warning was pytest-asyncio's deprecation warning for `asyncio.get_event_loop_policy`.

The first run had 1 failed test assertion, 83 passed, and 21 skipped. The replay implementation rejected the old signed override with `a prior override cannot clear a later breaker episode`; the test expected a later stale-episode message. This was a test assertion defect. The test now expects the observed earlier rejection boundary; no assertion was removed or weakened.

The suite includes manual override cases for unsigned input, tampering, `APPROVE`, mismatched breaker episode, mismatched configuration, replay after a later pause episode, and a valid operator-signed override bound to the active episode. The synthetic probe tests also distinguish `/mnt/wslg` from Windows drives and reject Windows `drvfs` plus 9p `aname=drvfs` mounts.

The 22 skipped tests remain `NOT_RUN`: POSIX worker identity on Windows (1), POSIX reviewer write boundary on Windows (1), Windows Job Object/POSIX containment cases (4; prohibited process-kill cases remain unexecuted), POSIX anchor/locking and recovery cases (9), real WSL/VM inventory (1), and E8 sandbox bake-off cases (6; mutation and process-kill cases prohibited).

## POSIX anchor and synthetic probe test runs

Store lifecycle command, executed in `vst-run.slice` as `vst-runner` with the four per-run inaccessible paths above:

```text
wsl.exe --distribution Ubuntu-24.04 --user root --exec systemd-run --wait --pipe --collect --unit=s2-store-posix-280e2d2 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/opt/vst-s2/source --property=InaccessiblePaths="/mnt/wsl /mnt/wslg /tmp/.X11-unix /usr/lib/wsl" /usr/bin/python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_store_lifecycle.py
```

Final result: exit 0; **19 passed, 0 skipped** in 1.59 seconds. This covered anchor CAS/fork rejection, older database restoration, lock setup and teardown failure injection, concurrent Store operations, reader/writer races, suffix recovery, and fail-closed malformed anchor states. No process was killed.

The first WSL executions exposed test-fixture/assertion problems and were corrected in the owned test files: an anchor assertion omitted the actual `immediate successor` error, and a POSIX `fcntl.flock` wrapper incorrectly required a third argument. The initial archive also held an older synthetic sandbox fixture missing its required operator key; the current owned test file was then staged into the WSL checkout. The final run above used the corrected owned test file and exact product source HEAD.

## Failure classification

| First failure | Classification | Evidence and correction |
|---|---|---|
| Windows manual-override replay expected a stale-episode message | Test defect | Store correctly rejected an existing replay earlier with `a prior override cannot clear a later breaker episode`; assertion now checks that earlier boundary. |
| Initial archived WSL Store tests had two failures | Test/fixture defect | The fork assertion omitted `checkpoint is not the immediate successor`; the archived synthetic sandbox fixture lacked its required `operator_key`. Current owned tests were corrected and staged into WSL. |
| Intermediate WSL Store unlock test had one failure | Test defect | Mock `fcntl.flock` wrapper required a third argument although POSIX uses two; wrapper now forwards variadic extra arguments. |
| First safe E8 helper invocation could not import `tools` | Test-harness environment setup | First invocation lacked the staged repository working directory; the next had the directory but driver lacked explicit source `sys.path`. Corrected driver then passed all selected scenarios. |
| First POSIX identity run failed with `NameError: sys is not defined` | Test defect | Added the local import; the two identity tests then passed. |

No failure was classified as a flake; each was tied to a deterministic test or invocation defect and passed after that specific correction.

Synthetic sandbox probe command, executed in `vst-run.slice` as `vst-runner` with the same per-run inaccessible paths:

```text
wsl.exe --distribution Ubuntu-24.04 --user root --exec systemd-run --wait --pipe --collect --unit=s2-probe-posix-280e2d0 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/opt/vst-s2/source --property=InaccessiblePaths="/mnt/wsl /mnt/wslg /tmp/.X11-unix /usr/lib/wsl" /usr/bin/python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_sandbox_probe.py
```

The current WSL runner and sandbox files were run together after adding both OS-identity tests:

```text
wsl.exe --distribution Ubuntu-24.04 --user root --exec systemd-run --wait --pipe --collect --unit=s2-runner-sandbox-posix-280e2d0 --slice=vst-run.slice --working-directory=/opt/vst-s2/source --property=InaccessiblePaths="/mnt/wsl /mnt/wslg /tmp/.X11-unix /usr/lib/wsl" --property=TemporaryFileSystem=/run/user:ro /usr/bin/python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_sandbox_probe.py
```

Result: exit 0; **76 passed, 11 skipped** in 1.32 seconds. Skips: E4 platform containment/process scenarios (4), actual WSL/VM inventory and egress proof (1), E8 bake-off scenarios (6). The WSL Store run was 19 passed, 0 skipped. Across the three owned files, the WSL executions yielded 95 passed and 11 skipped; Windows yields the same 106 collected tests with the two POSIX identity cases skipped on that platform.

## Selected safe E8 fixture scenarios

The available `tools/vst/slice.py::run_lifecycle_scenarios` is not safely selectable by scenario: it unconditionally invokes `HandWrittenWorker.crash_mid_edit`, whose child calls `os._exit(97)`. That crash path and the full bake-off remain `NOT_RUN` under the process-termination prohibition. I executed only separate safe fixture operations in one transient unit with the four inaccessible paths and `TemporaryFileSystem=/run/user:ro`:

```text
wsl.exe --distribution Ubuntu-24.04 --user root --exec systemd-run --wait --pipe --collect --unit=s2-e8-safe-280e2d2 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/opt/vst-s2/source --property=InaccessiblePaths="/mnt/wsl /mnt/wslg /tmp/.X11-unix /usr/lib/wsl" --property=TemporaryFileSystem=/run/user:ro /usr/bin/python3 /opt/vst-s2/e8-safe-scenarios.py
```

Result: exit 0. Selected scenario observations:

| Safe fixture scenario | Result | Limit |
|---|---|---|
| STOP and cleanup transition | STOP callback then cleanup callback; final state `READY` after resume | Callbacks were no-op fixture functions; no process termination occurred. |
| Resume and epoch fencing | Epoch advanced 2→3; stale epoch lease was rejected | Store/API fixture only. |
| Budget exhaustion | Overflow rejected as `budget`; one marker was written idempotently; event chain verified | Store/API fixture only. |
| Unauthorized write denial | Out-of-scope write rejected before worker subprocess; target file stayed absent | No authorized in-scope worker edit was run. |
| Blocked egress | Reserved-target smoke check returned blocked | One-target smoke check only; not a default-deny proof. |
| Mid-edit crash and complete E8 bake-off | `NOT_RUN` | `run_lifecycle_scenarios` cannot select safe scenarios without executing `crash_mid_edit`, which invokes `os._exit(97)`. |

The selected operations do not execute an actual worker process and do not establish the production worker's mount-namespace inheritance. There is no installed `vst-*` application service unit, and the repository's Supervisor API accepts a callback without configuring a systemd namespace. A worker launched as a child of a process already in the masked systemd unit would inherit that process namespace, but this deployment condition is not verified here.

## POSIX worker and read-only reviewer identity checks

The owned identity tests ran in a root test harness inside a transient `vst-run.slice` unit, with all four inaccessible paths and `TemporaryFileSystem=/run/user:ro`:

```text
wsl.exe --distribution Ubuntu-24.04 --user root --exec systemd-run --wait --pipe --collect --unit=s2-posix-identities-280e2d1 --slice=vst-run.slice --working-directory=/opt/vst-s2/source --property=InaccessiblePaths="/mnt/wsl /mnt/wslg /tmp/.X11-unix /usr/lib/wsl" --property=TemporaryFileSystem=/run/user:ro /usr/bin/python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture
```

Result: exit 0; **2 passed** in 0.41 seconds. The child worker used the provisioned `vst-worker` UID/GID `999/989`; runner was `997/988`, signer was `995/987`, and the worker's supplementary groups excluded runner and signer. Six disposable signer-owned 0600 trust-root fixture files were unreadable. The worker could not traverse/connect to a synthetic signer Unix socket with signer ownership, runner-group access, and no worker-group permission. No real key contents were read or printed. The real signer service was inactive during this test; its endpoint was not part of this fixture check.

The separate reviewer test used `vst-reviewer` UID/GID `993/985` against a worker-owned worktree and a real SQLite Store fixture. `require_read_only_reviewer` passed, and appends to the worktree file and Store file plus creation of a new worktree file were all denied. This proves the fixture permission boundary, not a full reviewer workflow or signed sandbox proof.

At the earlier identity-fixture run, the real signer endpoint was not part of the test. A separate resumed observation found that an earlier transient unit and its `/run` directory had disappeared; that observation produced no client request. The signer was later started successfully after the bounded ACL setup documented below. `run_manifest_commands` remains `NOT_RUN`; no operator key was read or invoked.

## Unsigned preflight diagnostic

The inventory ran as `vst-runner` in a transient `vst-run.slice` unit with the per-run inaccessible paths above. The run identifier embeds the product source HEAD because this probe schema has no separate code-head field; the run ID, spec digest and nonce identify the diagnostic. No signature was added.

- Run ID: `s2-280e2d0a613a0b70252c13ce7afe85f22734f7d1-preflight-wsl24-804c24a84d714e54`.
- Fresh nonce: `a089602060734e49aafba6472305c447`.
- `docs/SANDBOX_SPEC.md` SHA-256: `7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997`.
- Result: `FAIL`; operator attestation placeholder had no signature and final probe was not signed.
- The diagnostic driver invocation was `wsl.exe --distribution Ubuntu-24.04 --user root --exec systemd-run --wait --pipe --collect --unit=s2-preflight-280e2d0 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/opt/vst-s2/source --property=InaccessiblePaths="/mnt/wsl /mnt/wslg /tmp/.X11-unix /usr/lib/wsl" /usr/bin/python3 /opt/vst-s2/preflight-diagnostic.py`. It emitted only the run ID, nonce, spec digest, booleans, socket basenames and sanitized mount target/type counts.

| Probe check | Diagnostic value | Meaning |
|---|---:|---|
| `automount_disabled` | true | No Windows drive mount was detected; synthetic cases cover `/mnt/wslg`, `drvfs`, and `9p/aname=drvfs`. |
| `interop_disabled` | true | WSL interop check reported disabled. |
| `no_container_socket` | false | Socket inventory was incomplete; an empty basename list does not prove absence. |
| `non_root` | true | Probe process ran as a non-root identity. |
| `external_egress_blocked` | true | Reserved-address smoke check only; it does not prove default-deny policy. |
| `loopback_canary` | true | Local loopback canary succeeded. |
| `empty_external_allowlist` | false | Placeholder attestation had no signature, so it did not satisfy the signed shape. |

The runtime root `/run/user` was a real directory owned by UID/GID 0 with mode `0755`. It contained one numeric UID entry owned by UID/GID 0 with mode `0700`. That entry is the parent for direct Docker socket inspection; nested containerd and podman parents were missing when checked with root metadata access. `vst-runner` cannot traverse the root-owned `0700` UID directory, so the fail-closed scan cannot establish that its candidate sockets are absent. The actual field `container_socket_inventory_complete` was false, and the derived `no_container_socket` check was false; the failure is not merely the unsigned `no_container_socket=false` attestation bit. Socket basenames observed were empty.

Granting the runner traversal into root's private runtime directory would broaden access, so no ACL or mode change was made for the runner inventory. A separate transient systemd unit successfully masked `/run/user` with an empty read-only temporary filesystem (`TemporaryFileSystem=/run/user:ro`) while continuing to scan `/run/docker.sock`, `/var/run/docker.sock`, `/run/containerd/containerd.sock`, and the known per-UID candidates. In that unit `/run/user` had zero entries, `container_socket_inventory_complete=true`, and no socket basenames were observed. Its unsigned preflight diagnostic still returned `FAIL`: `no_container_socket=false` and `empty_external_allowlist=false` because the placeholder lacked a signature. This proves the scoped inventory only. No `vst-*` application service or worker unit is installed, and the repository does not configure `Supervisor` to run in a namespace-bearing unit, so actual worker inheritance of this mask is `NOT_RUN`. A later temporary ACL was applied only to the two intermediary directories for `vst-signer` execute/search, then restored as described below.

Masked-inventory diagnostic command:

```text
wsl.exe --distribution Ubuntu-24.04 --user root --exec systemd-run --wait --pipe --collect --unit=s2-preflight-maskrun-280e2d0 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/opt/vst-s2/source --property=InaccessiblePaths="/mnt/wsl /mnt/wslg /tmp/.X11-unix /usr/lib/wsl" --property=TemporaryFileSystem=/run/user:ro /usr/bin/python3 /opt/vst-s2/preflight-masked-runtime.py
```

Result: transient property accepted; empty `/run/user` listing; `container_socket_inventory_complete=true`; zero socket basenames; overall unsigned result `FAIL`. Run ID: `s2-280e2d0a613a0b70252c13ce7afe85f22734f7d1-preflight-mask-runuser-119d6d9a701d430b`; nonce: `b80dd50eb9b34534b0202761981617cc`; spec digest: `7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997`.

Sanitized mount target/type counts from the transient unit:

| Target class | Filesystem | Count | Review state |
|---|---|---:|---|
| `/mnt/wslg` | tmpfs | 1 | Contents inaccessible in the unit namespace; system mount approval not recorded. |
| Windows drive target | none | 0 | No Windows drive mount detected. |
| `/usr/lib/wsl*` | tmpfs | 1 | Contents inaccessible in the unit namespace; system mount approval not recorded. |
| `/usr/lib/modules` | overlay | 1 | Operator approval for this system mount is not recorded. |
| `/run/user` mask | tmpfs | 1 | Empty read-only temporary filesystem in the scoped unit. |
| Other targets | binfmt_misc 1, cgroup2 1, configfs 1, debugfs 1, devpts 1, devtmpfs 1, ext4 1, fusectl 1, hugetlbfs 1, mqueue 1, proc 1, rootfs 1, sysfs 1, tmpfs 8, tracefs 1 | present | System mount approval for the complete set is not recorded. |

The signer service needed a narrowly scoped traversal grant because its parent directories were root-owned mode `0700`. A temporary ACL granted only `vst-signer` execute/search on `/var/lib/vst` and `/var/lib/vst/keys`; no listing permission was granted. The dedicated runner-signer directory was already signer-owned mode `0700`, and its key remained signer-owned mode `0600`. After the socket exercise, both parent ACLs were restored to their original root-owned mode `0700` with no named signer entry. Final metadata still showed the dedicated directory at `995:987` mode `0700` and key at `995:987` mode `0600`. No other role path was changed and the operator key was not accessed.

The corrected transient signer then ran under `vst-signer` UID with `vst-runner` primary group, `PrivateNetwork=yes`, `RestrictAddressFamilies=AF_UNIX`, `NoNewPrivileges=yes`, `PrivateDevices=yes`, the per-run inaccessible-path mask, and read-only `/run/user`. The harmless runner client called `authorize_runner_over_socket`, submitted a valid synthetic signing request, replayed the same ID/payload (same signature), and attempted a changed payload with the same ID (rejected). The signer-side `SO_PEERCRED` log showed only runner UID/GID `997:988`. A separate worker UID/GID `999:989` connection attempt was denied with `PermissionError`/errno 13 before reaching the signer handler. A digest of the returned signature was `4ecd68df459a87d5fb9cbe1378f239a120bde765d4ec6067f1a86bcc539fc26e`; signature bytes and key contents are not recorded. This proves the real signer socket protocol and peer boundary for this synthetic request. The full `run_manifest_commands` integration remains `NOT_RUN`.

## Resource, egress and attestation sufficiency

- `systemctl show vst-run.slice --property=CPUQuotaPerSecUSec --property=MemoryMax --property=TasksMax` returned `CPUQuotaPerSecUSec=1s`, `MemoryMax=2147483648`, and `TasksMax=64` (100% of one CPU, 2 GiB, 64 tasks).
- The bounded resource proof ran as `vst-runner` in `vst-run.slice` with `CPUQuota=100%`, `MemoryMax=2G`, `TasksMax=64`, `RuntimeMaxSec=30s`, `InaccessiblePaths=-/mnt/wsl -/mnt/wslg -/tmp/.X11-unix -/usr/lib/wsl`, `TemporaryFileSystem=/run/user:ro`, `TemporaryFileSystem=/tmp:size=1G,mode=1777`, `PrivateNetwork=yes`, and `RestrictAddressFamilies=AF_UNIX`. The `-` prefix permits systemd to ignore a target that is absent; `/tmp/.X11-unix` was absent in this run. The first run without that prefix failed with systemd status `226/NAMESPACE`, because `/tmp/.X11-unix` did not exist.
- Effective manager properties were `RuntimeMaxUSec=30s`, `MemoryMax=2147483648`, `CPUQuotaPerSecUSec=1s`, and `TasksMax=64`. The process observed `/tmp` as writable `tmpfs`, mode `1777`, total size `1073741824` bytes. A child Python process inherited the same `/tmp` tmpfs, size and mode and successfully wrote a fixture file. This proves those limits and the `/tmp` namespace for the verification unit and its child. It does not prove an installed product worker unit uses those properties; no application unit is installed/configured here.
- `nftables.service` was active. A sanitized hash of `/usr/sbin/nft -j list ruleset` at the follow-up observation was `dbaadc56201799974415694d76208d9931f151a3b31fa28dc52fd9f6d0f1bba0`. It contained two `inet` chains in table `vst_s2_filter` (input and output), both default `drop`, and two terminal accept rules, each matched a loopback-named interface. No other terminal verdicts were present. The preflight's reserved-target smoke check also returned blocked, but that individual check alone is not policy proof.
- The inventory schema does not emit an `environment_id`; its value for an operator attestation is therefore `UNKNOWN` in this diagnostic. The observed platform identity was Ubuntu 24.04.5 LTS, systemd 255, in the `Ubuntu-24.04` WSL distribution.
- These facts support default-deny egress and resource-limit evidence for the WSL verification unit. They do **not** support a complete operator attestation: sanitized host/system mount categories remain pending approval, no installed application unit confirms the actual worker inherits these properties, and no signed inventory/network-policy attestation was created. Therefore `no_unapproved_host_paths=true` is not established, and no final preflight `PASS` is claimed.

## Acceptance matrix

| Requested item | State | Evidence | Remaining acceptance / dependency | Next action and owner |
|---|---|---|---|---|
| Signed manual override | Runtime-proven on Windows synthetic Store/Supervisor boundary | Valid signed override succeeds; unsigned, tampered, mismatched episode/config, replayed/stale and plain-APPROVE inputs reject. | Does not prove real operator key custody. | Keep operator key in signer boundary; security owner is not identified in current records. |
| Store anchor lifecycle | Runtime-proven on Ubuntu WSL under resource slice | 19/19 owned Store tests passed, including concurrent readers/writers and suffix recovery. | Full host isolation is separate and remains unsigned/unverified. | Retain this result as POSIX lifecycle evidence; operator owns host policy acceptance. |
| Synthetic probe contract and mount classification | Runtime-proven | Windows 3-mount regression cases and WSL synthetic probe tests passed. | Synthetic fixtures do not prove actual policy state. | Use actual signed inventory only after prerequisites are satisfied. |
| Read-only reviewer write denial | Runtime-proven for fixture permissions | Distinct worker/reviewer identities; helper passed and three direct writes failed with permission denial. | No complete reviewer workflow was exercised. | Functional owner may link this diagnostic to S6.3; broader journey still needs its acceptance test. |
| Actual WSL preflight | `FAIL` diagnostic; final verification `NOT_RUN` | Initial scan was incomplete; a scoped empty-runtime-mask diagnostic was complete but unsigned. A real runner-only signer socket was later verified, but no inventory was signed. | No worker/service configuration proves inheritance of the mask; host mount approval is unresolved; operator signature intentionally absent. | Operator/security owner to approve the mask deployment and host mounts, then authorize a fresh signed run. |
| Signer socket authority | Runtime-proven for the synthetic request | Runner `SO_PEERCRED` was 997:988; signing and identical replay succeeded, changed-payload replay was rejected; worker connection denied with errno 13. | Full `run_manifest_commands` path not exercised. | Run that focused integration only after the remaining worker manifest fixture is available; E2E owner. |
| Bounded writable workspace and deadline | Runtime-proven for the verification unit and one child | `/tmp` was a 1 GiB `tmpfs`, mode 1777; child inherited and wrote. Effective 30-second runtime, 2 GiB memory, 100% CPU, 64 tasks were read from systemd. | Actual product worker unit configuration remains unverified. | Add the same properties to the deployed runner parent unit and verify its child; deployment owner not identified. |
| E8 safe scenarios | Partial fixture evidence | STOP, budget, resume/epoch, unauthorized-write denial and one egress smoke ran in the scoped unit. | The calls used API fixtures, not a launched worker process. | Keep them as partial evidence; full worker acceptance needs a safely selectable worker entry point and approved environment. |
| E8 crash / process-kill / kill-table | `NOT_RUN` | Full E8 helper unconditionally enters `crash_mid_edit`/`os._exit(97)`; that path is prohibited. | Prohibition remains active. | No action until operator changes the prohibition or the scenario is safely selectable without process termination. |

## Provenance and limitations

- The Windows and WSL product source was exact committed HEAD `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- The WSL checkout used the committed product source, then received the current owned Store and sandbox test files from the Windows working tree so Linux ran the corrected tests. Test files were dirty and not yet committed.
- The earlier unsigned diagnostic at HEAD `c470542dbedf992b785804e421b1ff52e142003c` remains a historical `FAIL`; it was not changed into a passing result.
- No operator key, private key contents, full host mount paths, or private inventory output is included in this record.

## Final five-file Windows S2 run

- Tested repository HEAD: `d70b6b7530eabc25097b9e43f0aeebf2dab2cc10`.
- Product source remains `280e2d0a613a0b70252c13ce7afe85f22734f7d1`; this final run is on the committed E2E tests/evidence commit.
- Environment: Windows 11 build `10.0.26300-SP0`; Python 3.14.3 from `C:\Python314\python.exe`; pytest 8.4.2.
- Exact command:

```powershell
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py tests/vst/test_s2_sandbox_probe.py
```

- Result: exit 0; **144 passed, 22 skipped, 1 warning** in 7.95 seconds. The warning is pytest-asyncio's deprecation warning for `asyncio.get_event_loop_policy`.
- The 22 skips are explicit `NOT_RUN` cases, not passing acceptance evidence:
  - `test_posix_worker_cannot_read_signer_or_key_file`: Windows lacks the POSIX account and Unix-socket permission boundary.
  - `test_e4_platform_containment_scenarios_not_run[posix_process_group_cleanup]`, `[post_exit_descendant_cleanup]`, `[key_file_permissions_for_worker_identity]`, and `[windows_parent_job_nesting]`: platform containment needs the provisioned POSIX sandbox or authorized nested Windows Job Object host; process-kill/kill-table execution is prohibited.
  - `test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork`, `test_external_anchor_detects_restored_older_database_and_locks_writes`, `test_exactly_one_event_ahead_is_recovered_before_mutation`, and `test_multi_event_transaction_recovers_suffix_after_one_checkpoint_append`: POSIX external-anchor acceptance is platform-gated.
  - `test_invalid_external_anchor_suffix_fails_closed[external_anchor_ahead_of_database]`, `[external_anchor_missing_for_nonempty_database]`, `[forked_checkpoint_suffix]`, `[malformed_checkpoint_suffix]`, and `[tampered_checkpoint_suffix]`: POSIX external-anchor failure-state acceptance is platform-gated.
  - `test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture`: Windows lacks the POSIX reviewer credential boundary.
  - `test_real_sandbox_inventory_has_all_required_properties`: actual WSL/VM inventory and egress proof requires an operator-provisioned POSIX sandbox.
  - `test_e8_sandbox_bakeoff_scenarios_not_run[worker_crash_mid_edit]`, `[STOP_injection_and_cleanup]`, `[budget_exhaustion]`, `[resume_with_fresh_epoch_and_receipt]`, `[unauthorized_write_outside_scope]`, and `[blocked_egress_attempt]`: full E8 acceptance requires the sandbox; process-kill and mutation runs are prohibited, and synthetic results cannot prove isolation.

## Real signer socket authority check

The initial transient signer setup failed before opening the socket: `PermissionError: [Errno 13] Permission denied` from `os.open` in `_key_is_private`. Metadata showed both intermediary directories were root-owned mode `0700`, while the dedicated runner-signer directory and key were signer-owned mode `0700` and `0600`. To unblock only the dedicated service, a temporary named-user ACL granted `vst-signer` `--x` (search/execute only) on `/var/lib/vst` and `/var/lib/vst/keys`; neither directory-list permission nor group/other access was granted. No other role directory or key path was changed. The dedicated directory and key modes/owners remained `995:987` mode `0700` and `0600` respectively. After the socket exercise, both ACLs were restored to their original owner-only ACL/mode (`0700`, root:root), and final key metadata remained unchanged. The operator key was not accessed.

The corrected transient signer ran with an explicit source `sys.path`, UID `vst-signer`, primary GID `vst-runner`, `NoNewPrivileges=yes`, `PrivateDevices=yes`, `PrivateNetwork=yes`, and `RestrictAddressFamilies=AF_UNIX`. The runner client ran in `vst-run.slice` as UID/GID `997:988`, called `authorize_runner_over_socket`, signed a valid synthetic signing request, replayed the same ID/payload idempotently, then attempted a changed payload with the same ID and was rejected. All recorded `SO_PEERCRED` pairs were `997:988`. The signature digest was `4ecd68df459a87d5fb9cbe1378f239a120bde765d4ec6067f1a86bcc539fc26e`; no signature bytes or key contents are persisted.

A separate worker client ran as UID/GID `999:989`; its real Unix-socket connection was denied with `PermissionError`/errno 13. It did not reach the signer handler, and no worker peer credential was recorded. The service was stopped after these calls. This proves runner-only access and request signing for this synthetic protocol fixture. It does not prove the full `run_manifest_commands` path, which remains `NOT_RUN` because the complete v2 manifest runner fixture was not exercised.
