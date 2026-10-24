# 0051 S2 coordinator setup error cleanup

## What changed

- `tools/vst/lifecycle.py`: directory creation, sidecar open, permission handling, file initialization, flush and OS lock acquisition now share one `OSError` to `AnchorError` boundary. Existing `finally` cleanup closes a partial stream and releases the per-path mutex on setup failure.
- `tools/vst/store.py`: constructor setup and startup reconciliation already close the SQLite connection for typed coordinator `AnchorError`; this behavior remains the explicit resource policy for setup failures.
- Decision/lesson logs and document registry were updated.

## Why

Reliability re-review of `bf58c1b` found directory creation and sidecar file initialization write/flush outside the error-normalization boundary. A raw `OSError` could bypass Store's typed-error cleanup and leak its SQLite connection.

## Verification state

No tests, checks, builds, CI, migrations or runtime probes were run. The E2E owner should test coordinator directory/open/write/flush/lock failures where feasible, and rerun the Windows anchor scenarios on this exact head.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation engineer (`gpt-6-luna`).
- Runtime/test owner: designated E2E agent.
- Next: complete the required E2E rerun after this source head is available.

Agent-Attribution: implementation-engineer (`gpt-6-luna`); Codex executor
