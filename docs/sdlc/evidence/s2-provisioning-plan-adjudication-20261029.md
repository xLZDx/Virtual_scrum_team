# S2 provisioning-plan adjudication — 2026-10-29

## Correlated review

GPT-PM returned **MODIFY** for the non-secret S2 root/runtime provisioning plan. The review was
design-only against baseline `0dac9d58a3dd5bf779e1a2908a1ff2929ef5e69f`; it did not inspect the
live repository or host. The plan attachment SHA-256 at send time was
`f7dec5535f825d14f2daf4ff1f3b2742322c634f31d9cd6dd491867cc26a8b55`. Correlation: request
`d4bb9a93-90ec-4a7e-90a1-0f3c463cd18d`, user turn
`71b96989-1cc9-4d77-8889-357b1e475bbd`, reply
`7f061c3b-b73c-4d55-9da7-4d917a789e9a`, job
`429cd588-f403-48a9-8544-53fae729f6f3`.

The adjudication recorded **0 confirmed BLOCKER, 2 MAJOR and 2 MINOR** findings:

| Finding | Severity | Required correction |
|---|---|---|
| `S2-PROV-M01` | MAJOR | Give `vst-dispatch-owner` a distinct primary GID; retain `vst-supervisor-client` only as a supplementary shared-socket group. Recheck every proposed numeric/name identity immediately before any separately authorized creation. |
| `S2-PROV-M02` | MAJOR | Supply an exact non-installed owner-service unit, fixed executable/module and runtime provenance, fixed service identity/cgroup, AF_UNIX-only boundary, no Store write access, read-only public trust registry, fail-closed signed-instruction behavior, and no signing, assignment authority or retry after ambiguity. |
| `S2-PROV-m01` | MINOR | Complete numeric and name-based UID/GID inventory, including the newly selected owner primary GID and supplementary memberships. |
| `S2-PROV-m02` | MINOR | Provide exact field-by-field Supervisor, Runner, signer, dispatcher and owner configuration inventory, marking unavailable values instead of guessing. |

The review accepted the proposed Supervisor socket design and directed that the existing Runner
socket/identity contract remain unchanged. It did not authorize account or group creation, `/etc`
writes, key generation/reuse, signer creation, migration, runtime installation, service activation,
real dispatch, network changes, E5 attestation, push, PR or merge. The signed-instruction
architecture adjudication is unchanged.

## Current remediation record

On 2026-10-29, Codex performed read-only `/usr/bin/getent` lookups in `Ubuntu-24.04`. Each query
for dispatcher/owner usernames and groups, UIDs 980 and 981, and GIDs 982, 983 and 984 returned
empty output with exit code 1. This is a point-in-time observation, not a reservation; all values
must be rechecked before any separately authorized account creation.

Codex revised the plan candidate to owner UID 980 with distinct primary GID 982 and supplementary
socket GID 984; added `dispatch_owner_service.py` and exact non-installed
`vst-dispatch-owner.service` / `.socket` templates; updated the runtime artifact allowlist; and
added a field-level configuration matrix. The revised source and plan still require mapped tests,
specialist review, and a new exact-plan GPT-PM review. The new service is a relay only: Store and
Supervisor retain assignment authority, and production dispatch remains fail-closed without a
genuine authorized instruction issuer and pinned public key.

No test, check, build, CI, migration, account/group creation, root configuration write, key
operation, runtime installation, service activation or dispatch was performed as part of this
adjudication remediation.

