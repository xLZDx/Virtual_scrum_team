# S4 WSL source transfer attempt at 895d9f6

## Scope and provenance

- Candidate HEAD: `895d9f6b5cd96a32b94963987d7aca67fe18a9f5` on `s4-native-qa-runner`.
- Pre-run worktree: clean.
- Host: Windows PowerShell, invoked via `C:\Python314\python.exe`.
- WSL target: `Ubuntu-24.04`.
- The previously supplied private runner account, worker group ID, and snapshot root were used. They are intentionally omitted from this committed record.
- The command was limited to source transfer. No package installation or native pytest, signer, report, or gate path was invoked.

## Invocation and exact result

Invocation shape (private POSIX argument values redacted):

```text
C:\Python314\python.exe -m tools.qa.wsl_snapshot --cwd . --distribution Ubuntu-24.04 --wsl-user [REDACTED] --worker-gid [REDACTED] --snapshot-root [REDACTED]
```

The transfer command returned:

```text
{"reason":"[Errno 32] Broken pipe","schema_version":1,"state":"BLOCKED"}
```

No transfer metadata was returned:

- Run ID: `NOT_RETURNED`.
- Candidate HEAD in response: `NOT_RETURNED` (the requested candidate was the pre-run HEAD above).
- Bundle digest and size: `NOT_RETURNED`.
- Clone owner/group/mode verification: `NOT_RUN`.
- Worker read/write boundary: `NOT_RUN`.
- Exact cause: `UNKNOWN`; the command returned only a broken-pipe error.

## Follow-up and limits

The task required one attempt only and prohibited inspection, deletion, or retry without returned run metadata. No further WSL action was taken. A partial run-scoped destination may exist; its existence and identity are `UNKNOWN` and were not investigated.

Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`). The native signer socket, report, receipt, and gate remain separate `NOT_RUN` gates.
