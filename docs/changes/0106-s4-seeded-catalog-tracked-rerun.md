# 0106 S4 seeded catalog tracked-file rerun

## What changed

- Removed the temporary test seam that bypassed the Git tracked-file predicate for the seeded-failure catalog.
- Updated change record 0102 with the exact post-commit rerun evidence.

## Why

The first focused run happened while the catalog was still untracked. Once commit `d56ef79` included the test and catalog, the suite could exercise the real tracked-file boundary directly.

## Affected contracts and paths

- `tests/qa/test_s4_registry_contracts.py`: seeded catalog validation now uses the real repository tracking check.
- `docs/changes/0102-s4-functional-registry-tests.md`: superseded the pre-commit result with the post-commit exact-head result.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- The focused API/registry suite remains partial S4 evidence; it does not establish the pinned WSL runner, signer, report artifact, or full category gates.

## Verification state

- Exact HEAD: `d56ef7994bcee6c8a9f7a2359105bc1eb1e4fdc9`.
- Command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py`.
- Result: **8 passed**, one deprecation warning from globally installed `pytest-asyncio`.
- Environment: Windows, Python `3.14.15`, pytest `8.4.2`.
- Pinned Ubuntu 24.04 / CPython 3.12.3 execution remains `NOT_RUN`; the distro's `/mnt/d` is empty and the private pre-provisioned runner root is unavailable.

## Follow-up

1. Rerun against the coordinator's final committed registry after provenance heads and all category entries are reconciled.
2. Repeat on the pinned isolated WSL runner if its exact source snapshot and signer boundary are provisioned.
