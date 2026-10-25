# S4 synthetic report-bound fixture rerun

Date: 2026-10-25

- Test owner/executor: `e2e-runner` (GPT-6 Luna, low effort).
- Repository: `D:\Repo\Virtual_scrum_team-s4`; branch `s4-native-qa-runner`.
- HEAD before and after: `de8c6f8afaf34b9566e21a56c24b145b639f6cfd`.
- Environment: Windows; Python 3.14.3; pytest 8.4.2.
- Exact command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/qa/test_s4_report_bound_e2e.py`.
- Result: exit 0; 5 passed, 0 failed, 0 skipped; one pytest-asyncio deprecation warning for `asyncio.get_event_loop_policy`, scheduled for removal in Python 3.16.
- Covered journeys: exact mapped test-ID discovery; local synthetic signed runner receipt/artifact accepted by the local gate; stale-head rejection; missing-artifact rejection; corrupt-artifact rejection.
- The fixtures use temporary artifacts and local APIs. The module docstring explicitly excludes `tools.qa.run`, the deployed signer, and the sandbox boundary.
- The agent made no repository edits or commits. Pre-existing untracked `.codex-s4-final-review.patch` was preserved.
- This result does not close the S4 report-bound v2 runtime/identity/signer finding or aggregate report-bound regression.
