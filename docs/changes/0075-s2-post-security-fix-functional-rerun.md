# 0075 S2 functional recovery regressions after hook-free publication fix

## What changed

- Added a post-fix exact-head run record to `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md` for the four Store-level S2 external-operation and breaker-replay regressions.
- Updated the decision/lesson logs and regenerated the document registry.

## Why

Security remediation replaced direct push with hook-free object-pack transfer, then corrected candidate import ordering before ancestry checks. The functional Store-level recovery contracts needed a fresh run on the resulting source head.

## Verification state

- Exact source HEAD: `202e0680e8e1b4fb30dcbe9659bf550d06443d90`.
- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_operation_recovery.py`.
- Result: exit 0; 4 passed, 0 skipped, 1 pytest-asyncio deprecation warning.
- Environment and exact test IDs: `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md`.
- This targeted module does not cover the newly introduced Git hook-free pack transfer or source-only object handling; E2E owns those tests, and their evidence must remain tied to their own exact head.

## Ownership

- Accountable task owner: operator.
- Functional test executor: functional-test-reviewer (`gpt-6-luna`).

Agent-Attribution: functional-test-reviewer (`gpt-6-luna`); Codex executor
