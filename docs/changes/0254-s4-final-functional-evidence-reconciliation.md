# Change 0254: Reconcile S4 functional runtime evidence

## What changed

- Added `docs/sdlc/evidence/s4-reportbound-functional-7b0fe23.md` with the exact source snapshot, test commands/results, synthetic functional CLI receipt, artifact hashes, and scope limits.
- Updated the S4 plan, backlog, decision and lessons records to distinguish functional-category PASS from incomplete E2E, trusted signer, aggregate, and authoritative-gate acceptance.
- Refreshed the bilingual S4 status report with a current 15-item acceptance matrix and preserved historical run details as historical evidence.

## Why

At exact source/test HEAD `7b0fe2339980b6b5d7278c0aeaaa58cc5fab8b71`, `e2e-runner` (GPT-6 Luna, medium) completed ten mapped focused selectors (10 passed) and a synthetic `tools.qa.run` functional run (28 expected, 28 executed; QA report, TestRun receipt, and diff gate PASS). Prior report text still described this path as wholly unrun and omitted the corrected ancestor fixture result. Reconciliation is required to avoid both stale status and overclaiming.

## Decisions and ownership

- Functional synthetic-signer evidence is accepted only for the functional category and the exercised report/receipt/diff contracts.
- It does not close trusted deployed signer, authoritative task-gate, aggregate regression, or E2E denominator.
- Accountable task owner: operator. Executor/coordinator: Codex. Required test execution owner: `e2e-runner`. Canonical technical QA runner/gate and signer service owner: UNKNOWN.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-reportbound-functional-7b0fe23.md`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`
- `reports/S4_QA_AUTOMATION_2026-10-25.ru.html`, `reports/S4_QA_AUTOMATION_2026-10-25.html`

## Verification state

- Source/test HEAD: `7b0fe2339980b6b5d7278c0aeaaa58cc5fab8b71`.
- Focused tests: 10 passed in 0.34 seconds, exit 0, under the e2e-runner unit recorded in the evidence file.
- Synthetic functional CLI: 28/28 expected IDs executed, no failed/skipped/xfail/uncollected/unexpected IDs; QA report, TestRun receipt and diff gate PASS. Synthetic signer only.
- Current security review: static review at `e7f857f` found no actionable BLOCKER/MAJOR/MINOR; the later source change only shortened a test fixture.
- Documentation registry and report conformance are to be regenerated/checked after editing. No additional tests/checks are run by Codex.
- Exact-head GPT-PM approval and push/PR remain outstanding; the available PM Bridge previously returned `Transport closed`.

Executor: Codex
