# S4 WSL source transfer and worker boundary at e43329f

## Scope and provenance

- Candidate HEAD: `e43329f0d8312c94a0e4316a4d54ece605a79dec` on `s4-native-qa-runner`.
- Pre-run worktree: clean.
- Host: Windows PowerShell, transfer invoked via `C:\Python314\python.exe`.
- WSL target: `Ubuntu-24.04`.
- Private runner, worker-group, and snapshot-root values were supplied by the operator and used for this run. They are intentionally excluded here.
- Only the bounded source-transfer and run-scoped read-only permission probes were executed. No package installation or native pytest, signer, report, or gate path was used.

## Transfer response

Command shape (private POSIX argument values redacted):

```text
C:\Python314\python.exe -m tools.qa.wsl_snapshot --cwd . --distribution Ubuntu-24.04 --wsl-user [REDACTED] --worker-gid [REDACTED] --snapshot-root [REDACTED]
```

The transfer returned `TRANSFERRED` with:

- Run ID: `a198f0afd1c64dc2b960a08f757eff9c`.
- Candidate HEAD: `e43329f0d8312c94a0e4316a4d54ece605a79dec` (exact match).
- Bundle SHA-256: `922577ae0d8eaca8cb1c3592dc2208dc26f8dbd9f4b249a086705b0b17627bd5`.
- Bundle size: `959285` bytes.

The transfer tool validated equality between its independent Windows sender and WSL receiver bundle digest and byte count.

## Runner-side clone verification

A read-only WSL probe was run as the provisioned runner, scoped only to this returned run ID. It independently verified the bundle bytes/hash, cloned Git HEAD, owner/group and modes, and absence of symbolic links.

Sanitized result:

```json
{"bundle_bytes":959285,"bundle_sha256":"922577ae0d8eaca8cb1c3592dc2208dc26f8dbd9f4b249a086705b0b17627bd5","candidate_head":"e43329f0d8312c94a0e4316a4d54ece605a79dec","error_categories":[],"permission_result":"PASS","repo_entry_count":301,"repo_mode":"0750","run_mode":"2710"}
```

All 301 repository entries passed the expected owner/group and permission checks: directories mode `0750`; files mode `0640` or `0750` based on executable status. The run directory was mode `2710`; the clone root was mode `0750`; the bundle remained runner-only mode `0600`. No symbolic links were found. Probe exit code: `0`.

## Worker boundary verification

A read-only probe ran under the provisioned non-root worker identity and accessed only this run's clone. It opened `README.md` for reading, attempted a non-truncating `O_WRONLY` open and closed without writing, checked repository traversal, and checked repository-directory write access.

Sanitized result:

```json
{"boundary_result":"PASS","error_categories":[],"file_write_denied":true,"readable":true,"repo_directory_write_denied":true,"repo_traversable":true,"worker_group_membership":"PASS","worker_non_root":true}
```

Probe exit code: `0`. The clone was not modified by this probe.

## Remaining gates and ownership

- Source transfer and the run-scoped worker read-only boundary: `PASS` for this exact run only.
- Native pytest/report execution, signer socket, signed receipt, and exact-head VST gate: `NOT_RUN`; the signer socket remains a separate provisioning gate.
- Accountable task owner: operator under delegated S4 work. Executor: Codex (`e2e-runner`). The canonical technical owner for the signer/provisioning service is not established in repository records.
