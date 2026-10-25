# 0255 S4 bounded selector invocation

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `ba43fd6724783dabe9ba8aee3c520a1f84d91ff0`

## What changed

- Replaced one pytest command-line argument per eligible selector with deduplicated source-module paths and an invocation-local selector file.
- Extended the selector file with the expected category map and all known registry selectors. The pytest plugin deselects known selectors outside the requested category, including policy `NOT_RUN`, and retains unknown items for fail-closed reporting.
- Added explicit policy `NOT_RUN` reasons for E4 runner selectors that invoke timeout or child-process termination. E5 process-death selectors remain policy `NOT_RUN`.
- Updated the runner design, current-state checkpoint and S4 backlog with the exact-head evidence and remaining work.

## Why

The API category had 703 eligible selectors, which expanded the Windows process command to about 59 KB. `CreateProcess` rejected it before pytest started; the report therefore showed zero collected and executed nodes. Passing a handful of source modules keeps command arguments bounded while the selection file and plugin retain exact category filtering and accounting.

The static termination audit also identified additional E4 selectors that must not be invoked under the no-process-kill constraint. Their policy rows keep them visible in the denominator without executing them.

## Evidence and verification

- Before the code change, the exact candidate HEAD `ba43fd6724783dabe9ba8aee3c520a1f84d91ff0` had functional `PASS` (54 selectors, 109 concrete cases), integration `FAIL` (six required selectors skipped on Windows because POSIX sandbox/permissions were unavailable), and API `FAIL` before pytest startup (`exit_code=-2`, zero concrete nodes). The current-turn `e2e-runner` copied the functional, integration and API reports/stdout/stderr into `docs/sdlc/evidence/qa/`; all nine source/destination SHA-256 pairs matched.
- The static audit found ten additional E4 selectors that invoke timeout or child-process termination. The two E4 selectors already marked `NOT_RUN` terminate a background holder with `os.kill`. The E5 process-death module is policy `NOT_RUN`; two thread-only serialization selectors in that module do not terminate processes but remain conservatively excluded with the module.
- The implementation agent did not run tests. It accidentally ran `git diff --check` before coding was complete; it returned 0 and changed no files. No other test/check/build was run for this change.
- `NOT_RUN` E4 process-kill selectors were not executed. No process-kill path was invoked by the `ba43fd` API attempt because pytest did not start.
- The six integration skips are platform-dependent and remain unresolved by the command-line fix.
- The pre-existing untracked S2 evidence file remains untouched. No worktree was created or used for development.

## Acceptance and next steps

- VST-033: bounded argv implementation is present; focused authored coverage and exact-head runtime confirmation remain pending.
- VST-034: command selection fix is in place; designated test agents must update and author coverage, then rerun functional/API.
- VST-035: integration retains six platform skips; eligible selectors must rerun, with those six still non-passing until a supported POSIX sandbox run exists.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test author/executor roles: `functional-test-reviewer` and `e2e-runner`. Technical owner for the Windows launch boundary: UNKNOWN in canonical records.
- Next: test agents update the test contracts and E2E baseline to this committed source head; regenerate the QA category registry; run permitted QA categories on an exact clean candidate. Preserve all policy and unavailable-platform cases as `NOT_RUN` or skipped, never as passes.
