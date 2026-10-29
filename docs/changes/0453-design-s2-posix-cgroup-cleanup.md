# Change 0453: design least-privilege POSIX cross-UID cleanup

## What changed

- Added the implementation design for POSIX worker descendant cleanup when runner and worker have different UIDs.
- Compared a broad runner `CAP_KILL`, a systemd-delegated per-command cgroup, and a privileged root helper; selected scoped cgroup-v2 cleanup.

## Why

The user-authorized VST-013 E4.1 cross-UID test failed at source/test HEAD `161dcc7`: runner UID 997 timed out worker UID 999, but the worker descendant continued writing after cleanup. The current service profile exposes only `CAP_SETUID` and `CAP_SETGID`, so the runner cannot signal a differently owned process. Increasing capabilities would exceed the least-privilege boundary.

## Affected paths

- `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`
- `docs/changes/0453-design-s2-posix-cgroup-cleanup.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and verification

- Failure test source/test HEAD `161dcc7838b2bd05f01f485dab38a37cba9d82b2`; selector `test_posix_worker_timeout_kills_descendant_across_uid_boundary`; invocation `4399ad0027ec49bd8a273b587a24999c`; 1 failed after heartbeat continued post-cleanup.
- Read-only systemd preflight showed WSL supports a transient `Delegate=yes` unit, writable runner-owned cgroup directory, and `cgroup.kill` (command/result recorded in active execution log; durable exact-evidence record will accompany implementation).
- This is design only; no source fix or passing acceptance is claimed. No tests/checks/build/CI/migrations were run while preparing it.

## Ordered next steps and owners

1. Fresh `architect` review: challenge scope and lifecycle invariants before implementation.
2. Codex: implement a per-command cgroup-v2 cleanup path with gated exec; refuse worker launch if delegation is unavailable.
3. `functional-test-reviewer`: add deterministic helper/fail-closed coverage after the implementation contract is finalized.
4. `e2e-runner`: rerun only the cross-UID POSIX descendant selector in the delegated WSL unit.
5. Fresh reliability/security reviews: inspect exact tested head and any valid findings.

## Attribution

Change: 0453
Executor: Codex
