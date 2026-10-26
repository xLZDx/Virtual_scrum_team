# S4 identity-category functional tests — 2026-10-26

## Binding

- Repository: `D:\Repo\Virtual_scrum_team`.
- Exact repository HEAD: `f3677a98f7b51bc1646aea4e43b2443ce338ba3f`.
- Registry source head: `4d4341e4812ba726c0b35e83ee2fad0a3fb5a7f1`.
- Runtime: Windows CPython 3.14.3 at `C:\Python314\python.exe`.
- Executor: designated `functional-test-reviewer`.

## Command and result

```powershell
C:\Python314\python.exe -m pytest -q tests/qa/test_s4_functional_runner_contracts.py::test_s4_registry_accepts_real_committed_selector_denominator tests/qa/test_s4_functional_runner_contracts.py::test_s4_registry_rejects_non_singleton_identity_category tests/qa/test_s4_functional_runner_contracts.py::test_s4_runner_accepts_identity_category_fixed_artifact_paths tests/qa/test_s4_functional_runtime_matrix.py::test_s4_matrix_requires_identity_report_only_for_unprivileged_wsl
```

- Exit code: `0`.
- Result: `4 passed, 1 warning` in `10.78s`.
- Warning: pytest-asyncio deprecation about `asyncio.get_event_loop_policy`.
- Selectors: registry singleton/regression exclusion, non-singleton rejection, fixed category/artifact paths, and unprivileged WSL-only matrix binding.

## Acceptance boundary

These are focused local functional contract results. They do not prove WSL helper compilation or installation, AC-16 runtime identity isolation, AC-17 dependency target verification during an actual category run, seeded-failure report-bound behavior, or the 52 policy-excluded scenarios. Those remain pending or `NOT_RUN`.
