# S4 registry compact index and aggregate resource-budget evidence

## Scope and exact revision

- Story/gate: S4 QA registry validation and resource bounds (VST-032–037), source change 0155.
- Code HEAD under test: `6903b7bf3e3dd4fc1281412c173fb82db9924d11` on `s4-native-qa-runner`.
- Before execution: `git status --short --branch` returned only `## s4-native-qa-runner`; clean.
- After execution, before this evidence edit: same HEAD; only `tests/qa/test_s4_registry_contracts.py` was modified with the three new tests.
- Environment: Windows; Python 3.14.3; pytest 8.4.2.

## Targeted resource-contract run

Command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py -k 'parses_shared_test_source_once_per_load or rejects_aggregate_test_source_budget_overflow or rejects_more_than_2048_ids_before_node_resolution'
```

Exit 0: **3 passed, 17 deselected**, 1 pytest-asyncio deprecation warning, 1.26s.

- The compact shared-source fixture resolves two module functions and one class method, with one source read and one AST parse.
- Five distinct 900 KiB sources cross the 4 MiB aggregate limit; `load_registry` raises the explicit aggregate-limit `ContractError` after five bounded reads and four parses.
- 2,049 test IDs are rejected at the 2,048-ID limit before node resolution is called.

## Full focused module

Command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py
```

Exit 0: **19 passed, 1 skipped, 0 failed**, 1 pytest-asyncio deprecation warning, 6.96s. The skip is the symlink-component case because Windows link creation returned `WinError 1314`. The committed-registry integration test passed; no Git timeout occurred.

This is Windows functional evidence at the exact code HEAD above. POSIX symlink behavior remains `NOT_RUN`.
