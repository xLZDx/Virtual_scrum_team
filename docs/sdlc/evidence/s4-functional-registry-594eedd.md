# S4 focused functional/API/registry evidence

## Run identity

- Candidate HEAD: `594eeddcd1f6409928e7eebb1e9f8581c8eba75c`
- Worktree: clean before the run; no bytecode or pytest cache writes enabled.
- OS/shell: Windows PowerShell.
- Python: `3.14.3`
- pytest: `8.4.2`
- Exact command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py`
- Result: **9 passed, 0 failed**, in `5.25s`.
- Warning: one deprecation warning from the globally installed `pytest-asyncio` plugin (`asyncio.get_event_loop_policy`); this module has no asyncio tests.

## Test-to-acceptance map

| Test ID | Contract observed | S4 acceptance |
|---|---|---|
| `tests/qa/test_s4_registry_contracts.py::test_s4_registry_accepts_single_primary_category_per_test_id` | A valid synthetic registry accepts unique primary IDs and its returned hash matches the exact registry bytes. | AC-1, AC-3 |
| `tests/qa/test_s4_registry_contracts.py::test_s4_committed_registry_loads_with_resolved_nodes` | The actual repository registry loads with real tracked-file checks, actual Git ancestry, statically resolvable pytest node IDs, and a byte digest. | AC-1, AC-3, AC-8 |
| `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_duplicate_primary_category_assignment` | Reusing one node under two primary categories raises the contract error before an accepting registry is returned. | AC-1 |
| `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_provenance_outside_candidate_history` | A registry source commit outside the candidate's ancestry is rejected. | AC-3 |
| `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_unknown_pytest_node_id` | A tracked test file with a nonexistent node function is rejected. | AC-1 |
| `tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_supported_category_without_required_ids` | A supported category with an empty required-ID list is rejected. | AC-1, AC-5 |
| `tests/qa/test_s4_registry_contracts.py::test_s4_registry_manifest_projection_requires_exact_ids_and_commands` | The exact category-to-manifest ID set and pinned pytest argv are accepted; a stale ID is rejected. | AC-2, AC-3, AC-4, AC-5, AC-7 |
| `tests/qa/test_s4_registry_contracts.py::test_s4_seeded_failure_catalog_rejects_hash_mismatch` | A fixture whose canonical input digest does not match is rejected. | AC-12, AC-14 |
| `tests/qa/test_s4_registry_contracts.py::test_s4_seeded_failure_rejects_invalid_manifest_and_records_observation` | The committed fixture loads; unchanged `validate_task_manifest` rejects the malformed v2 input with the expected missing-fields context; the plugin records matching fixture ID, hash, expected/observed code, and executing node ID. | AC-12 |

## Limits

- This is focused local Windows functional/API evidence, not pinned native-runner evidence. The named `Ubuntu-24.04` WSL distribution reports CPython `3.12.3` and pytest `7.4.4`, but its `/mnt/d` mount is empty. The S4 transfer path also requires a pre-provisioned private destination root, runner account, worker group, and trusted signer socket; those values are not available in this checkout. Native S4 execution is `NOT_RUN`.
- The module does not prove the S4 report/signing/gate pipeline, category CLI execution, or sandbox acceptance. E2E placeholder tests cover only local slice and refusal behavior. Those remaining category paths stay `NOT_RUN` or `UNSUPPORTED` in the acceptance record.
- No package was installed. No full suite, build, lint, typecheck, CI, migration, mutation, or external-service test was run.
