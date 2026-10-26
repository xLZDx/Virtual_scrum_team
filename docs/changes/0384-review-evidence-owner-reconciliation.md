# Change 0384: reconcile review findings in S2/S3 evidence records

## What changed

- Replaced the generic S2 WSL inventory command placeholder with the exact read-only commands and documented one failed quoting attempt before the successful mount inventory.
- Reconciled S3 technical-boundary wording so the boundary may remain unidentified while Codex owns its identification and evidence closure.

## Why

The documentation review of change 0383 found that the inventory observations were not directly reproducible from its command section and that S3 plan rows still described technical boundary ownership as `UNKNOWN`.

## Affected paths

- `docs/sdlc/evidence/s2-readonly-wsl-system-inventory-20261027.md`
- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`

## Verification state

- The exact commands were compared to the read-only commands issued in the current turn; they do not start a worker, change environment state, or run a network probe.
- Read-only documentation review reported two MINOR findings, both addressed here.
- No tests, checks, builds, or source changes were made.

## Decision

Continue to report worker identity transition, containment, firewall/egress, and persistent deployment as unproven. Do not equate assigning Codex ownership with evidence that the technical boundary has been discovered or approved.
