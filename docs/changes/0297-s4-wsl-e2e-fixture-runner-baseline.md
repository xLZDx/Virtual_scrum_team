# 0297 S4 WSL E2E fixture runner baseline

**Date:** 2026-10-25  
**Executor:** Codex  
**Test author:** `functional-test-reviewer` (GPT-6 Luna)  
**Baseline before this change:** `08252020f24d47f1d23ffb15e15080193400bb9b`

## Problem

Four WSL E2E test selectors (seven concrete cases) returned `BLOCKED` before child pytest collection. The report command was empty and the synthetic CLI report reasons were `runner requires the pinned CPython 3.14 interpreter` and `runner executable is not the approved C:/Python314/python.exe`. The fixture copied its synthetic QA/VST implementation from hardcoded baseline `f0c91163`, whose runtime contract was Windows-only; the test therefore did not exercise the WSL-capable candidate runner.

## Change

Update only `BASELINE_HEAD` in `tests/qa/test_s4_e2e_runner_cli.py` to the committed WSL-capable source baseline `0825202`. The existing contract assertions remain unchanged: candidate and report binding, repeatable artifact chunks, sandbox-dependent `NOT_RUN`, fail-closed output truncation, and rejection of duplicate, uncollected, skipped, and xfailed selectors.

The targeted test reviewer verified that commit `0825202` includes `_wsl_distro_identity` and the WSL CPython 3.12.3 runtime-profile path. No tests or registry generation have run after this one-line fixture change; it is pending commit and exact-head rerun.

The document index was refreshed after adding this record: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and indexed 253 Markdown documents. This is documentation inventory generation only.

## Related exact-head diagnostics

- At candidate HEAD `0825202`, the Windows integration category passed 41 assigned selectors / 83 concrete cases; the prohibited timeout recovery selector was policy `NOT_RUN`. Its report run ID was `diag-windows-integration-0825202-a`; report SHA-256 `bd7109fe7818934e48693c531f7624edaf52dd0b4efd7885888859ac6377f4cc`, stdout SHA-256 `19efec4ae4343abcc4bb5fe62d65b4b1a325e0b66de0f98c3eda66846bd5ce36`, stderr SHA-256 `a790be6d8b616f585f3632a59dbd5d6dd00df05596eddab3dc067c19b938baab`.
- The same corrected-head root API launch passed its single assigned selector. The earlier `ModuleNotFoundError: No module named 'tools'` from the `e1a4278` diagnostic was not reproduced; its cause remains unknown. WSL `/tmp` cleanup prevented retention of a root API report artifact.
- These are partial category diagnostics, not a full matrix. Old `e1a4278` reports are non-accepting: Windows and WSL integration included the prohibited timeout selector. Do not use those reports for S4 acceptance.

## Next

Commit this test-only fixture change with its record and logs, regenerate the selector registry from committed sources, rerun focused S4 contracts, then run the complete assigned matrix at the resulting exact committed HEAD. Keep the timeout recovery selector policy `NOT_RUN` and retain all 52 policy exclusions.
