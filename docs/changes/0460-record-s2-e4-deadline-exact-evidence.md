# Change 0460: Record exact-head S2 E4 deadline evidence

## What changed

- Add exact-head evidence for the 12 focused POSIX lifecycle selectors at commit `2a71cf4fc32715a1f9f502ab5e7e7788aeff45e8`.
- Add exact-head evidence for the selected cross-UID POSIX descendant cleanup E2E under a bounded, transient Ubuntu-24.04 WSL systemd unit at the same source/test commit.
- Reconcile VST-013 backlog, S2 state, decision/lesson logs, and the generated document registry with the exact commands, outcomes, system properties, and retained limitations.

## Why

Change 0458 bounded serialized admission by the caller's absolute deadline; change 0459 corrected a deterministic timeout-test clock fixture. The exact commit now has focused lifecycle and real delegated WSL evidence for the changed path. Prior-head reports must remain scoped to their original revisions.

## Affected paths and contract scope

- `docs/sdlc/evidence/s2-e4-deadline-exact-2a71cf4-20261027.md`
- `docs/sdlc/STATE.md`, `core/STATE.md`, `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- Acceptance scope: S2 E4.1 POSIX cross-UID timeout cleanup and distinct-UID admission deadline/latch unit regressions only.

## Verification

- Functional reviewer, Windows/Python 3.14.3, exact commit `2a71cf4fc32715a1f9f502ab5e7e7788aeff45e8`: 97 collected, 12 selected, 12 passed, 85 deselected, 0 skipped; exit 0 in 3.23 seconds; one unrelated pytest-asyncio deprecation warning.
- E2E runner, Ubuntu-24.04 WSL2/Python 3.12.3/pytest 7.4.4, exact archived commit: selected `test_posix_worker_timeout_kills_descendant_across_uid_boundary` passed 1/1 in 4.30 seconds, transient unit exit 0. Runner/test archive hashes, unit properties, identities, capabilities, cgroup path/control, events, and limitations are in the evidence file.
- The final child `populated=0` cgroup event was not separately sampled before immediate scope removal; the test's cleanup and stopped-heartbeat assertions passed.
- Fresh architecture/security/reliability/silent-failure review results are pending. This record does not close VST-013, E4, or S2 Phase 8. Windows nested Job Object and prohibited process/kill-table, crash/resume, and mutation scenarios remain `NOT_RUN`.

## Ownership and next action

- Evidence authors/executors: designated `functional-test-reviewer` and `e2e-runner` roles; coordination/documentation/local Git: Codex.
- Independent code review: architecture, security, reliability, and silent-failure reviewer roles.
- Codex next action: reconcile exact-head review findings; keep unresolved platform/system acceptance separate from this POSIX result. No push, PR, merge, or S3 work is included.
