# Change 0466: Record bounded S2 WSL namespace snapshot

## What changed

- Added a current exact-source-head record for a bounded, read-only WSL sandbox namespace observer.
- Updated the POSIX cgroup design and S2 state/backlog to distinguish the exact-head `flock`/empty-scope evidence from the still-unverified persistent service and complete E5 acceptance.
- Kept the historical signed E5 run bound to `280e2d0`; no prior signature or nonce was reused.

## Why

The design status still described lock and empty stale-scope runtime evidence as pending after those facts had been recorded for `a6ea0dc`. A new observer supplied limited mount-visibility evidence, but did not run the E5 preflight or produce signed inventory. The records need to state both facts without upgrading partial evidence to acceptance.

## Affected contracts and paths

- `docs/sdlc/evidence/s2-current-namespace-snapshot-a6ea0dc-20261027.md`
- `docs/sdlc/evidence/s2-task-acceptance-a6ea0dc-20261027.md`
- `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`
- `core/BACKLOG.md`, `core/STATE.md`
- `docs/sdlc/STATE.md`, `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Source/test HEAD: `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`; repository documentation HEAD before this documentation change: `a2ab23aa4ad65ec2a7f2565035ab457b74c38b3e`.
- Read-only WSL observer ran as UID/GID `997:988` in a transient bounded systemd unit and exited 0. It reported 29 mount rows, zero Windows-drive mounts, no `drvfs`, `9p`, `overlay`, or non-root `ext4` candidates, and the specified masked paths were not readable/searchable.
- No product code, tests, network probes, signing keys, signatures, migrations, or persistent systemd units were used or changed by this evidence run.
- A separate read-only unit-name inventory found no matching `vst`, `runner`, or `worker` service names; this does not establish service absence under arbitrary names. No persistent service deployment or stable delegated-parent behavior is proven.
- Full E5 exact-head preflight, fresh run-bound operator attestation, and runner-signed inventory remain outstanding. Windows nested Job Object, populated stale-scope cleanup, crash/restart and policy-restricted scenarios remain `NOT_VERIFIED` or `NOT_RUN`.
- No tests/checks/build/CI/migration were run for this documentation update. The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not modified or staged.

## Decision and ownership

- Decision: retain S2 `NOT APPROVED`; treat this as supplemental mount evidence only.
- Codex owns evidence reconciliation and local Git. The operator remains the attestation/signature authority and owns any persistent service provisioning or policy changes. GPT-PM owns the exact-head S2 adjudication. Test execution remains with `e2e-runner` and `functional-test-reviewer`.
- No S3 source work, push, PR, or merge is authorized by this change.

Executor: Codex
