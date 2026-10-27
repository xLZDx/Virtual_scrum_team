# S2 read-only firewall inventory — 2026-10-27

## Scope and provenance

Read-only policy inspection on the current Windows host and the named `Ubuntu-24.04` WSL2 distribution. No network probe, rule change, child process, worker execution, or test was performed. This supplements, but does not replace, the WSL configuration/mount inventory in `s2-readonly-wsl-system-inventory-20261027.md`.

## Commands and observations

Windows PowerShell commands:

```powershell
Get-NetFirewallProfile -PolicyStore ActiveStore | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction
netsh advfirewall show allprofiles
```

Observed Domain, Private, and Public profiles were enabled, with inbound `Block` and outbound `Allow`. `netsh` reported `BlockInbound,AllowOutbound` for all three profiles and local firewall rules as GPO-store only. Therefore the host firewall configuration does not establish default-deny outbound traffic.

The same commands were repeated read-only on 2026-10-27 during the autonomous continuation. `Get-NetFirewallProfile -PolicyStore ActiveStore` again returned Domain/Private/Public `Enabled=1`, `DefaultInboundAction=4` (`Block`), and `DefaultOutboundAction=2` (`Allow`); `netsh advfirewall show allprofiles` again reported each profile `ON` with `BlockInbound,AllowOutbound`. A separate call omitting `-PolicyStore ActiveStore` returned raw enum value `0`; it is not used to override the ActiveStore/netsh observation. No network traffic was sent and no firewall rule was changed.

## Current-turn read-only host recheck — 2026-10-27

After change 0405 was committed as `77b319367b575b9f4c0a193e91405df507c886e6`, Codex ran only these host-status queries from `D:\Repo\Virtual_scrum_team`:

```powershell
Get-NetFirewallProfile -PolicyStore ActiveStore | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction
wsl --status
wsl --list --verbose
```

The current result again showed all three Windows firewall profiles enabled with inbound `Block` and outbound `Allow`; WSL default version `2`; `docker-desktop` running as WSL2; and `Ubuntu-24.04` stopped as WSL2. The queries did not start the stopped Ubuntu distribution or change firewall, WSL, or repository configuration. This confirms only a point-in-time host configuration/state observation. It is not a network, egress, worker-identity, process-containment, or persistence test and does not change S2 acceptance: Phase 8 remains `NOT APPROVED`, and prohibited scenarios remain `NOT_RUN`.

WSL read-only command:

```sh
ip -brief route
nft list ruleset
iptables -S
cat /proc/sys/net/ipv4/ip_forward
cat /proc/sys/net/ipv6/conf/all/forwarding
```

Run as `root` through `wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc ...`. A default route was present on `eth0`; the transient private gateway address is intentionally omitted. Nftables table `inet vst_s2_filter` had input and output chains set to `policy drop`; each chain accepts loopback only. `iptables` was unavailable. IPv4 forwarding was `1`; IPv6 forwarding was `0`.

## Acceptance disposition

The WSL ruleset is a point-in-time configuration observation. A second root-shell read-only inventory on 2026-10-27 again observed input/output `policy drop` and loopback-only accepts; it also observed IPv4 forwarding `1`, IPv6 forwarding `0`, and no packet was sent. It does not prove that the rules are immutable against the worker, persist across restart, cover every host/hypervisor path, or actually block all egress. The Windows host permits outbound traffic by default. Therefore complete S2 egress/system acceptance remains `NOT_VERIFIED`, and S2 Phase 8 remains NOT APPROVED. Prohibited process, crash, and mutation scenarios remain `NOT_RUN`.

Owner: Codex owns evidence recording and boundary reconciliation; the operator owns any provisioning or policy change; GPT-PM owns gate adjudication. Next: keep the distinction between observed WSL policy and end-to-end enforcement, and obtain permitted boundary evidence before requesting a new gate.
