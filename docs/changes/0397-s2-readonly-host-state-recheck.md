# Change 0397: record permitted S2 host-state recheck

## What changed

- Added current read-only Windows/WSL distribution-state observations to the S2 system inventory.
- Repeated the effective Windows ActiveStore and `netsh` firewall profile inventory; the reported inbound Block/outbound Allow configuration is unchanged.

## Why

The continuation requested additional permitted S2 system evidence while preserving prohibited process, crash, mutation, and network scenarios as unrun.

## Affected paths

- `docs/sdlc/evidence/s2-readonly-firewall-inventory-20261027.md`
- `docs/sdlc/evidence/s2-readonly-wsl-system-inventory-20261027.md`
- `docs/changes/0397-s2-readonly-host-state-recheck.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Read-only commands: `Get-ComputerInfo`, `Get-NetFirewallProfile` (including `-PolicyStore ActiveStore`), `wsl --status`, `wsl --list --verbose`, and `netsh advfirewall show allprofiles`.
- Observed Windows 10 Pro build `26300`, WSL version 2, and `docker-desktop` running. `Ubuntu-24.04` was stopped at the initial listing, then started by the static inspection and listed running afterward.
- ActiveStore and `netsh` reported the three firewall profiles enabled, inbound Block, and outbound Allow. No network traffic or rule modification occurred.
- The Ubuntu inventory ran as root and observed no queried Windows drive mount or Docker socket, `vst-worker` and `vst-runner` account records, input/output nftables drop policies with loopback-only accepts, and IPv4/IPv6 forwarding flags `1`/`0`.
- No tests, checks, builds, process scenarios, policy selectors, network probes, candidate acquisition or execution were performed.
- No source/test code changed; the protected untracked S2 evidence file was not modified or staged.

## Decision

Treat these as point-in-time host configuration observations only. They do not prove WSL provisioning for the S2 worker, egress enforcement, containment, persistence, or Phase 8 acceptance. Starting Ubuntu changed its runtime status from Stopped to Running to perform the allowed static inventory; no persistent configuration was intentionally changed.
