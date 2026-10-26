# Change 0354 — Reconcile S2/S4 evidence and prepare S3 topology

## What changed

- Added exact-candidate S4 report-bound evidence for the AC-16 identity selector (1/1) and three allowed AC-12 seeded-failure selectors (3/3), including dependency-target pre/post hashes and the explicit AC-17 `NOT_VERIFIED` execution-integrity limit.
- Recorded a proposed, non-approved VST-specific Temporal topology for S3-G07, with options, trust/data ownership, failure handling, rollback, verification conditions, and unresolved owners/gates.
- Updated S2/S4 state, backlog, plans, and prerequisite records to distinguish current evidence from older source-head results and provisioning-only history.
- Added a fresh S2 bounded run record: two Windows contract selectors and two unprivileged WSL anchor selectors passed at candidate `4fe1503`; S2 source/test files match the accepted `f0bbac8` content. The protected pre-existing untracked S2 evidence file remains untouched.

## Why

The exact report-bound S4 prerequisites were previously `NOT_RUN`. Provisioning made the tests available; the first identity attempt then found a too-long temporary AF_UNIX path. Change 0352 fixed that test-only setup issue without weakening assertions, and change 0353 refreshed the selector manifest. The subsequent exact-head reports now establish only the two permitted S4 categories. Separately, S2 still lacked fresh, narrowly permitted Windows/WSL evidence at the current candidate, and the latest GPT-PM S3 decision required an explicit topology dossier while keeping acquisition and execution closed.

## Affected paths and contracts

- S4 report artifacts and summary: `docs/sdlc/evidence/qa/` and `docs/sdlc/evidence/s4-report-bound-allowed-runs-20261026.md`.
- S2 fresh test evidence: `docs/sdlc/evidence/s2-fresh-permitted-runtime-4fe1503-20261026.md`.
- S3-G07 proposed topology: `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`.
- Status reconciliation: `core/STATE.md`, `core/BACKLOG.md`, `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`, and `docs/sdlc/evidence/s4-prerequisite-provisioning-20261026.md`.
- Correlated S3 decision remains CONDITIONAL SELECTION / ACQUISITION NOT APPROVED; this note grants no acquisition, build, install, execution, push, PR, or merge authority.

## Verification state

- S4 identity: report-bound PASS 1/1 at candidate `4fe150326a36faf401b045cfa1b9a2e64d89436b`, source/test head `96c9c1556e0bd7d7731bbfba40806c4d1e209907`, registry SHA-256 `9d232d33cd9b788fe5e4418b010ca0a7a29ee9cc1e2b81dd1e88ca72e3601b70`, run `s4-identity-20261026-r3`.
- S4 seeded-failure: report-bound PASS 3/3 at the same candidate/source/manifest, run `s4-seeded-failure-20261026-r4`.
- S4 dependencies: target contents matched before and after at SHA-256 `94f1a1e0330fe63dbba1bdf8ed173cb8862dbe707a4a654603e281d9cc9cc81f`; reports keep in-run mutation/change-and-restore integrity `NOT_VERIFIED`.
- S2 bounded Windows/WSL slice: four selectors passed; it does not prove Windows Job Object/POSIX process-group containment, production sandbox, egress, or E8 acceptance.
- S4 code review: GPT-6 Luna code-reviewer, low effort, no actionable finding. Security review: GPT-6 Luna security-reviewer, medium effort, no BLOCKER/MAJOR/MINOR finding. These were read-only and ran no tests.
- The 52 S4 policy selectors and prohibited process/crash/mutation cases were not run. No broad S4 matrix or S2 Phase 8 gate was completed.

## Provenance

- S4 implementation/test work remains in canonical checkout `D:\Repo\Virtual_scrum_team` on `s4-canonical-continuation`; no per-sprint development worktree/fork was used.
- Report-bound execution and S2 selector execution were performed by the designated `e2e-runner` at GPT-6 Luna. Codex authored this evidence/status reconciliation and topology proposal.
- Accountable program owner: operator. Test execution owner: `e2e-runner`. S3 architecture adjudicator and later exact-head gate owner: GPT-PM.
