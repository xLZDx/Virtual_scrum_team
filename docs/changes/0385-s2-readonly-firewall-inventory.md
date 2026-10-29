# Change 0385: S2 read-only firewall inventory

## What changed

- Recorded Windows host firewall profile defaults and WSL2 nftables/route configuration from read-only queries.
- Reconciled the S2 gate and backlog references to state that WSL currently shows an output-drop policy, while end-to-end egress enforcement remains unverified and Windows outbound is allowed.

## Why

The S2 E5 acceptance needs evidence about system boundaries. Reading the active policies provides useful configuration facts without performing a network probe or changing system rules.

## Affected paths

- `docs/sdlc/evidence/s2-readonly-firewall-inventory-20261027.md`
- `docs/sdlc/STATE.md`
- `core/BACKLOG.md`

## Verification state

- Windows Domain, Private and Public profiles were enabled with inbound Block and outbound Allow.
- WSL2 nftables input/output chains showed `policy drop` and loopback-only accepts; IPv4 forwarding was 1 and IPv6 forwarding was 0.
- Queries were run in the existing repository at documentation baseline `9326f1781864cfa00115d0d0d3711943911347ac`.
- No tests, checks, builds, network probes, process/worker execution, rule changes, crash or mutation scenarios were run.
- S2 Phase 8 remains NOT APPROVED; prohibited scenarios remain `NOT_RUN`.

## Decision

Treat the firewall results as current configuration observations only. They do not establish immutable policy, restart persistence or complete host/network enforcement.
