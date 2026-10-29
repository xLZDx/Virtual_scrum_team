# Change 0474 — Preserve S2 legacy recovery and stable WSL archive bytes

Date: 2026-10-28  
Sprint: S2  
Branch: `s4-canonical-continuation`  
Base HEAD: `7120e2c647cc95703704905efa76de735ca8d0ec`  
State: source corrections and 154 focused tests complete on the working diff; installer retry, fresh exact-head reviews, live runtime evidence, and GPT-PM final gate pending.

## Why

Fresh architecture review of change 0473 found that valid schema-v5 `PREDECESSOR_GENERATION_STOPPED` records written before 0473 could be rejected by the new validator, potentially integrity-locking a populated Store after upgrade. The first compatibility patch only covered part of the contract. Assigned tests caught three linked omissions: successor eligibility did not recognize the legacy disposition, the validator could skip a mismatched predecessor field, and startup history replay still required the new `terminal_disposition` field. In parallel, the exact-head S2 WSL installer failed because Git on this host exported LF shell scripts from `git archive` as CRLF when `core.autocrlf=true` and `* text=auto`; `/bin/sh` rejected `set -eu\r`.

## Changes

- `tools/vst/store.py`: accept the exact pre-0473 seven-field schema-v5 generation-stop event only after binding its grant ID and payload digest, actual predecessor state, and a distinct nonempty recovery generation. Apply the semantic validation in startup replay, claim-state inspection, and successor eligibility. A validated `PENDING` predecessor proves no execution was reserved and may be followed only by separately authorized work; an `EXECUTION_RESERVED` predecessor remains indeterminate and cannot authorize a successor. New terminalization events retain their stricter complete claim bindings. No schema migration was added.
- `tools/qa/install_wsl_runtime.ps1`: invoke `git archive` with `core.autocrlf=false` so POSIX source bytes in the deployment payload remain LF regardless of the caller's global checkout configuration.
- `tests/vst/test_s2_persistent_runner_service.py`: assigned functional-test-reviewer added a fresh-Store reopen regression for exact legacy history, separate preflight/successor authority, and five malformed/mismatched semantic variants whose event-chain MAC and anchor remain valid.
- `docs/sdlc/evidence/s2-wsl-installer-preflight-7120e2c-20261028.md`: retain the exact initial installer failure, deterministic archive conversion reproduction, read-only WSL snapshot, and limitations.
- Added exact attempt evidence for the regression/focused test rerun. Updated S2 state/backlog/decision/lesson records and the document registry.

## GPT-PM design basis

Correlated design clarification request `b84e73a1-55ac-47b0-87f8-20261028f002`, reply `8cc3b2ca-fc98-4d8a-98ee-120579a9cde6` permits successor gaps only after exact authenticated `PENDING` `NO_EXECUTION_PROVEN` or signed `EFFECTS_RESOLVED` from `EXECUTION_RESERVED`, with a separately authorized successor and no synthetic receipt. Change 0474 preserves the older pre-0473 `PENDING` event as equivalent only where the schema-v5 authenticated history and exact event shape prove that same pre-reservation invariant. The clarification is design-only, not an exact-head final gate.

## Verification

The designated `functional-test-reviewer` ran on Python 3.14.3 with committed base `7120e2c...` plus the final working source/test diff:

- Legacy schema-v5 compatibility nodes: 6 passed.
- Persistent runner module: 62 passed.
- E1 contract gate: 32 passed.
- E2 runner lifecycle: 38 passed.
- E6 diff gate: 22 passed.
- Unique focused total: **154 passed, 0 failed, 0 skipped**. The six legacy cases are included in the persistent-module total and are not double-counted. Each command emitted one `pytest-asyncio` deprecation warning.

Exact commands, hashes, IDs, failed intermediate attempts, and limits are in `docs/sdlc/evidence/s2-pre0473-schema-v5-compatibility-20261028-attempt2.md` (SHA-256 `b07ef56298579c322b01c604ba284c89b559f03f186254c5cc9bff15acc9a0f4`). This is focused in-memory/fresh temporary Store evidence, not a production database migration or deployed service proof.

At exact HEAD `7120e2c...`, the WSL provisioner read-only snapshot and failed install are recorded in `docs/sdlc/evidence/s2-wsl-installer-preflight-7120e2c-20261028.md`. The install failed before publishing runtime files; no pre-existing destination was overwritten. Read-only archive inspection established CRLF in the tar payload and the committed blob remained LF. The stage reported at failure was absent at the later read-only inspection; it was not deleted by this task. The current `core.autocrlf=false` archive correction has not yet been exercised at a new committed HEAD.

Five specialist reviewers at HEAD `7120e2c...` found one architecture MAJOR (legacy history compatibility) and no other new BLOCKER/MAJOR in their reviewed scopes; the regression led to the corrections in this change. Exact role-by-role findings and evidence limits are recorded in `docs/sdlc/evidence/s2-change-0473-specialist-review-20261028.md`. Fresh exact-head specialist reviews of the final 0474 diff remain pending.

## Remaining S2 acceptance

- Re-run the installer only after change 0474 is committed at its exact HEAD; collect permitted runtime evidence through `e2e-runner` only. Do not run process-kill, crash/recovery, mutation, E8, or policy selectors.
- Runtime snapshot is configuration evidence only: no external traffic was probed; full effective egress, descriptor/forwarding boundary, Windows containment, and deployed worker execution remain unproven.
- `S2-DISPATCH-M01` remains MAJOR/OPEN because no production coordinator call site exists. No scheduler, CLI, spool, or new assignment authority was introduced.
- Operator-only reconciliation peer credentials are not provisioned/active. E5 still requires actual run-bound operator attestation; no signature is inferred.
- Obtain fresh exact-head specialist reviews and one correlated GPT-PM final gate. Do not push/PR/merge or start S3 before the applicable gates.

