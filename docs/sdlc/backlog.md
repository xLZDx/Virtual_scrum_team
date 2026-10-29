# S2 backlog and acceptance plan

Sprint identity: Agentic_Framework sprint `39b7cc253f5d`, mapped to the already active project sprint **S2**. This is a tracking association, not a new sprint. S3 remains unstarted.

## Current execution checkpoint — 2026-10-30

This backlog is the ordered task queue. Dated evidence and older narrative sections retain their
historical scope; they must not silently reopen accepted code. Before a new implementation or
review, identify the missing numbered acceptance criterion and check its existing approval and
implementation. An accepted item is reopened only with a concrete regression or changed accepted
requirement. Permission to prepare a candidate does not make that candidate mandatory for S2.

| Order | Task / state | Evidence / remainder | Owner / next action |
|---|---|---|---|
| 1 | S2-4 tracking reconciliation — corrected in change0591 | Correct stale writer/issuer HOLD and push-pending summaries against I01 SOURCE GO, code/test approval `c978360`, and successful task push through `e09c78b`. | Codex: verify the containing commit is normally pushed, then take item 2. |
| 2 | S2-4 exact runtime inputs — VERIFIED, DELIVERY PENDING | Source compatibility fix a600774 is pushed; actual strict stage-only publication succeeded. Bundle32 artifacts, nine unit bindings and three rate-limit overrides are pinned to actual source/helper/task/policy/run identities. False local GPT-PM credential labeling was corrected; review and test evidence is retained in change0595. | Codex: normally commit/push change0595 and this exact bundle before the next runtime execution item. Focused9-case suite and actual UID999 command/parser passed; local registry HMAC valid/tamper checks passed; security and unit evidence are linked. Existing delegation is carried forward; no generic permission is pending. |
| 3 | S2-4 current E5 and real owner-to-Runner evidence — after item 2 delivery | Actual run-bound measurements and real execution remain to be produced; decisions already delegated by the operator are carried forward. Restricted scenarios remain NOT_RUN. | Codex prepares and coordinates actual evidence; designated test roles execute qualification; GPT-PM adjudicates required final acceptance. Do not repeat generic permission requests. |
| 4 | S2-5 final acceptance — not started | Requires S2-4 acceptance plus final revision/evidence review. | Codex assembles; GPT-PM decides. S3 remains unstarted. |

## Historical source update — change0556 (current state above)

The fresh-only authenticated assignment bootstrap is implemented in change0552 (`45dcf47`);
the detached issuance/verifier contract is change0553 (`e44f48d`). GPT-PM request
`c7a8e23e-91f5-489c-a096-c813d84c3b12`, correlated reply
`7c3e4eb6-3300-5c5b-ba5c-85aaa10d0487`, returned **GO for bounded integrated SOURCE** and
accepted the corrected I01 design as implementation-ready. This supersedes the earlier source
HOLD for the issuer; it does not supersede runtime, key provisioning, real signing, E5, forbidden
selector or final S2 gates. The specialized journal, root-Supervisor v1 issuer and transaction-bound admission/grant/runner
guards are present in the code/test scope approved at `c97836029a5d94ff84dee5cb15d1757efd5525c3`. There is no missing external
coordinator or unassigned owner. Required I01-SRC-01 through I01-SRC-05 are recorded in
`evidence/s2-i01-integrated-source-adjudication-20261029.md` and design change0554.

The historical schema-v5 fixture item below is resolved by change0551 and its designated
six-case fixture evidence; it is not a current product blocker. Final S2 tests still wait until
all in-scope coding is complete. Historical story/epic rows retain their original evidence scope.

## Sprint goal

Deliver and qualify the existing Store-authorized signed dispatch path through the real Runner boundary, while preserving fail-closed behavior and keeping production dispatch disabled until the required runtime evidence and exact-head approval exist.

**Scope boundary:** use the accepted `DispatchOwnerService` → authenticated Supervisor/Store admission → Store-filtered Pub/Sub → `StoreBackedDispatcher` path. Store remains the sole task, assignment, lease, and durable dispatch authority. No new scheduler, coordinator product, assignment authority, or external coordinator is needed. For the current exact qualification, Codex executes the delegated technical configuration, key preparation and truthful root-machine measurements described in requirements.md, current execution scope. Do not migrate an existing Store, enable unrestricted production dispatch, fabricate an issuer identity or personal human signature, or run restricted process-kill, crash/recovery, mutation, E8, or policy selectors. Keep those restricted selectors `NOT_RUN`.

**Prioritization rule:** finish the highest-risk dependency chain in order: establish source/test correctness first; prepare and review the exact non-secret runtime bundle next; collect permitted runtime evidence and qualify real owner-to-Runner integration; then run the final exact-head gate. A later item cannot substitute for missing evidence in an earlier item.

## Prioritized S2 stories

The machine-delegation decision is now recorded, rather than pending: request
`a3e130f0-9aec-4304-b001-388a45c0be55`, reply `0b0b8a4d-0816-4146-ba21-71857b5de49d`,
`MODIFY`; exact response in `evidence/s2-machine-authority-adjudication-20261029.md`.
Within S2-3, Codex prepares the concrete issuer-provenance and independent measurement contracts,
pure validators and read-only collectors. GPT-PM adjudicates corrections to both reported MAJORs.
This does not activate a replacement E5 contract or authorize production signing keys/services.
Operator authorization of the exact production delegation policy remains distinct from Codex's
preparation. No new external coordinator or human owner is required.

| Priority / story | Requirement trace | Owner | State at recorded evidence | Dependency / next action |
|---|---|---|---|---|
| S2-1 — Fail-closed signed instruction, Store admission, and recovery | REQ-001, REQ-002, REQ-004 | Codex | **Delivered — bounded source/test acceptance.** Evidence record and synchronized task documents were pushed in `e332ec4` (change records 0586/0587). GPT-PM request `f92b750e-485d-4f97-8c28-3bb2b8bfc3db` accepted baseline-plus-delta coverage and resolved S2-REVIEW-02 for this bounded scope at submitted HEAD `57c734e60787a9db14bb888116d7e808bc46970e`. Recorded tests: M03 130/130 at `c855ca4`; source-fidelity 5/5 at `206a746`; adapter 38/38 at `6952469`; exact wrapper regression 38/38 at `0da595e`. These are inherited reports, not tests run in the delivery turn; GPT-PM did not execute them or reproduce the Git continuity comparison. | No S2-1 source/test work remains. Runtime, production identity, current E5 and restricted scenarios remain unproven or NOT_RUN for their separate S2 acceptance. | None for bounded S2-1 delivery; full S2 remains open separately. | Codex owns task delivery; GPT-PM supplied the correlated source/test decision. | Start only the next queued task, S2-2; do not skip ahead to S2-4. |
| S2-2 — Authenticated owner transport to the existing Store-backed dispatcher | REQ-002, REQ-003 | Codex | **Delivered — bounded source/test acceptance.** GPT-PM request `b0f60d46-42b7-486a-b2f0-5d2253780f55` is correlated to reply `d555b078-5647-46eb-bfc1-dd99654d634f` (job `68efb4e6-a296-4fd7-bcfc-2c6fe2568d5c`, `correlated=true`); it accepted the bounded source/test scope and resolved transport M01/M02. Exact source/test blobs are in pushed commit `e987a24`; delivery reconciliation is change record 0588. The 34-case WSL result is inherited evidence. | Production `S2-DISPATCH-M01`, genuine systemd/PID1 identity, kernel peer credentials, pidfd, socket filesystem metadata, provisioned identities/configuration, Store/Runner integration and E5 remain open/unproven. | None for bounded source/test delivery; runtime acceptance remains a separate S2-4 dependency. | Codex owns evidence and delivery; GPT-PM owns the recorded source/test decision. | After change record 0588 is pushed, proceed to the next incomplete task, S2-4; preserve runtime limits. |
| S2-3 — Immutable non-secret runtime bundle and bounded WSL qualification preparation | REQ-004, REQ-005, REQ-006 | Codex; GPT-PM adjudicates the reviewed bundle | **Accepted and delivered for bounded inactive stage-only preparation; commit `ae07f8708adcc7ef4f69505477ad6b72e3c912cf` is pushed to `origin/s2-canonical-continuation`.** The exact source bundle and refreshed inventory were approved; the designated-runner direct regression passed 4/4 (8 deselected, 0 skipped) at `043980f`, and the blobs remained unchanged at reviewed source HEAD `ef465cd`. Stage-only execution then published the immutable versioned runtime/helper in Ubuntu-24.04, reporting `selected=false`, `selector_unchanged=true`, `systemd_units_installed=0`, `runtime_stage_only=true`. GPT-PM request `ac2d25a2-8b62-4d79-8614-fc6a9f7d0bb4`, correlated reply `1c8d392e-1a57-533c-b874-97823f5e4628`, approved the exact post-stage manifest SHA `78d21af798f66a3e54a8d638f393773af5d20120075cd02599ac70675cb84be7` with 0 BLOCKER/MAJOR in that scope. Evidence: `evidence/s2-3-stage-only-ef465cd.md`, `evidence/s2-3-post-stage-manifest-review-ac2d25a2.md`, and change record `0584-s2-3-stage-only-runtime-bundle.md`. | Task evidence and documentation are committed and pushed; advance only according to the sequential backlog. TP-10 remains PARTIAL for its broader refusal/error matrix; this task does not prove those unexecuted cases. Stage-only does not authorize selector/unit changes, activation, Store, service identity/configuration, keys/E5, dispatch, production, deployment, or S2 closure. |
| S2-4 — Production provenance and permitted real owner-to-Runner journey | REQ-001, REQ-003, REQ-004, REQ-005 | Codex: delegated technical configuration and evidence; GPT-PM: final adjudication; operator: expressly reserved actions only | **IN PROGRESS — runtime acceptance.** Existing I01 root V1 issuer code is implemented and covered by code/test APPROVE at `c97836029a5d94ff84dee5cb15d1757efd5525c3` (request `8fc2e0ba-07c9-49fc-b6b0-fac897e4408b`). The additional V2 verifier source/test slice was approved at `aa349632` and delivered with ledger `e09c78b`; normal push succeeded. | Remaining: exact authorized production configuration/key provenance, current run-bound E5 and permitted real owner-to-Runner qualification. `S2-DISPATCH-M01` describes this runtime/provenance remainder; an absent issuer implementation is not the blocker. Codex reconciles/prepares the permitted non-secret runtime inputs under existing authorization. A new V2 signing integration is not automatically an S2 prerequisite. |
| S2-5 — Final S2 review, exact-head approval, and sprint acceptance | REQ-006 | GPT-PM owns approval; Codex owns coordination and evidence submission | **Open.** No final GPT-PM approval for the complete S2 code, mapped test results, permitted runtime evidence, and relevant specialist reviews is recorded. | After S2-1 through S2-4 evidence is reconciled, obtain fresh relevant specialist reviews and submit the precise final Git head with correlated evidence to GPT-PM. Any subsequent code change invalidates that approval. Then record accepted/rejected/carried stories in `docs/sdlc/acceptance.md`. Do not begin S3 before S2 closes. |

## Numbered acceptance criteria

These criteria make the existing requirements testable; they do not add product scope. Source/test evidence and installed-runtime acceptance are separate.

### S2-1 — Signed instruction and recovery source contract

1. **Given** an instruction with any invalid, unsigned, expired, purpose-mismatched, or request/task/slot/attempt/epoch/run/key binding, **When** the root Supervisor verifies it, **Then** it rejects before durable dispatch intent and leaves Store assignment/lease authority unchanged. (REQ-001, REQ-002)
2. **Given** an ambiguous admission or a previously accepted outcome replayed after generation change, **When** the existing recovery path handles it, **Then** it follows the accepted read-only historical-result rule or fails closed; it does not append a duplicate event, mutate a lease, grant new admission, or launch a duplicate Runner. (REQ-004)
3. **Given** the recorded source/test evidence at the accepted revisions, **When** this story is assessed, **Then** it is labeled source/test accepted only and is not represented as proof of systemd, kernel identity, or production runtime behavior. (REQ-006)

**Recorded result:** source/test acceptance is retained; delivery is not closed until the task commit is pushed. `S2-PROV-M03-R01` evidence is linked from `core/BACKLOG.md` and `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`. The fixture correction is in `dcb5d63`. The four-file WSL selection passed 130/130 at `56cd816` and exact HEAD `2befed5`; adapter functional/E2E passed 35/35 and 2/2 at that HEAD. The source-fidelity verifier passed 5/5 focused tests and maps all 41 redactions. Independent review found no confirmed source defect; source identity and static invariants are documented in `docs/sdlc/evidence/s2-review-redaction-independent-review-2befed5-20261029.md`. GPT-PM re-adjudication remains pending; no approval or push is claimed. |

### S2-2 — Owner transport source/test contract

1. **Given** a valid signed instruction for work already authorized by Store, **When** the accepted owner transport path forwards it, **Then** the existing authenticated Supervisor/Store path performs admission and the existing Store-backed dispatcher relays it; transport does not create or assign work. (REQ-002, REQ-003)
2. **Given** malformed, partial, duplicated, or ambiguous transport input/outcome, **When** the owner service handles it, **Then** it fails closed without unsigned fallback or a second request on the same one-frame connection. (REQ-003)
3. **Given** the recorded WSL transport run, **When** reporting its result, **Then** report 34 passed, 0 skipped, 0 failed for that source/test run and explicitly retain mocked peer credentials, pidfd, and filesystem metadata as unproven runtime properties. (REQ-006)

**Recorded result:** accepted at source/test scope under GPT-PM request `b0f60d46-42b7-486a-b2f0-5d2253780f55`; exact run record: `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md`. This result is not production-runtime acceptance.

### S2-3 — Reviewed runtime bundle and bounded preparation

1. **Given** the accepted source/test scope and current repository revision, **When** Codex prepares runtime inputs, **Then** the review bundle identifies the exact source/artifact revision and contains configuration values and hashes without exposing secret contents. (REQ-005, REQ-006)
2. **Given** the GPT-PM conditional WSL authorization, **When** preparation reaches provisioning, **Then** it proceeds only after GPT-PM has reviewed the exact immutable bundle and the stated source/test gate is satisfied. (REQ-005)
3. **Given** an empty Store or an existing Store, **When** initialization is planned, **Then** only the conditionally allowed fresh schema-v6 initialization may proceed under its reviewed gate; an existing Store migration remains stopped for its separate gate. (REQ-006)
4. **Given** any need for a production instruction issuer/trust key or independent operator-root-signed E5/network-policy attestation, **When** runtime preparation requests those inputs, **Then** Codex neither generates nor impersonates them; the missing genuine authority is recorded explicitly. (REQ-005)

**Current result:** accepted and delivered for the bounded inactive stage-only preparation and exact post-stage manifest identity. The evidence set and backlog were committed as `ae07f8708adcc7ef4f69505477ad6b72e3c912cf` and pushed to `origin/s2-canonical-continuation`. TP-10's broad refusal matrix remains partial. This approval does not authorize runtime selection/activation, service or Store mutation, keys/E5, dispatch, production, or S2 closure.

### S2-4 — Permitted runtime and production integration

1. **Given** a reviewed bundle and genuinely provisioned authorized identities/configuration, **When** the permitted runtime qualification is executed, **Then** evidence identifies the exact revision, effective service identity, root-controlled configuration boundary, current run-bound provenance, and real owner-to-Runner result. (REQ-004, REQ-005, REQ-006)
2. **Given** missing or unauthenticated production issuer/trust-key provenance, owner identity, root configuration, or current E5/runtime evidence, **When** S2 acceptance is evaluated, **Then** `S2-DISPATCH-M01` remains MAJOR/OPEN and production dispatch remains disabled. (REQ-005)
3. **Given** any selector explicitly restricted by the current adjudication, **When** runtime coverage is reported, **Then** process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`; no skip or synthetic test is counted as a pass. (REQ-006)
4. **Given** runtime observations that do not include a genuine independent signer, **When** provenance is recorded, **Then** Codex reports observations as observations and does not claim an operator-root-signed E5/network-policy attestation. (REQ-005, REQ-006)

**Current result:** IN PROGRESS for runtime acceptance. The existing I01 root V1 issuer implementation is present and covered by the bounded code/test approval at `c97836029a5d94ff84dee5cb15d1757efd5525c3`, request `8fc2e0ba-07c9-49fc-b6b0-fac897e4408b`, reply `c0ff978a-76a3-5c9e-a0d4-e98fef016357`. The separate V2 verifier slice was approved at `aa349632` and pushed through `e09c78b`. Production configuration/key provenance, current E5 and a qualified real owner-to-Runner journey remain unverified under REQ-005. Do not reopen accepted issuer source or make a V2 signing replacement mandatory without a concrete defect or changed accepted requirement. Codex owns the delegated technical configuration and actual measurements; GPT-PM owns final adjudication. The current execution scope in requirements.md supersedes generic historical permission-pending wording; no personal human signature is asserted.

### S2-5 — Exact-head gate and sprint decision

1. **Given** completed source, mapped test, permitted runtime, and relevant specialist-review evidence, **When** final approval is requested, **Then** GPT-PM's approval names/correlates to the exact final Git head and evidence set. (REQ-006)
2. **Given** any code change after that approval, **When** sprint closure is reconsidered, **Then** the approval is stale and a fresh exact-head gate is required. (REQ-006)
3. **Given** missing runtime acceptance, a remaining valid code BLOCKER/MAJOR, or missing exact-head approval, **When** S2 status is recorded, **Then** S2 stays NOT APPROVED and S3 stays unstarted. (REQ-005, REQ-006)

**Current result:** open. Next: after all prior criteria are evidenced, Codex submits the exact head and correlated evidence to GPT-PM and writes sprint acceptance from the verdict.

## Definition of Ready

- The story traces to one or more `REQ` identifiers in `docs/sdlc/requirements.md`.
- Acceptance criteria are numbered, falsifiable, and identify whether source/test or runtime evidence is required.
- The accepted architecture and relevant GPT-PM authorization are linked; dependencies and restrictions are explicit.
- The exact evidence source and responsible project owner (Codex, GPT-PM, or operator) are named.

S2-1's bounded source/test task is delivered in pushed commit `e332ec4` after GPT-PM accepted S2-REVIEW-02 under request `f92b750e-485d-4f97-8c28-3bb2b8bfc3db`. S2-2's bounded source/test task is delivered in pushed commit `e987a24` and reconciled by change record 0588; its runtime limitations remain open. S2-3's bounded inactive stage-only preparation and post-stage manifest identity are accepted and delivered. S2-4 is the next incomplete task; it cannot be accepted until its genuine provenance and runtime prerequisites exist. S2-5 is a closing gate, not a substitute for unfinished stories.

## Definition of Done

- All in-scope source changes are committed with a dedicated linked change record in the same commit; the accepted source/test revisions and evidence are identified.
- Required mapped tests are authored/executed by the designated test roles after coding is complete; exact commands, revision, environment, results, and limitations are recorded. Unavailable or restricted scenarios are `NOT_RUN`, never `PASS`.
- Relevant specialist reviews are completed on the exact final diff; valid BLOCKER/MAJOR findings are resolved and rechecked.
- Runtime acceptance, if required by the story, is backed by current run-bound evidence from the authorized environment; mocks and source tests are not promoted to production proof.
- GPT-PM gives fresh approval for the exact final head and correlated evidence before push/PR. A later code change requires a new approval.
- `docs/sdlc/acceptance.md` records each S2 story as accepted, rejected, or carried with evidence and reason. One PR is used for S2. S3 begins only after S2 acceptance and required gates are complete.

## Current sprint disposition

| Story | Decision | Evidence / limitation |
|---|---|---|
| S2-1 | Delivered — bounded source/test acceptance | M03 130/130 at `c855ca4`; source-fidelity 5/5 at `206a746`; adapter 38/38 at `6952469`; correlated-wrapper regression 38/38 at `0da595e`. GPT-PM request `f92b750e-485d-4f97-8c28-3bb2b8bfc3db` resolved S2-REVIEW-02 for this scope at submitted HEAD `57c734e60787a9db14bb888116d7e808bc46970e`; evidence: `evidence/s2-1-coverage-adjudication-f92b750e.md`. Delivery: `e332ec4` pushed. Tests/reviews are inherited records, not work rerun by GPT-PM. Runtime remains unproven. |
| S2-2 | Delivered — bounded source/test only | GPT-PM request `b0f60d46-42b7-486a-b2f0-5d2253780f55`, correlated reply `d555b078-5647-46eb-bfc1-dd99654d634f`; exact source/test blobs are in pushed `e987a24`. WSL run record `evidence/s2-dispatch-owner-transport-wsl-run-20261029.md` reports 34 passed; peer credentials, pidfd and filesystem metadata are mocked. See delivery reconciliation 0588. |
| S2-3 | Bounded stage-only acceptance and delivery complete | Commit `ae07f8708adcc7ef4f69505477ad6b72e3c912cf` is pushed. Exact bundle/inventory and post-stage manifest identities, PM decision `ac2d25a2-8b62-4d79-8614-fc6a9f7d0bb4`, and stage result are linked above. Selector/units were not changed; TP-10 remains partial. |
| S2-4 | IN PROGRESS — runtime evidence remains | Existing issuer SOURCE is implemented and bounded code/test approved at `c978360`; V2 verification slice approved at `aa349632` and pushed. `S2-DISPATCH-M01` remains for production configuration/key provenance, current E5 and real owner-to-Runner qualification. Codex owns permitted preparation/evidence; GPT-PM adjudicates; operator owns reserved authority/custody and genuine attestation. Restricted selectors stay `NOT_RUN`. |
| S2-5 | Carried — final gate pending | No final exact-head GPT-PM approval for full S2 is recorded. Codex coordinates the submission after S2-3/S2-4 and reviews complete. |

### Focused test maintenance note

Historical item, resolved in change0551: Codex reconciled the exploratory selector `test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor` in `tests/vst/test_s2_persistent_runner_service.py`. It assumes a Store with `PRAGMA user_version == 5`, while both baseline `9c1be0f` and current source declare schema version 6. The selector is outside TP-26/27 acceptance and was excluded from the final focused assignment-basis run; do not silently change its historical fixture or count its failure against the accepted S2 candidate tests. Resolution: the designated functional-test reviewer restored a true schema-v5 fixture and reported six passing cases over two selectors; see `evidence/s2-legacy-v5-fixture-run-20261029.md`. Include its permitted regression only after the final S2 code freeze.

## Required evidence references

- Requirements and current limitation register: `docs/sdlc/requirements.md`.
- Current S2 coordinator/runtime adjudication and correlated decisions: `core/STATE.md`, “Current S2 coordinator/runtime adjudication — 2026-10-29”; `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`.
- S2 source/test backlog and M03 source/test closure: `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”; `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
- Transport test details and limits: `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md`.

