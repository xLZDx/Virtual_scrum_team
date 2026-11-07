# Change 0589 — S2-4 V2 authorization source slice

Date: 2026-10-30
Owner: Codex
Task: S2-4 bounded V2 authorization source slice (one ordered task; full S2-4 remains open)

## Why

GPT-PM request `70c7fd31-463d-47ad-b95b-dd8916d7218c` approved a design clarification for a
separate V2 machine-authorization contract. This change implements only the approved, bounded
source slice: validators and a root-owned read-only comparison. It does not grant authority to
sign or dispatch work, provision production trust, activate runtime, or replace human E5.

## What changed

- Added closed V2 policy, trust-registry, and assignment-authorization schemas with distinct V2
  signature purposes and fail-closed scope, key-purpose, expiry, and revocation validation.
- Added a pure comparator for an already verified V2 authorization and one Store snapshot.
- Added a root Supervisor verification method that accepts only an authorization ID from the
  caller, obtains the authorization/policy/trust from configured providers, checks the configured
  issuer peer and live root assignment policy, reads the current Store snapshot internally, and
  compares the complete immutable tuple.
- Added synthetic-key/disposable-Store tests and updated the design, backlog, test plan, and
  evidence record.

## Files

- `tools/vst/machine_authorization.py`
- `tools/vst/supervisor.py`
- `tests/vst/test_s2_machine_authorization_v2.py`
- `docs/sdlc/S2_DELEGATED_MACHINE_TRUST_DESIGN.md`
- `docs/sdlc/backlog.md`
- `docs/sdlc/test-plan.md`
- `docs/sdlc/evidence/s2-4-v2-authorization-source-20261030.md`
- `docs/changes/0589-s2-4-v2-authorization-source.md`

## Verification and review

The actual `functional-test-reviewer` authored and executed the tests. On Windows, Python 3.14.3
reported 2 passed and 11 POSIX-only skips. In Ubuntu-24.04 WSL, the focused command reported 13
passed in 0.79s, 0 skipped, exit 0. The exact command, source snapshot SHA-256 values, corrected
fixture history, and limitations are recorded in
`docs/sdlc/evidence/s2-4-v2-authorization-source-20261030.md`.

Final read-only `code-reviewer` and `security-reviewer` reviews reported no actionable finding in
this bounded diff. `git diff --check` returned no output. No build, migration, production key or
config provisioning, Store mutation, dispatch activation, E5 signing, or restricted selector was
run. These checks do not prove installed runtime or production behavior.

## Acceptance boundary and follow-up

GPT-PM approved the bounded source/test slice at exact code HEAD
`aa3496322ca7b05955dd60dfee7decd8056f34ee` (request
`b53d89ab-aca1-4432-87d3-5b139592f575`, correlated reply
`0477831c-98fa-5e91-8416-5b5b4ff7cacd`, 0 BLOCKER / 0 MAJOR). Full S2-4 remains **OPEN / not
accepted** because:

1. The verifier is not connected to a production or RPC issuance route.
2. The legacy V1 caller-selected operation-ID route remains an integration finding and must be
   disabled or cryptographically bound by the separately approved issuer implementation.
3. Production providers, identity/configuration, key custody, current run-bound provenance, and a
   genuine owner-to-Runner journey are absent or unverified.
4. Current human E5 remains required; no machine E5 replacement is approved.
5. Restricted process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`.

Codex owns the bounded source task delivery and next issuer proposal; GPT-PM owns contract review
and exact-head decisions; the operator owns reserved production delegation authorization and
human-attestation/key-custody actions. No later task starts before this task's acceptance record,
commit, and normal push are complete.
