# S2 dispatch-owner client design — 2026-10-28

## Decision and scope

GPT-PM adjudicated the remaining S2-DISPATCH-M01 boundary under request
`72e04f7e-aa30-4ee2-b079-1e6ee2e01107`: `MODIFY — BOUNDED EXTENSION`. It retains the approved
Store-backed Pub/Sub source and permits a minimal in-repository owner-client that submits an
explicitly identified, already-authorized task instruction through the existing
`submit_dispatch_intent` Supervisor RPC. M01 remains MAJOR/OPEN until runtime integration and
provenance are proven.

## Initial callable contract (superseded by the signed contract below)

The source reviewer found a MAJOR in the first implementation: a public instruction constructor
accepted any task-shaped fields without proving the instruction came from a trusted authorized
producer. The initial remediation was a fail-closed stub that sent no RPC. This finding and focused
re-review are in
`docs/sdlc/evidence/s2-dispatch-owner-client-review-20261028.md`.

The original proposal considered an unsigned typed instruction containing only:

- `task_id`: existing task already assigned to the authenticated principal
- `slot`: existing manifest `TestRun` slot
- `attempt`: already authorized current attempt
- `epoch`: current Store-owned owner epoch
- `run_id`: current authorized run

That shape was not sufficient to establish provenance. A deterministic request ID derived from
task fields alone was also rejected because distinct authorizations could collide. The accepted
contract requires an issuer-supplied unique request ID bound inside the signed instruction.

The accepted implementation forwards the exact signed envelope to the authenticated
`SupervisorClient.submit_dispatch_intent` method and verifies the response binds back to each
submitted field. The principal is derived by Supervisor from the kernel-authenticated peer and
root-owned mapping; it is never accepted from client input.

## Authority boundary

The owner client does not enumerate or choose tasks, create or renew assignments/leases, choose a
worker, command, model, artifact, or execution endpoint, access Store directly, sign grants, hold
service keys, or implement a queue, spool, scheduler, or retry loop. Its caller must supply an
explicit already-authorized task instruction. Store and Supervisor continue to revalidate owner,
lease, attempt, epoch, manifest, preflight, generation, and budget.

At the initial review point, the module was a fail-closed stub because no trusted task instruction
source existed. The initial public-constructor MAJOR was resolved for that stub; the finding and
focused re-review are recorded in `s2-dispatch-owner-client-review-20261028.md`. GPT-PM later
accepted a purpose-specific signed instruction as provenance only with independent verification at
the root Supervisor. Source code may now verify and forward a signed envelope, but it remains
fail-closed whenever the pinned public-key registry is absent or the instruction is invalid. No
trusted production instruction signer/key is currently evidenced, so no production request can be
authorized. Source implementation and synthetic-fixture tests are permitted but still need their
exact-head review and mapped test evidence. `S2-DISPATCH-M01` remains open until source acceptance,
a genuinely authorized issuer/key, authenticated identity/cgroup provisioning, and the
owner-to-Supervisor-to-dispatcher-to-Runner runtime journey are independently evidenced.

## Provisioning boundary

GPT-PM permits preparing non-secret config templates, identity/socket/cgroup maps, artifact/hash
inventory, key-custody matrix, and fresh E5 collection procedure. Creating the missing OS account
requires an exact provisioning plan reviewed and separately authorized. Key generation/reuse,
Store migration, runtime installation, systemd enable/start, real dispatch, and an operator
attestation signed by Codex remain unauthorized. The WSL inventory is recorded separately in
`s2-runtime-config-preparation-20261028.md`; no host change is made by this design.

## Source acceptance required before enabling production submission

- Only the exact signed envelope described below is sent to Supervisor; no unsigned fallback.
- The issuer supplies the unique request ID; the same envelope preserves the same ID on replay.
- The client verifies signature and expiry, and the root Supervisor independently verifies the
  complete envelope and principal mapping.
- Principal, lease, worker, command, model, artifact, and grant values are absent from client input.
- Response must match the exact task, slot, attempt, epoch, run, and request ID sent.
- Store binds the exact signed envelope and key identity to idempotency and the hash-chained event.
- RPC errors propagate without automatic retry.
- Local tests prove only the client contract; production M01 remains open until runtime evidence.

## Later GPT-PM provenance adjudication (2026-10-29 local time)

GPT-PM selected the signed-instruction option with mandatory Supervisor-side verification. A
purpose-specific signed instruction is accepted as provenance only when the root Supervisor
independently verifies it; the owner client alone is not a trust boundary. The Store remains the
sole task/assignment/lease authority, and the instruction signer may authorize only one exact
request for already-assigned work. The instruction key must not create tasks, leases, assignments,
or grants.

The accepted signed envelope binds `version`, `algorithm`, `purpose`, `key_id`, `expires_at`, and
the six request values `request_id`, `task_id`, `slot`, `attempt`, `epoch`, and `run_id` using
canonical encoding and domain separation. The issuer supplies a unique 32-character lowercase
hexadecimal request ID; the client must not derive a replacement on replay. The root-controlled,
purpose-specific public-key registry maps each key to its permitted principal. Expiry, revocation,
principal, current Store owner/lease, preflight, budget, generation, and exact payload must all be
checked before a durable event. Missing trust configuration or any malformed/unsigned request
fails closed. The event and idempotency record must bind the exact signed instruction. No unsigned
compatibility fallback is permitted.

Source verifier work is authorized. Private-key generation/reuse, creating an instruction-signing
service, account creation, root configuration installation, migration application, service
activation, real dispatch, and E5 attestation are not authorized. The production client remains
unusable until a real independently authorized signer and pinned public key are provisioned; the
authorized source work does not close M01. The correlated decision is recorded in
`s2-owner-instruction-provenance-adjudication-20261029.md`.
