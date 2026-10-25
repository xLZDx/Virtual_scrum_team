# Change 0232: Record exact-head S2 section 9 contract rerun

## What changed

- Added exact-head evidence for S2.D1/D2: manifest-mandatory commands, trusted parser pinning, and the bounded signed-waiver scope.
- Updated VST-025/026 backlog rows, both S2 HTML reports, and decision/lesson logs with the focused result and its limits.
- Regenerated the document registry.

## Why

The original autonomous task explicitly includes both section 9 items. They were implemented in prior source work and mapped in VST-025/026, but the portfolio acceptance matrix omitted them and lacked an exact-current-HEAD rerun. The designated functional test agent ran only the existing relevant selectors.

## Evidence

- Exact HEAD before and after: `a2a5d5a34d45c02c095c993260e313078f75bde9`.
- Agent: `functional-test-reviewer`, GPT-6 Luna, low effort.
- Command: see `docs/sdlc/evidence/s2-section9-contract-rerun-a2a5d5.md`.
- Result: 12 passed, 0 failed, 0 skipped; one pytest-asyncio deprecation warning.
- No source/test files changed; no mutation, CI, process-kill, or kill-table scenarios ran.

## Verification state

- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py reports\S2_ISOLATED_WORKER_SANDBOX_2026-10-25.ru.html reports\S2_ISOLATED_WORKER_SANDBOX_2026-10-25.html`: exit 0; refreshed both reports.
- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py --check reports\S2_ISOLATED_WORKER_SANDBOX_2026-10-25.ru.html reports\S2_ISOLATED_WORKER_SANDBOX_2026-10-25.html`: exit 0; both reports carry the required block.
- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0; generated 193 Markdown-document entries.
- `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0; registry current.
- `git diff --check`: exit 0.
- No product test suite ran during this documentation update.
