# Change 0331 — Retry and report Job Object setup cleanup failure

## What changed

- Updated `_JobObject.attach()` to retry `CloseHandle(job)` once when Win32 reports false or raises during setup-failure cleanup.
- Added an error log if both bounded close attempts fail; the method still returns `None`, preserving strict launch refusal.
- Added focused tests for false/exception recovery, persistent failure logging, and strict fail-closed behavior.
- Recorded exact test results, the initial test-only assertion defect and correction, and remaining platform limitations.

## Why

An earlier reliability review at `c7ad087` found that setup-failure cleanup ignored a false `CloseHandle` result. Strict mode already refuses to execute the requested command when Job Object attachment fails, but the ignored cleanup result could leave a kernel handle open without an observable diagnostic. One retry improves transient-failure recovery; persistent failure remains visible and cannot authorize execution.

## Evidence and verification

- Source file: `tools/vst/runner.py`, `_JobObject.attach()` setup exception cleanup.
- Test file: `tests/vst/test_s2_runner_lifecycle.py`.
- Test owner: designated `e2e-runner`, GPT-6 Luna.
- Working-tree source/test baseline HEAD: `d9b2a5c1ffced7930c6a5dfc82c04b7c6d9f88ce`; dirty source was explicitly recorded.
- Focused command passed 5/5 with 75 deselected; safe strict/nonstrict launch regressions passed 2/2. Python 3.14.3; one deprecation warning per command.
- Initial focused test run had one test assertion failure; the test author corrected the observed lifecycle boundary and reran 5/5. No source failure was reported.
- Full details and exclusions: `docs/sdlc/evidence/s2-job-object-attach-cleanup-tests-d9b2a5c.md`.
- No checks/builds/migrations were run. Exact committed-head rerun and specialist review remain pending.

## Remaining acceptance and owners

- The change does not prove real Windows Job Object nesting or process-tree termination. Those scenarios remain `NOT_RUN` or policy-prohibited.
- Operator remains accountable for S2; Codex owns implementation and coordination; the designated test and specialist reviewer roles own their assigned verification work.
- No push, PR, merge, process-kill test, or external environment change is authorized by this change.

Change: 0331  
Executor: Codex
