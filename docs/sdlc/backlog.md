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
| 2 | S2-4 exact runtime inputs — DELIVERED `473e559` | Source compatibility fix a600774 is pushed; actual strict stage-only publication succeeded. Bundle32 artifacts, nine unit bindings and three rate-limit overrides are pinned to actual source/helper/task/policy/run identities. False local GPT-PM credential labeling was corrected; review and test evidence is retained in change0595. | Codex: delivered change0595 in473e559; normal push output `9021b98..473e559` succeeded. Focused9-case suite and actual UID999 command/parser passed; local registry HMAC valid/tamper checks passed. Continue only item3. Existing delegation is carried forward; no generic permission is pending. |
| 3 | S2-4 current E5 and real owner-to-Runner evidence — IN PROGRESS | Current code/test correction `ee69f9f` and evidence commit `c8df57d` are pushed. GPT-PM approved the post-stage manifest consistency only: request `5ed4b8d8-1c5f-4e45-9e92-cb14df136fe7`, correlated reply `315cc40b-9e06-5641-88fc-4ab2ecdd93de`, 0 B/M. Manifest SHA-256 `fafaf93158fee300f1b62ea53e8712e8c600b89a7d0b350399de62989cddcc52`; current and previous runtime tree hashes were subsequently recalculated read-only and match. StageOnly publication is accepted; selector remains on `80c2b81`, nine units inactive, no jobs, Store absent. Focused source-extracted PowerShell parser probes passed; required pytest is `NOT_RUN` under the test role restriction. Current run-bound E5, permitted Owner-to-Runner, and report-bound TestRun remain `NOT_RUN`; S2-4 is not delivered. Detailed review and tree evidence: `evidence/s2-4-post-stage-manifest-review-5ed4b8d8.md`, `evidence/s2-4-post-stage-content-verification-ee69f9f-20261030.json`. | Codex: prepare the next exact runtime-qualification candidate bound to current source/target identities and request a separate one-shot adjudication; StageOnly approval cannot be reused. `e2e-runner`: run only the separately authorized bounded qualification. Keep S2-5 queued. |
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
| S2-4 | IN PROGRESS — runtime/E5 evidence remains | Diagnostic refusal fix is delivered and pushed in `055e913`. Fresh non-secret candidate run `s2-runtime-20261030-1977eaba61274396b6b58d069c5cede2`, request `98b38065170f468c9943aa8f22160ff9`, nonce `a2a0dcab58b9451281ff0a7b079d4aa2`, bundle SHA `05530c73…10f91f`. GPT-PM request `bbf54c64-e270-4ba6-b195-5af764fa3f07` returned MODIFY/MAJOR-01 because expected predecessor `069be3b` / tuple `212a…/334296…/b575…` differed from applied state in attempt `3a3a0e67` (`7d1d16f`, bundle `388e6bb…`, tuple `e520…/2b5e…/0aac…`). Codex corrected the predecessor pin and retained the older tuple for replay denial. Pushed `aedf712c07eb0cc531852d18443faa497e19bb2d` retains earlier exact-head evidence of 70 passed. Latest supplemental safe suite by `functional-test-reviewer`: 133 passed, 60 skipped, 8 deselected, 1 warning on the same HEAD plus uncommitted candidate changes; not clean exact-commit evidence. Exact command/provenance and full output are linked above. GPT-PM re-review ACCEPTED MAJOR-01, no direct blocker (request `24c2372b-5cf8-4144-a690-d22a65db90e0`, job `86b484fa-5597-4cc2-bfbb-225c8560e2db`, reply `e8448c22-a258-51a4-af4c-fed00e545f51`, correlated). The correction is committed and pushed; exact-head tests pass. Fresh runtime remains NOT_RUN; prior one-shot authorization `8ee40d1a` is consumed. | Next: Codex requests fresh correlated one-shot runtime authorization bound to the pushed code and current candidate identities; `e2e-runner` executes only the approved bounded scope. S2-5 remains queued. |
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

The parser source fix `ee69f9f` was reviewed and pushed; source-derived bounded PowerShell probes passed, while pytest remains `NOT_RUN` under the functional-test-reviewer role restriction. GPT-PM request `9174fd39-c2d4-4bd0-93ed-3e41243cdfd2` authorized one exact StageOnly invocation. It exited 0 and published the immutable runtime and helper without selection or unit installation. The read-only post-state confirms the previous `80c2b81` selector remains selected, all nine units are inactive/dead, there are no systemd jobs, and Store is absent.

GPT-PM then approved post-stage manifest identity/consistency only under request `5ed4b8d8-1c5f-4e45-9e92-cb14df136fe7`, correlated reply `315cc40b-9e06-5641-88fc-4ab2ecdd93de` (0 BLOCKER, 0 MAJOR). A read-only post-review check matched all 47 runtime source-map entries and recalculated both current and previous runtime tree hashes to the manifest. Full details are in `evidence/s2-4-post-stage-manifest-review-5ed4b8d8.md` and `evidence/s2-4-post-stage-content-verification-ee69f9f-20261030.json`.

This closes only S2-4 StageOnly publication and artifact consistency. Current run-bound E5, a permitted real Owner-to-Runner result, and report-bound TestRun remain `NOT_RUN`; no subsequent runtime operation is authorized by either review. Owner: Codex. Next: prepare a fresh exact runtime-qualification candidate bound to current source and target identities and obtain its separate one-shot adjudication; then `e2e-runner` executes only that bounded authorization. S2-4 remains **IN PROGRESS**; S2-5 remains queued; S3 stays unstarted.

### Focused test maintenance note

Historical item, resolved in change0551: Codex reconciled the exploratory selector `test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor` in `tests/vst/test_s2_persistent_runner_service.py`. It assumes a Store with `PRAGMA user_version == 5`, while both baseline `9c1be0f` and current source declare schema version 6. The selector is outside TP-26/27 acceptance and was excluded from the final focused assignment-basis run; do not silently change its historical fixture or count its failure against the accepted S2 candidate tests. Resolution: the designated functional-test reviewer restored a true schema-v5 fixture and reported six passing cases over two selectors; see `evidence/s2-legacy-v5-fixture-run-20261029.md`. Include its permitted regression only after the final S2 code freeze.

## Required evidence references

- Requirements and current limitation register: `docs/sdlc/requirements.md`.
- Current S2 coordinator/runtime adjudication and correlated decisions: `core/STATE.md`, “Current S2 coordinator/runtime adjudication — 2026-10-29”; `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`.
- S2 source/test backlog and M03 source/test closure: `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”; `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
- Transport test details and limits: `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md`.

