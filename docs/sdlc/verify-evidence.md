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
| S2-1 / signed admission and recovery | Source/test acceptance retained; task delivery still open | Four-file WSL selection 130/130 at `2befed5`; source-fidelity verifier 5/5 at committed HEAD `206a746`; adapter functional/E2E 35/35 and 2/2 at `2befed5`; prior adapter regression 38/38 at `6952469`; exact Bridge-wrapper regression 38/38 at committed code HEAD `0da595e`. All 41 redactions map across 15 exact Git blobs/lines, with no confirmed defect from independent security assessment. GPT-PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` closed S2-REVIEW-01 but left S2-REVIEW-02 open. Fresh request `4986ec77-698e-4dd0-bdd9-7ca5c6281a46` again found no confirmed B/M in the parser fix, resolved the source-fidelity concern, and kept S2-REVIEW-02 MAJOR/HOLD because complete independent path coverage was not established. The exact review input SHA, attachment size, reply and delta audit are recorded in `docs/sdlc/evidence/s2-exacthead-coverage-adjudication-20261029.md`. | GPT-PM must re-adjudicate the exact current head using the recorded full-range baseline review plus complete post-`d3f326f` code/test delta audit; then task push. Installed runtime, systemd/kernel identity, production configuration and E5 remain unproven | Current PM result is `MAJOR/HOLD`, not approval. Prior and current code-review reports are static only and do not prove runtime | Codex owns coverage record/packet and review request; GPT-PM owns formal decision | Submit one fresh exact-head PM review with the explicit path-mapped coverage record; follow the actual correlated verdict, then verify before normal push |
| Current branch changed-code test refresh / AF attachment transport | Exact test results recorded; test outputs are not GPT-PM approval | At `2befed5`: adapter functional 35/35, adapter E2E 2/2, four-file WSL selection 130/130. At exact committed HEAD `6952469`: 38/38 for inner-header parser. At exact committed HEAD `0da595e`: 38/38 for exact PM Bridge wrapper, test and adapter matched Git blobs before/after. Prior PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` used a 5,842,177-byte input with SHA `0e7e8be1ebd52f8f27f7581c4fef999c9ba0efc2f486aa3ef86e6e660a2e5cd9`; adapter rejected its reply with `review_status=NOT_RUN`, `verdict=UNRECOGNIZED`, `receipt_written=false`. | Fresh PM review and normal push remain; no approval file or runtime activation | Previous PM disposition remains HOLD; current code is committed/tested, but no fresh exact-head decision exists | `functional-test-reviewer` owns tests; Codex owns evidence; GPT-PM adjudicates | Submit new exact-head attachment through corrected adapter and inspect actual correlated result before push |
| S2-2 / authenticated owner transport | Prior source/test accepted | Existing 34-case WSL transport record, explicitly mocked kernel identity | Real activated endpoint to Runner | Genuine configured runtime and authority | Codex | Execute only mapped permitted runtime scenarios after gates |
| S2-3 / exact bundle and bootstrap preparation | Focused M-S2-3-03 review approved on source HEAD `ef465cd` (request `17aa39d9-fb95-4d27-ba94-858fe1cc954d`); exact bundle approved for inactive stage-only on plan SHA `59ebfee0435d7a34f4c09de6ef5269e08d7a6713a5e7301497ba754ef348d8e9`, inventory SHA `a3b6ea38103edfb0d25cab8ef3c2e405d8bcb2d08c0d16194668b4860095d054`, archive SHA `bc489ce6155e178b1f2c2ef6a9e8b88e78c3b3e991576107319c9b34c3543d44` (request `29c0c463-9d18-4c35-ae9d-8ed5331a4f70`). | Designated-runner direct regression: 4 passed, 8 deselected, 0 skipped on committed source `043980f`; blobs unchanged at reviewed `ef465cd`. | Run bounded stage-only before inventory expires; then collect and obtain separate review of complete post-stage manifest. | M-S2-3-03 and exact pre-stage package accepted. Stage not yet executed under refreshed approval. Store UNKNOWN; no selection, unit writes/activation, production keys/E5 or production. | Codex owns preparation/evidence; GPT-PM owns both correlated decisions; e2e-runner owns mapped test execution. | Execute only the exact hash-pinned stage-only operation after confirming the five-minute freshness bound and installer preconditions. |
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


## Post-integration current source verification — 2026-10-29

Sprint: 39b7cc253f5d

Source freeze: `67d1d55e5556c6936516f3404202faecba1e6707` on
`s2-canonical-continuation` in `D:\Repo\Virtual_scrum_team`.
The earlier writer-HOLD matrix above is historical and superseded for SOURCE by
GPT-PM's I01 SOURCE GO and the implementation/fixes through change 0564. It remains
correct that installed runtime, current E5 and final Phase 8 are not thereby proven.
No existing external coordinator is required: the bounded assignment/issuer source
is implemented in Store/Supervisor and the operation-ID-only authenticated route.

### Current permitted evidence

The actual functional and E2E roles are `gpt-6-luna`, medium effort. Their public
records retain exact commands, overlay hashes, environment, failed prior revisions
and current results. Tests are synthetic source/Store/RPC or explicit dedicated-WSL
permission boundaries, not production service activation. Results must not be added
across overlapping groups or revisions.

| Current selection | Source / result | Evidence and limit | Owner / next acceptance |
|---|---|---|---|
| Four functional modules, Windows | 67d1d55: 62 passed, 6 skipped | `evidence/s2-final-functional-e987a24-20261029.md`; six POSIX-only signed-key fixture cases are not Windows passes. | Codex reviews exact evidence; POSIX counterpart below. |
| Same four functional modules, WSL | 67d1d55: 68 passed | E2E reported terminal success with exact overlay hashes, including private-root fixture correction. | Codex reconciles the final E2E public command record. |
| Full delegated issue-to-reservation path and negative integration controls | 67d1d55 WSL: 26 passed | Completed issuance, admission/replay, exact grant persistence/replay, claim/reserve, duplicate refusal, live revocation and missing-link refusal. | Codex obtains fresh independent source reviews. |
| Legacy schema-v5 and TP28 regressions | 67d1d55 WSL: 7 passed | Current legacy/direct compatibility remains permitted without delegated downgrade. | Codex retains separate exact selector evidence. |
| POSIX anchor and worker/reviewer identity boundary | 67d1d55 WSL: 10 passed | Dedicated existing WSL fixture only; not production credentials or Windows ACL proof. | Codex preserves the platform limitation. |
| Windows allowed E1/E3/E6 and integration selection | 67d1d55: 97 passed, 26 skipped | E2E current report; skips are 25 POSIX-only integration cases and one POSIX reviewer case. | Codex maps each allowed result to original acceptance; no skip promoted. |
| Bundle/source plan/bootstrap/stage-only fixture groups | Prior 8beffcc: WSL 36 passed; Windows 28 passed, 8 skipped | Product paths and test modules unchanged by Store-only 0564. Historical scoped evidence, not a claim of a new run or installed bundle. | Codex includes source/blob identity in review; GPT-PM reviews exact staging candidate later. |
| Additional allowed E7 pub/sub, owner and idempotency contracts | 67d1d55: Windows 40 passed / 17 skipped; WSL 35 passed; separate WSL latch 7 passed | Exact nodes and fixtures in both public role reports. Windows POSIX skips have an explicitly separate WSL counterpart, not a Windows pass. | Codex obtains independent review; no real service/process operation is inferred. |
| Allowed E7 lifecycle, breaker and simulated recovery contracts | 67d1d55 Windows: 34 passed across six exact invocations | Source-inspected callbacks, synthetic keys, disposable SQLite and in-process threads. Real process recovery is NOT_RUN. | Local bare-Git/fake-PR fixture and pre-spawn injected timeout also passed; actual termination, remote providers and runtime remain NOT_RUN. |

### Remaining real acceptance and ordered closure

1. Allowed E7 regression mapping and current public records are complete for the
   permitted source scope. Codex commits the package with change record 0565; the
   source/test blobs, not an invented cumulative count, identify this evidence.
2. Codex launches fresh actual general-code, database and security/reliability reviews
   for the exact source package. Fix all confirmed code BLOCKER/MAJOR findings in a
   focused batch and run only designated direct regressions.
3. Codex prepares the exact final non-secret source staging plan and current target/
   compiler metadata. GPT-PM adjudicates the bounded source/runtime package before
   any actual staging, key/policy installation, runtime signing or service activation.
4. Current E5 still requires genuine run-bound evidence under the accepted contract.
   Operator owns any reserved human attestation; Codex owns permitted preparation and
   collection. No signature, policy installation or activation is inferred here.
5. Restricted actual termination/crash/mutation/E8 scenarios remain NOT_RUN. Codex
   supplies exact remaining scope; GPT-PM adjudicates acceptance and the operator
   owns any genuine scoped waiver or restriction change. A waiver cannot erase FAIL.
6. Only after acceptance and fresh exact-head GPT approval may Codex push/open the
   single S2 PR. S3–S5 remain ordered behind S2 closure. No self-written approval.


### Frozen-source specialist consensus and live observation

All three actual fresh-context reviewers completed their declared full new S2
source surfaces at d3f326f37a40936402d3933d5266e0ffb01017f0. Confirmed code
BLOCKER:0; MAJOR:0. See
`evidence/s2-frozen-source-reviews-d3f326f-20261029.md` for roles, exact scopes,
base, line evidence, initial capacity rejection and corrected security-scope sweep.
These findings do not claim an exhaustive generic audit or runtime acceptance.

The six committed test blobs at d3f326f match the exact SHA-256 overlays recorded
for current67d1d55 execution. The only tools/vst or tools/qa path changed between
those commits is tools/vst/schemas/README.md; product source did not change.

Permitted live Windows collection was actually attempted with fixed PS7, no fallback.
`Get-NetFirewallProfile` is unavailable in that restricted PS7 context although the
NetSecurity2.0.0.0 module is discoverable. An explicit native import also failed;
its precise exception is UNKNOWN, not an asserted permission error or source bug.
No complete snapshot/counts exist; normalization remains unsupported. Raw host data
is private and not part of this packet. Public sanitized record:
`evidence/s2-windows-live-observations-d3f326f-20261029.md`.

Requested GPT-PM adjudication is the exact code package and residual acceptance,
not a claim that S2 is fully done. If a bounded runtime step is authorized, state
its exact scope separately: stage an immutable versioned tree and helper from the
reviewed source/compiler recipe only, preserve the selected old runtime and units,
collect post-stage fingerprints, then review that transition manifest before any
selector/config/keys/service signing or activation. No source-plan JSON grants
permission. Existing compiler/path inventory is dated evidence and must be refreshed
for the actual stage. Genuine E5 and restricted-case disposition remain explicit;
Codex will not invent an operator signature/waiver or an external coordinator.

### S2-3 reviewed source/stage bundle verifier follow-up (2026-10-29)

- Baseline source HEAD: `c97836029a5d94ff84dee5cb15d1757efd5525c3` on
  `s2-canonical-continuation`; code and tests were run from the working-tree overlay, not from a
  committed S2-3 revision.
- The exact focused command was:
  `python -m pytest -q tests/vst/test_s2_wsl_bundle_verifiers.py tests/vst/test_s2_source_staging_plan.py tests/vst/test_s2_runtime_bundle.py tests/vst/test_s2_bootstrap_runtime.py tests/vst/test_s2_stage_only_install.py`.
- Designated `e2e-runner` execution: Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4;
  **54 passed, 0 failed, 0 skipped**, exit code 0. The initial run had 46 passed and 8 failed;
  triage established two test matcher wording defects and six failures from bootstrap's obsolete
  schema-1 marker comparison. The matchers now accept the actual hard-link refusal diagnostics,
  and bootstrap compares the complete schema-3 provenance marker to the reviewed manifest.
- Exact run ID, transfer and archive digests, and all 45 input-file SHA-256 values are recorded at
  `evidence/s2-3-focused-posix-rerun-d6d3fea7d21c4d01900b37860a29c2fa.md`.
- Independent `code-reviewer` reviewed that final schema-3 bootstrap comparison and found no
  blocker: the exact field set matches the bundle builder and stage verifier, so missing, extra,
  or mismatched marker values are refused.
- The test runner used and removed `/run/vst-test-8f280caeee154d11aa483cfef987a2c7`. It reports
  no repository/system/runtime mutation. These are fixture/source-contract results; no WSL target
  inventory, live runtime installation/selection, service activation, Store/key/E5 action, or
  production owner-to-Runner path was performed.
- Remaining S2-3: commit the task files, obtain the fresh exact-head GPT-PM verdict, then create
  fresh source-head-bound plan/inventory before the conditionally authorized stage-only operation.
  Previous GPT-PM `MODIFY` is not approval. S2-4 and S2-5 remain queued; no later sprint task has
  started.
