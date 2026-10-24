# S4 WSL transfer attempt with uncaptured result

## Scope and provenance

- Candidate HEAD: `e01f8e486eb35bbbbe9c7d95e913fa3d0b64b90b` on `s4-native-qa-runner`.
- Pre-run worktree: clean.
- Host: Windows PowerShell, invoked through `C:\Python314\python.exe`.
- WSL target: `Ubuntu-24.04`.
- The previously supplied private runner identity, worker group ID, and private snapshot root were used. These POSIX values are not committed.
- The transfer was invoked once. No native pytest, signer, report, or gate path was invoked.

## Invocation and output capture

Invocation shape (private POSIX argument values redacted):

```text
C:\Python314\python.exe -m tools.qa.wsl_snapshot --cwd . --distribution Ubuntu-24.04 --wsl-user [REDACTED] --worker-gid [REDACTED] --snapshot-root [REDACTED]
```

The command wrapper waited 30 seconds. The only captured output was the preflight revision and clean branch status:

```text
e01f8e486eb35bbbbe9c7d95e913fa3d0b64b90b
## s4-native-qa-runner
```

No transfer JSON or receiver error was captured. The nested command session handle was not retained, so its final process result cannot be recovered from this invocation. A later local process check found no matching transfer Python or WSL process, but that does not establish whether the receiver completed successfully.

Transfer state: `RESULT_NOT_CAPTURED` / `NOT_RETURNED`.

- Run ID: `NOT_RETURNED`.
- Candidate HEAD in transfer response: `NOT_RETURNED` (requested candidate was the pre-run HEAD above).
- Bundle digest and byte size: `NOT_RETURNED`.
- Clone ownership/mode and worker read/write checks: `NOT_RUN`.
- Transfer success or failure: `UNKNOWN`; no inference is made.

## Containment and next step

No WSL destination was inspected, deleted, retried, or otherwise acted on because no run ID was returned. Any possible receiver-side partial state remains unidentified and untouched.

This attempt does not add acceptance beyond the prior identified transfer in record 0123. Native E2E on the corrected code requires a separately authorized fresh clean transfer whose invocation result and session handle are captured through completion.

Accountable task owner: operator under delegated S4 work. Executor: Codex (`e2e-runner`).
