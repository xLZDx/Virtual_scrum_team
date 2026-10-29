# Change 0515: Record current S2 runtime preparation inventory

## What changed

- Added a read-only metadata record for the selected Ubuntu-24.04 WSL2 runtime in
  `docs/sdlc/evidence/s2-runtime-config-preparation-20261028.md`.
- Updated the top-level S2 status in `core/STATE.md` to mark the prior proposal as superseded and
  show current source/runtime state.
- Corrected the `/opt/vst-runtime` observation: it is a symlink whose target is a root-owned mode
  `0755` directory. The symlink's displayed mode `0777` was not a reason to change runtime
  permissions.

## Why

The earlier baseline predates the Pub/Sub source and did not make the present owner-caller,
dispatcher-account and runtime-target state clear. The current inventory gives the config review
accurate observed values without reading secrets or changing the WSL environment.

## Contracts and decisions

- Current S2 Pub/Sub source scope has GPT-PM approval under request
  `b2d8f20e-4eb0-4a4c-98ec-13c1c9437279`; full S2 and `S2-DISPATCH-M01` remain open.
- A separate GPT-PM adjudication for the owner-caller and configuration boundary was sent under
  request `72e04f7e-aa30-4ee2-b079-1e6ee2e01107`; at record time its reply was not yet correlated.
- No UID/GID, owner principal, cgroup, key, current E5 or attestation is invented.
- S3 remains unstarted and work remains in the canonical repository; no per-sprint worktree was
  created.

## Verification and non-actions

- Read-only commands recorded distribution identity, WSL config, service-account metadata, service
  activity, and exact runtime symlink/target metadata.
- No key contents, private E5 contents, or unrelated checkout was read.
- No test, migration, key/config write, account creation, permission change, service operation,
  network-policy change, E5 probe, push, PR, merge, or deployment was performed.
