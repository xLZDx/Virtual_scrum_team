# Change 0199: Refresh S4 acceptance reports with ancestry evidence

## What changed

- Updated the bilingual S4 reports, plan status/current evidence, and VST-032–037 backlog row against changes 0195–0198.
- Recorded the ancestry contract at source commit `7b8200c`: status 0 is ancestor, status 1 is non-ancestor, and status greater than 1, retry exhaustion, or invocation `OSError` is a typed fail-closed `ContractError`; retry remains at most two attempts of five seconds.
- Updated category counts at exact source/test HEAD `20fa7bb`: functional/integration/seeded 32/32, API 92 passed/1 skipped/0 failed across 73 selector IDs, and all 12 mapped E2E selectors passed.
- Kept API symlink runtime `NOT_RUN` after the Windows `WinError 1314` skip. Kept the E2E denominator `PARTIAL` because no `tools.qa.run` report-serialization/v2 signed-artifact selector exists.
- Kept trusted signer, run-specific manifest, current-head WSL/POSIX execution, report/receipt/authoritative gate, and full aggregate report-bound regression `NOT_RUN`.
- Recorded fresh code/reliability review as no BLOCKER/MAJOR/MINOR, plus reliability INFO: Git stderr is suppressed, so fatal-exit diagnostics expose only the status code.

## Why

The earlier status report and plan reflected 14 functional selectors and older exact heads. The ancestry-failure behavior and functional category count have since changed, and change 0198 supplies current exact-head results for all mapped local category runs.

## Affected paths and contracts

- `reports/S4_QA_AUTOMATION_2026-10-25.ru.html`
- `reports/S4_QA_AUTOMATION_2026-10-25.html`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `core/BACKLOG.md` (VST-032–037)
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, generated `governance/DOCUMENT_REGISTRY.md`

No source, test, selector, or category mapping was changed. The report remains `IN PROGRESS`; this is not PM approval, merge evidence, or full acceptance.

## Verification state

- Baseline branch HEAD: `94a8a0347b87d4ab28f61bc2fbbd413cd6b872f7`.
- Facts reconciled against source change 0195, category mapping commit `20fa7bb`, exact-head run evidence 0198, and reviewer findings supplied for source commit `7b8200c`.
- `.codex-s4-final-review.patch` was pre-existing untracked work and was not inspected, modified, staged, or removed.
- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py --check reports\S4_QA_AUTOMATION_2026-10-25.ru.html reports\S4_QA_AUTOMATION_2026-10-25.html` exited 0: `all reports carry the mandated block`.
- `C:\Python314\python.exe tools\build_document_registry.py` regenerated `governance/DOCUMENT_REGISTRY.md`; `C:\Python314\python.exe tools\build_document_registry.py --check` reported `DOCUMENT_REGISTRY.md is current`.
- No tests, builds, or runtime probes were run for this documentation-only update.

Executor: Codex
