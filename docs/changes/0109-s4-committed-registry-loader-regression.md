# 0109 S4 committed registry loader regression

## What changed

- Added a focused API test that loads the repository's actual committed category registry through the production `load_registry` boundary.
- The test checks the registry byte digest and that every supported node ID has a single primary-category assignment; `load_registry` itself resolves tracked test functions and validates source-head ancestry.

## Why

Earlier contract tests used synthetic registry inputs to isolate duplicate, stale-provenance, and selector failures. S4 also needs a positive acceptance case proving the real committed registry can load after category provenance and test IDs are reconciled.

## Affected contracts and paths

- `tests/qa/test_s4_registry_contracts.py`: API regression against the production registry loader and current committed registry.
- `docs/qa/categories.json`: committed registry inputs covered by the API assertion.
- `tools/qa/registry.py`: tracked source node resolution and candidate-history provenance behavior.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`functional-test-reviewer` owns this test).
- The source-head pin must be an ancestor of the current S4 candidate and contain all declared node definitions; the registry remains partial where scenario coverage is incomplete.
- This record is numbered 0109 because 0107 was already assigned to the E2E placeholder hardening commit.

## Verification state

- Exact-head functional execution is pending after the category registry reconciliation commit.
- The test file and its node were committed before the shared registry ID was added; no pass is claimed from the test's existence alone.
- No tests, checks, builds, or CI were run by Codex for this record.

## Follow-up

1. Add the committed loader node ID to the API denominator with source-head provenance.
2. Have the functional-test-reviewer run the real registry loader regression and the focused API module on the exact candidate head.
