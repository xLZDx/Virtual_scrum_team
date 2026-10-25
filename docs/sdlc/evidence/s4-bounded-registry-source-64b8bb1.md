# S4 bounded registry source resolution evidence

## Scope and revisions

- Product-fix baseline specified by coordinator: `6a4f2ec441938da6c0a7d62c03c15b63774963e1`.
- Test source commit: `ad6ddb075b2a9f2beefcf2595bd47c9bbcd1650a`.
- Category registration and exact test-run HEAD: `64b8bb1f2d847ce3ba33fafb1a75e7b2e81b71b7`.
- Worktree was clean before the focused run and remained unchanged during both runs. The evidence commit is subsequent and contains documentation only.

## Environment and command

- Shell: Windows PowerShell.
- Interpreter: `python`, Python 3.14.3.
- Pytest: 8.4.2.
- Exact command, executed twice at the same HEAD:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py
```

## Results

- First run: 14 passed, 1 skipped, 1 failed. The real committed-registry loader rejected the top-level source provenance with `ContractError: QA registry source_head must be a full lowercase Git SHA`. The referenced commit object was verified afterward with `git cat-file -e 'ad6ddb075b2a9f2beefcf2595bd47c9bbcd1650a^{commit}'` and existed. The exact underlying subprocess condition was not captured; `registry._git_commit_exists` returns `False` both for command failure and its 5-second timeout.
- One same-head retry: 14 passed, 1 skipped, 1 failed. This time the loader raised `ContractError: QA registry category 'functional' needs a full source_head` for `4913425c9327b2416ac7cc1e421268223ee43ae1`. A direct `git cat-file -e '4913425c9327b2416ac7cc1e421268223ee43ae1^{commit}'` confirmed the object exists. The exact underlying subprocess condition was not captured.
- Per coordinator instruction, no further retries were run after the same real-loader failure recurred. The module is therefore **not green**; registry runtime acceptance is blocked pending investigation/fix by the product owner.
- Both new functional cases passed in both runs. Canonical traversal/repeated-separator/backslash rejection and registry-loader escape rejection also passed.
- The existing symlink-component case skipped with Windows WinError 1314 (“A required privilege is not held by the client”). Symlink behavior remains `NOT_RUN` here.
- One global `pytest-asyncio` warning: `asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16.

## Test-to-criterion mapping

| Criterion | Test node(s) | Result |
|---|---|---|
| Reject test source larger than 1 MiB before AST parsing | `test_s4_registry_rejects_test_source_over_one_mib_before_ast_parse` | Passed in both runs; asserts `ast.parse` was never called |
| Treat parser `RecursionError` as unresolved | `test_s4_registry_treats_recursion_error_during_ast_parse_as_unresolved` | Passed in both runs |
| Retain canonical path confinement | traversal/repeated slash/backslash parameterized test; symlink test; registry-level traversal test | String and loader cases passed; symlink execution skipped on Windows |
| Load the committed registry and resolve all declared test IDs | `test_s4_committed_registry_loads_with_resolved_nodes` | Failed twice due source-head commit validation returning false for objects proven present by direct `git cat-file` |

The module collected 16 cases: 14 passed, 1 skipped, and 1 failed on each invocation.

## Limits and ownership

- No product source was changed by the functional-test owner.
- The focused suite did not establish a green committed-registry runtime result. The observed exception is known; whether its helper subprocess timed out or returned another nonzero status is `UNKNOWN` because that helper suppresses stderr and maps both conditions to `False`.
- Symlink runtime validation needs an environment permitted to create symlinks. No POSIX test run is claimed.
- Technical ownership of the QA registry implementation is not separately identified in canonical ownership records. Accountable task owner: operator under delegated S4 work; executor: Codex.
