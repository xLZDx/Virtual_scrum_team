# Change 0564: Reserve the exact current PENDING claim

Sprint: 39b7cc253f5d

Owner: Codex. Test execution: designated functional and E2E roles.

## Trigger and change

At 8beffcc the E2E owner recorded a WSL run with 31 passed and one failed.
The genuine issuer/admission/grant/replay/claim path reached reservation, where the
new delegated current-authority check treated the just-created PENDING claim as a
prior unresolved execution. The failure was in the product, not the fixture.

The existing locked authority chain now carries an optional reservation grant ID.
Only reserve_runner_execution supplies it, after exact persisted claim matching and
verification that the claim has precisely one PENDING event. The continuation guard
exempts only that same claim while retaining every other predecessor check. The
exception cannot admit a new claim, replay a PENDING grant, reserve twice, or accept
an EXECUTION_RESERVED/terminal state. All manifest, lease, owner, generation, key,
issuance, probe, budget, receipt and deadline checks remain in the same transaction.

## Verification state

All test commands were terminal before source modification. Tests/checks/build/CI
were not run by the primary agent. Required regressions owned by E2E: full positive
reservation, duplicate reservation and claim rejection, unrelated pending predecessor
refusal and delegated provenance refusal. Functional fixture corrections for POSIX
root-controlled key ancestors and the Windows subprocess constant are separate test
owner changes; real trust guards must not be weakened. Results at 8beffcc are historical,
not post-fix acceptance. Runtime installation/signing/services and E5 remain unproven.
