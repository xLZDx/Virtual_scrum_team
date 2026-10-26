# S4 regression fixture diagnostic and focused verification

## Scope and identity

- Repository: `D:\Repo\Virtual_scrum_team`.
- Source `HEAD`: `dd50fa5a0f7320d71a90fade64d685322536f1c0`.
- The focused run used the current worktree test edits, which were uncommitted at
  execution time. It is therefore source-level verification, not report-bound
  acceptance for a committed candidate.
- The prior registry SHA-256 is
  `4025e0ce72ada9eaf626336e7ed3e3947be966549257efbad43c49da6a05980c`; it is stale
  for the edited test sources and must be regenerated before a report-bound run.
- Runtime: Windows 11, CPython 3.14.3, pytest 9.0.3, pluggy 1.6.0.
- Isolated dependency target:
  `D:\Temp\vst-s4-diagnostic-target-20261026-dd50fa5-r1`.
- Target SHA-256 before and after: `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84`.
- Dependency lock SHA-256: `6e23fdd343a14e9d85a27f6d86cfb4498c1af9d33281e05ca5a3ff331c45e691`.
- Wheelhouse: `D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse`.

## Original regression and diagnostic findings

The report-bound Windows regression was run as
`s4-regression-20261026-win-dd50fa5-r1`. It reported 18 failed concrete cases
across 16 selector IDs, 1,828 passed, and 38 deselected. Its report row SHA-256
was `50409375529be029a57e94ec762dc447dcdc0b9b58bee4473237e0b66fb81bc7`; full
report SHA-256 was
`ad8851f929dcea482c6e9e0488533b56b2abf706057791bf1be89bfcb64bd292`. Its captured
output did not include failure tracebacks.

A direct diagnostic ran those 16 selector IDs, including all three parameter
variants. It produced 13 failures and 5 passes. The failures were caused by stale
synthetic fixtures and test expectations:

| Selector group | Exact failure evidence | Update made |
| --- | --- | --- |
| `test_s4_runner_reports_post_execution_dependency_mutation` | Synthetic candidate failed registry preflight: `identity test module must contain exactly the committed identity selector`; expected exit 1, observed exit 2. | Added the committed identity selector source to that synthetic candidate. |
| `test_s4_root_harness_child_binds_mount_and_parent_proof_then_launches_qa_through_setpriv` | Root harness received a synthetic `Namespace` without `dependency_wheelhouse` (`tools/qa/root_harness.py:270`). | Added the field, supplied it to the invalid-CLI fixture, and asserted child-command propagation. |
| `test_s4_main_persists_blocked_when_final_git_status_fails_after_pytest_passes` | Test patched the removed `_installed_versions` symbol. | Stubbed current `verify_dependency_environment` evidence while preserving the final-status BLOCKED assertions. |
| `test_s4_main_reports_wrong_interpreter_as_blocked_without_spawning_pytest` | Synthetic `Namespace` lacked `dependency_wheelhouse` (`tools/qa/run.py:179`). | Supplied the required path and valid dependency evidence so the test isolates the interpreter gate. It still asserts BLOCKED, no command, and zero child invocations. |
| `test_s4_runner_identifies_missing_locked_distribution` | Test called removed `run._installed_versions`. | Asserted current preparation rejects a locked pytest wheel missing from the wheelhouse and leaves the target uncreated. |
| `test_s4_matrix_accepts_report_with_matching_candidate_and_profile_bindings` (Windows, WSL user, WSL root variants) | The synthetic lock failed header validation at `tools/qa/dependencies.py:68`. | Replaced invalid lock bytes and populated schema-3 dependency evidence from the synthetic lock manifest. |
| `test_s4_matrix_normalizes_crlf_lock_and_rejects_bare_carriage_return` | The same invalid lock header failed before the CRLF contract was reached. | Uses the valid synthetic lock. |
| `test_s4_matrix_refuses_root_proof_bound_to_another_candidate` | The same invalid lock header failed before the candidate-proof assertion was reached. | Uses the valid synthetic lock. |
| `test_s4_matrix_refuses_root_proof_bound_to_another_helper_digest` | The same invalid lock header failed before the helper-proof assertion was reached. | Uses the valid synthetic lock. |
| `test_s4_matrix_rejects_missing_profile_report_references` | Fixture registry had no identity profile; `_expected_report_refs` raised `identity category must require exactly one unprivileged WSL profile report` (`tools/qa/matrix.py:64`). | Added the exact identity selector to the WSL-only profile map; missing-report assertion remains. |
| `test_s4_matrix_rejects_stale_candidate_and_corrupt_artifact_range` | The same invalid lock header failed before stale-head/range assertions were reached. | Uses the valid synthetic lock. |

The five S2 lifecycle selectors passed in the direct diagnostic but were reported
failed in the earlier broad regression. This discrepancy is unresolved; the broad
report remains authoritative evidence of those failures until the next full
regression checks them. No flake classification is made.

## Focused verification after fixture updates

Command, from `D:\Repo\Virtual_scrum_team`:

```text
C:\Python314\python.exe -m pytest -vv --tb=long -ra --show-capture=all -p no:cacheprovider tests/qa/test_s4_dependency_provenance.py::test_s4_runner_reports_post_execution_dependency_mutation tests/qa/test_s4_functional_root_harness.py::test_s4_root_harness_child_binds_mount_and_parent_proof_then_launches_qa_through_setpriv tests/qa/test_s4_functional_runner_contracts.py::test_s4_main_persists_blocked_when_final_git_status_fails_after_pytest_passes tests/qa/test_s4_functional_runner_contracts.py::test_s4_main_reports_wrong_interpreter_as_blocked_without_spawning_pytest tests/qa/test_s4_functional_runner_contracts.py::test_s4_runner_identifies_missing_locked_distribution tests/qa/test_s4_functional_runtime_matrix.py::test_s4_matrix_accepts_report_with_matching_candidate_and_profile_bindings tests/qa/test_s4_functional_runtime_matrix.py::test_s4_matrix_normalizes_crlf_lock_and_rejects_bare_carriage_return tests/qa/test_s4_functional_runtime_matrix.py::test_s4_matrix_refuses_root_proof_bound_to_another_candidate tests/qa/test_s4_functional_runtime_matrix.py::test_s4_matrix_refuses_root_proof_bound_to_another_helper_digest tests/qa/test_s4_functional_runtime_matrix.py::test_s4_matrix_rejects_missing_profile_report_references tests/qa/test_s4_functional_runtime_matrix.py::test_s4_matrix_rejects_stale_candidate_and_corrupt_artifact_range
```

The command file contains the literal selector names with underscores. Environment:

```text
PYTHONPATH=D:\Temp\vst-s4-diagnostic-target-20261026-dd50fa5-r1
VST_QA_DEPENDENCY_WHEELHOUSE=D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse
PYTHONDONTWRITEBYTECODE=1
PYTHONPYCACHEPREFIX=D:\Temp\vst-s4-fixture-fix-focused-evidence-20261026-dd50fa5-r2\pycache
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
PYTHONUTF8=1
```

Result: exit code 0; 13 passed in 26.68 seconds; no warnings. The three profile
variants account for 13 concrete items across 11 selectors. Full stdout SHA-256:
`2CD256C9169ACBE4FE527CA27BF2F98E92D537CCD3B398507E0AC6392E3759A7`; stderr was
empty. Exact command and raw outputs are retained at
`D:\Temp\vst-s4-fixture-fix-focused-evidence-20261026-dd50fa5-r2\`.

The five S2 lifecycle selectors were not included in this focused fixture check.
The 52 policy `NOT_RUN` selectors and the timeout/process-tree selector were not
run. No broad report-bound run was performed on this uncommitted test change.

## Test contract preservation

- Dependency mutation test still requires a detected post-execution target change
  and a failing report.
- Root harness still asserts safe command construction, proof binding, and now
  additionally checks that the dependency wheelhouse reaches the child runner.
- Wrong-interpreter test still requires BLOCKED, `exit_code` null, empty command,
  and no pytest child invocation.
- Final Git-status test still requires a BLOCKED report after pytest passes.
- Matrix tests retain their exact acceptance and rejection assertions; their
  fixtures now satisfy the prerequisite schema so those assertions are reached.

## State and next action

Four test modules are modified in the worktree. The protected pre-existing
`docs/sdlc/evidence/s2-functional-test-run.md` remains untouched. Registry refresh
and change records are pending. Owner Codex will commit these tests and regenerate
the registry in a separate commit; the next full regression must use a fresh
candidate and target and must reconcile the five S2 failures while preserving the
policy `NOT_RUN` set.
