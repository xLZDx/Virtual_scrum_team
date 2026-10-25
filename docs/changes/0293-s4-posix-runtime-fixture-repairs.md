# 0293 S4 POSIX runtime fixture repairs

**Date:** 2026-10-25  
**Executor:** Codex  
**Test author:** `functional-test-reviewer` (GPT-6 Luna)  
**Observed runtime candidate:** `e75e0fe5d0c772f513bf0af2092a5a859d95c61f`

## Why

The full S4 matrix at `e75e0fe` passed every assigned Windows profile, but WSL and root-profile rows exposed environment assumptions in test fixtures. The WSL functional and E2E failures came from synthetic candidates created outside the runner's enforced `/tmp/vst-s4-candidate` boundary. Two root-profile failures attempted `chown` after making fixture directories inaccessible to the capability-bounded root process, and cleanup assumed unrestricted root privileges.

## Changes

- Pin the Windows-specific final-Git-status contract test to `WINDOWS_PROFILE`, so its synthetic candidate does not depend on the host runtime profile.
- Give WSL E2E tests a unique candidate directory below `/tmp/vst-s4-candidate/test-fixtures`, validate the runner UID and parent ownership/mode/access, and remove only the unique child created by the fixture. Keep artifacts and scratch data in pytest's temporary directory.
- Set POSIX fixture modes before changing owners in the reviewer-worktree and signer-key/IPC tests. Restore only those fixture directories to root ownership and mode `0700` before cleanup, preserving the identity and access assertions.

Only the four test source files were edited. No production source, selector registry, evidence artifact, or pre-existing S2 evidence file was changed by this test-author pass.

## Verification and limitations

The prior focused run at exact candidate `e75e0fe` passed 108 tests with one pytest-asyncio deprecation warning. The full matrix at that same candidate returned `FAIL`: all assigned Windows categories passed; WSL integration, API, and seeded-failure passed; WSL functional had one fixture failure, WSL E2E had nine selector IDs with 12 concrete failing cases, and regression included those ten selector IDs. Three root report rows failed on two POSIX fixture selectors. Direct diagnostic runs identified the fixture causes above; they were diagnostic only and do not constitute acceptance evidence.

This record describes uncommitted test-author changes pending review/commit. The new WSL fixture parent `/tmp/vst-s4-candidate/test-fixtures` must be provisioned as UID 997, mode `0700`, before the designated WSL test run. The changes are not yet run, registered, or accepted. The 51 policy `NOT_RUN` selectors remain non-approving and must stay excluded from execution.

Documentation index generation: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and updated `governance/DOCUMENT_REGISTRY.md` to 249 Markdown documents. This is documentation inventory generation, not test or runtime evidence.

Evidence references: `D:\Temp\vst_s4_e75e0fe_wsl_matrix_evidence_20261025\qa\matrix.report.jsonl` (SHA-256 `8b306138b3ebd811f555829838ca97cad671f9cd06076dfbf8e9e1bfd342dad0`); `D:\Temp\s4-e75e0fe-runtime-evidence.zip` (SHA-256 `a93fe18a67fe3c6614d832045a147fa12740752dc6cfc5674eeb14f2f94a59e3`).

## Next

Review and commit the four test-only files with this record and the required state/log updates. Then regenerate the selector registry from committed test sources and run focused plus full exact-head acceptance through the designated test agents. Do not create per-sprint worktrees; development remains in `D:\Repo\Virtual_scrum_team`.
