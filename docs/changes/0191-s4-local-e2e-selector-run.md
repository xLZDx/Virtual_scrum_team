# 0191 — Run bounded local S4 E2E selectors at exact committed head

## What changed

- Executed only the five E2E selectors introduced in change 0189 and mapped by change 0190.
- All five selectors passed on exact source HEAD `7d14e43d1e9568dddd5366ed979a187457c507b9`.
- No test code or selector mapping changed as part of this evidence record.

## Command and environment

Working directory: `D:\Repo\Virtual_scrum_team-s4`  
Branch: `s4-native-qa-runner`  
Python: `C:\Python314\python.exe` — CPython 3.14.3  
pytest: 8.4.2

Exact command:

```powershell
C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/qa/test_s4_report_bound_e2e.py::test_s4_native_pytest_discovery_accounts_exact_required_ids tests/qa/test_s4_report_bound_e2e.py::test_s4_signed_runner_receipt_and_artifact_gate_approve_at_exact_head tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_stale_signed_runner_receipt tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_missing_signed_artifact tests/qa/test_s4_report_bound_e2e.py::test_s4_gate_rejects_corrupt_signed_artifact
```

Observed result:

```text
.....                                                                    [100%]
============================== warnings summary ===============================
tests/qa/test_s4_report_bound_e2e.py::test_s4_native_pytest_discovery_accounts_exact_required_ids
  C:\Users\koros\AppData\Roaming\Python\Python314\site-packages\pytest_asyncio\plugin.py:1216: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    return asyncio.get_event_loop_policy()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
5 passed, 1 warning in 12.35s
```

## Acceptance boundary

- Proven: native pytest collection accounts for the exact mapped E2E IDs; local v1 `run_and_sign`, artifact digest resolution, and VST gate fixture accept an exact-head receipt and reject stale-head, missing-artifact, and corrupt-artifact cases.
- Not proven: `tools.qa.run` report serialization, v2 signed report artifacts, trusted signer socket/identity, transferred POSIX WSL snapshot execution, and S4 sandbox deployment. These remain separate `NOT_RUN` runtime and coverage items; E2E denominator remains `PARTIAL` for the missing report-bound v2 selector.
- The pytest asyncio deprecation warning did not fail the run and is environment/plugin output; no quarantine or assertion change was made.

Executor: Codex
