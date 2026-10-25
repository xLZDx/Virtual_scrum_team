# 0266 S4 duplicate-event test assertion

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `6fd26c6ae416e2aca5c73785885cc91eff629985`

## What changed

- Corrected the synthetic duplicate-event E2E assertion to expect the registered selector in `failed_test_ids`, while retaining checks for the duplicate rejection reason and collected/executed node accounting.
- Preserved exact partial-run artifacts from the sixfd26c6 candidate for functional, integration, API and E2E.
- Updated the S4 state and backlog to distinguish passing assertions from platform skips and policy `NOT_RUN` rows.

## Why

At exact head `6fd26c6`, the duplicate-event fixture caused pytest to emit one passed and one failed concrete execution for the same node. The QA runner correctly rejected the duplicate and marked the selector failed; the test incorrectly expected it in `passed_test_ids`. No product defect was established.

## Evidence and verification

- Candidate: `6fd26c6ae416e2aca5c73785885cc91eff629985`; CPython 3.14.3, pytest 9.0.3, Windows 11 AMD64.
- Functional `s4-6fd26c6-functional-20261025t`: 58/58 selectors, 113/113 concrete cases passed, no skips/failures; QA `PASS`.
- Integration `s4-6fd26c6-integration-20261025t`: 48 selectors, 94 concrete cases; 84 passed, 0 failed, 6 POSIX-required skips and 36 policy `NOT_RUN`; QA `FAIL` because required runtime evidence is absent.
- API `s4-6fd26c6-api-20261025t`: 693 selectors, 1,502 concrete cases; 1,492 passed, 0 failed, 5 platform skips and 12 policy `NOT_RUN`; QA `FAIL` because skips and policy rows remain non-passing.
- E2E `s4-6fd26c6-e2e-20261025t`: 55 selectors, 59 concrete nodes; 58 passed, one failed, zero skips and one process-tree timeout selector policy `NOT_RUN`; QA `FAIL`. The failing node was `test_s4_e2e_cli_rejects_uncollected_duplicate_skipped_or_xfailed_selector[pass-duplicate-reasons]`. Its nested fixture report correctly contains `pytest emitted duplicate node IDs`, a concrete-case failure reason, and pytest exit 1; the outer test's `passed_test_ids` expectation was stale.
- Regression and seeded-failure were not started after the E2E assertion failure.
- The four categories' report/stdout files were copied from the disposable exact-head candidate into `docs/sdlc/evidence/qa/`; source and destination SHA-256 matched. Hashes:
  - functional report `899D988A7A86E5FA2FE3A3B731E06E756775D3D8500B50370BFF1001D80C87AE`; stdout `127A49C68D22C8BA594AF4A049AE2F83ABA740408F2F73A6A8A3199FF8608444`.
  - integration report `8D2D65503A08D785626B4BCD657EB4D4FCDAA6F5E754B3E14990E5A204B6D6AD`; stdout `38763356598E1B22BA351AD2EFBDD3FFE353CF4B194AA136928CAF2F51C473E0`.
  - API report `1E5EB98CC2291E2B7CF29A2D177638464A0BB805ED9B50CAEB6A2A3619B07C04`; stdout `CF3C9B2BB9BDEDDE330503ECB0101A6A28845B39154765FD402ABFA5E73F83EE`.
  - E2E report `B35AD6DD0A22586FFC1750F2E93A3FE3B8F600293297249D2BC12C87650B22A0`; stdout `89B6C867632AFC7F7EFC40B6327771B7589B8A98DD82A21F72D7D0B0057F7903`.
- All four stderr artifacts were unchanged from the seeded histories; their new run ranges are empty. The diagnostic did not run timeout/process-kill selectors. No worktree was created; all development remains in `D:\Repo\Virtual_scrum_team`.
- This assertion correction is included in this change and has not been rerun.

## Acceptance and next steps

- VST-035: the duplicate-event test expectation is corrected but not yet behaviorally rerun; POSIX skips and policy `NOT_RUN` remain non-passing, and regression/seeded-failure remain unrun.
- VST-037: partial exact-head artifacts are retained; final complete six-category evidence and VST gate receipt remain pending.
- Accountable task owner: operator under the delegated continuation. Executor: Codex. Test roles: `functional-test-reviewer` and `e2e-runner`.
- Next: regenerate the selector manifest after this test source commit, then rerun all supported categories on a new exact clean candidate; preserve skips and policy `NOT_RUN` as non-passing.
