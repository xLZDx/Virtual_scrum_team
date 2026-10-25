# 0172 — S4 focused Python API and seeded-failure evidence

## Scope and acceptance mapping

This record covers the committed API denominator and existing seeded fixture at tested code/registry HEAD `f057020c62211b7787de368f300929b7a35b9838`.

| Criterion | Coverage in this run | State / limitation |
|---|---|---|
| AC-1 | `test_s4_registry_accepts_single_primary_category_per_test_id`, `test_s4_registry_rejects_duplicate_primary_category_assignment`, `test_s4_registry_rejects_unknown_pytest_node_id`, `test_s4_registry_rejects_supported_category_without_required_ids`, and manifest projection exact-ID test | Runtime-proven by focused run. |
| AC-2 / AC-8 | Mapped API selectors exercise representative `contracts`, `gate`, `store`, `runner`, and `supervisor` behavior. `network_api` remains `UNSUPPORTED` in `categories.json`. | Representative Python API behavior is proven; exhaustive callable inventory is not. API breadth remains `PARTIAL`. |
| AC-3 | Provenance-outside-history test and committed-registry loading test | Runtime-proven by focused run. |
| AC-7 | Stale gate receipt rejects approval; runner negative exit yields failure; supervisor breaker state survives restart | These mapped failure/restart behaviors are runtime-proven. The API category is not the whole functional denominator. |
| AC-11 | Registry rejects duplicate IDs and unmapped/nonexistent selectors; projection requires exact IDs and commands | These registry/API boundary tests are runtime-proven. Full aggregate regression/report-bound accounting is outside this run and remains open. |
| AC-12 | `test_s4_seeded_failure_rejects_invalid_manifest_and_records_observation` loads the committed input hash, observes `INVALID_TASK_MANIFEST`, and records expected/observed verdict and test ID. The catalog has one fixture. | Runtime-proven for the one committed fixture; this is not mutation testing or proof of other defect classes. |

The five added mapped selectors are:

- `tests/vst/test_e1_contracts.py::test_manifest_valid_returns_equal_deep_copy`
- `tests/vst/test_e2_gate.py::test_stale_head_one_receipt_is_a_hard_reason_and_the_slot_is_unmet`
- `tests/vst/test_e3_store.py::test_reopen_of_a_version_three_database_keeps_data`
- `tests/vst/test_e4_runner.py::test_failing_command_nonzero_exit_gives_fail`
- `tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it`

The original mapped integration selector `test_harmless_command_produces_signed_passing_testrun` remains solely in `integration`; IDs cannot be assigned to two primary categories. The first attempted API inventory transiently duplicated that ID. On HEAD `c310b6098754036eacbe74ea09062cca929163f6`, the focused run reported 17 passed, 4 failed, 1 skipped. The four failures all arose from the duplicate candidate registry ID, which the AC-1 registry contract correctly refused. Change 0171 replaced it with the distinct runner failure selector before the passing rerun; no product code was changed.

## Exact commands and runtime

Machine: Windows x64, PowerShell. Interpreter: Python 3.14.3. Test runner: pytest 8.4.2. Test-runner warning: installed `pytest-asyncio` emitted a deprecation warning for `asyncio.get_event_loop_policy`; no selected test failed because of it.

On exact commit `f057020c62211b7787de368f300929b7a35b9838`, the command resolved API and seeded-failure selectors from the committed canonical JSON and ran only those selectors:

```powershell
$apiIds = (Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json).categories.api.test_ids
$seedIds = (Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json).categories.'seeded-failure'.test_ids
python --version
python -m pytest --version
git rev-parse HEAD
python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin @apiIds @seedIds
```

Result: **21 passed, 1 skipped, 0 failed** in 15.16 seconds. There are 19 API IDs and one seeded-failure ID; pytest expands parameterized selectors, yielding 22 collected cases. The only skip was the symlink path-confinement test. Its exact focused diagnostic command was:

```powershell
python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_symlinked_source_components_before_ast_acceptance
```

Result: **1 skipped** because Windows returned `[WinError 1314] A required privilege is not held by the client` while creating the symlink. This is `NOT_RUN` for that runtime-specific path, not a pass. The registry implementation separately has portable noncanonical-path and existing-target confinement cases that passed in the category run.

## Exact denominator limits

The plan names the five Python modules, but does not enumerate what “documented Python API” means as a finite callable inventory. Repository source shows additional public surface that this run does not individually map: `contracts.py` has canonicalization, digest, principal, receipt, result-derivation, and decision validators; `gate.py` exposes `evaluate`; `store.py` exposes dozens of `Store` methods for leases, receipts, events, idempotent operations, budgets, reconciliation, and gate evaluation; `runner.py` exposes environment/artifact helpers, `run_and_sign`, and `run_manifest_commands`; `supervisor.py` exposes worker lifecycle, gate, stop/resume, simulated publication, and receipt methods. Existing tests in the repository cover many of these, but they are not all registered in the API category. A full public-callable denominator cannot be claimed without an accepted explicit API inventory and category mapping; therefore API remains `PARTIAL` rather than inventing completeness from representative selectors.

Seeded-failure coverage is exact for the catalog's one fixture. Adding unrelated synthetic defects would not be justified by AC-12. Network API remains explicitly unsupported. Full aggregate regression, report-bound runner, signer socket/receipt/gate, and POSIX-specific symlink behavior remain outside this focused run and are not upgraded by these results.

## Ownership and next step

The operator is accountable for the delegated S4 task; Codex executed this test-owner scope. Canonical records do not identify a VST service owner. A future denominator expansion needs a project decision that enumerates the supported public callable inventory; until then retain the current truthful `PARTIAL` state. Report-bound signer acceptance remains dependent on the WSL signer and run-manifest environment and must be owned by the runner/evidence workstream, not attributed to this local functional run.
