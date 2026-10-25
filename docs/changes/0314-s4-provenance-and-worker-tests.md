# Change 0314 — S4 dependency provenance and worker identity tests

## What changed

- Added seven functional contract tests for locked wheel and installed dependency contents: same-version byte substitution, wheel hash mismatch, extra target files, unsupported `.data` relocation, mandatory wheelhouse argument, explicit schema-3 `NOT_VERIFIED`, and post-execution dependency mutation detection.
- Added the AC-16 POSIX report-bound selector for the fixed `vst-runner` 997:988 to `vst-worker` 999:989 helper. Registered the selector as WSL-only.
- Added two E2E/CLI contract tests for the mandatory wheelhouse argument and WSL-only selector assignment.
- Kept the 52 existing S4 policy-excluded selectors unchanged and `NOT_RUN`.

## Why

Change 0313 implemented exact locked-wheel and target-content verification after GPT-PM MAJOR-02. Change 0310 committed the narrow WSL identity helper and installer. These tests add focused evidence for the new contracts without running any excluded timeout, process-kill, process-death, mutation, or E8 scenario.

## Affected paths

- `tests/qa/test_s4_dependency_provenance.py`
- `tests/qa/test_s4_functional_worker_identity.py`
- `tests/qa/test_s4_e2e_runner_cli.py`
- `tools/qa/registry.py`
- `docs/qa/categories.json` is intentionally pending until these new test sources have committed provenance; regenerate it in the follow-up change before report-bound runtime.

## Verification

- Functional-test-reviewer, GPT-6 Luna, medium effort: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_dependency_provenance.py` — 7 passed, 0 failed/skipped, 1 pytest-asyncio deprecation warning, exit 0; Python 3.14.3; HEAD before and after `e792d2f99c82ccea95ae935705b1b84d92ccd9a7`.
- E2E-runner, GPT-6 Luna, low effort: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_cli_requires_explicit_dependency_wheelhouse tests/qa/test_s4_e2e_runner_cli.py::test_s4_worker_helper_selector_is_wsl_only` — 2 passed, 0 failed/skipped, 1 pytest-asyncio deprecation warning, exit 0; Python 3.14.3; HEAD `e792d2f99c82ccea95ae935705b1b84d92ccd9a7` with the assigned test changes present.
- The AC-16 WSL selector is authored but `NOT_RUN`: full report-bound execution needs the exact committed test source, refreshed category registry, the already-provisioned Ubuntu 24.04 WSL2 distribution, the authorized helper installation, and a trusted pre-existing wheelhouse for the QA runner. The project-referenced `D:\Temp\virtual_scrum_team_qa_f4ef8e7` is an installed dependency target, not a wheelhouse.
- No network download, dependency installation, WSL helper installation, runtime category/matrix, excluded selector, or Git worktree creation was performed in this change.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved and not staged.

## Decision and follow-up

All development remains in the canonical `D:\Repo\Virtual_scrum_team` checkout; no per-sprint worktree or fork folder is created. The project worktree listing contains pre-existing sibling checkouts, but their provenance is not established here and they were not used. This test-source change precedes the required `docs/qa/categories.json` refresh from committed provenance. Then the designated test role can run AC-16 through the report-bound WSL runner once a trusted wheelhouse is identified. This record does not close S4 or MAJOR-01.
