# Change 0369 — Refresh registry after the dependency-blocker assertion update

## What changed

- Regenerated `docs/qa/categories.json` after test commit `e3c3386b8b6eb622c896fb94f297b37e84152bd1`.
- Registry SHA-256: `4025e0ce72ada9eaf626336e7ed3e3947be966549257efbad43c49da6a05980c`.
- The registry still contains 963 selectors; 52 selectors remain without an allowed runtime profile. Windows E2E retains 58 runnable selectors and its explicit timeout/process-tree selector remains `NOT_RUN`.

## Why

Change 0368 updates the synthetic missing-dependency test assertion to match the current report-bound runner's deterministic inventory-verification reason while retaining its non-approval and no-child-command assertions. The registry source head and source inventory must bind that test commit before exact-candidate E2E reruns.

## Verification

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --write`
- Result: exit 0; `wrote docs/qa/categories.json`.
- Registry `source_head`: `e3c3386b8b6eb622c896fb94f297b37e84152bd1`.
- Parsed selector count: 963; profile-less count: 52; Windows E2E runnable count: 58.
- `git diff --check`: exit 0.
- Focused test execution was separate from registry generation: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_cli_reports_missing_dependency_without_fallback_or_child_invocation`; exit 0, 1 passed, 1 existing pytest-asyncio deprecation warning, 7.75 seconds. Fresh target SHA-256 before and after: `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84`.

## Acceptance still pending

- Rerun report-bound Windows E2E on a fresh exact candidate and dependency target at this registry commit. The prior exact-candidate run failed only the now-updated stale assertion; preserve its report as historical evidence.
- Keep the 52 profile-less policy selectors and the timeout/process-tree selector `NOT_RUN`.
- Run regression only after the E2E rerun is green.

## Ownership and next action

- Accountable owner: Codex.
- Registry generation: Codex.
- Next: commit this registry and record separately, then run the fresh exact-candidate E2E acceptance rerun.
