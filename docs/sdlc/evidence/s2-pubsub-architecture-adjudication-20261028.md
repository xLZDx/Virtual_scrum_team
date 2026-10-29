# S2 Store-backed pub/sub architecture adjudication — 2026-10-28

## Correlation

- PM Bridge request: `274a8f94-9438-4f16-8dd4-98a8daf64b37`
- Job: `232e6309-ea24-405e-b8c6-771215cdde2e`
- User turn: `d82d2124-ec09-4e3b-a321-d767350ed73a`
- Correlated response: `67045970-e83f-538b-866e-ba97e9d269ec`
- Verdict: **ACCEPT — WITH BINDING CONSTRAINTS**

This later response supersedes the earlier point-to-point proposal and the pending provenance
amendment only for the narrow source-implementation scope below. It does not close
`S2-DISPATCH-M01`, approve runtime or migration application, authorize key creation or service
activation, or authorize push/PR/merge/deployment.

## Accepted source contract

1. The durable intent is one typed `DISPATCH_INTENT_ACCEPTED` event in the existing hash-chained
   Store; no external broker, general-purpose bus, user queue/spool, task enumeration, scheduler,
   or assignment authority is introduced.
2. A narrowly configured owner peer submits one exact request. Supervisor derives its principal
   from AF_UNIX kernel credentials, pidfd/process identity, exact cgroup, provisioned UID/GID, and
   root-owned mapping. Principal is never accepted from the request body.
3. The event binds request ID, task, TestRun slot, attempt, epoch, run ID, derived lease ID,
   principal, canonical payload digest, current service generation, and manifest digest.
4. Store accepts the intent atomically only when the authenticated principal owns the live task
   epoch and the named lease, manifest slot, consumed preflight, receipt position, and budget are
   current. The dispatcher receives only Supervisor-filtered intents through AF_UNIX and cannot
   access Store directly.
5. The dispatcher forwards only the exact accepted intent using a Supervisor-issued grant. It
   cannot create tasks or leases, choose work, sign grants, or supply commands, paths, worker
   identities, Store paths, or model provenance.
6. Delivery is at-least-once. Same request ID and same payload may replay within the same generation;
   request-ID reuse with changed payload, owner/lease/epoch/manifest/generation changes, and
   ambiguous launches fail closed. No automatic retry follows an ambiguous execution.
7. The event chain and generation-/peer-bound cursor must be verified. Source-level schema/migration
   code may be prepared, but migration application requires separate independent review and
   authorization.

## Work and gates

The decision authorizes source implementation and mapped source tests after coding. It does not
authorize applying the schema-v6 migration, generating or provisioning keys, enabling or starting
services, dispatching a real task, or claiming E5/S2 acceptance. Required evidence still includes
owner identity, durable event, delivery/replay, idempotency, revocation/generation fencing, grant
integration, negative tests, exact-head independent review, and separately authorized runtime
acceptance. The earlier request `9fcaec9d-c344-4388-b79a-1392fb6f4cb4` remains uncertain and is not
approval.

## Current evidence boundary

This record preserves the correlated decision and its scope. It does not assert that implementation,
tests, migration, configuration, service activation, or runtime acceptance have completed. Current
code and documentation status is tracked in `core/STATE.md`, `core/BACKLOG.md`, and the linked
change record.
