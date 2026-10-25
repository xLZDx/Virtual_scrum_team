# Change 0158: Reconcile S4 status and acceptance report

## What changed

Added the bilingual S4 status report and reconciled the S4 plan/backlog with the latest registry functional run, mapped Windows E2E run, and fresh specialist reviews. Updated the decision and lesson logs, then regenerated the document registry.

## Why

The prior S4 summary predated the AST cache, Git timeout retry, aggregate source/ID limits, exact functional evidence, and current mapped Windows E2E rerun. The checkpoint distinguishes implemented behavior, runtime-proven scope, platform skips, and incomplete sandbox/category acceptance.

## Evidence and decisions

- Functional registry module at code HEAD `6903b7bf3e3dd4fc1281412c173fb82db9924d11`: 19 passed, 1 skipped, 0 failed; Python 3.14.3 / pytest 8.4.2; evidence/change 0156. The skip is Windows symlink privilege (`WinError 1314`).
- Seven mapped Windows E2E selectors at code/test HEAD `2dc6947e416b61103548285ec279d787c1027d8b`: 7 passed, 0 skipped, 0 failed; 25.47 seconds; evidence/change 0157.
- Fresh code, security, and reliability reviews at `2dc6947e416b61103548285ec279d787c1027d8b` (GPT-6 Luna, medium) found no open material code finding, security BLOCKER/MAJOR, or reliability BLOCKER/MAJOR.
- Full S4 acceptance remains open: current WSL transfer is `RESULT_NOT_CAPTURED`; POSIX symlink behavior, signer/report/receipt/gate integration, full native category denominator, and broad sandbox acceptance remain `NOT_RUN` or partial.
- No GPT-PM final gate, push, PR, or merge is claimed.

## Affected paths

- `reports/S4_QA_AUTOMATION_2026-10-25.ru.html`
- `reports/S4_QA_AUTOMATION_2026-10-25.html`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

`C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py --check reports\S4_QA_AUTOMATION_2026-10-25.ru.html reports\S4_QA_AUTOMATION_2026-10-25.html` exited 0 (`all reports carry the mandated block`). `C:\Python314\python.exe tools\build_document_registry.py --check` exited 0 (`DOCUMENT_REGISTRY.md is current`). No product tests were run by the coordinator. This checkpoint does not claim every S4 acceptance criterion passed.

## Provenance

Prepared by Codex from linked exact-head test and review records. The commit containing this record identifies the checkpoint revision.
