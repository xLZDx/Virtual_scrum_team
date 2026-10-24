# S4 WSL source transfer attempt

## Scope and provenance

- Candidate HEAD: `ea008c9ecfdf93dc689614ace957d6dfb7693627` on `s4-native-qa-runner`.
- Pre-run worktree: clean.
- Host: Windows PowerShell; invoked through `C:\Python314\python.exe`.
- WSL distribution: `Ubuntu-24.04`.
- Operator-provided provisioning facts: automount and interop disabled; nftables input/output default-drop with loopback allowed; the private snapshot root and runner/worker identity values had been provisioned and verified. Those POSIX identities and path are intentionally excluded from this public record.
- The native pytest/report path was not invoked. No package was installed.

## Invocation and result

The bounded source-transfer command was invoked once with `--cwd .`, the specified distribution, and the provisioned runner account, worker GID, and private snapshot root. Private argument values are omitted here as required.

The command returned nonzero with:

```text
{"reason":"WSL snapshot transfer failed: <3>WSL (346 - Relay) ERROR: CreateProcessCommon:810: chdir(/nonexistent) failed 2\nsource snapshot directory has an unexpected owner or group","schema_version":1,"state":"BLOCKED"}
```

No transfer response was returned. Therefore:

- Run ID: `NOT_RETURNED`.
- Candidate HEAD in transfer response: `NOT_RETURNED` (the requested source candidate was the pre-run HEAD above).
- Bundle digest and byte size: `NOT_RETURNED`.
- Clone permission verification and worker read/write probes: `NOT_RUN`; no run ID was available to identify the clone safely.
- Signed receipt, native report, and gate evidence: `NOT_RUN` by task scope and signer socket remains a separate unknown gate.

## Failure classification and containment

Classification: **environment/product-boundary failure, exact cause unresolved**. The WSL relay reported that the configured user's initial working directory does not exist, and the transfer receiver rejected a source snapshot directory owner/group check. The command did not return enough metadata to establish whether the clone reached its final verification stage.

Source inspection suggests a possible implementation issue: the receiver chmods the run directory to `0710`, clearing its setgid bit, before Git creates clone descendants, while later checks require those descendants to have the worker group. This is an inference from `tools/qa/wsl_snapshot.py`; actual WSL ownership was not inspected, so the inference is unconfirmed.

No retry, WSL enumeration, partial-tree inspection, permission probe, cleanup, or deletion was performed. Because no run ID was returned, any partial run-scoped directory is unlocated and its existence is `UNKNOWN`. Do not treat the WSL transfer or worker read-only boundary as accepted.

## Next step and ownership

- Accountable task owner: operator under delegated S4 work.
- Executor: Codex (`e2e-runner`).
- Technical owner for WSL provisioning/transfer boundary: `UNKNOWN` in repository ownership records.
- Next step: coordinator reviews the transfer receiver ownership failure and the WSL runner's initial-directory warning, implements or assigns a minimal correction, then requests one fresh bounded transfer attempt on a clean committed candidate. The signer socket remains a separate provisioning gate.
