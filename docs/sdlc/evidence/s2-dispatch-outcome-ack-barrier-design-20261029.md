# S2 dispatch outcome acknowledgement barrier — proposed design

**Status:** GPT-PM accepted the design and authorized implementation. The source change is now in
the working tree; focused tests, fresh reviews, and exact-head adjudication remain open.

## Prior GPT-PM adjudication

The initial option-3 proposal received `MODIFY` with two MAJOR findings. Correlation: PM Bridge
request `7d9c5f34-1a2b-4c8d-9e6f-0522b4a9c107`, user turn
`78e8189a-834f-4398-9cf3-8cb1f3301550`, reply `26ed29cd-0103-4de3-a081-16496ed714a6`, job
`5e9156cb-4ba9-45ca-a9d7-e8bca731b29b`.

- `S2-PROV-M03-A`: acknowledgement must mean relay verified and completed local response
  forwarding, not proven caller receipt. It must bind request ID, authenticated principal,
  canonical signed-instruction payload digest, accepted event sequence, canonical Supervisor result
  SHA-256, and service generation. Supervisor derives/verifies those values; duplicate exact ack is
  idempotent and conflicting ack fails closed.
- `S2-PROV-M03-B`: absence of pending markers cannot imply an open state. Startup/admission must
  reconstruct the complete verified event, operation, pending and ack history. Empty verified
  history or verified history with no accepted dispatch events may establish a baseline. Any legacy
  accepted event without the full new protocol blocks until separately authorized reconciliation.
  Missing/duplicate/malformed/contradictory/out-of-order history and incomplete external-anchor
  reconciliation fail closed. The actual Store connection must set and verify `synchronous=FULL`.
- The architecture direction itself was accepted in principle, with the Store barrier authoritative
  and systemd latch defense in depth. The submitted design remained `MODIFY` and was not approved for
  implementation until these corrections were adjudicated.

The revised design was subsequently accepted for implementation by GPT-PM. Correlation: request
`b992acde-35f0-4f18-91a2-0522c3d4e5f6`, user turn
`816ce1c6-626a-42f7-abcc-341983b4f338`, reply `8109099c-53f6-45db-be51-13a0d1e36acf`, job
`bce5a892-c0a2-4bdf-8b08-ab59908b1925`. GPT-PM marked both prior majors resolved at design level and
authorized the scoped Store/Supervisor/relay implementation. It explicitly left M03 implementation
and evidence, M01, production identities/configuration, E5/runtime, exact-head final acceptance,
full S2 approval and S3 open/blocked.

## Goal

Close the remaining `S2-PROV-M03` crash gap: after a dispatch intent may have been accepted, no
different signed intent may be admitted until the authenticated dispatch-owner relay has received,
validated, and forwarded the exact Supervisor result, or an authorized recovery reconciles it.
The barrier must survive relay/process/host failure without depending on `ExecStopPost` running.

## Current behavior and evidence

- `tools/vst/store.py::Store.accept_dispatch_intent` atomically appends
  `DISPATCH_INTENT_ACCEPTED` and its `supervisor_operations` idempotency result in one
  `BEGIN IMMEDIATE` transaction.
- `tools/vst/dispatch_owner_client.py::DispatchOwnerClient.submit` classifies any unconfirmed
  post-RPC outcome as unknown; `tools/vst/dispatch_owner_service.py` returns
  `reconciliation_required` and exits before a new connection.
- Change 0522 synchronously stops the systemd socket and writes an `/etc` latch afterward. The
  focused suite passed 107/107 at source/test revision
  `34bd7dc1b085789341b29937655af52e07f2ddbd`, but reliability review at HEAD
  `919947df338f857a7f6dea4c4f03f01008ba0d39` identified that helper kill/power loss before durable
  latch creation still permits a later activation. Thus M03 remains MAJOR/OPEN.
- No runtime, `/etc`, systemd, or production dispatch operation has been performed.

## Options and decision criterion

1. **Keep only the systemd latch.** Rejected: it cannot record the accepted outcome if the process or
   host fails before the hook creates the file.
2. **Create a root filesystem latch before every Supervisor submission.** This can protect the
   later RPC window, but introduces privileged synchronous `/etc` writes into each request and
   another storage failure window before the call. It also adds runtime privilege coupling to the
   request path.
3. **Use the existing Store transaction plus an authenticated owner acknowledgement (recommended).**
   The decisive criterion is whether an accepted outcome and its barrier share one durable commit
   before any success response can be sent. This reuses the current root Store authority and avoids
   schema migration or a new scheduler/assignment authority.

## Proposed design

1. In the same Store transaction that appends `DISPATCH_INTENT_ACCEPTED` and the existing
   idempotency result, append a supervisor-only `DISPATCH_OWNER_OUTCOME_PENDING` control note. It
   binds the exact `request_id`, principal, request payload digest, and canonical result digest.
   SQLite WAL connection durability is explicitly set to `synchronous=FULL` for this Store
   contract; no schema version/table migration is proposed.
2. Before a new signed intent is accepted, Store reconstructs admission state from the complete,
   verified event/control history and verifies correspondence among accepted events,
   `supervisor_operations` rows, operation notes, pending notes and acknowledgements. Absence of a
   pending note alone never establishes open admission. If one request remains pending, reject any
   different request ID. Permit only the same request ID and exact payload digest to retrieve the
   already-recorded result. The Dispatcher may continue consuming the already accepted Pub/Sub
   event; this barrier limits only new owner submissions.
3. The owner relay verifies the exact immutable result and successfully completes its local response
   forwarding operation, then invokes a new authenticated `ack_dispatch_intent` Supervisor RPC. The
   acknowledgement means **relay-forwarded**, not proven caller receipt: local `sendall()` cannot
   establish application receipt or durable observation. If the caller is still uncertain, safety
   depends on retrying the same immutable request ID and existing Store idempotency/Runner claim
   fencing. The Supervisor authorizes acknowledgement only for the dispatch-owner role and the same
   authenticated principal. Store derives and verifies the accepted event, payload digest,
   `event_seq`, canonical result SHA-256, and service generation from trusted records; the relay may
   not acknowledge an arbitrary request by supplying only a request ID. Store then appends
   `DISPATCH_OWNER_OUTCOME_ACKNOWLEDGED` in one transaction. Exact duplicate acknowledgement is
   idempotent; a conflicting acknowledgement fails closed.
4. An acknowledgement failure does not clear the Store barrier. The existing root socket latch remains
   defense in depth for ordinary relay exit, but Store admission remains authoritative across a
   crash before `ExecStopPost`.
5. On Store startup, reconstruct and validate the full history before enabling dispatch admission.
   A verified empty history, or a nonempty verified history with no `DISPATCH_INTENT_ACCEPTED`
   events, establishes an open baseline. Every historical accepted event must have exactly one
   matching new-protocol pending control note and a valid acknowledgement or one current pending
   state. Any accepted event without this protocol is `LEGACY_UNRESOLVED` and blocks new admission;
   it is never silently treated as acknowledged. Missing, duplicated, malformed, contradictory or
   out-of-order records, mismatched operation rows, external-anchor failure, or incomplete startup
   reconciliation fail closed. If the host fails after the acceptance transaction commits, the
   pending event is durable and the next Supervisor start reconstructs it before accepting
   requests. Replaying the exact request ID, authenticated principal, service generation, and
   signed payload returns the immutable result and permits a new acknowledgement; a different
   request stays refused. Service generation is part of the idempotency payload and acknowledgement
   tuple. If a restart rotates the generation, ordinary replay is refused and only separately
   authorized reconciliation can resolve the barrier. The in-repository generation reader binds
   `generation` to the current runner `INVOCATION_ID` (`tools/vst/runner_service.py`), so recovery
   across a generation change is refused by the current idempotency contract. Installed runtime
   generation behavior is not exercised here. No automatic new request or replay is created.

### Admission state machine

| Verified Store state | Same request ID and exact payload | Different request ID |
|---|---|---|
| `OPEN` (verified empty history, or verified history with no accepted dispatch event) | Normal authority checks | Normal authority checks |
| `PENDING` | Return the immutable recorded result; the authenticated relay may forward and acknowledge it | Refuse |
| `ACKNOWLEDGED` | Return the immutable recorded result idempotently | Normal authority checks |
| `LEGACY_UNRESOLVED` (accepted event without the new complete control protocol) | Only separately authorized reconciliation; no ordinary replay admission | Refuse |
| `INTEGRITY_FAILURE` or incomplete history | Refuse | Refuse |

`ACKNOWLEDGED` specifically records a relay-forwarding acknowledgement bound to the exact tuple
`(request_id, principal, payload_digest, event_seq, result_sha256, service_generation)`. It does not
assert that the external caller durably received the forwarded response. The Supervisor must derive
this tuple from its trusted operation result and authenticated peer identity; any caller-supplied
field mismatch or conflicting repeated acknowledgement is an integrity/authorization refusal.

## Ownership, compatibility, and rollback

- Store remains the sole assignment/acceptance source of truth; no scheduler, queue, signer, or new
  authority is introduced. The state is an append-only Store control note, not a new SQLite table,
  so no schema migration is needed. Existing `NOTE` storage and event hash chain remain in use.
- Codex owns source, compatibility review and evidence; `functional-test-reviewer` authors the
  crash/ack/idempotency cases; `e2e-runner` executes only after source coding is frozen; GPT-PM owns
  architecture adjudication and exact-head approval. Operator owns any future privileged recovery.
- Existing Store histories from before this feature have no acknowledgement markers. Mandatory rule:
  an empty verified history or a verified history with no accepted dispatch event may establish a
  baseline; any historical accepted event without the full new protocol blocks admission for
  separately authorized reconciliation. Do not silently infer that legacy requests were
  acknowledged or create a clean baseline by deleting/rewriting history.
- Rollback must not remove admission checks while an unacknowledged marker exists. Recovery remains
  closed until exact Store reconciliation and an explicitly authorized repair; schema rollback is
  unnecessary because the proposed format uses existing `NOTE` rows. The Store connection must set
  and verify `PRAGMA synchronous=FULL` before accepting dispatch, rather than relying on a default.
  A SQLite commit followed by external-anchor synchronization failure must not return successful
  acceptance; startup may restore only via the existing verified contiguous-suffix reconciliation.

## Failure modes and verification plan

| Failure point | Durable state and expected behavior | Focused test |
|---|---|---|
| Before the acceptance transaction commits | Neither accepted event nor pending marker exists; no dispatch event has been published; a later request may proceed | Inject transaction failure before commit and assert both records absent |
| Immediately after transaction commit, before Supervisor reply | Accepted event, idempotency result and pending marker all exist; only same-ID/digest/generation replay is allowed after restart | Reopen/reconcile Store and assert a different request is refused while exact replay with the original generation returns stored result |
| After relay receives result, before forwarding response | Pending marker remains; socket latch is defense in depth; exact replay required | Inject client send failure and assert no acknowledgement event |
| After response forwarding, before ack transaction commits | Pending marker remains; new request refused; exact retry can forward/ack | Inject ack RPC failure and assert pending survives |
| Ack transaction commits, ack response is lost | Relay-forwarded ack is durable; it does not claim caller receipt; exact replay remains idempotent | Drop ack response after commit and assert the ack is idempotent and result identity matches |
| Concurrent/different request while pending | Store transaction serializes access and rejects the different request | Two Store connections, controlled transaction ordering, assert exactly one accepted event |
| Legacy accepted event lacks new control notes | Admission is `LEGACY_UNRESOLVED`; only separately authorized reconciliation is allowed | Seed verified pre-protocol event/idempotency history and assert new and replay submissions refuse |
| Missing, duplicate, malformed or out-of-order control history | Store refuses new acceptance and acknowledgement | Mutate isolated fixtures before startup reconciliation; assert integrity-locked refusal |
| Event chain, external anchor, or Store reconciliation is incomplete | Store refuses new acceptance and acknowledgement | Existing event tamper/reconciliation gate cases plus pending-state validation |

The authorized test roles must derive final selectors and run them after all source changes. Also
repeat focused code, reliability and security reviews, then ask GPT-PM to adjudicate the exact source
and test evidence. Power-loss behavior and installed systemd behavior remain runtime claims until
separately authorized platform validation; source tests alone cannot prove hardware flush honesty.

## Decision and implementation status

GPT-PM accepted the revised relay-forwarding acknowledgement semantics, exact result binding,
full-history reconstruction, and legacy-unresolved rule for implementation. The current source
change adds `synchronous=FULL` read-back verification, appends the pending control note in the same
Store transaction as the accepted event and idempotency result, reconstructs the control history at
startup and inside both admission/acknowledgement transactions, and exposes an authenticated
`ack_dispatch_intent` operation only to the configured `dispatch_owner` role. The relay invokes the
acknowledgement only after local response `sendall()` succeeds; a forwarding or acknowledgement
failure leaves the barrier pending and stops the relay. This means local forwarding, not caller
receipt.

No tests have been run against this working-tree implementation. The prior 107/107 focused result
was for the latch-only revision and does not verify this Store barrier. M03 remains OPEN pending the
new focused tests, fresh code/reliability/security reviews, and exact-head GPT-PM adjudication; M01,
production identities/configuration, E5/runtime, full S2 approval, and S3 also remain open.
