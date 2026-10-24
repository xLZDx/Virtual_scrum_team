# S4 WSL source transfer attempt at 3ba2f35

## Scope and provenance

- Candidate HEAD: `3ba2f35b724da8f2ea5429d781710bbed6612af3` on `s4-native-qa-runner`.
- Pre-run worktree: clean.
- Host: Windows PowerShell, invoked through `C:\Python314\python.exe`.
- WSL target: `Ubuntu-24.04`.
- The previously supplied private runner identity, worker group ID, and snapshot root were used; their values are intentionally excluded from this committed record.
- This was one bounded source-transfer invocation only. No packages were installed, and no native pytest, signer, report, or gate path was invoked.

## Invocation and exact result

Invocation shape, with private POSIX values redacted:

```text
C:\Python314\python.exe -m tools.qa.wsl_snapshot --cwd . --distribution Ubuntu-24.04 --wsl-user [REDACTED] --worker-gid [REDACTED] --snapshot-root [REDACTED]
```

Exact returned response:

```text
{"reason":"snapshot run directory did not receive mode 2710","schema_version":1,"state":"BLOCKED"}
```

No transfer metadata was returned:

- Run ID: `NOT_RETURNED`.
- Candidate HEAD in response: `NOT_RETURNED` (requested candidate was the pre-run HEAD above).
- Bundle digest and byte size: `NOT_RETURNED`.
- Clone owner/group/mode verification: `NOT_RUN`.
- Worker read/write boundary: `NOT_RUN`.
- Receiver-side cause: `UNKNOWN`; the exact error is retained above.

## Containment and next step

No run directory was inspected, retried, cleaned up, or deleted because no run ID was returned. A receiver-side partial destination may exist; its existence and identity are `UNKNOWN`.

Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`). The next step is for the coordinator to resolve the mode-2710 receiver error before authorizing any new attempt. Signer socket, report, receipt, and gate remain separate `NOT_RUN` gates.
