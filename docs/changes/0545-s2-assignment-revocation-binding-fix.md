# Change 0545: keep assignment revocation independent from policy revocation

## Scope and reason

Sprint: S2. Correct the candidate assignment verifier in
`tools/vst/machine_authorization.py` after phase-7 test feedback found that the field-binding
loop compared the assignment record's own `revocation_id` with the signed delegation policy's
different `revocation_id`. The two records have independent revocation identities; equality is
not part of the assignment contract and caused valid, independently revocable assignments to be
rejected before signature and current-Store-snapshot verification.

## Change

Removed `revocation_id` from the policy-to-assignment equality bindings. The verifier continues
to reject an assignment when its own `revocation_id` occurs in the configured revocation list.
The signed policy continues to be checked by `verify_policy`, which independently checks the
policy revocation identifier and the delegated machine principal's revocation identifier. The
assignment verifier also independently rejects a revoked delegated issuer principal. No schema,
signature, project binding, issuer key binding, policy digest, or Store snapshot comparison was
weakened.

## Verification and limits

This is a source-only correction prompted by phase-7 test-agent feedback. No tests/checks were run
by this implementation agent. The test owner is to rerun the focused assignment authorization
case and its revoked-assignment/policy controls. The module remains a candidate validator, not a
production caller or authority source; caller-provided Store snapshot authentication is outside
this function. No signing service, private-key handling, Store I/O/mutation, E5 PASS, runtime
activation, provisioning, or production dispatch was added.

The earlier candidate-contract record is
`docs/changes/0543-s2-machine-source-contracts.md`; this file records the later correction and
must be committed with the corresponding source change.
