# S2 fresh bootstrap SOURCE authorization and root-bound issuer — 2026-10-29

Owner: Codex (implementation/coordination); GPT-PM (architecture/source adjudication).
Request: `8b6b69f3-9b39-491b-a948-03c497870b5d`; job: `4a1bded0-a2b5-4b74-bf89-22b0e9fa01cb`; correlated reply: `b1728c67-3bc2-4db5-9fbf-6b359a73ad82`.
Persisted transport status `uncertain`, result.correlated=true. Parked client deadline expired, but job status recovered the exact correlated reply below; no resend occurred.

## Exact reply

ChatGPT said:

REQUEST_ID: 8b6b69f3-9b39-491b-a948-03c497870b5d

S2 — Authenticated Bootstrap and Root-Bound Issuer Adjudication
DECISION 1: GO — SOURCE
DECISION 2: MODIFY

Reviewed source: 3d5f6c2048238a79fb92ddf805bc562b4b392a63
Scope: Fresh-only assignment bootstrap and delegated dispatch-instruction issuance architecture.
Excluded: Production authority, keys, provisioning, activation, E5 and final S2 approval.

1. Decision 1 — Fresh-only bootstrap writer

GO. Codex may implement the bounded bootstrap_assignment source and its mapped tests.

The fresh-only addendum resolves the architectural concerns identified in the previous review. The reviewed contract now specifies:

An authenticated assignment_bootstrap role distinct from delegated_issuer.

One exact assignment constrained by the root-approved policy.

Creation only when the story, task and corresponding assignment history are absent.

Attempt 1 only, with no adoption of existing or legacy assignments.

One execute_idempotent transaction for story, task, budget, epoch, lease, slot and immutable handoff.

Trusted run, consumed probe and active service generation.

Immutable replay without refreshing authority, changing TTLs or creating a second assignment.

Full rollback on failed eligibility, SQL, event or Store checks.

The proposed approach also correctly avoids nesting the existing public Store methods, whose transaction ownership would otherwise make the combined operation invalid.

The attached independent database and security design rechecks report no remaining design-level MAJOR in this scoped writer. Those reports support proceeding to implementation, while actual source acceptance remains a separate review.

S2-MACHINE-ISSUER-M01 is not yet closed: the upstream architecture is sufficiently specified for source implementation, but the authenticated writer itself has not been implemented and verified.

2. Decision 2 — Reuse root Supervisor for dispatch signing

MODIFY — accept the root-bound, purpose-separated v1 design as the preferred minimal architecture, with one mandatory issuance-state correction.

A separate issuer daemon and dispatch-instruction v2 format are not intrinsically required.

The existing root Supervisor already holds the trusted Store reference, manages generation and preflight validation, and signs execution grants. A distinct dispatch-instruction key, trust purpose and admission contract can be added without creating another scheduler or assignment authority.

This does not mean reusing the execution-grant signing key. The two signing authorities must remain cryptographically separate.

Recommended topology

The alternative keeps the signed v1 wire fields unchanged. The additional provenance lives in the root-controlled Store issuance record and is referenced by a deterministic signed request_id.

This is acceptable only because the Supervisor, not the external caller, verifies the exact journal record and handoff.

The journal must not be treated as optional logging. For a delegated key ID, it is a required part of authorization.

3. Required correction: issuance must be crash-consistent
1 DESIGN MAJOR — OPEN

Finding ID: S2-MACHINE-ISSUER-I01
Affected paths: Proposed Supervisor issuer method, Store.execute_external_idempotent(), Store.accept_dispatch_intent() and delegated-key verification.

The existing execute_external_idempotent() supports external effects and records pending/completed/unknown events. However, it explicitly permits repeating an effect when an earlier attempt has no confirmed completion, relying on the external backend to enforce idempotency.

A cryptographic signing operation is deterministic for identical Ed25519 inputs, but invoking it again after an ambiguous outcome is not equivalent to establishing that the original result was durably completed.

More importantly, a newly evaluated issuance request must not change its generation, expiry, request ID, key identity or assignment basis while retaining the same logical authorization identity.

Required state contract

State

	

Allowed behavior




ABSENT

	

Validate exact current authority; atomically commit immutable issuance intent




PENDING

	

No alternate issuance or new identity; resolve exact prior state




COMPLETED

	

Return exact persisted envelope bytes if current retrieval policy permits




UNKNOWN

	

Fail closed until exact evidence establishes completion or safe non-completion




CONFLICT

	

Refuse permanently for that operation identity




REVOKED / EXPIRED

	

No new admission or signing

The immutable issuance intent must fix all unsigned v1 fields before invoking OpenSSL, including request_id, expires_at, key_id and the full assignment tuple.

Its journal binding must also contain the handoff digest, policy digest, original run and generation, signer identity and intended envelope digest.

The original signature is then produced outside the SQLite transaction and the exact signed envelope is committed as a completion record.

No OpenSSL invocation may occur inside Store.execute_idempotent() or any other held SQLite write transaction.

A completed historical result may be inspected without creating new authority. Whether it can subsequently be admitted for execution still depends on current expiry, revocation, Store ownership, lease, probe and generation checks.

This is a design correction to the proposed issuer, not a defect confirmed in the currently implemented Store source.

4. Why v1 can remain unchanged

The v1 signed instruction contains the exact task, slot, attempt, epoch, run ID, request ID, key ID and expiry.

It does not itself contain a policy or handoff digest. That omission is not automatically unsafe if a delegated-key verifier enforces an additional trusted mapping:

Plain text
signed v1 request_id
        ↓
exact immutable issuance journal
        ↓
authenticated assignment handoff
        ↓
approved delegation policy
        ↓
current Store authority

The required binding is:

request_id
=
Trunc
⁡
128
(
SHA256
⁡
(
domain
∥
handoff identity
)
)
request_id=Trunc
128
	​

(SHA256(domain∥handoff identity))

The final domain and canonical identity must be fixed in the source contract, and the journal must reject collisions or reuse under changed policy, key, generation or envelope identity.

The deterministic request ID is an index and consistency binding, not proof of authorization by itself.

Delegated-key admission must remain atomic

For delegated key IDs, Store.accept_dispatch_intent() must verify, within the same admission transaction:

An exact completed issuance record exists.

The accepted signed instruction equals the journal's canonical signed envelope.

The journal links to a valid authenticated bootstrap handoff.

The policy and handoff were authorized under the applicable immutable root trust configuration.

The original handoff and issuance tuple match the current task, manifest, lease and run.

The current key/policy is neither revoked nor expired.

The current Supervisor generation and Store authority remain valid.

This must also be enforced when the same intent is later considered by next_dispatch_intent() and issue_dispatch_intent_grant(). Otherwise a policy revoked after acceptance could still permit a queued delegated instruction to receive a grant.

Those paths may read the verified immutable journal and repeat current authorization checks; they must not mint another instruction or change the historical acceptance.

The existing historical replay_dispatch_outcome() remains observation-only. A historical result may be recovered without restoring execution eligibility.

5. Preserve explicit legacy separation

The dispatch trust registry must distinguish:

Key class

	

Admission




Existing legacy v1 key

	

Existing approved v1 verification contract




Delegated-machine v1 key

	

v1 signature plus mandatory issuance journal, handoff and policy verification




Unknown or unclassified key

	

REFUSE




Revoked delegated key

	

REFUSE new admission/delivery/grant

A delegated key must never be reclassified as an unrestricted legacy key because its journal is missing or the feature is disabled.

The root-owned key registry must explicitly pin the key class and signing purpose. No key can silently move between classes on restart or configuration reload.

A distinct dispatch-instruction private key can reside in the existing root Supervisor trust boundary, but it must not be accessible to the relay, dispatcher, Runner or workers.

The extra permissions and configuration required for issuance remain subject to separate source and production authority reviews.

6. Focused source authorization and verification

Work item

	

Decision




Fresh-only bootstrap_assignment Store/Dispatcher-independent source

	

GO




Atomic locked Store helper refactoring

	

GO




Authenticated bootstrap-only Supervisor RPC

	

GO




Synthetic positive/negative/bootstrap rollback tests

	

GO




Root-bound v1 issuer architecture and pure validation contract

	

GO — DESIGN/SOURCE PREPARATION




Production private-key signing implementation

	

HOLD




Production issuer-key creation/provisioning

	

HOLD




Actual dispatch signing and admission activation

	

HOLD




Machine E5 attestation

	

HOLD

The next implementation tests must prove the fresh writer's atomic rollback and exact replay, then independently test the proposed issuance state machine for duplicate operations, ambiguous signing, journal corruption, concurrent requests, policy revocation, changed generation and legacy-key separation.

The designated functional and E2E reviewers should execute these mapped tests after implementation. Independent security/database reviewers must inspect the exact resulting source. The implementation author must not self-approve.

The recorded Windows/WSL 23 tests, WSL 36 component tests and WSL 16 journal tests remain component evidence at their respective source revisions, not one combined final-head pass. The report also preserves an exploratory historical schema-v5 failure rather than treating it as passing coverage. 
verify-evidence.md

7. Final gate disposition

Criterion

	

Status




Fresh-only authenticated bootstrap writer design

	

ACCEPTED — SOURCE GO




S2-MACHINE-ISSUER-M01 upstream provenance architecture

	

Design specified; implementation OPEN




Root-bound v1 delegated issuer design

	

MODIFY — I01 OPEN




Separate issuer daemon

	

NOT REQUIRED




Dispatch-instruction v2

	

NOT REQUIRED for selected Store-bound design




Per-task operator signature

	

NOT REQUIRED




Production delegated policy/key authorization

	

NOT ESTABLISHED




S2-MACHINE-E5-M01

	

MAJOR / OPEN




Existing operator E5 v1

	

UNCHANGED




S2-DISPATCH-M01

	

MAJOR / OPEN




Overall S2 / Phase 8

	

NOT APPROVED




S3

	

BLOCKED pending S2 acceptance

Final decision

DECISION 1 — GO: Codex may implement the narrowly specified, fresh-only, disabled-by-default authenticated assignment writer and submit actual source/test evidence for focused review. No additional generic operator approval is needed for that source preparation.

DECISION 2 — MODIFY: Use the existing root Supervisor rather than another issuer daemon, and retain v1 dispatch-instruction wire format. Before implementing production signing, make issuance reservation, immutable input freezing, ambiguous-outcome handling, journal authentication and delegated-key admission verification explicit in one exact contract.

Confirmed BLOCKER: 0. New proposed-design MAJOR: 1 (S2-MACHINE-ISSUER-I01).

Neither decision approves runtime activation, Store migration, key provisioning, machine E5, restricted selectors, production dispatch, push/PR/merge or full S2 acceptance.

Evidence boundary: This adjudication is based on the supplied source and review records. I have not independently verified Git HEAD 3d5f6c2 against the Windows checkout, rerun the recorded tests or performed host mutations.

