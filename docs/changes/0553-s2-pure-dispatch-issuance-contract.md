# Change 0553: Pure S2 root-bound dispatch issuance contract

## State

Bounded pure source preparation implemented under GPT-PM decision
`8b6b69f3-9b39-491b-a948-03c497870b5d`, correlated reply
`b1728c67-3bc2-4db5-9fbf-6b359a73ad82`. A follow-up reducer finding was fixed in this pass:
completion can no longer be accepted on envelope shape and digest alone. This does not implement
a signer, Store journal, Supervisor callsite, key/config producer, or runtime activation. Tests,
checks, build, runtime, review, PM exact-head verification, and commit were not performed in this
coding pass.

## Contract and changed paths

- `tools/vst/dispatch_issuance.py` adds detached validators for canonical duplicate-free JSON,
  the exact assignment policy and handoff shapes, explicit `DELEGATED_V1` key binding, stable
  deterministic issuance identities, and a frozen unsigned dispatch-instruction v1 intent.
- Request IDs use the approved
  `VST_S2_ROOT_DISPATCH_REQUEST_ID_V1\0` domain and the first 128 bits of SHA-256 over the
  canonical full validated handoff. Operation keys use the separate
  `VST_S2_ROOT_DISPATCH_ISSUANCE_OPERATION_V1\0` domain over the stable assignment operation ID;
  the full digest is retained. The frozen payload digest binds the full handoff, policy,
  unsigned v1 fields, current authority tuple, and signer identity.
- Freezing requires the explicit finite issuer maximum TTL and minimum safety slack from the
  approved root configuration. It persists both inputs and the preparation time, then verifies
  that expiry exactly equals the minimum TTL/handoff/policy/current-authority bound and retains
  the configured slack. No numeric TTL or slack is invented by this module.
- The pure event reducer accepts only intent → signing-started → completion or unknown ordering.
  A started operation without durable completion reduces to `UNKNOWN`; malformed bindings,
  duplicate/misordered events, changed payloads, and altered completion envelopes reduce to
  `CONFLICT`. `PENDING` and `UNKNOWN` never report signing authority. A Store transaction must
  separately claim a signing-started marker before any later implementation can invoke a signer.
- A durable completion is accepted only when `reduce_issuance_state(...,
  completion_verifier=callback)` receives an injected callable. Its exact interface is
  `callback(frozen_signer_binding, signing_bytes, signature_bytes) -> bool`: the binding is a
  copy of the frozen `{key_id, key_class, purpose, public_key_fingerprint}`, `signing_bytes` are
  produced by the unchanged v1 `dispatch_instruction_signing_bytes` contract (the
  `VST_S2_DISPATCH_INSTRUCTION_V1\0` domain followed by canonical unsigned-envelope bytes), and
  `signature_bytes` are the decoded Ed25519 signature. The reducer first checks exact unsigned
  equality against the frozen intent and the envelope key ID against the frozen signer; it accepts
  only the literal result `True`. The callback must verify Ed25519 and establish that its
  root-pinned public key has the frozen fingerprint and key identity. A missing verifier, false or
  non-literal-true result, or verifier exception yields `CONFLICT`. This callback contract does not
  provide key access or signing authority; the pure module reads no key and stores no verifier.
- The signing-started event now passes closed-schema validation before either `UNKNOWN` or
  completion can return, so unexpected extra fields consistently produce `CONFLICT`.
- Current revocation and expiry are an overlay (`REVOKED_EXPIRED`) and do not rewrite historical
  state. The reducer never infers signing authority from records and always returns
  `may_sign: false`. Existing v1 wire fields, signing domain, and signature encoding validation
  were not changed.

## Verification and remaining acceptance

- Source and interface were compared against `tools/vst/dispatch_instruction.py`:
  `verify_dispatch_instruction(value, trust_registry, *, expected_principal, openssl_path,
  now=None)` validates envelope shape, then uses `dispatch_instruction_signing_bytes` and the
  root-configured trust entry to verify the unchanged v1 signature domain. The pure callback
  adapter is not wired to that runtime verifier in this change. Independent review remains
  required for exact source.
- No test or static check was run during active coding. The designated functional-test reviewer
  must derive and execute pure-contract negative cases after S2 coding freezes.
- Store persistence, concurrency/crash behavior, signing, admission, delivery, grant enforcement,
  E5, provisioning, and production activation remain outside this change and are not approved by
  pure validation.
- This coding pass did not create a commit. Commit `0553` is recorded by the subsequent
  coordination pass after the explicit source and record paths were staged.
