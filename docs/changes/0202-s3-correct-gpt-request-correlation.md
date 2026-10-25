# Change record 0202: Correct S3 GPT-PM request correlation

## What changed

- Removed a PM Bridge request ID copied from other sprint context from the S3 bilingual status report.
- Marked S3 exact-head GPT-PM request/reply state as unconfirmed because PM Bridge mode, health, and job-status calls returned `Transport closed`.
- Updated change record 0201, the decision log, lesson log and generated document registry to keep evidence project-bound.

## Why

A request identifier is meaningful only with its canonical project/sprint and exact reviewed HEAD. Reusing an ID from another sprint cannot prove the S3 gate's send boundary, reply or approval.

## Evidence and limits

- Current-turn PM Bridge calls: `pm_bridge_mode_status`, `pm_bridge_health`, and `pm_bridge_job_status` each returned `Transport closed`.
- The S3 report records code/security/reliability findings at HEAD `86f59dc` and later documentation/source-audit commit `597259b`; those historical findings do not approve the later exact HEAD.
- No S3 PM review was sent during this correction. No S3 approval or merge is claimed.
- No tests, checks, build, candidate acquisition, installation or execution were performed.

## Ownership and next step

- GPT-PM owns the approval verdict; the operator remains accountable for the delegated S3 sprint.
- Codex executes the exact-head gate request after transport is restored.
- Technical service owner: not identified in the inspected S3 plan/backlog.
- Next: query S3-specific request state, prepare a complete gate for the current exact HEAD, then push/PR only after correlated approval.