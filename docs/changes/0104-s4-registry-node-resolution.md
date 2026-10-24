# 0104 S4 registry pytest node resolution

## What changed

- QA registry validation now resolves each declared node ID against its tracked Python test source instead of accepting any string whose source file is tracked.
- The supported registry node shape is a source-resolvable top-level test function or a test method on a top-level `Test*` class. Runtime-generated parametrized selectors are rejected because they cannot be established from the static source boundary.

## Why

An S4 focused functional run found that an unknown pytest node ID passed registry loading when its source file was tracked. A registry could therefore claim coverage for a test that pytest would not collect.

## Affected contracts and paths

- `tools/qa/registry.py`: `_pytest_node_id_exists` parses tracked test source without importing or executing it, then requires the declared node to match pytest's ordinary source naming convention.
- Existing registry checks still require repository-relative `tests/` paths and tracked files.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- Runtime-generated parameter IDs are not accepted in the QA registry because this static validation layer does not execute collection code. If a future category needs parametrized cases, its source-level deterministic ID mapping must be designed and reviewed before expanding this contract.
- No test ownership changed; the functional-test-reviewer owns the regression test and its rerun.

## Verification state

- Implementation was reviewed against the reported failing regression and the existing registry IDs by source inspection only.
- No test, collection, check, build, CI, or runtime command was run by Codex for this change. The functional-test-reviewer owns the pending regression rerun and full focused test suite.
- Exact runtime acceptance remains pending until the test owner records the result against a committed HEAD.

## Follow-up

1. Functional-test-reviewer reruns the unknown-node regression and its focused registry suite after this source change is committed.
2. Reconcile the functional test result and any further source defect before S4 specialist review.
