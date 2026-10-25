# S4 provenance regression exact-head rerun

## Revisions and environment

- Previous product code-fix commit: `9bb94b3c76c9ce8e5bb8c5c3e790c04382a92bc8`.
- Test-message correction commit: `921886d7f26126695adfc26d264e772052f8ac09`.
- Registry source pin commit: `56a58a72c337c7c712ce2efb72e99efc179552bd`.
- Exact run HEAD: `56a58a72c337c7c712ce2efb72e99efc179552bd`.
- Before and after status: clean; before and after HEAD were identical.
- Shell: Windows PowerShell; Python 3.14.3; pytest 8.4.2.

## Exact command

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py
```

## Result

- **15 passed, 1 skipped, 0 failed** in 8.97 seconds; process exit code 0.
- The symlink-component test was skipped because Windows denied symlink creation with WinError 1314 (“A required privilege is not held by the client”). Symlink runtime remains `NOT_RUN` on this host.
- One global warning: pytest-asyncio reports `asyncio.get_event_loop_policy` deprecated and scheduled for removal in Python 3.16.
- `test_s4_committed_registry_loads_with_resolved_nodes` passed. This confirms the exact committed-registry load no longer fails on the valid source-head commit-existence path previously observed at `64b8bb1`.
- `test_s4_registry_rejects_provenance_outside_candidate_history` passed after changing only its expected typed error wording from `stale or outside` to `missing, stale, or outside`. The rejection assertion remains intact.
- New source-bound and recursion regressions and existing path confinement cases passed.

## Historical results retained

- At `64b8bb1`, the module had two NOT_PASS runs: each 14 passed, 1 skipped, 1 failed because existing source-head Git objects were reported missing by the separate existence helper. Direct `git cat-file` proved both objects existed; change record 0145 preserves those runs.
- At `9bb94b3`, the committed-registry loader passed, but one stale test expectation failed because the product intentionally changed its typed provenance message. This was corrected in test-only commit 0147 and is not erased by this successful run.

## Acceptance map and limits

| Criterion | Test(s) | Result |
|---|---|---|
| Load actual committed registry and resolve registered selectors | `test_s4_committed_registry_loads_with_resolved_nodes` | PASS |
| Reject stale/out-of-history provenance with typed refusal | `test_s4_registry_rejects_provenance_outside_candidate_history` | PASS |
| Reject source traversal and path aliases | traversal/repeated-slash/backslash cases and loader escape test | PASS |
| Reject oversized source before AST parse and treat recursion as unresolved | bounded-source and `RecursionError` tests | PASS |
| Reject symlinked file/directory components | symlink test | `NOT_RUN` on Windows (WinError 1314) |

This run proves only the focused functional module on the exact Windows HEAD above. It does not establish the WSL transfer, signed runner/report, authoritative gate, or broader sandbox acceptance.
