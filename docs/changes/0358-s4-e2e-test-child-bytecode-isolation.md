# Change 0358 — Prevent E2E test children from writing into the dependency target

## What changed

- `tests/qa/test_s4_e2e_runner_cli.py`: the `_run_cli` fixture now explicitly sets `PYTHONDONTWRITEBYTECODE=1` for its child runner process. This keeps imported locked packages from creating `.pyc` files in the external dependency target.
- Added `test_s4_e2e_child_runner_disables_dependency_bytecode`, which captures the child environment and asserts this setting is present.

## Why

The report-bound E2E run at candidate `b3fb7bc38aee308520e29091707e4c6cb3d46da1` changed its isolated dependency target. A read-only comparison found 111 extra `.pyc` files and no missing or changed locked wheel files. The executed `_run_cli` helper constructed a child environment without inheriting `PYTHONDONTWRITEBYTECODE`, while the child runner imported packages from that target. This test-only change closes that environment gap; it does not alter the production QA runner.

## Affected contracts and paths

- Test helper contract: E2E nested runner children must not mutate the exact-content wheel target through Python bytecode writes.
- `tests/qa/test_s4_e2e_runner_cli.py`
- `docs/qa/categories.json` will be regenerated in a separate commit after this test-source commit so its source inventory binds to the committed test file.

## Verification state

- Focused command: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_child_runner_disables_dependency_bytecode`
- Result: exit 0; 1 passed, 1 existing `pytest-asyncio` deprecation warning, 1.27 seconds.
- `git diff --check`: exit 0.
- Report-bound E2E and aggregate regression reruns are pending a clean exact candidate with a freshly generated registry and fresh dependency targets. The previous broad candidate reports remain historical evidence and are not upgraded by this change.

## Ownership and next action

- Accountable owner: Codex.
- Test author and executor: E2E runner.
- Next: commit this test source with this record, regenerate and separately commit the registry, then run focused and report-bound acceptance on the exact new candidate. Preserve the 52 policy-excluded selectors as `NOT_RUN`.

Agent-Attribution: e2e-runner (`gpt-6-luna`); Codex executor
