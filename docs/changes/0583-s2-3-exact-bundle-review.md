# S2-3 exact bundle review and bounded stage authorization

## Scope and evidence

- Task: S2-3 immutable runtime bundle and bounded WSL qualification preparation.
- Source/test finding M-S2-3-03 was closed by focused GPT-PM approval on HEAD
  `ef465cd8790518e405164c82ec1598f843ae8a58` (request
  `17aa39d9-fb95-4d27-ba94-858fe1cc954d`).
- The exact source plan and read-only target/compiler inventory were generated from that code HEAD.
- GPT-PM request `29c0c463-9d18-4c35-ae9d-8ed5331a4f70`, correlated reply
  `c6a9e139-1f02-5672-a053-99e0cd4c3741`, approved only inactive artifact staging for the exact
  plan/inventory/archive identities documented in
  `docs/sdlc/evidence/s2-3-bundle-review-29c0c463.md`.
- No tests were run in this documentation/preparation change; the mapped direct regression is
  recorded in `docs/sdlc/evidence/s2-3-existing-runtime-regression-043980f.md`.

## Inventory and limits

The named WSL distribution is Ubuntu 24.04. Read-only inventory observed disabled Windows interop
and automount, no Windows-drive mounts, the existing selector still pointing to the prior immutable
runtime, all six S2 units inactive or not found, no pending systemd jobs, and absent fresh versioned
runtime/helper destinations. Store disposition remains `UNKNOWN`; no Store content or key material
was inspected. The inventory must remain within the installer's five-minute freshness limit.

## Current disposition and next action

Source finding M-S2-3-03 and the exact pre-stage bundle review are accepted. The only newly approved
operation is inactive stage-only publication of the exact versioned runtime and helper after the
installer rechecks all conditions. Selection, unit writes or activation, Store changes, identities,
configuration, production keys/E5 and production remain excluded. After staging, collect the full
read-only installed tree/helper manifest and obtain its separate GPT-PM review. S2-3 stays current;
S2-4 must not start yet.

## Freshness correction

The initial inventory authorized by request `29c0c463-9d18-4c35-ae9d-8ed5331a4f70` expired before
execution and was not used. Request `3cc174e5-826c-4b06-843e-269f58f2031c` approved refreshed
inventory SHA `8910daf3f94d3e88e7de80eb39dc5c6bb65720cbc4b20855ffe2969a63de332b`, observed at
`2026-10-29T21:08:15Z`; it retained the same plan/archive and stage-only scope. The updated
correlated reply is documented in `docs/sdlc/evidence/s2-3-target-inventory-refresh-3cc174e5.md`.
The five-minute age limit still applies at execution.

The source-plan artifact uses path-specific `-text -eol` attributes so Git preserves the exact
approved raw bytes and SHA-256 across commit/checkout; runtime handoff checks both the raw plan
digest and the committed Git blob identity before use.

The second refreshed inventory expired before staging and was not used. GPT-PM request
`5f47ce5d-3db2-4f22-9e72-cad81a139c9c` approved replacement inventory SHA
`a3b6ea38103edfb0d25cab8ef3c2e405d8bcb2d08c0d16194668b4860095d054` at observation time
`2026-10-29T21:14:10Z`; the correlated verification occurred 49 seconds later. The reply and exact
scope are recorded in `docs/sdlc/evidence/s2-3-target-inventory-refresh-5f47ce5d.md`. The new
inventory has not yet been used; verify freshness and all current blobs before stage-only.
