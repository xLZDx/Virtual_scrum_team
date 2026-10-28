# Change 0508 — Record coordinator request-provenance amendment

Date: 2026-10-28

## What changed and why

GPT-PM reviewed the operator-directed coordinator proposal and returned `MODIFY — CONDITIONAL
DESIGN`: the local-only AF_UNIX adapter is acceptable in principle, but an authenticated coordinator
process alone cannot authorize an individual dispatch. This change records that finding and
submits a precise request-provenance amendment before source implementation.

## Correlated architecture decision

- Request: `dd7175f5-40f3-4714-932d-dc44dca55cc2`.
- Reply: `c064e8f2-eb6d-5945-97e1-f6f6c71d6b92`.
- PM Bridge job: `e93fd0e2-2097-4e6d-8728-756d7672a99b`.
- User turn: `3ecfb955-de1d-4d63-8e05-173846fa7275`.
- Result: `S2-DISPATCH-M01` remains MAJOR/OPEN; runtime remains disabled.

GPT-PM permits only the existing dispatcher-authorized grant request and signed-grant forwarding.
The coordinator may not create tasks/leases, select or enumerate work, sign grants, mutate Store,
add new Supervisor operations, or introduce another assignment authority. The Supervisor remains
the sole grant issuer and Store remains the task/lease authority.

## Proposed request-source binding

The revised proposal binds one exact request to an explicit operator instruction for Codex-owned
work and an already-existing Codex-owned task/live lease in the root Store. AF_UNIX peer credentials
and pinned process identity establish the caller; root-owned deployment configuration maps the
authenticated peer to `Codex`, never a caller-supplied principal. The request names one task, slot,
attempt, epoch, and unique request ID. Supervisor independently checks the current Store owner,
lease, epoch, manifest, budget, preflight and service generation. The coordinator has no list,
batch, task creation, lease creation, arbitrary command, path, model, or Store-path operation.
Identical request IDs may resolve only the same canonical request and existing same-generation
result; conflicting reuse, stale/revoked lease, duplicate launch, or cross-generation retry fails
closed. This precise amendment is submitted to GPT-PM; it is not yet approved.

## Provisioning and E5 boundary

GPT-PM conditionally permits reviewed root-only service configuration and locally generated service
keys inside the dedicated WSL2. It explicitly reserves independent probe authority and the operator
network-policy attestation key; Codex must not impersonate the operator. External production
credentials must originate with their authorized owner. No service activation is authorized by the
architecture decision.

Historical signed E5 records bind earlier source heads and do not qualify current HEAD. Fresh E5
must bind current source/runtime/helper and sandbox spec digests, a fresh run ID/nonce, authentic
probe signature, independent operator-authorized network-policy attestation, actual system
inventory, and service generation/cgroup/artifacts. Unobserved host controls remain
`NOT_VERIFIED`.

## Verification state and next step

- The proposal and amendment are recorded in
  `docs/sdlc/evidence/s2-coordinator-architecture-proposal-20261028.md`.
- No coordinator source, root configuration, credential, key, service state, test, migration, or E5
  run was created in this change.
- No tests, checks, builds, or migrations were run.

Codex owns implementation and safe WSL provisioning after the trust-boundary amendment is
adjudicated. GPT-PM owns the architecture amendment and exact-head review. The operator has no
current request to find external artifacts or provide secrets. Next: record the correlated
amendment decision; implement only if approved. Keep systemd disabled until its distinct runtime
authorization and acceptance evidence are satisfied. Keep restricted process/crash/mutation/policy
scenarios `NOT_RUN` and do not start S3 before S2 closes.
