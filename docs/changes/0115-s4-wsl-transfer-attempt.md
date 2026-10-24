# 0115 S4 WSL source transfer attempt

## What changed

- Added `docs/sdlc/evidence/s4-wsl-transfer-ea008c9.md` with the bounded transfer invocation result and exact acceptance boundary.

## Why

The operator provided verified S4 provisioning inputs and authorized the source-only WSL transfer at clean HEAD `ea008c9ecfdf93dc689614ace957d6dfb7693627`. The attempt returned `BLOCKED`, so the result and unverified permission boundary must be retained without publishing private POSIX values.

## Affected contracts and paths

- `tools/qa/wsl_snapshot.py`: bounded Windows-to-WSL Git bundle transfer.
- `docs/sdlc/evidence/s4-wsl-transfer-ea008c9.md`: non-sensitive command context, exact result, returned metadata state, classification, and follow-up ownership.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 work. Executor: Codex (`e2e-runner`).
- The transfer was invoked once with the operator-provided runner identity, worker group ID, and private snapshot root. These values are not repeated in this record.
- No native test/report path, package install, retry, WSL enumeration, partial-tree inspection, cleanup, or deletion was performed.
- Technical owner for the WSL provisioning/transfer boundary remains `UNKNOWN` in repository records.

## Verification state

- Pre-run worktree was clean at exact HEAD `ea008c9ecfdf93dc689614ace957d6dfb7693627`.
- The bounded source-transfer command returned `BLOCKED` with a WSL `chdir(/nonexistent) failed` warning and receiver rejection `source snapshot directory has an unexpected owner or group`.
- No run ID, bundle digest, or byte count was returned. Clone permission and worker read/write checks are `NOT_RUN`.
- The evidence labels the potential setgid inheritance issue as an unconfirmed inference from receiver source. No code was changed.
- Signer socket, signed receipt, native report, and gate remain separate `NOT_RUN` items.

## Follow-up

1. Coordinator reviews the receiver's directory group check and WSL initial-directory warning; fix or assign the transfer boundary before another attempt.
2. On a new clean committed HEAD, perform one fresh bounded transfer and, only if successful, verify worker read access and write denial for the returned snapshot.
3. Resolve signer socket provisioning separately before native report/signature/gate acceptance.
