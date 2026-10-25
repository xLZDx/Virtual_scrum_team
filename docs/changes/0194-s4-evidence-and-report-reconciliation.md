# Change 0194: Reconcile S4 acceptance reports with exact-head evidence

## What changed

- Refreshed the bilingual S4 HTML reports, S4 plan status and current-evidence section, and canonical VST-032–037 backlog row to reflect changes 0186–0193.
- Replaced stale category counts and heads with the recorded exact-head evidence: functional/integration/seeded 27/27 at `c8bb027` (0192; 0187 also recorded 27/27 at `97c3900`), API 92 passed/1 skipped/0 failed at `c8bb027`, and all 12 mapped E2E selectors passed at `47918f9`.
- Kept the E2E denominator `PARTIAL` because no selector exercises `tools.qa.run` report serialization with v2 signed artifacts. Kept trusted signer, run-specific manifest, report/receipt/authoritative gate, fresh current-head WSL/POSIX transfer, sandbox acceptance, and mutation/red-green as `NOT_RUN` where required.
- Clarified that the prior WSL run at `56dce67` does not establish current-head acceptance, that the API symlink case skipped on Windows with `WinError 1314`, and that no full aggregate regression with report-bound artifacts was run.
- Recorded the no-BLOCKER/MAJOR code and reliability reviews and the reliability INFO diagnostic limitation.

## Why

The prior S4 report described old 8-functional/1-integration and 7-E2E counts and called the API denominator incomplete after newer exact-head evidence had been recorded. The plan and backlog also described completed local selectors as pending. The update keeps local category results separate from report-bound v2 and deployment runtime gates.

## Affected paths and contracts

- `reports/S4_QA_AUTOMATION_2026-10-25.ru.html`
- `reports/S4_QA_AUTOMATION_2026-10-25.html`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `core/BACKLOG.md` (VST-032–037)
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, and generated `governance/DOCUMENT_REGISTRY.md`

No source code, selector, or test behavior changed. The report remains `IN PROGRESS`; it is not PM approval, merge evidence, or proof of full acceptance.

## Verification state

- Reconciliation baseline was branch HEAD `458f60337bd3b1697f2e7b7f5141e947d81327ab`; only the documentation paths listed above were edited.
- Facts were checked against changes 0186–0193, `tools/qa/registry.py`, and `docs/qa/categories.json`.
- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py --check reports\S4_QA_AUTOMATION_2026-10-25.ru.html reports\S4_QA_AUTOMATION_2026-10-25.html` exited 0: `all reports carry the mandated block`.
- `C:\Python314\python.exe tools\build_document_registry.py` regenerated `governance/DOCUMENT_REGISTRY.md`; `C:\Python314\python.exe tools\build_document_registry.py --check` reported `DOCUMENT_REGISTRY.md is current`.
- No tests, builds, or runtime probes were run for this documentation-only change.

Executor: Codex
