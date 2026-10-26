# Change 0370: Refresh stale S4 QA test fixtures for current contracts

## What changed

Updated four S4 test modules to satisfy the committed identity, wheelhouse, locked-wheel, and schema-v3 report contracts:

- `test_s4_dependency_provenance.py` copies the committed identity selector source into its synthetic candidate.
- `test_s4_functional_root_harness.py` supplies `dependency_wheelhouse` and asserts it is propagated to the child runner.
- `test_s4_functional_runner_contracts.py` tests missing wheel selection through `prepare_dependency_target`, supplies the wheelhouse argument to runner fixtures, and stubs valid dependency evidence so the wrong-interpreter test isolates the interpreter gate. It still requires BLOCKED, an empty command, and no child invocation.
- `test_s4_functional_runtime_matrix.py` uses a valid locked pytest fixture, includes the required WSL identity report reference, and provides schema-v3 dependency evidence derived from the lock.

No production source changed. No pass condition was weakened.

## Why

At exact source/registry HEAD `dd50fa5a0f7320d71a90fade64d685322536f1c0`, the Windows regression reported 16 failed selector IDs and 18 concrete failed cases. A focused diagnostic reproduced 13 of those failures. Tracebacks showed stale test fixtures: a synthetic candidate omitted the committed identity module, namespaces lacked the new wheelhouse argument, tests called removed dependency helpers, and matrix fixtures used an invalid lock header or old report schema. The five S2 lifecycle selector failures were not reproduced in that focused diagnostic; they remain unresolved and are not reclassified as passes.

## Verification

The E2E runner executed the focused set of 11 QA selectors; parameterization expanded them to 13 items:

- Exact command: `D:\Temp\vst-s4-fixture-fix-focused-evidence-20261026-dd50fa5-r2\command.txt`.
- Source candidate before the test edits: `dd50fa5a0f7320d71a90fade64d685322536f1c0`.
- Result: exit 0, 13 passed in 26.68 seconds, no warnings.
- Environment: Windows 11, CPython 3.14.3, pytest 9.0.3; offline wheelhouse `D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse`; pytest cache disabled.
- Dependency target SHA-256 before and after: `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84`.
- Focused stdout SHA-256: `2CD256C9169ACBE4FE527CA27BF2F98E92D537CCD3B398507E0AC6392E3759A7`; stderr empty.
- Evidence: `docs/sdlc/evidence/s4-regression-fixture-focused-diagnostic-20261026.md`.

The focused pass covers fixture corrections only. The five S2 lifecycle failures remain unresolved pending the next full regression. The full report-bound regression has not been rerun at a registry that binds these test changes. The 52 policy-excluded selectors remain `NOT_RUN`.

## Next action

Codex regenerates and commits the selector registry separately, then the E2E runner performs the authorized full regression on a fresh exact-head candidate and dependency target. Reconcile the five S2 lifecycle selectors from that report; preserve all policy `NOT_RUN` rows.

## Ownership

Accountable task owner: operator under the delegated sprint request. Implementation and local Git: Codex. Focused test execution: designated E2E runner.
