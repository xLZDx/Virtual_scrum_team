---
project: Virtual_scrum_team
as_of: 2026-11-07
active_sprint: S2
scope: single_sprint
approved_sprints: S2
operator_approved: true
---
# Virtual_scrum_team - project plan

Sources: docs/sdlc/backlog.md (ordered S2 queue), docs/sdlc/acceptance.md (current bounded S2 disposition), docs/sdlc/AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md (sprint names), core/STATE.md, core/DECISION_LOG.md, docs/sdlc/S1_RETROSPECTIVE.md, Git history on branch s2-canonical-continuation (code candidate 96a8da7).

## Roadmap
| Sprint | Title | Status | Goal |
|---|---|---|---|
| S0 | Inventory and baseline | ACCEPTED | S0 inventory documents (docs/sdlc/s0/); approved by GPT-PM and merged with S1 (PR #1, merge d5cd7f5). |
| S1 | Control-plane core | ACCEPTED | State store, contracts, signing, gate and runner in tools/vst; approved and merged (PR #1, d5cd7f5, closure c5a8eb1). |
| S2 | Isolated worker sandbox | CODE SCOPE ACCEPTED; RUNTIME NOT ACCEPTED | Bounded source/test tasks are accepted and pushed. Live service-to-Runner, current E5 and production qualification remain NOT_RUN; do not report production readiness. |
| S3 | Worker pilot | NOT_STARTED — waits for S2-4E and S2 close | Single isolated story adapter on the S2 sandbox; compare BMad Loop, hand-written loop and a durable engine on one crash/resume fixture; vendor-neutral worker interface. Existing PR #3 predates this work; it is not evidence that S3 has started or that S2 is closed. |
| S4 | QA automation | NOT_STARTED | Real native runners for functional, integration, API, E2E, regression and seeded failures with reproducible artifacts; a skipped test never satisfies DoD. |
| S5 | AEVE gate | NOT_STARTED | Bounded static review with hashes and an independent evidence/coverage receipt; truthful analyzer status; stale HEAD fails. |

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
| S2-4D | REQ-003 source/test acceptance for stored owner-to-Runner handoff | Exact assignment-basis selector and focused bundle contract coverage; inspect the retained `tools/vst` product path. Retired WSL QA harness and Git-source checks are excluded from active scope. | ACCEPTED — bounded source/test | Windows selector 1 passed; bundle contract module 11 passed; internal code review found no BLOCKER/MAJOR; GPT-PM request `a2c98c0f` / reply `f981ea40` approved exact candidate `96a8da7` with 0 BLOCKER/MAJOR. | Codex; GPT-PM supplied final code review | S2-4C | 96a8da7 |
| S2-4E | Windows-local Owner→Runner functional path | Before S3 Worker pilot, a real Windows-local journey forwards an already-signed Owner instruction through Supervisor/Store admission and Store-backed Dispatcher to the Runner; the Runner executes only the Store-authorized one-use grant under Windows Job Object containment and returns a bound receipt. Functional and process E2E evidence must come from the assigned test agents. This does not require E5, production credentials, WSL, or a VPS and does not claim production readiness. | IN_PROGRESS | Source delta c4558a8 is pushed and GPT-PM accepted it; Store contract 5/5 and receipt contract 4/4 passed under the assigned functional-test-reviewer. Owner route pytest module and Windows process E2E remain NOT_RUN (pytest is prohibited; required Windows services/runtime inputs are absent and the harness does not self-elevate). | Codex | S2-4D | |
| S2-5 | Final S2 bounded code review, exact-head approval and acceptance | Record the bounded source/test disposition after internal review, mapped tests, exact-head GPT-PM decision and successful push; keep runtime/E5 separate. | ACCEPTED — bounded source/test | GPT-PM request `a2c98c0f` / correlated reply `f981ea40` approved exact candidate `96a8da7`; commit is present on `origin/s2-canonical-continuation`. Full matrix: `docs/sdlc/acceptance.md`. | Codex; GPT-PM supplied final code review | S2-4D | 96a8da7 |

## Sprint S3 - Worker pilot
Goal: Single isolated story adapter on the S2 sandbox (from AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md; no detailed task list exists, not expanded).

## Sprint S4 - QA automation
Goal: Real native test runners with reproducible artifacts (from AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md; no detailed task list exists, not expanded).

## Sprint S5 - AEVE gate
Goal: Bounded static review with independent evidence receipt (from AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md; no detailed task list exists, not expanded).
