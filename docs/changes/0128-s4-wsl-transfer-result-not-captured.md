# 0128 S4 WSL transfer result not captured

## What changed

- Added `docs/sdlc/evidence/s4-wsl-transfer-e01f8e4.md` with the exact preflight output and the transfer result-capture limitation.
- Updated the S4 backlog and lessons to retain the `RESULT_NOT_CAPTURED` state without inferring success or failure.

## Why

The coordinator requested one bounded transfer from clean HEAD `e01f8e486eb35bbbbe9c7d95e913fa3d0b64b90b`. The command wrapper returned after a 30-second wait without transfer JSON or a captured nested session handle. No run ID was available for a safe scoped verification.

## Affected contracts and paths

- `tools/qa/wsl_snapshot.py`: one bounded source-transfer invocation.
- `docs/sdlc/evidence/s4-wsl-transfer-e01f8e4.md`: exact captured output, missing metadata, and no-inference state.
- `core/BACKLOG.md`, `core/LESSONS_LOG.md`: current runtime status and session-handle retention lesson.
- `governance/DOCUMENT_REGISTRY.md`: generated document inventory.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 work. Executor: Codex (`e2e-runner`).
- Private runner identity, worker group ID, and snapshot root were used but are not committed.
- No WSL destination inspection, permission probe, deletion, retry, native pytest, signer, report, or gate operation was performed.
- The transfer result is `RESULT_NOT_CAPTURED` / `NOT_RETURNED`; no success/failure inference is recorded.

## Verification state

- Pre-run worktree was clean at exact HEAD `e01f8e486eb35bbbbe9c7d95e913fa3d0b64b90b`.
- Command invocation shape and captured preflight output are in the linked evidence. The nested command session handle was not retained after the 30-second wait, and no transfer JSON was delivered.
- No run ID, response HEAD, digest, or byte count was captured; worker-boundary checks are `NOT_RUN`.
- A later local process check found no matching transfer process, which does not establish its result.
- The prior identified transfer in record 0123 remains accepted only for its own exact run. Corrected native E2E remains pending a separately authorized fresh attempt.

## Follow-up

1. For any future bounded transfer, retain the exec session identifier and collect its final response before deciding whether run-scoped verification can proceed.
2. Do not inspect or clean any destination unless that transfer returns a run ID.
3. Obtain separate authorization for a new clean transfer; then run the corrected exact E2E selectors only if metadata and worker-boundary checks pass.
