# S2 backlog and acceptance plan

Sprint identity: Agentic_Framework sprint `39b7cc253f5d`, mapped to the already active project sprint **S2**. This is a tracking association, not a new sprint. Remote review found an already-open/draft S3 PR #3; this turn did not create or alter it.

## Current execution checkpoint — 2026-11-07

Resume checkpoint (2026-11-07): current task remains S2-4E, Windows Owner-to-Runner process proof. The Windows provisioner cleanup condition was repaired after a real Windows PowerShell 5.1 parser failure; functional-test-reviewer subsequently reported `PARSE_OK`, and the narrow code review found no material regression. The elevated installer did not start: Start-Process returned `The operation was canceled by the user.` after the Windows UAC request. The setup log and runtime root were absent. This is cancellation of OS elevation, not cancellation of S2. Do not retry elevation automatically. Operator owns OS consent; Codex owns installation/result collection and e2e-runner coordination. Next: obtain an elevated Windows execution for the existing installer, inspect its result/log, then execute the registered one-shot E2E once. Runtime proof remains NOT_RUN until the actual receipt journey passes; no new commit or push is claimed.

This table is the sole active task queue. Dated evidence and older narrative sections retain their
historical scope; every older `Next:` line is archived chronology, not an executable instruction.
They must not silently reopen accepted code. The S2-5 bounded code disposition is recorded in
`docs/sdlc/acceptance.md`; it supersedes older S2 closure summaries for source/test acceptance
only. Live runtime/E5/production acceptance remains `NOT_RUN`, not passed. Operator decision
2026-11-06 removed the WSL inventory/configuration-apply/qualification QA harness and its Git
source checks from active scope; no older WSL next-action may be followed. Before a new
implementation or review, identify the
missing numbered acceptance criterion and check its existing approval and implementation. An
accepted item is reopened only with a concrete regression or changed accepted requirement.
Permission to prepare a candidate does not make that candidate mandatory for S2.

| Order | Task / state | Evidence / remainder | Owner / next action |
|---|---|---|---|
| 1 | S2-4 tracking reconciliation — DELIVERED in change0591 | Corrected stale writer/issuer HOLD and push-pending summaries against I01 SOURCE GO, code/test approval `c978360`, and successful task push through `e09c78b`. | No remaining action; retain as accepted evidence. Do not repeat reconciliation. |
| 2 | S2-4 exact runtime inputs — DELIVERED `473e559` | Source compatibility fix a600774 is pushed; actual strict stage-only publication succeeded. Bundle32 artifacts, nine unit bindings and three rate-limit overrides are pinned to actual source/helper/task/policy/run identities. False local GPT-PM credential labeling was corrected; review and test evidence is retained in change0595. | No remaining action for the accepted bounded preparation; retain its limits and do not repeat the bundle work. |
| 3 | S2-4D REQ-003 source/test acceptance — DELIVERED `96a8da7` | Removed five QA-only WSL inventory/apply/qualification scripts and four dedicated test modules; retained the Store-backed product path. Windows selector: 1 passed; bundle contract module: 11 passed. GPT-PM request `a2c98c0f-a741-4ad6-8330-8cbde5bc3571`, reply `f981ea40-d56c-58aa-8c5e-87631a900140`: APPROVE, 0 BLOCKER / 0 MAJOR. Commit pushed to `origin/s2-canonical-continuation`, updating S2 PR #2. | Codex: preserve the bounded test/runtime distinction in `docs/sdlc/acceptance.md`; runtime/E5/production remain `NOT_RUN`. |
| 4 | S2-4E Windows-local Owner→Runner functional path — IN_PROGRESS | Source commit `c4558a8` is pushed; GPT-PM request `e4f0bb3a-75a2-4f87-b58a-7a5e53d11588` accepted the exact source delta with 0 B/M. Assigned functional-test-reviewer: Store contract 5/5 and receipt contract 4/4 passed. Owner→Dispatcher module is `NOT_RUN`: pytest is prohibited; its fixture requires POSIX root; and the real Windows trust path requires provisioned VST service identities and protected key ACLs, so mocks would weaken the proof. Process E2E is `NOT_RUN`: the harness was not run; current read-only inventory is recorded in `docs/sdlc/evidence/s2-4e-windows-process-e2e-preflight-20261107.json` (admin=false, services/config/inputs absent). | Codex coordinates; next: provide an elevated local Windows setup with the real SCM services and protected test inputs, then e2e-runner runs the existing process harness. No WSL, VPS, current E5, or production claim. |
| 5 | S2-5 final bounded S2 code acceptance — ACCEPTED for its reviewed scope | Exact code/test candidate `96a8da7bf5af5c9d5b37e56287c48472cb239254` received correlated GPT-PM APPROVE after internal review and focused Windows tests. Full task/requirement disposition is in `docs/sdlc/acceptance.md`. | This records the earlier bounded source/test disposition; it does not close the subsequently scoped S2-4E Windows-local task. S2 remains open until S2-4E acceptance; REQ-005 live E5/production remains `NOT_RUN` and excluded. |

Operator scope decision (2026-11-06) supersedes older S2-4 WSL execution next-actions below:
the WSL inventory/configuration-apply/qualification QA harness and its Git source checks were
removed from active project scope. Older WSL commands/results remain chronology only and must not
be executed or treated as current S2 acceptance. S2-4 closes at source/test scope; live runtime,
E5 and production status remain `NOT_RUN` and are not claimed.

Future product task `SAAS-01` is queued in `core/BACKLOG.md` for a later sprint after the planned
S2–S5 sequence. Windows-local remains the current priority; the SaaS item is not active work.

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
4. **Given** delegated production instruction issuer/trust-key and root policy authority, **When** runtime preparation records these inputs, **Then** Codex creates the authorized machine artifacts from verified source and measured evidence without claiming a personal human signature. The root policy signature is separate from the unsigned root-captured probe inventory. (REQ-005)

**Current result:** accepted and delivered for the bounded inactive stage-only preparation and exact post-stage manifest identity. The evidence set and backlog were committed as `ae07f8708adcc7ef4f69505477ad6b72e3c912cf` and pushed to `origin/s2-canonical-continuation`. TP-10's broad refusal matrix remains partial. This approval does not authorize runtime selection/activation, service or Store mutation, keys/E5, dispatch, production, or S2 closure.

### S2-4 — Permitted runtime and production integration

1. **Given** a reviewed bundle and genuinely provisioned authorized identities/configuration, **When** the permitted runtime qualification is executed, **Then** evidence identifies the exact revision, effective service identity, root-controlled configuration boundary, current run-bound provenance, and real owner-to-Runner result. (REQ-004, REQ-005, REQ-006)
2. **Given** missing or unauthenticated production issuer/trust-key provenance, owner identity, root configuration, or current E5/runtime evidence, **When** S2 acceptance is evaluated, **Then** `S2-DISPATCH-M01` remains MAJOR/OPEN and production dispatch remains disabled. (REQ-005)
3. **Given** any selector explicitly restricted by the current adjudication, **When** runtime coverage is reported, **Then** process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`; no skip or synthetic test is counted as a pass. (REQ-006)
4. **Given** runtime observations for the configured run/spec/nonce, **When** E5 provenance is recorded, **Then** Codex captures the exact probe JSON under root ownership, signs the network-policy attestation only after independently verifying its measured facts, and makes no personal human-signature claim. A probe signature is not required. (REQ-005, REQ-006)

**Current result:** IN PROGRESS for runtime acceptance. The existing I01 root V1 issuer implementation is present and covered by the bounded code/test approval at `c97836029a5d94ff84dee5cb15d1757efd5525c3`, request `8fc2e0ba-07c9-49fc-b6b0-fac897e4408b`, reply `c0ff978a-76a3-5c9e-a0d4-e98fef016357`. The separate V2 verifier slice was approved at `aa349632` and pushed through `e09c78b`. Ordered source/test child tasks S2-4.2 (invocation-bound root capture/freshness) and S2-4.3 (safe StageOnly beside an existing root-owned config directory) are implemented and focused-test reviewed; evidence is in `docs/changes/0598-s2-4-root-capture.md` and `docs/changes/0599-s2-stage-only-with-existing-config.md`. Production configuration/key provenance, live journal capture, current E5 and a qualified real owner-to-Runner journey remain unverified under REQ-005. Do not reopen accepted issuer source or make a V2 signing replacement mandatory without a concrete defect or changed accepted requirement. Codex owns the delegated technical configuration and actual measurements; GPT-PM owns final adjudication. The current execution scope in requirements.md supersedes generic historical permission-pending wording; no personal human signature is asserted.

**Delivered ordered subtask S2-4.1 — remove the Runner probe-signature cycle:** source/test and synchronized contract records are pushed in `8acd56ccb37e888a64b4f5898864bb07599683d0`; push output was `473e559..8acd56c` to `origin/s2-canonical-continuation`. The designated functional-test reviewer reports 65 passed, 8 skipped for the unsigned exact-schema/run-binding contract, synthetic Supervisor/Store path, removed `probe_key_path`, and runtime-config bundle. The security reviewer found no source regression from removing that signature, conditional on a trusted root capture. That condition is source-implemented and focused-test reviewed by ordered child S2-4.2 below, but not runtime-proven. Evidence and scope are in change record `0597-s2-4-remove-runner-probe-signature.md`.

**Delivered ordered subtask S2-4.2 — root capture source and freshness:** Codex added `tools/vst/preflight_capture.py` to accept exactly one systemd invocation, validate its worker journal record and root systemd success record against root-controlled run/spec/nonce inputs and attestation, and atomically publish a root-owned mode-0600 record without overwrite. Probe validation now rejects timestamps older than 120 seconds or from the future. Focused evidence: the designated functional-test reviewer reports 87 passed, 9 skipped for `python -m pytest -q tests/vst/test_s2_preflight_capture.py tests/vst/test_s2_sandbox_probe.py`; a further 7 passed for `python -m pytest -q tests/vst/test_s2_e8_synthetic_lifecycle.py tests/vst/test_s2_store_lifecycle.py::test_supervisor_consumes_a_synthetic_probe_once_for_one_run`. The Windows run skipped POSIX publication; the designated e2e-runner separately ran the exact committed S2-4.2 publication test on the WSL target at HEAD `29f2671` with Python 3.12.3 and pytest 7.4.4: 1 passed; eight other existing skip cases are not passes. Python and security reviewers found no concrete source issue. A real captured systemd probe invocation, bundle repinning/install, current E5 and owner-to-Runner runtime acceptance remain open; S2-4 stays IN PROGRESS and S2-5/S3 remain queued. Detailed record: `docs/changes/0598-s2-4-root-capture.md`.

**Delivered ordered subtask S2-4.3 — StageOnly with existing root config:** target inventory showed `/etc/vst-runner` already exists as root-owned mode `0755`, while the relevant units are inactive and runtime socket directories absent. The installer now allows that directory only when it is a real root-owned directory without group/world write bits; existing config is left untouched. The focused functional-test reviewer reports 8 passed, 1 warning in `tests/vst/test_s2_runtime_stage_policy.py`; the security reviewer found no concrete source defect. Detailed record: `docs/changes/0599-s2-stage-only-with-existing-config.md`.

**S2-4.4 — exact StageOnly inputs:** source plan and Ubuntu-24.04 target inventory for source `7c7d599af03860ede7d4960301ed8d0456c360c0` are captured in `docs/changes/0600-s2-runtime-source-inputs.md`, including exact SHA-256 identities. GPT-PM confirmed the plan/source hash and StageOnly boundary but held the first execution because its inventory aged past five minutes. Codex refreshed the read-only inventory at `2026-10-30T02:01:02.747390+00:00`, SHA-256 `37a9577b0e710c911dd3f6f84da43be9d756b22106460581bf5a53e121436848`; this exact digest must be reviewed before StageOnly. StageOnly has not run. Existing configuration, selector and services must remain unchanged.

**S2-4.4 result:** GPT-PM follow-up request `7ede96a5-6419-4510-afd8-64e480c2e54d` approved the refreshed inventory and resolved `M-S2-4-STAGE-01`. The exact StageOnly command then exited 1 because Python imports added unplanned `__pycache__` members. Read-only post-failure verification showed no target change: selector remains on `a600774`; requested runtime/helper are absent; nine S2 units are inactive; jobs, Store and runtime record are absent. Detailed evidence: `docs/changes/0600-s2-runtime-source-inputs.md`.

**S2-4.5 — preserve exact StageOnly source members:** Codex added `-B` to both StageOnly module-import paths; the functional-test reviewer added and ran the focused two-case regression (2 passed, one existing deprecation warning) in `tests/vst/test_s2_stage_only_install.py`. Commit `f685cc9778e516b277e243a14dfa123db34ec247` was normally pushed to `origin/s2-canonical-continuation`. Detailed record: `docs/changes/0601-s2-stage-only-import-fix.md`.

**Delivered S2-4.6 — bounded StageOnly publication:** GPT-PM request `7d4bd70e-ebbc-4b98-ac3b-fe6b84825fca` approved source plan SHA-256 `90b88d12f571b0e9bc3744e4f9aff723ee2c0740f5895108726b8e52da2b1a5d` and fresh target inventory SHA-256 `8ede4656da3c18eda730873524534892c58ac0c9056885a3cbd59045a66ff733`. The normal installer ran at about `2026-10-30T02:13Z`, exit 0: it published the immutable `f685cc9` runtime and helper with `selected=false`, `systemd_units_installed=0`. Read-only post-stage verification at `2026-10-30T02:17:23.380934+00:00` matched the complete runtime tree and marker to the pinned plan; helper SHA-256 `3e7fe2ed0006b9e86ceb08f41071ac6a69b547bb2fe603255a3763643ce2cf91`, owner/mode `root:vst-runner 0:988 4750`. Selector still points to `a600774`; nine units are inactive; no jobs/cgroups, Store, run record, or runtime sockets; config directory and unit/drop-in metadata are unchanged. Detailed record: `docs/changes/0602-s2-stage-only-refreshed-inputs.md`. This closes only inactive source publication. Next ordered task remains S2-4 permitted current-run qualification and owner-to-Runner evidence; S2-4 and S2-5 remain open.

**Delivered S2-4.7 — permit runtime selection beside existing safe configuration.** The selector validates only the
existing root-owned `/etc/vst-runner` directory metadata and leaves its files and Store untouched. It continues to
require absent `/run` service paths, inactive units, no pending jobs, and empty cgroups. Focused results: Windows
12 passed/2 POSIX-only skipped; WSL Python 3.12 ran the two POSIX selector cases 2/2; the code reviewer found no
actionable BLOCKER/MAJOR. Commit `80c2b81deac364ed6466600fd46af47aafe805e2` was normally pushed to
`origin/s2-canonical-continuation`. Evidence: `docs/changes/0603-s2-existing-config-runtime-selection.md`. The
selector has not been applied. A separate runtime configuration candidate still pins `a600774` and remains
uncommitted; it is not an activation input.

**S2-4.8 — exact source and target inputs for the selector fix.** Source plan for committed source
`80c2b81deac364ed6466600fd46af47aafe805e2` is `docs/sdlc/evidence/s2-runtime-source-plan-80c2b81deac364ed6466600fd46af47aafe805e2.json`
(SHA-256 `01818efcd23bc20a3a4b408921d7342f5e5f95adc16ad86fe7b2a3b7176e2344`). A fresh read-only Ubuntu-24.04
inventory refreshed at `2026-10-30T02:49:02Z` is
`docs/sdlc/evidence/s2-runtime-target-inventory-80c2b81deac364ed6466600fd46af47aafe805e2.json` (SHA-256
`5f011ff65577a9363d2c1b60747e586d12042995dc88e8dff8779bdb81b28a66`), refreshed at
`2026-10-30T02:49:02Z` after the prior inventory expired at installer validation (318.9 seconds old; limit 300).
It confirms the selector still points to `a600774`, all nine S2 units are inactive, no jobs are pending, Store
and current preflight are absent, and the root-owned compiler identity is present. The failed attempt made no
target change. No private bytes were read or hashed. Detailed record:
`docs/changes/0604-s2-runtime-inputs-80c2b81.md`.

**Delivered S2-4.9 — bounded StageOnly publication for `80c2b81`.** After pushing the refreshed inventory,
the normal installer exited 0 at `2026-10-30T02:50Z`. It verified the exact source map, published
`/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2`, and reported helper SHA-256
`0ee613b289ab4fcf79d82f1cae777b96fcd97c8a02c59dded50736797a4381f5`, owner/mode `root:vst-runner 0:988 4750`,
`selected=false`, `systemd_units_installed=0`. Record: `docs/changes/0605-s2-stage-only-80c2b81.md`.
This is immutable publication only; the selector is still on `a600774` and no services were activated. Next:
the non-secret candidate rebinding was delivered as S2-4.10 below. Current E5 and the one permitted
owner-to-Runner journey remain open.
Restricted process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`.

**Delivered S2-4.10 — rebind and test the non-secret runtime configuration candidate.** The candidate
now binds task/runtime/helper source to `80c2b81deac364ed6466600fd46af47aafe805e2`, uses a fresh
run/nonce/request identity, pins the verified incremental Git bundle, and contains a read-only
transition manifest generated by the staged runtime's `bootstrap_runtime prepare`. The focused
functional-test reviewer reports `python -m pytest -q tests/vst/test_s2_runtime_config_bundle.py`:
9 passed on HEAD `c59f1c5` / Python 3.14.3; one existing pytest-asyncio deprecation warning. No
runtime selection, configuration installation, or service start occurred. Exact record:
`docs/changes/0606-s2-runtime-config-80c2b81.md`.

**Delivered ordered preparation S2-4.11a — build and test the pinned non-secret config applier.**
`tools/qa/apply_s2_runtime_configuration.py` reads all bundle sources from an exact committed Git
revision, pins the bundle/layout digests, and lets WSL independently verify the exact 26
destination map, metadata, content hashes, fresh target inventory and selected runtime. It refuses
unknown target bytes, excludes private key material, applies only while the nine relevant units
are inactive, atomically replaces approved regular files, reloads systemd and confirms
loaded-inactive unit state. The focused functional-test reviewer reports 9 passed with one existing
pytest-asyncio deprecation warning; these are local payload-contract tests, not WSL installation or
runtime proof. Security review found no remaining concrete issue. Evidence and scope:
`docs/changes/0607-s2-runtime-config-applier.md`.

**Delivered ordered preparation S2-4.11b — select the exact staged runtime without activation.**
The existing root-only `bootstrap_runtime apply` transition accepted the exact candidate manifest
digest `dc516f6b7053ec48bf96aaa3ddb3042d87d57f8f7199284e27e98f8203cc7935` and returned
`bootstrap_selection=complete`, `services_started_or_reloaded=false`,
`store_opened_or_changed=false`. A post-selection e2e-runner inventory then confirmed selector
`80c2b81`, all nine relevant units `loaded/inactive`, no jobs, and an absent Store target. It found
19/26 config destinations matching and seven known differences. The config applier was corrected
to consume the actual `runtime_selector.link_target` inventory field; its focused regression suite
reports 10 passed with one existing pytest-asyncio warning. Exact evidence is in
`docs/changes/0608-s2-runtime-selection-and-inventory-contract.md`.

**Delivered ordered subtask S2-4.11c — apply and verify the exact 26-file configuration.** The
committed pinned applier ran against post-selection inventory SHA-256
`d68d5679936927172b2b143fb3c80c28278f7034940bbbf93ffdd72aeda8fba3` at source commit
`aa32afd6298233666897b8753efafa84909715ef`. It updated seven exact known config files; the other
19 destinations were already exact. All 26 post-install hashes match, systemd `daemon-reload`
succeeded, all nine units remained loaded/inactive, there were no jobs, and Store stayed absent.
Private bytes were excluded. Evidence and exact command are in
`docs/changes/0609-s2-runtime-config-install.md` and
`docs/sdlc/evidence/s2-runtime-config-post-install-20261030T033734Z.json`.

**Delivered ordered subtask S2-4.12a — root-measured probe capture implementation.** The helper
and focused synthetic coverage are complete: 53 passed; security and reliability reviewers found
no remaining MAJOR. GPT-PM request `69174c68-5974-4b48-bcfe-f356a763746d` approved bounded code
HEAD `19338baebc865bbc9fabec45115340a629c61807` (reply
`e273369c-e309-5a80-a3b7-eabe92d6e9bc`); normal push to `origin/s2-canonical-continuation`
succeeded. Local diff verification confirmed the reviewed four-file scope. This does not claim
live WSL/Runner evidence.

**Current ordered subtask S2-4.12b — bounded worker identity settling and one current-run qualification.**
The prior one-use authorization for run `s2-runtime-20261030-334296bd0779488d837a27e283b50b6a`,
request `212a23e66ee94a7d87355b11e07e34fe`, nonce `b57520d076e1acd355d310ed18364907` was consumed.
Its exact runtime error was UID/GID arrays `[0,0,0,0]` instead of configured `[999,999,999,999]`
and `[989,989,989,989]`; no root preflight record, Store, bootstrap, Supervisor, Runner, network
attestation, or TestRun was produced. The correlated evidence is
`docs/sdlc/evidence/s2-runtime-owner-runner-qualification-20261030-334296bd.json` (SHA-256
`94229746889b17186e0a421babeef87afd69e7c99136d57204c0590508292732`). A later journal/unit
observation showed the configured worker identity 999:989. A systemd credential-transition race is
plausible, not proven; do not report it as the established cause. The consumed identity is now
permanently retired and cannot be retried.

The current source candidate waits at most five seconds for only the exact same-process root-to-worker
credential transition while pinning PID start time, cgroup, invocation, systemd generation and boot
identity; all other mismatches and timeout remain fail-closed. Review found that nested subprocesses
could exceed the advertised wall-clock bound; the current code now passes one remaining monotonic
deadline to every nested systemd command and checks expiry even when the first sample is already the
worker identity. The functional-test-reviewer reran the focused suite on the final code: 93 passed,
one existing pytest-asyncio deprecation warning. Coverage includes declining command timeouts,
deadline exhaustion, worker-first late validation, and refusal of the consumed tuple before marker
creation. Security and final code reviews passed. GPT-PM exact-head review request
`7e63f76e-4454-4b9d-80ad-c8ce77f607f6` returned HOLD because its declared helper digest was stale:
request `d324c810…` versus actual committed/worktree helper bytes `0f3b7b6f…` (55,295 bytes).
Direct Git-blob/worktree comparison matches the latter; the mismatch is in the request metadata,
not evidence of a source defect. GPT-PM's exact-source follow-up request
`d5ba635a-dac4-45ab-9fed-6fae692d104a` approved implementation HEAD
`1b5dd9d7a639b629465ac6fcf29e300ba80c18ca`; that task was normally pushed to
`origin/s2-canonical-continuation` (output `002e361..1b5dd9d`). This approval covers the worker
identity-settling implementation only, not the new inventory validator. Detailed change record:
`docs/changes/0615-s2-4.12b-worker-identity-settle.md`.

**Current subtask update — fail-closed inventory validation.** The designated functional-test-reviewer
reports 29 passed, one existing pytest-asyncio deprecation warning for
`tests/vst/test_s2_runtime_config_inventory.py`; code and security reviewers found no remaining
concrete issue in the validator/applier path. It requires the exact 26-file consumed-run baseline,
complete fresh WSL/PID1/account/unit/source evidence, a read-only D: 9p mount, canonical octal mode
strings, matching top-level/readiness boot IDs, and the exact runtime symlink shape before apply.
The privileged applier checks and executes the verifier source from the exact committed Git blob and
validates the same inventory bytes before payload construction. GPT-PM request
`c21b6374-653d-46c5-9732-fcc810a81be5` held earlier HEAD `4f9887fc03d773c7159c87b105093a3a751cc3b0`
for the boot-ID and mode integration gaps; both have been corrected and need a new exact-head GPT-PM review. The
authorized replacement inventory request `9357ee74-c0ac-4ed4-9568-1b4a192bf874`
and correlated reply `6d0a5e51-1809-5420-8c45-9ebc6beb9ec4` are recorded in
`docs/sdlc/evidence/s2-runtime-owner-runner-qualification-9357ee74.json`. That read-only result
exited 0 but was incomplete: PID1 namespaces/start identity, `vst-runner` identity, systemd version,
baseline fingerprint comparison, and verbatim inventory persistence were missing. No apply,
preflight, claim/probe, or TestRun occurred. Both inventory authorizations are consumed. The new
corrected source still needs exact-head GPT-PM approval and push. Detailed record:
`docs/changes/0616-s2-runtime-inventory-validator.md`.

The candidate tuple remains unapplied and unclaimed. Before another target command, Codex must
finish exact-head GPT-PM source review, commit and normally push this validator task, then obtain a
new correlated runtime authorization for the pushed head and exact source pins. `e2e-runner` then
owns the one authorized complete inventory/apply/preflight/test sequence. S2-4 remains IN PROGRESS;
S2-5 is queued and S3 unstarted.

**Latest runtime result and source-pin correction.** GPT-PM request
`733857ce-024e-42ab-b65a-25e12162dc38`, reply `6402ed93-9fb2-5569-8710-50b32034b531`, authorized one
inventory and conditional downstream sequence on HEAD `f9f488f`. The one raw inventory is
`docs/sdlc/evidence/s2-runtime-target-inventory-f9f488f.json`, SHA-256
`d4dc31bcd0eb97478677a844b80c2f7ccfbb9d176a8197b52c4a7ea7cdb340a9`. The committed verifier ran
once and refused because its applier SHA pin was stale (`ac512…` vs authorized `7d208…`). No apply,
root preflight, durable claim/probe, or TestRun occurred. The collector also used
`/proc/1/ns/mount` rather than `/proc/1/ns/mnt`, leaving mount namespace and PID1 UID/GID evidence
incomplete; this is a collector-command defect. The expected old installed bootstrap identity was
observed, and candidate collision was false. Codex now derives both verifier and applier digests
from exact HEAD Git blobs and requires byte-identical worktree files; the focused suite reports 31
passed. Local code and security reviews found no concrete defect. This correction still needs a
task commit, exact-head GPT-PM source review, normal push, and a new bounded runtime authorization.
Next collector must use `/proc/1/ns/mnt` and `/proc/1/status`, persist full JSON, and run the verifier
once; do not repeat any used inventory/verifier invocation. Detailed record:
`docs/changes/0617-s2-runtime-inventory-source-pins.md`.

The candidate tuple remains unapplied and unclaimed: run
`s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910`, request
`e520e04f58ad5e6a431a3a20b0efb87c`, nonce `0aac24fec9a2a5c53c5e9da21cbb4a42`, bundle SHA-256
`388e6bb00f97b54bbd456994ccdd399317ab2e527c6f37d8a1b71ce20a280e45`. Runtime request
`c84a91af-1ce6-4a55-9ce7-eed30c64ba66` authorized one inventory, and replacement request
`9357ee74-c0ac-4ed4-9568-1b4a192bf874` authorized one corrected read-only inventory. Both inventory
invocations are used; the first failed before collection, and the second was incomplete. Neither
authorized path reached apply, root capture, claim/probe, or TestRun. Their exact-head scope is the
old HEAD `1b5dd9d7a639b629465ac6fcf29e300ba80c18ca`; the validator changes the code HEAD, so a new
correlated runtime authorization is required after this task is pushed. The prior installation
remains bound to the consumed run. S2-4 remains IN PROGRESS, S2-5 is queued, and S3 is unstarted.

**Latest S2-4.12b runtime attempts.** Request `53f946da-755c-4859-adca-6bfd64fb2293` / reply
`09ac688e-5ded-5b7b-aa9c-5e6a69e13ff7` authorized one inventory and validator at HEAD `2e6a796`;
the collector omitted `readiness.units`, so validation refused. No runtime mutation occurred. Its
inventory SHA was `7a7e97b1e9a7dedbfd57592c3df66fea7ff6847c0a6ff3e77d6e49abd5b168d0`; both records
are preserved under the `2e6a796` evidence suffix. Replacement request
`a2bd39ce-8ae4-4416-9b82-56382a610c92`, reply
`80091d4f-cbf2-5c72-af15-7ef9a48020bf`, authorized one inventory plus one validator and conditional
apply/preflight/TestRun at exact HEAD `2e6a796eaa04664812cf1266322b083f18770fa1`. Inventory SHA
`acb6b116aa66f4ba764a9e7c9ad505b90574323ed16129a71a61a970956e151c` recorded values matching
the requested target predicates but omitted the duplicate `readiness.runtime_selector`; the one verifier refused with
`selected runtime path differs from the pinned S2 runtime`. No apply, preflight, claim/probe, or
TestRun occurred; this was a collector serialization defect, not a confirmed target failure. Codex
added a collector candidate at `tools/qa/collect_s2_runtime_config_inventory.py`; its current
integration-corrected SHA-256 is `453fe70732c7309158cab7a0876b6bb7347b895056969ef87dbf988dd8cfa838`.
GPT-PM request `cf7a9515-0cd8-47d2-a0cb-1c351a3ef1e0` returned HOLD / MAJOR-01: six validator-
required fields were only top-level and absent from `readiness`, so the next verifier would fail.
The current uncommitted assembler correction duplicates the same captured values into both places.
The functional-test-reviewer added an integration regression through the production assembler and
real validator. `python -m pytest -q tests/vst/test_s2_runtime_inventory_collector.py` returned 52
passed, one existing pytest-asyncio deprecation warning, exit 0, Python 3.14.3, at HEAD
`1a7dca5527dbe48324426f9b5f56621e85a6279b`. The tests prove the valid assembly passes and missing
or contradictory values are refused for all eight duplicated readiness fields. Code review
re-reviewed the integration contract and found no actionable B/M issue. Security re-review found no
actionable B/M finding. The tester reran the command on committed HEAD
`b927a438a72d14a31229c9d0ad7514a19606c98e`: 52 passed, one existing deprecation warning, exit 0;
a subsequent task-record-only amendment changed no source or test bytes. Do not call this ready for
PM review yet. Current S2-4.12b next step: obtain
remediation review bound to exact HEAD and exact collector bytes, normally push, then request a fresh
one-shot runtime authorization bound to that pushed HEAD and pins. Execute no further runtime
command under the consumed requests.
S2-4 remains IN PROGRESS; S2-5 remains queued; S3 is unstarted.

The active AF push gate's `start_head` had pointed to `20fda2c` on the other
`s4-canonical-continuation` branch, not an ancestor of the S2 branch. Codex corrected this single
pointer to the previous delivered S2 HEAD `2e6a796`, preserving sprint ID and phase history. This
keeps the required exact-head review scoped to the current S2 continuation.

**Current checkpoint — bounded recovery authorization `f0d3a07d` (2026-10-30).** GPT-PM
request `f0d3a07d-4b1d-4eb7-a04e-25bbdf0be93d` returned `MODIFY — CONDITIONAL RECOVERY
AUTHORIZATION`, bound to HEAD `7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`. Its one fresh
collector/validator chain ran once through one continuous Ubuntu-24.04 WSL process. Collector exit
0 captured `docs/sdlc/evidence/s2-runtime-qual-f0d3a07d-s2-runtime-20261030-2b5e04a3-collector.stdout.bin`
(35,342 bytes, SHA-256
`6d9e4f818c91ee986c131dfef7b08aee36f36267e029302707f470be0cb23f53`); the committed validator
ran once and returned PASS for all 26 configuration destinations and the exact pinned original
baseline. Validator stdout is
`docs/sdlc/evidence/s2-runtime-qual-f0d3a07d-s2-runtime-20261030-2b5e04a3-validator.stdout.bin`
(449 bytes, SHA-256
`1bb165b1935462a671230d7a6566c957ef599277c0d7587daf44e1327a8818f7`). The scoped recovery
observation is in `docs/sdlc/evidence/s2-runtime-recovery-status-f0d3a07d-20261030.md`.

The collector recorded boot ID `270cd88b-183f-426c-8add-872d9e98bcec`. A targeted read-only
query at `2026-10-30T11:19:50Z` recorded boot ID
`b0d0e05e-8705-44ab-9f32-277742e4a343`, so boot identity changed after inventory capture; the
PM condition to keep boot identity unchanged failed. That later query also showed the nine named
VST units loaded/inactive/dead with `MainPID=0` for service units and an empty systemd jobs list.
Its shell exited 2 before the intended path observations; Store/preflight/socket state was not
re-observed by that query. No host-wide process enumeration was performed. Because the PM
authorization terminates on any failed or incomplete predicate, no apply, preflight, claim/probe,
or TestRun was authorized or performed. Collector and validator slots are consumed; do not repeat
them under request `f0d3a07d`. Current task remains S2-4 IN PROGRESS, S2-5 queued, and S3
unstarted. Next: GPT-PM must clarify whether the observed inactive unit state satisfies the approved
pre-apply readiness contract and, if so, issue a new exact-HEAD one-shot authorization for a fresh
same-session inventory/validator/status sequence. Codex owns coordination; e2e-runner executes an
authorized runtime chain. Production dispatch stays disabled.

**Current result — fresh qualification and conditional apply, authorization `7f3f3b3c` (2026-10-30).**
GPT-PM approved exactly one fresh zero-retry chain at the same HEAD and pins, with the authorization
ending after apply capture. The chain ran once through one continuous Ubuntu-24.04 WSL process.
Collector exit 0 captured at `2026-10-30T11:28:34.332497+02:00`; byte-exact host persistence was
acknowledged before validation. Collector stdout is 35,345 bytes, SHA-256
`29543f0a065ff844a6413c4536f7b1b737c9223060f7c276f3b73efe67d9c5f5`. The committed validator
ran once, exit 0, and returned `PASS: complete S2 runtime inventory` for all 26 original-baseline
destinations; validator stdout is 449 bytes, SHA-256
`7619b1d5d377f85403d5e6c7bf20e3c83bb924bcf6cbadab667d6829ecc158e8`. Same-session status showed
the boot ID unchanged, runtime selector unchanged, inventory age 3.45437 seconds, all nine required
units satisfying the approved loaded/inactive/dead/MainPID-zero state, no systemd jobs, no Store,
preflight, attestation or runtime sockets, no candidate collision, and all apply predicates true.

The one conditional apply ran at `2026-10-30T11:28:37.816Z`, exit 0; daemon reload succeeded,
four files were installed and 22 were already exact. Apply stdout is 4,354 bytes, SHA-256
`73a4aa80794f8337f1afadfaf50d77b0ce76b3381e9327b86a72b3c376a4eadb`. The status and protocol
hashes plus complete exact commands are preserved in
`docs/sdlc/evidence/s2-runtime-qual-7f3f3b3c-s2-runtime-20261030-2b5e04a3.attempt.json` and its
linked raw artifacts. No preflight, Owner→Runner claim/probe, TestRun, restricted selector,
production activation, or retry was run; GPT-PM explicitly limited this authorization to apply.
This closes the configuration apply substep only. S2-4 runtime/E5/Owner→Runner acceptance remains
IN PROGRESS; S2-5 remains queued and S3 unstarted. Next: Codex requests a separate post-apply
authorization from GPT-PM; the `e2e-runner` role executes only what that decision permits.

**Post-apply qualification attempt `d71586a1` — stopped before runtime observation (2026-10-30).**
GPT-PM request `d71586a1-9894-4b01-aafa-6dd5d0af7e48` authorized one S2-4.12c chain, retry cap
zero. Its first WSL wrapper invocation started at `2026-10-30T11:41:20.496569Z`, but could not
`chdir` to `/mnt/d/Repo/Virtual_scrum_team` (`FileNotFoundError(2, No such file or directory)`).
The wrapper returned `HOLD`; collector and root preflight were not invoked. Claim/probe and exact
selector TestRun remain `NOT_RUN`. No alternate mount, retry, or runtime operation occurred.
Evidence: `docs/sdlc/evidence/s2-runtime-qual-d71586a1-s2-runtime-20261030-2b5e04a3.attempt.json`
(SHA-256 `58c6306d418405848745c22a6f1d484ffc68634f1809210b7c3ecfbd44c62c38`) and matching WSL
stdout (529 bytes, SHA-256
`f9b4a7663a30d0d8297146bf8069ad13fafc56b6a122f652d05c0a3255320a81`). The one-shot authorization
is exhausted at this first access failure. S2-4 remains IN PROGRESS and S2-5 stays queued. Next:
Codex requests a new one-shot authorization that explicitly includes at most one temporary
read-only D: mount, then one post-apply status/preflight → claim/probe → exact-selector chain;
e2e-runner executes only after that decision.

**Authorization `c8c6ecb5` — host launch stopped before WSL (2026-10-30).** GPT-PM approved one
replacement zero-retry chain including one temporary read-only D: mount. Its first PowerShell
wrapper attempt failed before `wsl.exe` started: `StandardOutputEncoding is only supported when
standard output is redirected` (host command exit 1). No mount or runtime action occurred; post-
apply status, inventory, preflight, claim/probe and TestRun are all `NOT_RUN`. The authorization
was consumed at the first wrapper attempt and was not retried. Exact evidence:
`docs/sdlc/evidence/s2-runtime-qual-c8c6ecb5-s2-runtime-20261030-2b5e04a3.attempt.json`
(SHA-256 `29c20352696333f73fc5f1a746a3983ae0d313fc4a6321da78da5734463459a3`) and matching
`-host-launch.stderr.txt` (203 bytes, SHA-256
`2ef18f51555884c04dff7acaf8d883904dffdbad1b60a42d300c1426d6812693`). Next: Codex requests one
new GPT-PM authorization specifying a noninteractive Windows launcher with child stdout/stderr
redirected; only then may e2e-runner execute the same bounded chain. S2-4 remains IN PROGRESS,
S2-5 stays queued, S3 unstarted, and production activation remains NOT_RUN.

**Authorization `b3a9b780` — host command rejected before Python (2026-10-30).** GPT-PM issued a
one-shot replacement authorization with retry cap 0 and a complete persisted-claim guard. The
designated `e2e-runner` attempted the host call once through `cmd.exe`; command quoting caused
`C:\Python314\python.exe` to be treated as an unrecognized command (exit 1). Python and WSL did
not start; no runtime stage or target change occurred. The authorization is consumed. Exact
command/output and launcher SHA-256 are recorded in
`evidence/s2-runtime-qual-b3a9b780-host-launch-20261030.md`. S2-4 remains IN PROGRESS; S2-5 is
queued. GPT-PM adjudicated request `98594d0e-1fb5-40ba-9ad5-148a3413e4e8` as HOLD for execution,
GO for exactly two launcher-only corrections. The existing tuple remains valid only conditionally
and must pass fresh HEAD, six source-pin, boot/runtime, config and candidate-state checks; no WSL
execution is authorized by that reply. GPT-PM's MAJOR-01 required exact mountpoint detection
instead of `findmnt --target`; MAJOR-02 required an explicit verified repository import path under
isolated Python. Codex made these two changes only in
`evidence/s2-runtime-qual-b3a9b780-launcher.py`; focused GPT-PM review of those findings and direct
regressions is recorded below. Do not run the corrected launcher without a separate runtime
authorization.

The exact correlated outcome and authorized delta are recorded in
`evidence/s2-runtime-qual-98594d0e-launcher-adjudication-20261030.md`. Corrected launcher hash and
the focused review result are now recorded there. GPT-PM request
`43bc1ebf-523d-4e3a-a077-f0b959cf214f` APPROVED the exact bytes at SHA-256
`d4cd4b3d4eacc1ca620223db7ec997821106528e345a6110531ca1a8d32511d5`; MAJOR-01/02 are resolved
and direct regressions passed static review. The same reply explicitly did not authorize a Windows/
WSL invocation. Codex sent separate single-use runtime authorization request
`c7fe8392-72a3-4c81-91ee-8bfe8b3e4382` naming this hash and preserving the prior tuple/pins; reply
pending. No runtime invocation has occurred. If authorized, e2e-runner executes only the bounded
sequence and stops on the first failure.

**Authorization `dc6f1448` — one host launch, stopped before WSL (2026-10-30).** GPT-PM
authorized one direct `C:\Python314\python.exe -I -B -S` invocation of the corrected launcher
(SHA-256 `d4cd4b3d4eacc1ca620223db7ec997821106528e345a6110531ca1a8d32511d5`), with zero retries.
The local checkout was branch `s2-canonical-continuation`, HEAD
`7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`. The host Python process started and exited 0, but its
single attempt to create the authorized WSL child failed with
`FileNotFoundError: [WinError 206] The filename or extension is too long`; the embedded base64 WSL
program exceeded the Windows child-command limit. The attempt record says `wsl_spawned=false`.
Therefore mount/source-pin/runtime predicates, post-apply status, preflight, Owner→Runner
claim/probe, and TestRun are all `NOT_RUN`; no WSL target or Store mutation occurred. This
authorization is consumed and must not be retried. Raw evidence is retained in
`evidence/s2-runtime-qual-dc6f1448-outer.stdout.bin` (36,790 bytes, SHA-256
`da6e103956b4305b3d2ae1ab5e3e087b204c8aaa2582f6f70e93929221615c92`),
`evidence/s2-runtime-qual-dc6f1448-outer.stderr.bin` (0 bytes, SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`), and
`evidence/s2-runtime-qual-b3a9b780-s2-runtime-20261030-2b5e04a3.attempt.json` (36,960 bytes,
SHA-256 `e9aada51fcb599368409993dc192eba756813ce159c2a4c3c6b6a1e0805f84ea`), including WSL
stderr (71 bytes, SHA-256
`6432d39107ce2c19135d41644fad43543b5b4f6ef41d4b8a4a7138dbdeb279e2`) and empty WSL stdout
(SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). S2-4 remains
IN PROGRESS; S2-5 remains queued. Next: Codex coordinates a corrected command-length transport,
obtains a new correlated authorization for its exact bytes, and then the e2e-runner executes only
under that new one-shot decision. The stage-by-stage outcome is summarized in
`evidence/s2-runtime-qual-dc6f1448-outcome-20261030.md`.

**Authorization 268fd73c — HOLD before preflight (2026-10-30).** The one authorized direct host
Python invocation verified launcher SHA-256 6c6e0c6e41bf67c3c170cc08492b45b0c4ae18888741a7fd5d95d7ba6cf16fa1
and exact local HEAD 7d1d16f6348e6c00a5a568b5cfbc8caf309194b9, then started one Ubuntu-24.04 WSL
child. Tuple, six pins, all 26 installed configuration targets, boot/runtime identity, manifest,
systemd jobs/state, and empty Store/preflight/socket paths passed. The first failed predicate was
the launcher's nine-unit parser: all systemctl calls exited 0, but returned MainPID before the
other properties for services and omitted MainPID for the socket, unlike the launcher's assumed
fixed array order. WSL stopped with terminal HOLD before root preflight; no unit start, Owner-to-Runner
claim/probe, TestRun, retry, or production action occurred. The one temporary D: read-only mount
was verified and unmounted successfully. The authorization is consumed. Exact unit arrays, command,
stages, and artifact hashes are in
evidence/s2-runtime-qual-268fd73c-outcome-20261030.md and
evidence/s2-runtime-qual-dc22ee55-s2-runtime-20261030-2b5e04a3.attempt.json. S2-4 remains
IN PROGRESS; S2-5 remains queued. Codex owns the narrow named-property parser correction and new
correlated authorization; e2e-runner executes only under that authorization.

**Authorization 8ee40d1a — HOLD at root preflight (2026-10-30).** The one authorized direct host
invocation verified exact launcher SHA-256 5b03f670ec0f5adb01508d63d9f27582bde40fc66d0a8b490299721b621389db,
size 29,899 bytes, and checkout HEAD 7d1d16f6348e6c00a5a568b5cfbc8caf309194b9. One Ubuntu-24.04
WSL child started. All 17 tuple, HEAD, six source-pin, 26-target config, boot/runtime, manifest,
unit, systemd-job and empty-state checks passed. One temporary D: read-only mount was verified and
unmounted successfully. The single root-captured preflight returned exit 2 with
“probe capture refused: probe namespace exposes an unapproved Windows or host mount”; terminal
HOLD. The preflight command started the one-shot sandbox-probe systemd unit as its measurement
stage; that probe refused the mount inventory before writing an attestation. No assignment
bootstrap, issuer, Supervisor, Runner or dispatch service start, Owner-to-Runner claim/probe,
exact-selector TestRun, retry, workaround or production action occurred. The authorization is consumed. Exact command, stage evidence and raw
artifact hashes are in evidence/s2-runtime-qual-8ee40d1a-outcome-20261030.md and
evidence/s2-runtime-qual-3a3a0e67-s2-runtime-20261030-2b5e04a3.attempt.json. S2-4 remains
IN PROGRESS; S2-5 remains queued. Codex owns reconciling the approved temporary mount with the
preflight refusal; no preflight bypass is authorized.

**Fail-closed mount diagnostic delta (2026-10-30; working tree based on `38f843f`).** The
preflight refusal previously omitted the offending mount category, so the observed attempt cannot
identify the exact namespace entry. Codex added sanitized target classes and bounded filesystem
labels to the refusal message; it does not emit raw source paths or nested usernames and does not
change the rejection predicate. Helper SHA-256 is `c5d4f65b7eba42f68dfcf986ffd80fd35edcb096062d58360a3e51add9af72dd`;
the inventory collector's source pin and test fixture were updated to match. The focused test
command owned and run by `functional-test-reviewer` was
`python -m pytest -q tests/vst/test_s2_preflight_host_capture.py::test_mount_inventory_refusal_reports_sanitized_mount_classification tests/vst/test_s2_preflight_host_capture.py::test_mount_inventory_rejects_windows_drive_and_unlisted_host_mount tests/vst/test_s2_runtime_config_inventory.py` — 35 passed, 1 pytest-asyncio deprecation warning. Security review found no remaining issue. Python review and GPT-PM exact-source review are still pending; this code change is not runtime proof and cannot authorize a retry.

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
| S2-4 | IN PROGRESS — candidate code/config rebind delivered; runtime acceptance open | Latest pushed HEAD `de1c2561080750d1c39af29c3efe0f0c70e40e61` equals upstream. GPT-PM candidate review `7fb85a41-91d0-4b12-a4de-3aaf780e612c` / reply `5af1eb30-7170-5d6a-a517-a90a9b7ddd7f` is correlated and approves code/config commit/push only, 0 B/M; no apply, service activation, E5, Owner-to-Runner, TestRun, production, or full-S2 authority. Candidate suite evidence is 80 passed, 0 failed, one warning at `51b167b` plus the reviewed worktree delta, not a clean rerun at `de1c256`. Candidate is `PREPARED_NOT_INSTALLED`; its bundle/layout pins were reviewed. Previous one-shot runtime attempt `8ee40d1a` is consumed and ended HOLD because the probe rejected an unapproved host mount; Owner-to-Runner claim and TestRun did not run. This older attempt does not prove the current mount-free runner passes. Current run-bound E5, real Owner-to-Runner, and report-bound TestRun remain `NOT_RUN`. | Codex: reconcile the current qualification flow with S2-4's accepted runtime/E5 evidence requirements, then bind any needed run to the pushed source and obtain separate one-shot adjudication. `e2e-runner` executes only after that authorization. Keep S2-5 queued and S3 unstarted. |
| S2-5 | Carried — final gate pending | No final exact-head GPT-PM approval for full S2 is recorded. Codex coordinates the submission after S2-3/S2-4 and reviews complete. |

### Current S2-4 checkpoint — masked-mount false refusal fixed; runtime still open (2026-10-30)

This checkpoint supersedes older S2-4 next-action summaries above where they predate the
interrupted Owner-to-Runner attempt and its journal diagnosis. The current work item remains **S2-4**;
S2-5 is queued and must not start yet.

- **Implemented:** `tools/vst/preflight.py` accepts only an exact `SYSTEMD_MASKED_WSL_PATHS` entry
  whose mount uses the root device/filesystem and `/run/systemd/inaccessible/dir`. Other `/mnt/*`
  mounts, `drvfs`/`9p` drive mounts, and unrelated host mounts still fail closed.
- **Test evidence:** `functional-test-reviewer` added focused regression coverage; the designated
  selectors report **5 passed, 1 warning, 0 skipped** at `aedf712c` plus the dirty S2-4 source/config
  worktree. This is worktree evidence, not clean exact-commit evidence. Full output and provenance:
  `evidence/s2-masked-wsl-mount-regression-2026-10-30.txt` and `.json`.
- **Harness test evidence:** `functional-test-reviewer` added mock-only contract coverage for input
  bounds/correlation, archive and source-pin drift, one WSL child/no retry, and terminal HOLD record.
  Result: **4 passed, 1 warning**, at `aedf712c` plus the dirty S2-4 worktree. This is not
  exact-commit evidence. Full output/provenance:
  `evidence/s2-runtime-qualification-harness-tests-final-2026-10-30.txt` and
  `evidence/s2-runtime-qualification-harness-test-run-2026-10-30.json`.
- **Review evidence:** `code-reviewer` found the prior masked-path false refusal and re-reviewed the
  correction; the exact-path/source predicate is sound and no other confirmed BLOCKER/MAJOR was
  found in the reviewed S2-4 diff. Review was read-only and did not run tests.
- **Recovery review finding and fix:** focused security review found that existing-Store recovery
  verified only the original durable observation claim and could accept stale environment evidence
  after a runtime change (for example, a newly accessible container socket). Codex changed recovery
  to verify the original one-start Store claim, then take and validate one new bounded
  Supervisor-captured runtime observation with a fresh nonce before API readiness; it preserves the
  original Store binding. Independent code and security re-reviews found no B/M in this focused
  correction. Reviewers ran no tests/runtime.
- **Recovery tests:** `functional-test-reviewer` added nine focused POSIX loader cases. Windows
  selected the cases but skipped them due to the POSIX path guard (`9 skipped, 21 deselected`). The
  existing Ubuntu WSL has no `/mnt/d` project mount; evidence is
  `evidence/s2-4-supervisor-recovery-loader-wsl-attempt-2026-10-30.txt/.json`. The test owner then
  streamed a temporary archive of only the needed source/tests into WSL without mount, install, or
  service changes. Two fixture-only failures are retained as superseded attempts; after fixing the
  fixture, the same bounded selectors passed **9/9, 21 deselected** on Ubuntu-24.04, Python 3.12.3,
  pytest 7.4.4. Archive SHA-256 is
  `B80FE142657E9322A05F9BB5EC894F01DBC54321AB2F500FF816B51C55C69591`; test file SHA-256 is
  `E231200D024677C3FA8EE33C673DE501031BA637243C05DF7DFABB1BFEF744AF`. Full output/metadata:
  `evidence/s2-4-supervisor-recovery-loader-wsl-tests-final-2026-10-30.txt` and
  `evidence/s2-4-supervisor-recovery-loader-wsl-final-run-2026-10-30.json`. This is passing
  mocked recovery-contract evidence, not real WSL/systemd runtime evidence.
- **Runner source snapshot fix:** code review found that a clean runtime apply configured Runner's
  working directory `/var/lib/vst-runner/repository` without provisioning the source tree. The
  candidate now builds a deterministic archive of the exact pinned Git tree
  `80c2b81deac364ed6466600fd46af47aafe805e2` (724 entries, 7,802,880 bytes, SHA-256
  `c442a770c5580032b85006fa4522db81770955f7db2a2435c5e1d0e4bfcf3284`) and atomically installs
  one root-owned read-only snapshot before applying configuration; it creates no development
  checkout or per-sprint worktree. The designated Windows run passed **11/11** focused cases at
  `aedf712c` plus the dirty worktree, with one deprecation warning; because its fixture models
  ownership metadata and POSIX operations, this is source/package contract evidence, not live
  POSIX or runtime evidence. Exact command/output/provenance:
  `evidence/s2-4-task-source-snapshot-windows-owner-map-run2-20261030.json/.txt`. Ubuntu POSIX run
  and WSL archive comparison remain `NOT_RUN` because the authorized temporary DrvFS mount did not
  appear in `findmnt`. Read-only code and security reviews found no new B/M; test-fixture review
  confirmed ownership assertions and the root-owned `0777` negative case. Detailed change record:
  `docs/changes/0623-s2-4-runner-task-source-snapshot.md`.
- **Runtime diagnosis:** read-only journal records prove that the probe's `SIGTERM` coincided with
  Ubuntu-24.04 WSL powering down. The historical attempt was bound to source `b38e7239`, run
  `s2-runtime-20261030-87d47f635f1c4231ab052a074dba4be8`, and InvocationID
  `9ae0fc43f0534cc99dda2acb2f0661b0`; it is not evidence for the current `aedf712c` candidate.
  The `systemd-logind` power-off entries precede the probe exit by about 54 ms. Separate WSL
  invocations around a nonblocking service start are consistent with an idle-shutdown lifecycle gap;
  the journal does not prove that specific trigger. See
  `evidence/s2-runtime-distro-shutdown-20261030.md` and the original attempt JSON.
- **Current runtime state:** `INCONCLUSIVE`; no run-bound E5/preflight attestation, Owner-to-Runner
  completion, or authorized report-bound TestRun exists from the interrupted attempt. The old
  attempt is consumed (`retry_cap=0`); its run ID/nonce cannot be reused. The current launcher
  candidate holds one WSL child for its complete bounded protocol, but has not been runtime-proven.
- **Owners and next action:** Codex owns the current task's evidence, change record, and normal Git
  delivery; GPT-PM owns any required exact-head code/runtime adjudication. Current-turn read-only
  code and security reviews of the dirty S2-4 candidate found no new BLOCKER/MAJOR. The designated
  `e2e-runner` Windows source-snapshot run passed 11/11 focused cases, but mocked ownership means
  this is not live POSIX or runtime evidence. POSIX/WSL and current run-bound E5/Owner-to-Runner
  acceptance remain `NOT_RUN`/`INCONCLUSIVE`. The detailed delivery record is
  `docs/changes/0624-s2-4-runtime-candidate-source-delivery.md`. Next, Codex makes the normal
  task-local commit and push; the enforced pre-push hook must not be bypassed. After the exact
  pushed source/config/run identities are bound, Codex obtains a fresh correlated one-shot runtime
  decision; `e2e-runner` executes only that bounded E5 and Owner-to-Runner scope. The consumed
  `8ee40d1a` authorization is never reused. Keep S2-4 active until runtime acceptance and delivery
  are recorded; only then advance to S2-5.

### Latest S2-4 source-pin follow-up — runtime not run (2026-10-30)

GPT-PM's one-shot request `a1333e6f-716a-4ea7-9c21-c792142b1992` returned HOLD because it could not
independently verify the exact runtime execution chain, including host launcher binding. Exact
source inspection then found that the qualification launcher tried to read
`tools/qa/run_s2_runtime_qualification.py` and `tools/qa/s2_runtime_qualification_wsl.py` from
runtime source HEAD `80c2b81deac364ed6466600fd46af47aafe805e2`; both paths are absent from that Git
tree. The launcher now pins those two files separately under `qualification_source_head`, requires
that head to equal the current repository HEAD, verifies the exact committed blobs and worktree
bytes, and keeps runtime-archive pin coverage exact.

The designated `functional-test-reviewer` ran the five focused source-pin selectors at HEAD
`16549bb8f10113b2f05f41b3aa390bad80dab97e`: **5 passed, 0 failed**, exit 0, one pytest-asyncio
deprecation warning. Git/WSL boundaries were mocked. Exact command, file hashes and limitations:
`evidence/s2-4-qualification-head-pins-20261030.json` and `.txt`. Read-only `code-reviewer` and
`security-reviewer` found no material findings; neither ran tests. `git diff --check` passed.
Detailed change record: `docs/changes/0625-s2-4-qualification-source-head-binding.md`.

This focused source-pin criterion is implemented, tested and reviewed, but the change is not yet
committed/pushed. S2-4 remains **IN PROGRESS**: no fresh current-run E5 result, real Owner-to-Runner
result, or report-bound TestRun exists. The request returned HOLD and no runtime was executed.
Owner: Codex. Next: commit this task-local delta and normal-push it through the enforced hook; then
request a fresh correlated one-shot GPT-PM decision bound to the pushed qualification HEAD. Only
`e2e-runner` may execute the authorized bounded runtime scope. Do not reuse consumed authorization
`8ee40d1a`; S2-5 stays queued.

### S2-4 latest StageOnly publication — artifact approved, runtime still open (2026-10-30)

This is the current S2-4 status and supersedes older S2-4 summary/next-action statements above.

The parser source fix `ee69f9f` was reviewed and pushed; source-derived bounded PowerShell probes passed, while pytest remains `NOT_RUN` under the functional-test-reviewer role restriction. GPT-PM request `9174fd39-c2d4-4bd0-93ed-3e41243cdfd2` authorized one exact StageOnly invocation. It exited 0 and published the immutable runtime and helper without selection or unit installation. The read-only post-state confirms the previous `80c2b81` selector remains selected, all nine units are inactive/dead, there are no systemd jobs, and Store is absent.

GPT-PM then approved post-stage manifest identity/consistency only under request `5ed4b8d8-1c5f-4e45-9e92-cb14df136fe7`, correlated reply `315cc40b-9e06-5641-88fc-4ab2ecdd93de` (0 BLOCKER, 0 MAJOR). A read-only post-review check matched all 47 runtime source-map entries and recalculated both current and previous runtime tree hashes to the manifest. Full details are in `evidence/s2-4-post-stage-manifest-review-5ed4b8d8.md` and `evidence/s2-4-post-stage-content-verification-ee69f9f-20261030.json`.

The later candidate rebind is committed and pushed at `de1c2561080750d1c39af29c3efe0f0c70e40e61` (same as upstream). GPT-PM's correlated candidate-only review is request `7fb85a41-91d0-4b12-a4de-3aaf780e612c`, reply `5af1eb30-7170-5d6a-a517-a90a9b7ddd7f`: APPROVE, 0 BLOCKER/MAJOR, eligible for commit/push only. It verified the 25-destination current candidate separately from the 26-destination previous baseline and explicitly did not authorize runtime apply or activation. The designated `e2e-runner` reported the focused suite at `51b167b` plus the exact candidate worktree delta: 80 passed, 0 failed, one pytest-asyncio deprecation warning; this is not a clean run on committed `de1c256`. The candidate remains `PREPARED_NOT_INSTALLED`.

This closes the bounded candidate preparation/rebind and its code/config review only. Current run-bound E5, a permitted real Owner-to-Runner result, and report-bound TestRun remain `NOT_RUN`; no runtime operation is authorized by this review. The older one-shot `8ee40d1a` remains consumed and its HOLD cannot be retried or transferred to the current candidate. Owner: Codex. Next: reconcile the current runtime-evidence flow with S2-4's accepted criteria and then seek a separate, exactly bound one-shot decision before `e2e-runner` runs the scope. S2-4 remains **IN PROGRESS**; S2-5 remains queued; S3 stays unstarted.

### Focused test maintenance note

Historical item, resolved in change0551: Codex reconciled the exploratory selector `test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor` in `tests/vst/test_s2_persistent_runner_service.py`. It assumes a Store with `PRAGMA user_version == 5`, while both baseline `9c1be0f` and current source declare schema version 6. The selector is outside TP-26/27 acceptance and was excluded from the final focused assignment-basis run; do not silently change its historical fixture or count its failure against the accepted S2 candidate tests. Resolution: the designated functional-test reviewer restored a true schema-v5 fixture and reported six passing cases over two selectors; see `evidence/s2-legacy-v5-fixture-run-20261029.md`. Include its permitted regression only after the final S2 code freeze.

## Required evidence references

- Requirements and current limitation register: `docs/sdlc/requirements.md`.
- Current S2 coordinator/runtime adjudication and correlated decisions: `core/STATE.md`, “Current S2 coordinator/runtime adjudication — 2026-10-29”; `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`.
- S2 source/test backlog and M03 source/test closure: `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”; `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
- Transport test details and limits: `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md`.

### S2-4 current checkpoint — manifest prepared; apply authorization unresolved (2026-11-04)

Current task remains `S2-4-runtime-owner-runner-qualification` (REQ-003); S2-5 remains queued. The single GPT-PM-authorized read-only `bootstrap_runtime.py prepare` invocation completed once at source head `ee69f9fbf074a4c73d2d5d1da81c627a57d06071`, exit code 0. Candidate manifest digest `fafaf93158fee300f1b62ea53e8712e8c600b89a7d0b350399de62989cddcc52` and its parsed JSON value match the previously reviewed post-stage manifest; this reuses accepted artifact evidence and does not repeat its review. Captured stdout, stderr, exit code, pins, and decision correlation: `evidence/s2-4-bootstrap-prepare-result-20261104.json` and its referenced files.

The requested next operation is a distinct one-shot `apply`: it would change the runtime selector and write the six manifest-bound unit files while leaving services inactive, and create a persistent recovery journal. GPT-PM request `e1c87043-327f-43e4-a406-a76e3a8d1c92` / job `e63b3124-62be-4046-88c9-bc58623f300f` is `UNCERTAIN`, with no correlated `userTurnId` or `replyId`; the same-ID retry resolved to the original job with `attempts=1` and did not yield approval. The latest `pm_bridge_job_status` call reported “No compatible PM Bridge orchestrator is active; durable job status is unavailable”; `pm_bridge_health` separately reported OK/ON, while the message log still contained no outbound record for this request. No apply was run. Exact proposed invocation and transfer ID are preserved in `evidence/s2-4-bootstrap-apply-proposal-20261104.txt`. Do not start apply without a correlated GPT-PM APPROVE, and do not retry or recover an uncertain/partial apply.

Runtime E5, live Owner-to-Runner, report-bound TestRun, and production acceptance remain `NOT_RUN`. The manifest-authorized assignment-basis test passed 1/1 at `173b7af`; its source/test files are unchanged through `943ee9a`, so that accepted result is retained rather than repeated for a HEAD-only change. Owner: GPT-PM for exact apply adjudication; Codex for the same-request Bridge recovery and subsequent authorized execution. Next action: resolve the durable status for request `e1c87043-327f-43e4-a406-a76e3a8d1c92`; only after a correlated approval, execute its exact one-shot command, then capture read-only post-apply evidence. S2-4 remains **IN PROGRESS**.

Internal code-review evidence is recorded at `evidence/s2-4-internal-code-review-943ee9a-20261104.md`: bounded source review of the assignment-basis path and exact proposed bootstrap apply found no material issue. This does **not** satisfy the manifest-required signed VST `IndependentReview` receipt; that receipt and report-bound `TestRun` remain absent. The separate stop/restart capability in `tools/qa/apply_s2_runtime_configuration.py` is outside the exact bootstrap command and is not invoked by it. The review did not run tests or establish runtime/E5/Owner-to-Runner evidence.

Latest same-turn read-only Bridge check: job `e63b3124-62be-4046-88c9-bc58623f300f` remains `uncertain` / `sending`, with `userTurnId=null`, `replyId=null`, `attempts=1`, and held generation lease; no retry or apply was issued. `pm_bridge_health` reported `DAEMON_DOWN`, while `pm_bridge_mode_status` reported mode ON, one active send-and-await for another project, and queue depth 3; project message log had no exchanges. Do not start a second daemon or disturb queued work. Codex owns same-request status recovery; GPT-PM owns the correlated apply decision.

Task-manifest reconciliation is still open. Committed `HEAD:docs/sdlc/runtime-config/task-manifest.json` has `base_head=ee69f9f` and allows only the assignment-basis test path. The pre-existing worktree edit (origin/approval not verified; not changed in this turn) sets `base_head=67361bb` and adds the manifest itself to the allowlist; its SHA-256 is `7e5675de860b493db755465957ed05b7f3e9c63fdd0fe29ab670ce9bef078c04`. Against that worktree base and committed HEAD `943ee9a`, Git reports 12 changed paths and none are in the edited allowlist. The runtime snapshot helper independently pins task source `67361bb` and its tree; this does not make the edited manifest or a report-bound receipt accepted. Do not claim a report-bound run from either manifest identity until the task input/scope is reconciled.

### S2-4 continuation correction — task-manifest and Bridge state (2026-11-04)

Correction to the preceding note: comparing manifest base `67361bb` directly with branch HEAD `943ee9a` does **not** establish that the report-bound runner diff gate fails. The runtime snapshot helper pins a clean task candidate at `67361bb`; the actual task execution cwd/candidate must be used for that gate conclusion. No report-bound TestRun was created, so this candidate/manifest relationship remains unresolved rather than failed.

The read-only runtime inventory `evidence/s2-4-runtime-inventory-stdout-20261104.json` records installed `/etc/vst-runner/task-manifest.json` SHA-256 `9c1f6f11f7e92294a3bad3425febfae2ef432d269e53aa6ff0ce3bb3e895296a`, which matches the committed task-manifest blob at `ee69f9f` (size 3596). The current branch bundle manifest at HEAD `943ee9a` declares task-manifest SHA-256 `65e591a2214c653502da8228fdcd5ec88f2ed27d7ed47f74a7839063eff1c61e`; the pre-existing worktree task-manifest edit is instead SHA-256 `7e5675de860b493db755465957ed05b7f3e9c63fdd0fe29ab670ce9bef078c04`. These are three distinct identities. The prepared `bootstrap_runtime.py apply` proposal is pinned to source HEAD `ee69f9f` and its scope replaces the runtime selector and six unit files; it does not install/update `/etc/vst-runner/task-manifest.json`. Therefore that apply alone cannot reconcile the installed task manifest with the current bundle/worktree candidate. No separate configuration apply is authorized or executed.

Latest read-only PM Bridge status in this continuation: health `OK`, mode `ON`, queue depth 2 across two projects, active 0, held by nothing. The exact S2-4 apply authorization job `e63b3124-62be-4046-88c9-bc58623f300f` for request `e1c87043-327f-43e4-a406-a76e3a8d1c92` remains `uncertain` / `sendPhase=sending`, `attempts=1`, `userTurnId=null`, `replyId=null`, `generationLease=held`, `CHATGPT_SEND_UNCONFIRMED`. Project message log still reports no exchanges. This is not an approval and does not authorize apply; no resend, apply, test, runtime mutation, or activation occurred in this continuation.

Current ordering: (1) Codex reconciles the exact task snapshot, manifest identity and installed configuration path without treating branch HEAD as the task candidate; (2) recover the same uncertain Bridge job without sending a duplicate and obtain a correlated GPT-PM decision before the proposed runtime apply; (3) only after those dependencies are resolved, run the allowed task-bound runtime evidence through the designated `e2e-runner`. S2-4 remains IN PROGRESS; report-bound signed TestRun, signed VST IndependentReview, current E5 and live Owner-to-Runner remain NOT_RUN; S2-5 stays queued.

Same-turn recovery result: `gpt_session_peek` for the existing `:peek` idempotency key is refused because that read-only job is durably cancelled (`attempts=0`); `gpt_await_reply` for the original apply-authorization request fails with “No durable successful send baseline exists.” Neither call sends a new GPT-PM message. The original send-and-await job remains uncertain with no correlated user turn or reply. No apply or runtime work is authorized. Owner remains GPT-PM for the decision and Codex for exact same-request transport recovery; next action is to resume same-request status recovery only when Bridge can establish a durable correlated send/reply, then proceed only on an actual APPROVE.

### S2-4D exact scope reconciliation — installed manifest rejects pinned candidate (2026-11-04)

The active ordered subtask is S2-4D, not S2-4E: reconcile the report-bound task manifest and TestRun scope before current E5/Owner-to-Runner qualification. Exact snapshot source is pinned in `tools/qa/runtime_snapshot_transaction.py` as `TASK_HEAD=67361bb4aa23355d9a6bc7877a987ba688559eda`. The WSL inventory records installed `/etc/vst-runner/task-manifest.json` SHA-256 `9c1f6f11f7e92294a3bad3425febfae2ef432d269e53aa6ff0ce3bb3e895296a`; that blob is the committed version at `ee69f9f`, whose `base_head` is `80c2b81` and whose sole allowed path is `tests/vst/test_s2_assignment_basis.py`. A read-only Git path comparison from that installed base (`80c2b81`) to the pinned task candidate (`67361bb`) finds 30 changed paths, all 30 outside the installed manifest allowlist. Thus the installed manifest cannot accept a report-bound TestRun for this pinned candidate; this is a confirmed scope mismatch, not the earlier unsupported comparison of task candidate `67361bb` to branch HEAD `943ee9a`.

The committed task-manifest at branch HEAD `943ee9a` has `base_head=ee69f9f` and is what the committed bundle manifest expects (SHA-256 `65e591a2214c653502da8228fdcd5ec88f2ed27d7ed47f74a7839063eff1c61e`). The pre-existing worktree candidate has `base_head=67361bb`, allows the assignment-basis test plus the manifest path, and SHA-256 `7e5675de860b493db755465957ed05b7f3e9c63fdd0fe29ab670ce9bef078c04`; it is not installed and its origin/approval is not verified. The prepared `e1c87043` bootstrap apply is based on source `ee69f9f` and changes only the runtime selector and six unit files; it does not update task-manifest configuration, so it cannot by itself close S2-4D.

Owner: Codex reconciles the exact approved task-manifest/bundle candidate and prepares the narrowly scoped configuration operation; GPT-PM must issue the required correlated approval before any root-owned runtime/configuration mutation. Next: do not run the existing bootstrap apply as a substitute; first produce the exact task-manifest installation plan and review it against pinned `67361bb`, then seek its own correlated decision. After S2-4D passes and the required report-bound TestRun/IndependentReview exist, continue to S2-4E for current E5 and the bounded real Owner-to-Runner journey. Current Bridge job `e63b3124` has no durable successful send baseline and no correlated reply; its `:peek` job is cancelled, so no approval is available now. No test/runtime command was run in this continuation.

Architecture-boundary check: `tools/vst/runtime_snapshot_transaction.py` and the deployment source manifest pin the task snapshot at `67361bb`, while `bundle-manifest.json` pins `runtime_source_head` and `source_head` to `ee69f9f`. Existing consistency assertions in `tests/vst/test_s2_runtime_config_bundle.py` require `bundle.source_head == bundle.runtime_source_head` and `task.base_head == policy.source_head == bundle.source_head`; the second assertion therefore binds the task diff base to `ee69f9f`, not the task snapshot `67361bb`. The pre-existing worktree candidate's `base_head=67361bb` would conflict with that asserted contract, and its new allowlist does not reconcile the installed policy/bundle digest chain. This test file was read, not executed. S2-4D now requires GPT-PM to adjudicate the intended identity contract (separate task-source base from runtime-source head, or an alternate candidate/scope) before Codex changes the cross-bound configuration. Do not expand the allowlist, rewrite digests, or apply root configuration by inference.

The read-only architecture request is `f2070578-cdc4-47e5-a602-c4dc9ef3f02d`, Bridge job `8b3e5848-8a50-4b4d-8776-bb7dbb121e9d`. PM Bridge health is OK/ON, but the request remains queued (`attempts=0`, `sendPhase=not-started`, no userTurnId/replyId); the shared worker is processing another project's job and the queue is shared across five projects. The request was sent once; do not duplicate it. The stale e1 apply-authorization job remains uncertain and cannot authorize this contract or any apply. Next: Codex resumes the same adjudication job/status; after the correlated GPT-PM decision, implement only its accepted contract delta, delegate the focused tests, then seek a separate exact configuration authorization. No tests/runtime actions were run.

Follow-up in the next turn: the same apply job still has no correlated user turn/reply and remains `uncertain`. Bridge health now reports `OK`; mode status is ON, but the queue has an active `stuck-lease-probe` not yet claimed and depth 4. The read-only peek job was cancelled before execution (`attempts=0`); no new GPT-PM message was sent and no apply/test was run. Continue status recovery by the same request/job identity; do not resend or restart while the shared queue is active.

### S2-4D hash-chain correction — current bundle digest does not match either task-manifest copy (2026-11-04)

Current-turn byte hashing corrected the preceding S2-4D digest note. At `HEAD=943ee9af3361df74f513e5c4f361a57ca1b2df8f`, the committed task-manifest SHA-256 is `65e591a2214c653502da8228fdcd5ec88f2ed27d7ed47f74a7839063eff1c61e`; the pre-existing worktree candidate remains `7e5675de860b493db755465957ed05b7f3e9c63fdd0fea29b670ce9bef078c04`. The clean committed `bundle-manifest.json` instead pins task-manifest SHA-256 `f00e05e42822d383acd7cd74a149872abeed745f04014933261fbb3d6515be2f` (64 hex characters, as recorded in its `task_manifest_sha256` field), which matches neither copy. The deployment-source manifest independently binds runtime source `ee69f9f` and task source `67361bb`; do not collapse those identities. A read-only scan of the three commits containing this tracked manifest found no blob matching the bundle's declared digest. Therefore the existing worktree candidate is not a verified bundle-compatible manifest, and the prior statement that the bundle expected `65e591...` was incorrect.

The same single read-only GPT-PM contract request remains queued as request `f2070578-cdc4-47e5-a602-c4dc9ef3f02d`, job `8b3e5848-8a50-4b4d-8776-bb7dbb121e9d`; latest status is `attempts=0`, `sendPhase=not-started`, with no correlated user turn/reply. No resend, manifest edit, configuration apply, test, or runtime mutation was performed. Owner: Codex for exact hash-chain reconciliation; GPT-PM for the queued identity-contract adjudication. Next: consume the same correlated adjudication if it arrives, then reconcile a single task-manifest candidate against the bundle/policy/diff-gate contract before requesting any narrowly scoped configuration authorization. S2-4D remains IN PROGRESS; S2-4E and S2-5 remain queued.

### S2-4D PM transport recovery — no architecture decision received (2026-11-04)

The prior paragraph's `f2070578` job was confirmed `queued`, `attempts=0`, `sendPhase=not-started`, then cancelled before execution; it was never sent. A replacement read-only adjudication was sent once under request `b932b968-91ac-44be-82b8-2a53d7990c93`, job `b418942f-93fb-477d-bcce-47eeb57e75be`, correlated to `userTurnId=3fd0dd10-bf46-4a1a-ab13-ed80857bdc2f`. The await result is `correlated=true`, `replyId=e5e3992c-b203-59e2-918f-cf4a3d46c49a`, but its entire content is `ChatGPT said: This response couldn’t load / Reload response`; it contains no adjudication and is not approval. A subsequent read-only `peek` returned `operation was aborted`; its queued job was cancelled before execution (`attempts=0`). No resend, code/config change, test, or runtime action followed.

Therefore S2-4D remains **IN PROGRESS**. Current-turn source inspection established the corrected digest evidence above; the only repository edit in this continuation was this backlog evidence correction. Owner: GPT-PM for the actual architecture decision; Codex for resuming that same adjudication once PM Bridge can return readable content and then implementing only its accepted delta. Exact remaining dependency: a readable, correlated GPT-PM decision specifying whether/how task-source/base identity is separated from runtime-source identity; without it, changing the validators or manifest digest chain would choose an unadjudicated contract. A second read-only peek request `e7bcf75d-babc-4fa7-a9ba-8d09d1228750`, job `7594f013-10bd-4379-bbde-a365275477ce`, also aborted before execution and was cancelled at `attempts=0`; no additional review message was sent. S2-4E and S2-5 remain queued.



### S2-4D correction and current candidate reconciliation (2026-11-04)

The hash comparison recorded above was invalid: `bundle-manifest.task_manifest_sha256` is the canonical-JSON digest defined by `tools/vst/contracts.py::manifest_sha256`, not the raw file SHA-256. The committed bundle at baseline `943ee9af3361df74f513e5c4f361a57ca1b2df8f` was internally consistent: its canonical task-manifest digest was `f00e05e42822d383acd7cd74a149872abeed745f04014933261fbb3d6515be2f`, and its raw file record matched committed task-manifest SHA `65e591a2214c653502da8228fdcd5ec88f2ed27d7ed47f74a7839063eff1c61e` (3596 bytes). The pre-existing dirty manifest candidate (`7e5675...`) was a separate, unbound candidate. Thus the earlier claim that the committed bundle did not match its manifest was wrong; the actual S2-4D need is to bind the selected task-source base and allowed-path scope into a reviewed new candidate, while retaining the distinct runtime-source identity.

Current-turn implementation updated only the existing task-manifest candidate, assignment policy, supervisor policy pin, bundle member records and two candidate digest pins. The selected contract keeps runtime source `ee69f9fbf074a4c73d2d5d1da81c627a57d06071` separate from task source/base `67361bb4aa23355d9a6bc7877a987ba688559eda`; task manifest `base_head` now matches task source, its allowed path list matches `change_scope.allowed_paths` and excludes the manifest itself, and the policy, supervisor and bundle digests are cross-bound. The exact current candidate values are recorded by the files in `docs/sdlc/runtime-config/` and the pins in `tools/qa/apply_s2_runtime_configuration.py` and `tools/qa/verify_s2_runtime_config_inventory.py`; no runtime apply or test was performed in this turn. These edits are a local candidate only and do not establish installation, current E5, Owner-to-Runner, or task acceptance.

The GPT-PM reply previously recorded under request `b932b968-91ac-44be-82b8-2a53d7990c93` contained only a client load-error message, not architecture adjudication; its prompt also used the invalid raw-vs-canonical comparison, so neither that prompt nor its reply is decision evidence. Owner: Codex for the concrete source/config reconciliation and exact evidence; GPT-PM for review of the actual code delta before commit/push. Next: finish internal source review, then delegate focused tests for the cross-binding regression, relevant specialist review, and request fresh exact-head GPT-PM code approval. S2-4D remains IN PROGRESS until those checks and its authorized scope are complete. S2-4E and S2-5 remain queued.


### S2-4D candidate implementation and verification status (2026-11-04)

Current S2-4D acceptance remains: bind the report-run task manifest to the task-source base and its exact allowed paths, preserve separate runtime/task source identities, make the diff-gate input internally consistent, and obtain GPT-PM's exact runtime-authorization adjudication. No runtime apply, E5, production configuration, Owner-to-Runner run, or report-bound TestRun occurred.

Current-turn candidate changes: the TaskManifest is now pinned to the task-source HEAD `67361bb4aa23355d9a6bc7877a987ba688559eda`; its `scope` equals `change_scope.allowed_paths`, which excludes the manifest itself. The bundle retains runtime HEAD `ee69f9fbf074a4c73d2d5d1da81c627a57d06071` separately from `task_source_head`. Applier, inventory validator, and collector pins now cross-bind the validated canonical TaskManifest digest, assignment policy, Supervisor pin, deployment-source binding, exact raw bundle member hashes, and `tools/vst/contracts.py` source hash. The TaskManifest is passed through the shared `validate_task_manifest`/`manifest_sha256` contract before acceptance. Candidate bundle state remains `PREPARED_NOT_INSTALLED`.

The functional-test reviewer updated three existing test files to match split runtime/task identities, the V2 apply payload, the 27-destination configuration set, and `git-pack-shallow-v1`; it also added malformed-schema and identity-cross-binding regression cases. These edits are uncommitted and are authored test changes, not test evidence. Exact current evidence: the designated test role reports **no tests executed**; the single report-bound selector `tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment` remains `NOT_RUN`, and new local applier/inventory selectors also remain `NOT_RUN`. The report-bound tool `tools.qa.run` is not available in this session, and direct pytest is prohibited by the active test-role profile; no substitute runner was used.

Internal review results: `code-reviewer` findings for schema validation, collector hashes, contracts source pinning, and collector field mapping were corrected; its final pass reported no remaining finding. `python-reviewer` reported no Python correctness findings. `security-reviewer` reported no security finding in the source/config delta. These reviews do not replace unrun tests or runtime evidence.

State: S2-4D remains **IN PROGRESS** and no commit/push was made. Owner: Codex coordinates the missing VST Runner interface and then the permitted tests; GPT-PM owns the exact code/runtime-authorization adjudication after current evidence is assembled. Next: make the designated `tools.qa.run` interface available to the test role, execute only the report-bound selector, then run the authorized focused local regression selectors; reconcile results and request one exact-head GPT-PM review. S2-4E and S2-5 remain queued.

### S2-4D delivery checkpoint - 2026-11-05

S2-4D remains IN PROGRESS. Two code candidates were committed and normally pushed to origin/s2-canonical-continuation: 4ec4fbc binds the TaskManifest/task-source contract and digest chain; e1f6d93 binds the report-bound TestRun receipt candidate head, nested manifest digests, and PASS diff-gate verdict to the exact authorized immutable task snapshot.

GPT-PM approved the exact 4ec4fbc source/config candidate under request 62c95b1d-4f94-4f73-815c-5cb4ef2f2ac1 and approved the exact WSL source hash D68D613F8F1C33B84696FFE726A67A5B8358769D57CFFF1D15962BDC2F1D7C43 under request 47d94dbf-7467-4c0f-b8d6-3e62c6a439f2. Test file SHA 320A36331E01F8F9F4A6E1E8F4C26A69A083DB8496E762B15541406215772DF8 matched at commit time. The designated e2e-runner reported 84 passed, 1 warning, exit 0, at base HEAD 4ec4fbc while exercising the exact changes committed as e1f6d93. No duplicate run was requested. Internal code, Python, security and architecture reviews found no remaining in-scope finding after the candidate-head identity disagreement was resolved against the frozen task-source contract.

The mandatory report-bound selector tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment remains NOT_RUN and blocks final S2-4D acceptance. GPT-PM explicitly granted no runtime authorization. The candidate bundle remains PREPARED_NOT_INSTALLED; no config apply/install, service activation, bootstrap, current E5, live Owner-to-Runner execution, or production dispatch is claimed. The AssignmentPolicy window was 2026-11-04T20:31:32Z through 2026-11-05T20:31:32Z and must be rechecked before any separately authorized runtime operation.

Owner: Codex coordinates preparation and the exact request. Dependency: correlated GPT-PM one-shot runtime authorization plus the required exact prepared target. Next: assemble that tuple and request authorization for only the manifest-bound report TestRun; after authorization and target preparation, e2e-runner executes the selector and records command, revision, and result. Keep S2-4D current; do not start S2-4E/S2-5 until acceptance closes.

### S2-4D inventory launcher failure - 2026-11-05

GPT-PM request `2f72c8c5-ea0a-4f17-9f2b-c6060f80704a`, correlated reply `b61d2783-0a70-56db-a126-171ebf759f49`, authorized exactly one read-only collector invocation. The command returned exit 2 before loading the collector because `/mnt/d/Repo/Virtual_scrum_team/tools/qa/collect_s2_runtime_config_inventory.py` was unavailable. Complete stdout (0 bytes), stderr (156 bytes), exit code and authorization metadata are preserved in `s2-4-runtime-config-target-inventory-20261105T0144Z.*` under this evidence directory. The grant is consumed; no retry was performed. No collector, service/configuration/Store mutation or test execution occurred in that invocation.

Current task remains S2-4D. Codex owns correcting the launch boundary: inspect mountpoint before loading the collector, permit a read-only D: mount only when absent, preserve binary stdout/stderr and exit status. The corrected invocation is subject to narrow internal review and a fresh correlated authorization; prior accepted source/tests/reviews remain the baseline. S2-4E and S2-5 remain queued.

### S2-4D selected target and Windows transport remediation - 2026-11-05

Codex collected complete binary-preserved inventory at current HEAD e1f6d93 (`s2-4-runtime-config-target-inventory-20261105-operator-01.*`); functional-test-reviewer ran the local validator, which refused the selected old runtime. Codex then applied the unchanged accepted bootstrap manifest fafaf93158fee300f1b62ea53e8712e8c600b89a7d0b350399de62989cddcc52 under the operator autonomous GO. Exact output in `s2-4d-bootstrap-selection-20261105-operator-01.*`: exit 0, bootstrap_selection=complete, services_started_or_reloaded=false, store_opened_or_changed=false. The target now selects ee69f9f; do not repeat bootstrap apply. The original stage-inventory hash and fresh config-inventory hash identify different artifacts; code-explorer withdrew its unsupported claim that the accepted bootstrap manifest needed a new hash.

Fresh postselection inventory (`s2-4-runtime-config-target-inventory-20261105-operator-02.stdout.json`, raw SHA 46336c47cd5cab0b60e5f623725d65acdc66bedc7aef84dee6d41c3951bdf342) passed the assigned local validator. Config installation has NOT reached WSL: attempts 01/02 refused host checkout identity (CRLF-only clean test file restored to exact accepted Git blob by functional-test-reviewer; index metadata refreshed), then attempt03 failed Windows CreateProcess with WinError206 before WSL because the embedded root Python source exceeded command-line length. Full exact outputs/exit codes are in `s2-4d-config-apply-20261105-operator-0{1,2,3}.*`. No config install or service/TestRun/Store activation is claimed.

Codex implemented the concrete transport remediation in apply_s2_runtime_configuration.py: short -c loader, bounded 8-byte source-length frame over stdin, followed by unchanged original payload, for apply and recovery. Collector applier hash updated. Coding is complete and local tests are owned by functional-test-reviewer. Initial focused result 84 passed/1 failed exposed a candidate-source fixture identity mismatch, currently under test-only reconciliation; it is not a passing run. Next: finish focused tests, relevant independent code/security reviews and internal consensus, final GPT-PM review of only this source delta, commit/push, then fresh inventory and exact configuration apply. S2-4D remains current; S2-4E/S2-5 queued.

### S2-4D transport candidate ready for final code review - 2026-11-05

The designated functional test roles completed real Windows subprocess long-source/framing tests and both normal/recovery main wiring tests. Combined exact command: `python -m pytest -q --tb=line tests/vst/test_s2_runtime_configuration_apply.py tests/vst/test_s2_runtime_config_inventory.py`; captured exit 0, 93 passed, one pytest_asyncio deprecation warning in 51.05s. Exact output, exit, baseline HEAD and source/test SHA are in `s2-4d-wsl-transport-tests-20261105-captured.*`. This supersedes the earlier failed fixture run; production source guards remain intact.

Independent actual code-reviewer `/root/s2_4d_transport_code_review` and security-reviewer `/root/s2_4d_transport_security_review` (configured gpt-6-luna, explicit medium effort) reviewed only the four-file transport delta and direct integrations; no in-scope findings remain. They did not execute runtime/tests independently. Final GPT-PM code review was sent once as request `c697062b-d2dc-49a3-a503-809b0a144d5c`; baseline e1f6d9363ed9b85c998786a2688ca79f4aeca8ff, candidate applier SHA fb5450576ddd74a6987b576b2e3c6d2166fffe1444b9d578914b6414fe802e3b, diff SHA ee6f52d8841acdf820d2fae2e95dc13e032fe9fa32fff17f0b65aefaf31a99c8. Await the same request; do not resend or fabricate approval.

Current source candidate is not yet committed/pushed. Next: receive final candidate code verdict, commit/push only its four files if approved, then collect fresh target inventory and resume the exact config installer. Bootstrap selection has already completed; do not repeat it. New transport WSL apply/recovery and report-bound TestRun remain NOT_RUN. S2-4D stays current; S2-4E/S2-5 remain queued.

### S2-4D transport delivered; real systemd admission correction - 2026-11-05

GPT-PM request c697062b-d2dc-49a3-a503-809b0a144d5c approved exact four-file source candidate with 0 BLOCKER/MAJOR/MINOR and independently matched all hashes. Codex committed/pushed 908463f076335a27fbc2694a51b983e58821d366 normally (e1f6d93..908463f), HEAD equals upstream, PR #2 updated. Do not reopen accepted transport or repeat93 tests solely due new HEAD.

The real configuration attempt at 908463f passed Windows transport but initially refused a missing Git repository inside WSL. Read-only diagnostics proved distro PID1 restarted between separate WSL calls (same kernel boot ID, changed PID1 start_ticks); temporary read-only D mount was lost. A scoped stdin-held WSL process then kept one distro lifetime across fresh collection and apply; its stdin was closed and exit0 observed afterward. No persistent keepalive was installed.

The held-lifetime attempt `s2-4d-config-apply-908463f-20261105-02.*` reached root-side unit admission and refused before configuration publication: `unit is transitioning or failed; refusing configuration apply: vst-supervisor.service`. Read-only actual output in `s2-4d-systemd-order-diagnostic-20261105.json` proves systemctl --value does not emit requested property order; ControlGroup empty was misread as ActiveState. Config remains NOT_INSTALLED; no TestRun/service activation/Store operation is claimed. Bootstrap selection remains complete and must not repeat.

Codex completed a scoped source fix: named systemctl key=value output, strict exact-five-field parser rejecting missing/duplicate/unknown/malformed fields, preserved empty values, existing state/mask guards retained, collector applier SHA updated (candidate24e53a80dc4a728384407fe52d4121854e9c08b1cc2154bc0456aa49fd8465bf). Designated functional-test-reviewer is authoring/running the concrete property-order admission regressions after coding. Next: focused verification, code/security consensus on this delta only, final GPT-PM code review, commit/push, then repeat fresh held-lifetime inventory/config apply after the actual refusal has been fixed. S2-4D current; later tasks queued.

### S2-4D named parser delivered; authentic bootstrap predecessor adapter - 2026-11-05

Final GPT-PM review b4fc9eb2-fbfd-41aa-9349-83307ea7ba97 independently matched the three source/test hashes and approved named-systemd parser source with 0 B/M/minor. Codex committed and normally pushed 2b86f091d07ae3b6525e1d088b61d062d9a4dbca (908463f..2b86f09), current upstream equal; PR #2 updated. Designated focused tests105passed, exit0; baseline accepted.

The held-lifetime real WSL attempt `s2-4d-config-apply-2b86f09-20261105-01.*` passed corrected transport/Git/named-property admission, then refused BEFORE configuration publication: protected service invocation identity unavailable. Existing code unconditionally requires actual systemd invocation and STOPPED_EMPTY, while this target has inactive services with no current invocation. No config install/activation/TestRun occurred, lifetime holder exited0.

Actual READONLY eligibility evidence `s2-4d-cold-eligibility-2b86f09-20261105-01.json` SHA614c44a8ab60c99c37a53e8d5aeab543070c6b45841a13d9320773a0e93b0770 confirms ledger/generation absent; role-UID process counts0; bothprotectedunits inactive/dead with empty IDs/groups; live root present root0755, reviewed predecessor a600774649527ff0b33eb81f4d431f8226119b2c/tree38a0a60b6170d068beb370c62f25b008d246902f. Fixed cgroup emptiness must be positively observed by the existing bootstrap primitive/shared guard; it is not inferred from empty systemd ControlGroup. Do not invent a historical never-ever-started claim.

Architect and code-explorer reconciled older design wording with latest actual configuration: this is exact pinned predecessor config replacement, not all-configs-absent install. Deployed immutable runtime ee69f9f already contains runner_fence.bootstrap_empty identical to HEAD; it can emit genuine BOOTSTRAP_EMPTY only with empty ledger, inactive Runner, no reserved-UID processes, fixed cgroup empty/nochildren, and root-controlled config. Accepted path: separately typed RUNNER_BOOTSTRAP_EMPTY transaction state and current root quiescence proof, no fake systemd ID or STOPPED_EMPTY receipt, strict hot path unchanged, no generic historical-ledger upgrades. Existing present-root snapshot/config/recovery lineage remains mandatory.

Current coding ownership: implementation-engineer /root/s2_4d_bootstrap_transaction_helper owns only runtime_snapshot_transaction.py shared observation/ensure/cold-state/recovery validation; Codex owns applier integration and collector pin. Code is still IN PROGRESS; no new tests executed yet. Next: finish shared helper, then designated functional/POSIX tests, relevant independent architecture/code/security consensus, final GPT-PM code/contract review, commit/push, actual fresh held-lifetime apply. Codex owns technical execution/coordination, GPT-PM final adjudication. Later sprint/tasks remain queued.

### S2-4D bootstrap adapter code freeze and focused verification - 2026-11-05

Helper implementation-agent completed only runtime_snapshot_transaction.py: pinned EE bootstrap/source checks, strict current quiescence observation, authentic one-record BOOTSTRAP_EMPTY baseline and derived generation repair, distinct cold journal state, exact-mask/guard proof, pre-exchange recheck, and cold recovery receipt requirement. Parent found and worker corrected candidate-live recovery observation to accept only reviewed candidate HEAD/tree/mode0555 with readonly Git proof, alongside exact predecessor0755; helper frozen SHA4f623aad13155e5867758a9cc61386c900476e169840927eb9066759c1c4b078. No helper runtime mutation occurred.

Codex integrated cold apply/recovery call sites, leaving hot stop/fence branches strict, and updated collector source pin. First designated host test capture `s2-4d-bootstrap-host-tests-20261105-01.*` failed collection on a parent-authored recovery indentation error; no cases executed. Codex restored the accepted recovery baseline and inserted the cold branch at the actual top-level stopped-fence block, preserving completed-recovery quick exit. Current applier freeze SHAc66df10dc7909c6944c674f7a7d513c850665970c70a2f7c17ae20b2d28657d3; collector pins it. Designated test role owns existing apply tests plus new test_s2_runtime_bootstrap_transaction.py; resumed host tests after source refreeze. POSIX-only cases must run in established WSL system pytest environment after test files freeze; Windows skips are NOT_RUN, not PASS. Current source uncommitted, no root apply retry until assigned verification/review/commit/push. S2-4D stays current; bootstrap selection already complete, do not repeat.


### S2-4D cold predecessor adapter delivered; runtime qualification pending - 2026-11-05

Current-turn final candidate: helper3b2f44d, applierc66df10d, collectorbe0629ee, applytests3df32048, bootstraptestsea552639. Designated host evidence host-tests-20261105-05:109passed,1POSIXmodule skipped; final native bootstrap-posix-tests-20261105-06:44passed,exit0,stderr empty. Earlier -05 four failures were test expectations and missing stat path redirection, fixed without changing helper3b. Actual read-only observer02 passed at04:14:05UTC, no ensure/bootstrap/exchange executed. Real power-cut NOT_RUN.

Independent current-turn reliability reviewer resolved its parent-directory fsync MAJOR; independent code reviewer found no material direct regression. GPT-PM final correlated request ae97205e-f1c1-4fc9-9928-17d95332fb76/reply67e6f11d-dd9b-5d40-9bee-b87066eb10d3 approved all exact five file hashes and diffd04a8caa with0BLOCKER/MAJOR/MINOR. Exact reviewed blobs committed as1886810e79b8fc1815f92708559a8798d7740dab and normally pushed origin s2-canonical-continuation (2b86f09..1886810),exit0. Existing PR#2 updated. Unrelated pre-existing dirty documents/reports preserved, not included.

S2-4D remains current/open: next fresh held-lifetime real configuration apply using pushed1886810 under existing operator sandbox-setup GO; then actual correlated one-shot report-bound TestRun authorization and designated execution. This source review does not itself grant runtime/production authority or establish task acceptance. Do not repeat accepted bootstrap selection or earlier approved source work. Codex owns execution/coordination; GPT-PM owns required final runtime adjudication. S2-4E/S2-5 and later sprints queued, not begun.


### S2-4D exact worker Git trust remediation delivered - 2026-11-05

Real apply1886810 evidence config-apply-1886810-20261105-01 refused in build_git_stage before transaction/config publication. Actual diagnostic stage-git-diagnostic-1886810-20261105-01 captured workerUID997 rc128 dubiousownership; exact command-local trust replay captured expected67361bb HEAD/0c4a844 tree/shallowtrue. Marker/Store/ledger absent; disposable stage retained, not removed.

Codex changed only shared helper Git argv: absolute canonical root-owned directory with no group/other writes or wildcard, exact command-local safe.directory; output/binarydiff share it. Functional role authored actual tiny shallowGit-stage/worker/env/unsafe-root/dirty tests; e2e role final native bootstrap-posix-tests-20261105-07:48passed,exit0,stderr empty. Actual independent code/security reviews found no actionable findings. GPT-PM correlated6bc91aa6-92bf-4ebc-b9a4-7b4f28a009b0 approved exact helpercc6eb947/test8549aa61 and diff49d2120f,0B/M/minor, preserving priorae97205e acceptance. Codex committed/pushed ad45ba1bc8134cfc6caddf205d74204a216dc881; upstream matched. PR#2 updated.

Current S2-4D next operation is single fresh held-lifetime configapply atad45ba1 under existing operator sandbox-setupGO. No report-bound TestRun yet. Codex owns execution; GPT-PM required runtime adjudication after actual configuration result. Later tasks not started.


### S2-4D actual guard representation residual; same task - 2026-11-05

Single fresh applyad45ba1 (config-apply-ad45ba1-20261105-01) passed Git snapshot stage, published exact persistent guard pair and reloaded systemd, then refused before create_transaction: literal Conditions string was absent. READONLY guard-diagnostic/guard-dbus-diagnostic-ad45ba1-20261105-01 confirms systemctl Conditions=[unprintable], bothguardfilesroot0644 SHA05e12ed07359a8ec83b161dda0d79ac4f15c27c366e75f1e5beefa9c76fafb37 loaded inDropInPaths; actual nativeD-Bus a(sbbsi) rows are ConditionPathExists,false,true,exactmarkerpath,0. Marker/ledger/Store absent. No blind retry/removal.

Codex completed candidate helper45c6f5c0, applier4368ea4a, collectord24db7bb: bounded typedcondition parser/read-only fixedbusctlquery replaces unprintable-substring checks in normalapply/recovery/bootstrap; exactguard fingerprints retained. Current-turn independent code/security reviews no actionable findings. Designated e2e readonly integration typed-guard-readonly-20261105-01 calls exacthelper on bothrealunits:true,true,exit0,nomutation. Functionalrole owns pending focusedtests/nativehandoff; candidate not committed/pushed yet. Next: finish focused host/native evidence, final boundedGPTreview, exactcandidate commit/normalpush, freshapply. S2-4D stillcurrent; later tasks not begun. Codex owns technicalexecution/coordination; GPT-PM final code/runtime adjudication as applicable.


### S2-4D typed guard delivered; exact prepublished guard retry residual - 2026-11-05

GPT-PM correlated3c1b8c79-fc42-4ac8-bffa-4f8b8f8b0024 approved exact5filetypedguardcandidate and diff1b1f1863,0B/M/minor. Codex committed/pushed11c90281c514465db8b89b90b76b6cd80f1a8111; upstream matched. Requiredhost03:112passed,1POSIXmoduleskip,exit0. Native08:113passed/3testassertionfailures; correctedtargeted09:3passedexit0 separately. Realreadonlytypedhelperbothunits true. Extra mistaken legacycollector35fixtureerrors retained separately, notacceptedPASS; unchangedlegacyinterface outsidetypedguarddelta.

Single fresh config-apply-11c9028-20261105-01 collectedinventoryexit0, thenhostvalidatorrefusedexit2 beforeWSLapply: newrecoveryguards mustbeabsent despiteexactpreviouspublication. Freshinventory showsbothroot0gid0mode0644,size93,SHA05e12ed07359a8ec83b161dda0d79ac4f15c27c366e75f1e5beefa9c76fafb37. No newapplymutation. Existingguardsnotdeleted.

Codex codednarrowvalidatorcandidate cd98cc7e /collectorpin01316a06: onlyaddedguardpairmaybepositivelyabsent OR exactnewfingerprintfrompinnedbundle/layout; other25candidatepreviousfingerprintsstrictunchanged. Functionalrole owns ONLYconfig_inventorytests now; independent code/security reviewrequested. No currentnative/hostbroadrepeatsneeded. Nextfocusedtests,finalGPTsourceapproval,commit/push,freshheld-lifetimeapply. S2-4Dcurrent/open; Codextechnicalowner/GPT-PMreviewowner; S2-4E/S2-5queued.


### S2-4D real configuration installation completed; TestRun pending - 2026-11-05

FinalGPT-PM61b346ba-dc05-4eec-becd-fa07749f17b8/reply64d1757c-ebed-5e66-b995-3687fbb98eef verified exact3candidatehashes and diffced74263,APPROVE0B/M/minor. Designatedinventorytests77passed,exit0. Codex committed/pushed558ed801cdf96dc6f35515fc17e59bbaefe5fec9,upstreammatched; PR#2updated.

Actual single held-lifetime config-apply-558ed80-20261105-01 finishedexit0:27destinations installed/already-exact, daemon-reloadsuccess, runtimeEEselected, tasksource67361bb/tree0c4a844 atomicallyinstalled at/var/lib/vst-runner/repository. ReadonlyGitproof worker997:988 status/diff/untracked/ignoredallclean; fullinventorySHAaa6982802bf0da70010840b1b565c9f6039249e5f53108a120e2e79083419282. Transaction212d76ea69ce4074b53820bd6e859d3c stateACTIVATION_RESTORED, olda600snapshotretained as repository-recovery-a600774649527ff0b33eb81f4d431f8226119b2c-212d76ea69ce4074b53820bd6e859d3c. Lifetimeholderexit0. SourcequalificationHEAD558ed80 remainsdistinct runtimeEE andtask673. Do NOT repeat bootstrapselection/configapply or acceptedsourcechecks.

No report-bound TestRun or serviceactivation claimed; S2-4D stillcurrent/open. E2Erole assigned read-only exact runtime/config/source tuple and replayavailability capture, privatebytesdigestonly; no qualificationlaunch before actualcorrelatedone-shotGPT-PM grant. Codexowns technicalcoordination/evidence; GPT-PM owns required one-shot adjudication. Next: final actualtuplegrantrequest, designatedexistinglauncheroneattempt, reconcile signedreceipt/acceptance; S2-4E/S2-5andlater remainqueued.


### S2-4D actual runtime grant HOLD remediated in qualifier candidate - 2026-11-05

Actual read-only tuple02:39paths present/regular,27applyfingerprints match; runtimearchive3e0bc434, taskcanonical195a471a, configmapae0f3bf9. Host14runtime+2qualificationpins collected; exactlauncherhistoricalglob12files, no errors/configuredidentitymatches. Candidate0bd491d0/canonicaltuple5df5d8f3 remains immutable. Requestac87df4b-4c5b-4a18-8485-29583820a299 returned correlatedHOLD, notgrant: MAJOR01 qualifier policy.source_head(task673) wascomparedto runtimeEE. Apply558andtupleaccepted; qualificationNOT_STARTED, noattemptconsumed. Rawreply savedruntime-hold-ac87df4b. Do NOT rerunapply, createauthorizationfromHOLD, or repeatoldacceptedsourcework.

Codex completed ONLYqualifiercandidate2c020ef8: validateTaskManifestcanonicaldigestbeforebase40hex and bindpolicytoit; runtimeidentityseparate. Actualread-onlyexactunitcommandalso proved positionalshoworderwrong andsocketlacksMainPID; parsernowstrictnamedprops,9unitallowlist,serviceMainPIDrequired/socketoptional,allControlPIDrequired/numeric,zeroPIDprestart. No config/runtime changes. Functionalrole harness110passed,exit0,test58e0754a afterfixture-onlypath/argvfixes; source2c unchanged. Code/securityreviews no actionablefindings. E2EreadonlyASTtargetintegration runtime/configidentityPASS andall9unitsloaded/inactive/dead:serviceMainPID0/socketabsent,allControlPID0; no starts. Managerread nojobs/running; exact5forbiddenStore/socket/issuerpathsabsent.

Final source approval request78fb3eac-8b54-41f1-8b11-d3e26a22c99c pending for2exactfiles/diff30fb0d7b. Next actualdecisionthencommit/normalpush, refreshONLYqualificationHEAD/helperpin innewimmutabletuple, newcorrelatedone-shotgrant, assignedlauncheronce. PreviousHOLDneverupgradedorreused; config39/runtimeEE/task673 proofsretained. S2-4Dcurrent/open; Codextechnicalcoordination/GPT-PMreviewowner; later tasksnotstarted.


### S2-4D one-shot runtime authorization actually granted - 2026-11-05

Actual78fb3eac source verdict APPROVE closedac87MAJOR01, accepted110passingharness andrealreadonlytargetidentity/nineunitproof. Exactsource2c020ef8/test58e0754a committed+pushedas df5f713b38cf0a385285f062c819cd06c0470f37,upstreammatched. Runtime/config/taskinstallation558unchanged. Refreshedimmutablecandidate d770349ccebb3fee6dd659a615db428c794ce1984729c20bca6cdbf088aa4cd7/canonicaleed9b79bfd1a886cfebca67b9c6ab6d16e6fe3e0baa97983f879837b4d43f981 changesonlyqualificationHEAD/helperpin;14runtimepinsand39configpinsunchanged.

Newactualcorrelatedrequest6228a031-6cae-4dbe-b533-0584543832e3 replye5cdb312-fe79-529a-837e-a0c0a5dc30e6 returned VERDICT AUTHORIZE_ONE_SHOT,operationS2-4_OWNER_RUNNER_TESTRUN,retry_cap0,soleassignmentbasisselector. Realjob3cd95e88-1860-465a-a479-84ad1b03f32a,userturnbcd5d7a4-404b-4b17-abab-37004bdff176,payload8887e54ad054b89a57765c78ca2560eb9cc384c0ad6518f4913a8ca410be5fe7 savedrawruntime-grant-6228a031-20261105.json. Thesevaluesaretoolmetadata,notinvented. Ac87HOLDremainsseparate/nonreusable.

Designatedactuale2e-runnerassigned toconstructclosedAUTH_INPUT_V1fromverifiedcandidate+actualmetadataandinvokeexistinglauncheronce withunique6228attemptpath. No launch/result reportedyet; doNOTclaimTestRunPASSorS2Dclosed. Anyactualstartedattemptconsumesgrantincludingunknownoutcome; no blindretry/IDrotation/extra selectors. CurrentqualificationHEADmustremain df5f713untilexecutionfinishes. Codexownscoordination; GPT-PMactualgrantreceived; next step awaitobservedoneattemptresultandreceiptreconciliation. Later tasksnotbegun.


### S2-4D real authorized launcher refused before runtime; no retry - 2026-11-05

Designated e2e-runner verified rawBridgegrant6228metadata and exclusively createdAUTH_INPUT_V1 s2-4d-runtime-authorization-6228a031-20261105.json (8122bytes,SHA14f540e7dbf1617c111c1ff487f9357682eb15f80e36f94140f5b963e66a458f). Exactlyoneexistinglauncher invocation finishedexit2 in0.73s: runtime bundle digest doesnotmatch exactpinnedGitarchive. Outerproof runtime-launch-6228a031-20261105-01.* retained; innerlauncherattemptfileABSENT. No WSLruntime/serviceactivation/TestRun; no retry. Treat6228grant's permittedinvocationasUSED/nonreusable even thoughruntimeattemptneverstarted. Config/runtime/taskinstallationunchanged.

Actualreadonly archive diagnostic df5f713 shows buildercanonicalGit -c core.autocrlf=false -c core.eol=lf yields SHA3e0bc434d04f3374ebf980520042cd1911c189994aa4aaf8040c961155569902 matchinginstalledbundle; inheritedGit yields7d9bbd50df77c3992cfe1fa8202dece6032add033b1a708e736312242b271b9f. Same1331200bytes/47files. Codex also identified itsinputpreparationerror:14minimumrequiredpinsprovided, but existingverifierrequiresfull47archivefilemap; all14exactsubset/33missing. Fullcorrectmapstoredindiagnostic. DoNOTrelax digest/complete-map checks orreuse6228input/grant.

Currentone-source candidate run_s2_runtime_qualification.py BFAD0665... applies same2command-local LFsettingsasbuilder; noWSLhelper/config/manifestchange. Code/securityreviews noactionablefindings; functionalroleowns isolatedrealGitEOL/full-pin regressionharness. E2Eroleassigned READONLY _runtime_identity withfull47pins only (no39config/nineunitrepetition, no launcher). Nextfocusedtests,finalsourceapproval,commit/normalpush,composefull47candidatewithnewqualificationHEAD/outerpin,actualREADONLY verify_source_pins beforeNEWcorrelatedgrantrequest. Oldrun/nonceunusedinruntime; reusewouldrequireexplicitnewgrantafterdeclaredhost-onlyrefusal,noblindretry. S2-4Dcurrent/open; Codextechnicalowner/GPT-PMrequiredreview/grantowner.

### S2-4D deployed-runtime projection and archive canonicalization - 2026-11-05

Current task remains S2-4D; owner Codex. Accepted installed runtime EE/task673/config39 setup is unchanged and is not being repeated. The spent6228 launcher invocation refused on the host before an inner attempt/WSL; no retry occurred, TestRun remains NOT_RUN.

Concrete source delta against df5f713: launcher BFAD0665 uses the same command-local LF Git archive settings as the existing plan builder; qualifier E98F40EC verifies the installer deployed42 source files plus canonical marker against all47 archive pins, excluding only5 fixed installation-only artifacts. Complete archive equality remains mandatory. Codex also corrected its candidate preparation mistake (14 minimum pins was not the required47 complete closure).

Actual functional-test-reviewer froze harness1F591B11: host112passed12skipped exit0, evidence s2-4d-runtime-projection-host-20261105-06.*. Actual e2e-runner executed those12 POSIX-root cases:12passed exit0, evidence s2-4d-runtime-projection-native-20261105-04.*, stdout82f84f1d30c7e2b136d5ead8482f1b4bf594692da604e31ab40260dd9b81671e. Earlier native invocations -01 cwd error/-02 missing fixture O_RDONLY/-03 missing fixture os.sep are retained failures, not accepted evidence. Product BF/E98 unchanged by fixture corrections.

Actual full installed tree read-only proof passed with full47 map, evidence s2-4d-runtime-full-pins-readonly-20261105-04.*. This was worktree-overlay proof, not clean-HEAD qualification or live TestRun. Actual independent code-reviewer and security-reviewer found no actionable B/M in current source delta/direct installer integration. Final GPT-PM source review request877d728c-8401-4e5e-b81b-3004c92ddf32 is pending. Next: receive actual decision, then exact3-file commit/normal push; create fresh47-pin immutable candidate at pushed HEAD, designated e2e read-only verify_source_pins, then request new correlated runtime grant. No old grant reuse; no next task started.

S2-4D continuation: actual GPT-PM877d728c APPROVE exact3 blobs,0BLOCKER/MAJOR. Source commit e42c82ff297902991b9b6e1aa322f44ca08bffb9 normally pushed, HEAD/upstream matched. Existing single sprint PR#2 updated (OPEN DRAFT). Candidate s2-4d-runtime-grant-candidate-e42c82f-20261105.json rawSHAa87d911ba70d1f86c68ff086b080f3bf5ecc42492e63a67434bfde485b7abe3d canonicalSHA012f66714c3899ccf8ff36aa0f5e87e5b0bcc72a324e48158c233855cbafe2ba includes complete47 runtime pins plus2 committed qualification pins. Designated e2e actual source-pin precheck pending before new correlated runtime grant. TestRun NOT_RUN; no next task started.

S2-4D runtime continuation: actual e2e source-pin precheck PASS at pushed e42c82f,47+2 pins (source-pins-precheck-e42c82f-01), historical scan12files0matches0parse-errors (historical-identity-scan-e42c82f-02). New actual correlated GPT-PM grant1c93d05e-13e8-4d34-b94a-81372e7e381e AUTHORIZE_ONE_SHOT operation S2-4_OWNER_RUNNER_TESTRUN retry_cap0 received, raw job s2-4d-runtime-grant-1c93d05e-20261105.json. Designated e2e-runner assigned exactly one existing launcher invocation, sole candidate selector; no retry/reinstall/restricted scenarios. Candidate rawSHAa87d911b; canonical complete candidate including schema012f6671; canonical identity+source_pins onlya14d8f21ff288aaa47a61c6e59ed6525acbc7985f1820606b702fbdac954e9d3. Grant is not execution/result evidence; task remains OPEN pending actual result. No qualification HEAD change.

S2-4D actual1c93 one-shot result: invocation06:42:39.987Z-06:42:45.074Z,exit2HOLD,no timeout. Inner attempt created, SHA4c7e0b2c49f48970065147145da10a82b0319bbda134237fd6bb31666c74d889, source_pins_verified=true,stages empty, only current_transient_unit observationcommand. Stop before selector/components: unexpected numeric/dev/pts0,1. This identity and authorization are consumed; no retry occurred. Report-bound TestRun NOT_RUN. Independent architect recommended tightening profile by masking/dev/pts; current narrow2source-file correction adds exact mask+empty rootmode000 verification and exact measured underlying devpts contract, no numericdevice allowlist. Current outerSHAea3de649263406fb2b622cff467f726b9b148ec1f7763c665d21ad993f756dcf, helperSHAa60e8e61a7828934bcdbebb592d2a4b470ccf5a2ac27d8a6b343f6f4b59ff243. Functional-test-reviewer owns focused tests now; final reviews follow. No runtime/config reinstallation or next task.

### S2-4D mask proof and distinct fresh binding - 2026-11-05

Actual GPT-PM3155384f APPROVE exact3 source/test files and separately AUTHORIZE_MOUNT_AUDIT_ONCE. Commit b02377168d8f511fc5d0d4a15f79ee020126ad5d normally pushed. Actual designated e2e mount-only diagnostic ran once, exit0PASS,4.28s,no stderr; evidence s2-4d-ptsmask-native-audit-b023771-20261105-01.*, raw stdoutSHA9be8bfa57f4e85cc26a6add6c0ca3e651ab86bc4d70bf721e40459ddf90776d6.44mountrows,0rejects/Windowsrows/isolationfailures; effectivepts rootmode000 inaccessible-dir overlay, no children;0runtime selector invocations/VST starts/persistent changes/attemptcreates. No repeated diagnostic.

Actual existing collector capture before that commit at e42: s2-4d-consumed-binding-current-inventory-e42c82f-20261105-01.*, stdoutSHA10f17b89bd56ab1bbd584b63e0f362fe4f925a568717ab3a63c9308e9ed90365.9inactive units/27present configs/Storeabsent/EEselector. Current accepted bundle8f487494/layoutf46e977 match both Git blobs and worktree bytes; an explorer's contrary PowerShell-derived claim was explicitly disproven and retracted. Do not reopen accepted config provenance.

Current same task S2-4D; owner Codex. Fresh binding prepared in8 scoped source/data files, not installed: run s2-runtime-20261105-cbd53635c3eb47bfbf7a7e594399cdd7; bootstrap f4adc20007b44d6b8a4580ef6a2d1ed4; nonce cd7f47554f384611a89328af6d1d87e0. Existing private-material paths/layout/keys/runtime/task673 unchanged. BundleSHA4c13f2991f39cf12b84af4b0440621ab1adaa74ca1894dfda29eec1006cd7138. Validator previous exact27 baseline e42 includes both installedguards, rejects any missing/tampered destination or changed destination set; olde520 identity retained in history and consumedIDs now1c93 tuple. Frozen applierc563417271bb5e6a5c2e10cbb129713c22ec3fd0e8c54d541a72aba63ff8c3b4; validator91f16810ac283b07ae047461ff27abd5780bd01e2eba126048504ace329503d8; collectora9471920497a963772d7474896c2624865113d9ba4e9cb86f58819bb4abac359. Functional-test-reviewer assigned focused bundle/inventory test authoring/execution after source complete. Next: test results, actual relevant internal reviewers, final GPT source review, exact commit/push; then fresh current inventory/dry-payload and bounded existing apply, new full47 candidate/grant/one runtime journey. Old1c93 identities/grant remain consumed. TaskOPEN/TestRunNOT_RUN; nexttask not started.

S2-4D fresh-binding final test/review update: exact THREE installed byte changes bootstrap/network-profile/supervisor (not two; corrected Codex inference). Functional tests caught removed upfront guard source/member validation; fixed for ALL27 candidate source paths/size/hashes, meaningful tests retained. Frozen validatorc334c6cdcf2677c8f3d87f52c74951d61717e64f7dbe0f77cc0541cc32f5d135; collector39f07005985eace76cfe99ab9ac764402122598051e3240336e65fd342960971; applierc563417271bb5e6a5c2e10cbb129713c22ec3fd0e8c54d541a72aba63ff8c3b4; candidatebundle4c13f2991f39cf12b84af4b0440621ab1adaa74ca1894dfda29eec1006cd7138. Actual functional final command python -m pytest -q --tb=line tests/vst/test_s2_runtime_config_bundle.py tests/vst/test_s2_runtime_config_inventory.py:102passed exit0, stdout9ff2b8da0a25183d5d5d4506b41869f31b9635fcf5698f9d999952b22639ff2a, evidence s2-4d-fresh-binding-host-20261105-04.*. TestSHA2733102b0deda21d73fe3500525e1cb45f503775a64953d424ec925bfeb451de and497df55b1cebfefe234c2cda1741a62ead2edaebbddbc34bff156f94f418bef3. Host03 without restored2 cases is not final evidence. Actual independent code/security reviewers clear, no B/M.

Final GPT-PM request d18c5007-6319-4d70-b183-e71db9205aa3 pending for exact10-file source/data/test delta vs b023 plus separate bounded existing configrefresh afterpush/freshinventory/drypayload (existing same-head673 snapshot transaction may occur; not mislabelled no-op). First send refused beforequeue on unchanged secret-rejection marker literals in full test bundle file. Corrected safe send accepted: nine full files, omitted test file represented explicitly by exact11-line diff+baseline/currentSHA, no source redaction/edit or fabricated evidence. Packet docs/sdlc/.pm-review/s2-4d-fresh-binding-final-20261105-hashes-v2.json; full deltaSHAbe8b8ac4f59447e6edc7a177f0749f5e04e81d457c1a87401cd278f86ad2b94e. Do not resend while pending. Next: actual verdict, exact10-file commit+normalpush, freshcurrent inventory and drypayload then boundedapply, actualtuple/sourcepins/history then newruntimegrant. S2-4D remainsOPEN; task/sprint not advanced.

S2-4D fresh-binding source DELTA APPROVED actual GPTd18c5007 (0B/M) plus AUTHORIZE_BOUNDED_CONFIG_REFRESH. Exact10 filehashes verified beforestage/inindex; source08 fullSHA condition satisfied, no redactions. Commit4fe846fc1c3172f02a4fe915936ecc9c249ac61d normally pushed; existing singlePR#2 updated. OwnerCodex assigned e2e existing keeper+freshcollector+pure build_payload dryverification before ONE applier invocation under samekeeper, then prescribed postcapture andkeeperrelease. Abort any source/HEAD/fingerprint/destination/identity/unsafe service mismatch, no blindretry. Exact27 destinations/3 contentchanges, samehead673 transaction permitted with retention/fencing/journal/restoration; no runtime reinstall/keygen/Storedeletion/TestRun. Fresh grant f0c83b02 was consumed by one keeper start, but the PowerShell stream-read error stopped execution before collector/applier: fresh inventory, dry payload and post-inventory NOT_RUN; applier invocations 0; target mutation NOT_RUN. Approved stdin sentinel did not close the WSL command within 30s; later read-only snapshots still showed WSL PIDs 42016/20620/15892 and Ubuntu-24.04 Running, with original parent PID 38760 absent. Whether keeper Python remains alive is UNKNOWN; no kill or distro termination attempted. Do not retry under this grant (retry_cap=0), start another keeper, or advance task. Terminal reconciliation: docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-03.terminal-reconciliation.json. Next: Codex confirms old process tree terminal through non-mutating evidence; then request a fresh GPT-PM one-shot grant before any new keeper. TestRun remains NOT_RUN; no later task started. Raw approval s2-4d-fresh-binding-source-review-d18c5007-20261105.json. Do not move qualificationHEAD during this flow.

S2-4D recovery update 2026-11-05: read-only Win32 snapshot 2026-11-05T15:24:58.7446692Z confirms original PID 38760 absent but WSL PIDs 42016 (created 17:15:11.33617+02:00), 20620 (17:15:11.588986+02:00), 15892 (17:15:20.51393+02:00) and console descendants 40072/25072 remain. Ubuntu WSL command/keeper lifecycle is unresolved; no collector identity or termination evidence. Corrected wrapper plan: docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-04.process-snapshot-wrapper-plan.json. GPT-PM request 9bd01af3-d739-4f57-8925-d3c45f872ca2, reply 6ed68170-fea5-5bf5-ba4c-ce6b50132437: HOLD; original grant consumed; no new grant. Do not retry/start keeper/run collector or applier/kill/terminate WSL. Owner Codex: continue read-only process reconciliation; after all bound PIDs and descendants exit with identity evidence, submit the snapshot and corrected wrapper plan for a fresh independent grant. Task remains OPEN; TestRun NOT_RUN; applier calls 0.

S2-4D follow-up snapshot 2026-11-05T15:27:33.4523435Z: same decision-bound WSL process tree remained present (PIDs 42016/20620/15892; descendants 40072/25072), exact creation times recorded in docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-05.process-snapshot.json. Parent 38760 absent; WSL keeper and Linux collector identities UNKNOWN. This does not satisfy GPT-PM termination condition. No runtime operation, kill, or WSL termination; task remains OPEN.

S2-4D closure 2026-11-05T15:29:46.4555893Z: CLOSED AS-IS BY OPERATOR — NOT DELIVERED; acceptance remains NOT_SATISFIED. Fresh inventory/dry payload/post-inventory NOT_RUN; applier=0; target mutation NOT_RUN; TestRun NOT_RUN. GPT-PM 9bd01af3/6ed68170 held the task pending process lifecycle; no retry or process termination. Durable closure: docs/sdlc/evidence/s2-4d-bounded-config-refresh-operator-closure-20261105.json. No further S2-4D execution under this disposition.

S2-4D reopened 2026-11-05T15:32:30.6709222Z: operator asked to continue after the prior CLOSED_AS_IS_BY_OPERATOR_NOT_DELIVERED disposition. Acceptance remains NOT_SATISFIED. Read-only snapshot 2026-11-05T15:31:48.8367729Z still shows PIDs 42016/20620/15892 and descendants 40072/25072; keeper Python identity UNKNOWN. Prior grant consumed; no collector/applier/TestRun, process kill, or WSL termination. Snapshot: docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-06.reopened-process-snapshot.json. Await separate cleanup adjudication; no new keeper.

S2-4D PM-authorized read-only cleanup snapshot 2026-11-05T15:35:04.1239468Z: command exited 0; all five original PIDs 42016/20620/15892/40072/25072 remain, with matching creation times and command lines. Raw evidence: docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-07.cleanup-snapshot.txt, SHA256 8FABA416652922BA80C033D421745432E44FF4783C2919E643D1B49ED88073E2. GPT-PM cleanup request d427d120-31bb-4cff-bd82-185038a7e88a returned HOLD — NO PROCESS ACTION AUTHORIZED. Old grant consumed; no new grant; no keeper/collector/applier/TestRun. Task reopened by operator but remains OPEN / NOT_DELIVERED; no process kill or WSL shutdown.

S2-4D follow-up read-only snapshot 2026-11-05T15:45:36.3401551Z: exact GPT-PM Windows-only process query exited 0; PIDs 42016, 20620, 15892, 40072, 25072 all remain with matching creation times. Raw command/output: docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-08.cleanup-snapshot.txt; SHA256 5C114189A94BBDA23091C489BD7E552C1221BEE07B81B7CE9A4521734103EB67. GPT-PM cleanup adjudication d427d120-31bb-4cff-bd82-185038a7e88a: HOLD, no process action authorized, old grant consumed; only read-only observation until these exact process instances exit. Task remains OPEN / NOT_DELIVERED.

S2-4D follow-up PM-authorized read-only snapshot 2026-11-05T15:56:05.8525764Z: command exited 0; all five bound PIDs 42016/20620/15892/40072/25072 remain with original creation times. Raw evidence docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-09.cleanup-snapshot.txt SHA256 A2BFC40FD7CD12BA586A28322CBEA0BFE7848E475D9ABB010C054D4BCD49C1EB. Grant remains consumed; GPT-PM d427d120/cleanup reply authorized read-only observation only. S2-4D OPEN / NOT_DELIVERED; runtime steps remain NOT_RUN.

S2-4D follow-up read-only snapshot 2026-11-05T16:06:19.3394806Z: exact authorized query exited 0; PIDs 42016/20620/15892/40072/25072 remain with original creation times. Evidence docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-10.cleanup-snapshot.txt SHA256 AE2655D57586BB5A77C6776154FE38F9B0C05181164320294849EB6FDB39C234. No new runtime, collector, payload, applier, TestRun, process signal, kill, or WSL shutdown. S2-4D remains OPEN / NOT_DELIVERED; only authorized next action is read-only observation after future interval until all five process instances exit.

S2-4D follow-up read-only snapshot 2026-11-05T16:17:36.7090702Z: exact authorized query exited 0; all five original WSL/conhost PIDs 42016/20620/15892/40072/25072 remain with matching creation times. Evidence docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-11.cleanup-snapshot.txt SHA256 2E9DBB6EC6CCD0A8E6EDF8B5C645CDA7FD0B4EE71607B9B49C54C5453DC50A4F. No runtime/collector/payload/applier/TestRun or process action; task remains OPEN / NOT_DELIVERED.

S2-4D follow-up read-only snapshot 2026-11-05T16:27:46.5043213Z: exact authorized query exited 0; original PIDs 42016/20620/15892 and descendants 40072/25072 remain with same creation times. Evidence docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-12.cleanup-snapshot.txt SHA256 5A054E2E178A9B43185BD0DE9790863A0ECC67068C29A04EF1E8391ED473CB50. No runtime, collector, payload, applier, TestRun, process signal, kill, or WSL shutdown. Task remains OPEN / NOT_DELIVERED.

S2-4D follow-up read-only snapshot 2026-11-05T16:38:00.4296565Z: exact authorized query exited 0; PIDs 42016/20620/15892/40072/25072 remain with original creation times. Evidence docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-13.cleanup-snapshot.txt SHA256 36F0287B09E079EB1B45127B551FB7679E222A4EDE56A7AB290F071D3CF2BBA9. No new runtime, collector, payload, applier, TestRun or process action. S2-4D remains OPEN / NOT_DELIVERED.

S2-4D follow-up read-only snapshot 2026-11-05T16:48:56.9991796Z: exact authorized query exited 0; PIDs 42016/20620/15892/40072/25072 remain with original creation times. Evidence docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-14.cleanup-snapshot.txt SHA256 B3F1DAE080A187A23693945B0A9838060958A14A85D43F46B6E93E65D8C03E3B. No new runtime, collector, payload, applier, TestRun, or process action. S2-4D remains OPEN / NOT_DELIVERED.

S2-4D follow-up read-only snapshot 2026-11-05T16:59:09.7216513Z: exact authorized query exited 0; all five process IDs 42016/20620/15892/40072/25072 remain with original creation times. Evidence docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-15.cleanup-snapshot.txt SHA256 FC6080BD27FBCA72EADEB8DC1DAA32F571491D221E5A5267793EFE17F946C9F3. No runtime, collector, payload, applier, TestRun, or process action. S2-4D remains OPEN / NOT_DELIVERED.

S2-4D follow-up read-only snapshot 2026-11-05T17:11:15.5107437Z: exact authorized query exited 0; original PIDs 42016/20620/15892 and descendants 40072/25072 remain with original creation times. Evidence docs/sdlc/evidence/s2-4d-bounded-config-refresh-f0c83b02-f043-4f09-8ea4-cdc8e608b6a0-16.cleanup-snapshot.txt SHA256 33BC2CCE148265122564AC45BD6F65CB841BBD2212DE4AE8864578192206C77C. No runtime, collector, payload, applier, TestRun, or process action. S2-4D remains OPEN / NOT_DELIVERED.
