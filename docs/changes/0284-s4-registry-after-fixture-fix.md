# 0284 S4 selector registry after fixture correction

**Date:** 2026-10-25  
**Executor:** Codex  
**Test source HEAD:** `05d9935c7ae8ace69ab9e8d1e083ae96c353741b`

## What changed

- Regenerated `docs/qa/categories.json` from the committed test sources in change 0283.
- Preserved the full policy `NOT_RUN` set and bound all selector inventory hashes to the corrected test source commit.
- Updated S4 state and backlog records with the new source head and focused-test queue.

## Verification state

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write` exited 0 and wrote `docs/qa/categories.json`.
- Read-only inventory report: source HEAD `05d9935c7ae8ace69ab9e8d1e083ae96c353741b`; functional 90; integration 84; API 705; E2E 56; seeded-failure 3; regression 884; policy `NOT_RUN` 51.
- Registry generation is not test evidence. The latest focused execution remains 87 passed / 21 failed / 1 warning at `7cc903b`, before the fixture corrections.
- Documentation registry command: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (260 lines). This is documentation-index generation only.

## Next step

Commit this selector registry refresh, then run the three focused S4 contract modules through `functional-test-reviewer` at the resulting exact HEAD. Preserve all 51 policy `NOT_RUN` selectors.
