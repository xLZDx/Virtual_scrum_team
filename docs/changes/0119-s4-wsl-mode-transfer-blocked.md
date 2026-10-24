# 0119 S4 WSL transfer blocked on run-directory mode

## What changed

- Added `docs/sdlc/evidence/s4-wsl-transfer-3ba2f35.md` with the sanitized result of one bounded transfer attempt.
- Updated the S4 backlog to record this third transfer attempt and its exact returned reason.

## Why

The coordinator authorized one source-only transfer on clean HEAD `3ba2f35b724da8f2ea5429d781710bbed6612af3` after the previous receiver change. The receiver returned `BLOCKED` before producing metadata, so the exact result and unverified boundaries must remain visible without recording private POSIX provisioning values.

## Affected contracts and paths

- `tools/qa/wsl_snapshot.py`: one bounded Windows-to-WSL source-transfer invocation.
- `docs/sdlc/evidence/s4-wsl-transfer-3ba2f35.md`: exact output, response metadata state, and containment decision.
- `core/BACKLOG.md`: records the latest native-transfer blocker and next step.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 work. Executor: Codex (`e2e-runner`).
- The previously supplied runner identity, worker group ID, and snapshot-root values were used but are not committed.
- No retry, WSL inspection, clone permission probe, cleanup, or deletion was performed without returned run metadata.
- Technical owner for the transfer receiver remains `UNKNOWN` in repository ownership records.

## Verification state

- Pre-run worktree was clean at exact HEAD `3ba2f35b724da8f2ea5429d781710bbed6612af3`.
- Exact result: `{"reason":"snapshot run directory did not receive mode 2710","schema_version":1,"state":"BLOCKED"}`.
- No run ID, response HEAD, digest, or byte count was returned; clone boundary and worker read/write checks are `NOT_RUN`.
- No native pytest, signer, report, gate, package installation, or migration was run.

## Follow-up

1. Coordinator resolves the receiver's run-directory mode error using local source review and a safe correction.
2. Only a later authorized attempt returning a run ID can proceed to exact HEAD/hash/size and worker read/write verification.
3. Keep signer provisioning separate from source-transfer acceptance.
