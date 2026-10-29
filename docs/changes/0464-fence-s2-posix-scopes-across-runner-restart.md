# Change 0464: Fence stale S2 POSIX command scopes across runner restarts

## What changed

- Add a private cross-process `flock` in `/run/vst-runner/cgroup-admission.lock` around distinct-UID POSIX worker admission and execution.
- Before admission, reconcile only strict `vst-command-<pid>-<uuid>` child cgroups under the current runner's delegated cgroup. Kill and remove a stale scope only after bounded confirmation that `cgroup.events` reports `populated 0`.
- Return a non-approving capture-incomplete result if the runtime directory/lock is unsafe or unavailable, stale-scope inspection fails, or cleanup cannot be confirmed. Include lock wait and reconciliation in the existing absolute command deadline.
- Update the S2 POSIX cgroup design and schema README with the runtime-directory, stable delegated-subtree, and rollout contracts.

## Why

Full architecture and reliability reviews of the seven-file S2 delta at source/test HEAD `4c1692d61ee04e945fc0ccdd44db71869ccd5468` independently found that the cleanup latch and admission mutex existed only in process memory. If a runner exited while a child cgroup remained populated, a replacement process could lose that latch and launch a second worker. The repository had no evidence that an external service boundary fenced this restart path.

## Affected contracts and paths

- `tools/vst/runner.py`
- `tools/vst/schemas/README.md`
- `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`
- `tests/vst/test_s2_runner_lifecycle.py` (focused restart/lock acceptance; test owner: functional-test-reviewer)
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/STATE.md`, `docs/sdlc/STATE.md`

The lock directory must be provisioned as a real `/run/vst-runner` directory owned by the runner identity and not group/world writable. All lock-aware runner processes must use one stable delegated subtree. Pre-lock runner instances must be stopped before rollout; the code cannot fence a separate old service subtree it cannot see.

## Verification state

- Source and focused test implementation are in the working tree; exact code-head test evidence is pending.
- The designated `functional-test-reviewer` ran 11 focused selectors on dirty repository HEAD `6b0f32948c7b2b804123ba5e1b67271197ef97a9`: `C:\Python314\python.exe -m pytest -q` followed by the seven lock/stale-scope selectors, `test_distinct_uid_worker_refuses_launch_when_delegated_cgroup_is_unavailable`, `test_distinct_uid_launch_preserves_expired_absolute_deadline_at_admission`, and `test_distinct_uid_cgroup_cleanup_failure_is_non_approving`. Final result: 11 passed, one existing pytest_asyncio deprecation warning, 1.63 s. The first attempt had three test-fixture `NameError` failures because the test module lacked `time`; the test role added the import and reran.
- After tightening runtime-directory validation to require owner-only mode, the reviewer reran four lock selectors (the runtime-directory parameterization contributes three node IDs): 6 passed, one deprecation warning, 1.62 s. It separately reran the deterministic contended-lock deadline selector: 1 passed, one deprecation warning, 1.37 s. The test role corrected two faulty timing assertions before the successful run. These are working-tree results, not a committed exact-head result.
- The tests use synthetic fixtures and mocked `fcntl`; they do not prove real cross-process lock contention or WSL stale-cgroup cleanup. No tests, checks, builds, CI, migration, or system provisioning was run by the coordinator. The e2e-runner must obtain exact-head bounded WSL evidence for the provisioned runtime directory, cross-process lock, and empty stale-scope reconciliation before these controls are considered runtime-proven.
- Prohibited process-kill, crash/recovery, mutation, E8, and policy scenarios remain `NOT_RUN`.

## Decision and ownership

- Decision: require a trusted shared lock and fail-closed reconciliation instead of treating a process-local latch as a restart boundary.
- Code and in-repository contract: Codex. Required test authoring/execution: functional-test-reviewer. WSL runtime evidence: e2e-runner. Stable service/runtime provisioning and any required system-boundary attestation: operator. Exact sprint adjudication: GPT-PM.
- This change does not approve S2, waive any `NOT_RUN` scenario, or authorize a push, PR, merge, or S3 source work. All previously recorded S2 evidence remains tied to its own exact source/test head until rerun or explicitly treated as unaffected supporting evidence.
