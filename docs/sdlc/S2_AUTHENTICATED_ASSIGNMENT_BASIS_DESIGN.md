# S2 authenticated Store assignment-basis design

Sprint: Agentic_Framework `39b7cc253f5d`, tracking the already active S2.
Status: candidate source design; implementation and the upstream assignment writer are absent.
Decision: GPT-PM request `4b2e7e61-c0bd-407d-9b2c-b9078da5f7d9`, response preserved verbatim at
`docs/sdlc/evidence/s2-store-assignment-provenance-adjudication-20261029.md`.
The ruling partially resolves S2-MACHINE-ISSUER-M01: no signature per task is required, but one
MAJOR remains until the upstream assignment operation is authenticated and enforced.

## Existing boundary

`Store.execution_grant_basis()` at `tools/vst/store.py:2013` validates one exact task/slot/attempt/
epoch/run against the registered manifest, current live owner, lease, consumed probe, receipt
position and budget. Its `expected_owner` and `expected_lease_id` arguments enforce the expected
principal and lease. `Supervisor._validate_current_dispatch_intent()` at
`tools/vst/supervisor.py:451` already calls this check before dispatching an accepted intent.
The Store continues to own task/lease authority; Runner admission and reservation continue to
recheck it.

`AuthenticatedSupervisorAPI._dispatch()` at `tools/vst/supervisor_service.py:205` currently
routes only the declared operations. Its role allowlist at line 776 has no assignment-basis or
authenticated assignment-bootstrap role. The peer identity comes from kernel credentials and
cgroup inspection in the same module; a caller-supplied principal is not authentication.
`Store.acquire_epoch()` accepts a plain owner string. Its value and an event-chain MAC alone do
not prove an authorized caller established the assignment. The current code has no
assignment-bootstrap operation or authenticated provenance result. Legacy ownership/lease rows
therefore cannot by themselves authorize delegated signing.

## Bounded design

Use two separate Supervisor roles, neither enabled by default:

1. `assignment_bootstrap` is the only role allowed to create the exact bounded S2 assignment
   transition under a concrete, operator-authorized delegation policy. Kernel UID/GID, pidfd and
   cgroup are mapped to this role in root-owned peer configuration. The Supervisor fixes the
   actor from that mapping; the request cannot name its own principal, policy digest, owner or
   epoch. The entrypoint accepts one task/story tuple present in the pinned S2 manifest and only
   the fixed operations `open_story`, `register_task`, `acquire_epoch`, and `acquire_lease`;
   implementation must use existing Store invariants and bind the resulting task, current epoch,
   lease, runner, run and consumed probe. It cannot enumerate tasks or create arbitrary scope.
   This mutation endpoint is only specified here; implementation and enablement require a fresh
   independent security/code review under the PM decision.
2. `delegated_issuer` is read-only. It can call only `assignment_basis`; it receives no direct
   Store handle and cannot list tasks, create assignments/leases, mutate the Store, or invoke
   dispatch submission. Its principal and generation are derived from trusted configuration.

The proposed root-owned policy `VST_S2_ASSIGNMENT_DELEGATION_POLICY_V1` has exactly these fields:
`schema`, `policy_id`, `repository`, `sprint_id`, `source_head`, `manifest_sha256`,
`owner_principal`, `allowed_assignments`, `bootstrap_peer`, `issuer_peer`,
`allowed_bootstrap_operations`, `maximum_handoff_ttl_seconds`, `valid_from_utc`,
`expires_at_utc`, and `revocation_id`. `owner_principal` is exactly `Codex`.
`allowed_assignments` is a nonempty duplicate-free array of exact objects
`{story_id, task_id, task_manifest_sha256, test_run_slots}`; each slot list is nonempty,
duplicate-free, and matches only `TestRun` slots in that exact task manifest.
`bootstrap_peer` and `issuer_peer` each have exactly `{role, uid, gid, cgroup}` with distinct
positive integer UID/GID pairs; roles are respectively `assignment_bootstrap` and
`delegated_issuer`. `allowed_bootstrap_operations` is exactly the four-operation array above.
The TTL is a positive integer bounded by the configured upper limit 300 seconds; validity times
are canonical UTC and expiry exceeds validity. IDs/digests use the repository's fixed patterns.
Unknown fields, booleans for integer values, duplicate assignments, duplicate roles, peer
collisions or any out-of-policy task/slot refuse. Bind `policy_sha256` to the canonical policy
bytes without a digest/signature self-field. The candidate is authorized by the operator only
when that exact digest and corresponding root-owned config are approved for installation; merely
writing the file or enabling AF does not make it approved.

A proposed policy or the framework's generic GO is not an installed authorization. No peer or
policy config for these new roles is currently evidenced. The current v1 instruction verifier
and human E5 contract remain unchanged. This design does not implement signing, provision
keys/configuration, enable either peer, issue work, or close the separate machine-E5 finding.

## Durable handoff record

Implementation clarification: the exact handoff also contains `bootstrap_request`, whose exact
schema is the bootstrap request defined below (including its full canonical task manifest).
The operation ID is SHA-256 over `b"VST_S2_AUTHENTICATED_ASSIGNMENT_V1\0"` followed by canonical
JSON of exactly `{policy_sha256, task_id, story_id, task_manifest_sha256, request_id}`.
The journal's `payload_sha256` is independently recomputed from canonical JSON of exactly
`{request: bootstrap_request, bootstrap_peer: policy.bootstrap_peer, policy_sha256}`. The reader
validates request-to-handoff identity and task manifest digest; it does not trust a matching event
and row digest without recomputing the actual payload. This prepares verification only, not a
writer endpoint or an authenticated historical record.

Freshness correction from the focused negative test: the exact handoff also includes
`service_generation`, fixed by the authenticated upstream operation, not the issuer request.
The Store reader requires trusted `expected_run_id` and `active_service_generation` and compares
both to the handoff inside the same read transaction. Supervisor must supply its configured
current run ID; absence disables the path. A still-live consumed probe from another Supervisor
run or a handoff from a prior service generation cannot be relabelled as current authority.
Old records missing this field are refused; no compatibility fallback is authorized.

The authenticated bootstrap operation writes one completed row through the existing
`supervisor_operations` table and `Store.execute_idempotent()` transaction, then records the
existing append-only `SUPERVISOR_OPERATION` NOTE event. No table or migration is added. Operation
name is exactly `VST_S2_AUTHENTICATED_ASSIGNMENT_V1`; operation key is a lowercase SHA-256 over a
fixed domain label and the canonical tuple of the root-derived policy digest, task ID, story ID,
manifest digest and bootstrap request ID. The canonical idempotency payload includes the exact
request and kernel-derived bootstrap peer mapping. Same key/same payload returns the immutable
stored result. Same key/different payload or unresolved result refuses; it never reassigns or
renews a lease.

The mutation request has exactly `schema` (`VST_S2_ASSIGNMENT_BOOTSTRAP_REQUEST_V1`),
`request_id` (32 lowercase hex), `story_id`, `task_id`, `task_manifest`, `slot`, `attempt`, and
`run_id`. The handler rejects a story/task/manifest/slot outside the exact root policy. It does
not accept actor, owner, peer, policy, source head, epoch, lease ID, worker ID, expiry, or event
actor from the caller. It derives owner `Codex`, current epoch, lease, worker ID, manifest digest,
run/probe identity and service generation from the trusted peer, verified policy, and Store.
Idempotency identity is domain-separated from the canonical request and policy digest. The fixed
request cannot perform task enumeration or select a task outside its named allowlist.

The completed result has exactly these fields and no others:

```json
{
  "schema": "VST_S2_AUTHENTICATED_ASSIGNMENT_V1",
  "assignment_operation_id": "64 lowercase hex operation key",
  "policy_id": "root configured identifier",
  "policy_sha256": "64 lowercase hex",
  "repository": "Virtual_scrum_team",
  "sprint_id": "39b7cc253f5d",
  "source_head": "40 lowercase hex",
  "manifest_sha256": "64 lowercase hex",
  "bootstrap_peer": {
    "role": "assignment_bootstrap",
    "uid": 980,
    "gid": 982,
    "cgroup": "/system.slice/vst-assignment-bootstrap.service"
  },
  "assignment_principal": "Codex",
  "task_id": "Store task identifier",
  "story_id": "Store story identifier",
  "task_manifest_sha256": "64 lowercase hex",
  "slot": "one manifest TestRun slot",
  "attempt": 1,
  "epoch": 1,
  "lease_id": 1,
  "runner_id": "configured runner principal",
  "run_id": "preflight run identifier",
  "probe_sha256": "64 lowercase hex",
  "issued_at_utc": "canonical YYYY-MM-DDTHH:MM:SSZ",
  "expires_at_utc": "canonical YYYY-MM-DDTHH:MM:SSZ",
  "handoff_sha256": "64 lowercase hex"
}
```

The numeric identities and cgroup above are illustrative schema values, not observed or reserved
production IDs. Schema validation rejects placeholders, booleans in integer fields, malformed
digests/IDs/times, unknown/missing fields, expired handoffs, and values outside the loaded
root-owned policy. `handoff_sha256` hashes the canonical result with that field omitted. The
Store operation row's `operation` must equal the fixed name; its `payload_sha256` and canonical
result must match the exact bootstrap request and this schema. The linked NOTE event must match
operation key, operation name, payload digest and result digest. Existing
`Store._verify_supervisor_records()` validates operation/event correlation. Verification also
requires the complete Store chain and configured external anchor, if used, to verify.

The new bootstrap handler derives `bootstrap_peer` and policy fields only from the authenticated
Supervisor peer plus loaded root-owned policy, never from JSON supplied by its caller. It
derives `assignment_principal=Codex` from that policy. An event actor string alone does not prove
the peer; the verified handoff result must bind the kernel-derived role, UID, GID and cgroup.
Rows from older operation names or without this exact result are legacy and are rejected for
issuer use.

## Read-only `assignment_basis` request and response

Request has exactly `schema` (`VST_S2_ASSIGNMENT_BASIS_REQUEST_V1`) and
`assignment_operation_id` (64 lowercase hex). It has no task, owner, policy, generation,
manifest or lease selector. Supervisor matches the request to one exact operation row, linked
verified NOTE event, policy and authenticated bootstrap result. Zero, multiple, malformed,
revoked, expired or noncanonical records refuse.

Response has exactly `schema` (`VST_S2_ASSIGNMENT_BASIS_RESPONSE_V1`),
`assignment_operation_id`, `handoff_sha256`, `policy_id`, `policy_sha256`,
`repository`, `sprint_id`, `source_head`, `manifest_sha256`, `task_id`, `story_id`,
`task_manifest_sha256`, `slot`, `attempt`, `epoch`, `lease_id`, `runner_id`,
`principal`, `run_id`, `probe_sha256`, `authority_expires_at_utc` and
`service_generation`. Every value is derived from the verified handoff, fixed policy and
current Store snapshot. Principal is the root-configured issuer audience `Codex`; the issuer's
own kernel identity is independently fixed by its `delegated_issuer` peer entry. The request
cannot choose either value.

Store implements this as one read-only transaction. Refactor
`execution_grant_basis()` into a locked internal helper that accepts the current SQLite
connection; do not nest `BEGIN` transactions. Within that same `_read_tx()`, verify the event
chain, external anchor and supervisor-operation/event correspondence on that connection, load the
exact operation row/result, validate the handoff schema and policy binding, and call the locked
basis helper with `expected_owner="Codex"` and the handoff's exact `expected_lease_id`.
Cross-check every basis field against the handoff; derive current service generation from the
root Supervisor provider and cap authority expiry by the current owner/lease expiry and handoff
expiry. The response is an observation in time, not a lease reservation or a promise of future
authority. Existing admission and Runner rechecks stay in force.

No direct Store access is added to the issuer. The allowlist adds an optional role with exactly
`assignment_basis`; existing dispatch_owner/dispatcher/runnerd/signer operation sets are
unchanged. Existing configs do not enable it by default. Root-owned config load is strict and
must reject duplicated roles, identity collisions, unexpected UID/GID/cgroup/policy bindings,
unknown operations and missing policy. No DB migration, new table, task enumeration or E5 change
is part of this read-only API.

Whole-policy revocation is fail-closed: the trusted Supervisor provider reopens the fixed
root-owned policy on every query and verifies its validity and exact configured digest pin.
Removing it, losing safe access, changing its bytes or allowing it to expire disables the API.
A cached policy alone is insufficient; a configured feature without a trusted provider refuses.
The provider is installed by trusted root service setup, never supplied by the RPC caller.
Individual assignment revocation is not implemented; revoke the whole policy if needed until
that narrower mechanism is separately designed. A `revocation_id` string by itself is not
evidence of checking a revocation source.

## Implementation order and focused tests

1. Implement pure exact handoff/request/response validators and the read-only locked Store helper.
   Keep the external per-task signed-record module detached; it is not the selected production
   source and must not be wired to the Supervisor.
2. Add a fail-closed `assignment_basis` Supervisor method and RPC for a separately configured
   issuer peer. It accepts only the opaque operation key and uses the root-derived policy/peer.
   Do not add assignment mutation in this change.
3. After independent source/security review of the authenticated upstream contract, implement
   the separate bounded bootstrap mutation entrypoint as its own reviewed change. It must write
   the exact handoff result and linked Store event atomically through existing operation APIs.
   Legacy events remain ineligible.
4. Designated functional-test-reviewer authors and runs tests after coding: valid same-transaction
   basis and no DB mutation; bad operation/event/result/payload hash or actor identity; legacy
   row; unknown/duplicate/expired/revoked assignment; wrong principal, task, slot, attempt, epoch,
   lease, run, policy or manifest; stale generation/authority; external-anchor failure; duplicate
   read-only requests; and confirmation that existing Supervisor roles still cannot call the new
   operation. E2E runtime/provisioning is separate and not proven by synthetic RPC tests.

Codex owns source and evidence. GPT-PM owns independent review and adjudication of
S2-MACHINE-ISSUER-M01. The operator owns explicit authorization of the exact production
delegation policy and any reserved production action. The external per-task operator signature
is retired from the proposed contract under this decision; the authenticated assignment writer
and final trusted production policy remain to be reviewed and authorized. S2-MACHINE-E5-M01,
current E5 v1, production dispatch, overall S2 closure and exact-head approval are unchanged.

## Fresh-only bootstrap transaction correction (design only; disabled)

This section narrows step 3 above. It is a proposed source contract, not implementation,
authorization, or evidence that a new endpoint is allowed. The earlier four-operation wording
must not be read as permission to compose the four public Store methods. Before any writer code,
security and database reviewers must approve this transaction boundary and GPT-PM must issue a
source GO. The production policy still needs the separately required exact authorization.

### Eligibility is one new assignment, not adoption or recovery

The only eligible transition is creation of one exact assignment pinned by the root-owned policy:
`story_id`, `task_id`, project and phase, canonical manifest digest and contents, and one declared
`TestRun` slot. The request identifies that policy tuple; it cannot widen it. The manifest's
`cost_cap` and `retry_cap` are fixed by its pinned digest, and `register_task` seeds the task budget
row from `cost_cap` (`tools/vst/store.py:1937-1972`). This design does not add a caller-selectable
budget override.

Eligibility is checked inside the write transaction against the same SQLite connection: the
operation key is new; the story and task IDs have no rows; the task has no lease, receipt, terminal
marker, or prior attempt; the requested slot is in both the pinned assignment and manifest and is
typed `TestRun`; attempt is exactly 1; Store reconciliation and event-chain verification are
healthy; and trusted Supervisor state supplies the current run, consumed probe, and service
generation. Any existing story/task/lease/receipt, noninitial attempt, expired assignment, prior
generation, legacy ownership, or existing operation is ineligible. In particular, this does not
adopt an unowned legacy story, refresh an expired lease/assignment, continue a new generation,
retry work, or act as a scheduler. A duplicate completed operation is handled only by the
idempotency rule below; it does not re-enter eligibility or reacquire anything.

### Minimum trusted policy inputs and identities

Extend the strict, closed root policy schema only with fields needed to make this one transition
deterministic: for the exact allowed assignment, `project_id` and `phase`; and at policy scope,
`owner_principal`, `worker_id`/`runner_id` (one configured identity with a specified mapping, not
two caller aliases), `owner_ttl_seconds`, and `lease_ttl_seconds`. Keep the assignment's exact
task/story/manifest digest/TestRun-slot allowlist. Reject unknown or missing keys, duplicate
assignment tuples, invalid types, nonfinite/nonpositive TTLs, and TTLs above a documented local
maximum. `owner_ttl_seconds` is passed to the existing epoch transition; `lease_ttl_seconds` to
lease creation. The budget cap remains the pinned manifest `cost_cap`; attempt budget is fixed at
1 and retry policy at the pinned manifest. Do not accept principal, worker/runner identity, owner,
epoch/generation, expiry, either TTL, budget values, run, probe, or policy digest from the RPC
caller. A request may carry only the fixed operation/request identifier and the exact assignment
tuple selectors needed to locate the one policy entry, plus its canonical manifest if required by
the existing RPC contract; compare every value to root policy before writing.

The kernel-authenticated peer (UID/GID/cgroup and process identity as already established by the
Supervisor transport) selects the single optional `assignment_bootstrap` role. That role alone
may invoke `bootstrap_assignment`; it is not a new authority class, scheduler, generic Store API,
or substitute for `delegated_issuer`. The trusted Supervisor derives the source principal and
current run/probe/service-generation values and checks them again in the Store callback immediately
before commit. The handoff records the fixed `owner_principal`, `runner_id`, epoch and lease
identifiers/expiry, assignment tuple, manifest digest, run, probe and service generation. The
response and stored handoff must contain the same committed values. A caller-supplied event actor
string is never identity evidence. This change provides no signing key, key distribution, policy
provisioning, service activation, or E5/runtime authority.

### One transaction; preserve existing public APIs

The current public `open_story` (`store.py:1633-1648`), `acquire_epoch`
(`1654-1665`), `register_task` (`1937-1972`), and `acquire_lease` (`2192-2300`) each own a
`self._tx()` transaction. Calling those public methods from an idempotent callback would nest
transactions and is prohibited. Implementation may extract connection-taking private locked
primitives from their existing bodies, preserving validation, events, return values, and public
wrappers. `_acquire_epoch_locked(conn, ...)` already exists (`1668-1717`); reuse it. Do not create
a second transaction abstraction or make a public method conditionally accept a connection.

One `Store.execute_idempotent` invocation owns the sole transaction. Its callback receives `conn`
(`store.py:3633-3663`) and invokes only connection-taking primitives. It creates the new story,
registers the pinned task and initial budget, acquires epoch 2 from the just-created epoch-1 story,
creates the attempt-1 lease and slot claim, and writes the complete handoff row/result. The
operation record and linked `SUPERVISOR_OPERATION` NOTE event are already written by
`execute_idempotent` on that same connection. Consequently, story/task/budget/epoch/lease/slot,
handoff/result, operation journal and event either commit together or roll back together. Do not
commit intermediate rows or perform network, signing, runtime launch, or other external effects
inside the callback.

The fresh preconditions are deliberately sufficient to make `acquire_lease`'s historical
commit-before-raise branches unreachable: there is no previous lease or failed attempt, so retry
exhaustion cannot hold; the budget row is just seeded with `spent = 0` and cap equal to the pinned
manifest `cost_cap`, so `spent > cap` and an existing budget marker cannot hold; and attempt 1 is
the only valid first attempt. Prove these predicates under the transaction before invoking the
lease primitive. If that proof fails, refuse and roll back. Do not remove, reorder, or change the
legacy public `acquire_lease` behavior that commits a signed retry/budget marker and raises after
commit (`2192-2300`); the new path must avoid those branches, not weaken their semantics. Extracted
locked helpers must not catch such errors and turn them into success.

### Idempotency, reconciliation and fail-closed errors

Use one domain-separated operation name and stable operation key derived from the authenticated
bootstrap request identity. `execute_idempotent` already hashes the canonical payload, returns the
stored JSON result for the same operation and payload, and refuses a key reused with different
operation or payload (`store.py:3633-3659`). For a duplicate exact completed request, return that
exact committed result without calling the callback, refreshing TTLs, incrementing epoch, or
reacquiring a slot. Conflicting payloads refuse. If the journal/anchor cannot establish whether a
first commit completed, use the existing operation reconciliation contract and return
`INCONCLUSIVE`/failure closed; never generate a new key, synthesize a result, or start a second
assignment. Any malformed/missing handoff or event, stale generation/run/probe, changed policy,
failed integrity check, or mismatch between committed result and handoff fails closed. The
read-only `assignment_basis` remains the independent way to verify the resulting committed
provenance; it is not itself a writer approval.

### Eligibility and failure matrix for the later implementation

| Case | Required result |
|---|---|
| Exact root policy tuple; absent story/task/history; attempt 1; live trusted run/probe/generation; healthy Store | One atomic initial assignment and a read-back-verifiable handoff |
| Same operation key and byte-equivalent canonical payload after commit | Return the exact stored result; no row/event/lease/TTL change |
| Same operation key with different operation or payload | Duplicate conflict; no write |
| Existing story or task, lease, receipt, terminal marker, or noninitial attempt | Refuse as ineligible; no adoption or refresh |
| Unknown policy tuple, wrong manifest digest/content, undeclared/non-`TestRun` slot, or caller attempts trusted-field override | Refuse before mutation |
| Wrong peer role/UID/GID/cgroup, absent policy, policy digest drift/expiry, or invalid TTL/config | Refuse before mutation |
| Run/probe/generation changes before the transaction's final trusted-state check | Roll back all assignment writes |
| No Store slot, stale row/fence, unexpected validation/SQL/event failure | Roll back all rows and operation event |
| Retry/budget marker condition is encountered despite fresh proof | Treat as invariant violation; transaction rolls back; preserve public legacy semantics |
| Commit/anchor outcome cannot be reconciled, or stored handoff/result/event disagree | Inconclusive/fail closed; never infer success or retry under a new key |

The later focused test plan belongs to the designated `functional-test-reviewer` and
`e2e-runner`, after implementation is complete: (1) one valid single-transaction bootstrap and
read-only basis verification; (2) same-key/same-payload exact-result replay with unchanged row
counts and TTL; (3) conflicting payload; (4) each existing-row/history exclusion; (5) peer,
policy, manifest, slot, attempt, TTL and caller-override rejection; (6) Store slot exhaustion and
injected failure at each write boundary proving complete rollback; (7) trusted run/probe/generation
change before commit; (8) simulated retry/budget invariant violation with rollback and a separate
regression proving the public `acquire_lease` still commits its legacy marker before raising; and
(9) uncertain anchor/commit reconciliation and mismatched handoff/event/result. These are planned,
not run. No endpoint is approved by this design; only fresh independent security/database review
and GPT-PM source GO can authorize a code batch.
