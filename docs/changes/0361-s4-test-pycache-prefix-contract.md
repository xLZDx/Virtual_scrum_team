# Change 0361 — Test cache-prefix isolation for nested QA runners

## What changed

- `tests/qa/test_s4_e2e_runner_cli.py`: the `_run_cli` child environment now assigns its Python bytecode cache prefix under that test's `tmp_path`.
- The child-environment assertion verifies that prefix is rooted under the per-test temporary directory and outside the dependency target.
- The existing `_pytest_command` construction test now checks that each test run's bytecode prefix is under its `scratch_run` directory and outside the dependency target, for both one-selector and 1,000-selector cases.

## Why

Report-bound E2E and regression runs at `b3fb7bc38aee308520e29091707e4c6cb3d46da1` changed a fresh wheel target from 495 expected files to 606 actual files. Read-only inventory found 111 extra `.pyc` files, with zero missing or changed locked files. The test helper builds a restricted child environment, so the outer cache prefix did not reach nested CLI processes. A report-bound diagnostic with an in-memory prefix only on the outer pytest child still failed target verification; its report row SHA-256 was `b5b30d4a7ca1dcfbb5bf3d39905df7a6cb6b3779ce3328921b219efbf5e173dd`, and the isolated cache-prefix directory had zero files. The nested helper therefore needs its own scratch-rooted prefix.

Production-side propagation is implemented separately in change 0360 (`tools/qa/run.py`); this commit adds the test-side assertion for both propagation paths.

## Focused verification

- Command: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_child_runner_disables_dependency_bytecode tests/qa/test_s4_e2e_runner_cli.py::test_s4_pytest_argv_size_depends_on_source_files_not_selector_count`
- Result: exit 0; 2 passed, 1 warning, 1.11 seconds.
- Warning: existing `pytest-asyncio` deprecation at `C:\Users\koros\AppData\Roaming\Python\Python314\site-packages\pytest_asyncio\plugin.py:1216`, where `asyncio.get_event_loop_policy` is deprecated and slated for removal in Python 3.16.
- `git diff --check`: exit 0.

## Acceptance still pending

- Exact-candidate report-bound E2E and regression reruns have not been performed after production change 0360 and these test assertions. Run both only after the separate test-source and registry commits are current, using fresh dependency targets.
- Preserve all 52 selectors without an allowed runtime profile as `NOT_RUN`. The prior report-bound E2E/regression FAIL rows and target inventory diffs remain preserved historical evidence.

## Ownership

- Accountable owner: Codex.
- Test author: E2E runner.
- Production implementation: Codex (change 0360).
- Next: commit this test file with this record, regenerate and separately commit the registry, then execute report-bound E2E and regression at the exact committed candidate.
