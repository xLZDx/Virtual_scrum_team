# S2 M03 cross-generation outcome recovery adjudication — 2026-10-29

## Correlated decision

GPT-PM reviewed the narrowly scoped historical-result recovery contract under request
`f67c5dd7-5279-42b1-9dc4-94ed4b72b5a1`, job `e818848b-1845-425f-85c2-2d06e488a8f5`,
user turn `1fc7a604-1133-411f-8906-199a5bb5b8b7`, and reply
`5cd963a6-2a9a-4ae7-96c6-f3955df216ea`.

Disposition: **MODIFY — historical exact-result replay principle accepted, with one additional
authorization-boundary invariant.** GPT-PM confirmed that this narrow recovery is within the
previously accepted M03 implementation scope and does not need a separate operator business
decision. It does not approve full S2, runtime provisioning, production dispatch, E5, push, PR, or
merge.

The adjudication was based on supplied source facts and reported prior evidence. GPT-PM did not
independently verify repository HEAD or rerun the previously reported 119-test suite. Its declared
review HEAD was `1bd00cbacac099f34717e9c68fc720a467f6d519`, with earlier source/test HEAD
`a34c574d232448b21f8169b9fa058ca7c6be8d61`.

## Required separation

- **Historical replay** observes an immutable accepted result. The authenticated dispatch-owner
  caller must supply the complete original envelope. Store must derive the principal from the
  authenticated peer, and in one consistent read snapshot verify the exact accepted event,
  operation result, supervisor note, pending/ack control protocol, original event sequence and
  original service generation, plus the complete event chain and external anchor.
- A historical result may be replayed after the original signature expires or its key is removed
  from current trust configuration. That exception applies only to the exact prior acceptance; an
  absent or mismatched result must be refused.
- The route is read-only. It cannot append an event, create an idempotency row, change a lease,
  issue a grant, or trigger Runner execution. It does not fall through to new admission.
- **New admission** stays on the existing RPC and continues to require current signature/key
  eligibility, owner, lease, preflight, run ID, generation, manifest, budget, and receipt-position
  checks. Invalid or expired instructions never create new acceptance.
- ACK remains restricted to authenticated `dispatch_owner` and binds the original tuple
  `(request_id, principal, payload_digest, event_seq, result_sha256, original_service_generation)`.
  Relay ACK occurs only after local response forwarding. ACK does not change Runner claims or prove
  that a child did not execute.
- Legacy-unresolved, corrupt, incomplete, or contradictory histories stay closed for separately
  authorized reconciliation. Stale events remain fenced from new-generation dispatch/grant paths.

## Implementation and evidence status

The source implementation adds a distinct authenticated read-only replay RPC and Store lookup;
normal submission remains the sole path for new admission. The owner client may use historical
lookup after a current verification failure or an ambiguous/current-generation submission result,
but it never retries admission. This is implementation evidence only until the mapped tests and
fresh code/security/reliability reviews complete.

The decision confirms one MAJOR, `S2-PROV-M03-R01`, remains open until the implementation is
tested and independently reviewed. `S2-DISPATCH-M01` also remains MAJOR/OPEN because no production
coordinator call site is present. Runtime/E5, production identity/configuration, prohibited
scenarios, final exact-head GPT-PM gate, and full S2 acceptance remain separate gates. S3 remains
unstarted.
