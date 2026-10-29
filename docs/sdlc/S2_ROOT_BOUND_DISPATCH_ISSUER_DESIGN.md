# S2 root-bound v1 dispatch issuer: crash-consistent source design

Sprint: `39b7cc253f5d` (S2). Status: implementation-ready design proposal; not independently reviewed, GPT-PM verified, activated, or runtime-proven. Owner: Codex for design/source coordination; GPT-PM for independent architecture adjudication; operator for any root key/config provisioning or activation authorization.

Decision source: GPT-PM request `8b6b69f3-9b39-491b-a948-03c497870b5d`, correlated reply `b1728c67-3bc2-4db5-9fbf-6b359a73ad82`, reproduced in [the adjudication record](evidence/s2-bootstrap-source-and-root-issuer-adjudication-20261029.md). Decision 2 is `MODIFY`: reuse the existing root Supervisor and the unchanged signed dispatch-instruction v1; close finding `S2-MACHINE-ISSUER-I01` with the crash-consistent protocol below. This proposal does not close the finding until independent database/security review and a targeted GPT-PM verification accept this exact contract.

## 1. Scope and current repository boundary

This design adds no scheduler, daemon, v2 wire format, table, or schema migration. It defines a possible issuer path inside the root Supervisor and a specialized append-only journal protocol using the existing SQLite `supervisor_operations` rows and hash-chained `NOTE` events.

The current source constraints are:

- `tools/vst/dispatch_instruction.py:13-19,25-64` fixes `VST_S2_DISPATCH_INSTRUCTION_V1\0`, purpose `VST_S2_DISPATCH_INSTRUCTION_V1`, the exact 12-field envelope, canonical UTC expiry, 32-hex request ID, and Ed25519 signature representation. Its v1 bytes and signing domain remain unchanged.
- `tools/vst/store.py:335-353` defines `supervisor_operations(operation_key PRIMARY KEY, operation, payload_sha256, result)` and update/delete refusal triggers. The same append-only table is created for existing databases in `tools/vst/store.py:766-787`; this design does not loosen the triggers.
- `Store.execute_idempotent()` in `tools/vst/store.py:3650-3700` executes its callback under the Store transaction and explicitly prohibits external effects there. It cannot wrap OpenSSL.
- `Store.execute_external_idempotent()` in `tools/vst/store.py:4712-4860` journals a pending sentinel and append-only intent/completion/unknown notes, but can invoke the effect again when there is no durable completion. That retry contract is intentionally not used for signing.
- `Store._verify_supervisor_records()` in `tools/vst/store.py:3539-3649` currently reconciles only generic internal operations, generic external-operation notes and probes. A specialized issuance protocol must extend this verifier with exact issuance-event parsing and operation-row correlation before such rows can be used safely; adding arbitrary NOTE names alone is insufficient.
- `Store.accept_dispatch_intent()` in `tools/vst/store.py:1099-1245` currently verifies exact request idempotency and checks live task owner/epoch, lease, consumed probe, attempt/receipt and budget before appending acceptance. `Supervisor.accept_dispatch_intent()` and `_validate_current_dispatch_intent()` in `tools/vst/supervisor.py:457-528` verify signature/current generation; `next_dispatch_intent()` and `issue_dispatch_intent_grant()` at `:529-620` revalidate before delivery/grant. Delegated-v1 checks must be added to all three use-time boundaries, not only initial receipt.
- `docs/sdlc/S2_AUTHENTICATED_ASSIGNMENT_BASIS_DESIGN.md` specifies the selected Store-backed immutable handoff. This design consumes that record; it does not replace its writer or create another assignment authority.

All paths above describe existing repository source. The protocol below is proposed behavior, not implemented source. The upstream writer agent owns the Store/Supervisor/API code and is outside this document's edit scope.

## 2. Authority and trust separation

The root Supervisor is the only issuer. It obtains one authenticated, immutable assignment handoff by its exact assignment operation ID; it does not enumerate work or accept a caller-selected task tuple. The accepted bootstrap writer's root-approved policy bounds project, sprint, task/story, manifest, slot, attempt and principal. The Supervisor independently reads current Store authority and binds the currently configured run, consumed probe and service generation.

Use a dispatch-instruction key distinct from the execution-grant key and distinct from the event-chain HMAC root. The dispatch private key is readable only by the root Supervisor signing boundary; it is never exposed to dispatcher/relay, runner, worker, ordinary caller or Store client. Root-owned configuration pins key ID, key class, exact purpose, public/private key paths, public-key fingerprint, enabled state and issuer maximum TTL. Fingerprints and immutable class bindings are checked on every process start and every accept/next/grant path, including when issuance is disabled.

Key class is explicit and immutable:

| Class | Required treatment |
|---|---|
| `LEGACY_V1` | Preserve the existing v1 verification and admission contract exactly. No issuer-journal requirement is added to legacy keys. |
| `DELEGATED_V1` | Require a valid completed issuance record, exact canonical signed envelope, matching immutable handoff/policy and current authorization checks. |
| `UNKNOWN` / unclassified | Refuse. Never infer legacy from a missing journal or configuration. |

Persist the first observed `(key_id, class, purpose, public_key_fingerprint)` as an immutable `SUPERVISOR_DISPATCH_KEY_CLASS_BOUND` NOTE in the existing append-only journal. A later mismatch is `CONFLICT`/integrity failure and cannot reclassify the key after restart, feature disablement or configuration reload. This is a journal convention over existing primitives, not a new schema table or trigger exception. The root-controlled registry remains the authority; the journal binding detects drift and downgrade.

`enabled` defaults to false. When false, do not offer an issuance operation. Still classify every key unconditionally: a `DELEGATED_V1` envelope cannot fall through to legacy verification simply because issuance is disabled or an intent record is unavailable. Preserve current default role permissions; introduce only an explicit capability for this bounded feature if the existing Supervisor capability model can represent it without widening any default role. A read-only delegated issuer process is optional and may remain unused; no new daemon is part of this design.

## 3. Canonical issuance identity and frozen envelope

### 3.1 Identity

Define the canonical handoff identity as the exact, validated Store handoff identity, including `assignment_operation_id`, handoff digest, policy ID/digest, project/repository/sprint, source head, manifest digest, task/story, principal, slot, attempt, epoch, lease ID, run ID, probe digest and the generation recorded by that handoff. Reject unknown/missing fields, duplicate JSON keys, booleans where integers are required, noncanonical encodings and digest/fingerprint mismatch before constructing the identity. `assignment_operation_id` is the stable one-issuance logical key; the frozen payload below binds the entire identity and every current signer/envelope value. The existing fresh-only bootstrap contract prevents creating a replacement assignment for an existing task history.

For an accepted handoff identity `H`, derive:

```text
request_id = hex_lower(SHA256(
    b"VST_S2_ROOT_DISPATCH_REQUEST_ID_V1\\0" || canonical_bytes(H)
))[0:32]

operation_key = "dispatch-issue:" + hex_lower(SHA256(
    b"VST_S2_ROOT_DISPATCH_ISSUANCE_OPERATION_V1\\0" || canonical_bytes({
      "assignment_operation_id": H.assignment_operation_id
    })
))
```

The full operation hash, never the truncated request ID, is the journal key. The request ID is an index and v1 signature binding only. The journal stores the full handoff identity and full operation hash; any truncated-ID collision, changed full handoff under the same assignment operation ID, changed key/generation/expiry/payload under that key, or same request ID under a different operation key is `CONFLICT` and permanently refused. The operation row's payload digest covers the full canonical handoff identity plus every frozen issuance field, so it cannot be replaced with a new generation or signer. There is no “new logical identity” escape after an ambiguous attempt.

### 3.2 Exact unsigned v1 object

Before reserving invocation, derive and freeze exactly these unsigned fields, with no caller overrides:

```json
{
  "version": 1,
  "algorithm": "Ed25519",
  "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
  "request_id": "32 lowercase hex from the formula above",
  "task_id": "from authenticated handoff",
  "slot": "from authenticated handoff",
  "attempt": 1,
  "epoch": 1,
  "run_id": "original handoff run",
  "key_id": "root-configured DELEGATED_V1 dispatch key",
  "expires_at": "canonical UTC YYYY-MM-DDTHH:MM:SSZ"
}
```

The numeric values above illustrate types only; actual `attempt` and `epoch` must equal the handoff/current Store values. The intent record freezes the exact full handoff, policy bytes/digest and validity, Store manifest digest, live lease ID/expiry, consumed run/probe digest, current service generation, signer key ID/class/purpose/fingerprint, signing-domain identifier, canonical unsigned JSON bytes and SHA-256 digest. Store also records the intended completed-envelope identity as `unsigned_sha256` plus the exact request ID and every v1 field; it cannot know the signature bytes in advance. The signed completion record binds `unsigned_sha256` to the exact canonical full envelope bytes and their SHA-256 digest.

Expiry is computed once and never refreshed: `expires_at = min(now_utc + root_configured_max_issuer_ttl, handoff_expiry, policy_expiry, current_owner_expiry, current_lease_expiry)`, rounded down to whole UTC seconds required by v1. Source authorities, not this design, must supply finite TTL values. Refuse if max issuer TTL is absent/nonfinite/nonpositive, expiry is not later than issuance time, or the remaining window is below the existing minimum safety slack needed by execution-grant policy. Do not invent a numeric maximum here. Root config must explicitly set a finite bound no greater than the approved policy/handoff validity; its exact value requires the source owner/GPT-PM to accept the policy. Expired and revoked keys/policies fail closed.

## 4. Existing-journal protocol and crash recovery

Use existing `supervisor_operations` as the unique reservation and existing append-only `NOTE` events for immutable protocol records. Do not call the generic `execute_external_idempotent()` for this operation. Implement a specialized reserve/complete/read reducer using the existing transaction and append-event helpers; never update/delete an operation row or event.

Operation name is `VST_S2_ROOT_DISPATCH_ISSUE_V1`. The row has `operation_key` (full SHA-256 identity above), `operation` (exact constant), `payload_sha256` (SHA-256 of the canonical full identity plus frozen issuance object), and result exactly `{"_vst_state":"PENDING"}`. In the same short SQLite write transaction that inserts the row, append one NOTE event `SUPERVISOR_DISPATCH_ISSUANCE_INTENT` containing the full frozen record, its canonical digest, handoff/policy references and operation key. If the unique insert loses a concurrent race, read and validate the winning row/event; never make a second intent for that identity. Extend `_verify_supervisor_records()` to recognize this as a third explicit operation family: exactly one issuance intent is the required row witness; operation key/name/payload digest/result sentinel must match; only the defined started/completed/unknown events may follow; all fields, event order and terminal multiplicity must validate. Reject mixing the issuance family with generic `SUPERVISOR_OPERATION` or `SUPERVISOR_EXTERNAL_OPERATION_*` events for the same key. Generic behavior and all other operation families remain unchanged. This is code to the existing verifier, not a schema or trigger change.

The issuer then re-reads the row and intent through a verified read transaction and confirms that the entire canonical intent matches the just-derived object. It rechecks live authority before starting. Immediately before invoking OpenSSL, it appends `SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED` in a short Store transaction, bound to the same operation key, intent digest and unsigned digest. Only the caller that transitioned an absent reservation to this started marker may invoke OpenSSL. A `PENDING` intent without a started marker proves the external signer was not entered and can be resumed by the one caller that atomically adds the marker; after a started marker, no process may invoke the signer again for this identity.

The Ed25519 signing call is outside all SQLite transactions and Store locks. Before accepting a completion, the root Supervisor must cryptographically verify the exact v1 signing-domain-prefixed canonical unsigned bytes and returned signature against the root-pinned public key and its frozen fingerprint. Encoding, matching fields and a hash are insufficient. The shared reducer must require a trusted completion verifier and return CONFLICT for a persisted completion when verification is absent, raises, or does not return literal True. The detached source contract now exposes that mandatory verifier callback; it never supplies its own trust authority. Invalid signer output before completion is durably UNKNOWN, not a successful completion and never permission to retry. Historical replay is returned only after the same cryptographic binding succeeds.

Verification subprocesses and root-key file reads also stay outside Store transactions. A root-owned verification context may cache the result for exact immutable envelope bytes, unsigned digest and signer fingerprint; it is not an RPC argument or a caller-supplied boolean. Inside the Store transaction, the shared reducer must bind that trusted result to precisely the current journal envelope/intent/key-registry identity, refusing any mismatch. A changed row, key registry or fingerprint invalidates the context and requires fresh external verification before another transaction; it does not allow a stale proof or an external process inside a SQL callback. It signs exactly `VST_S2_DISPATCH_INSTRUCTION_V1\\0 || canonical_bytes(frozen_unsigned_v1)`. On successful return, validate the signature encoding locally, assemble the exact v1 envelope and append one `SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED` NOTE containing the canonical full envelope (or its canonical bytes encoded losslessly), unsigned digest, envelope digest, operation/payload digest, signer identity and intent reference. The specialized reducer considers the operation complete only when exactly one valid completion event exists and all bindings verify. Do not mutate the pending row. A duplicate byte-identical completion observation is harmless only if produced from the same durable record; two different completed envelopes for one identity are `CONFLICT`.

Any error/timeout/termination after the signing-start marker but before a valid durable completion is `UNKNOWN`: append a best-effort `SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN` NOTE with stable error class and exact bindings, then refuse. If the process dies before it can append UNKNOWN, startup reduction maps `SIGNING_STARTED` with no valid completion to `UNKNOWN`. Never infer non-execution from a subprocess timeout or missing stdout. Never automatically call OpenSSL again from `PENDING-after-start`, `UNKNOWN`, or `CONFLICT`, even for deterministic Ed25519 and even if a new generation, expiry, key or policy is available.

If exact prior signed bytes are already present in a valid completion record, a read-only retry may return those same bytes subject to retrieval policy; this does not create current execution authority. If signed bytes exist only in process memory/output and were not durably journaled, they cannot be reconstructed by re-signing; remain `UNKNOWN`. An operator-authorized integrity reconciliation may classify evidence but does not silently reset or re-run the operation.

### 4.1 State reducer

Reducer output is derived from the row plus all matching immutable NOTE events after event-chain/anchor verification. Malformed JSON, duplicate terminal events, digest mismatch, missing/multiple intent, event/row disagreement or nonidentical completions produce `CONFLICT` and fail closed.

| State | Exact durable evidence | Allowed behavior |
|---|---|---|
| `ABSENT` | No operation row and no matching issuance events | Validate current authority; atomically reserve the exact intent. Only the winning reservation may proceed. |
| `PENDING` | Valid operation row and intent, no started marker | Revalidate the exact same frozen identity; atomically append started marker once, then that winner may invoke signer. Changed identity is `CONFLICT`. |
| `COMPLETED` | Valid intent, started marker and one exact valid completed envelope event | Return only the exact persisted envelope bytes if retrieval is allowed. Admission still rechecks current authority. |
| `UNKNOWN` | Started marker but no valid durable completion, including an explicit unknown event | Fail closed; no new identity and no signature retry. Read-only evidence reconciliation only. |
| `CONFLICT` | Any immutable record disagreement, collision, malformed/multiple nonidentical completion, changed binding or failed integrity verification | Permanently refuse this operation identity; alert/record the integrity failure. |
| `REVOKED_EXPIRED` | A historical valid issuance whose key, policy, handoff, instruction or authority has expired/revoked | Preserve underlying history; refuse new admission, delivery and grant. No re-signing or fallback. |

`REVOKED_EXPIRED` is an authorization disposition layered over the historical journal state, not a rewrite of `COMPLETED` or deletion of evidence. Integrity `CONFLICT` takes precedence over other interpretations. Startup, admission, delivery and grant code must use one shared reducer; no callsite may reinterpret an unknown state as absence.

## 5. Admission and current-authority enforcement

### Initial acceptance

In `Store.accept_dispatch_intent()`'s existing single admission transaction, classify the key unconditionally. For `LEGACY_V1`, use the existing path byte-for-byte in behavior. For `DELEGATED_V1`, require all of:

1. The journal reducer returns one valid `COMPLETED` issuance and current key/policy/handoff are not revoked or expired.
2. Incoming canonical instruction bytes exactly equal the completed journal envelope bytes; v1 signature verification uses the configured key whose purpose, class and fingerprint match the immutable binding.
3. Handoff operation ID/digest and policy ID/digest are present and verified; the assignment principal, task/story, manifest, slot, attempt, epoch, lease, run, probe and generation equal the frozen intent.
4. Within this same Store admission transaction, the current task/story owner epoch, live lease, manifest, eligible attempt/receipt gap, consumed probe, active run and generation remain equal to the handoff/intent, and budget/receipt guards still pass.
5. The normal existing `DISPATCH_INTENT_ACCEPTED` event and `supervisor_operations` idempotency record commit atomically with these checks.

Do not verify the delegated provenance in an earlier read and then admit based on that stale snapshot. Reuse/refactor existing locked helpers so all reads used by delegated acceptance share the existing transaction; do not nest public Store methods or invent a parallel authority API.

### Queued delivery and grant

`Supervisor._validate_current_dispatch_intent()` remains the shared caller-facing predicate for `next_dispatch_intent()` and `issue_dispatch_intent_grant()`, but it must delegate to a single Store snapshot boundary. Introduce a connection-taking current-intent helper which, on one connection, verifies immutable key class, the exact completed issuance and trusted signature-verification context, handoff and current root policy/revocation identity, current run/generation/probe, owner/lease/manifest/receipt/budget, and calls `_execution_grant_basis_locked()` directly. Do not perform a provenance pre-read followed by public `Store.execution_grant_basis()` in a different read transaction. Root-owned policy/generation/key-registry providers are re-read at the commit check; caller values cannot supply current authority.

For delivery, select and validate the candidate in that same verified read snapshot. Its bytes are a delivery hint observed at that snapshot, not an execution permission: later revocation can make a previously delivered hint unusable. The grant path must repeat the entire locked predicate in the write transaction that commits the immutable dispatch-grant operation, including exact replay. Build and cryptographically sign outside SQL, then recheck and bind the exact signed grant to the same dispatch request and issuance before committing/publishing it; on a changed authority snapshot, refuse without returning a usable grant. Preserve the existing execution-grant wire format and use the append-only dispatch-grant operation to retain the association.

The existing `claim_runner_execution()` and `reserve_runner_execution()` write boundaries must likewise join a delegated grant to its immutable dispatch-grant operation and recheck the same current delegated predicate before the durable new claim/reservation. This preserves revocation through the execution admission point rather than treating an earlier delivery or grant read as a lasting permission. A delegate-origin task/issuance can never become legacy merely because its feature is disabled or its journal lookup fails; unclassified or missing provenance is refusal. Existing exact COMPLETE receipt replay is observation-only and grants no new execution. No public nested transaction or second scheduler is introduced.

Historical `replay_dispatch_outcome()` remains observation-only: it may return a recorded outcome but cannot restore delivery, signing, grant or execution authority. A stale or revoked accepted intent remains a historical fact while all new delegated authorization use is refused.

If feature configuration is disabled, block all new delegated issuance and delegated authorization use; do not turn delegated keys into legacy keys. If trust registry or journal is unavailable, treat delegated entries as unavailable and fail closed. Preserve existing legacy key behavior where its class binding is already established; unknown class never passes.

## 6. Failure and concurrency rules

- Two concurrent first requests: exactly one inserts the full-operation-key row and intent; the loser re-reads the winner and can proceed only if it wins the unique `SIGNING_STARTED` append under a guarded transaction. The loser returns PENDING/UNKNOWN or exact COMPLETED bytes; it never signs.
- Same operation key, different canonical payload/unsigned envelope: immutable digest mismatch is `CONFLICT`; do not change request ID, generation, key ID, expiry or tuple.
- Same truncated `request_id` for different full identities: detect by searching/validating the immutable intent binding; refuse as collision.
- Crash before reservation commits: state is ABSENT and no signer was called.
- Crash after reservation but before started marker: state is PENDING and no signer was called; one winner may continue the exact frozen operation.
- Crash after started marker and before durable completion: state is UNKNOWN, even if the signer may not actually have started. This conservative availability loss is intentional to prevent duplicate/changed issuance.
- Signer reports any failure after marker, returns malformed signature, or times out: UNKNOWN; never auto-retry.
- Crash after completion event commits but before response: state is COMPLETED; return the exact persisted bytes after verifying all hashes and current retrieval policy.
- Journal chain, anchor, row/event or envelope hash failure: CONFLICT/integrity refusal; no signing.
- Policy/key/handoff revoked or expired after completion: historical COMPLETED remains observable, effective disposition is REVOKED_EXPIRED; no acceptance/delivery/grant.
- A new service generation does not relabel an old intent. It remains historical; new work needs a different authenticated handoff identity. If the identity is unchanged but generation differs, immutable-payload mismatch refuses rather than creating a second identity.

## 7. Implementation order and source ownership

1. **Codex/source owner:** implement pure exact validators and deterministic identity/freeze preparation only; no private-key signing or activation. Keep v1 validator/signing bytes unchanged. Define schemas/domains and key-class reducer as described above.
2. **Existing Store/Supervisor writer owner:** implement specialized append-only reservation, started marker, completion/unknown records and reducer using `supervisor_operations` plus NOTE events. Do not edit schema version, add migration/table, weaken triggers, or call OpenSSL from a transaction.
3. **Existing Supervisor/API writer owner:** expose only one bounded issuer operation tied to a trusted handoff ID and authenticated root peer; no caller tuple, enumeration or assignment mutation. Default it off. Maintain the legacy path and validate delegated key class at admission, next and grant.
4. **Independent database/security reviewers:** review concurrency, transaction boundaries, crash recovery, journal corruption and key downgrade behavior against the final source diff. Record exact finding disposition.
5. **GPT-PM:** adjudicate this corrected I01 contract and authorize the bounded integrated source scope after independent design rechecks; later exact-source tests/reviews and a fresh final gate are separate. Design acceptance alone does not close runtime or sprint acceptance.
6. **Operator:** only after separate accepted source review, provide/provision root-owned dispatch-key and finite TTL configuration or explicitly leave issuance disabled. No secret belongs in chat. Any production activation remains separately gated.

The current upstream writer owns `tools/vst/store.py`, `tools/vst/supervisor.py`, and the RPC callsite; this document author does not modify those files. The implementation must be integrated by that existing owner and then reviewed at its exact head.

## 8. Focused acceptance evidence to collect after source coding

This section is a test plan only; no tests are added or run in this design task. `functional-test-reviewer`/`e2e-runner` own execution after all sprint coding is complete.

| Contract | Required falsification case | Expected result |
|---|---|---|
| Exact identity/freeze | Changed key, generation, policy, handoff, expiry, unsigned field or payload under one operation key | `CONFLICT`; no signer call |
| Request ID | Stable identical handoff; forced 128-bit truncated collision | same 32-hex ID for same identity; collision refused, full operation digest retained |
| Reservation | Concurrent identical first requests | one row/intent and at most one started marker winner |
| Crash recovery | crash before reserve; after reserve; after started marker; after signer output before completion; after completion before response | respectively `ABSENT`, `PENDING`, `UNKNOWN`, `UNKNOWN`, exact `COMPLETED` replay |
| Signer invocation | timeout/nonzero/malformed output after started marker; restart and retry | `UNKNOWN`; no second OpenSSL invocation |
| Journal integrity | row/event digest mismatch, missing/multiple intent, invalid chain, conflicting completion bytes | `CONFLICT`; fail closed |
| Admission | valid legacy v1; valid delegated completion; missing journal; unknown key class; revoked/expired key | legacy unchanged; delegated accepted only with complete current binding; other delegated/unknown/revoked cases refused |
| Use-time freshness | revoke policy or change run/generation/lease after acceptance, before next/grant | historical event remains; no delivery or grant |
| Separation | dispatch key equals execution grant/HMAC key; feature disabled and delegated entry presented | reject configuration; no delegated fallback |
| TTL/time | missing/nonfinite/nonpositive max TTL, already expired or shorter-than-required slack authority | refuse before reservation/signing |

Exact commands, source revision, environment and execution results must be recorded by the test owners. Until then, these cases are `NOT_RUN`, not passing evidence.

## 9. Decisions deliberately not invented

The source authority must provide the finite maximum issuer TTL and existing execution minimum slack. The approved root config must provide key IDs, paths, fingerprints, policy/handoff expiry, revocation source and exact enablement procedure. No numeric TTL, credential, private-key path/value, production host, or activation authorization is inferred here. These are separate configuration/provisioning and source-review inputs; absence keeps issuer disabled and does not justify a permissive default.

The design does not claim resistance to a compromised root/Windows administrator, WSL root, kernel, or host able to alter both the SQLite journal and signing process. It guarantees conservative crash/downgrade handling within the existing trusted root Supervisor/Store boundary, subject to the external-anchor and root ownership guarantees already required by the repository.


## 10. Current focused design remediation

At source HEAD `e44f48dca00802b9f6ad6c8629fe909dbe0a4a99`, the actual database and security design reviewers identified two MAJOR omissions in the earlier proposal: signature verification before claiming COMPLETED, and the snapshot/commit boundary between delegated provenance and grant authority. Sections 4 and 5 now make both mandatory, including replay and the durable runner claim/reservation. These edits are a proposal pending those reviewers' targeted rechecks and GPT-PM's source adjudication; no production signer, activation or acceptance is inferred.
