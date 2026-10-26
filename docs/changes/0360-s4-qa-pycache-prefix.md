# Change 0360 — Isolate pytest bytecode cache from locked dependencies

## What changed

- `tools/qa/run.py`: the report-bound pytest child now receives `PYTHONPYCACHEPREFIX` rooted at that run's scratch directory, alongside the existing `PYTHONDONTWRITEBYTECODE=1` setting.

## Why

At candidate `c0cb5109be791b82225a5287d60b347ce106c3c1`, the report-bound E2E selector set passed, but exact dependency-target verification failed after 111 `.pyc` files appeared under locked packages (110 ordinary CPython caches and one pytest-rewritten cache). A focused E2E run reproduced the same inventory change while both the outer pytest and `_run_cli` child had `PYTHONDONTWRITEBYTECODE=1`. A second focused run with `PYTHONPYCACHEPREFIX` applied only to the outer pytest still changed the target, which localized the remaining writes to nested child processes. The approved fix gives each report-bound pytest child a per-run cache root outside the dependency target.

## Affected contract and paths

- AC-17 report-bound dependency integrity: imports must not mutate the hash-locked dependency target.
- `tools/qa/run.py`, `_pytest_command()` environment.

## Verification state

- Root cause evidence: report-bound E2E run `s4-e2e-20261026-win-c0cb510-r1` passed all 58 registered selectors but failed dependency post-inventory verification; row SHA-256 `0ac34d9aa0ef5913b7067f4363fba2e324e186948db6184a936fe69645d72389`.
- Focused diagnostic `s4-e2e-pycacheprefix-20261026-win-c0cb510-r1` still failed target verification when the cache prefix was applied only to the outer process; row SHA-256 `b5b30d4a7ca1dcfbb5bf3d39905df7a6cb6b3779ce3328921b219efbf5e173dd`.
- Focused worktree verification by the designated E2E runner: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_child_runner_disables_dependency_bytecode tests/qa/test_s4_e2e_runner_cli.py::test_s4_pytest_argv_size_depends_on_source_files_not_selector_count`; exit 0, 2 passed, 1 existing pytest-asyncio deprecation warning, 1.11 seconds.
- The two behavioral assertions are present in the E2E runner's uncommitted test-source change and will be recorded with its own change record. Exact-candidate report-bound E2E/regression reruns remain pending; no report-bound result is upgraded by this code change.
- Existing 52 policy-excluded selectors remain `NOT_RUN`.

## Ownership and next action

- Accountable owner: operator.
- Production implementation: Codex.
- Test author and executor: designated E2E runner.
- Next: have the E2E runner complete the two environment-boundary assertions and rerun report-bound E2E with a fresh dependency target at the committed source and registry candidate; preserve exact before/after hashes and keep policy exclusions unchanged.
