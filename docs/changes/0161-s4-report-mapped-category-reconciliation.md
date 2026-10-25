# Change 0161: Reconcile S4 report with mapped category evidence

## What changed

Updated the S4 acceptance report, plan, backlog, decision log, and document registry to include the exact-head functional and integration selector results in change 0160.

## Why

The preceding checkpoint reported registry/API, E2E, and WSL evidence but did not yet include the mapped functional and integration categories. The category registry now has evidence for each currently declared mapped primary-category selector, while full aggregate regression and report-bound acceptance remain incomplete.

## Evidence

- At clean code HEAD `b741dc205a111e56bb984c59a63af2801870e4fc`, the eight mapped functional selectors passed 8/8 and the one mapped integration selector passed 1/1 on Windows / Python 3.14.3 / pytest 8.4.2; no skips/failures. Evidence/change 0160.
- The registry module at code HEAD `6903b7b` passed 19, skipped one Windows symlink case, failed zero (0156).
- Seven mapped Windows selectors passed at `2dc6947` (0157); seven mapped POSIX selectors and the worker read-only boundary passed in run `f3ad62c94bc0429987bc24277103d5b4` at source `56dce67` (0159).
- Fresh code/security/reliability reviews at `2dc6947` found no open BLOCKER/MAJOR.
- Full aggregate regression, report-bound runner, signer, receipt, authoritative gate, POSIX symlink-specific test, full API/category completeness, and broader sandbox acceptance remain open.

## Affected paths

- `reports/S4_QA_AUTOMATION_2026-10-25.ru.html`
- `reports/S4_QA_AUTOMATION_2026-10-25.html`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

Mapped category evidence was already recorded by the test owner in 0160. This change reconciles the bilingual report, plan, backlog, decision/lesson logs, and registry to that evidence. `report_conform.py` refresh and `--check` both exited 0 (`all reports carry the mandated block`); `tools/build_document_registry.py --check` exited 0 (`DOCUMENT_REGISTRY.md is current`). No new product tests were run by this documentation change.

## Provenance

Prepared by Codex from test-owner evidence records 0156, 0157, 0159, and 0160.
