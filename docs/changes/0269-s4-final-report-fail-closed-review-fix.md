# 0269 S4 final report fail-closed review fix

**Date:** 2026-10-25  
**Executor:** Codex with implementation-engineer and functional-test-reviewer roles  
**Reviewed source head:** `ac17bdef511f980c6f92dbd5d13fd008aaa72ef0`  
**Current candidate before source/test commit:** `9cceab35afcca0189aa203ce3c062069f5123e74` (dirty source/test tree)

## What changed

- Moved persistence of the category report until after the final candidate Git status query succeeds in `tools/qa/run.py`.
- Added a fault-injection functional regression proving a final Git status timeout after pytest PASS leaves exactly one durable `BLOCKED` record for that run ID, not `PASS`.
- Reconciled the S4 backlog and decision/lesson logs with the specialist findings and targeted regression result.

## Why

The S4 runner previously appended a computed `PASS` before its final candidate-cleanliness query. If that query timed out or failed, the CLI returned `BLOCKED` while the JSONL still contained an approving report. A report consumer could therefore treat an unverified candidate state as passing evidence.

## Reviews

- `reliability-reviewer`, GPT-6 Luna, medium effort, read-only at exact head `ac17bde`: **MAJOR** false-success finding at `tools/qa/run.py` final report append / final Git status error path. The source fix defers report append to after final status succeeds; the exception path can then persist `BLOCKED`.
- `security-reviewer`, GPT-6 Luna, medium effort, read-only at exact head `ac17bde`: **MINOR** — wheel SHA-256 pins in `requirements.lock` are parsed but not verified against installed files in the external dependency target. Distribution names/versions are checked; provenance and immutability of the target remain unverified. Technical owner is not established in canonical sources. The issue is retained under VST-033 and is not changed in this commit.
- `code-reviewer`, GPT-6 Luna, low effort, read-only at exact head `ac17bde`: no other material findings in the S4 runner, registry, fixtures, tests, or immediate VST runner contracts. The reviewer disclosed one accidental `git diff --check` invocation despite the task's explicit no-check instruction; it returned no diagnostics and changed no files. This process lapse is recorded in `core/LESSONS_LOG.md`.
- `functional-test-reviewer`, GPT-6 Luna, medium effort: added `test_s4_main_persists_blocked_when_final_git_status_fails_after_pytest_passes` and ran only that selector. Exact command: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_functional_runner_contracts.py::test_s4_main_persists_blocked_when_final_git_status_fails_after_pytest_passes`; `PYTHONPATH=D:\Temp\virtual_scrum_team_qa_f4ef8e7`; result **1 passed**, one unrelated pytest-asyncio deprecation warning, 15.72 seconds. HEAD before/after was `9cceab35afcca0189aa203ce3c062069f5123e74`; source and test were dirty and not committed during the targeted run.

## Remaining review observations

- `reliability-reviewer` recorded INFO: concurrent same-category runs append to shared report/stdout/stderr paths without serialization, so byte ranges may overlap; existing integrity validation should reject mismatched evidence. Append-only evidence also has no cumulative size bound. These do not recreate the MAJOR durable-PASS path but remain reliability hardening opportunities.
- No full six-category suite or exact-head post-fix run is represented by this change. The prior six-category run is tied to `ac17bde` and remains historical baseline evidence.
- The S4 selector registry must be regenerated and committed after this test-source change. Then the designated test roles must run the full supported category set on the resulting exact HEAD. Platform-required skips and prohibited process-kill/timeout/`os._exit` cases remain non-passing/`NOT_RUN`.
- No tests were run by the primary coordinator. The functional-test reviewer ran only the targeted case above. One reviewer accidentally invoked `git diff --check`; the no-output result is disclosed above and in the lesson log. No builds, CI, migrations, push, PR, or merge were performed for this change.
- Development and test-source edits are in `D:\Repo\Virtual_scrum_team`; no Git worktree was created or used.

## Acceptance and next steps

- VST-033 / VST-037: the MAJOR report-ordering defect is fixed in source and the focused regression passes, but exact-HEAD full-suite acceptance is pending.
- VST-034 / VST-035: previous candidate reports remain tied to `ac17bde`; platform skips and policy `NOT_RUN` still prevent closure.
- Accountable task owner: operator under delegated autonomous continuation. Executor: Codex. Regression author/executor: functional-test-reviewer. Full-suite executor: e2e-runner. Technical owner for installed dependency target provenance: UNKNOWN in canonical records.
- Next: commit the source/test fix with this record, refresh the S4 category registry in its own evidence commit, run the six categories on that exact candidate, then perform fresh specialist review and request the exact-head GPT-PM gate. Do not push or merge before approval.
