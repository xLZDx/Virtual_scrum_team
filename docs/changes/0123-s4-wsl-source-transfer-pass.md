# 0123 S4 WSL source transfer and worker boundary pass

## What changed

- Added `docs/sdlc/evidence/s4-wsl-transfer-e43329f.md` with the successful transfer result and run-scoped clone/read-only verification.
- Updated the S4 backlog and lessons to distinguish per-run source-transfer acceptance from still-unrun native QA/signing/gate work.

## Why

The coordinator authorized one bounded transfer from a clean committed S4 HEAD after receiver fixes. This run returned an ID and matching source bundle metadata, which permitted verification of only that run's clone and worker boundary.

## Affected contracts and paths

- `tools/qa/wsl_snapshot.py`: bounded Windows-to-WSL Git bundle transfer.
- `docs/sdlc/evidence/s4-wsl-transfer-e43329f.md`: candidate, run ID, hash, size, clone modes, worker boundary, and remaining gates.
- `core/BACKLOG.md`, `core/LESSONS_LOG.md`: transfer status and scoped acceptance notes.
- `governance/DOCUMENT_REGISTRY.md`: regenerated document inventory.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 work. Executor: Codex (`e2e-runner`).
- Private runner identity, worker group ID, and snapshot root are not committed.
- Worker probes were limited to the returned run ID. No other destination was listed, opened, cleaned, or deleted.
- No native pytest, signer, report, or gate path was invoked. Signer socket remains a separate unknown gate.

## Verification state

- Pre-run worktree was clean at HEAD `e43329f0d8312c94a0e4316a4d54ece605a79dec`.
- Transfer state `TRANSFERRED`; returned candidate HEAD matched exactly, sender/receiver SHA-256 matched, bundle size was 959285 bytes.
- Runner-side clone verification passed: run mode `2710`, repository root `0750`, 301 filesystem entries with expected owner/group and modes, no symlinks.
- Worker-side probe passed: non-root group member, clone traversable, `README.md` readable, file write open denied, and repository directory nonwritable. The probe performed no writes.
- Exact sanitized outputs are in the linked evidence. No tests, package installs, migrations, or builds were run.

## Follow-up

1. Preserve this run's source-transfer acceptance as scoped to run ID `a198f0afd1c64dc2b960a08f757eff9c` and candidate `e43329f`.
2. Resolve the separate trusted signer socket gate before native report/signature/gate execution.
3. Keep private POSIX provisioning values out of public repository records.
