# 0078 S2 functional recovery rerun after pack resource limits

## What changed

- Recorded a fresh run of the four functional-owned Store recovery and breaker-replay regressions in `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md`.
- Updated the decision/lesson logs and regenerated the document registry.

## Why

The S2 source moved through hook-free Git object transfer, object-import ordering, and cumulative storage limits. The operator requested another exact-head run of the isolated functional Store module after E2E test authoring completed.

## Verification state

- Exact source HEAD: `1ef3fee07d5743dc8e42c632e1dc3100601116a7`.
- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_operation_recovery.py`.
- Result: exit 0; 4 passed, 0 skipped, 1 pytest-asyncio deprecation warning in 1.35 seconds.
- Environment and exact test IDs: `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md`.
- The hook-free pack-transfer security and storage/resource behavior remains outside this functional module and requires its separate E2E evidence.

## Ownership

- Accountable task owner: operator.
- Functional test executor: functional-test-reviewer (`gpt-6-luna`).

Agent-Attribution: functional-test-reviewer (`gpt-6-luna`); Codex executor
