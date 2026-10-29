# S2 Store-backed assignment provenance alternative — 2026-10-29

Owner: Codex (coordination); GPT-PM (architecture adjudication).
Request: `4b2e7e61-c0bd-407d-9b2c-b9078da5f7d9`. Source: successful PM Bridge send-and-await harvested response, preserved verbatim below. This is architecture scope, not source/runtime/final approval.

## Exact response

Persisted PM Bridge correlation subsequently verified: job
`bb7d72a5-6525-4831-bb02-92421660298a`, reply `dd91f9f4-728f-44ee-8e88-6762280569f1`,
status `succeeded`, `correlated=true`. The response text below is unchanged.

ChatGPT said:

REQUEST_ID: 4b2e7e61-c0bd-407d-9b2c-b9078da5f7d9

S2 — Store-Backed Assignment Provenance Architecture
MODIFY
ALTERNATIVE ACCEPTED IN PRINCIPLE
1 MAJOR OPEN

Project: Virtual_scrum_team
Review scope: Alternative remediation for S2-MACHINE-ISSUER-M01 only
Decision: An authenticated Store-backed assignment provenance source can replace the proposed per-task operator signature, provided the upstream assignment authority is established and enforced.

1. Architecture ruling

A separate human signature for every task is not intrinsically necessary.

The code-explorer's central observation is correct: the existing Store already contains significant assignment and execution-authority information.

In particular:

Store.execution_grant_basis() verifies a current owner epoch, registered manifest, eligible TestRun slot, live lease, consumed preflight, receipt position and budget. 
store.py

Supervisor._validate_current_dispatch_intent() supplies the signed intent's principal as expected_owner and the recorded lease identity as expected_lease_id. 
supervisor(7).py

Runner admission and reservation independently recheck execution authority. Those checks remain required.

These mechanisms support using the root Supervisor and Store as the source of current assignment facts instead of introducing an external per-task authorization database.

However, one distinction remains decisive:

A verified Store assignment is not automatically proof that the assignment was created by an authorized actor.

The proposal must close that upstream boundary before the machine issuer can treat a Store assignment as sufficient signing authorization.

2. Focused finding

Finding

	

Severity

	

Decision




S2-MACHINE-ISSUER-M01 — authenticated assignment provenance

	

MAJOR

	

PARTIALLY RESOLVED / OPEN




New confirmed BLOCKER

	

—

	

0




Additional confirmed MAJOR within this alternative

	

—

	

0




S2-MACHINE-E5-M01

	

MAJOR

	

OPEN — outside this review

S2-MACHINE-ISSUER-M01 — Upstream authorization is not yet authenticated

The exact gap is visible in the Store interfaces.

Store.acquire_epoch() accepts an owner string and establishes that owner when no currently live owner exists. Store.acquire_lease() accepts a task, worker, epoch and attempt under its existing Store checks.

These methods enforce state consistency, but their public in-process arguments do not themselves authenticate the actor requesting the mutation.

For example, Store.acquire_epoch() validates that the supplied owner is nonempty and applies the ownership compare-and-swap. It does not verify a kernel-authenticated caller identity. 
store.py

Consequently, this sequence is not yet sufficient:

Plain text
Store says owner = Codex
    ↓
Machine issuer requests assignment_basis
    ↓
Supervisor confirms current owner = Codex
    ↓
Machine issuer signs

The missing question is: Who was authorized to establish that Store ownership and lease in the first place?

The HMAC event chain protects recorded history against undetected alteration within its key-custody assumptions. It does not independently authenticate the original assignment decision.

This is the remaining MAJOR invariant—not the absence of a per-task human signature.

3. Required narrow upstream contract

The safe alternative is a fixed, authenticated assignment/bootstrap boundary that uses the existing Store APIs rather than introducing a second authority.

The minimum upstream requirements are:

1. Authenticated assignment principal. A root-configured service identity, pinned by UID/GID, cgroup and kernel peer credentials, may invoke only the specifically authorized existing Store transitions. It must not become a general-purpose Store writer.

2. Fixed delegation scope. A reviewed, operator-authorized policy binds the machine principal to Virtual_scrum_team, the exact repository, approved sprint/manifest scope, allowed owner Codex, permitted transitions, validity and revocation. This authorizes a class of operations, not arbitrary work.

3. Bounded mutation entrypoint. Any required assignment/bootstrap RPC must use exact fields and existing Store compare-and-swap mechanisms. It cannot accept a caller-asserted owner identity as authentication evidence.

4. Durable provenance. The authenticated actor, delegation-policy identity/digest and exact assignment operation must be durably attributable to the resulting Store transition. A plain event actor string is insufficient unless the trusted API derives and fixes it.

5. Fail-closed legacy behavior. Historical assignments created before authenticated provenance was established cannot automatically become eligible for delegated machine issuance. They require independently authorized reconciliation or a fresh, properly authenticated assignment transition.

6. No arbitrary task discovery. The issuer must receive one exact authorized work reference. It cannot enumerate tasks, select the next task or turn an arbitrary requested task ID into proof of assignment.

This does not require a new human participant. The sole operator may authorize a bounded machine bootstrap role through a concrete delegation policy. The machine's authenticated execution then supplies the per-operation provenance.

4. Exact assignment_basis contract

A separate read-only Supervisor RPC is acceptable within this architecture.

A suitable operation name is:

assignment_basis

It must be restricted to the new purpose-specific issuer peer, not added to the generic dispatch_owner, dispatcher, runner or signer roles.

Request

The minimal request should identify an exact, preauthorized assignment handoff, such as an opaque assignment-operation identity whose issuance is rooted in the authenticated upstream transition.

It must not accept a caller-controlled owner principal, service generation, manifest digest or policy as authoritative values.

If the request includes task_id, slot, attempt or epoch for matching, those fields are selectors only. The Supervisor must derive their authoritative counterparts and validate them against the authenticated handoff.

Response

The root Supervisor derives and returns an immutable snapshot containing:

Field

	

Authoritative source




Project/repository/sprint scope

	

Approved root-owned delegation manifest and registered task




task_id, story_id, slot, attempt

	

Authenticated assignment handoff and Store




principal

	

Trusted peer/delegation mapping, expected Codex




epoch, lease_id, worker identity

	

Current Store state




manifest_sha256, timeout and budget eligibility

	

Registered Store manifest/budget




run_id, consumed probe identity

	

Current Supervisor/Store preflight




service_generation

	

Trusted current Runner generation provider




Owner/lease authority expiry

	

Current Store snapshot




Delegation policy ID/digest

	

Root-controlled approved policy




Assignment-operation ID/digest

	

Verified authenticated transition history

The Store must verify these facts within one consistent read snapshot, rather than assembling independently timed responses.

The response is a short-lived statement of observed authority, not a lease reservation or durable promise that the authority will remain valid.

The issuer must verify that sufficient authority remains for issuance. Supervisor/Store must recheck current authority at dispatch acceptance; Runner must continue its existing claim/reservation fencing.

No signed instruction may be issued from a stale, incomplete, ambiguous or unverified assignment basis.

5. Issue-once and v2 instruction rules

The proposed machine issuer remains bounded by the earlier accepted safeguards:

One exact assignment identity produces at most one immutable signed envelope.

The issue-once journal preserves the original request ID, expiry and canonical signed bytes.

A confirmed duplicate returns the exact stored envelope.

An ambiguous signing/journal outcome never authorizes generating a replacement identity.

The private signing key remains unavailable to relay, dispatcher, Runner and worker.

The issuer cannot create tasks, leases or ownership.

The v2 envelope should bind the authenticated assignment-operation digest and root-derived snapshot, along with the immutable deployment-policy scope.

The existing v1 instruction and verifier must remain unchanged during preparation. A new v2 verifier must explicitly enforce the new provenance fields and must not accept a v1 instruction as equivalent machine-delegated authority.

The submitted design currently describes a mandatory externally signed assignment-authorization record. That part may be replaced by the authenticated Store provenance contract, but the design document must be revised consistently: removing only the signature field while retaining references to an external authorization object would leave contradictory trust rules. 
S2_DELEGATED_MACHINE_TRUST_DESIGN.md

6. Can the external per-task operator signature be retired?

YES — as a proposed design requirement.

The earlier requirement for independently authenticated assignment provenance did not inherently require a per-task operator signature.

The external signed-authorization record was one possible way of establishing provenance. A properly authenticated and durably attributable Store assignment/bootstrap operation can satisfy the same security objective.

This ruling therefore permits Codex to retire the mandatory external per-task signature from the candidate architecture, replacing it with the upstream authenticated assignment provenance mechanism described above.

It does not authorize removing any existing production signature verification. The approved v1 dispatch-instruction verification and current operator E5 requirements remain unchanged.

A concrete operator-authorized delegation policy is still needed to establish which machine principal may create or approve assignments. Broad GO alone is not a substitute for that exact machine-authority policy.

7. Source work permitted now
BOUNDED READ-ONLY SOURCE GO

Codex may implement and test a strictly read-only assignment_basis path after updating the architecture contract to specify its authenticated handoff and required provenance fields.

The permitted source work includes:

Pure validators for the delegation and assignment-basis schemas.

A read-only Store snapshot function.

A narrowly authenticated Supervisor RPC with fixed issuer-role authorization.

Synthetic tests for exact matching, wrong principal, stale epoch/lease/generation, unknown assignment, missing provenance, expired delegation, integrity failure and read-only behavior.

Documentation replacing mandatory per-task operator authorization with authenticated Store provenance.

The following remain held: production issuer signing code, machine-key provisioning, new privileged assignment mutation endpoints, activation, runtime dispatch and any change to the E5 acceptance verifier.

The upstream mutation/bootstrap contract must receive independent source/security review before such an endpoint is implemented or enabled.

8. Final status

Gate

	

Decision




Store-backed provenance alternative

	

ACCEPTED IN PRINCIPLE




Mandatory external per-task operator signature

	

MAY BE RETIRED FROM CANDIDATE DESIGN




S2-MACHINE-ISSUER-M01

	

MAJOR / OPEN — upstream provenance invariant




Read-only assignment_basis source preparation

	

AUTHORIZED




Production machine issuer

	

NOT AUTHORIZED




S2-MACHINE-E5-M01

	

MAJOR / OPEN — unchanged




Machine E5 replacement

	

NOT ACCEPTED




S2-DISPATCH-M01

	

MAJOR / OPEN




Full S2 / Phase 8

	

NOT APPROVED

Final disposition — MODIFY

The simplified approach is preferable to requiring a human to sign every task, provided authenticated assignment provenance begins at the Store mutation boundary.

execution_grant_basis() already supplies most of the current-state validation needed for a read-only issuer query. It does not supply authenticated provenance for the original assignment creator.

Required next step: Codex should revise S2_DELEGATED_MACHINE_TRUST_DESIGN.md to replace external per-task authorization with one precise authenticated bootstrap/assignment-operation contract, then implement only the read-only basis API and mapped synthetic tests.

One MAJOR remains open for this alternative: S2-MACHINE-ISSUER-M01.

No operator question is needed for this bounded design/source preparation. No production authority, key creation, privileged provisioning, E5 approval, restricted testing, push, PR, merge or full S2 acceptance is granted.

Evidence limitation: This decision is grounded in the attached Store, Supervisor, Supervisor RPC and candidate design files. It does not verify a deployed assignment source, a live WSL identity, current signed E5, or an exact Git HEAD.

