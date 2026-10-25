# S4 registry source-path functional evidence

## Scope and revisions

- Product/source baseline before the test work: `0baf9856a8a9231555ea335cc411df28592ca836` (clean).
- Test-source commit: `f7098d145e3af7d6a00eeae78209d973ce077afe` (`test(s4): reject noncanonical registry source paths`).
- Registry/category registration and exact run HEAD: `d5d2de80a4abaa18166dd595cf268759064b0c53` (`docs(s4): register registry path regression cases`).
- Worktree was clean before the exact-head run. Evidence documentation is committed afterward; it does not change the tested source or categories.

## Environment and command

- Shell: Windows PowerShell.
- Interpreter: `python`, Python 3.14.3.
- Pytest: 8.4.2.
- Command (run twice on the same clean HEAD after one transient retry):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py
```

## Results

- First invocation: 12 passed, 1 skipped, 1 failed. The existing real-registry loader test hit a bounded 5-second `git rev-parse --verify HEAD` subprocess timeout inside `_current_candidate_head`; it raised `ContractError: cannot identify the QA candidate HEAD`. No path regression failed.
- One exact repeat on the same unchanged clean HEAD: **13 passed, 1 skipped, 0 failed** in 8.32 seconds.
- The skip is the symlink-component scenario: Windows denied symlink creation with WinError 1314 (“A required privilege is not held by the client”). The assertion was not weakened. The test source covers both a linked file and linked directory when symlink creation is available.
- One global `pytest-asyncio` deprecation warning: `asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16.
- Symlink runtime behavior remains `NOT_RUN` on this host. Linux/WSL symlink execution is outside this focused functional run.

## Acceptance mapping

| Acceptance criterion | Test node(s) | Outcome |
|---|---|---|
| Reject traversal and canonicalization aliases before AST acceptance | `test_s4_registry_rejects_noncanonical_source_paths_before_ast_acceptance` (3 parametrized cases: `tests/../outside.py`, repeated slash, backslash) | All 3 passed |
| Reject symlink file and directory components before AST acceptance | `test_s4_registry_rejects_symlinked_source_components_before_ast_acceptance` | `NOT_RUN` by Windows symlink privilege skip |
| Reject a noncanonical registry selector even when the resolved outside file has a valid test AST | `test_s4_registry_loader_rejects_noncanonical_path_even_when_ast_target_exists` | Passed |
| Preserve existing S4 registry, provenance, projection and seeded-failure contracts | Remaining selectors in `tests/qa/test_s4_registry_contracts.py` | Passed in final repeat; first attempt had transient HEAD subprocess timeout |

Registered API category IDs: 3 new selector IDs; pytest collects the path-alias selector as 3 cases. Focused module total: 14 collected cases.

## Limitations and ownership

- The first failure is retained as observed evidence; the single repeat passed and did not motivate a product-code change.
- No product source was changed in this task. Technical owner for the registry trust boundary is not separately named in canonical ownership records. Accountable task owner: operator under delegated S4 work; executor: Codex.
- Native POSIX symlink behavior and broader signer/report/sandbox acceptance are not established by this run.
