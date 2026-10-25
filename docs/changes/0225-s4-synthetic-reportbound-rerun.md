# Change 0225: Record S4 synthetic report-bound fixture rerun

## What changed

- Added `docs/sdlc/evidence/s4-reportbound-synthetic-rerun-de8c6f8.md` with exact runner, command, revision, environment, outcome, scenario scope and explicit runtime limitations.
- Reconciled the English and Russian S4 status reports and the canonical VST-032–037 backlog row to include the 5/5 exact-head synthetic result while retaining the unclosed report-bound runtime criteria.
- Added a decision and lesson entry preserving the distinction between local fixture evidence and deployed execution.

## Why

A fresh `e2e-runner` execution established that the existing local synthetic fixture passes at the current exact S4 HEAD. Accurate status should include that current evidence without upgrading it to a pass for boundaries the fixture excludes.

## Evidence

- Branch: `s4-native-qa-runner`.
- Exact HEAD before and after execution: `de8c6f8afaf34b9566e21a56c24b145b639f6cfd`.
- Test owner/executor: `e2e-runner`, GPT-6 Luna, low effort.
- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/qa/test_s4_report_bound_e2e.py`.
- Result: exit 0; 5 passed, 0 failed, 0 skipped; one pytest-asyncio deprecation warning.
- No product code changed. `tools.qa.run`, deployed signer, sandbox, runner-to-worker identity transition and authoritative deployed gate remain NOT_RUN.
- Pre-existing untracked `.codex-s4-final-review.patch` was preserved.
- Documentation conformance, registry and whitespace checks are recorded after their execution below.

## Verification state

- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py reports\S4_QA_AUTOMATION_2026-10-25.ru.html reports\S4_QA_AUTOMATION_2026-10-25.html`: exit 0; refreshed both reports.
- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py --check reports\S4_QA_AUTOMATION_2026-10-25.ru.html reports\S4_QA_AUTOMATION_2026-10-25.html`: exit 0; both reports carry the required block.
- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0; generated 299 Markdown-document entries.
- `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0; registry current.
- `git diff --check`: exit 0.
- No product test suite was rerun during this documentation update.
