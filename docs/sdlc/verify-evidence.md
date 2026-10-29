# S2 verification evidence and remaining acceptance

Sprint: 39b7cc253f5d

Product sprint: existing S2. Framework phase: 7 Verify. This is an evidence record, not an
approval file. Overall S2 remains NOT APPROVED; production/runtime criteria below are unresolved.

## Provenance and verification layers

Continuation baseline: `9c1be0f`. Runtime journal correction: `5724ba8`. Read-only authenticated
assignment API: `c2b1cd2`; current run/generation correction: `3d5f6c2048238a79fb92ddf805bc562b4b392a63`.
Later documentation changes do not imply these tests executed at a different source revision.
The primary agent coordinated tests and assessed coverage but did not author or execute them.

Reconciliation addendum (2026-10-29): the complete original epic/deferred-item denominator and
the 0552/0553 decision boundary are mapped in [S2 original epic coverage reconciliation](S2_ORIGINAL_EPIC_COVERAGE_MATRIX.md).
The corrected historical schema-v5 fixture has its own two-selector result in
[s2-legacy-v5-fixture-run-20261029.md](evidence/s2-legacy-v5-fixture-run-20261029.md); it is
maintenance evidence and does not combine with the component rows below or establish final-head
S2 acceptance. GPT-PM's recovered correlated source reply and exact limits are recorded in
[the bootstrap and issuer adjudication](evidence/s2-bootstrap-source-and-root-issuer-adjudication-20261029.md).
Unsigned host/guest observations remain UNKNOWN as detailed in
[s2-machine-observations-20261029.md](evidence/s2-machine-observations-20261029.md). The root-bound
issuer design is linked separately at [S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md](S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md);
it is design/source preparation only and does not close its issuance-state finding.

The implementer reported one accidental `git diff --check` invocation during this continuation
with no output. This report was not independently reproduced and is not a test, build, runtime,
or acceptance result. It does not alter the exact commands and owners reported below.

| Actual role / model / effort | Source and command scope | Recorded result | Boundary |
|---|---|---|---|
| functional-test-reviewer / gpt-6-luna / medium | Three new runtime-bundle/source-plan/machine-contract test files; exact source/hash references in s2-bootstrap-functional-run-20261029.md | Windows 30 passed / 6 POSIX skips; WSL 36 passed, exit 0 | Real synthetic Ed25519 keys and public verification in WSL; detached candidate contracts, no production authority |
| e2e-runner / gpt-6-luna / medium | Two bootstrap/stage-only test files at c2b1cd2; s2-bootstrap-e2e-run-20261029.md | WSL 16 passed; Windows 8 passed / 8 POSIX skips | Disposable filesystem and mocked systemd boundaries; real harmless Python argv mapping; ordinary partial-write exceptions, no process crash |
| functional-test-reviewer / gpt-6-luna / medium | test_s2_assignment_basis.py plus two explicitly named safe Store regressions at 3d5f6c2; s2-assignment-basis-functional-run-20261029.md | Windows 23 passed; WSL 23 passed, exit 0 | Real disposable Store read transactions and synthetic future handoff; no authenticated production writer or configured peer |

The three rows are separate commands at their identified revisions; do not present them as one
full-suite or final deployed-head run. Runtime-bundle and journal components unchanged by the
run/generation correction retain their recorded component-level evidence. All exact commands,
tool versions, hashes, skipped cases and limitations are in the linked records.

## Independent review and corrections

| Actual reviewer / model / effort | Findings and disposition | Remaining scope |
|---|---|---|
| code-reviewer (s2_runtime_code_review) / gpt-6-luna / medium | Two valid MAJORs: partial preparation journal and partial retention copy could strand retry. Fixed at 5724ba8, reproduced then passing by E2E owner, focused source recheck on 3d5f6c2 resolved both. Argument-index finding explicitly retracted; actual subprocess test confirms existing indexing. | Source/fixture proof only |
| security-reviewer (s2_runtime_security_review) / gpt-6-luna / medium | No reachable BLOCKER/MAJOR in reviewed runtime/candidate-contract diff 9c1be0f..7e9c519 | Production trust and E5 unchanged |
| database-reviewer (s2_basis_database_review) / gpt-6-luna / medium | No reachable BLOCKER/MAJOR in read-only source diff 5724ba8..3d5f6c2; one consistent read transaction and rollback-only close, chain/anchor/journal/probe/live-authority checks | Future writer needs atomic conn-taking helpers and explicit failure contract |
| security-reviewer (s2_basis_security_review) / gpt-6-luna / medium | No reachable BLOCKER/MAJOR in the same read-only source; optional issuer-only operation, trusted current policy/run/generation | Future writer and real deployment are not accepted by this source review |
| database-reviewer and security-reviewer focused design rechecks / gpt-6-luna / medium | Fresh-only writer addendum resolves the previously reported transaction, eligibility, authenticated caller and replay/legacy design gaps; no remaining design-level MAJOR in the reviewed slice | Explicit GPT-PM SOURCE decision still required before writer implementation; production is separate |

Focused tests also found duplicate embedded guard, independent revocation-ID conflation, and
stale Supervisor run/generation acceptance. Fixes 0544, 0545 and 0549 are linked to their negative
regressions. An exploratory historical schema-v5 selector is incompatible with the pre-existing
schema-v6 baseline; its unchanged hard-coded assertion and failed command remain recorded, not
hidden or counted as new-feature coverage. Codex owns its backlog reconciliation.

## Acceptance matrix

| Criterion / meaning | State | Evidence/completed work | Remaining acceptance | Dependency/blocker | Owner | Next step |
|---|---|---|---|---|---|---|
| S2-1 / signed admission and recovery | Prior bounded source/test acceptance retained; selected Store regressions pass | Prior M03 records and current two targeted Store cases | Actual installed-runtime properties are not inferred | Runtime qualification below | Codex | Preserve historical/source boundaries in final gate |
| S2-2 / authenticated owner transport | Prior source/test accepted | Existing 34-case WSL transport record, explicitly mocked kernel identity | Real activated endpoint to Runner | Genuine configured runtime and authority | Codex | Execute only mapped permitted runtime scenarios after gates |
| S2-3 / exact bundle and bootstrap preparation | Implemented, source-tested, independently reviewed | Source plan generator, stage-only path, manifest/selector/journal and fixes; compiler/known-path metadata | Exact current source-plan review, inactive artifact staging and post-stage manifest review | Current plan is unsigned; no actual install/selection occurred | Codex; GPT-PM adjudicates | Regenerate exact plan after source freeze, submit source/test/review bundle |
| S2-4 / authenticated assignment and runtime provenance | Read-only basis implemented/tested; full criterion OPEN | One-snapshot journal/probe/lease/run/generation proof and issuer-role refusal | Authenticated bootstrap writer, precise policy, issuer, genuine current E5 and real journey | Writer source held pending corrected contract review; production/E5 not authorized | Codex; GPT-PM adjudicates; operator owns exact production policy/reserved trust acts | Review fresh-only writer transaction contract and obtain bounded SOURCE decision |
| S2-5 / exact-head gate and delivery | OPEN | Correlated architecture decisions and actual role evidence retained | Fresh full S2 acceptance and exact-head GPT-PM approval, then one sprint PR | S2-3/S2-4 runtime acceptance unresolved | GPT-PM; Codex coordinates | Submit complete evidence only when prerequisites established; never self-approve |
| Restricted scenarios / process-kill, crash/recovery, mutation, E8 and policy selectors | NOT_RUN | Explicit restrictions preserved | No pass or waiver inferred | Prohibited execution | Operator for any changed scope; Codex preserves status | Leave NOT_RUN; obtain only a precise authorized disposition if required for acceptance |

## Ordered remaining work

1. Codex obtains independent focused DB/security review of the fresh-only writer transaction
   addendum, then GPT-PM's explicit bounded source decision. No new human owner or external
   coordinator is required; per-task operator signatures are retired from the proposed design.
2. Complete only newly authorized source, then mapped tests and direct specialist review. Keep
   new writer and issuer disabled until exact policy/runtime gates are satisfied.
3. Regenerate source staging plan for the final code revision; GPT-PM reviews it with compiler and
   current target metadata before staging. Review actual tree/helper/old-state fingerprints in a
   separate post-stage selection manifest. Neither plan is an approval or activation permit.
4. Establish genuine current runtime/E5/authority evidence under the accepted contract; restricted
   scenarios remain NOT_RUN. Finish S2 acceptance and exact-head gate before S3 implementation.

Current human E5 verifier is unchanged; unsigned machine observations always remain UNKNOWN.
No production signing key/service, Store migration, dispatch activation, push, PR or merge is
claimed by this record.
