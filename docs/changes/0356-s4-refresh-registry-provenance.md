# Change 0356 — Refresh S4 registry after the test-source commit

## What changed

- Regenerated `docs/qa/categories.json` after test source commit `62e9c946bdb66fccc6eaf0b164b8c5e178592cf8` so the new wheel-tag selector and the source inventory bind to the actual latest commit of `tests/qa/test_s4_dependency_provenance.py`.
- Updated S4 backlog counts to 958 total regression IDs: 906 runnable and 52 policy-excluded `NOT_RUN`. The functional category now contains 106 selectors, and the aggregate regression category contains 906 selectors.
- Recorded that the lock-pinned wheelhouse itself now passes read-only tag/hash verification, while the older installed dependency target fails exact inventory validation and was not modified.

## Provenance and command

- Registry build: `C:\Python314\python.exe -m tools.qa.build_registry --write`.
- Result: exit 0, `wrote docs/qa/categories.json`.
- Registry SHA-256: `aa9c7370d87500d280771d8eb356f8a3debd903238f48f763af4b0c7c0c2b72b`.
- Registry `source_head`: `62e9c946bdb66fccc6eaf0b164b8c5e178592cf8`.
- The added selector's `source_commit` is also `62e9c946bdb66fccc6eaf0b164b8c5e178592cf8`, resolving the MAJOR source-provenance issue found in the fresh code review before this refresh.

## Verification and remaining work

- This is a registry/data and backlog update; no tests or checks were run for this commit.
- The code/test commit's focused regression result is recorded in change 0355: 1 passed, exit 0, with one pytest-asyncio deprecation warning.
- Read-only `_verified_wheels` validation accepted all six locked wheels in the existing trusted wheelhouse. The pre-existing dependency target failed `verify_dependency_environment` due extra files; it and the wheelhouse remain unchanged.
- The S4 report-bound broad matrix at candidate `4fe1503` did not reach test selectors: Windows stopped at the corrected tag parser's prior behavior, and a WSL candidate staging attempt failed before the runner. Those rows remain `NOT_RUN`, with exact setup outcomes preserved in change 0355.
- Next, create a separate fresh dependency target from the existing hash-pinned wheelhouse, run the permitted report-bound selectors at the new clean exact head, and keep all 52 policy exclusions `NOT_RUN`.
- AC-17 same-identity mutation/change-and-restore during pytest remains `NOT_VERIFIED`; this registry refresh makes no stronger claim.

## Ownership

- Accountable owner: operator.
- Registry, backlog and provenance update: Codex.
- Report-bound test execution: designated `e2e-runner`.
