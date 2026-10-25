# 0298 S4 selector registry after WSL fixture baseline update

**Date:** 2026-10-25  
**Executor:** Codex  
**Test source HEAD:** `dc853578e9076db6a6ff75738e8230219fd4bc17`

## What changed

Regenerated `docs/qa/categories.json` from the committed fixture baseline correction in change 0297. The synthetic WSL E2E candidate now copies the runner baseline that contains the WSL Python 3.12.3 runtime profile.

## Verification state

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`
- Exit code: 0; generator wrote `docs/qa/categories.json` and bound it to exact source HEAD `dc853578e9076db6a6ff75738e8230219fd4bc17`.
- Inventory: 935 regression selectors total, 883 assigned runnable and 52 policy `NOT_RUN`; the separate seeded-failure category contains 3 selectors. Functional has 90 selectors; E2E has 56.
- Registry generation only; no tests or runtime profiles were run during this refresh. The timeout recovery selector remains `NOT_RUN` and must not be invoked.

The document index was regenerated after this record was added: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and indexed 254 Markdown documents. This is documentation inventory generation only.

## Next

Run the focused S4 contract modules through `functional-test-reviewer`, then the complete assigned Windows/WSL/restricted-root matrix through `e2e-runner` at the exact committed head containing this registry. Preserve all 52 policy `NOT_RUN` selectors as non-approving.
