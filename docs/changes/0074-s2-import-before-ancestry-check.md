# 0074 S2 import candidate before fast-forward validation

## What changed

- Reordered the hook-free synthetic backend branch update so it imports the requested candidate object pack into the trusted bare target before asking `merge-base --is-ancestor` to validate a fast-forward.
- Rejected non-fast-forward updates still leave the target branch ref unchanged; object imports are content-addressed and harmless when unreferenced.

## Why

Source review found that the previous 0073 ordering checked ancestry before importing a candidate commit that exists only in the source worktree. The target-side `merge-base` therefore cannot resolve the new head. The source diff was uncommitted and no test agent had run the 0073 code yet. This fix makes object availability explicit before the ancestry check.

## Ownership

- Accountable task owner: operator.
- Executor: Codex.
- Runtime test authorship/execution: `e2e-runner` and `functional-test-reviewer` after source completion.

## Verification state

- Previous source head: `4571730a5494ed22c15bfbc6e0a53f55eeb672e4`.
- No tests/checks/builds/CI/migrations were run by Codex.
- The designated E2E agent was asked to hold execution until this commit and will verify source-only candidate transfer and fast-forward behavior.
