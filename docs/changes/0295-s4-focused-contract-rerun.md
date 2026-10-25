# 0295 S4 focused contract rerun after POSIX fixture repair

**Date:** 2026-10-25  
**Executor:** Codex  
**Test owner:** `functional-test-reviewer` (GPT-6 Luna)  
**Test source HEAD:** `af424b51592646dc5dd918bd571f47110bd82cc9`

## Scope and command

The designated functional-test reviewer reran the three focused S4 functional contract modules after changes 0293 and 0294. The run used the canonical `D:\Repo\Virtual_scrum_team` checkout; no per-sprint worktree was created.

```text
C:\Python314\python.exe -m pytest tests/qa/test_s4_functional_runner_contracts.py tests/qa/test_s4_functional_runtime_matrix.py tests/qa/test_s4_functional_root_harness.py -q --tb=short
```

## Result

- Runtime: Windows, Python 3.14.3.
- Exit code: 0; 108 passed, 0 failed, 0 skipped.
- Pytest duration: 183.85 seconds; total command duration: 189.95 seconds.
- One pytest-asyncio deprecation warning reported use of an API scheduled for removal in Python 3.16.
- The agent reported no file edits or commits during execution.

The document index was refreshed after adding this record: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and indexed 251 Markdown documents. This is documentation inventory generation only.

## Limits and next step

This is focused contract evidence only. It does not verify the full Windows/WSL/root category matrix, the installed root helper's successful runtime, or the matrix artifact. Run all assigned categories through `e2e-runner` at one exact committed candidate. Preserve all 51 policy `NOT_RUN` selectors as non-approving.
