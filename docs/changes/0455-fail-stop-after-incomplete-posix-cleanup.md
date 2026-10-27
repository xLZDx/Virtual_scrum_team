# Change 0455: fail-stop after incomplete POSIX cleanup

## What changed

- Bound the nonblocking POSIX exec-gate environment handoff by the same deadline as command execution; an expired handoff closes the gate without executing worker code and returns timeout or `EXIT_CAPTURE_INCOMPLETE` according to cleanup evidence.
- Stop launching later commands in both runner APIs after any `EXIT_CAPTURE_INCOMPLETE`. Remaining manifest commands are recorded with exit code -4 and `skipped_after_capture_incomplete=true`; the run cannot pass.
- Updated the S2 cgroup design, sandbox specification, runner schema guide, backlog, state, decision/lessons logs, and document registry.

## Why

The fresh review of change 0454 identified two valid lifecycle gaps. First, the parent wrote worker environment data to a blocking pipe before starting the per-command timeout; a stalled gate could therefore hold the runner beyond its command deadline. Second, if cgroup cleanup could not be confirmed, the manifest loop still launched later commands in the shared run workspace, where a surviving descendant could influence them. Both conditions must fail closed within the same run.

## Affected paths and contract

- `tools/vst/runner.py`: `_write_pipe_before_deadline`, `_run_one`, `run_and_sign`, and `run_manifest_commands`.
- `tests/vst/test_s2_runner_lifecycle.py`: timeout/refusal and both-public-API fail-stop coverage mapped to S2 E4.1 / VST-013.
- `tools/vst/schemas/README.md`, `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`, `docs/SANDBOX_SPEC.md`.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/STATE.md`, `docs/sdlc/STATE.md`, generated `governance/DOCUMENT_REGISTRY.md`.

## Review evidence and decisions

Fresh read-only reviewers at exact code HEAD `ce8f7eeae840d911ae89ae91f0264eec2d540874` found:

- `reliability-reviewer`: MAJOR — later commands could run after unconfirmed cleanup. Fixed by stopping both public command loops and recording later entries as not run.
- `architect`: MINOR — gate setup was outside the command timeout. Fixed by nonblocking pipe writes and a shared deadline beginning before setup.
- `security-reviewer`: no finding in the committed cgroup gate path.

All were GPT-6 Luna, medium effort, read-only reviews. These reviews apply to the previous code head; fresh exact-head reviews remain required after this follow-up commit.

## Verification state

- Test author: `functional-test-reviewer`.
- Pre-commit focused command: `python -m pytest -q tests/vst/test_s2_runner_lifecycle.py -k 'distinct_uid_worker_refuses or distinct_uid_cgroup_gate or distinct_uid_attach_failure or gate_environment_timeout or run_and_sign_stops_after or run_manifest_commands_stops_after'`.
- Result: 9 passed, 85 deselected, exit 0, 0.53s; one pytest-asyncio deprecation warning. This run used the uncommitted working tree based at `ce8f7eeae840d911ae89ae91f0264eec2d540874`; exact-commit rerun is pending.
- The real WSL selector passed at `ce8f7ee` before this follow-up. It is not exact-head evidence for this code. Its active cgroup path/events were not retained.
- No source code changed after the focused run. The protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched.
- No CI/build/migration, push, PR, or S2 closure is claimed.

## Ordered next steps

1. Codex: commit the source, tests, and required records with the generated registry.
2. `functional-test-reviewer`: rerun the focused selectors at the exact new commit.
3. `e2e-runner`: rerun only the cross-UID WSL selector at that commit and preserve the pytest summary and available runtime cgroup evidence in one foreground WSL session.
4. Fresh architecture, reliability, security and silent-failure reviews: inspect the exact post-test head; fix any valid findings and rerun impacted tests.
5. Codex: continue S2 acceptance in order; do not start S3 before S2 closes.

## Attribution

Implementation and project records: Codex. Test authorship and execution: `functional-test-reviewer`. Prior reviews: `architect`, `reliability-reviewer`, `security-reviewer`. Exact-head runtime remains assigned to `e2e-runner`.
