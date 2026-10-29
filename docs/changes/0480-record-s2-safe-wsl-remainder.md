# Change 0480: Record the permitted S2 WSL remainder audit

## What changed

- Recorded a read-only E2E-role triage of remaining POSIX/WSL selectors at exact source/test HEAD
  `d5001797cb94113efd9a8dc26e4a15f2dc130976`.
- Classified each candidate that was excluded by the active worker/key, mutation, process-containment
  or service-provisioning boundaries.
- Kept the operator-owned configuration/authorization dependency explicit and preserved the final
  GPT-PM `NOT APPROVED` status.

## Why

After the S2 gate remained blocked, a safe selector was still worth checking before stopping. The
designated E2E role found no remaining POSIX/WSL selector that could run within the active limits.
The audit records the exact reason; it is not a test result or an inferred pass.

## Affected paths

- `docs/sdlc/evidence/s2-safe-wsl-remainder-audit-d500-20261028.md`
- `core/DECISION_LOG.md`, `core/BACKLOG.md`, `core/STATE.md`, `docs/sdlc/STATE.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- No tests or checks were executed by this change.
- The designated e2e-runner reports that no candidate fit the current restrictions; exact
  dispositions are in the linked audit.
- Source/test code remains at `d5001797cb94113efd9a8dc26e4a15f2dc130976`; subsequent commits are
  documentation-only.
- S2 Phase 8 remains blocked in PM Bridge. No service, key, Runner configuration, manifest, E5,
  network probe or prohibited selector was used.

## Next action and owner

The operator owns root-owned Runner configuration/credentials and authorization for the specific
worker/service scenarios. Codex coordinates; `e2e-runner` executes only selectors newly authorized
and within the accepted scope. Until those prerequisites exist, preserve the scenarios as
`NOT_RUN` and do not start S3.

## Commit attribution

Executor: Codex
