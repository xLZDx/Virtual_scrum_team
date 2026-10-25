# S4 registry AST cache functional evidence

## Scope and acceptance

- Story/gate: S4 QA registry source-node validation (VST-032–037), change 0151.
- Acceptance: within one registry load, two distinct pytest node IDs in one source file cause only one source read and one AST parse; an oversized source remains a non-match and is read at most once when multiple IDs refer to it.
- Code HEAD under test: `93cd3c334c66683a379ca594215eaa3f5507bfd8` (`s4-native-qa-runner`). The two new test cases were uncommitted working-tree additions during execution; they are included in the test-evidence commit that links this record.
- Environment: Windows, Python 3.14, pytest 8.4.2 (from the run environment/plugin output).

## Targeted acceptance run

Command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py -k 'parses_shared_test_source_once_per_load or caches_oversized_source_as_fail_closed'
```

Result: exit 0; **2 passed, 16 deselected**, 1 pytest-asyncio deprecation warning, 1.05s. Both acceptance cases passed.

## Full focused module

The exact full-module command was run three times after adding the tests. Latest result:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py
```

Result: exit 1; **16 passed, 1 skipped, 1 failed**, 1 warning, 7.76s. The skip is Windows symlink creation unavailable (`WinError 1314`). The unrelated committed-registry integration test failed closed because `_current_candidate_head`'s bounded `git rev-parse --verify HEAD` subprocess timed out after 5 seconds. Earlier full-module attempts likewise had bounded Git subprocess timeouts (the first had a tracked-file helper timeout); a direct helper call outside pytest returned true. New AST-cache tests passed in all three full-module attempts.

The exact timeout and fail-closed trace are retained in the test-run output from this session. This module is **NOT_PASS** overall, despite the targeted regression acceptance passing. No product source was changed by the test owner.
