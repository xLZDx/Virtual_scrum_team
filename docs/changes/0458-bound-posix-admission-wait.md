# Change 0458: Bound POSIX admission wait by the command deadline

## What changed

- Make the process-local distinct-UID launch lock acquire with a timeout equal to the command's current remaining budget.
- Carry the caller's absolute command/overall deadline through admission into `_run_one`, so time queued on the lock is included in worker execution and cleanup.
- Return a timeout result without cgroup creation or `Popen` if the budget expires before or during admission.
- Preserve `skipped_by_deadline` in `run_manifest_commands` and `run_and_sign` when admission itself expires.
- Add a deterministic regression that holds the admission lock past a short command budget and asserts timeout metadata plus zero cgroup/Popen calls.
- Update the POSIX design, sandbox spec, schema notes, decision, lesson, state, and backlog.

## Why

Architecture and security reviews of change 0457 independently found that a queued distinct-UID launch could wait past the caller's budget and then start with the stale timeout value. This violates the runner's documented command deadline. Admission must share the same absolute deadline as execution.

## Affected contracts

- `tools/vst/runner.py`: bounded lock admission and absolute deadline propagation.
- `tests/vst/test_s2_runner_lifecycle.py`: queued-admission deadline regression and lock fake adaptation.
- `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`, `docs/SANDBOX_SPEC.md`, `tools/vst/schemas/README.md`: document deadline-bound admission.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/BACKLOG.md`, `core/STATE.md`, `docs/sdlc/STATE.md`: record finding, fix, and pending exact-head verification.

## Verification state

- Source and test edits are complete; exact-head test and reviewer results are pending.
- The E4.1 WSL selector passed 1/1 at parent change 0457 (`3be44ad4ea93bc9e68cee1534d1d4c4e731ac451`), but it predates this deadline fix and is not final-head evidence.
- Do not infer full VST-013 or S2 acceptance from this change. Prohibited process/crash/mutation scenarios remain `NOT_RUN`; remaining platform and system acceptance stays separately tracked.

## Decision and ownership

- Decision: lock wait consumes the same absolute per-command/overall deadline; if it expires, the queued worker is not started.
- Implementation, documentation, evidence coordination, and local Git: Codex.
- Focused test authoring/execution: `functional-test-reviewer`; permitted platform runtime execution: `e2e-runner`.
- Independent architecture/security/reliability/silent-failure review: the respective GPT-6 Luna agent roles; project ownership remains Codex/GPT-PM/operator.
- No push, PR, merge, systemd provisioning, or external configuration is part of this change.
