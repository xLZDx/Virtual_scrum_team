# 0107 S4 committed registry loader regression

## What changed

- Added a focused API test that loads the repository's actual committed category registry through the production `load_registry` boundary.
- The test checks the registry byte digest and that every supported node ID has a single primary-category assignment; `load_registry` itself resolves tracked test functions and validates source-head ancestry.

## Why

Earlier contract tests used synthetic registry inputs to isolate duplicate, stale-provenance, and selector failures. S4 also needs a positive acceptance case proving the real committed registry can load after category provenance and test IDs are reconciled.

## Affected contracts and paths

- `tests/qa/test_s4_registry_contracts.py`: real repository loader acceptance path.
- `docs/qa/categories.json`: the coordinator owns the final source-head and category-entry update; this test must be included in the API denominator.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- The test uses the exact worktree path and Git history; no Git or repository-file mocks are used on this path.

## Verification state

- `NOT_RUN` at authoring time because the coordinator's registry provenance update and API test-ID entry are pending.
- Planned focused command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py`.
- The pinned Ubuntu 24.04 / CPython 3.12.3 run is separately `NOT_RUN` because the WSL distribution has no mounted checkout at `/mnt/d` and the isolated runner root is not provisioned.

## Follow-up

1. After this test source is committed, update the API category test-ID list and set source heads to an ancestor containing all registered nodes.
2. Run the focused command against the exact committed category registry and record its result.
