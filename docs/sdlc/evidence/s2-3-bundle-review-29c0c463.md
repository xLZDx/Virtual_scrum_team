# S2-3 exact bundle review — 2026-10-29

- PM Bridge request: `29c0c463-9d18-4c35-ae9d-8ed5331a4f70`.
- Correlated reply: `c6a9e139-1f02-5672-a053-99e0cd4c3741`.
- Verdict: **APPROVE — inactive artifact staging only**.
- Source HEAD: `ef465cd8790518e405164c82ec1598f843ae8a58`.

## Reviewed immutable identities

| Artifact | SHA-256 |
|---|---|
| Source plan | `59ebfee0435d7a34f4c09de6ef5269e08d7a6713a5e7301497ba754ef348d8e9` |
| Target inventory | `137e416c7a12870c658a9bc9712ac95af8b435f51b55b6d0ab793a9fcaf01908` |
| Declared source archive | `bc489ce6155e178b1f2c2ef6a9e8b88e78c3b3e991576107319c9b34c3543d44` |

The reviewed plan is V2, `UNSIGNED_REVIEW_CANDIDATE`, maps 44 source archive entries, and declares
activation `NOT_AUTHORIZED_BY_THIS_PLAN`. The inventory is bound to the source HEAD and was observed
at `2026-10-29T21:03:04Z` in the named `Ubuntu-24.04` WSL distribution. It recorded compiler
identity, inactive/not-found S2 units, no pending systemd jobs, absent new versioned destinations,
Windows-drive mounts absent, and interop/automount disabled. Store disposition remains `UNKNOWN`;
no Store path/content or key bytes were read.

GPT-PM found no BLOCKER or MAJOR within the requested stage-only scope. It approved publication of
only the immutable versioned runtime and worker-helper artifacts, subject to all installer checks
and the inventory remaining no older than five minutes at execution. The installer must fail closed
on any changed state, expired inventory, compiler mismatch, or other precondition failure.

## Explicit exclusions

This approval does not authorize selector changes, systemd unit writes/reload/start/enable, service
identity or configuration creation, Store read/initialization/migration, production keys/issuer,
E5 attestation, owner dispatch, production activation/deployment, S2 phase 8, or sprint closure.
A complete post-stage manifest requires a separate review before any selector mutation.

GPT-PM relied on the attached plan/inventory hashes and existing source/test evidence, including
the focused M-S2-3-03 approval. The declared archive itself was not attached; the Windows handoff
must regenerate it and verify the approved archive hash before extracting or installing.

The first reviewed inventory expired before execution and was not used. GPT-PM request
`3cc174e5-826c-4b06-843e-269f58f2031c` approved its replacement hash
`8910daf3f94d3e88e7de80eb39dc5c6bb65720cbc4b20855ffe2969a63de332b` while retaining this source
plan/archive and exact stage-only scope. The fresh inventory and correlated decision are recorded in
`s2-3-target-inventory-refresh-3cc174e5.md`; execution still requires the five-minute freshness
check.

The second inventory replacement also expired before staging and was not used. GPT-PM request
`5f47ce5d-3db2-4f22-9e72-cad81a139c9c` approved inventory SHA
`a3b6ea38103edfb0d25cab8ef3c2e405d8bcb2d08c0d16194668b4860095d054` as a further replacement,
retaining the source plan/archive and the same conditional stage-only authorization. The exact
reply, freshness check, and limits are recorded in
`s2-3-target-inventory-refresh-5f47ce5d.md`.
