# 0117 S4 WSL source transfer returned broken pipe

## What changed

- Added `docs/sdlc/evidence/s4-wsl-transfer-895d9f6.md` with the exact result of one bounded source transfer at the new clean candidate HEAD.

## Why

The coordinator authorized one new transfer attempt after the candidate was committed. The attempt returned `BLOCKED` with a broken-pipe error and no run metadata; that result must remain visible without recording private POSIX provisioning values.

## Affected contracts and paths

- `tools/qa/wsl_snapshot.py`: one bounded source-only invocation.
- `docs/sdlc/evidence/s4-wsl-transfer-895d9f6.md`: candidate identity, sanitized invocation, exact returned error, and unverified acceptance boundaries.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`).
- The previously supplied private runner, worker group, and snapshot-root values were used but are not committed.
- No retry, WSL inspection, cleanup, or deletion was performed because no run metadata was returned.
- Native pytest, signer, report, and gate execution were outside this transfer-only task and remain `NOT_RUN`.

## Verification state

- Pre-run worktree was clean at exact HEAD `895d9f6b5cd96a32b94963987d7aca67fe18a9f5`.
- Exact command shape is recorded in the linked evidence; private argument values are redacted.
- Result: `BLOCKED`, `{"reason":"[Errno 32] Broken pipe","schema_version":1,"state":"BLOCKED"}`.
- No run ID, candidate response HEAD, digest, or byte count was returned. Clone permissions and worker read/write behavior are `NOT_RUN`.
- Current repository remains unchanged by the transfer attempt; any possible WSL-side partial run is unknown and was not inspected.

## Follow-up

1. Coordinator determines the receiver/transport cause before authorizing another transfer attempt.
2. A future attempt must use a new clean candidate HEAD; only a response with a run ID permits clone-boundary checks.
3. Resolve the signer socket separately before native QA reporting and gate acceptance.
