# S2 E5 real runner integration and scoped WSL evidence

## Scope and provenance

- Product source HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- The Windows checkout was at documentation HEAD `15e05f199833a2b1b8f75822435dbdf9242aaf33`; `git diff --quiet 280e2d0a613a0b70252c13ce7afe85f22734f7d1 HEAD -- tools/vst` returned 0. The WSL source archive has no Git metadata, so its eight integration-relevant files were SHA-256 compared with this checkout before execution.
- Environment: WSL distribution `Ubuntu-24.04`, Ubuntu 24.04.5 LTS, systemd 255, Python 3.12.3, pytest 7.4.4. The runner service identity was `vst-runner` UID:GID `997:988`; the command worker was `vst-worker` UID:GID `999:989`; the signer service used `vst-signer` UID 995 and runner primary group 988.
- The command used a disposable synthetic Git repository in the unit's `/tmp` tmpfs. It contained copied runner/parser code, the owned lifecycle pytest module and helper, and a single `src/app.py` change. Its generated base/candidate Git IDs are synthetic and are not repository revisions.
- No production source or test files were edited. No operator key was read, invoked, or changed; no operator attestation was created. The existing untracked functional evidence file was preserved and excluded from this change.

## Exact command and outcome

Orchestration command:

```text
wsl -d Ubuntu-24.04 -- python3 /opt/vst-s2/run-manifest-integration.py
```

The temporary harness started the real signer service and invoked `tools.vst.runner.run_manifest_commands` from the copied source. The runner invocation used a synthetic v2 manifest with two mandatory test IDs and a required review slot; it ran one copied pytest node and one harmless worker-boundary command. The bounded command timeout was 15 seconds, the run deadline was 30 seconds, and the transient runner unit had a 45-second runtime ceiling.

Result: exit 0. The runner TestRun receipt was `PASS`; executed IDs were `t1` and `t2`, with no skipped IDs. Both commands exited 0. The diff gate was `PASS` for the single synthetic `src/app.py` change. The runner receipt signature and diff-gate signature were both present. The signer logged 26 requests, all with peer UID:GID `997:988`. The worker boundary command observed UID:GID `999:989` and signer socket denial with errno 13.

The first pytest diagnostic initially emitted its marker on the same line as pytest's progress dot, which the trusted parser correctly did not count. The temporary fixture was corrected to print a blank line before `PASS t1`; it then parsed `t1` and `t2` and the actual `run_manifest_commands` receipt passed. No parser assertion was weakened.

## Effective unit boundary

The runner was launched with these effective systemd properties:

```text
CPUQuotaPerSecUSec=1s
MemoryMax=2147483648
TasksMax=64
RuntimeMaxUSec=45s
TemporaryFileSystem=/run/user:ro
TemporaryFileSystem=/tmp:size=1G,mode=1777
TemporaryFileSystem=/dev/shm:size=64M,mode=1777
InaccessiblePaths=-/mnt/wsl -/mnt/wslg -/tmp/.X11-unix -/usr/lib/wsl -/usr/lib/modules -/var/tmp -/dev/mqueue -/run/lock -/run/shm
PrivateNetwork=yes
RestrictAddressFamilies=AF_UNIX AF_INET
NoNewPrivileges=yes
CapabilityBoundingSet=CAP_SETUID CAP_SETGID
AmbientCapabilities=CAP_SETUID CAP_SETGID
TMPDIR=/tmp
```

AF_INET was available only within the private network namespace so the inventory's egress smoke check could run. The signer service remained AF_UNIX-only. The actual worker reported `/tmp` as tmpfs of 1 GiB, mode `1777`, with `TMPDIR=/tmp`; `/dev/shm` as tmpfs of 64 MiB, mode `1777`; and `/var/tmp`, `/run/lock`, `/run/shm`, and `/dev/mqueue` inaccessible. The worker found zero other writable mount targets after these masks. The worker also found its home absent, could not traverse `/var/lib/vst`, could not write the source tree, could not write `/run/user`, and could not list `/usr/lib/modules`.

Host mount inventory classification observed in the real probe: Windows-drive mounts `0`; `/mnt/wslg` `1`; `/usr/lib/wsl*` `1`; `/usr/lib/modules` `1`; `/run/user` runtime mask `1`. Other filesystem counts: `binfmt_misc=1`, `cgroup2=1`, `configfs=1`, `debugfs=1`, `devpts=1`, `devtmpfs=1`, `ext4=1`, `fusectl=1`, `hugetlbfs=1`, `proc=1`, `rootfs=1`, `sysfs=1`, `tmpfs=10`, `tracefs=1`. **Correction:** fresh host mount metadata shows `/usr/lib/modules` is not a distinct host mount and resolves through the distro root `/` (`ext4`). The runner/worker namespace creates a tmpfs mask at `/usr/lib/modules`, and the worker confirmed it was inaccessible. These counts are sanitized; no personal mount paths are recorded.

## Probe and policy correlation

The integration's separate inventory diagnostic used:

- Source HEAD encoded in run ID: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- Run ID: `s2-280e2d0a613a0b70252c13ce7afe85f22734f7d1-e5-runmanifest-9d1ef6e1966a4f6080318e5c4a67e81b`.
- Nonce: `4e0e5aeeddbe4e9386b05827690e6713`.
- `docs/SANDBOX_SPEC.md` SHA-256: `7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997`.
- Raw JSON ruleset digest passed to the unit at integration time: `371e1ad145e0a83ac125ea8b3360820520bad1d211eff6eedc41fc4f6f82083c`.
- Evidence-body SHA-256: `8752be6e2188b6397c2e7c011a25dde3fa3790cfbfa46c5ab571c7b37127ac8e`.

The run ID binds the source revision by convention; the inventory schema has no separate code-head field. `AuthenticatedSigner` signed the runner inventory through the real local socket. The operator attestation was absent. The probe result remains `FAIL`: `external_egress_blocked=true` and socket enumeration was complete with zero sockets, but the checked policy properties `empty_external_allowlist` and `no_container_socket` were false without an operator attestation. This is not a failed runner lifecycle receipt.

Sanitized nftables summary from the dedicated distro: input and output policies default-drop, with loopback accepts only. The raw JSON ruleset digest at this integration was `371e1ad145e0a83ac125ea8b3360820520bad1d211eff6eedc41fc4f6f82083c`. A later independent operator check observed raw digest `e199643c67e156130c0ca0e3da8f707bdaaa35da9133c8270b703b82acb5fea0`; my subsequent recheck observed raw digest `340f65dd7b5751e2cfa0ceafe6eddb05c014cfafc518cd2340295c75df31cd7b`. The handle-stripped normalized semantic JSON currently hashes to `c88c93ba40791971895a4c6c719c8ae37d2b2b676d499fb5f5b7f8f0875cc8b0`, matching the operator's normalization and one-table/two-rule summary. The raw snapshots were not retained, so attribution of all raw digest differences solely to ephemeral handles is `NOT_VERIFIED`. The earlier raw digest in change 0059 (`dbaadc56201799974415694d76208d9931f151a3b31fa28dc52fd9f6d0f1bba0`) is a separate historical observation. Recompute raw and normalized fingerprints together at final probe time. No host/system mount approval was inferred from successful namespace checks.

## Acceptance matrix

| Item | State | Evidence and remaining acceptance | Dependency and next action |
|---|---|---|---|
| Real runner-to-worker integration | `PASS` | `run_manifest_commands` produced a signed PASS TestRun, executed `t1`,`t2`, both command exits were 0, and diff-gate signature/verdict were present. | No further action for this synthetic integration. Production runner-unit deployment remains a separate acceptance item. |
| Runner signer access and worker denial | `PASS` | Signer peer IDs were all `997:988`; worker `999:989` got errno 13. | Signer trust-root path/ACL must remain provisioned as recorded in change 0059. |
| Resource and scratch limits | `PASS` for this transient unit | Effective tmpfs, runtime, memory, CPU, task and mask properties were observed by the child worker. | Deployment owner must apply the reviewed properties to the actual production worker parent unit before claiming deployment acceptance. |
| WSL mount and socket inventory | `PASS` for attested library-level scope | Final inventory reported complete socket enumeration and zero paths, zero Windows-drive sources, and all seven checks true in the scoped runner unit. | Production worker-unit deployment remains a separate acceptance item. |
| E5 signed environment policy | `PASS` for the reserved run | The exact run/spec/nonce-bound operator-root attestation was supplied and independently verified together with the runner-signed final inventory. The earlier diagnostic remains historical `FAIL`. | No further action for this final probe. Do not interpret it as a claim that a production service is installed. |
| POSIX store anchor and startup recovery scenarios | `NOT_RUN` | This command exercised runner lifecycle and sandbox/resource boundaries, not the store-anchor acceptance set. | Run the owned safe POSIX anchor scenarios separately; process-kill/crash paths remain prohibited. |
| Process-kill, kill-table and mutation scenarios | `NOT_RUN` | Explicitly prohibited; none were invoked. | No action unless the operator changes that prohibition. |

## Final signed E5 probe

The previously reserved correlation was used exactly once. The public operator-root attestation is [s2-e5-operator-attestation.json](./s2-e5-operator-attestation.json); it contains only the signed attestation fields and signature, not the private inventory.

- Run ID: `s2-280e2d0a613a0b70252c13ce7afe85f22734f7d1-e5-final-0681fa0a871c4e40a2746c5c1c1d2eb4`.
- Nonce: `8024493e38ba44df96ee5f127a24b338`.
- Spec SHA-256: `7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997`.

The primary coordinator verified the private inventory before this final evidence update: `verify_fresh_probe` returned `true`, `verify_network_policy_attestation` returned `true`, the probe result was `PASS`, all seven checked properties were true, socket enumeration was complete with zero paths, and Windows-drive count was zero. The provided attestation matched this exact run ID, nonce, spec digest, policy digest, evidence digest, environment ID, and all three policy booleans.

- Final orchestration ran only in `Ubuntu-24.04`; the transient runner unit invocation was:

  ```text
  systemd-run --wait --pipe --collect --unit=s2-e5-final-probe --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/opt/vst-s2/source --setenv=VST_UNIT=s2-e5-final-probe.service --setenv=TMPDIR=/tmp --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property='InaccessiblePaths=-/mnt/wsl -/mnt/wslg -/tmp/.X11-unix -/usr/lib/wsl -/usr/lib/modules -/var/tmp -/dev/mqueue -/run/lock -/run/shm' --property=TemporaryFileSystem=/run/user:ro --property=TemporaryFileSystem=/tmp:size=1G,mode=1777 --property=TemporaryFileSystem=/dev/shm:size=64M,mode=1777 --property=PrivateNetwork=yes --property='RestrictAddressFamilies=AF_UNIX AF_INET' --property=NoNewPrivileges=yes --property='CapabilityBoundingSet=CAP_SETUID CAP_SETGID' --property='AmbientCapabilities=CAP_SETUID CAP_SETGID' /usr/bin/python3 /opt/vst-s2/final-e5-runner.py
  ```

  That script called `collect_inventory(RUN_ID, NONCE, network_policy_attestation=ATTESTATION)`, then `sign_inventory_with_service(inventory, signer_socket="/run/vst-signer/s2-final-e5-8024493e38ba/signer.sock")`. The signed JSON was captured privately rather than printed.
- Result: exit 0; probe `PASS`; signer request succeeded once with peer UID:GID `997:988`.
- Final raw nftables JSON SHA-256: `20d81857a511981ef8290ba4914c04e843796f119bbf6a0f9639205553f5ebfa2`. Handle-stripped normalized policy SHA-256: `c88c93ba40791971895a4c6c719c8ae37d2b2b676d499fb5f5b7f8f0875cc8b0`, matching the attestation.
- Seven checks: `automount_disabled=true`, `interop_disabled=true`, `no_container_socket=true`, `non_root=true`, `external_egress_blocked=true`, `loopback_canary=true`, `empty_external_allowlist=true`.
- Inventory facts: UID:GID `997:988`; container socket enumeration complete `true`, present count `0`; Windows-drive mount count `0`; WSL interop absent and disabled; 27 mount rows.
- Runner signature SHA-256: `bf05ab2d68880f4d64f5f585e4b6ae9c710ab00898cea4dccf815bde87740820`.
- Operator attestation signature SHA-256: `efbe3e659313415350d3dedb8766828b3cc1fa7600a15a578afe7be1a0e2b8f1`.
- The complete signed inventory remains private in WSL at `/var/lib/vst/private-e5-final-inventory-8024493e38ba44df96ee5f127a24b338.json`, owner `root:root`, mode `0600`; it was verified by the primary coordinator and is not committed. No operator key was accessed by the E2E executor.
- The operator-root HMAC and host-mount review were performed by Codex under the user's delegated autonomous WSL task. The E2E subagent did not read or invoke the operator key; the signed public attestation was provided by the primary coordinator. No independent human approval is claimed.

The reserved run ID, nonce and spec digest are consumed and must not be reused for a different probe or changed evidence bundle.

## Fresh pre-probe environment and mount review (2026-10-24 19:55 UTC)

This read-only inspection did not collect a new inventory, call the signer, or consume the reserved correlation above. It used only the named `Ubuntu-24.04` WSL distribution and transient unit `s2-preprobe-live-9ca127a2.service` with the same namespace/resource properties listed above.

- Environment identity evidence: `wsl -d Ubuntu-24.04`; `/etc/os-release` reported Ubuntu 24.04.5 LTS; systemd reported 255.4; Python reported 3.12.3. `/etc/wsl.conf` contained `systemd=true`, `[automount] enabled=false`, `[interop] enabled=false`, and `appendWindowsPath=false`. No other distribution was listed or accessed.
- nftables was active. At this snapshot, raw `nft -j list ruleset` SHA-256 was `9aa0d3519e0f49fe76eb5b0675dbb3204c065a51aee1800b8e784c193f6efa1f`. Recursively removing `handle` fields and hashing canonical JSON produced `c88c93ba40791971895a4c6c719c8ae37d2b2b676d499fb5f5b7f8f0875cc8b0`. The normalized snapshot had one table, input/output chains with `drop` policy, and two rules. Raw hashes vary between observations; raw snapshots were not retained, so a handle-only explanation is not verified. Recompute both hashes together at final-probe time.
- The effective scoped inspection unit reported `CPUQuotaPerSecUSec=1s`, `MemoryMax=2147483648`, `TasksMax=64`, `RuntimeMaxUSec=45s`, `PrivateNetwork=yes`, `RestrictAddressFamilies=AF_INET AF_UNIX`, `NoNewPrivileges=yes`, and only `CAP_SETUID`/`CAP_SETGID` in its capability bounding and ambient sets. It used `/run/user:ro`, `/tmp:size=1G,mode=1777`, `/dev/shm:size=64M,mode=1777`, and the masks listed above. In-unit checks denied access to `/usr/lib/modules`, `/var/tmp`, `/run/lock`, `/run/shm`, and `/dev/mqueue`; `/tmp` was tmpfs, 1 GiB, mode `1777`, and `TMPDIR=/tmp`.

### Sanitized mount inventory

The host view contained 31 mount rows. Exhaustive category/type counts were:

| Category | Mount types and counts |
|---|---|
| Distro root | `/` on `ext4` ×1 |
| OS pseudo-filesystems | `rootfs` ×1, `devtmpfs` ×1, `sysfs` ×1, `proc` ×1, `devpts` ×1, `binfmt_misc` ×1, `cgroup2` ×1, `hugetlbfs` ×1, `mqueue` ×1, `debugfs` ×1, `tracefs` ×1, `fusectl` ×1, `configfs` ×1 |
| Private runtime and memory | `tmpfs` ×7 |
| WSL host bridge | `tmpfs` ×2, `9p` ×1, `overlay` ×1 |
| Other system or redacted targets | `overlay` ×1 on a system target; `ext4` ×1 on a redacted `/mnt` target (device-backed); `overlay` ×2 on redacted `/mnt` targets; `tmpfs` ×1 on a redacted subtree target; `tmpfs` ×1 on a redacted `/mnt` target |

The two redacted `/mnt` overlay rows are overlay filesystems, not path-source binds. The redacted `/mnt` ext4 row is device-backed with filesystem root `/`, not a subtree bind. No source names or personal mount paths are retained. The host view had zero Windows-drive sources under the contract rule (`drvfs`, or `9p` with `aname=drvfs` and a drive-letter source).

The same scoped unit contained 27 rows:

| Category | Mount types and counts |
|---|---|
| Distro root | `/` on `ext4` ×1 |
| OS pseudo-filesystems | `rootfs` ×1, `devtmpfs` ×1, `devpts` ×1, `hugetlbfs` ×1, `proc` ×1, `binfmt_misc` ×1, `tmpfs` ×1 at an OS pseudo-filesystem subtree, `sysfs` ×1, `cgroup2` ×1, `fusectl` ×1, `configfs` ×1, `debugfs` ×1, `tracefs` ×1 |
| Private runtime and memory | `tmpfs` ×8 |
| WSL host bridge masks | `tmpfs` ×3 |
| System-path mask | `/usr/lib/modules` as `tmpfs` ×1 |
| Other system target | `tmpfs` ×1; exact target was redacted and is not independently verified |

The scoped unit had zero Windows-drive sources and no visible `9p`, `overlay`, or non-root `ext4` mounts. Its only device-backed filesystem was the distro root. The other rows were pseudo-filesystems, private tmpfs paths, or systemd masks. Thus the scoped worker view exposed no host/user-data bind mount; WSL bridge filesystems observed in the host view were masked from the worker.

### Coordinator rationale for bounded mount acceptance

The bounded rationale for this library-level acceptance is that a real `run_manifest_commands` child and a complete socket inventory were exercised inside the same scoped namespace; no persistent product service is needed for this acceptance. The observed host mount classes are the dedicated distro root, OS pseudo-filesystems, private runtime/memory filesystems, and WSL support bridges. Windows-drive sources were absent. The WSL bridge mounts and `/usr/lib/modules` were masked from the worker, and the child view had no host/user-data bind mount. This supports the bounded `no_container_socket` and `no_unapproved_host_paths` assessment for this run. Codex performed the host-mount review and used operator-root signing authority under the user's delegated autonomous WSL task; the public signed attestation was then provided to the E2E subagent by the primary coordinator. No independent human approval is claimed.
