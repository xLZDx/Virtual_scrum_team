---
project: Virtual_scrum_team
as_of: 2026-11-07
active_sprint: S3
scope: single_sprint
approved_sprints: S2, S3
operator_approved: true
---
# Virtual_scrum_team - project plan

Sources: docs/sdlc/backlog.md (ordered S2 queue), docs/sdlc/acceptance.md (current bounded S2 disposition), docs/sdlc/AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md (sprint names), core/STATE.md, core/DECISION_LOG.md, docs/sdlc/S1_RETROSPECTIVE.md, Git history on branch s2-canonical-continuation (code candidate 96a8da7).

## Roadmap
| Sprint | Title | Status | Goal |
|---|---|---|---|
| S0 | Inventory and baseline | ACCEPTED | S0 inventory documents (docs/sdlc/s0/); approved by GPT-PM and merged with S1 (PR #1, merge d5cd7f5). |
| S1 | Control-plane core | ACCEPTED | State store, contracts, signing, gate and runner in tools/vst; approved and merged (PR #1, d5cd7f5, closure c5a8eb1). |
| S2 | Isolated worker sandbox | ACCEPTED (merged) | All S2 tasks are accepted. The bounded source/test scope (S2-1..S2-5) and the real Windows-local Owner-to-Runner process E2E (S2-4E, run 4 green) are merged into main with PR #2 (7c94c6c). Current E5 and production qualification remain NOT_RUN; do not report production readiness. |
| S3 | Worker pilot | IN_PROGRESS — S2 merged (PR #2, 7c94c6c); the operator ordered S3 to be finished (2026-11-07) | Single isolated story adapter on the S2 sandbox; compare BMad Loop, hand-written loop and a durable engine on one crash/resume fixture; vendor-neutral worker interface. Existing PR #3 predates this work; it is not evidence that S3 has started or that S2 is closed. |
| S4 | QA automation | PARTIAL — evidence exists on local unpushed branches; not on main, not accepted | Real native runners for functional, integration, API, E2E, regression and seeded failures with reproducible artifacts; a skipped test never satisfies DoD. |
| S5 | AEVE gate | NOT_STARTED — prepared only; no AEVE source or analyzer is available | Bounded static review with hashes and an independent evidence/coverage receipt; truthful analyzer status; stale HEAD fails. |

## Sprint S0 - Inventory and baseline
Goal: Ground-truth inventory of profiles, repositories and tool capabilities (docs/sdlc/s0/); approved by GPT-PM on head abc0d50 and merged with S1 (PR #1, merge d5cd7f5).

| Task | Title | Acceptance | Status | Evidence | Owner | Depends | Commit |
|---|---|---|---|---|---|---|---|
| S0-1 | Profile resolution | Inventory document docs/sdlc/s0/PROFILE_RESOLUTION.md recorded from ground truth | ACCEPTED | GPT-PM request 50828a0d-f780-405b-b49c-30de58c5bd52 approved head abc0d50 (no new BLOCKER/MAJOR); record 0028. Not verified in S0: remote repository state, sonnet alias binding, gh authentication. | Codex | - | d5cd7f5 |
| S0-2 | Repository registry | Inventory document docs/sdlc/s0/REPO_REGISTRY.md recorded from ground truth | ACCEPTED | GPT-PM request 50828a0d-f780-405b-b49c-30de58c5bd52 approved head abc0d50 (no new BLOCKER/MAJOR); record 0028. Not verified in S0: remote repository state, sonnet alias binding, gh authentication. | Codex | - | d5cd7f5 |
| S0-3 | Tools capability matrix | Inventory document docs/sdlc/s0/TOOLS_CAPABILITY_MATRIX.md recorded from ground truth | ACCEPTED | GPT-PM request 50828a0d-f780-405b-b49c-30de58c5bd52 approved head abc0d50 (no new BLOCKER/MAJOR); record 0028. Not verified in S0: remote repository state, sonnet alias binding, gh authentication. | Codex | - | d5cd7f5 |

## Sprint S1 - Control-plane core
Goal: State store, contracts, signing, gate and runner in tools/vst (design baseline BD-1..BD-7); approved by GPT-PM on head abc0d50 and merged (PR #1, d5cd7f5, closure c5a8eb1).

| Task | Title | Acceptance | Status | Evidence | Owner | Depends | Commit |
|---|---|---|---|---|---|---|---|
| S1-E1 | Contracts | JSON schemas and strict validator for TaskManifest, four receipt types and GateDecision; closed enums, no defaults | ACCEPTED | Four independent review rounds (12 of 14 reviewer runs MODIFY, all MAJOR findings fixed); GPT-PM APPROVE at abc0d50. Tests (E1-E3 1193, E4 289, E5 72 passed, 2 skipped) ran on the working tree, not re-run on the exact head; mutation checks NOT_RUN. See docs/sdlc/S1_RETROSPECTIVE.md. | Codex | - | d5cd7f5 |
| S1-E2 | Gate | Pure verdict function per BD-4; stale head, missing receipt and unlisted FAIL give non-approval | ACCEPTED | Four independent review rounds (12 of 14 reviewer runs MODIFY, all MAJOR findings fixed); GPT-PM APPROVE at abc0d50. Tests (E1-E3 1193, E4 289, E5 72 passed, 2 skipped) ran on the working tree, not re-run on the exact head; mutation checks NOT_RUN. See docs/sdlc/S1_RETROSPECTIVE.md. | Codex | S1-E1 | d5cd7f5 |
| S1-E3 | State store | SQLite store: epoch compare-and-swap, attempts, lease/slot tables, hash-chained receipts and event log | ACCEPTED | Four independent review rounds (12 of 14 reviewer runs MODIFY, all MAJOR findings fixed); GPT-PM APPROVE at abc0d50. Tests (E1-E3 1193, E4 289, E5 72 passed, 2 skipped) ran on the working tree, not re-run on the exact head; mutation checks NOT_RUN. See docs/sdlc/S1_RETROSPECTIVE.md. | Codex | S1-E1 | d5cd7f5 |
| S1-E4 | Runner and signing | Runner records argv, exit codes and artifact hashes and signs receipts with a key outside the worker directory | ACCEPTED | Four independent review rounds (12 of 14 reviewer runs MODIFY, all MAJOR findings fixed); GPT-PM APPROVE at abc0d50. Tests (E1-E3 1193, E4 289, E5 72 passed, 2 skipped) ran on the working tree, not re-run on the exact head; mutation checks NOT_RUN. See docs/sdlc/S1_RETROSPECTIVE.md. | Codex | S1-E1 | d5cd7f5 |
| S1-E5 | Vertical slice harness | Synthetic story through supervisor, worker stub, runner and gate with worker death, zombie write, stale head and retry after FAIL | ACCEPTED | Four independent review rounds (12 of 14 reviewer runs MODIFY, all MAJOR findings fixed); GPT-PM APPROVE at abc0d50. Tests (E1-E3 1193, E4 289, E5 72 passed, 2 skipped) ran on the working tree, not re-run on the exact head; mutation checks NOT_RUN. See docs/sdlc/S1_RETROSPECTIVE.md. | Codex | S1-E1 | d5cd7f5 |
| S1-E6 | Process alignment | Orchestrator skill and DoD match BD-1; change record, logs and document registry regenerated | ACCEPTED | Four independent review rounds (12 of 14 reviewer runs MODIFY, all MAJOR findings fixed); GPT-PM APPROVE at abc0d50. Tests (E1-E3 1193, E4 289, E5 72 passed, 2 skipped) ran on the working tree, not re-run on the exact head; mutation checks NOT_RUN. See docs/sdlc/S1_RETROSPECTIVE.md. | Codex | S1-E1 | d5cd7f5 |

## Sprint S2 - Isolated worker sandbox
Goal: Qualify the existing Store-authorized signed dispatch path (DispatchOwnerService, Supervisor/Store admission, StoreBackedDispatcher) through the real Runner boundary; S3 does not start before S2 closes. Task rows follow the S2 stories and S2-4 subtasks in docs/sdlc/backlog.md.

| Task | Title | Acceptance | Status | Evidence | Owner | Depends | Commit |
|---|---|---|---|---|---|---|---|
| S2-1 | Fail-closed signed instruction, Store admission and recovery | Invalid or replayed instructions rejected before durable intent; source/test acceptance only (REQ-001, REQ-002, REQ-004) | ACCEPTED | GPT-PM request f92b750e accepted bounded scope; M03 130/130, adapter 38/38 (inherited reports); backlog "Delivered" | Codex | | e332ec4 |
| S2-2 | Authenticated owner transport to Store-backed dispatcher | Transport forwards only, fails closed on malformed input; 34 passed WSL (REQ-002, REQ-003) | ACCEPTED | GPT-PM request b0f60d46 accepted source/test scope; peer creds, pidfd and fs metadata still mocked; change 0588 | Codex | S2-1 | e987a24 |
| S2-3 | Immutable non-secret runtime bundle and bounded WSL stage-only preparation | Exact reviewed bundle published stage-only, selected=false (REQ-004, REQ-005, REQ-006) | ACCEPTED | GPT-PM request ac2d25a2 approved post-stage manifest; TP-10 refusal matrix remains PARTIAL | Codex | S2-2 | ae07f87 |
| S2-4A | Instruction issuer (root V1) and V2 verifier source/test | Issuer code and tests approved for exact bytes | ACCEPTED | GPT-PM request 8fc2e0ba approved c978360; V2 verifier approved aa349632, ledger e09c78b | Codex | S2-3 | e09c78b |
| S2-4B | Runtime preparation steps 4.1-4.12a (probe-signature removal, root capture, StageOnly, selector, config applier and install) | Each step delivered with focused tests and pushed; no live Runner evidence claimed | ACCEPTED | Backlog "Delivered" records and change records 0597-0609; 4.12a GPT-PM request 69174c68 approved 19338ba; focused suites reported by functional-test-reviewer, not rerun here | Codex | S2-4A | 19338ba |
| S2-4C | Runtime qualification hardening 4.12b (worker identity settling, mount audit, inventory binding) | Exact code/test bytes approved; fail-closed mismatch evidence retained | ACCEPTED | GPT-PM decision S2-4-PM08-CODE-REVIEW-20261101-29 approved exact bytes pushed as 67361bb; e2e-runner 3+32+6 passed at base 470de537 plus worktree delta; no clean post-commit rerun | Codex | S2-4B | 67361bb |
| S2-4D | REQ-003 source/test acceptance for stored owner-to-Runner handoff | Exact assignment-basis selector and focused bundle contract coverage; inspect the retained `tools/vst` product path. Retired WSL QA harness and Git-source checks are excluded from active scope. | ACCEPTED | Bounded source/test acceptance. Windows selector 1 passed; bundle contract module 11 passed; internal code review found no BLOCKER/MAJOR; GPT-PM request `a2c98c0f` / reply `f981ea40` approved exact candidate `96a8da7` with 0 BLOCKER/MAJOR. | Codex; GPT-PM supplied final code review | S2-4C | 96a8da7 |
| S2-4E | Windows-local Owner→Runner functional path | Before S3 Worker pilot, a real Windows-local journey forwards an already-signed Owner instruction through Supervisor/Store admission and Store-backed Dispatcher to the Runner; the Runner executes only the Store-authorized one-use grant under Windows Job Object containment and returns a bound receipt. Functional and process E2E evidence must come from the assigned test agents. This does not require E5, production credentials, WSL, or a VPS and does not claim production readiness. | ACCEPTED | Real Windows process E2E passed on 2026-11-07 (run 4, `LAST_TASK_RESULT=0`, `docs/sdlc/evidence/s2-4e-e2e-run-20261107-4.out`); GPT-PM round 7 APPROVE (0 B/M) for `34e934d..8fa7399`. Merged into main with the single S2 PR (#2, 7c94c6c). | Codex | S2-4D |  57c22d3 |
| S2-5 | Final S2 bounded code review, exact-head approval and acceptance | Record the bounded source/test disposition after internal review, mapped tests, exact-head GPT-PM decision and successful push; keep runtime/E5 separate. | ACCEPTED | Bounded source/test acceptance. GPT-PM request `a2c98c0f` / correlated reply `f981ea40` approved exact candidate `96a8da7`; commit is present on `origin/s2-canonical-continuation`. Full matrix: `docs/sdlc/acceptance.md`. | Codex; GPT-PM supplied final code review | S2-4D | 96a8da7 |

## Sprint S3 - Worker pilot
Goal: Single isolated story adapter on the S2 sandbox; compare BMad Loop, a hand-written loop and a durable engine on one crash/resume fixture (docs/S3_WORKER_PILOT_PLAN_2026-10-24.md).

| Task | Title | Acceptance | Status | Evidence | Owner | Depends | Commit |
|---|---|---|---|---|---|---|---|
| S3-A | Vendor-neutral single-story adapter and idempotent operations (VST-027) | Adapter contract and one synthetic story | PARTIAL | Adapter contract and synthetic pilot integrated onto main (c0f7c17 on branch s3-worker-pilot); registry VST-027: GPT-PM APPROVE at an older head, focused modules passed 9/9 there. Focused tests on the current base are running by the test agents; no push yet. | Operator accountable; Codex implements | previous sprint close |  |
| S3-B | Candidate identity, immutable revision, license and compatibility audits (VST-028) | Candidate audited before any execution | PARTIAL | Registry VST-028: read-only audit APPROVED, Temporal chosen PROVISIONALLY as the sole durable-engine comparator (server af08a5e); acquisition NOT APPROVED by the operator. BMad Loop audit NOT_VERIFIED. | Operator accountable; Codex implements | previous sprint close |  |
| S3-C | Shared crash/resume, STOP, retry and budget fixture (VST-029) | Deterministic fixture run by the test agents | PARTIAL | Registry VST-029: local synthetic selectors passed (9 adapter + 9 pilot at 7816aeb on an older base); process-kill, mutation, external-candidate and sandbox selectors NOT_RUN. | Operator accountable; Codex implements | previous sprint close |  |
| S3-D | Sandbox-bound worktree, credentials, diff and egress proof (VST-030) | Proof inside the S2 sandbox | BLOCKED_OPERATOR | Registry VST-030: needs a fresh run-bound signed probe in an operator-provisioned sandbox; the sandbox choice (dedicated WSL2 vs Windows-local) is an operator decision and WSL work is out of scope now. | Operator accountable; Codex implements | previous sprint close |  |
| S3-E | Candidate comparison, residual risk and operator choice (VST-031) | Comparison recorded; operator decides | BLOCKED_OPERATOR | Registry VST-031: static comparison recorded; the final worker choice belongs to the operator and needs a common runtime denominator from S3-D. | Operator accountable; Codex implements | previous sprint close |  |

## Sprint S4 - QA automation
Goal: Real native test runners with reproducible artifacts; a skipped test never satisfies DoD (docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md).

| Task | Title | Acceptance | Status | Evidence | Owner | Depends | Commit |
|---|---|---|---|---|---|---|---|
| S4-A | Category manifest, test-ID registry and denominator (VST-032) | Registry and denominator | PARTIAL | Registry VST-032: registry head 3885d8a, 963 selectors. The code lives on local, unpushed branches (s4-*), not on main; not accepted. | Operator accountable; Codex implements | previous sprint close |  |
| S4-B | Pinned test environment and bounded native runner (VST-033) | Reproducible runner | PARTIAL | Registry VST-033: pinned environment and bounded runner passed focused rows on Windows and WSL at 05b1845. Local unpushed branches only; not accepted. | Operator accountable; Codex implements | previous sprint close |  |
| S4-C | Functional, integration and Python API selectors (VST-034) | Selectors with artifacts | PARTIAL | Registry VST-034: functional 90/90 and API 688/688 passed, API INCONCLUSIVE (14 policy exclusions). Local unpushed branches only; not accepted. | Operator accountable; Codex implements | previous sprint close |  |
| S4-D | E2E and regression selectors (VST-035) | Selectors with artifacts | PARTIAL | Registry VST-035: integration 41/41, E2E 55/55, regression 874/874 passed with policy exclusions (INCONCLUSIVE). Local unpushed branches only; not accepted. | Operator accountable; Codex implements | previous sprint close |  |
| S4-E | Synthetic seeded-failure fixture catalog (VST-036) | Seeded failures detected | PARTIAL | Registry VST-036: seeded-failure catalog 3/3 PASS on Windows and WSL at 621ddc01. Local unpushed branches only; not accepted. | Operator accountable; Codex implements | previous sprint close |  |
| S4-F | Evidence envelope, hashes and no-skip gate integration (VST-037) | Gate rejects skipped tests | PARTIAL | Registry VST-037: report envelope passed 897/897 expected selectors but is INCONCLUSIVE (53 policy selectors NOT_RUN). Local unpushed branches only; not accepted. | Operator accountable; Codex implements | previous sprint close |  |

## Sprint S5 - AEVE gate
Goal: Bounded static review with hashes and an independent evidence/coverage receipt; stale HEAD fails (docs/S5_AEVE_GATE_PLAN_2026-10-24.md).

| Task | Title | Acceptance | Status | Evidence | Owner | Depends | Commit |
|---|---|---|---|---|---|---|---|
| S5-A | Versioned static evidence provenance contract (VST-038) | v1-compatible contract | NOT_STARTED | Registry VST-041: prepared only; no AEVE source or analyzer found, AEVE transport unavailable. No implementation exists. | Operator accountable; Codex implements | previous sprint close |  |
| S5-B | Independent analyzer authority and signature binding (VST-039) | Signed analyzer provenance | NOT_STARTED | As S5-A: blocked by the missing AEVE identity and signer service owner. | Operator accountable; Codex implements | previous sprint close |  |
| S5-C | Bounded read-only analyzer adapter and snapshot hashing (VST-040) | Deterministic snapshot | NOT_STARTED | As S5-A: blocked by the missing AEVE analyzer. | Operator accountable; Codex implements | previous sprint close |  |
| S5-D | Truthful rule coverage and finding evidence map (VST-041) | Coverage reported truthfully | NOT_STARTED | As S5-A: blocked by the missing AEVE rule inventory. | Operator accountable; Codex implements | previous sprint close |  |
| S5-E | Exact-head gate and reproducible evidence integration (VST-042) | Stale head fails | NOT_STARTED | As S5-A: depends on S5-A..D. | Operator accountable; Codex implements | previous sprint close |  |
