# 0069 S2 source-backed synthetic publishing

## What changed

- `SyntheticOperationBackend` now requires explicit `source_repo` and target bare repository paths.
- Added bounded `git -C <source_repo> push <bare_target> <head>:<ref>` for synthetic branch and pull-request refs. Existing target ref checks and operation-key payload binding are retained.
- Updated the E8 lifecycle harness to pass the worker repository to the backend at initial startup and after restart.
- Updated the S2 S7.2 design and VST schema documentation. No external remote, network path, schema migration, or receipt version change was introduced.

## Why

The E2E scenarios found that worker candidate commits exist in a source repository distinct from the local bare remote, but the prior backend attempted to push from the bare target itself. The E8 candidate head was therefore unavailable to its own backend. The test report and source path are recorded in change record 0068 and `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md`.

## Ownership

- Accountable task owner: operator.
- Executor: Codex.
- Required test author/executor: `e2e-runner`; functional contract tests remain with `functional-test-reviewer`.
- No named technical service owner is established in canonical records.

## Verification state

- Source HEAD before this fix: `cc30917644e762065a6afed3650ad890cf124e22`.
- No tests, checks, builds, CI, migrations, or process-kill scenarios were run by Codex.
- Designated test agents are rerunning their focused regressions after this code batch. Exact head and results will be recorded by their evidence/change record.
- `docs/sdlc/evidence/s2-functional-test-run.md` was pre-existing at task start; it remains untouched and unstaged.
