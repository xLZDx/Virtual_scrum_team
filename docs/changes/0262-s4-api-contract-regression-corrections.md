# 0262 S4 API contract corrections after exact-head run

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `3558b14a420a249d34f5d17309944b5c5a0d3f25`

## What changed

- Corrected the foreign-schema test denominator to exclude schema version 3, which the current store explicitly migrates to schema version 4.
- Corrected the synthetic E4 timeout test fixture to return a non-terminating fake Job Object, so it reaches the mocked timeout and incomplete-capture branch without claiming to test real process termination.
- Preserved the partial exact-head API run artifacts and updated current S4 status and decision/lesson records.

## Why

The exact-head API run failed in two selectors. Static source review showed both assertions were stale test setups, not demonstrated product regressions: schema version 3 is an explicitly supported additive migration, and returning `None` from Job Object attachment makes the runner correctly refuse before entering the timeout scenario.

## Evidence and verification

- Exact candidate: `3558b14a420a249d34f5d17309944b5c5a0d3f25`; CPython 3.14.3, pytest 9.0.3, Windows 11 AMD64.
- Functional category: 58/58 selectors passed and 113 concrete nodes executed, with no failed/skipped/unexpected cases; QA `PASS`.
- Integration category: 42/48 selectors passed and 6 platform skips; 36 process-death selectors were policy `NOT_RUN`. Pytest exited 0; QA `FAIL` because required selectors were unavailable.
- API category: 686/693 selectors passed, 2 failed, 5 platform skips; 12 process-termination selectors were policy `NOT_RUN`. Pytest completed with exit 0; QA report result was `FAIL`. The runner was configured with `--tb=no --no-summary --show-capture=no`, so no traceback/assertion detail was retained.
- Recorded run IDs: `s4-3558b14-functional-20261025t1410`, `s4-3558b14-integration-20261025t1410`, and `s4-3558b14-api-20261025t1410`.
- Failed selectors: `tests/vst/test_e3_store.py::test_foreign_schema_version_is_refused[3]` and `tests/vst/test_e4_runner.py::test_root_that_survives_the_kill_gives_exit_minus_four`.
- The supported child invocation used `-m pytest -q --no-header --no-summary --tb=no --disable-warnings --show-capture=no --color=no -p tools.qa.pytest_plugin`, with run-scoped selection/event files and these source modules:
  - functional: `tests/qa/test_s4_functional_report_contracts.py`, `tests/qa/test_s4_functional_runner_contracts.py`, `tests/vst/test_s2_contract_gate.py`, `tests/vst/test_s2_diffgate.py`.
  - integration: `tests/vst/test_s2_operation_recovery.py`, `tests/vst/test_s2_runner_lifecycle.py`, `tests/vst/test_s2_store_lifecycle.py`.
  - API: `tests/vst/test_e1_contracts.py`, `tests/vst/test_e2_gate.py`, `tests/vst/test_e3_store.py`, `tests/vst/test_e4_runner.py`, `tests/vst/test_s2_sandbox_probe.py`, `tests/vst/test_s3_worker_adapter.py`.
- All nine functional/integration/API report/stdout/stderr files were copied from the exact candidate to `docs/sdlc/evidence/qa/`; source and destination SHA-256 matched. Hashes:
  - functional report `C976418405A33783C3EC88339CAE4F54787EE5A667612C181193A1645A8223A5`; stdout `2D471594D8119CA4D962B7F553AE4DD805DC0D791A8B2EA7283F2C9A68AEE64B`; stderr `1932684BD5FF43A2D720E739EFF51D82C5EC576D20819B33633255A5462B3451`.
  - integration report `6BA374CD9587D020C66560E106A7066C2589B6A8C556719C762B3AA64784C6A1`; stdout `4527C5535289D0E3906BAB5489AC78651301EBCF631F892A4B1FF1E13FEE56D2`; stderr `A790BE6D8B616F585F3632A59DBD5D6DD00DF05596EDDAB3DC067C19B938BAAB`.
  - API report `CA632E5468D36B6B6AC06828E0991065A89C970A07507D51349B8B65DE4BEF73`; stdout `460209DF607289404863DD09395F7F3B24EC506FEFC6AFC07A8F349E3E50B0C9`; stderr `A790BE6D8B616F585F3632A59DBD5D6DD00DF05596EDDAB3DC067C19B938BAAB`.
- `tools/vst/store.py` declares `SCHEMA_VERSION = 4` and migrates version 3 in `_init_schema`; the test must therefore keep 3 out of the foreign-version cases.
- `_run_one` requires a non-`None` Job Object on Windows. The revised E4 fixture uses a no-op fake and keeps `_kill_tree` mocked, so no real process-kill scenario is executed. This test does not prove OS-level termination.
- Functional category also passed independently on this exact HEAD: 58/58 selectors, 113 concrete cases, no skips/failures. E2E run's integration category reported 42/48 selectors passed, 6 POSIX/permission skips, and 36 policy `NOT_RUN` selectors; because required skips exist, the QA result is `FAIL` even though pytest exited 0.
- The two API test corrections are included in this change and have not been rerun. E2E, regression and seeded-failure were not run on this candidate after the API failure.
- All development remains in `D:\Repo\Virtual_scrum_team`; only disposable test candidates were used, with no Git worktree created. The pre-existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- VST-034: functional category passes on exact `3558b14a`; the corrected API tests are committed by this change but runtime acceptance remains pending.
- VST-035–037: integration retains platform skips and policy `NOT_RUN`; E2E, regression and seeded-failure need a full exact-head run after the correction commit and refreshed selector manifest.
- Accountable task owner: operator under the delegated continuation. Executor: Codex. Test author/executor roles: `functional-test-reviewer` and `e2e-runner`.
- Next: regenerate and commit the selector manifest after this test-source commit, then rerun the complete supported six-category suite on the resulting exact clean candidate. Preserve the integration skips and all policy `NOT_RUN` selectors as non-passing.
