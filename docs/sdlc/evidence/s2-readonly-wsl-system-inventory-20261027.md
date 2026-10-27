# S2 read-only WSL system inventory — 2026-10-27

## Scope and provenance

Read-only inventory from the canonical repository `D:\Repo\Virtual_scrum_team`. No source or test files were changed, no package was installed, and no network probe, child-process/worker execution, process termination, crash, or mutation scenario was run. The invoking shell used the existing `Ubuntu-24.04` WSL2 distribution as `root`.

## Observed facts

Commands executed from PowerShell in `D:\Repo\Virtual_scrum_team`:

```powershell
wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc 'cat /etc/wsl.conf'
wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc 'id; test -S /var/run/docker.sock && echo docker_socket=present || echo docker_socket=absent; grep -E "Max processes|Max open files|Max locked memory|Max address space" /proc/self/limits'
wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc "findmnt -rn -o TARGET,FSTYPE,SOURCE,OPTIONS | grep -E '^(/ |/tmp |/dev/shm |/mnt/c |/mnt/d )' || true; printf 'LISTENING_SOCKET_COUNT='; ss -H -lntup 2>/dev/null | wc -l; printf 'WSL_VERSION='; uname -r; printf 'USER='; id -un"
wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc "findmnt -rn -o TARGET,FSTYPE,SOURCE,OPTIONS | grep -E '^(/ |/tmp |/dev/shm |/mnt/c |/mnt/d )' || true; getent passwd vst-worker || true; getent passwd vst-runner || true; test -S /var/run/docker.sock && echo docker_socket=present || echo docker_socket=absent; ss -H -lntup 2>/dev/null | wc -l"
```

The first mount-filter attempt used an incorrectly quoted `awk` expression and failed without mount output; the subsequent `findmnt | grep` commands above are the successful observations used below. The environment was not changed between these read-only queries.

- Kernel identifies as WSL2: `6.6.114.1-microsoft-standard-WSL2`.
- `/etc/wsl.conf` reports `automount.enabled=false`, `interop.enabled=false`, and `appendWindowsPath=false`.
- The queried mount inventory showed `/` on ext4 and `/dev/shm` on tmpfs; no `/mnt/c` or `/mnt/d` mount was present in the queried mount output.
- `/var/run/docker.sock` was absent.
- The queried network socket inventory counted 13 listening sockets. This is a point-in-time count, not an egress or firewall test.
- The command identity was `root` (UID 0). Accounts `vst-worker` (UID 999) and `vst-runner` (UID 997) exist, but this inventory did not execute as either account and does not prove the authorized identity transition.
- The observed `/proc/self/limits` reported 127709 max processes, 10240 soft / 1048576 hard open files, 64 MiB locked memory, and unlimited address space. These are process limits for this root shell, not proof of sandbox resource enforcement.

## Acceptance disposition

This inventory is supplemental system evidence only. It does not prove worker isolation, process containment, filesystem write exclusion, full egress enforcement, persistent deployment, host firewall/hypervisor policy, or Windows Job Object behavior. S2 Phase 8 remains NOT APPROVED. Prohibited process, crash, and mutation scenarios remain `NOT_RUN`; do not infer PASS from this inventory. The prior 81-case safe Windows/WSL subset and its 86-ID registry denominator remain documented in `s2-safe-platform-subset-6ca2ee0-20261026.md`.

Owner: Codex owns evidence recording and gate reconciliation; the operator owns any authorization to broaden process/crash/mutation scope; GPT-PM owns gate adjudication. Next: preserve these limits and request another gate only after all mandatory permitted evidence and any required explicit waiver are recorded.

## Windows/WSL host state screen — 2026-10-27

Additional read-only commands from the same canonical checkout:

```powershell
Get-ComputerInfo | Select-Object WindowsProductName,WindowsVersion,OsBuildNumber,OsArchitecture
Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction
wsl --status
wsl --list --verbose
```

Observed output reported Windows 10 Pro, version `2009`, build `26300`, 64-bit; WSL default version `2`; `docker-desktop` running as WSL2; and `Ubuntu-24.04` stopped as WSL2 at the time of `wsl --list --verbose`. The firewall command without an explicit policy store returned raw enum defaults of `0`; the ActiveStore plus `netsh` commands documented in `s2-readonly-firewall-inventory-20261027.md` are retained for effective-profile interpretation.

## Ubuntu 24.04 static system recheck — 2026-10-27

The distribution was listed `Stopped` immediately before this read-only inventory. Running `wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc ...` started it to permit configuration inspection; the following `wsl --list --verbose` listed it `Running` afterward. No package, file, configuration, account, firewall rule, or network state was changed intentionally. The commands executed were:

```sh
id
uname -r
cat /etc/wsl.conf
findmnt -rn -o TARGET,FSTYPE | grep -E '^(/ |/tmp |/dev/shm |/mnt/c |/mnt/d )'
getent passwd vst-worker vst-runner
ls -l /var/run/docker.sock
nft list chain inet vst_s2_filter input
nft list chain inet vst_s2_filter output
cat /proc/sys/net/ipv4/ip_forward
cat /proc/sys/net/ipv6/conf/all/forwarding
```

Observed identity was `root` (UID 0), kernel `6.6.114.1-microsoft-standard-WSL2`, and `/etc/wsl.conf` had systemd enabled, automount disabled, interop disabled, and Windows PATH append disabled. The queried mounts were `/` on ext4 and `/dev/shm` on tmpfs; no Windows drive mount appeared in that filtered output. Accounts `vst-worker` (UID 999/GID 989) and `vst-runner` (UID 997/GID 988) exist; this did not execute as either account. `/var/run/docker.sock` was absent. The nftables input and output chain policies were `drop` with loopback-only accepts. IPv4 forwarding was `1`; IPv6 forwarding was `0`.

These are point-in-time static observations from a root shell. No packet, DNS, egress, process-containment, or worker-identity test was performed. Starting the stopped WSL distribution changed its runtime state to Running; no persistent system configuration was altered. S2 remains NOT APPROVED.
