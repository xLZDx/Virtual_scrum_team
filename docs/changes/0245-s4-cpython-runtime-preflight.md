# 0245 S4 CPython runtime preflight correction

**Date:** 2026-10-25  
**Executor:** Codex  
**Implementation agent:** `implementation-engineer`, GPT-6 Luna, low effort  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `65c0fbbad4ea27e679d342bb720775802f99a4bd`

## What changed

- Corrected the QA runner's runtime implementation check to use `platform.python_implementation()`, which returns the canonical display name `CPython`.
- Preserved the independent pinned-interpreter path check and Python 3.14 version check.
- Removed a machine-specific temporary absolute path from change record 0244; the record now identifies the retained pytest report by its temporary-directory role and repository-relative location.

## Why

The exact-head S4 test run showed seven CLI cases blocked before child pytest execution with `runner requires the pinned CPython 3.14 interpreter`, despite report metadata identifying Python 3.14.3 and executable `C:/Python314/python.exe`. The implementation compared `sys.implementation.name` with `CPython`; CPython reports that attribute as lowercase `cpython`. This made the preflight reject the supported runtime.

## Evidence and verification

- Test-agent execution at `0b73000bb7eb2a0d25caa8364b066c64299abd85`: four authored QA modules reported 11 failed, 51 passed, 2 skipped, 1 warning in 232.34 seconds, using `C:\Python314\python.exe`, Python 3.14.3, pytest 9.0.3, and the isolated hash-locked target. The E2E reports showed `command: []`, `exit_code: null`, and `capture: {}` for the seven preflight-blocked cases.
- Static source evidence: `sys.implementation.name` is the lowercase implementation identifier; `platform.python_implementation()` returns the display name used in the runner's environment record.
- The implementation change is one line in `tools/qa/run.py`. **No tests were run after this correction**, so runtime acceptance remains pending.
- No worktree or clone was created. The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.

## Acceptance and next steps

- S4 pinned runtime preflight: corrected in code; exact-head runtime proof remains pending.
- E2E CLI cases: remain unverified after the fix; test fixture hygiene was corrected separately in change 0244.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Implementation executor: `implementation-engineer`; test executor: `e2e-runner`.
- Next: finish the test-author correction to the valid non-ancestor Git fixture, commit all in-scope corrections, then rerun the permitted S4 suite on the resulting exact HEAD. Keep process-tree timeout `NOT_RUN`.
