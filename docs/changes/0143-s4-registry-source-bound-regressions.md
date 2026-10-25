# 0143 S4 registry bounded-source regression tests

## What changed

- Added a regression proving a valid pytest function located after a test source exceeds the 1 MiB read limit is rejected before `ast.parse` is called.
- Added a regression proving `RecursionError` from AST parsing is treated as an unresolved node rather than escaping registry validation.
- Preserved the existing canonical path, traversal, and symlink-component regressions.
- No product source was changed.

## Why

The registry source resolver now bounds test-source reads and fails closed on parser recursion exhaustion. These cases assert observable rejection, including the ordering requirement that oversized source never reaches AST parsing.

## Affected contracts and paths

- `tests/qa/test_s4_registry_contracts.py`: bounded source and parser-recursion regressions.
- `docs/qa/categories.json`: registration and provenance update will follow this source commit.

## Verification state

- Test source authored, not yet executed. The focused module will run only after its exact node IDs are registered against this commit and committed.
- Existing symlink test may be skipped where the platform lacks symlink creation privileges; that limitation remains separate from these two new cases.

## Ownership and next steps

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for this QA registry trust boundary is not separately identified in canonical ownership records.
- Commit source, register the two selectors with provenance pinned to the source commit, run only the focused module on clean exact HEAD, and record durable evidence.
