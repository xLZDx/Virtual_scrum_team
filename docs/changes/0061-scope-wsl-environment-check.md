# 0061 Scope correction for WSL environment verification

## What changed

- Added a lesson to `core/LESSONS_LOG.md` documenting that a broad `wsl --list --verbose` query exposed names outside the explicitly requested distribution.
- No other WSL distribution was inspected or modified; no repository product source or test file changed.

## Why

The user authorized a dedicated `Ubuntu-24.04` WSL environment. A direct query to that named distribution was sufficient; enumerating all distributions exceeded the requested project scope.

## Verification state

The command output showed only distribution names and versions. No commands were sent to any distribution other than `Ubuntu-24.04`. This is a process correction, not product acceptance evidence. No tests, checks, builds, CI, migrations, or runtime probes were run for this documentation change. The document registry is regenerated.

## Ownership and next action

- Accountable task owner: operator. Executor: Codex.
- Next: continue all WSL work with explicit `--distribution Ubuntu-24.04` calls only.

Agent-Attribution: Codex executor
