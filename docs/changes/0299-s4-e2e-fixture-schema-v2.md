# 0299 S4 E2E synthetic manifest schema v2

**Date:** 2026-10-25  
**Executor:** Codex  
**Test author:** `functional-test-reviewer` (GPT-6 Luna)  
**Baseline HEAD:** `3ff4017f817d78dfd5a530612f97f7d064d9e465`

## Problem

After change 0297 pinned the synthetic E2E candidate to a WSL-capable runner, the runner correctly rejected the test fixture's schema-v1 manifest. The targeted Windows run at `3ff4017` returned 108 passed and 7 failed; the seven failures occurred in four selected E2E functions. A targeted WSL rerun at the same candidate also returned 7 failed concrete cases. Reports had no expected selectors because the synthetic CLI returned `BLOCKED` before child pytest collection. No timeout selector was included in either targeted command.

## Change

Update only `tests/qa/test_s4_e2e_runner_cli.py` so `_category_manifest` emits schema-v2 fields required by the current runner: runtime profile inventory, full artifact map, source inventory, per-test source and runtime provenance, category-level `NOT_RUN` mapping, regression aggregate, and unsupported API declaration. Derive the runnable selector's platform profiles from `tools.qa.registry.required_runtime_profiles`. Preserve the existing output truncation, repeatable artifact, `NOT_RUN`, uncollected, duplicate, skipped, and xfailed assertions unchanged.

## Verification status

- The exact current change has not been tested, registered, or committed yet.
- The prior focused commands at `3ff4017` are failed diagnostics, not acceptance. Windows: 108 passed, 7 failed, 0 skipped, one deprecation warning. WSL: 7 failed concrete cases across the four requested selectors.
- The timeout selector `test_s4_e2e_cli_timeout_is_nonapproving_without_install_or_fallback` was not selected or executed in these focused runs.
- During the code-edit pass, the test reviewer accidentally ran `git diff --check` despite the no-checks-before-code-completion rule. It produced no output and is not verification evidence. This process error is recorded in `core/LESSONS_LOG.md`; no further check was run by that agent.

## Next

Commit this test-fixture update with its record and log entries. Regenerate the selector registry from committed sources, then have the designated test agents rerun the focused contracts and complete assigned matrix at one exact committed HEAD. Preserve all 52 policy `NOT_RUN` selectors.

The document index was refreshed after adding this record: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and indexed 255 Markdown documents. This is documentation inventory generation only.
