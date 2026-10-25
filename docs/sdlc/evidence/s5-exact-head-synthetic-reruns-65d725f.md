# S5 exact-head synthetic reruns

Date: 2026-10-25

- Repository/branch: `Virtual_scrum_team-s5` / `s5-bounded-aeve-evidence`.
- Source/test HEAD before both test runs: `65d725f0101c5e1d0f758cd7850f97313144dc06`; both agents reported the worktree stayed clean and HEAD unchanged.
- Environment: Windows 10, Python 3.14.3, pytest 8.4.2.
- Test owners/executors: `functional-test-reviewer` and `e2e-runner`, GPT-6 Luna, low effort.

## Functional contract

- Command: `python -m pytest -q -p no:cacheprovider tests/vst/test_s5_v3_evidence.py`
- Result: 39 passed, 1 skipped, 0 failed; one pytest-asyncio deprecation warning.
- Scope: synthetic v3 evidence contract and local digest/receipt semantics. The skip is the Windows symlink privilege case; this run does not establish analyzer runtime or attestor provisioning.

## Store-to-Gate E2E

- Command: `python -m pytest -q -rs -p no:cacheprovider tests/vst/test_s5_v3_store_gate_e2e.py`
- Result: 3 passed, 0 skipped, 0 failed; one pytest-asyncio deprecation warning.
- Scope: synthetic local S1 Store-to-Gate path; static-only acceptance remains bounded to the declared evidence. No AEVE runtime, analyzer attestor, seeded-rule run or clean checked-rule run was exercised.

## Acceptance boundary

These exact-head reruns confirm the local synthetic evidence contracts only. They do not close S5-M01 (bounded analyzer adapter, immutable snapshot and runtime restrictions) or S5-M02 (authorized analyzer rule inventory plus demonstrated seeded finding and clean checked-rule execution). The prior correlated GPT-PM full-acceptance finding remains the latest review; no current-head fresh GPT-PM review is established by these reruns.
