# 0138 S4 registry source-path regression tests

## What changed

- Added focused functional regressions for traversal (`tests/../...`), repeated separators, backslash paths, and symlinked file/directory components.
- Added a registry-loader regression proving a syntactically valid test outside `tests/` is rejected before its AST selector can be accepted.
- No product source was changed.

## Why

The source-path confinement implementation in change 0137 needs direct negative coverage. Merely confirming an invalid path string is rejected would not prove that traversal or symlink resolution cannot reach a valid AST outside the repository's canonical `tests/` tree.

## Affected contracts and paths

- `tests/qa/test_s4_registry_contracts.py`: direct path resolution and registry-loader rejection coverage.
- `docs/qa/categories.json`: API category registration is a separate follow-up commit after this source commit, so provenance can point to a commit containing these test nodes.

## Verification state

- Test source is authored; execution is intentionally pending the subsequent category-registration commit and clean exact-head focused run.
- Symlink case will report `NOT_RUN` as a skip if the host cannot create symlinks; the test will not weaken its assertions.

## Ownership and next steps

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for this registry trust boundary is not separately named in repository ownership records.
- Commit these tests, register their exact node IDs with source provenance pinned to this commit, then run the focused registry module and record evidence.
