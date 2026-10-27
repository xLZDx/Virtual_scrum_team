# Change 0456: latch the runner after unconfirmed cgroup cleanup

## What changed

- Added a process-local event latch when delegated cgroup kill/removal cannot be confirmed.
- Refuse all later distinct-UID launches from that runner process before creating another cgroup or calling `Popen`.
- Added focused coverage proving a cleanup failure prevents a later invocation; tests isolate the process-local latch per case.
- Updated cgroup and sandbox contracts, backlog, decision/lessons/state records, and generated document registry.

## Why

Security review of exact HEAD `55cc6313dceeffe2d6777b10e686ab851e0a8b8c` found no confirmed vulnerable caller path, but identified a conditional same-process retry risk: if an external caller reuses a long-lived runner and workspace after cleanup failed, a surviving descendant could affect that later invocation. The current command loop already stops within the failed run; this latch extends that fail-stop to later invocations within the same runner process.

## Affected paths and contract

- `tools/vst/runner.py`: `_POSIX_CGROUP_CLEANUP_FAILED` latch, `kill_and_remove`, and distinct-UID launch admission.
- `tests/vst/test_s2_runner_lifecycle.py`: cleanup failure blocks a subsequent launch before cgroup creation/Popen; test-local event isolation.
- `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`, `docs/SANDBOX_SPEC.md`, `tools/vst/schemas/README.md`.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/STATE.md`, `docs/sdlc/STATE.md`, and generated `governance/DOCUMENT_REGISTRY.md`.

## Review and evidence

- `security-reviewer` at exact HEAD `55cc631` found no confirmed issue; raised only the conditional same-process retry path because no production caller was found in the repository. The latch addresses that concern without assuming caller behavior.
- The prior `ce8f7ee` and `55cc631` architecture, reliability, and security reviews remain historical for their exact revisions; fresh reviews are required after this latch commit.
- Test author: `functional-test-reviewer`.
- Pre-commit focused command: `python -m pytest -q tests/vst/test_s2_runner_lifecycle.py -k 'distinct_uid_cgroup_cleanup_failure_is_non_approving or unconfirmed_cgroup_cleanup_latches_later_distinct_uid_launches or gate_environment_timeout_cleans_scope'`.
- Result: 4 passed, 91 deselected, exit 0, 0.93s; one pytest-asyncio deprecation warning. Run at exact prior HEAD `55cc6313dceeffe2d6777b10e686ab851e0a8b8c` plus the uncommitted latch source/test changes; exact-commit rerun is pending.
- The delegated WSL selector passed at `55cc631`; that evidence predates this latch and must be repeated at the final head.
- No CI/build/migration, push/PR, or S2 closure is claimed.

## Ordered next steps

1. Codex: commit the latch, its test, records, and registry.
2. `functional-test-reviewer`: rerun focused E4 selectors at the exact commit.
3. `e2e-runner`: rerun only the cross-UID WSL selector at that exact commit, capturing the live scoped cgroup evidence.
4. Fresh architecture, reliability, security, and silent-failure reviews: inspect the exact head and fix valid findings.
5. Codex: continue S2 acceptance in order; do not start S3 before S2 closes.

## Attribution

Implementation and project records: Codex. Test authorship/execution: `functional-test-reviewer`. Security review that motivated this hardening: `security-reviewer`. Exact-head runtime remains assigned to `e2e-runner`.
