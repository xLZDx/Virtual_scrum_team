# Change 0507 — Record operator-directed coordinator architecture proposal

Date: 2026-10-28

## What changed and why

The operator directed Codex to build the missing coordinator and prepare root-owned configuration
and fresh E5 evidence. Existing project policy requires architecture adjudication before adding a
new production caller after GPT-PM previously prohibited a new assignment authority. This record
captures a minimal proposal for adjudication before source implementation.

## Current evidence and affected contracts

- Source/design proposal: `docs/sdlc/evidence/s2-coordinator-architecture-proposal-20261028.md`.
- Current baseline when prepared: repository HEAD `70f8953c69276fa9cbc00f2695dde2ca5aded1cc`.
- Existing code contains a root Supervisor, Store task/lease checks, signed one-use grants,
  persistent runner, service templates, and `dispatch_authorized_manifest_run`; the latter is a
  library function and not a runnable production caller (`tools/vst/systemd/README.md`).
- Read-only `wsl.exe --list --verbose` showed `Ubuntu-24.04` present as WSL2 and stopped. A
  read-only WSL query found `/etc/vst-runner/runner-service.json`,
  `/etc/vst-runner/supervisor-service.json`, and `/etc/vst-runner/signer-service.json` absent;
  the three services were disabled and inactive. No configuration or service state was changed.
- Historical E5 records exist for earlier source heads, including `f0bbac8` and `280e2d0`; they do
  not prove fresh E5 acceptance for the current source head.

## Proposed design boundary

The proposed coordinator is local-only and forwards bounded requests to the existing root
Supervisor. It creates no tasks, assignments, leases, independent queue, or spool. The Store remains
the only durable task/lease authority, and the Supervisor remains the only grant issuer. The
coordinator is authenticated through a fixed Unix peer identity and service cgroup, cannot accept
caller-selected commands, executable paths, UIDs, or Store paths, and has no network or fallback
execution path. Missing or stale root configuration/helper/runtime artifacts/fresh E5 causes
refusal. Fresh signatures cannot claim unobserved host or firewall properties.

## Verification state

- One architecture proposal was sent to GPT-PM under request
  `dd7175f5-40f3-4714-932d-dc44dca55cc2`; the response is pending.
- The earlier GPT-PM request `c775dfb6-563b-4c9c-a589-ddd694c359ab` ended uncertain after its
  wait deadline; no correlated reply was present in the project message log at last reconciliation.
- No coordinator source, key, root configuration, service state, test, migration, or E5 run was
  changed or created by this proposal.

## Ownership and next step

Codex owns the proposal, implementation, and safe local provisioning after the boundary is
adjudicated. GPT-PM owns architecture adjudication and exact-head review. The designated test
agents own required tests. Next: record GPT-PM's correlated decision; if approved, implement only
the accepted trust boundary, complete all source coding, then run permitted tests/reviews and fresh
E5 evidence. Keep restricted process/crash/mutation/policy scenarios `NOT_RUN` and keep S3
unstarted until S2 closes.
