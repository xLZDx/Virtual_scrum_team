# Change 0486 — Record S2 dispatch architecture adjudication

Date: 2026-10-28

## What and why

Recorded GPT-PM's correlated architecture decision for `S2-DISPATCH-M01`. The decision confirms
that dispatch must remain disabled until an existing trusted coordinator and authenticated caller
are identified. It prevents the unresolved production integration from being filled with an
unreviewed second assignment authority.

## Decision provenance

PM Bridge request `fca31d62-2d04-4d22-9753-103b748b5ae9`, correlated reply
`73847bec-1421-53e7-8c8d-ffb98ef240e5`, job `a1d2be1d-1d39-4edc-a369-76772cb8587c`, user turn
`f4ab4233-d63b-481a-abfd-a5bc1e93282b`; `correlated: true`. GPT-PM selected Option A: keep
production dispatch fail-closed and disabled; do not add a scheduler, independent authority, CLI,
queue, spool, synthetic identity or validation bypass. The reply explicitly leaves
`S2-DISPATCH-M01` MAJOR/OPEN and S2 NOT APPROVED.

## Affected acceptance and next evidence

Closure requires an exact existing coordinator source path/revision/callsite, durable task/lease
authority, authenticated caller/IPC boundary, traceable assignment-to-grant path, negative tests,
and an exact-head independent gate. If the source is outside this repository, the operator must
identify its exact path before read-only inspection. No neighboring checkout was searched and no
production code changed.

## Verification state

- Recorded the correlated response in `docs/sdlc/evidence/s2-dispatch-architecture-adjudication-20261028.md`.
- No code or tests changed or ran for this documentation-only record.
- S2 remains open; no S3 work, PR, merge or deployment was started.

## Ownership

Codex owns in-scope source discovery and evidence coordination. The operator owns identifying any
external source path and providing the actual operational artifacts. GPT-PM owns architecture and
exact-head adjudication. Next: continue only evidence-backed S2 work; keep dispatch disabled until
the required existing coordinator evidence is available.
