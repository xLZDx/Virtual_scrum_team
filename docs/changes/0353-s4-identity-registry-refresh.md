# Change 0353 — Refresh S4 identity selector provenance

## What changed

Regenerated `docs/qa/categories.json` after the AC-16 identity fixture change. The registry now binds the identity test content and source inventory to commit `96c9c1556e0bd7d7731bbfba40806c4d1e209907`.

## Why

The prior manifest was bound to test source `4d4341e4812ba726c0b35e83ee2fad0a3fb5a7f1`. The test fixture now creates the AF_UNIX socket in a short unique `/tmp` directory so pytest's deep scratch path cannot exceed the kernel socket path limit. The manifest must identify the corrected test source before any new report-bound run.

## Affected contract and paths

- S4 selector registry provenance and source digest: `docs/qa/categories.json`.
- AC-16 identity selector remains assigned only to `wsl-ubuntu-24.04-cpython-3.12.3`.
- Regression membership and all policy `NOT_RUN` reasons are unchanged.

## Verification state

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`.
- Registry SHA-256: `9d232d33cd9b788fe5e4418b010ca0a7a29ee9cc1e2b81dd1e88ca72e3601b70`.
- Tests: `NOT_RUN` for this registry refresh. The designated test roles must execute after coding is complete.
- The previous report-bound identity result remains `FAIL` at its older source head; a fresh exact-head rerun is pending.

## Provenance

- Registry source head: `96c9c1556e0bd7d7731bbfba40806c4d1e209907`.
- Executor: Codex in the canonical checkout `D:\Repo\Virtual_scrum_team`.
