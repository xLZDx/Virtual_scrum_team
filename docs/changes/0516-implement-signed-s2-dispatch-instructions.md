# Change 0516: verify signed S2 dispatch instructions at the Supervisor boundary

## Change summary

Implemented the GPT-PM-adjudicated signed instruction path for the S2 dispatch-owner client. The
client accepts only an exact versioned Ed25519 envelope, verifies it locally, and forwards the full
envelope. The authenticated root RPC derives the principal from kernel peer mapping and verifies
the signature again; `Supervisor` repeats verification before Store authority checks. `Store`
persists the full signed envelope and key ID in the hash-chained dispatch event and binds them to
the durable idempotency digest. Delivery and grant issuance revalidate signature, expiry, key
purpose/principal and current Store authority. No unsigned fallback is accepted.

The change does not create a signer or private key, root configuration, account, assignment source,
scheduler, queue, or migration. It does not install a runtime, activate services, dispatch work,
produce E5 evidence, or close S2/M01.

## Why

The first owner-client implementation accepted a public caller-constructible task-shaped object.
An authenticated process and a current Store owner/lease prove peer identity and assignment state,
but not that the exact dispatch request was authorized. A focused code review found a MAJOR. The
temporary fail-closed client removed the unsafe RPC path.

GPT-PM selected a purpose-specific signed instruction without creating a second assignment
authority, with a binding requirement that the root Supervisor independently verify it. The Store
remains the sole task/assignment/lease authority. The signer may authorize only one exact request
for already-assigned work.

## Affected contracts and files

- `tools/vst/dispatch_instruction.py` defines the exact envelope, canonical UTC expiry,
  Ed25519-only algorithm, domain-separated canonical bytes, key purpose/principal mapping, and
  fail-closed verifier.
- `tools/vst/dispatch_owner_client.py` verifies and forwards the complete envelope without
  constructing or changing request identity.
- `tools/vst/supervisor_service.py` accepts only the envelope, uses kernel-authenticated peer
  principal, verifies it at the RPC boundary, and requires a root-configured public-key registry.
- `tools/vst/supervisor.py` repeats verification before Store admission, and rechecks provenance
  before delivery and grant issuance, including expiry and revocation state.
- `tools/vst/store.py` binds the envelope and key ID into the event and idempotency digest and
  cross-checks their exact correspondence to the event request fields.
- `docs/sdlc/evidence/s2-owner-instruction-provenance-adjudication-20261029.md` preserves the
  correlated architecture decision; `s2-dispatch-owner-client-design-20261028.md` reconciles the
  superseded unsigned proposal with the signed contract.
- `docs/sdlc/evidence/s2-dispatch-owner-client-review-20261028.md` records the initial MAJOR and
  focused re-review of the temporary fail-closed stub.
- `docs/sdlc/evidence/s2-root-runtime-provisioning-plan-20261028.md` records a non-secret,
  unprovisioned identity map and the current read-only WSL inventory.
- `core/STATE.md`, `core/BACKLOG.md`, `core/DECISION_LOG.md`, and `core/LESSONS_LOG.md` record the
  current S2 state, ownership, GPT-PM decisions, corrected symlink-mode interpretation, and the
  owner-client provenance lesson.

## Key decisions

GPT-PM source request `7c64c79c-452c-454f-9c55-3143a0fe2976` returned `MODIFY — OPTION A WITH
SUPERVISOR VERIFICATION`, correlated reply `4c5606a1-6026-56e3-914b-61c89a7e45a9`, job
`65d31f0e-ba68-411a-8d9a-aeaa5d6c1f0d`, user turn `820712a7-3927-4abd-b115-8755623ac987`. The
signed fields bind `version`, `algorithm`, `purpose`, `request_id`, `task_id`, `slot`, `attempt`,
`epoch`, `run_id`, `key_id`, and `expires_at`. The issuer supplies the request ID; the client does
not derive a substitute. Root Supervisor independently verifies the pinned purpose-specific
public key's principal and signature before Store admission. The exact signed envelope is included
in event and idempotency data.

No unsigned compatibility fallback is permitted. The current event-history validator rejects a
legacy unsigned dispatch event, causing Store startup/history verification to fail closed rather
than allowing it to reach a grant. Compatibility with any pre-existing such Store has not been
proven; no automatic conversion or migration was performed.

The trusted issuer and public key are not present in current evidence. The production path remains
unusable until an independently authorized issuer and root-pinned public key are provided through
the proper custody path. Do not create/reuse a signing key or claim M01 acceptance.

## Review and verification state

- GPT-PM source scope: exact response above authorizes source verifier work and synthetic-fixture
  tests; it explicitly does not authorize signer/key generation, account or root-config creation,
  migration application, service activation, real dispatch, or E5 attestation.
- Prior focused code review found a MAJOR in the first caller-constructible instruction version.
  After conversion to an unconditional fail-closed stub, the same reviewer confirmed no RPC path;
  evidence is `docs/sdlc/evidence/s2-dispatch-owner-client-review-20261028.md`.
- Fresh code-reviewer review of the signed-envelope implementation at working-tree base HEAD
  `0dac9d58a3dd5bf779e1a2908a1ff2929ef5e69f` found no confirmed BLOCKER/MAJOR. The reviewer
  confirmed exact schema/domain binding, RPC and Supervisor verification, Store authority checks,
  durable envelope binding, and signature revalidation at delivery/grant. The known fail-closed
  legacy-history and empty-trust-registry startup limitations are in
  `docs/sdlc/evidence/s2-signed-dispatch-code-review-20261029.md`. The review agent used GPT-6
  Luna; launch effort was not recorded in the primary session. No test/check/build was run by the
  reviewer.
- Functional acceptance tests are pending a designated `functional-test-reviewer` run at the
  exact committed source. No tests, checks, builds, CI, migrations, WSL writes, account/key/config
  provisioning, service activation, or real dispatch were performed for this change.

## Ordered next actions

1. `functional-test-reviewer` authors and executes the synthetic-key contract tests against the
   exact source head; retain direct-RPC, tamper, expiry, revocation, replay, Store-authority and
   unsigned-history coverage.
2. Fix only valid BLOCKER/MAJOR findings, then obtain fresh architecture/security review of the
   final implementation and direct regressions.
3. Obtain GPT-PM exact-head review of the code/test evidence. This source review is not production
   runtime approval.
4. Keep M01 open until an authorized issuer/key, separately reviewed runtime config, permitted
   runtime evidence and final S2 gate exist. Keep S3 unstarted.
