# S2 backlog and acceptance plan

Sprint identity: Agentic_Framework sprint `39b7cc253f5d`, mapped to the already active project sprint **S2**. This is a tracking association, not a new sprint. S3 remains unstarted.

## Current source update — change0556

The fresh-only authenticated assignment bootstrap is implemented in change0552 (`45dcf47`);
the detached issuance/verifier contract is change0553 (`e44f48d`). GPT-PM request
`c7a8e23e-91f5-489c-a096-c813d84c3b12`, correlated reply
`7c3e4eb6-3300-5c5b-ba5c-85aaa10d0487`, returned **GO for bounded integrated SOURCE** and
accepted the corrected I01 design as implementation-ready. This supersedes the earlier source
HOLD for the issuer; it does not supersede runtime, key provisioning, real signing, E5, forbidden
selector or final S2 gates. Codex is implementing the specialized journal, root-Supervisor v1
issuer and transaction-bound admission/grant/runner guards. There is no missing external
coordinator or unassigned owner. Required I01-SRC-01 through I01-SRC-05 are recorded in
`evidence/s2-i01-integrated-source-adjudication-20261029.md` and design change0554.

The historical schema-v5 fixture item below is resolved by change0551 and its designated
six-case fixture evidence; it is not a current product blocker. Final S2 tests still wait until
all in-scope coding is complete. Historical story/epic rows retain their original evidence scope.

## Sprint goal

Deliver and qualify the existing Store-authorized signed dispatch path through the real Runner boundary, while preserving fail-closed behavior and keeping production dispatch disabled until the required runtime evidence and exact-head approval exist.

**Scope boundary:** use the accepted `DispatchOwnerService` → authenticated Supervisor/Store admission → Store-filtered Pub/Sub → `StoreBackedDispatcher` path. Store remains the sole task, assignment, lease, and durable dispatch authority. No new scheduler, coordinator product, assignment authority, or external coordinator is needed. Do not migrate an existing Store, enable production dispatch, invent a production issuer/trust key or independent operator-signed E5/network-policy attestation, or run restricted process-kill, crash/recovery, mutation, E8, or policy selectors. Keep those restricted selectors `NOT_RUN`.

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
| S2-1 — Fail-closed signed instruction, Store admission, and recovery | REQ-001, REQ-002, REQ-004 | Codex | **Source/test acceptance retained; task delivery OPEN before push.** The original `S2-PROV-M03-R01` closure is at `c855ca4`; regression correction is committed in `dcb5d63`. At HEAD `6952469`, the four-file WSL selection passed 130/130 at `2befed5`, source-fidelity verifier passed 5/5 at `206a746`, and prior adapter functional passed 38/38 on that exact commit. The verifier maps all 41 redactions across 15 files; independent security review found no confirmed source defect. GPT-PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` resolved S2-REVIEW-01 but retained S2-REVIEW-02 as `MAJOR/HOLD`; the persisted correlated reply has a `ChatGPT said:` wrapper before `REQUEST_ID`. Change 0577 now requires the matching ID after that wrapper; its focused suite passes 38/38 against the uncommitted worktree at `74fdbf6`. | Commit wrapper correction with evidence, rerun focused suite on exact committed head, refresh AF packet, obtain fresh GPT-PM exact-head adjudication, then normal push. Static/source tests do not establish installed runtime, production identity, E5, or restricted scenarios. Codex owns correction/evidence; GPT-PM owns formal review. Do not begin S2-2 before S2-1 is pushed. |
| S2-2 — Authenticated owner transport to the existing Store-backed dispatcher | REQ-002, REQ-003 | Codex | **Accepted — source/test scope.** GPT-PM transport decision `b0f60d46-42b7-486a-b2f0-5d2253780f55`; WSL transport evidence reports 34 passed, 0 skipped/failed. Kernel peer credentials, pidfd, filesystem metadata, installed systemd identity, and production runtime were not proven by that test. | Source scope is closed. Carry its limits into runtime qualification; do not count the mocked metadata as production acceptance. |
| S2-3 — Immutable non-secret runtime bundle and bounded WSL qualification preparation | REQ-004, REQ-005, REQ-006 | Codex; GPT-PM adjudicates the reviewed bundle | **Open / next.** Existing records authorize bounded Ubuntu 24.04 WSL preparation conditionally, after source/test review and exact bundle review. No current acceptance record in the reconciled sources establishes that the final bundle has been reviewed or runtime qualification completed. | Codex prepares the exact non-secret configuration/artifact bundle and collision rechecks, then obtains GPT-PM review before any conditional provisioning. Fresh schema-v6 Store initialization is conditionally allowed; migration of an existing Store is a separate gate. |
| S2-4 — Production provenance and permitted real owner-to-Runner journey | REQ-001, REQ-003, REQ-004, REQ-005 | Codex for preparation, authorized provisioning and evidence; GPT-PM for contract adjudication; operator for exact production delegation authorization and reserved key custody/human signature | **Not accepted.** `S2-DISPATCH-M01` remains MAJOR/OPEN. Current runtime provenance and real owner-to-Runner acceptance are not evidenced. | Codex corrects the proposed machine contracts and obtains GPT-PM review. After exact delegation-policy authorization and source/bundle gates, Codex performs only the specifically permitted provisioning/collection. Current human E5 stays required until an explicitly accepted machine version is selected. Never invent a signature, authority or successful measurement. |
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

**Current result:** not yet accepted in the reconciled sources. Next: Codex prepares the non-secret bundle and collision rechecks; GPT-PM reviews it before conditional WSL provisioning.

### S2-4 — Permitted runtime and production integration

1. **Given** a reviewed bundle and genuinely provisioned authorized identities/configuration, **When** the permitted runtime qualification is executed, **Then** evidence identifies the exact revision, effective service identity, root-controlled configuration boundary, current run-bound provenance, and real owner-to-Runner result. (REQ-004, REQ-005, REQ-006)
2. **Given** missing or unauthenticated production issuer/trust-key provenance, owner identity, root configuration, or current E5/runtime evidence, **When** S2 acceptance is evaluated, **Then** `S2-DISPATCH-M01` remains MAJOR/OPEN and production dispatch remains disabled. (REQ-005)
3. **Given** any selector explicitly restricted by the current adjudication, **When** runtime coverage is reported, **Then** process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`; no skip or synthetic test is counted as a pass. (REQ-006)
4. **Given** runtime observations that do not include a genuine independent signer, **When** provenance is recorded, **Then** Codex reports observations as observations and does not claim an operator-root-signed E5/network-policy attestation. (REQ-005, REQ-006)

**Current result:** open. Codex owns corrected machine-contract design, bounded source and authentic measurements; GPT-PM adjudicates both reported MAJORs. The operator authorizes the exact proposed production delegation policy and retains reserved custody/human-attestation actions. Current human E5 remains authoritative until an explicit accepted machine replacement is selected; no human artifact is impersonated.

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

S2-1 and S2-2 are ready and already accepted for their bounded source/test scope. S2-3 is the next executable item under its conditional bundle-review gate. S2-4 cannot be accepted until its genuine provenance and runtime prerequisites exist. S2-5 is a closing gate, not a substitute for unfinished stories.

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
| S2-1 | Source/test accepted; delivery open, exact-head approval and push pending | Four-file WSL suite 130/130; source-fidelity suite 5/5 at `206a746`; adapter functional 38/38 at exact committed HEAD `6952469`. GPT-PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` resolved S2-REVIEW-01 but retained S2-REVIEW-02 MAJOR/HOLD. The correlated-reply parser fix and end-to-end matched/mismatch cases are committed; fresh PM review and push remain. Runtime remains unproven. |
| S2-2 | Accepted — source/test only | GPT-PM transport decision `b0f60d46-42b7-486a-b2f0-5d2253780f55`; WSL run record `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md` (34 passed; peer credentials, pidfd, filesystem metadata mocked). |
| S2-3 | Carried / next | Exact bundle review and conditional WSL preparation/qualification are not evidenced as complete in the reconciled sources. Codex prepares; GPT-PM adjudicates the exact bundle. |
| S2-4 | Carried — genuine provenance/runtime evidence incomplete | `S2-DISPATCH-M01` is MAJOR/OPEN. Codex owns machine-contract correction, bounded preparation and measurements; GPT-PM owns contract review; operator owns exact production policy authorization and reserved custody/human-signature actions. Current human E5 is unchanged. Restricted selectors remain `NOT_RUN`. |
| S2-5 | Carried — final gate pending | No final exact-head GPT-PM approval for full S2 is recorded. Codex coordinates the submission after S2-3/S2-4 and reviews complete. |

### Focused test maintenance note

Historical item, resolved in change0551: Codex reconciled the exploratory selector `test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor` in `tests/vst/test_s2_persistent_runner_service.py`. It assumes a Store with `PRAGMA user_version == 5`, while both baseline `9c1be0f` and current source declare schema version 6. The selector is outside TP-26/27 acceptance and was excluded from the final focused assignment-basis run; do not silently change its historical fixture or count its failure against the accepted S2 candidate tests. Resolution: the designated functional-test reviewer restored a true schema-v5 fixture and reported six passing cases over two selectors; see `evidence/s2-legacy-v5-fixture-run-20261029.md`. Include its permitted regression only after the final S2 code freeze.

## Required evidence references

- Requirements and current limitation register: `docs/sdlc/requirements.md`.
- Current S2 coordinator/runtime adjudication and correlated decisions: `core/STATE.md`, “Current S2 coordinator/runtime adjudication — 2026-10-29”; `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`.
- S2 source/test backlog and M03 source/test closure: `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”; `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
- Transport test details and limits: `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md`.

