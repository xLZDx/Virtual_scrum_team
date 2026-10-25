# 0294 S4 selector registry after POSIX runtime fixture repairs

**Date:** 2026-10-25  
**Executor:** Codex  
**Test source HEAD:** `a318f11b0a93c50f7c37e242f2dabd78358e0f73`

## What changed

Regenerated `docs/qa/categories.json` from the committed test sources in change 0293. The registry binds to the exact source HEAD and retains the three declared runtime profiles.

## Verification state

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`
- Exit code: 0; the generator wrote `docs/qa/categories.json`.
- Registry inventory: 935 total selectors, 884 assigned runnable and 51 policy `NOT_RUN`; functional has 90 selectors. E2E has 56 selectors.
- This is selector registry generation only. No tests or runtime profiles were executed by this registry refresh.
- Preserve all 51 policy `NOT_RUN` selectors as non-approving. Next test run must use the committed registry and exact candidate HEAD.

Documentation index generation: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 after adding this record and updated `governance/DOCUMENT_REGISTRY.md` to 250 Markdown documents. This is documentation inventory generation, not test or runtime evidence.

## Next

Run the focused three S4 functional contract modules through `functional-test-reviewer` at the exact commit that includes this registry. If focused tests pass, run the full assigned matrix through `e2e-runner`, after provisioning the WSL fixture parent as UID 997 with mode `0700`. Do not create per-sprint worktrees.
