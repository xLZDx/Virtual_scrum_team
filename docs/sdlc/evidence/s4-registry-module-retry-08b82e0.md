# S4 focused registry module after bounded Git timeout retry

## Scope and exact revision

- Story/gate: S4 QA registry validation and AST cache (VST-032–037), changes 0151–0153.
- Code HEAD under test: `08b82e07bceb1bd928a5a02ac6ee9479854caf16` on `s4-native-qa-runner`.
- Before execution: `git status --short --branch` returned only `## s4-native-qa-runner`; worktree clean.
- After execution, before this evidence edit: same HEAD and same clean status.
- Environment: Windows; Python 3.14.3; pytest 8.4.2.

## Command and result

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py
```

Exit 0: **17 passed, 1 skipped, 0 failed**, 1 pytest-asyncio deprecation warning, 6.12s. The skip is the symlink-component case, unavailable on this Windows account because link creation returned `WinError 1314`. The committed-registry integration case passed; no Git timeout occurred. Both AST-cache regression cases passed.

This is Windows functional evidence at the exact code HEAD above. POSIX symlink behavior remains `NOT_RUN`; the skip does not establish that platform behavior.
