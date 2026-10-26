# Change 0364 — Pass the verified wheelhouse in nested QA runner tests

## What changed

- `tests/qa/test_s4_e2e_runner_cli.py`: the synthetic candidate baseline now archives source commit `7929bc01d8f0a09975e319c8357c6497b9aba04e`, which contains the pytest cache-prefix fix. `_run_cli` requires `VST_QA_DEPENDENCY_WHEELHOUSE`, fails clearly if it is absent, and passes its value using `--dependency-wheelhouse`. The child-runner contract test checks both the missing-variable failure and the exact CLI argument.
- The E2E `_pytest_command` contract test checks that the validated wheelhouse path reaches its child environment.
- `tests/qa/test_s4_functional_report_contracts.py` and `tests/qa/test_s4_functional_runner_contracts.py`: all `_pytest_command` call sites now supply a scoped temporary wheelhouse path; the report contract asserts the environment handoff.

## Why

The synthetic E2E candidate archives the runner at `BASELINE_HEAD`. Before this change, it archived obsolete runner commit `fc20c9e31e1d4bb9bd9356921add66e14e5e230a`; that runner had no cache-prefix assignment. Updating the fixture to production commit `7929bc0` exposed a required `--dependency-wheelhouse` CLI option. The preceding nested invocation failed during argument parsing before running its selector because `_run_cli` omitted that option. The parent report-bound runner now passes its already verified wheelhouse path to the pytest child through `VST_QA_DEPENDENCY_WHEELHOUSE` (production handoff in change 0363); this test change consumes it without introducing another dependency source or network/install behavior.

## Focused verification

- Source HEAD before this test change: `577fc5e53515c65b8ea7fe84d7f13da02ecc73a5` (`fix(qa): pass verified wheelhouse to test child`). Test files were uncommitted during verification.
- Command: `$env:PYTHONDONTWRITEBYTECODE='1'; C:\Python314\python.exe -m pytest -q tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_child_runner_disables_dependency_bytecode tests/qa/test_s4_e2e_runner_cli.py::test_s4_pytest_argv_size_depends_on_source_files_not_selector_count tests/qa/test_s4_functional_report_contracts.py::test_s4_runner_command_selection_is_exact_and_does_not_install_packages tests/qa/test_s4_functional_report_contracts.py::test_s4_runner_rejects_empty_selector_invocation tests/qa/test_s4_functional_runner_contracts.py::test_s4_pytest_command_bounds_argv_for_hundreds_of_selectors`
- Result: exit 0; 5 passed, 1 warning, 1.04 seconds.
- Warning: existing `pytest-asyncio` deprecation at `C:\Users\koros\AppData\Roaming\Python\Python314\site-packages\pytest_asyncio\plugin.py:1216`: `asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16.
- `git diff --check`: exit 0.

## Acceptance still pending

- The five focused contract tests do not prove nested collection or report-bound acceptance. After this test commit and a separate registry refresh/commit, run the approved nested collection selector, then report-bound E2E on a fresh exact candidate and fresh dependency target.
- Keep all 52 policy-excluded selectors `NOT_RUN`; do not infer a report-bound result from the focused unit tests.

## Ownership and next action

- Accountable owner: Codex.
- Production handoff: Codex, change 0363.
- Test author and executor: designated E2E runner.
- Next: commit these three test files with this record, regenerate and separately commit the selector registry, then perform the approved fresh-target report-bound E2E run.
