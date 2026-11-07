# S2-DISPATCH-M01 architecture adjudication — 2026-10-28

## Correlation and scope

- Project: `virtual_scrum_team`
- Scope: active Sprint S2 only
- Declared repository HEAD: `bcb2b65eec9d23076d447f996ecb6ace0e5f4c0f`
- PM Bridge request: `fca31d62-2d04-4d22-9753-103b748b5ae9`
- Correlated reply: `73847bec-1421-53e7-8c8d-ffb98ef240e5`
- PM Bridge job: `a1d2be1d-1d39-4edc-a369-76772cb8587c`
- User turn: `f4ab4233-d63b-481a-abfd-a5bc1e93282b`
- Correlation: verified by PM Bridge job status (`correlated: true`).

## Decision

GPT-PM confirmed Option A: production dispatch remains fail-closed and disabled until an existing,
trusted production coordinator and its authenticated assignment identity are identified and
verified. The absence of a known production caller is an unresolved integration dependency; it
does not authorize a second assignment authority.

The reply explicitly does not authorize a new scheduler, independent assignment authority,
production dispatch CLI/queue/spool, invented caller identity, bypass of task/lease ownership or
Supervisor/Store validation, or treating a library helper as production integration. A different
coordinator architecture needs a separate adjudication before implementation.

## Minimum reconsideration evidence

1. Exact existing production repository, file, commit and callsite.
2. Existing durable task/lease authority.
3. Authenticated caller identity, permitted operations and IPC boundary.
4. Traceable assignment-to-dispatch-to-grant path through Supervisor validation and Store.
5. Negative tests for unauthorized caller, stale lease, duplicate request and generation mismatch.
6. Exact-head independent GPT-PM verification.

If the source is outside `D:\Repo\Virtual_scrum_team`, its exact path must be identified before
read-only review. No neighboring checkout was searched.

## Effect on S2

- `S2-DISPATCH-M01`: MAJOR / OPEN; not closed.
- Production dispatch: disabled / fail-closed.
- New coordinator implementation: not authorized by this decision.
- S2: NOT APPROVED; unchanged.
- S3: blocked until S2 closes.
- PR, merge and deployment: no approval granted.

This is a scoped architecture adjudication, not a fresh full-repository audit. GPT-PM relied on the
three attached records and did not independently fetch the declared HEAD. Full response and
correlation metadata remain in PM Bridge under the request/reply/job IDs above.
