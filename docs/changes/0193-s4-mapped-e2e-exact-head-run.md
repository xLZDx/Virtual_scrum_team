# 0193 — Run all mapped S4 E2E selectors at exact committed head

## What changed

- Executed all twelve selectors in the committed E2E category manifest together at source HEAD `47918f9c0a229b4dac0ea095763775eb20eb6755`.
- The run passed all twelve selectors. No selector or product code changed for this evidence record.

## Command and environment

- Repository: `D:\Repo\Virtual_scrum_team-s4`
- Branch: `s4-native-qa-runner`
- Operating system: Microsoft Windows NT 10.0.26300.0; PowerShell 7.6.7
- Interpreter: `C:\Python314\python.exe`, CPython 3.14.3
- pytest: 8.4.2

Exact command:

```powershell
C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_commits_only_the_manifest_scoped_synthetic_change tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_rejects_out_of_scope_edit_before_worker_invocation tests/vst/test_s3_worker_pilot_e2e.py::test_s3_app_checkpoint_can_resume_same_effect_under_new_store_epoch tests/vst/test_s3_worker_pilot_e2e.py::test_s3_stop_fences_interrupted_attempt_idempotently_and_rejects_stale_start tests/vst/test_s3_worker_pilot_e2e.py::test_s3_candidate_identity_cannot_be_self_selected tests/qa/test_s4_qa_e2e.py::test_s4_e5_synthetic_slice_cli_journey_preserves_gate_and_restart_evidence tests/qa/test_s4_qa_e2e.py::test_s4_e6_qa_snapshot_cli_refuses_an_unapproved_distribution tests/qa/test_s4_report_bound_e2e.py::test_s4_native_pytest_discovery_accounts_exact_required_ids tests/qa/test_s4_report_bound_e2e.py::test_s4_signed_runner_receipt_and_artifact_gate_approve_at_exact_head tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_stale_signed_runner_receipt tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_missing_signed_artifact tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_corrupt_signed_artifact
```

Mapped selector IDs:

1. `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_commits_only_the_manifest_scoped_synthetic_change`
2. `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_rejects_out_of_scope_edit_before_worker_invocation`
3. `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_app_checkpoint_can_resume_same_effect_under_new_store_epoch`
4. `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_stop_fences_interrupted_attempt_idempotently_and_rejects_stale_start`
5. `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_candidate_identity_cannot_be_self_selected`
6. `tests/qa/test_s4_qa_e2e.py::test_s4_e5_synthetic_slice_cli_journey_preserves_gate_and_restart_evidence`
7. `tests/qa/test_s4_qa_e2e.py::test_s4_e6_qa_snapshot_cli_refuses_an_unapproved_distribution`
8. `tests/qa/test_s4_report_bound_e2e.py::test_s4_native_pytest_discovery_accounts_exact_required_ids`
9. `tests/qa/test_s4_report_bound_e2e.py::test_s4_signed_runner_receipt_and_artifact_gate_approve_at_exact_head`
10. `tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_stale_signed_runner_receipt`
11. `tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_missing_signed_artifact`
12. `tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_corrupt_signed_artifact`

Observed output:

```text
............                                                             [100%]
============================== warnings summary ===============================
tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_commits_only_the_manifest_scoped_synthetic_change
  C:\Users\koros\AppData\Roaming\Python\Python314\site-packages\pytest_asyncio\plugin.py:1216: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    return asyncio.get_event_loop_policy()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 1 warning in 24.40s
```

## Acceptance boundary

- Proven on this Windows exact head: all twelve currently mapped E2E selectors pass together, including the local fixture-only v1 runner/gate artifact scenarios.
- Not proven: `tools.qa.run` report serialization with v2 signed artifacts, trusted signer socket/identity, POSIX WSL transfer/runtime, or sandbox deployment. These remain `NOT_RUN`; E2E selector coverage remains `PARTIAL` for the report-bound v2 selector gap.
- The pytest asyncio deprecation warning was observed and did not fail the run. This run does not establish WSL/POSIX-specific behavior.

Executor: Codex
