# Change 0461: Preserve caller's absolute deadline through admission

## What changed

- Pass the caller's absolute deadline, capped by the per-command budget, from `run_and_sign` and `run_manifest_commands` into `_run_one`.
- Make the distinct-UID admission wrapper use the supplied absolute deadline instead of rebuilding a new one from the relative remaining duration.
- Add a regression where the positive relative limit remains but the caller's absolute deadline is already expired at wrapper entry; require timeout and zero cgroup/Popen calls.

## Why

Reliability review of exact commit `2a71cf4fc32715a1f9f502ab5e7e7788aeff45e8` found the 0458 correction still rebased the remaining relative budget when the wrapper began. A scheduling pause between the caller's remaining-time calculation and wrapper entry could therefore extend the original overall deadline. Absolute propagation closes that pre-wrapper gap as well as the already-tested lock-wait gap.

## Affected contracts

- `tools/vst/runner.py`: absolute `deadline_at` propagation for `run_and_sign`, `run_manifest_commands`, and serialized POSIX admission.
- `tests/vst/test_s2_runner_lifecycle.py`: expired caller-deadline regression.
- `docs/sdlc/evidence/s2-e4-deadline-exact-2a71cf4-20261027.md`: parent-head evidence and limitation.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/BACKLOG.md`, and S2 state: review finding and exact-head verification status.

## Verification state

- At parent commit `2a71cf4`, the exact focused lifecycle selection passed 12/12 and the selected cross-UID WSL E4.1 selector passed 1/1. Those results are recorded in `docs/sdlc/evidence/s2-e4-deadline-exact-2a71cf4-20261027.md`, but do not verify this 0461 correction.
- The new caller-deadline source/test change is committed here; exact-head functional execution, WSL E2E rerun, and fresh review are pending.
- Prior architecture/security reviews reported no actionable BLOCKER/MAJOR at `2a71cf4`; reliability found the rebase defect; silent-failure review found no issue in its stated scope. All four roles must review the corrected exact head.
- Full S2 acceptance remains open. Windows Job Object, prohibited process/kill-table, crash/resume, and mutation scenarios retain `NOT_RUN` status.

## Decision and ownership

- Decision: the overall deadline is authoritative; each command's absolute deadline is the earlier of the overall deadline and its per-command limit, computed before wrapper entry.
- Implementation/docs/Git/evidence coordination: Codex. Test author/executor: `functional-test-reviewer`; permitted WSL runtime executor: `e2e-runner`; independent reviews: architect, security, reliability, and silent-failure roles.
- No push, PR, merge, S3 work, provisioning, or external configuration is included.
