# 0112 S4 functional exact-head evidence

## What changed

- Recorded the exact clean-head result for the nine-case API/registry/seeded-failure suite in `docs/sdlc/evidence/s4-functional-registry-594eedd.md`.
- Mapped every owned test ID to the S4 acceptance criteria it exercises and recorded environment limitations.

## Why

The S4 gate requires evidence tied to the exact tested candidate, plus explicit treatment of unrun native runner and signer paths. The focused suite now covers the actual committed registry and its Git/node-resolution boundaries in addition to negative synthetic fixtures.

## Affected contracts and paths

- `tests/qa/test_s4_registry_contracts.py`: nine focused acceptance cases.
- `docs/sdlc/evidence/s4-functional-registry-594eedd.md`: exact command, head, environment, outcomes and test-to-AC map.
- `governance/DOCUMENT_REGISTRY.md`: regenerated to list this evidence and change record.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- The Windows focused result is valid behavioral evidence for these Python APIs; it is not substituted for the pinned Ubuntu native runner or report/signing gate.
- The globally installed `pytest-asyncio` deprecation warning is recorded; no async tests are in this module.

## Verification state

- Exact HEAD: `594eeddcd1f6409928e7eebb1e9f8581c8eba75c`.
- Worktree was clean before the test command.
- Command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py`.
- Result: **9 passed, 0 failed**, in `5.25s`; one `pytest-asyncio` deprecation warning.
- Environment: Windows PowerShell, Python `3.14.3`, pytest `8.4.2`.
- Pinned Ubuntu 24.04 / CPython 3.12.3 native execution remains `NOT_RUN`: the available distribution has an empty `/mnt/d`, and the private snapshot root and signer runtime are unavailable.

## Follow-up

1. Keep report/signature/artifact and sandbox-dependent category evidence `NOT_RUN` until the exact private S4 runner provisioning values are available.
2. Reconcile this focused category evidence with the E2E agent's two local scenarios; do not claim full category coverage from this module alone.
