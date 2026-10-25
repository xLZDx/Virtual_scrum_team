# Change 0154: Record S4 registry module after bounded Git retry

## What changed

- Recorded the full focused S4 registry module rerun after change 0153 introduced one timeout-only retry for bounded Git lookups.
- Updated the S4 backlog and decision history with the exact result and remaining Windows symlink limitation.

## Why

The AST-cache module's first full runs were interrupted by five-second Git subprocess timeouts. The product change in 0153 preserves fail-closed behavior and adds one retry with a bounded total wait. This record captures the designated functional result at the resulting exact code HEAD.

## Affected paths

- `docs/sdlc/evidence/s4-registry-module-retry-08b82e0.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

At code HEAD `08b82e07bceb1bd928a5a02ac6ee9479854caf16`, Python 3.14.3 / pytest 8.4.2: focused module exit 0, 17 passed, 1 skipped, 0 failed, 6.12s. One pytest-asyncio deprecation warning. The skip is Windows symlink creation privilege (`WinError 1314`); POSIX symlink runtime is not covered.

## Provenance

Test owner: functional-test-reviewer (GPT-6 Luna, medium). Exact command and before/after HEAD/status are recorded in the linked evidence.
