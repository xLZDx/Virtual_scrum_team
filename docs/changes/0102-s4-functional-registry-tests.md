# 0102 S4 functional, registry, and seeded-failure coverage

## What changed

- Added eight focused behavioral tests for supported category uniqueness, duplicate assignments, stale provenance, unknown test nodes, missing required IDs, exact manifest selectors and commands, malformed fixture hashes, and a real unchanged-product rejection observation.
- Added one bounded seeded-failure fixture for a v2 task manifest rejected by the existing Python validator. Its canonical input SHA-256 is `eeed0bf7ca96a320d4262965fb2667ce528eab6eed7c4805b9720117e1b8510e`.
- The API and seeded-failure registry entries are being reconciled by the coordinator after all newly registered test nodes are committed. The E2E agent separately owns its test source and change record.

## Why

S4 acceptance requires exact primary-category assignment and manifest projection, stale-source rejection, and a committed synthetic failure fixture whose input digest and observed rejection are bound to one test ID. The first run also exposed that a tracked test file name alone did not prove the pytest node existed; the implementation owner fixed that behavior in commit `b0c61a1` and the regression is included here.

## Affected contracts and paths

- `tests/qa/test_s4_registry_contracts.py`: focused API/registry behavior and one seeded-failure observation.
- `docs/qa/seeded_failures.json`: canonical input, expected rejection, digest, and linked test ID.
- `docs/qa/categories.json`: API/seeded category reconciliation is pending coordinator ownership of the shared registry file.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- The synthetic input is `{"contract_version":2}`; the existing `validate_task_manifest` function must reject it with `ContractError` before the test records `INVALID_TASK_MANIFEST` as the stable fixture-level rejection code.
- Network APIs remain unsupported because no HTTP route contract is present in the in-scope repository.
- E2E tests and their source ownership remain with the E2E agent.

## Verification state

- Source HEAD before this test commit: `0c8232e237477328d3dd5b9a658288d977360073`.
- Command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py`.
- Result: **8 passed**, with one deprecation warning from the globally installed `pytest-asyncio` plugin. Environment: Windows, Python `3.14.15`, pytest `8.4.2`.
- The first run occurred before the catalog file was committed and temporarily stubbed only the Git tracked-file predicate. That run was superseded by an exact post-commit rerun at `d56ef7994bcee6c8a9f7a2359105bc1eb1e4fdc9` with the stub removed: **8 passed**, using the same command and environment.
- The pinned `Ubuntu-24.04` / CPython `3.12.3` run is `NOT_RUN`: `/mnt/d` is empty in the available WSL distribution, and the S4 snapshot command requires a pre-provisioned private destination root plus runner account and worker group. No package was installed.

## Follow-up

1. Commit this test source and fixture, then rerun without the temporary tracked-file seam.
2. After the shared registry records all committed API, seeded-failure, and E2E node IDs with a verified ancestor source head, rerun the registry loader against that exact committed registry.
3. Run pinned native acceptance only after the isolated WSL snapshot destination and signer runtime are available; keep unavailable scenarios `NOT_RUN`.
