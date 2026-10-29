# S2 M03 exact source/test review — 2026-10-29

## Correlated GPT-PM decision

- Request: `d16dbf96-54f8-4c96-8fa7-2b24445f85d9`
- Job: `4a1b0672-1ed2-4a1e-9561-c4871745ce68`
- User turn: `f435ecea-6025-4c99-af91-f49c0672a68c`
- Reply: `480839e2-2ad2-482f-85a8-c980bddb5bdb`
- Current repository HEAD declared: `f0804966a0d91c7423a0cd85fb179d1f67e814e9`
- Source/test HEAD: `c855ca4f2888d7288b006973950e4c6d28023b63`
- Baseline: `1bd00cbacac099f34717e9c68fc720a467f6d519`

Disposition: **ACCEPT — SOURCE/TEST SCOPE.** GPT-PM confirmed zero new BLOCKER and zero new
MAJOR, and marked `S2-PROV-M03-R01` **RESOLVED — SOURCE** for the submitted source/test revision.
It did not approve overall S2, production dispatch, E5, runtime provisioning, prohibited
selectors, push, PR, or merge.

## Adjudicated invariant

The historical-result route is distinct from current execution authorization. It accepts the
complete original envelope and authenticated principal, verifies the complete Store event chain,
anchor and accepted event/operation/control history in one read snapshot, then returns only the
matching immutable result with its original event sequence and service generation. It cannot append
or mutate Store state, change a lease, issue a grant, or launch Runner.

Current signature expiry, key revocation, or service-generation rotation cannot invalidate an
already verified historical acceptance. An absent or mismatched history is refused and never
falls through to new admission. New admission retains current signature, owner, lease, preflight,
generation, manifest, budget and receipt-position checks. Stale intents remain excluded from
current-generation delivery/grant paths; Runner claim and reservation fencing is unchanged.
Legacy-unresolved or corrupt history remains closed. A known compromise incident that casts doubt
on a past acceptance still requires separate security reconciliation.

## Evidence reviewed

- The attached focused run reported **130 passed, 0 failed**, exit 0, in Ubuntu 24.04 WSL with
  Python 3.12.3 and pytest 7.4.4, at source/test HEAD `c855ca4`. Exact command and four test-file
  hashes are in `s2-cross-generation-outcome-recovery-test-run-20261029.md`.
- GPT-PM checked three attached test-file hashes against the test record; all three matched. The
  fourth selected file, `test_s2_dispatch_owner_latch.py`, was not attached and its bytes were not
  independently checked by GPT-PM.
- Fresh independent code, security, reliability and database reviewers at repository HEAD
  `f0804966a0d91c7423a0cd85fb179d1f67e814e9` found no valid BLOCKER/MAJOR. They ran no tests or
  checks. Their source and exact-line findings are summarized in change 0537.
- GPT-PM did not independently inspect the Windows Git checkout to verify that repository HEAD
  `f080496` differs from source/test HEAD `c855ca4` only by evidence/state documentation. The
  declared relationship is recorded, not independently certified by that review.

## Remaining S2 gates

`S2-PROV-M03-R01` is closed for source and mapped tests. The full S2 remains NOT APPROVED.
`S2-DISPATCH-M01` is MAJOR/OPEN because no production coordinator/issuer/assignment identity is
present in this repository. Production identity/root configuration, installed systemd/runtime
behavior, E5 provenance, explicitly prohibited selectors, and the final overall exact-head GPT-PM
gate remain separate. S3 remains unstarted.
