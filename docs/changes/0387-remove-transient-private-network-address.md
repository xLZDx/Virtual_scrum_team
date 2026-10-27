# Change 0387: remove transient private gateway detail

## What changed

- Replaced the transient private WSL gateway address with the acceptance-relevant observation that a default route exists on `eth0`.
- Recorded the public-evidence minimization decision and lesson.
- Regenerated the document registry from the staged Markdown index.

## Why

The exact gateway address was environment-specific and unnecessary to support the S2 firewall conclusion. Removing it reduces incidental network-topology disclosure.

## Affected paths

- `docs/sdlc/evidence/s2-readonly-firewall-inventory-20261027.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Read-only source diff confirms the address is no longer present in the tracked evidence.
- No tests, checks, builds, network probes, or system configuration changes were run.
- S2 egress and containment remain `NOT_VERIFIED`; prohibited process/crash/mutation scenarios remain `NOT_RUN`.

## Decision

Keep only network configuration facts needed to explain acceptance status; do not publish transient private routing details.
