# Change 0368 — Match the missing-dependency E2E assertion to the runner reason

## What changed

- `tests/qa/test_s4_e2e_runner_cli.py`: the missing-dependency fixture now asserts the stable dependency-verification reason emitted by the current report-bound runner: `dependency target inventory differs from the locked wheel inventory`.
- Existing assertions that the nested runner command is empty and `exit_code` is `None` remain unchanged, preserving the no-child-invocation and non-approving behavior checks.

## Why

The exact-candidate report-bound E2E run correctly blocked a synthetic candidate with an empty dependency target before invoking pytest. The test then failed because it expected the older message `locked QA dependencies are missing or mismatched`, while the current runner reports `locked QA dependency content verification failed: dependency target inventory differs from the locked wheel inventory`. The observed behavior satisfied the intended contract; the test's message assertion had drifted. This is a test defect, not a product or environment failure.

## Failure evidence

- Exact candidate: `92f69607f6afc748b5eca7978b8e76d338f79920`; registry SHA-256 `5d62689a72a77237173b9c58cd1329bfde78ee5999250a74d8660fb2cf96abd5`.
- Exact runner command: `C:\Python314\python.exe -m tools.qa.run --category e2e --repo-root D:\Temp\vst-s4-wheelhouse-focused-candidate-20261026-92f6960 --manifest docs/qa/categories.json --fixtures docs/qa/fixtures.json --dependency-target D:\Temp\vst-s4-wheelhouse-e2e-target-20261026-92f6960 --dependency-wheelhouse D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse --scratch-root D:\Temp\vst-s4-report-bound-e2e-scratch-20261026-92f6960 --run-id s4-e2e-20261026-win-92f6960-r1 --expected-head 92f69607f6afc748b5eca7978b8e76d338f79920 --report-path docs/sdlc/evidence/qa/e2e.report.jsonl --stdout-path docs/sdlc/evidence/qa/e2e.stdout.txt --stderr-path docs/sdlc/evidence/qa/e2e.stderr.txt`.
- Runner process environment: `PYTHONDONTWRITEBYTECODE=1`; `PYTHONPYCACHEPREFIX=D:\Temp\vst-s4-report-bound-e2e-scratch-20261026-92f6960\controller-pycache`.
- Report-bound run: `s4-e2e-20261026-win-92f6960-r1`, Windows CPython 3.14.3, 58 expected E2E selectors. Result `FAIL`: 57 selector IDs passed and one failed; the explicit timeout/process-tree selector remained `NOT_RUN`. Pytest expanded parameterized selectors into 62 executed concrete node IDs. No unexpected candidate changes were reported.
- Failing selector: `tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_cli_reports_missing_dependency_without_fallback_or_child_invocation`.
- Failing assertion before this change: `assert any("locked QA dependencies are missing or mismatched" in reason for reason in report["reasons"])`.
- Inner synthetic report: `D:\Temp\vst-s4-report-bound-e2e-scratch-20261026-92f6960\s4-e2e-20261026-win-92f6960-r1\pytest-of-unknown\pytest-0\test_s4_e2e_cli_reports_missin0\candidate\docs\sdlc\evidence\qa\e2e.report.jsonl`. It records `BLOCKED`, the exact nested reason above, `command: []`, `exit_code: null`, and `dependency_content_verified_before: false`.
- Parent report row SHA-256: `a38115f8f2711895e8e16c5ea1cc6349ce21fecbe0fe468930c00f469b5933d1`.
- Full appended report SHA-256: `8426528d7a6793bd3f3e5dec047c48d34aff955f68f0ba37fb7f1dbdf2bb1990`.
- Preserved raw files: `D:\Temp\vst-s4-report-bound-e2e-evidence-20261026-92f6960\e2e.report.jsonl`, `e2e.stdout.txt`, and `e2e.stderr.txt`. Their full-file SHA-256 values are respectively `8426528d7a6793bd3f3e5dec047c48d34aff955f68f0ba37fb7f1dbdf2bb1990`, `69c5b560f911fd47832ce6ad5bc8721a8f732c1c26b1ee0a7b7797938108772e`, and `a528b1e4d996e9b60eccbc8a0592358d1272e47b0eedcbdee4f448ee8777562b`.
- Locked target SHA-256 was `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84` before and after the run. Dependency content was verified both times.

## Verification still required

- This test-only assertion update has not yet been run. Rerun the E2E category only after this test commit and a separate registry refresh commit, using a fresh exact candidate and target.
- Keep the 52 profile-less policy selectors and the explicit timeout/process-tree selector `NOT_RUN`.
- Run regression only after the E2E category is green and registry filtering continues to exclude those policy selectors.

## Ownership and next action

- Accountable owner: Codex.
- Test author: designated E2E runner.
- Next: commit this test assertion and record, regenerate/commit the registry separately, then rerun the report-bound E2E category on a fresh exact candidate and target.
