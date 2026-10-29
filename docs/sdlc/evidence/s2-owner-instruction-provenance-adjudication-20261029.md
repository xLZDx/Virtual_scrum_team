# S2 signed dispatch-instruction provenance adjudication — 2026-10-29

## Correlation and scope

- GPT-PM request: `7c64c79c-452c-454f-9c55-3143a0fe2976`
- PM Bridge job: `65d31f0e-ba68-411a-8d9a-aeaa5d6c1f0d`
- User turn: `820712a7-3927-4abd-b115-8755623ac987`
- Correlated reply: `4c5606a1-6026-56e3-914b-61c89a7e45a9`
- Declared source baseline: `0dac9d58a3dd5bf779e1a2908a1ff2929ef5e69f`
- Verdict: `MODIFY — OPTION A WITH SUPERVISOR VERIFICATION`

The decision authorizes source work only for the trusted dispatch-instruction verifier. It retains
`S2-DISPATCH-M01` as `MAJOR / OPEN`, full S2 as `NOT APPROVED`, and S3 as blocked. GPT-PM reviewed
the supplied files and previously established S2 contracts; it did not independently fetch the
declared Git HEAD, run tests, or modify this repository.

## Binding contract

An explicit signed instruction can establish provenance for one exact dispatch request without
creating a second assignment authority. The Store remains the sole task, assignment, and lease
authority. The signer can authorize only an exact request for already-assigned work; it cannot
create tasks, assignments, leases, or execution grants.

The signed envelope binds the exact fields:

`version`, `algorithm`, `purpose`, `request_id`, `task_id`, `slot`, `attempt`, `epoch`, `run_id`,
`key_id`, `expires_at`, and `signature`.

The six dispatch identifiers plus key ID and absolute UTC expiry must be included in a canonical,
domain-separated Ed25519 signature. The issuer supplies a unique 32-character lowercase
hexadecimal `request_id`; the client must preserve it on replay. No unsigned field may change
authorization meaning. Principal, UID/GID, worker, command, model, artifact path, Store/config path,
grant, or lease mutation instructions are prohibited from the envelope.

The root Supervisor must independently verify the exact schema, version, algorithm, signature,
domain/purpose, pinned key, principal mapping, expiry, key revocation/trust, request identity,
current Store owner and lease, epoch, attempt, manifest slot, run-bound preflight, budget, and
service generation before appending `DISPATCH_INTENT_ACCEPTED`. Client verification alone is not
sufficient. Missing/unavailable trust configuration and malformed signatures fail closed; no
unsigned compatibility path is allowed. The exact signed envelope and key identity must be bound
to the hash-chained event and durable idempotency record: identical request ID plus identical
envelope may resolve to the same outcome; the same ID with different bytes is refused.

Trust is purpose-separated. The client has no signing authority. The instruction private key
belongs to an independently authorized issuer; the public verification key belongs in a
root-controlled Supervisor registry mapping key ID to principal and purpose. It must not be reused
for E5 attestation, execution grants, Store event integrity, receipts, or reconciliation.

## Authorized and prohibited work

Authorized source work:

- Strict typed signed-envelope parsing and verification.
- Purpose-specific Ed25519 verification against a pinned public-key registry.
- Expiry, revocation, principal binding, exact-envelope replay protection, and Supervisor-side
  verification.
- Tests with synthetic signing fixtures, explicitly identified as non-production test keys.
- Keep submission fail-closed until real trusted issuer configuration exists.

Not authorized:

- Creating or reusing an instruction-signing private key or inventing an authorized signer.
- Account creation, root configuration installation, migration application, runtime installation,
  service activation, real dispatch, network-policy claims, or E5 operator attestation.
- Adding a scheduler, task/assignment/lease authority, task enumeration/selection, queue/spool, or
  grant-signing path.

The decision explicitly requires `M01 MAJOR / OPEN` until implementation, independent source and
security review, an actually authorized issuer and pinned public key, OS identity/service boundary,
Store admission, Pub/Sub delivery, one-use grant/Runner integration, replay/revocation/generation
evidence, authorized runtime acceptance, and the exact-head GPT-PM gate are evidenced. Source
authorization is not runtime authorization or acceptance.

## Next steps and owners

1. Codex implements the envelope verifier and Supervisor enforcement while preserving the
   fail-closed default.
2. `functional-test-reviewer` authors and executes the acceptance cases after source coding is
   complete; GPT-6 Luna is the required/default model for that test role.
3. Codex coordinates exact-scope architecture/security review; GPT-PM reviews the exact resulting
   source and trust-registry contract.
4. The operator owns any separate decision to establish a real instruction issuer/private key or
   authorize privileged runtime provisioning. No signer/key exists in current evidence, and no
   secret is requested in chat.

`S2-DISPATCH-M01` and full S2 remain open until all applicable source, runtime, and gate evidence
is complete.
