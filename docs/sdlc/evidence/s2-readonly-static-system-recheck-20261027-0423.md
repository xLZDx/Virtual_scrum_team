# S2 Windows and WSL static system recheck — 2026-10-27

## Scope and provenance

Read-only configuration snapshot from the canonical checkout `D:\Repo\Virtual_scrum_team`, branch `s4-canonical-continuation`, repository HEAD `c528913afc43223d8a5ff81916f349f97001d36c`. No source/test file, package, policy, firewall rule, or WSL configuration was changed. No network packet, DNS/egress probe, child-worker acceptance scenario, process termination, crash/recovery, mutation, or test was run.

## Commands and observations

Windows PowerShell:

```powershell
Get-ComputerInfo | Select-Object WindowsProductName,WindowsVersion,OsBuildNumber,OsArchitecture
Get-NetFirewallProfile -PolicyStore ActiveStore | Format-Table -Property Name,Enabled,DefaultInboundAction,DefaultOutboundAction -AutoSize
netsh advfirewall show allprofiles
wsl.exe --status
wsl.exe --list --verbose
```

Observed Windows host: Windows 10 Pro, version `2009`, build `26300`, 64-bit. All Domain, Private, and Public firewall profiles were enabled with inbound `Block` and outbound `Allow`; `netsh` reported `BlockInbound,AllowOutbound` and local rules as GPO-store only. WSL default version was 2. Before the explicit Linux inventory, `docker-desktop` was Running and `Ubuntu-24.04` was Stopped.

Read-only Linux inventory, invoked as the existing distro's root account:

```sh
id
uname -r
cat /etc/wsl.conf
findmnt -rn -o TARGET,FSTYPE,SOURCE,OPTIONS | grep -E '^(/ |/tmp |/dev/shm |/mnt/c |/mnt/d )'
getent passwd vst-worker vst-runner
ls -l /var/run/docker.sock
nft list chain inet vst_s2_filter input
nft list chain inet vst_s2_filter output
cat /proc/sys/net/ipv4/ip_forward
cat /proc/sys/net/ipv6/conf/all/forwarding
```

Observed identity was `root` (UID 0); kernel `6.6.114.1-microsoft-standard-WSL2`. `/etc/wsl.conf` had `systemd=true`, `automount.enabled=false`, `interop.enabled=false`, and `appendWindowsPath=false`. Filtered mount output showed `/` on ext4 and `/dev/shm` on tmpfs, with no `/mnt/c` or `/mnt/d` result. Accounts `vst-worker` (UID 999/GID 989) and `vst-runner` (UID 997/GID 988) exist; neither was used. `/var/run/docker.sock` was absent. Both observed `inet vst_s2_filter` input and output chains had `policy drop` and accepted loopback only. IPv4 forwarding was `1`; IPv6 forwarding was `0`.

The command started `Ubuntu-24.04` to read its configuration; an immediate WSL listing showed it Running. A later point-in-time `wsl.exe --list --verbose` showed `Ubuntu-24.04` Stopped again. No persistent configuration change was made intentionally.

## Acceptance disposition

These are static, point-in-time configuration observations from a root shell. They do not prove that a worker cannot alter policy, that egress is blocked end-to-end, that host/hypervisor paths are contained, or that the named UID transition works. Windows outbound remains Allow. No Windows Job Object nesting, POSIX process-group/descendant cleanup, child identity acceptance, network probe, process-kill, crash/resume, or mutation scenario was performed. S2 Phase 8 remains `NOT APPROVED`; prohibited scenarios remain `NOT_RUN`.

Owner: Codex records permitted read-only evidence and maintains acceptance boundaries; `e2e-runner` owns required test scenarios when permitted; operator owns any decision to broaden restricted scope. Next: keep prohibited scenarios `NOT_RUN` and continue only permitted evidence that can materially close a named S2 acceptance gap.
